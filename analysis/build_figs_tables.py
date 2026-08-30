#!/usr/bin/env python3
"""Publication figures + tables for the main (web-search) arm."""
import json, csv, glob, os
from collections import defaultdict, Counter
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

A = os.path.dirname(os.path.abspath(__file__))
plt.rcParams.update({"font.size": 11, "font.family": "Arial Narrow",
                     "font.sans-serif": ["Arial Narrow", "Arial", "DejaVu Sans"],
                     "axes.spines.top": False,
                     "axes.spines.right": False, "figure.dpi": 300})
MC = {"gpt": "#2A9D8F", "claude": "#E76F51", "gemini": "#6A4C93"}
ML = {"gpt": "GPT-5.5", "claude": "Claude Opus 4.8", "gemini": "Gemini 3.5 Flash"}
TIERS = ["low", "moderate", "high"]
TIERLAB = {"low": "Low\n(~190–480)", "moderate": "Moderate\n(~1.2–1.9k)", "high": "High\n(~3.2–4.8k)"}

# ---- data ----
rows = [json.loads(l) for l in open(os.path.join(A, "..", "data", "main_websearch", "verdicts.jsonl"))]
crude = defaultdict(lambda: [0, 0])           # (model,tier) -> [problematic, denom]
vtype = defaultdict(Counter)                  # model -> verdict counts
for r in rows:
    vtype[r["model_key"]][r["verdict"]] += 1
    if r["verdict"] == "omission":
        continue
    k = (r["model_key"], r["tier"]); crude[k][1] += 1
    if r["problematic"]: crude[k][0] += 1

emm = {}
for row in csv.DictReader(open(os.path.join(A, "emm_main.csv"))):
    emm[(row["model"], row["tier"])] = (float(row["prob"]), float(row["asymp.LCL"]), float(row["asymp.UCL"]))

searches = defaultdict(list)
for f in glob.glob(os.path.join(A, "..", "data", "main_websearch", "raw", "*.json")):
    d = json.load(open(f)); searches[d["model_key"]].append(d.get("searches") or 0)

# ===== FIG 1: adjusted hallucination rate by model x tier =====
def fig1(dark=False):
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    bg = "#1e1e1e" if dark else "white"; fg = "white" if dark else "black"
    fig.patch.set_facecolor(bg); ax.set_facecolor(bg)
    w = 0.26; x = range(len(TIERS))
    for j, m in enumerate(["gpt", "claude", "gemini"]):
        ys = [emm[(m, t)][0] * 100 for t in TIERS]
        lo = [(emm[(m, t)][0] - emm[(m, t)][1]) * 100 for t in TIERS]
        hi = [(emm[(m, t)][2] - emm[(m, t)][0]) * 100 for t in TIERS]
        xs = [i + (j - 1) * w for i in x]
        ax.bar(xs, ys, w, color=MC[m], label=ML[m], yerr=[lo, hi], capsize=3,
               error_kw={"elinewidth": 1, "ecolor": fg})
        for xi, t in zip(xs, TIERS):
            top = emm[(m, t)][2] * 100
            ax.text(xi, top + 0.8, f"{emm[(m, t)][0]*100:.0f}", ha="center", va="bottom", fontsize=8.5, color=fg)
    ax.set_xticks(list(x)); ax.set_xticklabels([TIERLAB[t] for t in TIERS], color=fg)
    ax.set_ylabel("Adjusted reference hallucination rate (%)", color=fg)
    ax.set_xlabel("Literature resource level (PubMed articles)", color=fg)
    ax.set_title("Reference hallucination by model and literature-resource level", color=fg, fontsize=11.5)
    ax.tick_params(colors=fg); ax.set_ylim(0, 45)
    leg = ax.legend(frameon=False, loc="upper right"); [t.set_color(fg) for t in leg.get_texts()]
    for s in ax.spines.values(): s.set_color(fg)
    fig.tight_layout(); fig.savefig(os.path.join(A, f"fig1_model_tier{'_dark' if dark else ''}.png"),
                                    facecolor=bg); plt.close()

