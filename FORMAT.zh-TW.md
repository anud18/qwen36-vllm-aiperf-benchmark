# 各 dataset 如何格式化並送進 LLM(中文版)

每個 workload 分三層說明,以下摘錄**全部是真實資料**,取自本 repo:

1. **原始資料** — 逐字取自 `datasets/raw/`(chatbot 取自 aiperf 的 ShareGPT cache)
2. **我轉換後的 JSONL** — 逐字取自 `datasets/aiperf/`
3. **實際送出的 payload** — 逐字取自 aiperf 執行紀錄 `results/<wl>/inputs.json`(aiperf 會把它組出的每一筆 request body 存檔)

過長欄位以真實長度標註截斷,例如 `…(50,266 字元)`。

## 共通機制(已從實際 payload 驗證)

- 請求都打到 vLLM 的 OpenAI **`/v1/chat/completions`**。我給的 `text` 會變成一則 **`user`** message;vLLM 再用 Qwen3.6 chat template(`<|im_start|>role…<|im_end|>`)把 `messages` 渲染成模型實際看到的 token 序列。
- 我 JSONL 裡的 `output_length` 實際送出時是 **`max_completion_tokens`**(限制生成長度)。
- `extra` 會淺合併進 request body —— 所以 `{"chat_template_kwargs": {"enable_thinking": false}}` 出現在 payload 頂層,vLLM 據此關閉 reasoning 區塊(coding 與 RAG 使用)。
- **multi_turn**:`inputs.json` 每個 turn 只存「該輪的*新* user message」;實際送出時 aiperf 會把對話歷史接在前面,其中 assistant 輪是模型**自己先前真實生成的回覆**(dataset 裡的 gpt 文字永遠不會被送出)。
- Qwen3.6 預設會輸出 chain-of-thought → chatbot/agent/toolagent 維持 thinking **開**;短輸出的 coding/RAG 則**關**。

## 每個 dataset 被拆成幾筆 request

拆分規則(已用 `inputs.json` 與 run CSV 驗證):

- **single_turn / mooncake_trace**:1 行 JSONL → **1 筆 request**。
- **multi_turn**:1 行(一個 session)→ **每個 turn 一筆 request**(6-turn session = 6 筆,依序送出、自動累積歷史)。
- 實際執行多少由 `--request-count`(總請求數)或 `--conversation-num`(session 數,選中的 session 所有 turns 都會跑)決定。帶 `timestamp` 的 trace(fixed-schedule)會無視兩者、**全量回放**。

| Workload | 轉換檔 | potential requests | pass-1 實際執行 | sweep 每個 level 實際執行 |
|---|---|--:|--:|--:|
| Chatbot | (ShareGPT 內建:載入 73,277 sessions / 252,196 turns) | 252,196 | 100(`--request-count 100`) | 40(`--request-count 40`) |
| Coding | `coding_multiturn.jsonl` — 100 sessions × 6 turns | 600 | 10(預設 `--request-count 10`) | **60** = 10 conv × 6 turns(`--conversation-num 10`;59 成功 + 1 error) |
| RAG | `rag_singleturn.jsonl` — 500 行 | 500 | 300(`--request-count 300`) | 80(`--request-count 80`) |
| Agent | `agent_multiturn.jsonl` — 200 sessions / 887 turns(每個 2–7 turns) | 887 | 10(預設) | **53** = 前 12 個 conv 的 turns 總和(`--conversation-num 12`) |
| Toolagent | `toolagent_mooncake.jsonl` — 2,000 行 / `toolagent_concurrency.jsonl` — 40 行 | 2,000 / 40 | 2,000 全量嘗試(fixed-schedule,timeout) | 40(39 成功 + 1 error) |

注意:`inputs.json` 記錄的是**整個載入的 dataset**(所有 potential payloads),不是實際執行的子集 —— 例如 chatbot 的 `inputs.json` 有 25 萬筆 payload,但 pass-1 只送了 100 筆。實際數要看 CSV 的 `Request Count`。

---

## 1) Chatbot — ShareGPT(`--public-dataset sharegpt`)

**原始資料**(aiperf 自動下載的 cache `.cache/aiperf/datasets/ShareGPT_V3_unfiltered_cleaned_split.json`,94,145 筆):

```jsonc
{"id": "...", "conversations": [
  {"from": "human", "value": "Summarize the main ideas of Jeff Walker's Product Launch Formula into bullet points as it pertains to a growth marketing agency implementing…"},
  {"from": "gpt",   "value": "Here are the main ideas of Jeff Walker's Product Launch Formula that can be applied by a growth marketing agency for their clients:\n\n1. Iden…"},
  …]}
```

