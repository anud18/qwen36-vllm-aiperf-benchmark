from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

IMG="results/nvfp4/ppt_assets"
OUT="/home/howard/benchmark/results/nvfp4/optimumxt_findings.pptx"
INK=RGBColor(0x26,0x26,0x2a); MUTED=RGBColor(0x6b,0x6b,0x70); SPARK=RGBColor(0x2a,0x78,0xd6)
ENDPT=RGBColor(0xeb,0x68,0x34); SURF=RGBColor(0xfc,0xfc,0xfb); RULE=RGBColor(0xe4,0xe4,0xe2)
FONT="Noto Sans CJK TC"

prs=Presentation(); prs.slide_width=Inches(13.333); prs.slide_height=Inches(7.5)
W,H=prs.slide_width,prs.slide_height
def blank(): 
    s=prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid(); s.background.fill.fore_color.rgb=SURF
    return s
def tb(s,x,y,w,h,text,size=18,bold=False,color=INK,align=PP_ALIGN.LEFT,space=6):
    box=s.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h)); f=box.text_frame
    f.word_wrap=True; f.margin_left=0; f.margin_top=0; f.margin_right=0; f.margin_bottom=0
    for i,line in enumerate(text.split("\n")):
        p=f.paragraphs[0] if i==0 else f.add_paragraph()
        p.alignment=align; p.space_after=Pt(space)
        r=p.add_run(); r.text=line
        r.font.size=Pt(size); r.font.bold=bold; r.font.color.rgb=color; r.font.name=FONT
    return box
def rule(s,x,y,w):
    from pptx.enum.shapes import MSO_SHAPE
    sh=s.shapes.add_shape(MSO_SHAPE.RECTANGLE,Inches(x),Inches(y),Inches(w),Pt(2))
    sh.fill.solid(); sh.fill.fore_color.rgb=RULE; sh.line.fill.background(); sh.shadow.inherit=False
def pic(s,path,top,bottom,left=0.9,right=0.9):
    """fit an image inside the box without overflowing either dimension"""
    from PIL import Image
    iw,ih=Image.open(path).size; ar=ih/iw
    maxw=13.333-left-right; maxh=bottom-top
    w=min(maxw,maxh/ar); h=w*ar
    s.shapes.add_picture(path,Inches((13.333-w)/2),Inches(top+(maxh-h)/2),width=Inches(w))
    return top+(maxh+h)/2

def head(s,title,kicker=None):
    if kicker: tb(s,0.9,0.55,11.5,0.35,kicker,13,False,MUTED)
    tb(s,0.9,0.92,11.5,0.7,title,30,True,INK)
    rule(s,0.9,1.72,11.5)
def stat(s,x,y,w,value,label,color=SPARK):
    tb(s,x,y,w,1.0,value,44,True,color)
    tb(s,x,y+0.85,w,0.9,label,13,False,MUTED,space=2)

# 1 title
s=blank()
tb(s,0.9,2.5,11.5,1.0,"Dynamo optimumxt 端點效能診斷",40,True,INK)
tb(s,0.9,3.5,11.5,0.8,"以 spark 本機 vLLM 重現同一組 benchmark，26 個測試點",20,False,MUTED)
rule(s,0.9,4.5,4.0)
tb(s,0.9,4.8,11.5,0.9,"2026-08-04    量測工具 aiperf 0.10.0    NVIDIA GB10 / vllm-openai v0.24.0",13,False,MUTED)

# 2 conclusion
s=blank(); head(s,"結論：問題出在部署，不在硬體","一句話")
stat(s,0.9,2.2,3.6,"32–177×","端點 prefill 比同機器的 vLLM 慢\n（12 組同模型對照，全部成立）")
stat(s,4.9,2.2,3.6,"0.93–1.7×","decode 差距不大\nLlama 幾乎相同，Qwen 慢約 1.5 倍",RGBColor(0x1b,0xaf,0x7a))
stat(s,8.9,2.2,3.6,"0.88×","併發從 1 加到 2，端點反而變慢\n（同一測試在本機是 2.09× 加速）",ENDPT)
rule(s,0.9,4.6,11.5)
tb(s,0.9,4.9,11.5,2.0,
 "•  同一台機器、同一個模型、逐 token 相同的輸入 —— 差異只可能來自服務層。\n"
 "•  GB10 的 KV cache 容量 426k–480k tokens，併發 32 下可維持 346 output tok/s。\n"
 "•  曾讓端點卡死 25 分鐘的高併發測試，本機 226 秒乾淨跑完、零錯誤。",16,False,INK,space=10)

