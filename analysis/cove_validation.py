#!/usr/bin/env python3
"""cove arm (Arm 2): validate verification strategies against the EXPERT gold standard.
Strategy ladder vs expert (problematic = expert verdict != 'real'):
  S1 no-check        : flag nothing
  S2 PMID-existence  : flag if stated PMID does not resolve to any PubMed record
  S3 PMID-title bind : flag if stated PMID does not resolve to the *claimed* paper
  S4 cove full-field : flag if any non-benign discrepancy (verify.py problematic)
"""
import json, csv, os, re
from collections import Counter

A = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(A, "..", "data", "main_websearch")

# --- expert gold standard (cp949) ---
def load_expert():
    for e in ("utf-8-sig", "cp949", "euc-kr", "cp1252"):
        try:
            rows = list(csv.DictReader(open(os.path.join(A, "cove_EXPERT_adjudication_sheet_JKH_adjudicated.csv"), encoding=e)))
            if rows and "review" in rows[0]:
                return rows
        except Exception:
            continue
    raise SystemExit("cannot read expert CSV")
erows = load_expert()
vcol = [c for c in erows[0] if c.startswith("EXPERT_verdict")][0]
expert = {(r["review"].strip(), str(r["index"]).strip()): (r[vcol] or "").strip().lower() for r in erows}

# --- key: R-code -> model/topic/run ---
key = {k["code"]: k for k in json.load(open(os.path.join(A, "cove_selection_KEY.json")))}

# --- claimed refs + verify verdicts ---
pmap = json.load(open(os.path.join(D, "master_pubmed_map.json")))
verdicts = {}
for l in open(os.path.join(D, "verdicts.jsonl")):
    r = json.loads(l)
    verdicts[(r["model_key"], r["topic_slug"], r["run"], str(r["index"]))] = r

def norm(s):
    import unicodedata
    s = "".join(c for c in unicodedata.normalize("NFKD", str(s or "")) if not unicodedata.combining(c)).casefold()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s)).strip()
def title_match(a, b):
    na, nb = norm(a), norm(b)
    if not na or not nb: return False
    if na == nb: return True
    if norm(str(a).split(":")[0]) == norm(str(b).split(":")[0]): return True
    A_, B_ = set(na.split()), set(nb.split())
    return len(A_ & B_) / len(A_ | B_) >= 0.6 if (A_ | B_) else False

# --- build per-ref strategy flags + gold ---
recs = []
for code, kinfo in key.items():
    f = os.path.join(D, "raw", f"{kinfo['model']}__{kinfo['topic']}__run{kinfo['run']:02d}.json")
    rec = json.load(open(f))
    for ref in (rec.get("parsed_refs") or []):
        idx = str(ref.get("index"))
        gv = expert.get((code, idx))
        if gv is None: continue
        gold = 0 if gv == "real" else 1                      # expert: 1=problematic
        pmid = str(ref.get("pmid", "")).strip()
        resolves = bool(re.fullmatch(r"\d{1,9}", pmid)) and pmap.get(pmid) is not None
        binds = resolves and title_match(ref.get("title"), pmap[pmid]["title"])
        v = verdicts.get((kinfo["model"], kinfo["topic"], kinfo["run"], idx))
        s4 = int(bool(v and v["problematic"]))               # cove full-field
        s1, s2, s3 = 0, int(not resolves), int(not binds)
        recs.append({"code": code, "model": kinfo["model"], "idx": idx, "gold": gold,
                     "gold_verdict": gv, "S1": s1, "S2": s2, "S3": s3, "S4": s4,
                     "cove_verdict": (v["verdict"] if v else None)})

print(f"matched refs: {len(recs)} | expert problematic: {sum(r['gold'] for r in recs)}")

def metrics(flagkey):
    tp = sum(1 for r in recs if r["gold"] == 1 and r[flagkey] == 1)
    fn = sum(1 for r in recs if r["gold"] == 1 and r[flagkey] == 0)
    tn = sum(1 for r in recs if r["gold"] == 0 and r[flagkey] == 0)
    fp = sum(1 for r in recs if r["gold"] == 0 and r[flagkey] == 1)
    def w(k, n):  # Wilson 95% CI
        if n == 0: return (0, 0, 0)
        p = k / n; z = 1.96; d = 1 + z*z/n
        c = (p + z*z/(2*n)) / d; h = z*((p*(1-p)/n + z*z/(4*n*n))**0.5)/d
        return (100*p, 100*(c-h), 100*(c+h))
    sens = w(tp, tp+fn); spec = w(tn, tn+fp); ppv = w(tp, tp+fp); npv = w(tn, tn+fn)
    return tp, fp, tn, fn, sens, spec, ppv, npv

print("\n=== Verification-strategy ladder vs EXPERT gold standard ===")
names = {"S1": "1. No check (trust LLM)", "S2": "2. PMID exists", "S3": "3. PMID-title binding", "S4": "4. cove full-field"}
ladder = {}
for s in ["S1", "S2", "S3", "S4"]:
    tp, fp, tn, fn, se, sp, pp, nv = metrics(s)
    ladder[s] = {"sens": se, "spec": sp, "ppv": pp, "npv": nv, "tp": tp, "fp": fp, "tn": tn, "fn": fn}
    print(f"{names[s]:26s} sens {se[0]:5.1f}% ({se[1]:.0f}-{se[2]:.0f})  spec {sp[0]:5.1f}% ({sp[1]:.0f}-{sp[2]:.0f})  "
          f"PPV {pp[0]:4.0f}  NPV {nv[0]:4.0f}   [TP{tp} FP{fp} TN{tn} FN{fn}]")

# detection by expert error type (cove S4)
print("\n=== cove (S4) detection by expert error type ===")
for et in ["misattribution", "field_error", "fabricated"]:
    sub = [r for r in recs if r["gold_verdict"] == et]
    caught = sum(r["S4"] for r in sub)
    print(f"  {et:15s}: {caught}/{len(sub)} caught" + (f" ({100*caught/len(sub):.0f}%)" if sub else ""))

json.dump({"ladder": ladder, "n": len(recs), "expert_problematic": sum(r['gold'] for r in recs),
           "expert_dist": dict(Counter(r['gold_verdict'] for r in recs))},
          open(os.path.join(A, "cove_validation_results.json"), "w"), indent=1)
print("\nsaved cove_validation_results.json")
