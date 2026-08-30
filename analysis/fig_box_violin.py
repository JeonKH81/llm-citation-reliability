#!/usr/bin/env python3
"""Box and violin plot of per-review hallucination rate by model and tier."""
import json, os
from collections import defaultdict
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

A = os.path.dirname(os.path.abspath(__file__))
rows = [json.loads(l) for l in open(os.path.join(A, "..", "data", "main_websearch", "verdicts.jsonl"))]
rev = defaultdict(lambda: [0, 0]); tier = {}
for r in rows:
    if r["verdict"] == "omission":
        continue
    k = (r["model_key"], r["topic_slug"], r["run"]); rev[k][1] += 1
    if r["problematic"]: rev[k][0] += 1
    tier[k] = r["tier"]
rate = {k: 100 * v[0] / v[1] for k, v in rev.items() if v[1]}

MODELS = ["gpt", "claude", "gemini"]
MLAB = {"gpt": "GPT-5.5", "claude": "Claude Opus 4.8", "gemini": "Gemini 3.5 Flash"}
TIERS = ["low", "moderate", "high"]
MC = {"gpt": "#2A9D8F", "claude": "#E76F51", "gemini": "#8B6BB7"}
def data(m, t): return [rate[k] for k in rate if k[0] == m and tier[k] == t]

def plot(dark):
    fg = "#e8e8e8" if dark else "black"
    bg = "#0a0a0a" if dark else "white"
    plt.rcParams.update({"font.size": 11, "font.family": "Arial Narrow",
                         "font.sans-serif": ["Arial Narrow", "Arial", "DejaVu Sans"],
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, ax = plt.subplots(figsize=(9.2, 5.8))
    fig.patch.set_facecolor(bg); ax.set_facecolor(bg)
    pos = 0; xticks = []; xlabs = []; centers = []
    for m in MODELS:
        start = pos
        for t in TIERS:
            vals = data(m, t)
            vp = ax.violinplot(vals, positions=[pos], widths=0.82, showextrema=False)
            for b in vp["bodies"]:
                b.set_facecolor(MC[m]); b.set_alpha(0.30 if dark else 0.25); b.set_edgecolor("none")
            bp = ax.boxplot(vals, positions=[pos], widths=0.42, patch_artist=True, showfliers=False,
                            medianprops=dict(color=fg, lw=1.5),
                            whiskerprops=dict(color=fg), capprops=dict(color=fg), boxprops=dict(color=fg))
            for box in bp["boxes"]: box.set(facecolor=MC[m], alpha=0.8)
            jit = np.random.default_rng(1).uniform(-0.13, 0.13, len(vals))
            ax.scatter(jit + pos, vals, s=9, color=fg, alpha=0.30, zorder=3, edgecolors="none")
            xticks.append(pos); xlabs.append(t); pos += 1
        centers.append((start + pos - 1) / 2)
        pos += 0.8
    ax.set_xticks(xticks); ax.set_xticklabels(xlabs, fontsize=9, color=fg)
    for c, m in zip(centers, MODELS):
        ax.text(c, -15, MLAB[m], ha="center", va="top", fontsize=11.5, fontweight="bold", color=fg)
    ax.set_ylabel("Per-review problematic reference rate (%)", color=fg)
    ax.set_ylim(-5, 100); ax.tick_params(colors=fg)
    ax.grid(axis="y", color="#333" if dark else "#ddd", ls=":", lw=0.7)
    for s in ax.spines.values(): s.set_color("#555" if dark else "#888")
    fig.tight_layout()
    suffix = "_dark" if dark else ""
    for stem in ("fig1_model_tier", "fig4_box_violin"):
        fn = f"{stem}{suffix}.png"
        fig.savefig(os.path.join(A, fn), dpi=300, bbox_inches="tight", facecolor=bg)
        print("saved", fn)
    plt.close()

plot(False); plot(True)