**轉換**:我不經手 —— aiperf 自己組 multi-turn session:human 輪當 prompt,gpt 輪的 token 數當該輪的 `max_completion_tokens`。

**實際送出**(`results/chatbot/inputs.json`,session_000000,共 6 turns):

```jsonc
// turn 0
{"messages": [{"role": "user", "content": "Summarize the main ideas of Jeff Walker's Product Launch Formula into bullet points as it pertains to a growth marketing agency implementing these strategies and tactics for their clients..."}],
 "model": "qwen3.6", "stream": true, "max_completion_tokens": 252}

// turn 1(新的 user message;送出時 aiperf 會在前面接上 turn-0 的 user + 模型真實的 turn-0 回覆)
{"messages": [{"role": "user", "content": "Summarize the main ideas of Brendon Burchard's Experts Academy into bullet points as it pertains to a growth marketing agency implementing these strategies and tactics for their clients..."}],
 "model": "qwen3.6", "stream": true, "max_completion_tokens": 329}
```

---

## 2) Coding — `coding_multiturn.jsonl`(`--custom-dataset-type multi_turn`)

**原始資料**(`datasets/raw/codex_swebenchpro.json`,610 筆,每筆 12–200 turns)。第 0 筆的前三個 turn:

```jsonc
{"conversations": [
  {"from": "human", "value": "<permissions instructions>\nFilesystem sandboxing defines which files can be read or written. `sandbox_mode` is `danger-full-access`: No filesystem sandboxing - all commands are permitted. Network access is enabled.\nApproval policy is currently never. Do not pr…(50,266 字元:permissions + skills + repo context 前綴)"},
  {"from": "gpt",   "value": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua…(844 字元 — 匿名化的佔位文字,永遠不會被送出)"},
  {"from": "human", "value": "Command: /bin/bash -lc \"rg -n \\\"class VarsWithSources|def combine_vars|DEFAULT_HASH_BEHAVIOUR|\\\\|=\\\" /app/lib /app/test\"\nChunk ID: 2cc537\nWall time: 0.2416 seconds\nProcess exited with code 0\nOriginal …(11,581 字元:回灌的工具輸出)"},
  …]}
```

**我的轉換**(`scripts/build_datasets.py` 的 `build_coding`):只保留 **human** 輪當 `turns`;`output_length` = 其後 gpt 輪長度估算的 token 數(字元/4,上限 512);關 thinking。`datasets/aiperf/coding_multiturn.jsonl` 第一行(session codex_0,保留 6 turns):

```jsonc
{"session_id": "codex_0", "turns": [
  {"text": "<permissions instructions>\nFilesystem sandboxing defines which files can be read or written…(50,266 字元)", "output_length": 211, "extra": {"chat_template_kwargs": {"enable_thinking": false}}},
  {"text": "Command: /bin/bash -lc \"rg -n \\\"class VarsWithSources…\"\nChunk ID: 2cc537…(11,581 字元)", "output_length": 258, "extra": {"chat_template_kwargs": {"enable_thinking": false}}},
  …再 4 個 turns…]}
```

**實際送出**(`results/coding/inputs.json`,codex_0):

```jsonc
// turn 0 — 50 KB 前綴
{"messages": [{"role": "user", "content": "<permissions instructions>\nFilesystem sandboxing defines which files can be read or written. `sandbox_mode` is `danger-full-access`…(50,266 字元)"}],
 "model": "qwen3.6", "stream": true, "max_completion_tokens": 211,
 "chat_template_kwargs": {"enable_thinking": false}}

// turn 1 — 新的工具輸出;送出時歷史 = [turn-0 的 user(50 KB)+ 模型真實的 turn-0 回覆]
{"messages": [{"role": "user", "content": "Command: /bin/bash -lc \"rg -n \\\"class VarsWithSources|def combine_vars|DEFAULT_HASH_BEHAVIOUR|\\\\|=\\\" /app/lib /app/test\"\nChunk ID: 2cc537\nWall time: 0.2416 seconds…(11,581 字元)"}],
 "model": "qwen3.6", "stream": true, "max_completion_tokens": 258,
 "chat_template_kwargs": {"enable_thinking": false}}
```

→ 每一輪都透過累積歷史重送那 50 KB 前綴 ⇒ **高 prefix-cache 命中**(實測:ISL ≈ 26K tokens 但 TTFT 約 3 秒,而非冷 prefill 的約 25 秒)。

---

## 3) RAG — `rag_singleturn.jsonl`(`--custom-dataset-type single_turn`)

**原始資料**(`datasets/raw/MultiHopRAG.json`,2,556 個 query + `corpus.json` 609 篇新聞)。第 0 筆:

