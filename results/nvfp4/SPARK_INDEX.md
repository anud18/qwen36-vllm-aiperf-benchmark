# Output file index — spark local reproduction, 2026-08-04

Every artifact produced while reproducing the `optimumxt` Dynamo endpoint benchmarks on **spark
itself** (NVIDIA GB10, aarch64, 119 GB unified memory) against `vllm/vllm-openai:v0.24.0` at
`max-model-len 4096`. All paths are relative to `~/benchmark/results/nvfp4/`.

**26 points, 13 per model. All completed: 0 errors, `osl_mismatch_count = 0`.**

| report | contents |
|---|---|
| [`SPARK_REPRO.md`](SPARK_REPRO.md) | The report — endpoint and spark figures side by side per point, prefill/decode throughput, parity method, findings |
| [`INDEX_optimumxt.md`](INDEX_optimumxt.md) | Index of the **endpoint-side** artifacts being reproduced, and which of those are invalid |
| `SPARK_INDEX.md` | This file |

## Benchmark points

### Llama-3.1-8B-Instruct — `spark_repro_llama31/`

| point directory | workload | conc. | reqs | warmup | ISL total | OSL total | duration | valid |
|---|---|--:|--:|--:|--:|--:|--:|---|
| [`spark_repro_llama31/w2_chatbot_c1/chatbot_flat/c1/`](spark_repro_llama31/w2_chatbot_c1/chatbot_flat/c1/) | chatbot_flat | 1 | 10 | 2 | 6,199 | 2,790 | 202.7 s | ✅ |
| [`spark_repro_llama31/w2_chatbot_c2/chatbot_flat/c2/`](spark_repro_llama31/w2_chatbot_c2/chatbot_flat/c2/) | chatbot_flat | 2 | 20 | 2 | 12,518 | 6,080 | 216.4 s | ✅ |
| [`spark_repro_llama31/w2_chatbot_c1_rep/chatbot_flat/c1/`](spark_repro_llama31/w2_chatbot_c1_rep/chatbot_flat/c1/) | chatbot_flat | 1 | 10 | 2 | 6,199 | 2,790 | 202.5 s | ✅ |
| [`spark_repro_llama31/w2_agent_c1/agent_flat/c1/`](spark_repro_llama31/w2_agent_c1/agent_flat/c1/) | agent_flat | 1 | 10 | 2 | 16,967 | 2,344 | 172.3 s | ✅ |
| [`spark_repro_llama31/w0_chatbot_c1/chatbot_flat/c1/`](spark_repro_llama31/w0_chatbot_c1/chatbot_flat/c1/) | chatbot_flat | 1 | 20 | 0 | 12,176 | 5,970 | 433.1 s | ✅ |
| [`spark_repro_llama31/w0_agent_c1/agent_flat/c1/`](spark_repro_llama31/w0_agent_c1/agent_flat/c1/) | agent_flat | 1 | 20 | 0 | 33,226 | 4,766 | 350.3 s | ✅ |
| [`spark_repro_llama31/w0_chatbot_c1_rep/chatbot_flat/c1/`](spark_repro_llama31/w0_chatbot_c1_rep/chatbot_flat/c1/) | chatbot_flat | 1 | 20 | 0 | 12,176 | 5,970 | 434.1 s | ✅ |
| [`spark_repro_llama31/w0_agent_c2/agent_flat/c2/`](spark_repro_llama31/w0_agent_c2/agent_flat/c2/) | agent_flat | 2 | 20 | 0 | 33,226 | 4,766 | 168.1 s | ✅ |
| [`spark_repro_llama31/r100_chatbot_c1/chatbot_flat/c1/`](spark_repro_llama31/r100_chatbot_c1/chatbot_flat/c1/) | chatbot_flat | 1 | 100 | 0 | 65,546 | 24,723 | 1,799.0 s | ✅ |
| [`spark_repro_llama31/r100_agent_c1/agent_flat/c1/`](spark_repro_llama31/r100_agent_c1/agent_flat/c1/) | agent_flat | 1 | 100 | 0 | 163,441 | 22,348 | 1,642.4 s | ✅ |
| [`spark_repro_llama31/r100_chatbot_c2/chatbot_flat/c2/`](spark_repro_llama31/r100_chatbot_c2/chatbot_flat/c2/) | chatbot_flat | 2 | 100 | 0 | 65,546 | 24,723 | 859.8 s | ✅ |
| [`spark_repro_llama31/r100_agent_c2/agent_flat/c2/`](spark_repro_llama31/r100_agent_c2/agent_flat/c2/) | agent_flat | 2 | 100 | 0 | 163,441 | 22,348 | 784.4 s | ✅ |
| [`spark_repro_llama31/c32_chatbot/chatbot_flat/c32/`](spark_repro_llama31/c32_chatbot/chatbot_flat/c32/) | chatbot_flat | 32 | 320 | 16 | 212,802 | 78,337 | 226.4 s | ✅ |

