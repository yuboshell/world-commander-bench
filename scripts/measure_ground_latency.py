#!/usr/bin/env python3
"""Grounding-latency decomposition experiment.

Splits the SC2 LLM call into three conditions on the SAME real game state, and measures
prefill (time-to-first-token) vs decode (rest) via streaming:

  A  full reasoning   : real prompt (system + observation) -> Analysis + Actions   (the status quo)
  B  ground-only,full : same full state, but only resolve a fixed NL command -> <Attack_Unit(tag)>
  C  ground-only,shrunk: minimal state (just the enemy list) + the same command -> <Attack_Unit(tag)>

A vs B isolates the decode savings (removing reasoning); B vs C isolates the prefill lever
(shrinking the state). All against the live vLLM (Qwen3-4B-AWQ) at :8001.
"""
import urllib.request, json, time, re

BASE  = "http://localhost:8001/v1/chat/completions"
MODEL = "Qwen/Qwen3-4B-AWQ"
LOGD  = "/mnt/c/Users/yuboh/github/world-commander-bench/reference/LLM-PySC2/llm_log/20260621201701-1/CombatGroupSmac"
OUT   = "/mnt/c/Users/yuboh/github/world-commander-bench/outputs/ground_latency_results_cold.txt"
STEP  = 0          # opening 8v8 — the heaviest (richest) state
RUNS  = 3
CMD   = "Focus fire the lowest-health enemy unit."

def rd(p): return open(p, encoding="utf-8", errors="replace").read()

system = rd(f"{LOGD}/prompt.txt")
obs    = json.loads([l for l in rd(f"{LOGD}/o.txt").splitlines() if l.strip()][STEP])[str(STEP)]
m      = re.search(r"Nearby Enemy Units:(.*?)(?:\n\n|\Z)", obs, re.S)
enemy  = "Nearby Enemy Units:" + (m.group(1) if m else "")

NOTHINK = " /no_think"   # match the harness (its outputs carry no <think> block)
GROUND  = (f'\n\nYour commander\'s order: "{CMD}"\n'
           "Output ONLY the single action line in the form <Attack_Unit(tag)> for the correct "
           "enemy unit — no analysis, no other text.")
cond = {
  "A full-reasoning":     (system + "\n" + obs + "\n\nNow, start generating your analysis and actions:" + NOTHINK, 320),
  "B ground / full-state":(system + "\n" + obs + GROUND + NOTHINK, 48),
  "C ground / shrunk":    ("You control StarCraft II units. Visible enemy units:\n" + enemy + GROUND + NOTHINK, 48),
}

def measure(prompt, max_tokens):
    prompt = f"(unique request {time.time_ns()})\n" + prompt   # bust vLLM prefix cache -> COLD prefill
    payload = {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
               "max_tokens": max_tokens, "temperature": 0.0, "stream": True,
               "stream_options": {"include_usage": True}}
    req = urllib.request.Request(BASE, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time(); ttft = None; usage = None; text = ""
    with urllib.request.urlopen(req) as r:
        for raw in r:
            ln = raw.decode("utf-8", "replace").strip()
            if not ln.startswith("data:"): continue
            d = ln[5:].strip()
            if d == "[DONE]": break
            ch = json.loads(d)
            chs = ch.get("choices") or []
            if chs and chs[0].get("delta", {}).get("content"):
                if ttft is None: ttft = time.time() - t0
                text += chs[0]["delta"]["content"]
            if ch.get("usage"): usage = ch["usage"]
    return ttft, time.time() - t0, usage, re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()

lines = []
def log(s):
    print(s, flush=True); lines.append(s)

# warmup (discarded — first call after idle pays a one-off penalty)
measure("Say OK." + NOTHINK, 8)

log(f"Grounding-latency decomposition (COLD / cache-busted) — {MODEL}, step {STEP}, median of {RUNS}")
log(f"{'condition':24} {'in_tok':>7} {'out_tok':>7} {'prefill':>8} {'decode':>7} {'total':>7}")
res = {}
for name, (prompt, mt) in cond.items():
    runs = []; out = ""
    for _ in range(RUNS):
        ttft, total, usage, text = measure(prompt, mt)
        runs.append((ttft or 0.0, total, usage)); out = text
    runs.sort(key=lambda x: x[1]); ttft, total, usage = runs[len(runs)//2]
    pin = usage.get("prompt_tokens", 0); pout = usage.get("completion_tokens", 0)
    dec = total - ttft; res[name] = (pin, pout, ttft, dec, total)
    log(f"{name:24} {pin:7d} {pout:7d} {ttft:7.2f}s {dec:6.2f}s {total:6.2f}s")
    log(f"    grounded -> {out[:140]}")

a = res["A full-reasoning"]; b = res["B ground / full-state"]; c = res["C ground / shrunk"]
log("")
log(f"A->B (drop reasoning): total {a[4]:.1f}s -> {b[4]:.1f}s  ({a[4]-b[4]:+.1f}s; mostly decode)")
log(f"B->C (shrink state):   total {b[4]:.1f}s -> {c[4]:.1f}s  ({b[4]-c[4]:+.1f}s; prefill)")
log(f"A->C (both):           total {a[4]:.1f}s -> {c[4]:.1f}s  ({a[4]/max(c[4],0.01):.1f}x faster)")
open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\nwrote", OUT)