# ===== FIG 2: verdict-type composition by model =====
def fig2():
    # left (non-problematic) -> right (problematic); boundary marked per bar
    order  = ["verified", "verified_benign", "real_non_pubmed", "omission", "field_error", "misattribution", "fabrication"]
    labels = ["Verified", "Verified (benign)", "Real, non-PubMed", "Omission",
              "Field error", "Misattribution (valid PMID, wrong paper)", "Fabrication"]
    cols   = ["#2A9D8F", "#8AB17D", "#A8C5DA", "#BDBDBD", "#F4A261", "#E76F51", "#9D0208"]
    PROB = {"field_error", "misattribution", "fabrication"}
    fig, ax = plt.subplots(figsize=(9.6, 3.9))
    mods = ["gpt", "claude", "gemini"]
    tot = {m: sum(vtype[m].values()) for m in mods}
    bottom = [0.0, 0.0, 0.0]; nonprob_end = [0.0, 0.0, 0.0]
    for v, lab, c in zip(order, labels, cols):
        vals = [100 * vtype[m][v] / tot[m] for m in mods]
        ax.barh(range(3), vals, left=bottom, color=c, label=lab, height=0.62, edgecolor="white", linewidth=0.4)
        if v == "misattribution":
            for i, (b, x) in enumerate(zip(bottom, vals)):
                if x > 4: ax.text(b + x/2, i, f"{x:.0f}%", ha="center", va="center", color="white", fontsize=9.5, fontweight="bold")
        bottom = [b + x for b, x in zip(bottom, vals)]
        if v not in PROB: nonprob_end = list(bottom)
    # boundary line + total problematic label
    for i, m in enumerate(mods):
        prob = 100 * sum(vtype[m][k] for k in PROB) / tot[m]
        ax.plot([nonprob_end[i]]*2, [i-0.33, i+0.33], color="#222", lw=1.4, ls=(0,(2,1)))
        ax.text(101.5, i, f"{prob:.0f}%\nproblematic", va="center", ha="left", fontsize=9, fontweight="bold")
    ax.set_yticks(range(3)); ax.set_yticklabels([ML[m] for m in mods]); ax.invert_yaxis()
    ax.set_xlim(0, 100); ax.set_xlabel("Share of references (%)")
    ax.set_title("Reference error types by model",
                 fontsize=11)
    ax.legend(frameon=False, ncol=4, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.22))
    ax.margins(y=0.08)
    fig.subplots_adjust(left=0.15, right=0.82, bottom=0.34, top=0.86)
    fig.savefig(os.path.join(A, "fig2_verdict_types.png"), dpi=300); plt.close()

# ===== FIG 3: web-search use vs hallucination =====
def fig3():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.4, 4.0))
    mods = ["gpt", "claude", "gemini"]
    # left: mean searches per review
    means = [sum(searches[m]) / len(searches[m]) for m in mods]
    a1.bar(range(3), means, color=[MC[m] for m in mods])
    for i, m in enumerate(mods):
        lab = "n/r¹" if m == "gemini" else f"{means[i]:.1f}"
        a1.text(i, means[i] + 0.3, lab, ha="center", va="bottom", fontsize=9)
    a1.set_xticks(range(3)); a1.set_xticklabels([ML[m].split()[0] for m in mods])
    a1.set_ylabel("Mean web-search calls per review (reported)")
    a1.set_title("(a) Reported search calls", fontsize=10.5)
    a1.set_ylim(0, max(means) * 1.3 + 1)
    a1.text(0.5, -0.30, "¹Gemini did not return grounding metadata (search not observable),\n"
            "but its accuracy improved with the tool (see Supplement).", transform=a1.transAxes,
            ha="center", fontsize=7, color="#666")
    # right: overall hallucination
    overall = [100 * sum(crude[(m, t)][0] for t in TIERS) / sum(crude[(m, t)][1] for t in TIERS) for m in mods]
    a2.bar(range(3), overall, color=[MC[m] for m in mods])
    for i, v in enumerate(overall): a2.text(i, v + 0.5, f"{v:.0f}%", ha="center", va="bottom", fontsize=9)
    a2.set_xticks(range(3)); a2.set_xticklabels([ML[m].split()[0] for m in mods])
    a2.set_ylabel("Hallucination rate (%)"); a2.set_title("(b) Citation hallucination", fontsize=10.5)
    a2.set_ylim(0, 32)
    fig.suptitle("Web search ≠ accurate identifiers: Claude searched 11.5×/review yet erred in 27%",
                 fontsize=11, y=1.04)
    fig.tight_layout(); fig.savefig(os.path.join(A, "figS3_search_vs_accuracy.png"), bbox_inches="tight"); plt.close()