### Qwen3-VL-30B-A3B-Instruct — `spark_repro_qwen3vl/`

| point directory | workload | conc. | reqs | warmup | ISL total | OSL total | duration | valid |
|---|---|--:|--:|--:|--:|--:|--:|---|
| [`spark_repro_qwen3vl/w2_chatbot_c1/chatbot_flat/c1/`](spark_repro_qwen3vl/w2_chatbot_c1/chatbot_flat/c1/) | chatbot_flat | 1 | 10 | 2 | 5,937 | 2,790 | 94.3 s | ✅ |
| [`spark_repro_qwen3vl/w2_chatbot_c2/chatbot_flat/c2/`](spark_repro_qwen3vl/w2_chatbot_c2/chatbot_flat/c2/) | chatbot_flat | 2 | 20 | 2 | 12,040 | 6,080 | 137.3 s | ✅ |
| [`spark_repro_qwen3vl/w2_chatbot_c1_rep/chatbot_flat/c1/`](spark_repro_qwen3vl/w2_chatbot_c1_rep/chatbot_flat/c1/) | chatbot_flat | 1 | 10 | 2 | 5,937 | 2,790 | 92.3 s | ✅ |
| [`spark_repro_qwen3vl/w2_agent_c1/agent_flat/c1/`](spark_repro_qwen3vl/w2_agent_c1/agent_flat/c1/) | agent_flat | 1 | 10 | 2 | 16,864 | 2,344 | 81.2 s | ✅ |
| [`spark_repro_qwen3vl/w0_chatbot_c1/chatbot_flat/c1/`](spark_repro_qwen3vl/w0_chatbot_c1/chatbot_flat/c1/) | chatbot_flat | 1 | 20 | 0 | 11,698 | 5,970 | 197.4 s | ✅ |
| [`spark_repro_qwen3vl/w0_agent_c1/agent_flat/c1/`](spark_repro_qwen3vl/w0_agent_c1/agent_flat/c1/) | agent_flat | 1 | 20 | 0 | 33,160 | 4,766 | 162.2 s | ✅ |
| [`spark_repro_qwen3vl/w0_chatbot_c1_rep/chatbot_flat/c1/`](spark_repro_qwen3vl/w0_chatbot_c1_rep/chatbot_flat/c1/) | chatbot_flat | 1 | 20 | 0 | 11,698 | 5,970 | 197.3 s | ✅ |
| [`spark_repro_qwen3vl/w0_agent_c2/agent_flat/c2/`](spark_repro_qwen3vl/w0_agent_c2/agent_flat/c2/) | agent_flat | 2 | 20 | 0 | 33,160 | 4,766 | 109.0 s | ✅ |
| [`spark_repro_qwen3vl/r100_chatbot_c1/chatbot_flat/c1/`](spark_repro_qwen3vl/r100_chatbot_c1/chatbot_flat/c1/) | chatbot_flat | 1 | 100 | 0 | 63,251 | 24,723 | 829.2 s | ✅ |
| [`spark_repro_qwen3vl/r100_agent_c1/agent_flat/c1/`](spark_repro_qwen3vl/r100_agent_c1/agent_flat/c1/) | agent_flat | 1 | 100 | 0 | 161,083 | 22,411 | 766.8 s | ✅ |
| [`spark_repro_qwen3vl/r100_chatbot_c2/chatbot_flat/c2/`](spark_repro_qwen3vl/r100_chatbot_c2/chatbot_flat/c2/) | chatbot_flat | 2 | 100 | 0 | 63,251 | 24,723 | 551.8 s | ✅ |
| [`spark_repro_qwen3vl/r100_agent_c2/agent_flat/c2/`](spark_repro_qwen3vl/r100_agent_c2/agent_flat/c2/) | agent_flat | 2 | 100 | 0 | 161,083 | 22,411 | 508.5 s | ✅ |
| [`spark_repro_qwen3vl/c32_chatbot/chatbot_flat/c32/`](spark_repro_qwen3vl/c32_chatbot/chatbot_flat/c32/) | chatbot_flat | 32 | 320 | 16 | 206,916 | 78,337 | 513.5 s | ✅ |

