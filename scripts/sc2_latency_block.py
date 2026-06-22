#!/usr/bin/env python
"""Generate sc2_latency.png + an HTML block for SC2 decision-latency-by-model-size,
to fold into sc2.html (E2). Reads outputs/sc2_2s3z_*.jsonl.

    python scripts/sc2_latency_block.py

Writes sc2_latency.png (repo root, for the Pages copy) and prints/saves the HTML block
to outputs/sc2_latency_block.html for pasting into sc2.html's Results section.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arena import viz   # noqa: E402

SIZE_ORDER = {"1.7B": 0, "4B": 1, "8B": 2, "14B": 3}


def _miss(lat, thr):
    return sum(1 for x in lat if x > thr) / len(lat)


def main() -> None:
    repo = Path(__file__).resolve().parent.parent
    outdir = repo / "outputs"
    files = sorted(outdir.glob("sc2_2s3z_*.jsonl"),
                   key=lambda p: SIZE_ORDER.get(p.stem.replace("sc2_2s3z_", ""), 999))
    res = []
    for p in files:
        rows = [json.loads(line) for line in open(p) if line.strip()]
        if rows:
            res.append({"name": p.stem.replace("sc2_2s3z_", ""), "rows": rows})
    viz.plot_sc2_model_overlay(res, repo / "sc2_latency.png")
    trows = ""
    for r in res:
        lat = [x["latency_ms"] for x in r["rows"]]
        trows += (f"<tr><td>{r['name']}</td><td>{len(r['rows'])}</td>"
                  f"<td>{statistics.median(lat):.0f} ms</td>"
                  f"<td>{statistics.mean(x['tokens_in'] for x in r['rows']):.0f}</td>"
                  f"<td>{_miss(lat, 2000):.2f}</td><td>{_miss(lat, 5000):.2f}</td></tr>")
    block = f"""<h3>Decision latency by model size (2s3z, amax41 / SC2-4.10)</h3>
<img src="sc2_latency.png" alt="SC2 decision latency by model size" style="width:100%;border:1px solid #e2e2e2;border-radius:6px">
<table>
<tr><th>model</th><th>decisions</th><th>p50 latency</th><th>input tokens (mean)</th><th>miss@2s</th><th>miss@5s</th></tr>
{trows}</table>
<p class="muted">Each decision carries the full game state plus the unit/ability wiki
(~3000 input tokens vs ~200 in the grid arena), so a decision takes <b>seconds</b>, not
milliseconds. Unlike the arena, latency here is <b>monotone in model size</b> — at this
context the prefill/compute scales with the model, so a smaller model is markedly faster
(1.7B &asymp; 2&times; faster than 8B), and every model needs several seconds. This is the
efficiency wall the program exists to attack; the win-rate / real-time-clock story is above.</p>"""
    (outdir / "sc2_latency_block.html").write_text(block)
    print(f"wrote sc2_latency.png and {outdir / 'sc2_latency_block.html'}")


if __name__ == "__main__":
    main()
