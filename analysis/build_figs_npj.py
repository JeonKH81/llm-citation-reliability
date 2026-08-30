#!/usr/bin/env python3
"""npj Digital Medicine figures: Arial, Okabe-Ito colour-blind-safe palette, no red/green contrast,
lower-case panel labels (a, b), no suptitles (text belongs in the figure legend), RGB 300 dpi PNG + vector PDF."""
import json, os
from collections import defaultdict
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "main_websearch", "verdicts.jsonl")
OUT = os.path.join(HERE, "figures"); os.makedirs(OUT, exist_ok=True)
plt.rcParams.update({"font.family": "Arial", "font.sans-serif": ["Arial", "Helvetica"], "font.size": 9,
                     "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42, "ps.fonttype": 42})
# Okabe-Ito
BLUE, SKY, ORANGE, VERM, PINK, GREY, BLACK = "#0072B2", "#56B4E9", "#E69F00", "#D55E00", "#CC79A7", "#999999", "#000000"
MC = {"gpt": BLUE, "claude": ORANGE, "gemini": PINK}
ML = {"gpt": "GPT-5.5", "claude": "Claude Opus 4.8", "gemini": "Gemini 3.5 Flash"}
MODELS = ["gpt", "claude", "gemini"]; TIERS = ["low", "moderate", "high"]

rows = [json.loads(l) for l in open(DATA)]
def save(fig, stem):
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(OUT, f"{stem}.{ext}"), dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig); print("saved", stem)

# ---------- Figure 1: per-review problematic rate, box + violin + points ----------
rev = defaultdict(lambda: [0, 0]); tier = {}
for r in rows:
    if r["verdict"] == "omission": continue
    k = (r["model_key"], r["topic_slug"], r["run"]); rev[k][1] += 1
    if r["problematic"]: rev[k][0] += 1
    tier[k] = r["tier"]
rate = {k: 100 * v[0] / v[1] for k, v in rev.items() if v[1]}
fig, ax = plt.subplots(figsize=(7.2, 4.4))
pos = 0; xt = []; xl = []; centers = []
for m in MODELS:
    start = pos
    for t in TIERS:
        vals = [rate[k] for k in rate if k[0] == m and tier[k] == t]
        vp = ax.violinplot(vals, positions=[pos], widths=0.82, showextrema=False)
        for b in vp["bodies"]: b.set_facecolor(MC[m]); b.set_alpha(0.22); b.set_edgecolor("none")
        bp = ax.boxplot(vals, positions=[pos], widths=0.42, patch_artist=True, showfliers=False,
                        medianprops=dict(color="black", lw=1.4), whiskerprops=dict(color="black"),
                        capprops=dict(color="black"), boxprops=dict(color="black"))
        for box in bp["boxes"]: box.set(facecolor=MC[m], alpha=0.75)
        jit = np.random.default_rng(1).uniform(-0.13, 0.13, len(vals))
        ax.scatter(jit + pos, vals, s=7, color="black", alpha=0.35, zorder=3, edgecolors="none")
        xt.append(pos); xl.append(t.capitalize()); pos += 1
    centers.append((start + pos - 1) / 2); pos += 0.8
ax.set_xticks(xt); ax.set_xticklabels(xl, fontsize=8)
for c, m in zip(centers, MODELS): ax.text(c, -14, ML[m], ha="center", va="top", fontsize=9, fontweight="bold")
ax.set_ylabel("Problematic references per review (%)"); ax.set_ylim(-4, 100)
ax.set_xlabel("Publication-volume level", labelpad=22)
ax.grid(axis="y", color="#dddddd", ls=":", lw=0.6)
fig.tight_layout(); save(fig, "Fig1")

# ---------- Figure 2: verification outcome composition by model ----------
vtype = defaultdict(lambda: defaultdict(int))
for r in rows: vtype[r["model_key"]][r["verdict"]] += 1
order = ["verified", "verified_benign", "real_non_pubmed", "omission", "field_error", "misattribution", "fabrication"]
labels = ["Verified", "Verified, benign discrepancy", "Real, not in PubMed", "Omission",
          "Field error", "Misattribution", "Fabrication"]
cols = [BLUE, SKY, "#CFCFCF", GREY, ORANGE, VERM, BLACK]
PROB = {"field_error", "misattribution", "fabrication"}
fig, ax = plt.subplots(figsize=(7.2, 3.2))
tot = {m: sum(vtype[m].values()) for m in MODELS}
bottom = [0.0] * 3; nonprob_end = [0.0] * 3
for v, lab, c in zip(order, labels, cols):
    vals = [100 * vtype[m][v] / tot[m] for m in MODELS]
    ax.barh(range(3), vals, left=bottom, color=c, label=lab, height=0.6, edgecolor="white", linewidth=0.4)
    if v in ("verified", "misattribution"):
        for i, (b, x) in enumerate(zip(bottom, vals)):
            if x > 6: ax.text(b + x / 2, i, f"{x:.0f}%", ha="center", va="center", color="white", fontsize=8, fontweight="bold")
    bottom = [b + x for b, x in zip(bottom, vals)]
    if v not in PROB: nonprob_end = list(bottom)
for i, m in enumerate(MODELS):
    prob = 100 * sum(vtype[m][k] for k in PROB) / (tot[m] - vtype[m]["omission"])
    ax.plot([nonprob_end[i]] * 2, [i - 0.32, i + 0.32], color="black", lw=1.2, ls=(0, (2, 1)))
    ax.text(101, i, f"{prob:.1f}%\nproblematic", va="center", ha="left", fontsize=8)
ax.set_yticks(range(3)); ax.set_yticklabels([ML[m] for m in MODELS]); ax.invert_yaxis()
ax.set_xlim(0, 100); ax.set_xlabel("Share of references (%)")
ax.legend(frameon=False, ncol=4, fontsize=7.5, loc="upper center", bbox_to_anchor=(0.45, -0.25))
fig.subplots_adjust(left=0.17, right=0.84, bottom=0.36, top=0.97); save(fig, "Fig2")

# ---------- Figure 3: CoVe detection ----------
BYTYPE = [("Overall\n(n = 62)", 60, 62), ("Misattribution\n(n = 51)", 51, 51), ("Fabrication\n(n = 4)", 4, 4), ("Field error\n(n = 7)", 5, 7)]
def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return 100 * p, 100 * (c - h), 100 * (c + h)
fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 3.1), gridspec_kw={"width_ratios": [1.5, 1]})
labs = [b[0] for b in BYTYPE][::-1]; kn = [(b[1], b[2]) for b in BYTYPE][::-1]
cols = [ORANGE, BLACK, VERM, BLUE]           # field, fab, misattr, overall (bottom to top after reversal)
vals = [wilson(k, n) for k, n in kn]
a1.barh(range(4), [v[0] for v in vals], color=cols, height=0.6,
        xerr=[[max(0, v[0] - v[1]) for v in vals], [max(0, v[2] - v[0]) for v in vals]], capsize=3, error_kw={"elinewidth": 0.9, "ecolor": "#444444"})
