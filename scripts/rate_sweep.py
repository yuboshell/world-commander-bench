#!/usr/bin/env python
"""Command-stream load curves: how fast can commands arrive before the model
falls behind its deadline?

    python scripts/rate_sweep.py --deadline-ms 500

Reuses the per-command latency sequences already recorded by the model-size
sweep (outputs/model_*.json), so it needs **no GPU**: each model's real latencies
are replayed through a single-server FIFO queue (arena.rate) at a grid of arrival
rates. Emits outputs/rate_sweep.json + outputs/rate_frontier.png and prints each
model's sustainable command rate (highest rate with <= threshold unmet).

The streaming thesis made measurable: a faster (smaller) model sustains a higher
command rate before backlog pushes responses past the deadline.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arena.rate import load_curve              # noqa: E402
from arena import viz                          # noqa: E402


def _load_models(indir: str, pattern: str) -> list[dict]:
    models = []
    for f in sorted(glob.glob(str(Path(indir) / pattern))):
        d = json.load(open(f))
        lat = [r["lat"] for r in d.get("rows", []) if "lat" in r]
        if not lat:
            continue
        mean_lat = sum(lat) / len(lat)
        models.append({
            "label": d.get("label", Path(f).stem),
            "model": d.get("model", ""),
            "latencies_ms": lat,
            "mean_lat_ms": mean_lat,
            "service_hz": 1000.0 / mean_lat if mean_lat else 0.0,
        })
    return models


def _sustainable_rate(rows: list[dict], threshold: float) -> float:
    """Highest rate whose unmet_rate is within threshold (0 if even the slowest misses)."""
    ok = [r["rate_hz"] for r in rows if r["unmet_rate"] <= threshold]
    return max(ok) if ok else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--indir", default="outputs")
    ap.add_argument("--outdir", default="outputs")
    ap.add_argument("--pattern", default="model_*.json")
    ap.add_argument("--deadline-ms", type=float, default=500.0)
    ap.add_argument("--rate-min", type=float, default=None, help="Hz; default auto from service rates")
    ap.add_argument("--rate-max", type=float, default=None)
    ap.add_argument("--rate-steps", type=int, default=25)
    ap.add_argument("--queue-cap", type=int, default=None, help="bounded in-system queue; default unbounded")
    ap.add_argument("--threshold", type=float, default=0.1, help="unmet fraction defining 'sustainable'")
    args = ap.parse_args()

    models = _load_models(args.indir, args.pattern)
    if not models:
        sys.exit(f"no model_*.json with per-command 'lat' found in {args.indir}/")

    services = [m["service_hz"] for m in models if m["service_hz"] > 0]
    lo = args.rate_min if args.rate_min is not None else 0.2 * min(services)
    hi = args.rate_max if args.rate_max is not None else 2.0 * max(services)
    step = (hi - lo) / (args.rate_steps - 1)
    rates = [round(lo + i * step, 4) for i in range(args.rate_steps)]

    for m in models:
        m["rows"] = load_curve(m["latencies_ms"], rates, args.deadline_ms, args.queue_cap)
        m["sustainable_hz"] = _sustainable_rate(m["rows"], args.threshold)
    models.sort(key=lambda m: m["service_hz"], reverse=True)  # fastest first

    Path(args.outdir).mkdir(parents=True, exist_ok=True)
    out_json = Path(args.outdir) / "rate_sweep.json"
    # drop the raw latency arrays from the saved summary (keep it small)
    summary_models = [{k: v for k, v in m.items() if k != "latencies_ms"} for m in models]
    json.dump({"deadline_ms": args.deadline_ms, "queue_cap": args.queue_cap,
               "threshold": args.threshold, "rates_hz": rates, "models": summary_models},
              open(out_json, "w"), indent=2)
    png = viz.plot_rate_frontier(models, args.deadline_ms, Path(args.outdir) / "rate_frontier.png")

    print(f"deadline {args.deadline_ms:.0f} ms, queue_cap={args.queue_cap}, "
          f"rates {rates[0]:.2f}..{rates[-1]:.2f} Hz")
    print(f"{'model':>10} {'service Hz':>11} {'sustainable Hz':>15}  (unmet <= "
          f"{args.threshold:.0%})")
    for m in models:
        print(f"{m['label']:>10} {m['service_hz']:>11.2f} {m['sustainable_hz']:>15.2f}")
    print(f"\nwrote {out_json} and {png}")


if __name__ == "__main__":
    main()
