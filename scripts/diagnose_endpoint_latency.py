#!/usr/bin/env python3
"""Is the harness's ~28s/call the Windows<->WSL2 network boundary? Same call, run from Windows (conda,
where the harness lives) vs from WSL (where vLLM lives). Self-contained (no file reads)."""
import urllib.request, json, time, sys, platform
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001/v1/chat/completions"
MODEL = "Qwen/Qwen3-4B-AWQ"
para = ("Protoss Stalkers are ranged units with the Blink ability; Zealots are melee units with Charge. "
        "Focus fire the lowest-health enemy and retreat damaged units. ") * 180   # ~5k-token input
prompt = para + "\n\nIn about 200 words, summarize the tactics above. /no_think"

def run(stream):
    payload = {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
               "max_tokens": 256, "temperature": 0.1, "stream": stream}
    if stream: payload["stream_options"] = {"include_usage": True}
    req = urllib.request.Request(BASE, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    t0 = time.time(); ttft = None; usage = None
    with urllib.request.urlopen(req) as r:
        if not stream:
            data = json.loads(r.read()); return None, time.time() - t0, data.get("usage")
        for raw in r:
            ln = raw.decode("utf-8", "replace").strip()
            if not ln.startswith("data:"): continue
            d = ln[5:].strip()
            if d == "[DONE]": break
            ch = json.loads(d); chs = ch.get("choices") or []
            if chs and chs[0].get("delta", {}).get("content") and ttft is None: ttft = time.time() - t0
            if ch.get("usage"): usage = ch["usage"]
    return ttft, time.time() - t0, usage

print(f"env: {platform.system()} py{platform.python_version()}  base={BASE}")
_, t, u = run(False)
print(f"  NON-STREAM total={t:5.2f}s  in={u['prompt_tokens']} out={u['completion_tokens']}  -> {1000*t/max(u['completion_tokens'],1):.0f} ms/tok")
ttft, t, u = run(True)
print(f"  STREAM     total={t:5.2f}s  prefill={ttft:.2f}s decode={t-ttft:5.2f}s out={u['completion_tokens']}  -> {1000*(t-ttft)/max(u['completion_tokens'],1):.0f} ms/tok decode")
