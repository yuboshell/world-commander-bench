# StarCraft II bring-up (LLM-PySC2)

Reproducible recipe for running the SC2 testbed against our **own** vLLM. The
harness code is vendored (gitignored) in `reference/LLM-PySC2`; the integration
**patches below live only in that copy**, so re-apply them if you re-clone it.

Status (2026-06-20): **LLM decisions firing end-to-end** in `2s3z` against
Qwen3-4B-AWQ on GPU 2. First real numbers: ~6 s per decision, ~4000 input tokens
(SC2 state + wiki) / ~230 output tokens, 0 errors. SC2's long context makes a
decision ~10x slower than the arena — the core efficiency problem, now measured.

**Correction:** an earlier note claimed a "smoke test passing" with 120 LLM
actions. That was wrong — those were rule-based camera-calibration moves; vLLM saw
0 requests. The LLM only fires after the fix below.

**Two integration issues found:**
- SMAC camera calibration does not converge on SC2 4.10, so the agent never
  reached the LLM. Worked around with a **calibration cap** (`WCB_SC2_CALIB_CAP`,
  patch in `main_agent_funcs.py`) that forces the agent to proceed after N steps.
  Win-rate is therefore not yet meaningful (centering imperfect); latency/token
  metrics are valid. Proper calibration is a later fix.
- The `pvz_task*` custom maps segfault SC2 4.10 (`-11`) — they likely need a
  different game version. SMAC maps load fine.

**Clock caveat:** LLM-PySC2 is synchronous (the game waits for the model), so this
measures per-decision latency honestly but does not yet enforce the unpausable
clock — that is our real-time layer, still to add.

## Components
- **Game**: SC2 4.10 Linux (`Base75689`), from `http://blzdistsc2-a.akamaihd.net/Linux/SC2.4.10.zip`
  (unzip password `iagreetotheeula`). Installed at `/mnt/yubo/StarCraftII`; point at it with `SC2PATH`.
- **Maps**: copied `reference/LLM-PySC2/llm_pysc2/maps/{llm_smac,llm_pysc2}` into `$SC2PATH/Maps/`.
- **Env**: conda `llm-pysc2` (python 3.9), `pip install -e reference/LLM-PySC2`
  plus `sniffio anyio` (missing transitive deps of `zhipuai`). Uses `openai==0.28`
  (legacy SDK) — kept separate from the bench venv's `openai>=1.0`.
- **Model**: our controllable vLLM on GPU 2 (`CUDA_VISIBLE_DEVICES=2`, port 8001),
  e.g. `vllm serve Qwen/Qwen3-4B-AWQ --quantization awq --max-model-len 8192
  --enforce-eager --dtype half`.

## Integration patches (in `reference/LLM-PySC2`, re-apply if re-cloned)
1. `llm_pysc2/lib/llm_client.py` → `gpt_query_runtime`: add `max_tokens=512` and
   `chat_template_kwargs={"enable_thinking": False}` to `ChatCompletion.create`
   (Qwen3 otherwise spends the budget on `<think>` and never answers — same gotcha
   as the arena). openai 0.28 forwards these as request-body fields to vLLM.
2. `llm_pysc2/agents/llm_pysc2_agent.py`: `FACTORY[self.model_name]` →
   `FACTORY.get(self.model_name, llm_client.GptClient)` (2 sites), so an arbitrary
   served id (e.g. `Qwen/Qwen3-4B-AWQ`) routes to the OpenAI client and is sent verbatim.
3. `llm_pysc2/bin/llm_smac/2s3z.py`: after `config = ConfigSmac_2s3z()`, call
   `config.reset_llm(model_name=$WCB_SC2_MODEL, api_base=$WCB_SC2_API_BASE, api_key='EMPTY')`
   (env-overridable).

## Run the smoke test
```bash
# 1. serve our model on GPU 2
CUDA_VISIBLE_DEVICES=2 ~/enter/envs/vllm/bin/vllm serve Qwen/Qwen3-4B-AWQ \
  --host 127.0.0.1 --port 8001 --quantization awq --max-model-len 8192 \
  --enforce-eager --dtype half &
# 2. run 2s3z headless
cd reference/LLM-PySC2
SC2PATH=/mnt/yubo/StarCraftII WCB_SC2_API_BASE=http://127.0.0.1:8001/v1 \
~/enter/envs/llm-pysc2/bin/python -m pysc2.bin.agent \
  --map 2s3z --agent_race protoss --parallel 1 --norender \
  --max_episodes 1 --max_agent_steps 60 \
  --agent llm_pysc2.bin.llm_smac.2s3z.MainAgentLLMSmac
```

## Next
- This proves the loop drives the game. It is **not** yet our benchmark: add the
  real-time layer (wall-clock decision deadlines, drop late actions, VRAM ceiling,
  metric logging) on top — the same primitives validated in the arena.
- Scale the model up for real win-rate runs; sweep KV-cache policies (long SC2
  context is where that finally bites) on our own vLLM.
