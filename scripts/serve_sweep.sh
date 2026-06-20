#!/usr/bin/env bash
# Serve each model on GPU 2 (port 8001), run the arena, tear down, next.
# Teardown is scoped to GPU 2 + port 8001 ONLY — it never touches a server on
# another port/GPU (e.g. a shared vLLM on :8000).
#
#   VLLM_BIN=/path/to/vllm CUDA_DEVICE=2 bash scripts/serve_sweep.sh
set -uo pipefail
cd "$(dirname "$0")/.."

VLLM_BIN="${VLLM_BIN:-vllm}"
CUDA_DEVICE="${CUDA_DEVICE:-2}"
PORT=8001
PY=.venv/bin/python
COMMANDS="${COMMANDS:-90}"

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
  echo "=== $(date +%H:%M:%S) serving $label : $model $extra ==="
  teardown
  CUDA_VISIBLE_DEVICES="$CUDA_DEVICE" "$VLLM_BIN" serve "$model" \
    --host 127.0.0.1 --port "$PORT" --max-model-len 4096 \
    --gpu-memory-utilization 0.85 --enforce-eager --dtype half $extra \
    > "/tmp/wcb-vllm-$label.log" 2>&1 &
  ready=0
  for _ in $(seq 1 120); do   # up to ~10 min for download + warmup
    if [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$PORT/v1/models)" = "200" ]; then
      ready=1; break
    fi
    sleep 5
  done
  if [ "$ready" = 1 ]; then
    echo "=== $(date +%H:%M:%S) $label ready; running arena ==="
    $PY scripts/run_one_model.py --base-url "http://127.0.0.1:$PORT/v1" \
      --model "$model" --label "$label" --commands "$COMMANDS" --tick-ms 500 \
      --out "outputs/model_$label.json"
  else
    echo "!!! $label FAILED to start"; tail -8 "/tmp/wcb-vllm-$label.log"
  fi
  teardown
}

run_model 0.6B Qwen/Qwen3-0.6B ""
run_model 1.7B Qwen/Qwen3-1.7B ""
run_model 4B Qwen/Qwen3-4B-AWQ "--quantization awq"
run_model 8B Qwen/Qwen3-8B-AWQ "--quantization awq"
run_model 14B Qwen/Qwen3-14B-AWQ "--quantization awq"
echo "=== $(date +%H:%M:%S) SWEEP DONE ==="
