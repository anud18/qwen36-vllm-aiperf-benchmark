import json
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

INK=RGBColor(0x26,0x26,0x2a); MUTED=RGBColor(0x6b,0x6b,0x70); ENDPT=RGBColor(0xeb,0x68,0x34)
SPARK=RGBColor(0x2a,0x78,0xd6); SURF=RGBColor(0xfc,0xfc,0xfb); HEADBG=RGBColor(0xf2,0xf2,0xf0)
WARN=RGBColor(0xe3,0x49,0x48); GOOD=RGBColor(0x1b,0xaf,0x7a); FONT="Noto Sans CJK TC"
g=lambda r,k,f='avg': (r[k].get(f) if isinstance(r[k],dict) else r[k]) if k in r else None

def add_c1c2_slides(prs, blank, head, tb, rule):
    A=json.load(open("results/nvfp4/r100_chatbot_flat_c1/chatbot_flat/c1/profile_export_aiperf.json"))
    B=json.load(open("results/nvfp4/r100_chatbot_flat_c2/chatbot_flat/c2/profile_export_aiperf.json"))
    s=blank(); head(s,"Dynamo 端點：併發 1 vs 併發 2","附錄：端點自身的併發比較　·　Llama-3.1-8B · chatbot_flat · 100 請求")
    def n(v,d=2): return f"{v:,.{d}f}"
    def rat(a,b,inv=False):   # always c2 / c1 -- inv kept for call-site compatibility
        return f"{b/a:.2f}×"
    rows=[
     ("TTFT avg (ms)",           n(g(A,'time_to_first_token'),1), n(g(B,'time_to_first_token'),1), rat(g(A,'time_to_first_token'),g(B,'time_to_first_token'))),
     ("ITL = TPOT avg (ms)",     n(g(A,'inter_token_latency')),   n(g(B,'inter_token_latency')),   rat(g(A,'inter_token_latency'),g(B,'inter_token_latency'))),
     ("E2E latency avg (ms)",    n(g(A,'request_latency'),1),     n(g(B,'request_latency'),1),     rat(g(A,'request_latency'),g(B,'request_latency'))),
     ("Prefill throughput (tok/s/user)", n(g(A,'prefill_throughput_per_user'),1), n(g(B,'prefill_throughput_per_user'),1), rat(g(A,'prefill_throughput_per_user'),g(B,'prefill_throughput_per_user'),True)),
     ("Decode throughput (tok/s/user)",  n(g(A,'output_token_throughput_per_user')), n(g(B,'output_token_throughput_per_user')), rat(g(A,'output_token_throughput_per_user'),g(B,'output_token_throughput_per_user'),True)),
     ("Output throughput, system (tok/s)", n(g(A,'output_token_throughput')), n(g(B,'output_token_throughput')), rat(g(A,'output_token_throughput'),g(B,'output_token_throughput'),True)),
     ("Request throughput (req/s)", n(g(A,'request_throughput'),4), n(g(B,'request_throughput'),4), rat(g(A,'request_throughput'),g(B,'request_throughput'),True)),
     ("Benchmark duration (s)",  n(g(A,'benchmark_duration'),1),  n(g(B,'benchmark_duration'),1),  rat(g(A,'benchmark_duration'),g(B,'benchmark_duration'))),
     ("Prefix cache 命中率 (%)", n(g(A,'overall_usage_prompt_cache_read_pct')), n(g(B,'overall_usage_prompt_cache_read_pct')), ""),
     ("ISL total (tokens)",      f"{g(A,'total_isl'):,.0f}",      f"{g(B,'total_isl'):,.0f}",      "相同"),
     ("OSL total (tokens)",      f"{g(A,'total_osl'):,.0f}",      f"{g(B,'total_osl'):,.0f}",      "相同"),
     ("Successful requests",     f"{g(A,'request_count'):.0f} / 100", f"{g(B,'request_count'):.0f} / 100", ""),
    ]
    nrow=len(rows)+1
    t=s.shapes.add_table(nrow,4,Inches(0.9),Inches(1.9),Inches(11.5),Inches(0.325*nrow)).table
    t.columns[0].width=Inches(4.3); t.columns[1].width=Inches(2.5)
    t.columns[2].width=Inches(2.5); t.columns[3].width=Inches(2.2)
    for c,txt in enumerate(["指標","併發 1","併發 2","c2 相對 c1"]):
        cell=t.cell(0,c); cell.text=""
        p=cell.text_frame.paragraphs[0]; r=p.add_run(); r.text=txt
        r.font.size=Pt(12.5); r.font.bold=True; r.font.name=FONT; r.font.color.rgb=ENDPT if c in (1,2) else INK
        p.alignment=PP_ALIGN.LEFT if c==0 else PP_ALIGN.RIGHT
        cell.fill.solid(); cell.fill.fore_color.rgb=HEADBG
    for i,row in enumerate(rows,start=1):
        for c,txt in enumerate(row):
            cell=t.cell(i,c); cell.text=""
            p=cell.text_frame.paragraphs[0]; r=p.add_run(); r.text=str(txt)
            r.font.size=Pt(12.5); r.font.name=FONT; r.font.color.rgb=INK
            r.font.bold=(c==3 and txt not in ("",))
            if c==3 and txt=="相同": r.font.color.rgb=GOOD
            p.alignment=PP_ALIGN.LEFT if c==0 else PP_ALIGN.RIGHT
            cell.fill.solid(); cell.fill.fore_color.rgb=SURF
    y=1.9+0.325*nrow+0.18
    tb(s,0.9,y,11.5,0.5,
       "總工作量固定 100 個請求，併發加倍後端點卻多花 13.6% 的時間才跑完 —— 加大併發是負效益。",13,True,INK)
    tb(s,0.9,y+0.34,11.5,0.4,
       "比值欄一律為 c2 ÷ c1：延遲類 > 1 代表變慢，吞吐類 < 1 代表變差。",11,False,MUTED)
    tb(s,0.9,y+0.7,11.5,0.8,
       "機制在 decode：ITL 67.4 → 181.7 ms（+170%），per-user decode 掉到 6.62 tok/s，系統輸出從 8.97 降到 7.89。\n"
       "同一組測試在 spark 本機是加速 2.09×、系統輸出 13.74 → 28.75 tok/s（見第 5 頁）。",11.5,False,MUTED,space=3)

    s=blank(); head(s,"端點其餘 c1 / c2 組合為何不可比","附錄：端點自身的併發比較")
    tb(s,0.9,2.1,11.5,0.5,"端點側只有上一頁那一組是乾淨的併發對照。其餘三組各有不同問題：",15,False,INK)
    items=[("Qwen3-VL · w2 chatbot c1 / c2",
            "兩點的請求數與 trace 切片不同（10 筆 entries[2:12] 對 20 筆 entries[2:22]），ISL 總和 5,937 對 12,040。\n"
            "這是兩個不同的 workload，不是同一工作量的併發比較。"),
           ("Qwen3-VL · w0 agent c1 / c2",
            "c2 的 20 筆中有 6 筆撞上 ngrok 月流量配額（403 ERR_NGROK_725），實際只完成 14 筆，\n"
            "ISL 總和因此變成 21,714 對 c1 的 33,160。工作量不同，無法比較。"),
           ("Llama-3.1-8B · r100 agent c1 / c2",
            "兩點分別遺失 3 筆與 10 筆 Cloudflare 524 逾時，ISL 總和 155,303 對 135,900。\n"
            "524 砍掉的是最慢的請求，兩邊被砍掉的比例還不同，比較會雙重失真。")]
    yy=2.75
    for title,body in items:
        tb(s,0.9,yy,11.5,0.4,title,14,True,INK)
        tb(s,0.9,yy+0.42,11.5,0.8,body,12,False,MUTED,space=2)
        yy+=1.32
    rule(s,0.9,yy+0.05,11.5)
    tb(s,0.9,yy+0.3,11.5,0.6,
       "spark 本機四組 c1 / c2 全部有效（ISL 逐點相同、0 錯誤），加速倍率 1.50× 至 2.09×。",13,True,INK)
