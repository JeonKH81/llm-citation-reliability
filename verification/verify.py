#!/usr/bin/env python3
"""Confirmatory verification pipeline (Arm 1, automated).
Oracle: PubMed (primary) + Crossref (lightweight backstop). Implements the D9
full-field rubric with normalization and the pre-specified benign list.

Per reference verdict (primary 'problematic' = field_error | misattribution | fabrication):
  omission        : no stated identifier            (excluded from primary denominator)
  verified        : correct paper, all fields ok    (not problematic)
  verified_benign : correct paper, only benign diffs (not problematic; benign flags logged)
  field_error     : correct paper (PMID+title), >=1 non-benign field wrong (problematic; severity=field)
  misattribution  : stated PMID points elsewhere/invalid but claimed paper exists (problematic; severity=identity)
  fabrication     : claimed paper found nowhere      (problematic; severity=identity)
  real_non_pubmed : claimed paper real via Crossref, not in PubMed (NOT hallucination; out-of-scope)

Outputs: master_pubmed_map.json (cache), verdicts.jsonl, verdicts_summary.json.
NOTE: automated metric; to be calibrated against the 270-ref expert gold set (Arm 2)."""
import os, re, sys, json, time, glob, unicodedata, urllib.request, urllib.parse, urllib.error

ROOT = os.path.dirname(os.path.abspath(__file__))
ARM = os.environ.get("ARM_DIR", "main_websearch")  # or parametric_supp
BASE = os.path.join(ROOT, ARM)
RAW_DIR = os.path.join(BASE, "raw")
ENV = os.path.expanduser("~/.config/cove-refhalluc-2026/.env")
PMAP = os.path.join(BASE, "master_pubmed_map.json")
REVSEARCH = os.path.join(BASE, "reverse_title_cache.json")
CROSSREF = os.path.join(BASE, "crossref_cache.json")
VERDICTS = os.path.join(BASE, "verdicts.jsonl")
SUMMARY = os.path.join(BASE, "verdicts_summary.json")
print(f"[verify arm: {ARM}]")
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
NCBI_KEY = None  # set from env if present

def load_env():
    if os.path.exists(ENV):
        for ln in open(ENV):
            m = re.match(r'\s*export\s+(\w+)="(.*)"\s*$', ln)
            if m: os.environ[m.group(1)] = m.group(2)
    global NCBI_KEY
    NCBI_KEY = os.environ.get("NCBI_API_KEY")

def _get(url, timeout=30):
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503): time.sleep(1.5 * (attempt + 1)); continue
            raise
        except Exception:
            time.sleep(1.0 * (attempt + 1))
    return None

def _rate(): time.sleep(0.11 if NCBI_KEY else 0.34)  # 10/s with key else ~3/s

# ---------- normalization ----------
def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))

def norm(s):
    if s is None: return ""
    s = strip_accents(str(s)).casefold()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def tokens(s): return set(norm(s).split())

def jaccard(a, b):
    A, B = tokens(a), tokens(b)
    return (len(A & B) / len(A | B)) if (A | B) else 0.0

def title_match(claim, truth):
    """Return (match, benign_subtitle). Subtitle omission / minor wording tolerated."""
    nc, nt = norm(claim), norm(truth)
    if not nc or not nt: return (False, False)
    if nc == nt: return (True, False)
    mc, mt = norm(claim.split(":")[0]), norm(truth.split(":")[0])  # main title before subtitle
    if mc and mc == mt: return (True, True)  # subtitle omission
    j = jaccard(nc, nt)
    if j >= 0.85: return (True, False)
    if j >= 0.6 and (mc == mt or nc.startswith(mt[:20]) or nt.startswith(mc[:20])): return (True, True)
    return (False, False)

def surname(name):
    n = norm(name.split(",")[0])           # first listed author
    return n.split(" ")[0] if n else ""    # leading token = family name (Vancouver "Sliwa K")

def surnames_list(s):
    """Ordered family names from a claim author string ('Smith J, Lee K, et al.') or a
    PubMed authors list (['Smith J', 'Lee K', ...])."""
    if isinstance(s, list):
        parts = [x.get("name", "") if isinstance(x, dict) else str(x) for x in s]
    else:
        parts = str(s or "").split(",")
    out = []
    for p in parts:
        p = p.strip()
        if not p or re.match(r"(?i)^(et al|and others|others)\.?$", p):
            continue
        sn = norm(p).split(" ")
        sn = sn[0] if sn else ""
        if sn and not re.match(r"(?i)(group|investigators|committee|consortium|trial|study)", sn):
            out.append(sn)
    return out

def year_of(s):
    m = re.search(r"(19|20)\d\d", str(s)); return int(m.group(0)) if m else None

def start_page(s):
    m = re.match(r"\s*([A-Za-z]?\d+)", str(s or "")); return m.group(1).lower() if m else ""

def norm_doi(s):
    s = str(s or "").strip().lower()
    s = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", s)
    s = re.sub(r"^doi:\s*", "", s)
    return s.strip().rstrip(".")

