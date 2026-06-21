#!/usr/bin/env bash
# Firm macro-capability curve: representation_sweep --fresh (macro, xy framing) at
# n=COMMANDS across model sizes. GPU-2 models are served + torn down one at a time
# (teardown scoped to GPU2 + port 8001 ONLY — never the shared :8000); 14B uses the
# shared :8000 (it won't fit + serve alone on one 2080 Ti).
#
#   VLLM_BIN=/path/to/vllm CUDA_DEVICE=2 COMMANDS=200 bash scripts/macro_curve.sh
set -uo pipefail
cd "$(dirname "$0")/.."

VLLM_BIN="${VLLM_BIN:-vllm}"
CUDA_DEVICE="${CUDA_DEVICE:-2}"
PORT=8001
PY=.venv/bin/python
COMMANDS="${COMMANDS:-200}"

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

run_gpu_model() {
  label="$1"; model="$2"; extra="${3:-}"
  echo "=== $(date +%H:%M:%S) serve $label : $model $extra ==="
  teardown
  CUDA_VISIBLE_DEVICES="$CUDA_DEVICE" "$VLLM_BIN" serve "$model" \
    --host 127.0.0.1 --port "$PORT" --max-model-len 8192 \
    --gpu-memory-utilization 0.85 --enforce-eager --dtype half $extra \
    > "/tmp/wcb-macrocurve-$label.log" 2>&1 &
  ready=0
  for _ in $(seq 1 120); do
    if [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$PORT/v1/models)" = "200" ]; then ready=1; break; fi
    sleep 5
  done
  if [ "$ready" = 1 ]; then
    $PY scripts/representation_sweep.py --base-url "http://127.0.0.1:$PORT/v1" \
      --model "$model" --tag "cap_$label" --commands "$COMMANDS" --fresh --styles xy
  else
    echo "!!! $label FAILED to start"; tail -6 "/tmp/wcb-macrocurve-$label.log"
  fi
  teardown
}

echo "=== $(date +%H:%M:%S) 14B via shared :8000 (no serve) ==="
$PY scripts/representation_sweep.py --base-url http://127.0.0.1:8000/v1 \
  --model Qwen/Qwen3-14B-AWQ --tag cap_14B --commands "$COMMANDS" --fresh --styles xy
run_gpu_model 1.7B Qwen/Qwen3-1.7B ""
run_gpu_model 4B Qwen/Qwen3-4B-AWQ "--quantization awq"
run_gpu_model 8B Qwen/Qwen3-8B-AWQ "--quantization awq"
echo "=== $(date +%H:%M:%S) MACRO CURVE DONE ==="
