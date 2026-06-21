#!/usr/bin/env python
"""Quantify the prefix-cache lever for an SC2-scale static prefix.

    python scripts/prefix_cache_sweep.py --base-url http://127.0.0.1:8001/v1 --model Qwen/Qwen3-4B-AWQ

A decision's context is mostly STATIC (system prompt + unit/ability wiki) with a small
changing game-state/command suffix. With vLLM prefix caching (default ON), serve the
SAME large static prefix + a varying suffix → the prefix is cached after warmup.
Compare against UNIQUE-prefix requests (cache defeated). The gap is the per-decision
prefill saving caching buys for a long but reused context. Writes outputs/prefix_cache.json.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arena.config import load_config           # noqa: E402
from arena.model_client import SYSTEM          # noqa: E402

WIKI = "Unit Stalker: ranged, blink. Ability Blink: short teleport. Note: irrelevant. "


def _p50(xs):
    return round(statistics.median(xs), 1) if xs else 0.0


def main() -> None:
    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8001/v1")
    ap.add_argument("--model", default="Qwen/Qwen3-4B-AWQ")
    ap.add_argument("--prefix-tokens", type=int, default=3000)
    ap.add_argument("--reps", type=int, default=12)
    ap.add_argument("--outdir", default="outputs")
    a = ap.parse_args()

    from openai import OpenAI
    client = OpenAI(base_url=a.base_url, api_key=cfg.api_key)
    static = WIKI * max(1, a.prefix_tokens // 12)        # WIKI ~12 tokens

    def call(prompt):
        t0 = time.perf_counter()
        r = client.chat.completions.create(
            model=a.model,
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": prompt}],
            temperature=0.0, max_tokens=16,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}})
        return (time.perf_counter() - t0) * 1000.0, r.usage.prompt_tokens

    # cached: shared static prefix, varying suffix (warm the cache first)
    for w in range(2):
        call(static + "\nOrder: move the red agent north.\nMoves:")
    cached, ptoks = [], None
    for i in range(a.reps):
        lat, ptoks = call(static + f"\nOrder: move agent {i} north.\nMoves:")
        cached.append(lat)

    # uncached: unique prefix each call -> no reuse
    uncached = []
    for i in range(a.reps):
        lat, _ = call(f"[uniq {i}] " + static + f"\nOrder: move agent {i} north.\nMoves:")
        uncached.append(lat)

    res = {"model": a.model, "prefix_tokens": ptoks, "reps": a.reps,
           "cached_p50": _p50(cached), "uncached_p50": _p50(uncached),
           "saving_ms": round(_p50(uncached) - _p50(cached), 1)}
    print(res)
    Path(a.outdir).mkdir(parents=True, exist_ok=True)
    json.dump(res, open(Path(a.outdir) / "prefix_cache.json", "w"), indent=2)
    print("wrote", Path(a.outdir) / "prefix_cache.json")


if __name__ == "__main__":
    main()
