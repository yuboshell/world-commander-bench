#!/usr/bin/env python
"""Decompose macro: LLM maps intent→primitive, code does the geometry.

    python scripts/intent_decompose.py --base-url http://127.0.0.1:8001/v1 --model Qwen/Qwen3-4B-AWQ

The macro-capability curve showed LLMs are bad at goal *planning* (per-agent geometry)
but the region result showed they're fine at *reference*. And the geometry is trivially
computable in code (`toward_dirs`/`away_dirs`). So the efficient design is: the LLM only
classifies the order into a goal primitive (converge/scatter/home/flee) — easy intent
understanding — and code executes it exactly. This measures the classification accuracy;
effective macro grounding under decomposition ≈ that accuracy (execution is exact).
Compare with the LLM doing the geometry itself (~0.38 on 4B). Writes outputs/intent_decompose.json.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arena.commands import MACRO_FORMS, sample_command   # noqa: E402
from arena.config import load_config                     # noqa: E402
from arena.world import GridWorld                         # noqa: E402

PRIMS = ["converge", "scatter", "home", "flee"]
SYS = ("Map the order to exactly one primitive and reply with ONLY that word.\n"
       "converge = move toward the centre; scatter = spread out from the centre; "
       "home = go to the top-left corner; flee = move away from the nearest enemy.")


def main() -> None:
    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8001/v1")
    ap.add_argument("--model", default="Qwen/Qwen3-4B-AWQ")
    ap.add_argument("--per-form", type=int, default=30)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--outdir", default="outputs")
    a = ap.parse_args()

    from openai import OpenAI
    client = OpenAI(base_url=a.base_url, api_key=cfg.api_key)

    def classify(text):
        r = client.chat.completions.create(
            model=a.model,
            messages=[{"role": "system", "content": SYS},
                      {"role": "user", "content": f'Order: "{text}"\nPrimitive:'}],
            temperature=0.0, max_tokens=8,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}})
        reply = (r.choices[0].message.content or "").lower()
        for p in PRIMS:
            if p in reply:
                return p
        return "?"

    per_form, correct, total, confusion = {}, 0, 0, {}
    for fi, form in enumerate(MACRO_FORMS):
        ok = 0
        for i in range(a.per_form):
            w = GridWorld.random_init(cfg.grid, cfg.agents, cfg.npcs,
                                      rng=random.Random(a.seed + 1000 * (fi + 1) + i))
            cmd = sample_command(w, random.Random(a.seed + 7000 + i), forms=[form])
            pred = classify(cmd.text)
            confusion[(form, pred)] = confusion.get((form, pred), 0) + 1
            ok += int(pred == form)
        per_form[form] = round(ok / a.per_form, 3)
        correct += ok
        total += a.per_form
        print(f"{form:>9}: {per_form[form]:.3f}")

    acc = round(correct / total, 3)
    print(f"overall intent-classification accuracy: {acc}")
    Path(a.outdir).mkdir(parents=True, exist_ok=True)
    json.dump({"model": a.model, "per_form": per_form, "accuracy": acc,
               "confusion": {f"{k[0]}->{k[1]}": v for k, v in confusion.items()}},
              open(Path(a.outdir) / "intent_decompose.json", "w"), indent=2)
    print("wrote", Path(a.outdir) / "intent_decompose.json")


if __name__ == "__main__":
    main()
