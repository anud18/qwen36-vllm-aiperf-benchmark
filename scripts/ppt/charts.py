import json, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.family"]=["Noto Sans CJK TC","DejaVu Sans"]
plt.rcParams["axes.unicode_minus"]=False
OUT="results/nvfp4/ppt_assets"
SPARK="#2a78d6"; ENDPT="#eb6834"; INK="#26262a"; MUTED="#6b6b70"; GRID="#e4e4e2"; SURF="#fcfcfb"

PAIRS=[("Qwen","w2 chatbot c1","qwen3vl","w2_chatbot_c1/chatbot_flat/c1","qwen3vl_ngrok/chatbot_flat/c1"),
 ("Qwen","w2 chatbot c2","qwen3vl","w2_chatbot_c2/chatbot_flat/c2","qwen3vl_ngrok/chatbot_flat/c2"),
 ("Qwen","w2 chatbot c1 rep","qwen3vl","w2_chatbot_c1_rep/chatbot_flat/c1","qwen3vl_ngrok_run2/chatbot_flat/c1"),
 ("Qwen","w2 agent c1","qwen3vl","w2_agent_c1/agent_flat/c1","qwen3vl_ngrok/agent_flat/c1"),
 ("Qwen","w0 chatbot c1","qwen3vl","w0_chatbot_c1/chatbot_flat/c1","w0_chatbot/chatbot_flat/c1"),
 ("Qwen","w0 agent c1","qwen3vl","w0_agent_c1/agent_flat/c1","w0_agent/agent_flat/c1"),
 ("Qwen","w0 chatbot c1 rep","qwen3vl","w0_chatbot_c1_rep/chatbot_flat/c1","w0_chatbot_rep/chatbot_flat/c1"),
 ("Llama","w0 chatbot c1","llama31","w0_chatbot_c1/chatbot_flat/c1","cf_llama31_chatbot/chatbot_flat/c1"),
 ("Llama","w0 agent c1","llama31","w0_agent_c1/agent_flat/c1","cf_llama31_agent/agent_flat/c1"),
 ("Llama","w0 chatbot c1 rep","llama31","w0_chatbot_c1_rep/chatbot_flat/c1","cf_llama31_chatbot_rep/chatbot_flat/c1"),
 ("Llama","r100 chatbot c1","llama31","r100_chatbot_c1/chatbot_flat/c1","r100_chatbot_flat_c1/chatbot_flat/c1"),
 ("Llama","r100 chatbot c2","llama31","r100_chatbot_c2/chatbot_flat/c2","r100_chatbot_flat_c2/chatbot_flat/c2")]
g=lambda r,k: r[k]["avg"] if isinstance(r[k],dict) else r[k]
D=[]
for mdl,name,mk,l,e in PAIRS:
    L=json.load(open(f"results/nvfp4/spark_repro_{mk}/{l}/profile_export_aiperf.json"))
    E=json.load(open(f"results/nvfp4/{e}/profile_export_aiperf.json"))
    D.append(dict(mdl=mdl,name=name,
        pf_r=g(L,'prefill_throughput_per_user')/g(E,'prefill_throughput_per_user'),
        dc_r=g(L,'output_token_throughput_per_user')/g(E,'output_token_throughput_per_user')))

def style(ax):
    ax.set_facecolor(SURF); ax.figure.set_facecolor(SURF)
    for s in ("top","right"): ax.spines[s].set_visible(False)
    for s in ("left","bottom"): ax.spines[s].set_color(GRID)
    ax.tick_params(colors=MUTED, length=0, labelsize=11)
    ax.xaxis.grid(True,color=GRID,lw=1); ax.yaxis.grid(False); ax.set_axisbelow(True)

# 1) prefill ratio
d=sorted(D,key=lambda x:x["pf_r"])
fig,ax=plt.subplots(figsize=(13,4.9))
y=range(len(d)); v=[x["pf_r"] for x in d]
ax.barh(list(y),v,height=.62,color=SPARK)
for i,(x_,r) in enumerate(zip(v,d)):
    ax.text(x_+2.5,i,f"{x_:.0f}×",va="center",ha="left",color=INK,fontsize=12,fontweight="bold")
ax.set_yticks(list(y)); ax.set_yticklabels([f"{x['mdl']} · {x['name']}" for x in d],color=INK,fontsize=11)
ax.set_xlim(0,205); ax.set_xlabel("端點 prefill 比 spark 本機慢幾倍",color=MUTED,fontsize=11,labelpad=10)
style(ax); fig.tight_layout(); fig.savefig(f"{OUT}/prefill.png",dpi=200); plt.close(fig)

# 2) decode ratio
d=sorted(D,key=lambda x:x["dc_r"])
fig,ax=plt.subplots(figsize=(13,4.9))
v=[x["dc_r"] for x in d]
ax.barh(list(range(len(d))),v,height=.62,color=[SPARK if x>1.15 else "#9ec5f4" for x in v])
ax.axvline(1.0,color=ENDPT,lw=2,zorder=3)
ax.text(1.04,-0.85,"1.0× = 兩邊相同",color=ENDPT,fontsize=11,va="center")
for i,x_ in enumerate(v): ax.text(x_+.04,i,f"{x_:.2f}×",va="center",color=INK,fontsize=12,fontweight="bold")
ax.set_yticks(list(range(len(d)))); ax.set_yticklabels([f"{x['mdl']} · {x['name']}" for x in d],color=INK,fontsize=11)
ax.set_ylim(-1.4,len(d)-0.4)
ax.set_xlim(0,3.8); ax.set_xlabel("端點 decode 比 spark 本機慢幾倍",color=MUTED,fontsize=11,labelpad=10)
style(ax); fig.tight_layout(); fig.savefig(f"{OUT}/decode.png",dpi=200); plt.close(fig)

# 3) concurrency scaling lives in scaling2.py -- do not duplicate it here
print("charts ok")
print("prefill ratio range:", f"{min(x['pf_r'] for x in D):.0f}-{max(x['pf_r'] for x in D):.0f}")
print("decode ratio range:", f"{min(x['dc_r'] for x in D):.2f}-{max(x['dc_r'] for x in D):.2f}")