# 3 prefill
s=blank(); head(s,"Prefill 慢 32–177 倍","主要發現")
pic(s,f"{IMG}/prefill.png",1.95,6.45)
tb(s,0.9,6.6,11.5,0.7,"每一組都是同模型、同 prompt、ISL 逐 percentile 完全相同的對照。端點實際更慢：其 prefix cache 命中率 46–74%，那些 token 計入 ISL 但未實際運算。",12,False,MUTED)

# 4 decode
s=blank(); head(s,"Decode 沒有問題 —— 除了併發之下","對照")
pic(s,f"{IMG}/decode.png",1.95,6.45)
tb(s,0.9,6.6,11.5,0.7,"Llama 兩邊幾乎相同（0.93–0.98×，本機甚至略慢），代表 GB10 的 decode 速度是硬體實況。Qwen 慢 1.5–1.7×。最上面兩筆是 c2 併發點。",12,False,MUTED)

# 5 scaling
s=blank(); head(s,"併發加倍：本機加速 2.09×，端點反而慢 12%","對照")
pic(s,f"{IMG}/scaling.png",1.95,6.25)
tb(s,0.9,6.35,11.5,0.9,"總工作量固定 100 個請求，端點卻花更久才跑完。機制在 ITL：67 → 182 ms（+170%），兩個請求沒有被 batch 在一起而是互相搶資源。\n端點僅此一組 c1/c2 皆有效，其餘併發點被 tunnel 配額或逾時破壞。",12,False,MUTED,space=4)

# 6 hardware
s=blank(); head(s,"硬體從來不是瓶頸","佐證")
tb(s,0.9,2.1,5.4,0.5,"高併發測試 c32（320 個請求）",18,True,INK)
tb(s,0.9,2.7,5.4,2.9,
 "端點\n    worker 卡死約 25 分鐘，未產出任何結果\n\n"
 "本機 Llama\n    226 秒完成、0 錯誤，系統輸出 346 tok/s\n\n"
 "本機 Qwen\n    514 秒完成、0 錯誤，系統輸出 153 tok/s",14,False,INK,space=4)
tb(s,7.0,2.1,5.4,0.5,"KV cache 容量（端點從未揭露）",18,True,INK)
tb(s,7.0,2.7,5.4,2.9,
 "Llama-3.1-8B\n    426,496 tokens，併發上限 104×\n\n"
 "Qwen3-VL-30B\n    479,504 tokens，併發上限 117×\n\n"
 "皆在 4096 context 設定下量得",14,False,INK,space=4)
rule(s,0.9,5.6,11.5)
tb(s,0.9,5.9,11.5,1.0,"同一台機器上，stock vLLM 在併發 32 時系統輸出達 346 tok/s；端點在併發 1 時只有 9.4 tok/s。",16,True,INK)

# 7 actions
s=blank(); head(s,"建議與限制","下一步")
tb(s,0.9,2.05,11.5,0.45,"建議",18,True,INK)
tb(s,0.9,2.6,11.5,2.0,
 "1.  優先查 Dynamo 的 prefill 路徑 —— 這是唯一數量級的差距，且兩個模型都成立。\n"
 "2.  檢查併發排程：端點在併發 2 就開始劣化，32 直接卡死。\n"
 "3.  context 上限 4096 是部署設定，非模型能力。放寬後另外三個 workload 才跑得動。",15,False,INK,space=9)
rule(s,0.9,4.7,11.5)
tb(s,0.9,4.95,11.5,0.45,"本次量測的已知限制",18,True,INK)
tb(s,0.9,5.5,11.5,1.6,
 "•  本機端沒有 prefix cache 命中率（為與端點方法論一致而保留 REMOTE=1）。\n"
 "•  端點有 4 個測試點因 tunnel 配額或逾時而無效，已於報告中標記，未納入結論。\n"
 "•  端點與本機的 tunnel 差異未單獨隔離；但 110 ms vs 11,444 ms 的差距遠超網路可解釋範圍。",14,False,INK,space=8)