def journal_match(claim, src, full):
    nc = norm(claim)
    if not nc: return True  # no claim -> don't penalize
    ns, nf = norm(src), norm(full)
    if nc in (ns, nf): return True
    # abbrev<->full: token containment either direction
    Tc = tokens(claim)
    if Tc and (Tc <= tokens(full) or tokens(src) <= Tc or jaccard(claim, full) >= 0.5 or jaccard(claim, src) >= 0.6):
        return True
    # initialism, e.g. "JSCAI" = Journal of the Society for Cardiovascular Angiography & Interventions
    cl = re.sub(r"[^a-z]", "", nc); stop = {"of", "the", "for", "and", "a", "an", "in", "on"}
    if cl and len(cl) <= 8:
        for name in (full, src):
            initials = "".join(w[0] for w in norm(name).split() if w and w not in stop)
            if cl == initials:
                return True
    return False

# ---------- PubMed ----------
def collect_pmids():
    pmids = set()
    for f in glob.glob(os.path.join(RAW_DIR, "*.json")):
        rec = json.load(open(f))
        for r in (rec.get("parsed_refs") or []):
            p = str(r.get("pmid", "")).strip()
            if re.fullmatch(r"\d{1,9}", p): pmids.add(p)
    return sorted(pmids)

def build_pubmed_map():
    cache = json.load(open(PMAP)) if os.path.exists(PMAP) else {}
    pmids = collect_pmids()
    todo = [p for p in pmids if p not in cache or (cache.get(p) and "authors" not in cache[p])]
    print(f"unique stated PMIDs: {len(pmids)} | to fetch: {len(todo)}")
    for i in range(0, len(todo), 200):
        chunk = todo[i:i + 200]
        key = ("&api_key=" + NCBI_KEY) if NCBI_KEY else ""
        url = f"{EUTILS}/esummary.fcgi?db=pubmed&id={','.join(chunk)}&retmode=json{key}"
        d = _get(url); _rate()
        res = (d or {}).get("result", {})
        for p in chunk:
            r = res.get(p)
            if not r or r.get("error"):
                cache[p] = None; continue
            doi = next((x["value"] for x in r.get("articleids", []) if x.get("idtype") == "doi"), None)
            cache[p] = {"title": r.get("title", ""), "source": r.get("source", ""),
                        "fulljournalname": r.get("fulljournalname", ""), "year": year_of(r.get("pubdate", "")),
                        "volume": r.get("volume", ""), "issue": r.get("issue", ""), "pages": r.get("pages", ""),
                        "first_author": (r.get("authors", [{}]) or [{}])[0].get("name", ""),
                        "authors": [a.get("name", "") for a in (r.get("authors") or [])[:6]], "doi": doi}
        json.dump(cache, open(PMAP, "w"), ensure_ascii=False)
        print(f"  fetched {min(i+200,len(todo))}/{len(todo)}")
    return cache

def reverse_title_exists(title, cache):
    """esearch the claimed title; return True if PubMed has a plausible match."""
    nt = norm(title)
    if len(nt) < 8: return None
    if nt in cache: return cache[nt]
    key = ("&api_key=" + NCBI_KEY) if NCBI_KEY else ""
    term = urllib.parse.quote(f'"{title}"[Title]')
    d = _get(f"{EUTILS}/esearch.fcgi?db=pubmed&term={term}&retmode=json{key}"); _rate()
    found = bool((d or {}).get("esearchresult", {}).get("idlist"))
    if not found:  # looser: title words AND
        term2 = urllib.parse.quote(" ".join(nt.split()[:12]) + "[Title]")
        d2 = _get(f"{EUTILS}/esearch.fcgi?db=pubmed&term={term2}&retmode=json{key}"); _rate()
        found = bool((d2 or {}).get("esearchresult", {}).get("idlist"))
    cache[nt] = found
    json.dump(cache, open(REVSEARCH, "w"), ensure_ascii=False)
    return found

def crossref_exists(title, doi, cache):
    ckey = (doi or norm(title))[:120]
    if ckey in cache: return cache[ckey]
    found = False
    try:
        if doi:
            d = _get("https://api.crossref.org/works/" + urllib.parse.quote(doi), timeout=20)
            found = bool(d and d.get("status") == "ok")
        if not found and title and len(norm(title)) >= 10:
            q = urllib.parse.quote(title)
            d = _get(f"https://api.crossref.org/works?query.bibliographic={q}&rows=1", timeout=20)
            items = (d or {}).get("message", {}).get("items", [])
            if items:
                found = jaccard(title, " ".join(items[0].get("title", []) or [""])) >= 0.7
    except Exception:
        found = False
    time.sleep(0.2)
    cache[ckey] = found
    json.dump(cache, open(CROSSREF, "w"), ensure_ascii=False)
    return found

