#!/usr/bin/env python
"""Latency vs context length: why SC2 (~3000-token state) is ~10x slower than the
arena (~200 tokens). Pads the prompt to increasing input-token counts and measures
decision latency at fixed (short) output — isolating the prefill/context cost.

    python scripts/context_latency.py --base-url http://127.0.0.1:8001/v1 --model Qwen/Qwen3-4B-AWQ

Writes outputs/context_latency.json.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arena.commands import sample_command          # noqa: E402
from arena.config import load_config               # noqa: E402
from arena.model_client import SYSTEM              # noqa: E402
from arena.world import GridWorld                  # noqa: E402

FILLER = "Irrelevant background state included only to pad the context window. "


def main() -> None:
    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8001/v1")
    ap.add_argument("--model", default="Qwen/Qwen3-4B-AWQ")
    ap.add_argument("--pads", default="0,300,800,1800,2800,3800", help="approx pad tokens")
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--outdir", default="outputs")
    a = ap.parse_args()
    pads = [int(x) for x in a.pads.split(",")]

    from openai import OpenAI
    client = OpenAI(base_url=a.base_url, api_key=cfg.api_key)
    w = GridWorld.random_init(cfg.grid, cfg.agents, cfg.npcs, rng=random.Random(0))
    cmd = sample_command(w, random.Random(0))
    base = f"{w.render_text()}\nOrder: \"{cmd.text}\"\nMoves:"

    rows = []
    for pad in pads:
        prompt = FILLER * max(0, pad // 9) + base    # FILLER ~9 tokens
        lats, ptoks = [], None
        for _ in range(a.reps):
            t0 = time.perf_counter()
            resp = client.chat.completions.create(
                model=a.model,
                messages=[{"role": "system", "content": SYSTEM},
                          {"role": "user", "content": prompt}],
                temperature=0.0, max_tokens=16,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}})
            lats.append((time.perf_counter() - t0) * 1000.0)
            ptoks = resp.usage.prompt_tokens
        row = {"target_pad": pad, "prompt_tokens": ptoks,
               "lat_p50": round(statistics.median(lats), 1),
               "lat_mean": round(statistics.mean(lats), 1)}
        rows.append(row)
        print(row)

    Path(a.outdir).mkdir(parents=True, exist_ok=True)
    out = Path(a.outdir) / "context_latency.json"
    json.dump({"model": a.model, "rows": rows}, open(out, "w"), indent=2)
    print("wrote", out)


if __name__ == "__main__":
    main()
