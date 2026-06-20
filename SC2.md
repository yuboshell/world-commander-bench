# StarCraft II bring-up (LLM-PySC2)

Reproducible recipe for running the SC2 testbed against our **own** vLLM. The
harness code is vendored (gitignored) in `reference/LLM-PySC2`; the integration
changes are captured as a committed patch at **`reference-patches/llm-pysc2.patch`**
(see *Integration patches* below) so any machine can reproduce them.

> Repo path note: the code tree was renamed `/mnt/yubo/github` → **`/mnt/yubo/repos`**
> (a `github → repos` compat symlink keeps old paths working). SC2 itself lives
> outside it at `/mnt/yubo/StarCraftII`.

## ⚠️ Platform split — read first
LLM-PySC2 requires **SC2 ≥ 5.0.13 (Base 92440)** (its `docs/problems.md`). But
**Blizzard's public *Linux* headless package stops at 4.10** (2019): `SC2.4.10.zip`
is the newest downloadable build; every ≥4.11 / 5.0.x URL is 404. Newer builds
ship only via **Battle.net** (Windows/Mac retail). Consequence:

| Machine | SC2 | What it's good for |
|---|---|---|
| **amax41** (Linux) | 4.10 (only option) | **decision latency / token economy** — valid |
| **yubopc** (Windows, RTX 4060) | 5.0.x via Battle.net | **win-rate** (correct camera/maps) |

On SC2 4.10 the agent's camera-centering (`get_camera_xy` → `move_camera`) does
**not** place units at screen-center, so after calibration the per-unit gate in
`get_camera_func_smart` loops forever and the **LLM is never queried** — and the
`pvz_task*` maps segfault (`-11`). Both are 4.10↔(≥5.0.13) version-mismatch
symptoms. **Win-rate is therefore not achievable on amax41**; do it on yubopc.

## Status (2026-06-20)
- **Latency/tokens (amax41, 4.10):** measured and valid. ~6 s/decision for
  Qwen3-4B-AWQ at ~3000–4000 input tokens (SC2 state + wiki) / ~230 output, 0 errors.
  Latency monotone in model size (p50 1.7B 2.7 s / 4B 4.5 s / 8B 5.3 s / 14B 7.5 s);
  all miss a 2 s deadline; synchronous throughput 0.22 dec/s (4B) → 0.11 (14B).
- **Calibration:** the original quarter-step camera-centering never converged on
  4.10; replaced with an **analytic one-shot offset** (converges in ~4 steps —
  `校准完成True`). The fix is correct and carries to 5.0.x, but on 4.10 it's gated
  behind the broken downstream centering above, so it doesn't yet yield win-rate.
- **Win-rate:** blocked on SC2 version → pending yubopc (5.0.x).
- *History/correction:* an earlier note claimed a "120-action smoke test"; those
  were camera moves, not LLM calls. The earlier `WCB_SC2_CALIB_CAP` force-proceed
  hack has been **removed** in favor of the analytic fix.

**Clock caveat:** LLM-PySC2 is synchronous (the game waits for the model) — honest
per-decision latency, but it does not yet enforce the unpausable real-time clock
(our layer, still to add).

## Components
- **Game**: amax41 → SC2 4.10 Linux (`Base75689`), from
  `http://blzdistsc2-a.akamaihd.net/Linux/SC2.4.10.zip` (unzip password
  `iagreetotheeula`), at `/mnt/yubo/StarCraftII` (`SC2PATH`). yubopc → SC2 5.0.x
  via Battle.net (pysc2 auto-detects the retail install, or set `SC2PATH`).
- **Maps**: copy `reference/LLM-PySC2/llm_pysc2/maps/{llm_smac,llm_pysc2}` into `$SC2PATH/Maps/`.
- **Env**: conda `llm-pysc2` (python 3.9), `pip install -e reference/LLM-PySC2`
  plus `sniffio anyio` (missing transitive deps of `zhipuai`). Uses `openai==0.28`
  (legacy SDK) — separate from the bench venv's `openai>=1.0`.
- **Model**: our controllable vLLM (`CUDA_VISIBLE_DEVICES=2`, port 8001), e.g.
  `vllm serve Qwen/Qwen3-4B-AWQ --quantization awq --max-model-len 8192
  --enforce-eager --dtype half`. (On yubopc, run vLLM in WSL2 and let the Windows
  pysc2 process reach it via `localhost:8001`.)

## Integration patches → `reference-patches/llm-pysc2.patch`
Apply against a fresh upstream clone (base commit `551c863` "v0.1"):
```bash
git clone https://github.com/NKAI-Decision-Team/LLM-PySC2 reference/LLM-PySC2
git -C reference/LLM-PySC2 apply ../../reference-patches/llm-pysc2.patch
```
What the patch does (5 files):
1. `lib/llm_client.py` → `gpt_query_runtime`: add `max_tokens=512` +
   `chat_template_kwargs={"enable_thinking": False}` (Qwen3 otherwise burns the
   budget on `<think>`); plus per-decision JSONL metrics via `WCB_SC2_METRICS`.
2. `agents/llm_pysc2_agent.py`: `FACTORY[name]` → `FACTORY.get(name, GptClient)`
   so any served id (e.g. `Qwen/Qwen3-4B-AWQ`) routes to the OpenAI client verbatim.
3. `agents/main_agent_funcs.py`: **analytic one-shot calibration** — replace the
   quarter-step iteration with an exact offset (`Δoffset = err_px · SCREEN_WORLD_GRID
   / size_screen`), accept within a realistic tolerance or after a few corrections.
4. `bin/llm_smac/2s3z.py` + `bin/llm_pysc2/pvz_task1.py`: `config.reset_llm(model_name=
   $WCB_SC2_MODEL, api_base=$WCB_SC2_API_BASE, api_key='EMPTY')` + `MAX_LLM_QUERY_TIMES`.

## Run (amax41 — latency only)
```bash
# 1. serve our model on GPU 2
CUDA_VISIBLE_DEVICES=2 ~/enter/envs/vllm/bin/vllm serve Qwen/Qwen3-4B-AWQ \
  --host 127.0.0.1 --port 8001 --quantization awq --max-model-len 8192 \
  --enforce-eager --dtype half &
# 2. run 2s3z headless (calibration now converges; LLM fires on a ≥5.0.13 build)
cd reference/LLM-PySC2
SC2PATH=/mnt/yubo/StarCraftII WCB_SC2_API_BASE=http://127.0.0.1:8001/v1 \
WCB_SC2_METRICS=$PWD/../../outputs/sc2_metrics.jsonl \
~/enter/envs/llm-pysc2/bin/python -m pysc2.bin.agent \
  --map 2s3z --agent_race protoss --parallel 1 --norender \
  --max_episodes 1 --max_agent_steps 60 \
  --agent llm_pysc2.bin.llm_smac.2s3z.MainAgentLLMSmac
```

## Win-rate on yubopc (next)
1. Mirror repos from GitLab (`worldcommander/` group; see the GitHub-suspension notes).
2. Install **SC2 5.0.x** via Battle.net; copy the LLM-PySC2 maps into the retail `Maps/`.
3. Clone upstream LLM-PySC2 + `git apply reference-patches/llm-pysc2.patch`; set up the py3.9 env.
4. Serve a small vLLM in WSL2 (4B-AWQ fits 8 GB); point `WCB_SC2_API_BASE` at it.
5. Run `pvz_task1` / SMAC — on 5.0.x the camera centers, the LLM is queried, and
   win-rate becomes meaningful. Then layer on our real-time clock + deadline drops.
