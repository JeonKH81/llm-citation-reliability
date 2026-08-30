#!/usr/bin/env python3
"""Three-way comparison on the 270-ref validation set:
   expert gold standard  vs  verify.py (deterministic PubMed field-match)  vs  real CoVe (LLM factored).
Outputs per-method sensitivity/specificity vs expert, agreement, and a discordance list."""
import json, csv, os, glob
from collections import defaultdict

A = os.path.dirname(os.path.abspath(__file__))          # .../analysis/cove_real_run
ANA = os.path.dirname(A)                                  # .../analysis
DATA = os.path.join(ANA, "..", "data")
KEY = {k["code"]: k for k in json.load(open(os.path.join(ANA, "cove_selection_KEY.json")))}

# ---- expert gold ----
def load_expert():
    for e in ("utf-8-sig", "cp949", "euc-kr", "cp1252"):
        try:
            r = list(csv.DictReader(open(os.path.join(ANA, "cove_EXPERT_adjudication_sheet_JKH_adjudicated.csv"), encoding=e)))
            if r and "review" in r[0]: return r
        except Exception: pass
    raise SystemExit("expert csv")
er = load_expert()
vcol = [c for c in er[0] if c.startswith("EXPERT_verdict")][0]
# expert: real -> 0, anything else (field_error/misattribution/fabricated) -> 1 (problematic)
expert = {}
for r in er:
    v = (r[vcol] or "").strip().lower()
    expert[(r["review"].strip(), str(r["index"]).strip())] = 0 if v.startswith("real") else 1

# ---- verify.py verdicts (deterministic) ----
verd = {}
for l in open(os.path.join(DATA, "main_websearch", "verdicts.jsonl")):
    d = json.loads(l); verd[(d["model_key"], d["topic_slug"], d["run"], str(d["index"]))] = d

# ---- real CoVe outputs ----
cove = {}
for f in sorted(glob.glob(os.path.join(A, "output", "R*.json"))):
    rev = os.path.splitext(os.path.basename(f))[0]
    for c in json.load(open(f)):
        cove[(rev, str(c["index"]))] = c

# ---- join ----
rows = []
for code, k in KEY.items():
    for idx_key, gold in [((code, ix), g) for (rv, ix), g in expert.items() if rv == code]:
        code_, idx = idx_key
        # verify.py
        v = verd.get((k["model"], k["topic"], k["run"], idx))
        vpy = int(bool(v and v["problematic"])) if v else None
        # cove
        c = cove.get((code, idx))
        cv = c["problematic"] if c else None
        rows.append({"review": code, "index": idx, "model": k["model"],
                     "expert": gold, "verifypy": vpy,
                     "cove": (None if cv is None else int(bool(cv))),
                     "cove_verdict": (c["verdict"] if c else None),
                     "cove_notes": (c.get("notes","") if c else "")})

def metrics(pairs):   # pairs = [(gold, pred)] excluding None preds
    tp = sum(1 for g,p in pairs if g==1 and p==1); fn = sum(1 for g,p in pairs if g==1 and p==0)
    tn = sum(1 for g,p in pairs if g==0 and p==0); fp = sum(1 for g,p in pairs if g==0 and p==1)
    sens = tp/(tp+fn) if tp+fn else float('nan'); spec = tn/(tn+fp) if tn+fp else float('nan')
    acc = (tp+tn)/(tp+tn+fp+fn) if (tp+tn+fp+fn) else float('nan')
    return dict(tp=tp,fn=fn,tn=tn,fp=fp,sens=sens,spec=spec,acc=acc)

n_expert_prob = sum(1 for r in rows if r["expert"]==1)
print(f"N = {len(rows)} refs; expert problematic = {n_expert_prob}")
print(f"CoVe coverage: {sum(1 for r in rows if r['cove'] is not None)}/{len(rows)} (unverifiable/missing = {sum(1 for r in rows if r['cove'] is None)})")
print(f"verify.py coverage: {sum(1 for r in rows if r['verifypy'] is not None)}/{len(rows)}")

for name, key in [("verify.py (deterministic)", "verifypy"), ("real CoVe (LLM factored)", "cove")]:
    pairs = [(r["expert"], r[key]) for r in rows if r[key] is not None]
    m = metrics(pairs)
    print(f"\n=== {name} vs expert (n={len(pairs)}) ===")
    print(f"  sens {100*m['sens']:.1f}%  spec {100*m['spec']:.1f}%  acc {100*m['acc']:.1f}%   [TP{m['tp']} FN{m['fn']} TN{m['tn']} FP{m['fp']}]")

# CoVe vs verify.py agreement (where both present)
both = [(r["verifypy"], r["cove"]) for r in rows if r["verifypy"] is not None and r["cove"] is not None]
agree = sum(1 for a,b in both if a==b)
print(f"\n=== CoVe vs verify.py agreement: {agree}/{len(both)} = {100*agree/len(both):.1f}% ===")

# discordances CoVe vs expert
disc = [r for r in rows if r["cove"] is not None and r["cove"] != r["expert"]]
print(f"\n=== CoVe vs expert discordances: {len(disc)} ===")
for r in disc:
    print(f"  {r['review']}#{r['index']} ({r['model']}): expert={'prob' if r['expert'] else 'real'} "
          f"cove={'prob' if r['cove'] else 'real'} [{r['cove_verdict']}] {r['cove_notes'][:90]}")

json.dump(rows, open(os.path.join(A, "three_way_rows.json"), "w"), ensure_ascii=False, indent=1)
print("\nsaved three_way_rows.json")
