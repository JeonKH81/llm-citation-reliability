#!/usr/bin/env python3
"""Supplement: model behavioral characterization.
(1) GPT-5.5 refusal (no-tools/parametric arm), (2) Gemini non-grounding (web arm),
(3) parametric vs web-search hallucination per model."""
import json, glob, os, re
from collections import defaultdict, Counter
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

A = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(A, "..", "data")
MODS = ["gpt", "claude", "gemini"]
MLAB = {"gpt": "GPT-5.5", "claude": "Claude Opus 4.8", "gemini": "Gemini 3.5 Flash"}
MC = {"gpt": "#2A9D8F", "claude": "#E76F51", "gemini": "#6A4C93"}
TIERS = ["low", "moderate", "high"]
REF = re.compile(r"(can.?t|cannot|sorry|unable|risk fabricat|without verification|not able to)", re.I)

def rate_from_verdicts(path):
    r = defaultdict(lambda: [0, 0])
    for l in open(path):
        d = json.loads(l)
        if d["verdict"] == "omission": continue
        r[d["model_key"]][1] += 1
        if d["problematic"]: r[d["model_key"]][0] += 1
    return {m: (100 * r[m][0] / r[m][1] if r[m][1] else None, r[m][1]) for m in MODS}

# --- (1) refusal (parametric) ---
refus = defaultdict(lambda: defaultdict(int)); attempted = defaultdict(lambda: defaultdict(int))
for f in glob.glob(os.path.join(DATA, "parametric_supp", "raw", "*.json")):
    d = json.load(open(f)); attempted[d["model_key"]][d["tier"]] += 1
    if d["parse_status"] in ("fail", "refusal") and len(d.get("raw_text", "")) < 1500 and REF.search(d.get("raw_text", "")[:600]):
        refus[d["model_key"]][d["tier"]] += 1

# --- (2) search behavior (web) ---
searches = defaultdict(list)
for f in glob.glob(os.path.join(DATA, "main_websearch", "raw", "*.json")):
    d = json.load(open(f)); searches[d["model_key"]].append(d.get("searches") or 0)

# --- (3) parametric vs web hallucination ---
para = rate_from_verdicts(os.path.join(DATA, "parametric_supp", "verdicts.jsonl"))
web = rate_from_verdicts(os.path.join(DATA, "main_websearch", "verdicts.jsonl"))

print("=== (1) GPT refusal by tier (parametric/no-tools) ===")
for m in MODS:
    print(f"  {m}: " + " ".join(f"{t}={refus[m][t]}/{attempted[m][t]}" for t in TIERS))
print("\n=== (2) web-search use ===")
for m in MODS:
    s = searches[m]; print(f"  {m}: mean {sum(s)/len(s):.1f} searches/review, {100*sum(1 for x in s if x>0)/len(s):.0f}% grounded")
print("\n=== (3) parametric vs web hallucination (% problematic, n) ===")
for m in MODS:
    pv, pn = para[m]; wv, wn = web[m]
    pv_s = f"{pv:.1f}% (n={pn})" if pv is not None else "n/a"
    print(f"  {m}: parametric {pv_s}  ->  web {wv:.1f}% (n={wn})")

# ===== FIGURE =====
fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.6), gridspec_kw={"width_ratios": [1, 1.2]})
# panel a: GPT refusal by tier
x = range(3)
a1.bar(x, [100 * refus["gpt"][t] / attempted["gpt"][t] for t in TIERS], color="#2A9D8F", width=0.6)
for i, t in enumerate(TIERS):
    a1.text(i, 100 * refus["gpt"][t] / attempted["gpt"][t] + 2, f"{refus['gpt'][t]}/{attempted['gpt'][t]}", ha="center", fontsize=9)