for i, ((k, n), v) in enumerate(zip(kn, vals)):
    a1.text(1.5, i, f"{v[0]:.0f}%  ({k}/{n})", va="center", ha="left", color="white" if v[0] > 30 else "black", fontsize=8, fontweight="bold")
a1.set_yticks(range(4)); a1.set_yticklabels(labs, fontsize=8)
a1.set_xlim(0, 105); a1.set_xlabel("Problematic references detected (%)")
a1.grid(axis="x", color="#dddddd", ls=":", lw=0.6)
s = wilson(60, 62); sp = wilson(205, 208)
bars = a2.bar([0, 1], [s[0], sp[0]], color=[BLUE, SKY], width=0.55,
              yerr=[[max(0, s[0] - s[1]), max(0, sp[0] - sp[1])], [max(0, s[2] - s[0]), max(0, sp[2] - sp[0])]], capsize=4, error_kw={"elinewidth": 0.9, "ecolor": "#444444"})
for b, v in zip(bars, (s, sp)):
    a2.text(b.get_x() + b.get_width() / 2, 80.5, f"{v[0]:.1f}%", ha="center", va="bottom", color="white", fontsize=9, fontweight="bold")
a2.set_xticks([0, 1]); a2.set_xticklabels(["Sensitivity", "Specificity"]); a2.set_ylim(80, 101)
a2.set_ylabel("Agreement with expert (%)"); a2.grid(axis="y", color="#dddddd", ls=":", lw=0.6)
for ax, lab, x in ((a1, "a", 0.01), (a2, "b", 0.62)):
    fig.text(x, 0.98, lab, fontsize=11, fontweight="bold", va="top")
fig.tight_layout(rect=(0, 0, 1, 0.96)); save(fig, "Fig3")
print("CoVe sens CI %.1f-%.1f | spec CI %.1f-%.1f" % (s[1], s[2], sp[1], sp[2]))
