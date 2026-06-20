#!/usr/bin/env bash
# Serve each model on GPU 2 and run the 2s3z SC2 task with per-decision metrics.
# Teardown is scoped to GPU 2 + port 8001 ONLY (never the shared :8000 server).
#
#   VLLM_BIN=/path/to/vllm bash scripts/sc2_model_sweep.sh
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
VLLM_BIN="${VLLM_BIN:-vllm}"
CUDA_DEVICE="${CUDA_DEVICE:-2}"
PORT=8001
PYREF="${PYREF:-/home/yubo/enter/envs/llm-pysc2/bin/python}"
SC2PATH_VAL="${SC2PATH:-/mnt/yubo/StarCraftII}"

teardown() {
  pkill -f -- "--port $PORT" 2>/dev/null || true
  uuid=$(nvidia-smi --query-gpu=index,uuid --format=csv,noheader | awk -F', ' -v d="$CUDA_DEVICE" '$1==d{print $2}')
  for p in $(nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | awk -F', ' -v u="$uuid" '$1==u{print $2}'); do
    kill -TERM "$p" 2>/dev/null || true
  done
  for _ in $(seq 1 40); do
    used=$(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader,nounits | awk -F', ' -v d="$CUDA_DEVICE" '$1==d{print $2}')
    [ "${used:-9999}" -lt 800 ] && break
    sleep 2
  done
}

run_model() {
  label="$1"; model="$2"; extra="${3:-}"
  echo "=== $(date +%H:%M:%S) serve $label : $model $extra ==="
  teardown
  CUDA_VISIBLE_DEVICES="$CUDA_DEVICE" "$VLLM_BIN" serve "$model" \
    --host 127.0.0.1 --port "$PORT" --max-model-len 8192 \
    --gpu-memory-utilization 0.85 --enforce-eager --dtype half $extra \
    > "/tmp/wcb-vllm-sc2-$label.log" 2>&1 &
  for _ in $(seq 1 120); do
    [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$PORT/v1/models)" = "200" ] && break
    sleep 5
  done
  rm -f "$ROOT/outputs/sc2_2s3z_$label.jsonl"
  ( cd reference/LLM-PySC2 && \
    SC2PATH="$SC2PATH_VAL" WCB_SC2_API_BASE="http://127.0.0.1:$PORT/v1" \
    WCB_SC2_MODEL="$model" WCB_SC2_CALIB_CAP=12 \
    WCB_SC2_METRICS="$ROOT/outputs/sc2_2s3z_$label.jsonl" \
    timeout 540 "$PYREF" -m pysc2.bin.agent \
      --map 2s3z --agent_race protoss --parallel 1 --norender \
      --max_episodes 8 --max_agent_steps 2000 \
      --agent llm_pysc2.bin.llm_smac.2s3z.MainAgentLLMSmac \
      > "/tmp/wcb-sc2-$label.log" 2>&1 ) || true
  n=$(wc -l < "$ROOT/outputs/sc2_2s3z_$label.jsonl" 2>/dev/null || echo 0)
  echo "=== $(date +%H:%M:%S) $label: $n decisions ==="
  teardown
}

run_model 1.7B Qwen/Qwen3-1.7B ""
run_model 8B Qwen/Qwen3-8B-AWQ "--quantization awq"
echo "=== $(date +%H:%M:%S) SC2 MODEL SWEEP DONE ==="