a1.set_xticks(x); a1.set_xticklabels(["low", "moderate", "high"]); a1.set_ylim(0, 105)
a1.set_ylabel("GPT-5.5 refusal rate (%)"); a1.set_title("(a) GPT-5.5 refuses to cite from memory\n(no-tools arm) — most on low-resource topics", fontsize=10.5)
a1.spines[["top", "right"]].set_visible(False)
# panel b: parametric vs web hallucination, paired
w = 0.36
for j, arm, hatch in [(0, para, ""), (1, web, "//")]:
    xs = [i + (j - 0.5) * w for i in range(3)]
    ys = [arm[m][0] if arm[m][0] is not None else 0 for m in MODS]
    bars = a2.bar(xs, ys, w, color=[MC[m] for m in MODS], alpha=0.95 if j == 1 else 0.55,
                  hatch=hatch, edgecolor="white",
                  label="web-search (main)" if j == 1 else "no-tools (parametric)")
    for xi, m in zip(xs, MODS):
        v = arm[m][0]
        a2.text(xi, (v or 0) + 1, "refused*" if (m == "gpt" and j == 0) else f"{v:.0f}" if v is not None else "", ha="center", fontsize=8)
a2.set_xticks(range(3)); a2.set_xticklabels([MLAB[m].split()[0] for m in MODS])
a2.set_ylabel("Hallucination rate (%)"); a2.set_ylim(0, 70)
a2.set_title("(b) No-tools vs web-search hallucination\nAll models improve with web search (GPT also stops refusing)", fontsize=10.5)
a2.legend(frameon=False, fontsize=9, loc="upper left")
a2.spines[["top", "right"]].set_visible(False)
a2.text(0.5, -10, "*GPT-5.5 refused 34/90 no-tools reviews (mostly low-resource); shown rate is non-refused subset",
        transform=a2.transAxes, ha="center", fontsize=7, color="#666")
fig.suptitle("Supplement: model behavioral differences under the citation task", fontsize=12, y=1.03)
fig.tight_layout()
fig.savefig(os.path.join(A, "figS1_behavior.png"), dpi=300, bbox_inches="tight"); plt.close()
print("\nsaved figS1_behavior.png")

# tables (md)
md = "## Supplementary Table S1. GPT-5.5 refusal rate by resource tier (no-tools arm)\n\n"
md += "| Tier | GPT-5.5 refusals | Claude | Gemini |\n|---|---|---|---|\n"
for t in TIERS:
    md += f"| {t} | {refus['gpt'][t]}/{attempted['gpt'][t]} | {refus['claude'][t]}/{attempted['claude'][t]} | {refus['gemini'][t]}/{attempted['gemini'][t]} |\n"
md += ("\n## Supplementary Table S2. Web-search use (main arm)\n\n"
       "| Model | Mean reported search calls/review | Reviews with grounding metadata |\n|---|---|---|\n")
for m in MODS:
    s = searches[m]
    val = "n/r¹" if m == "gemini" else f"{sum(s)/len(s):.1f}"
    grd = "0%¹" if m == "gemini" else f"{100*sum(1 for x in s if x>0)/len(s):.0f}%"
    md += f"| {MLAB[m]} | {val} | {grd} |\n"
md += ("\n¹Gemini 3.5 Flash returned no grounding metadata, so its search use is not directly observable; "
       "however its hallucination fell from 66.1% (no-tools) to 27.0% (web), and verified citations rose "
       "from 6% to 70%, indicating it did leverage the search tool (Table S3).\n")
md += "\n## Supplementary Table S3. No-tools vs web-search hallucination (% problematic)\n\n| Model | No-tools (parametric) | Web-search (main) |\n|---|---|---|\n"
for m in MODS:
    pv, pn = para[m]; wv, wn = web[m]
    pv_s = f"{pv:.1f}% (n={pn})" if pv is not None else "refused"
    md += f"| {MLAB[m]} | {pv_s} | {wv:.1f}% (n={wn}) |\n"
md += "\n*GPT-5.5 no-tools rate is on the 56 non-refused reviews (refused 34/90, mostly low-resource).*\n"
open(os.path.join(A, "tables_supplement.md"), "w").write(md)
print("saved tables_supplement.md")
