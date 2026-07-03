# yubopc setup — START HERE (StarCraft II win-rate)

> **For the agent on yubopc:** read this file first, then `SC2.md` for full detail.
> This is the Windows (RTX 4060) setup to run StarCraft II win-rate experiments
> for the *World Commander* benchmark.

## Why this machine
LLM-PySC2 needs **SC2 ≥ 5.0.13**, which Blizzard ships only via **Battle.net on
Windows/Mac** — the Linux headless package caps at 4.10. So win-rate work runs
**here**, not on amax41 (which stays the latency/efficiency box). On SC2 4.10 the
camera never centers units, so the LLM is never queried and win-rate is impossible.

## Hosting note
GitHub is canonical again under the `yuboshell` account (the 2026-06-20 suspension
hit the old `yubohuangai` account; it and the `DreamSoul-AI` org stay retired).
GitLab (`worldcommander/*`) is kept as a mirror: after commits, push both —
`git push && git push gitlab`.

## Steps

**1. Repos (GitHub canonical, GitLab mirror).** Install/auth `gh` first
(`winget install GitHub.cli`; then `gh auth login`). Clone:
- `https://github.com/yuboshell/world-commander-bench.git`  ← this repo
- `https://github.com/yuboshell/world-commander.git`  (research docs)
- `https://gitlab.com/huangyubo/memex.git`  (my knowledge base, optional; GitLab-tracked)

Then add the mirror remote to the two world-commander repos:
`git remote add gitlab https://gitlab.com/worldcommander/<repo>.git`

**2. SC2 5.0.x.** Install via the Battle.net client (latest retail is ≥5.0.13).
Then copy `reference/LLM-PySC2/llm_pysc2/maps/{llm_smac,llm_pysc2}` into the retail
install's `Maps/` folder. pysc2 auto-detects the Battle.net install; else set `SC2PATH`.

**3. LLM-PySC2** (the `reference/` tree is gitignored — clone upstream + apply the
committed patch):
```
git clone https://github.com/NKAI-Decision-Team/LLM-PySC2 reference/LLM-PySC2
git -C reference/LLM-PySC2 apply ../../reference-patches/llm-pysc2.patch
```
Create a **Python 3.9** env, `pip install -e reference/LLM-PySC2`, plus `sniffio anyio`.
Run pysc2 as **Windows-native** Python so it can launch the Windows SC2 binary.

**4. vLLM.** Qwen3-4B-AWQ fits the 4060's 8 GB. Run it in **WSL2** (Linux + CUDA);
Windows reaches it at `127.0.0.1:8001` via WSL2 localhost forwarding. Set
`WCB_SC2_API_BASE=http://127.0.0.1:8001/v1` (and `WCB_SC2_MODEL=Qwen/Qwen3-4B-AWQ`).

> **Use `127.0.0.1`, not `localhost`.** On Windows, `localhost` resolves to IPv6 `::1` first and stalls
> ~21 s per request before falling back to IPv4 — it added ~21 s to *every* SC2 decision (~27 s instead
> of ~6 s). `127.0.0.1` forces IPv4 and removes it. Verified: 0.09 s vs 21 s time-to-first-token.
Arch is Ada (sm_89) — use a normal AWQ serve (no Turing `--enforce-eager` hack needed).

**5. Run.** `pvz_task1` and SMAC `2s3z` (commands in `SC2.md`). On 5.0.x the camera
centers, the LLM is actually queried, and **win-rate becomes meaningful**. Log
per-decision metrics with `WCB_SC2_METRICS=<path>.jsonl`. Report win-rate + latency.

## Then
Layer on our real-time clock (wall-clock decision deadlines, drop late actions,
VRAM ceiling) — the same primitives validated in the command arena. See `SC2.md`
→ *Win-rate on yubopc* and the repo's `CLAUDE.md` for project conventions.
