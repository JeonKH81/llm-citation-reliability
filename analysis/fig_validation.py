#!/usr/bin/env python3
"""Figure 3 (validation arm, expert gold standard, n=270 refs, 62 problematic).
Focus: how well the LLM-based CoVe detects problematic references.
Panel (a): detection by expert error type. Panel (b): CoVe vs expert (sensitivity/specificity).
Light + dark."""
import os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

A = os.path.dirname(os.path.abspath(__file__))

# from compare.py and by-type computation
BYTYPE = [("Overall\n(n=62)", 96.8, 60, 62),
          ("Misattribution\n(n=51)", 100.0, 51, 51),
          ("Fabrication\n(n=4)", 100.0, 4, 4),
          ("Field error\n(n=7)", 71.4, 5, 7)]
SENS, SPEC = 96.8, 98.6

def plot(dark):
    fg = "#e8e8e8" if dark else "#222"; bg = "#0a0a0a" if dark else "white"
    grid = "#333" if dark else "#ddd"
    plt.rcParams.update({"font.size": 11, "font.family": "Arial Narrow",
                         "font.sans-serif": ["Arial Narrow", "Arial", "DejaVu Sans"],
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.7), gridspec_kw={"width_ratios": [1.5, 1]})
    fig.patch.set_facecolor(bg)
    for ax in (a1, a2): ax.set_facecolor(bg); ax.tick_params(colors=fg)

    # panel A: detection by error type (horizontal)
    labs = [b[0] for b in BYTYPE][::-1]; vals = [b[1] for b in BYTYPE][::-1]
    cols = ["#F4A261", "#9D0208", "#E76F51", "#1d6f63"][::-1]   # field, fab, misattr, overall
    y = range(len(labs))
    a1.barh(list(y), vals, color=cols, height=0.62)
    for i, (v, b) in enumerate(zip(vals, list(BYTYPE)[::-1])):
        a1.text(v - 3, i, f"{v:.0f}%", va="center", ha="right", color="white", fontsize=11, fontweight="bold")
        a1.text(101, i, f"{b[2]}/{b[3]}", va="center", ha="left", color=fg, fontsize=9.5)
    a1.set_yticks(list(y)); a1.set_yticklabels(labs, color=fg, fontsize=10)
    a1.set_xlim(0, 108); a1.set_xlabel("Problematic references caught by CoVe (%)", color=fg)
    a1.set_title("(a) CoVe detection by error type", color=fg, fontsize=11.5)
    a1.grid(axis="x", color=grid, ls=":", lw=0.7)
    for sp in a1.spines.values(): sp.set_color(fg if dark else "#888")

    # panel B: CoVe vs expert overall
    m = ["Sensitivity", "Specificity"]; v = [SENS, SPEC]
    bars = a2.bar(range(2), v, color=["#2A9D8F", "#4C72B0"], width=0.55)
    for b, val in zip(bars, v):
        a2.text(b.get_x() + b.get_width()/2, val + 0.4, f"{val:.1f}%", ha="center", va="bottom",
                color=fg, fontsize=12, fontweight="bold")
    a2.set_xticks(range(2)); a2.set_xticklabels(m, color=fg); a2.set_ylim(90, 102)
    a2.set_ylabel("CoVe vs expert (%)", color=fg)
    a2.set_title("(b) CoVe vs expert adjudication", color=fg, fontsize=11.5)
    a2.grid(axis="y", color=grid, ls=":", lw=0.7)
    for sp in a2.spines.values(): sp.set_color(fg if dark else "#888")

    fig.suptitle("Chain-of-Verification performance against expert adjudication\n"
                 "270 references, 62 problematic, single expert reviewer",
                 color=fg, fontsize=11.5, y=1.06)
    fig.tight_layout()
    fn = f"fig3_validation{'_dark' if dark else ''}.png"
    fig.savefig(os.path.join(A, fn), dpi=300, bbox_inches="tight", facecolor=bg); plt.close()
    print("saved", fn)

plot(False); plot(True)