# 8 appendix parity
s=blank(); head(s,"附錄：如何確保兩邊在比同一件事","方法論")
tb(s,0.9,2.05,11.5,1.5,
 "端點數據固定不動，所有對齊都在 spark 這一側完成。",16,True,INK)
tb(s,0.9,2.6,11.5,3.4,
 "ISL 是 server 回報的 prompt_tokens，只有在模型、tokenizer、chat template 三者都一致時才會相同。\n\n"
 "過程中修正兩處：\n"
 "•  一開始誤把本機 Llama 與 Qwen 端點並列比較 —— 不同 tokenizer，兩欄不可比。已全部改為同模型對照。\n"
 "•  Llama 的 chat template 缺少 system block，每個請求少 25 個 token（ISL 總和 11,676 對端點 12,176）。\n"
 "    以 --chat-template 修正後三重驗證：對端點逐筆記錄全數相符、對 Meta 官方 template 在 300 筆 entries\n"
 "    token 數完全相同、對執行中的伺服器實測 69 = 69。\n\n"
 "結果：12 組同模型對照的 ISL 與 OSL，在 avg / p50 / p90 / p95 / p99 / max 每一格都完全相同。",14,False,INK,space=7)

# 9 appendix data
s=blank(); head(s,"附錄：測試範圍與資料","方法論")
tb(s,0.9,2.05,5.4,0.45,"測試點",17,True,INK)
tb(s,0.9,2.55,5.4,3.2,
 "26 個點，兩個模型各 13 個\n全部完成：0 錯誤、OSL 零偏差\n\n"
 "併發 1 / 2 / 32\n請求數 10 / 20 / 100 / 320\n\n"
 "workload：chatbot_flat、agent_flat\n（多輪對話攤平，每個請求自帶完整歷史）",14,False,INK,space=6)
tb(s,7.0,2.05,5.4,0.45,"資料集特性",17,True,INK)
tb(s,7.0,2.55,5.4,3.2,
 "384 筆 entries / 109 個 session\nISL 中位數 530，OSL 中位數 233\n\n"
 "OSL 由 trace 以 ignore_eos 鎖定\n→ 每個有效點偏差為 0\n\n"
 "prefix cache 理論上限 64.8% / 72.8%\n實測 c1 全部落在 3 個百分點內",14,False,INK,space=6)
rule(s,0.9,5.95,11.5)
tb(s,0.9,6.2,11.5,0.9,"完整報告：results/nvfp4/SPARK_REPRO.md　·　資料集說明：DATASETS_optimumxt.md　·　檔案索引：SPARK_INDEX.md",12,False,MUTED)

# 10..21  per-pair comparison tables
import sys; sys.path.insert(0,"scripts/ppt")
from tables import add_table_slides
add_table_slides(prs, blank, head, tb, rule)

# 22  spark points without an endpoint counterpart
s=blank(); head(s,"附錄：無端點對照的 spark 測試點","逐組對照")
tb(s,0.9,2.05,11.5,3.4,
 "以下 spark 點沒有可比的端點數據，因此不出現在前面的對照表：\n\n"
 "•  Llama 的 w2 系列 4 個點 —— 端點從未跑過這組設定。\n"
 "•  w0 agent c2（兩個模型）—— 端點該點 20 筆中有 6 筆撞上 ngrok 流量配額。\n"
 "•  r100 agent c1 / c2（兩個模型）—— 端點分別遺失 3 筆與 10 筆（Cloudflare 逾時）。\n"
 "    逾時砍掉的是最慢的請求，會讓端點數字看起來偏好，不能採用。\n"
 "•  r100 chatbot / agent（Qwen）—— 100 請求系列只對 Llama 端點跑過。\n"
 "•  c32（兩個模型）—— 端點該點 worker 卡死，未產出任何結果。\n\n"
 "這些點在 spark 上全部完成、0 錯誤，數據見 results/nvfp4/SPARK_INDEX.md。",14,False,INK,space=7)

from endpoint_tables import add_endpoint_slides
add_endpoint_slides(prs, blank, head, tb, rule)

prs.save(OUT); print("saved", OUT, len(prs.slides.__iter__.__self__._sldIdLst), "slides")