fig1(False); fig1(True); fig2(); fig3()
print("figures: fig1_model_tier(.png/_dark), fig2_verdict_types.png, figS3_search_vs_accuracy.png")

# ===== TABLES (HTML + Markdown) =====
def pct(x): return f"{x*100:.1f}"
# Table 1: rates by model x tier
t1 = [["Model", "Tier", "N refs", "Crude %", "Adjusted % (95% CI)"]]
for m in ["gpt", "claude", "gemini"]:
    for t in TIERS:
        p, n = crude[(m, t)]; pr, lo, hi = emm[(m, t)]
        t1.append([ML[m], t, str(n), pct(p / n), f"{pr*100:.1f} ({lo*100:.1f}–{hi*100:.1f})"])
# Table 2: hypothesis tests
t2 = [["Hypothesis / contrast", "Estimate", "p"],
      ["H1 model effect (LRT χ²(2))", "109.5", "<2.2e-16"],
      ["  GPT-5.5 vs Claude (OR)", "0.295", "<0.0001"],
      ["  GPT-5.5 vs Gemini (OR)", "0.297", "<0.0001"],
      ["  Claude vs Gemini (OR)", "1.01", "1.00 (ns)"],
      ["H2 publication-volume gradient (linear, log-odds)", "−0.361", "0.05 (ns)"],
      ["  publication-volume main effect (LRT χ²(2))", "3.77", "0.15 (ns)"],
      ["H3 model × volume interaction (LRT χ²(4))", "8.35", "0.08 (ns)"]]
# Table 3: verdict types
vt_order = ["verified", "verified_benign", "real_non_pubmed", "field_error", "misattribution", "fabrication", "omission"]
t3 = [["Verdict"] + [ML[m] for m in ["gpt", "claude", "gemini"]]]
for v in vt_order:
    t3.append([v] + [str(vtype[m][v]) for m in ["gpt", "claude", "gemini"]])

def md(tbl):
    out = ["| " + " | ".join(tbl[0]) + " |", "|" + "|".join(["---"] * len(tbl[0])) + "|"]
    for r in tbl[1:]: out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)

def html_tbl(tbl, cap):
    h = [f'<table><caption><b>{cap}</b></caption>', "<thead><tr>" + "".join(f"<th>{c}</th>" for c in tbl[0]) + "</tr></thead><tbody>"]
    for r in tbl[1:]: h.append("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>")
    h.append("</tbody></table>"); return "\n".join(h)

open(os.path.join(A, "tables_main.md"), "w").write(
    "## Table 1. Reference hallucination rate by model and resource level (web-search arm)\n\n" + md(t1) +
    "\n\n## Table 2. Hypothesis tests (GLMM)\n\n" + md(t2) +
    "\n\n## Table 3. Reference verdict counts by model (of 2,700 each)\n\n" + md(t3) + "\n")

style = "<style>body{font-family:'Times New Roman',Times,serif;margin:30px;color:#222}table{border-collapse:collapse;margin:18px 0;font-size:13px}caption{text-align:left;padding:6px 0;font-size:14px}th,td{border:1px solid #bbb;padding:6px 10px;text-align:left}thead th{background:#2A9D8F;color:#fff}tbody tr:nth-child(even){background:#f3f7f6}h1{font-size:18px}</style>"
open(os.path.join(A, "tables_main.html"), "w").write(
    "<html><head><meta charset='utf-8'>" + style + "</head><body><h1>STUDY2 — Main (web-search) arm: Tables</h1>" +
    html_tbl(t1, "Table 1. Reference hallucination rate by model and resource level") +
    html_tbl(t2, "Table 2. Hypothesis tests (mixed-effects logistic GLMM)") +
    html_tbl(t3, "Table 3. Reference verdict counts by model (n=2,700 each)") + "</body></html>")
print("tables: tables_main.md, tables_main.html")