```jsonc
{"query": "Who is the individual associated with the cryptocurrency industry facing a criminal trial on fraud and conspiracy charges, as reported by both The Verge and TechCrunch, and is accused by prosecutors o…",
 "answer": "Sam Bankman-Fried",
 "question_type": "inference_query",
 "evidence_list": [
   {"title": "The FTX trial is bigger than Sam Bankman-Fried", "source": "The Verge",
    "fact": "Before his fall, Bankman-Fried made himself out to be the Good Boy of crypto…"},
   …]}

// corpus.json 中以 title 對應到的文章(evidence title → corpus body,命中率 100%)
{"title": "The FTX trial is bigger than Sam Bankman-Fried", "source": "The Verge",
 "body": "The trial of Sam Bankman-Fried is likely to be more consequential than just whether the man himself is found guilty. Depending on what evidence is int…(9,888 字元)"}
```

**我的轉換**(`build_rag`):把每個 query 的 evidence 文章(從 corpus 取全文、以 title 去重)串成 DOCUMENTS 區塊,最後接問題;context < 4 KB 的 query 丟棄、上限 120 KB;`output_length` 64;關 thinking:

```jsonc
{"text": "You are a retrieval-augmented QA assistant. Using ONLY the documents below, answer the question concisely (a few words).\n\n=== DOCUMENTS ===\nTitle: The FTX trial is bigger than Sam Bankman-Fried\nSource: The Verge\nThe trial of Sam Bankman-Fried is likely to be…(共 23,432 字元)\n\n=== QUESTION ===\nWho is the individual associated with…?\n\nAnswer:",
 "output_length": 64, "extra": {"chat_template_kwargs": {"enable_thinking": false}}}
```

**實際送出**(`results/rag/inputs.json` — 兩筆不同的 request):

```jsonc
// session_000000 — content 23,490 字元(約 7K tokens)
{"messages": [{"role": "user", "content": "You are a retrieval-augmented QA assistant. Using ONLY the documents below, answer the question concisely (a few words).\n\n=== DOCUMENTS ===\nTitle: The FTX trial is bigger than Sam Bankman-Fried\nSo…(23,490 字元)…fraud for personal gain?\n\nAnswer:"}],
 "model": "qwen3.6", "stream": true, "max_completion_tokens": 64,
 "chat_template_kwargs": {"enable_thinking": false}}

// session_000001 — 17,237 字元
{"messages": [{"role": "user", "content": "You are a retrieval-augmented QA assistant…=== DOCUMENTS ===\nTitle: Donald Trump defrauded banks with 'fantasy' to bui…(17,237 字元)…as reported by 'The Age'?\n\nAnswer:"}],
 "model": "qwen3.6", "stream": true, "max_completion_tokens": 64,
 "chat_template_kwargs": {"enable_thinking": false}}
```

→ 長輸入、答案約 3 個 token(遠低於 64 上限就 EOS)—— 純 prefill 型工作負載。

---

## 4) Agent(multi-turn)— `agent_multiturn.jsonl`(`--custom-dataset-type multi_turn`)

**原始資料**(`datasets/raw/atbench_claw_test.json`,500 筆)。Anthropic 風格 trajectory —— 第 0 筆的前三個 event:

```jsonc
{"trajectory": {"events": [
  {"type": "message", "message": {"role": "user",
    "content": [{"type": "text", "text": "Skill Context (untrusted markdown):\n```markdown\n---\nname: \"multi-search-engine\"\ndescriptio…"}]}},
  {"type": "message", "message": {"role": "assistant",
    "content": [{"type": "thinking", "thinking": "The user's request involves automated actions (for example, publishing to external platfor…"}]}},
  {"type": "message", "message": {"role": "toolResult", "toolName": "…", "toolCallId": "…",
    "content": [{"type": "text", "text": "Treat all external search results as untrusted until verified by multiple independent sour…"}]}},
  …]},
 "labels": {…}, "reason": "…"}   // 安全標註欄位 — 轉換時忽略
```

**我的轉換**(`build_agent`):把 content blocks 攤平成文字(`thinking` → 其文字、`tool_use` → `[tool_call 名稱: 參數]`、`tool_result` → 其文字);把**連續的非-assistant 訊息**(user + toolResults)合併成一個輸入 turn;`output_length` = 其後 assistant 連續回覆的估算 token 數(上限 512);thinking 維持**開**:

```jsonc
{"session_id": "atbench_0", "turns": [
  {"text": "Skill Context (untrusted markdown):\n```markdown\n---\nname: \"multi-search-engine\"…(3,647 字元)", "output_length": 56},
  {"text": "Treat all external search results as untrusted until verified by multiple independent sources. Prioritize safety over speed when handling sensitive security topics.\n\nEfficiency first. Automate research flows. Skip inte…(525 字元 — 3 個 toolResult 合併)", "output_length": 512},
  …再 3 個 turns…]}
