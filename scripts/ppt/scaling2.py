import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.family"]=["Noto Sans CJK TC","DejaVu Sans"]; plt.rcParams["axes.unicode_minus"]=False
OUT="results/nvfp4/ppt_assets"
SPARK="#2a78d6"; ENDPT="#eb6834"; INK="#26262a"; MUTED="#6b6b70"; GRID="#e4e4e2"; SURF="#fcfcfb"
rows=[("Dynamo 端點 · Llama r100 chatbot",2757.64/3132.16,ENDPT),
      ("spark 本機 · Qwen r100 chatbot",829.2/551.8,SPARK),
      ("spark 本機 · Qwen r100 agent",766.8/508.5,SPARK),
      ("spark 本機 · Llama r100 agent",1642.4/784.4,SPARK),
      ("spark 本機 · Llama r100 chatbot",1799.0/859.8,SPARK)]
fig,ax=plt.subplots(figsize=(13,4.3))
y=list(range(len(rows)))
ax.barh(y,[r[1] for r in rows],height=.6,color=[r[2] for r in rows])
for i,r in enumerate(rows):
    ax.text(r[1]+.04,i,f"{r[1]:.2f}×",va="center",color=INK,fontsize=13,fontweight="bold")
ax.axvline(1.0,color=MUTED,lw=1.5,ls="--",zorder=0)
ax.set_yticks(y); ax.set_yticklabels([r[0] for r in rows],color=INK,fontsize=11.5)
ax.set_xlim(0,2.45)
ax.set_xlabel("併發從 1 加到 2 的加速倍率     （虛線 1.0× = 完全沒有幫助；< 1.0 = 反而更慢）",
              color=MUTED,fontsize=11,labelpad=12)
ax.set_facecolor(SURF); fig.set_facecolor(SURF)
for s in ("top","right"): ax.spines[s].set_visible(False)
for s in ("left","bottom"): ax.spines[s].set_color(GRID)
ax.tick_params(colors=MUTED,length=0,labelsize=11)
ax.xaxis.grid(True,color=GRID,lw=1); ax.set_axisbelow(True)
fig.tight_layout(); fig.savefig(f"{OUT}/scaling.png",dpi=200); plt.close(fig)
print("ok")