# ---------- per-reference classification ----------
def classify_fields(claim, truth):
    problematic, benign = [], []
    cy, ty = year_of(claim.get("year")), truth.get("year")
    if cy and ty:
        dy = abs(cy - ty)
        if dy == 1: benign.append("epub_print_year")
        elif dy > 1: problematic.append("year")
    ca = surnames_list(claim.get("authors", ""))
    ta = surnames_list(truth.get("authors") or truth.get("first_author", ""))
    k = min(3, len(ca), len(ta))          # compare order of the first few authors
    if k >= 1 and ca[:k] != ta[:k]:
        problematic.append("authors")
    cv = norm(claim.get("volume")); tv = norm(truth.get("volume"))
    if cv and tv and cv != tv: problematic.append("volume")
    cp = start_page(claim.get("pages")); tp = start_page(truth.get("pages"))
    if cp and tp and cp != tp: problematic.append("start_page")
    if not journal_match(claim.get("journal", ""), truth.get("source", ""), truth.get("fulljournalname", "")):
        problematic.append("journal")
    cd = norm_doi(claim.get("doi")); td = norm_doi(truth.get("doi"))
    if cd and td and cd != td: problematic.append("doi")   # stated DOI != PubMed-recorded DOI
    ci = norm(claim.get("issue")); ti = norm(truth.get("issue"))
    if ci and ti and ci != ti: benign.append("issue")
    return problematic, benign

def classify_ref(ref, pmap, revcache, crcache):
    pmid = str(ref.get("pmid", "")).strip()
    doi = str(ref.get("doi", "")).strip()
    title = str(ref.get("title", "")).strip()
    pmid_ok = bool(re.fullmatch(r"\d{1,9}", pmid))
    has_id = pmid_ok or bool(doi)
    if not has_id:
        return {"verdict": "omission", "problematic": False, "severity": None, "fields": [], "benign": []}
    truth = pmap.get(pmid) if pmid_ok else None
    if truth:  # stated PMID resolves
        tmatch, sub = title_match(title, truth["title"])
        if tmatch:
            prob, benign = classify_fields(ref, truth)
            if sub: benign.append("subtitle")
            if prob:
                return {"verdict": "field_error", "problematic": True, "severity": "field", "fields": prob, "benign": benign}
            return {"verdict": ("verified_benign" if benign else "verified"), "problematic": False,
                    "severity": None, "fields": [], "benign": benign}
        # PMID resolves to a DIFFERENT paper -> wrong identifier, always problematic
        if reverse_title_exists(title, revcache) or crossref_exists(title, doi, crcache):
            return {"verdict": "misattribution", "problematic": True, "severity": "identity", "fields": ["wrong_paper_for_pmid"], "benign": []}
        return {"verdict": "fabrication", "problematic": True, "severity": "identity", "fields": ["no_such_paper"], "benign": []}
    if pmid:  # a PMID was stated but is invalid or unresolved (incl. garbled non-numeric) -> problematic
        if reverse_title_exists(title, revcache) or crossref_exists(title, doi, crcache):
            return {"verdict": "misattribution", "problematic": True, "severity": "identity", "fields": ["bad_pmid_real_paper"], "benign": []}
        return {"verdict": "fabrication", "problematic": True, "severity": "identity", "fields": ["no_such_paper"], "benign": []}
    # no PMID stated at all (DOI only) -> a real non-PubMed article is out of scope, not a hallucination
    if reverse_title_exists(title, revcache) or crossref_exists(title, doi, crcache):
        return {"verdict": "real_non_pubmed", "problematic": False, "severity": None, "fields": ["non_pubmed"], "benign": []}
    return {"verdict": "fabrication", "problematic": True, "severity": "identity", "fields": ["no_such_paper"], "benign": []}

def main():
    load_env()
    print("NCBI key:", "yes" if NCBI_KEY else "no (3/s)")
    pmap = build_pubmed_map()
    revcache = json.load(open(REVSEARCH)) if os.path.exists(REVSEARCH) else {}
    crcache = json.load(open(CROSSREF)) if os.path.exists(CROSSREF) else {}
    out = open(VERDICTS, "w")
    counts = {}
    files = sorted(glob.glob(os.path.join(RAW_DIR, "*.json")))
    for fi, f in enumerate(files):
        rec = json.load(open(f))
        for ref in (rec.get("parsed_refs") or []):
            v = classify_ref(ref, pmap, revcache, crcache)
            row = {"model_key": rec["model_key"], "model_returned": rec.get("model_returned"),
                   "topic_slug": rec["topic_slug"], "tier": rec["tier"], "run": rec["run"],
                   "index": ref.get("index"), "pmid": ref.get("pmid"), "doi": ref.get("doi"),
                   **v}
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            counts[v["verdict"]] = counts.get(v["verdict"], 0) + 1
        if (fi + 1) % 20 == 0: print(f"  classified {fi+1}/{len(files)} reviews")
    out.close()
    json.dump(counts, open(SUMMARY, "w"), indent=1)
    print("VERDICT COUNTS:", json.dumps(counts, indent=1))

if __name__ == "__main__":
    main()
