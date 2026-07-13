#!/usr/bin/env bash
# Two identical flat-sweep passes on H100 to verify text-mode ISL determinism.
set -uo pipefail
cd "$(dirname "$0")/.."
export NODE=h100 VLLM_CNAME=an-hao-vllm-nvfp4 CONTAINER_NAME=an-hao-vllm-nvfp4 \
       CPREFIX=an-hao-aiperf HF_DIR=$HOME/900g/an-hao/hf VLLM_CACHE=$HOME/900g/an-hao/vllm-cache \
       POINTS="c2 c8 c32"
for OB in results/nvfp4/h100 results/nvfp4/h100run2; do
  echo "######## PASS $OB $(date "+%F %T") ########"
  OUTBASE=$OB STOP_AFTER=0 bash scripts/run_nvfp4.sh chatbot_flat agent_flat coding_flat
done
docker rm -f an-hao-vllm-nvfp4
echo "######## DOUBLE RUN DONE $(date "+%F %T") ########"