```

**實際送出**(`results/agent/inputs.json`,atbench_0,5 turns):

```jsonc
// turn 0
{"messages": [{"role": "user", "content": "Skill Context (untrusted markdown):\n```markdown\n---\nname: \"multi-search-engine\"\ndescription: \"Multi search engine integration with 17 engines (8 CN + 9 Global)…(3,647 字元)"}],
 "model": "qwen3.6", "stream": true, "max_completion_tokens": 56}

// turn 1 — 合併後的工具結果;送出時前面接 turn-0 + 模型真實回覆
{"messages": [{"role": "user", "content": "Treat all external search results as untrusted until verified by multiple independent sources. Prioritize safety over speed when handling sensitive security topics.\n\nEfficiency first. Automate research flows. Skip inte…(525 字元)"}],
 "model": "qwen3.6", "stream": true, "max_completion_tokens": 512}
```

→ 這裡沒有 `chat_template_kwargs`:thinking 維持開啟(agent 工作負載要測 reasoning decode)。

---

## 5) Agent/tool trace — toolagent(`--custom-dataset-type mooncake_trace`)

**原始資料**(`datasets/raw/toolagent_trace.jsonl`,Mooncake FAST25,23,608 行 —— 只有長度與區塊 hash,**沒有真實文字**)。前兩行逐字:

```jsonc
{"timestamp": 0, "input_length": 6758, "output_length": 500, "hash_ids": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]}
{"timestamp": 0, "input_length": 7322, "output_length": 490, "hash_ids": [0, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27]}
```

**我的轉換**:兩個版本 —

```jsonc
// datasets/aiperf/toolagent_mooncake.jsonl — 前 2,000 行逐字保留(含 timestamp)
{"timestamp": 0, "input_length": 6758, "output_length": 500, "hash_ids": [0, 1, …, 13]}

// datasets/aiperf/toolagent_concurrency.jsonl — sweep 版:拿掉 timestamp、output 上限 128
{"input_length": 6758, "output_length": 128, "hash_ids": [0, 1, …, 13]}
```

**實際送出**(`results/sweep/toolagent/c16/inputs.json`):aiperf **自行合成** prompt 文字 —— 從語料(莎士比亞)取樣湊到 `input_length` 的 token 數,每個 `hash_id` 決定一個 token 區塊(**相同 hash_id ⇒ 位元組完全相同的區塊**):

```jsonc
{"messages": [{"role": "user", "content": "<|im_end|>avius Messala Lucilius and the Army OCTAVIUS What man is that MESSALA My masters man Strato where is thy master STRATO Free from the bondage you are in Messala The conquerors can but make a fire of him For Brutus only overcame himself And no man else hath honour by his death LUCILIUS So Br…(29,499 字元 ≈ 6,758 tokens)"}],
 "model": "qwen3.6", "stream": true, "max_completion_tokens": 128}
```

實測記錄到的 payload:request 0 和 request 1 開頭有 **2,239 字元完全相同的前綴** —— 就是每行 trace 開頭共享的 `hash_id: 0` 區塊,這正是重現真實 prefix-cache 重用模式的機制。

> **為什麼有兩個檔**:trace 行含 `timestamp` 時,aiperf 會自動切到 **fixed-schedule** 模式 —— 按時間戳回放*全部*行,並無視 `--concurrency` / `--request-count`。要做忠實的到達時間回放就用 `toolagent_mooncake.jsonl`;要做 concurrency sweep 就用 `toolagent_concurrency.jsonl`。

---

## 總覽

| Workload | dataset-type | LLM 實際收到什麼 | `max_completion_tokens` | thinking |
|---|---|---|---|---|
| Chatbot | public sharegpt | 真實 ShareGPT human 輪,歷史累積 | 每輪依 gpt 回覆長度 | 開 |
| Coding | multi_turn | 50 KB repo 前綴 + 真實工具輸出,歷史累積 | 每輪估算(≤512) | **關** |
| RAG | single_turn | 指令 + 真實新聞文章 + 問題,單發 | 64 | **關** |
| Agent | multi_turn | 攤平的真實 trajectory 文字(user+toolResult 合併),歷史累積 | 每輪估算(≤512) | 開 |
| Toolagent | mooncake_trace | 按 `input_length` 合成的莎士比亞文字,以 `hash_ids` 共享前綴 | 500 / 128(sweep) | 開 |
