# reference-patches

Committed patches for the **gitignored** vendored deps under `reference/`, so the
integration is reproducible on any machine.

## `llm-pysc2.patch`
Integration changes to [LLM-PySC2](https://github.com/NKAI-Decision-Team/LLM-PySC2)
(base commit `551c863` "v0.1"). Apply to a fresh clone:

```bash
git clone https://github.com/NKAI-Decision-Team/LLM-PySC2 reference/LLM-PySC2
git -C reference/LLM-PySC2 apply "$PWD/reference-patches/llm-pysc2.patch"
```

Touches 5 files: `lib/llm_client.py` (Qwen3 no-think + `max_tokens` + JSONL metrics
via `WCB_SC2_METRICS`), `agents/llm_pysc2_agent.py` (FACTORY fallback to `GptClient`),
`agents/main_agent_funcs.py` (analytic one-shot camera calibration),
`bin/llm_smac/2s3z.py` + `bin/llm_pysc2/pvz_task1.py` (`reset_llm` to our vLLM +
`MAX_LLM_QUERY_TIMES`). Full context: `../SC2.md`.