`w2` = `WARMUP=2`, `w0` = `WARMUP=0`, `r100` = 100 requests on context-filtered datasets,
`c32` = the point that wedged the Dynamo worker. Trace slices: `w2` uses `[2:...]`, everything
else `[0:...]`.

Qwen and Llama ISL totals differ from each other by design — different tokenizers over the same
text. Each matches *its own* endpoint exactly wherever a valid endpoint point exists; see the
parity section of [`SPARK_REPRO.md`](SPARK_REPRO.md).

## Driver logs

| file | what it covers |
|---|---|
| [`spark_repro_llama31.log`](spark_repro_llama31.log) | all 13 Llama points, with per-point start/end timestamps |
| [`spark_repro_qwen3vl.log`](spark_repro_qwen3vl.log) | all 13 Qwen points |

## Scripts

| file | purpose |
|---|---|
| `../../scripts/serve_optimumxt_repro.sh` | brings up vLLM for either model at 4096 context; `MODEL_KEY=llama31\|qwen3vl` |
| `../../scripts/run_optimumxt_repro.sh` | runs all 13 points for one model, in the order the endpoint runs happened |
| `../../scripts/chat_templates/llama31_dynamo.jinja` | Llama 3.1 template with the system block Dynamo applied — **required for ISL parity**, worth exactly 25 tokens/request |
| `../../scripts/filter_le4096.py` | drops trace entries over the context cap; tokenizer-dependent, so it is rerun per model |

`scripts/serve_nvfp4.sh` was deliberately **not** reused — it hardcodes `--reasoning-parser qwen3`,
wrong for Llama, and would alter the measured output.

## Datasets

| path | used by | notes |
|---|---|---|
| `../../datasets/aiperf/nvfp4_{chatbot,agent}_flat.jsonl` | `w2` and `w0` series | unmodified |
| `../../datasets/aiperf/le4096/` | Llama `r100` series | agent kept 279/384 |
| `../../datasets/aiperf/le4096_qwen3vl/` | Qwen `r100` series | agent kept 277/384 |

Filtering is tokenizer-dependent, which is why the two models keep different entry counts — their
`r100 agent` points are therefore not identical workloads *to each other*, though each matches its
own endpoint counterpart.

## Artifact layout

Each point directory holds the same files as the endpoint runs — see the *Artifact layout* section
of [`INDEX_optimumxt.md`](INDEX_optimumxt.md). Two differences:

- `prefix.json` is `{"unavailable": true}` on **all 26 points**. `REMOTE=1` was kept so the
  workloads match the endpoint runs, which could not reset the prefix cache or read `/metrics`;
  vLLM's OpenAI API also returns `prompt_tokens_details: null`, so aiperf has no per-request cache
  figure either. Prefix cache hit rates are therefore missing from the local side.
- `inputs.json` and `logs/` are not committed, matching the existing `results/` convention.

## Serving configuration

| | Llama-3.1-8B | Qwen3-VL-30B-A3B |
|---|---|---|
| weights | `NousResearch/Meta-Llama-3.1-8B-Instruct` (15 GB) | `Qwen/Qwen3-VL-30B-A3B-Instruct` (58 GB) |
| gpu-memory-utilization | 0.60 | 0.88 |
| GPU KV cache | 426,496 tokens | 479,504 tokens |
| max concurrency @ 4096 | 104.1× | 117.1× |
| chat template | **overridden** — see scripts table | stock |

The official `meta-llama/Llama-3.1-8B-Instruct` repo is gated; the NousResearch mirror carries
identical weights but a stripped chat template, hence the override.

## Reproduce

```bash
cd ~/benchmark

MODEL_KEY=llama31 bash scripts/serve_optimumxt_repro.sh
MODEL_KEY=llama31 bash scripts/run_optimumxt_repro.sh

docker run --rm --entrypoint python -v $PWD:/w -w /w \
  -v $HOME/.cache/huggingface:/root/.cache/huggingface aiperf:local \
  scripts/filter_le4096.py --tokenizer Qwen/Qwen3-VL-30B-A3B-Instruct \
  --out datasets/aiperf/le4096_qwen3vl
MODEL_KEY=qwen3vl bash scripts/serve_optimumxt_repro.sh
MODEL_KEY=qwen3vl bash scripts/run_optimumxt_repro.sh
```
