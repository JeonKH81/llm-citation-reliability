#!/usr/bin/env python3
"""Confirmatory generation pipeline — 3 models x 9 topics x 10 runs = 270 reviews.
Standardized prompt (input/PROMPT_confirmatory.md), fresh API call per run,
web/tools OFF, provider-default decoding (temperature etc. omitted), high max-output.
Resumable (skips existing output files). PHI: none (tool-validation study)."""
import os, re, sys, json, time, urllib.request, urllib.error, datetime, argparse, random
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(ROOT, "..", ".."))
ENV = os.path.expanduser("~/.config/cove-refhalluc-2026/.env")
ARM = os.environ.get("ARM_DIR", "parametric_supp")   # gen.py = no-tools (parametric supplement) generator
RAW_DIR = os.path.join(ROOT, ARM, "raw")
LOG = os.path.join(ROOT, ARM, "gen_log.jsonl")
PROMPT_MD = os.path.join(PROJ, "input", "PROMPT_confirmatory.md")
TOPICS = os.path.join(ROOT, "topics.json")

MAX_OUT = {"anthropic": 12000, "openai": 16000, "google": 24000}  # output cap (generous; thinking models need headroom). NOT a decoding default.
TRUNC = {"MAX_TOKENS", "length", "MAXTOKENS"}
RETRIES = 5

def is_good(path):
    """A saved record is 'done' only if it parsed references and was not truncated."""
    try:
        r = json.load(open(path))
    except Exception:
        return False
    ps = r.get("parse_status", "")
    return (ps.startswith("ok") or ps.startswith("partial_count")) and (r.get("finish") not in TRUNC)

def load_env():
    for ln in open(ENV):
        m = re.match(r'\s*export\s+(\w+)="(.*)"\s*$', ln)
        if m: os.environ[m.group(1)] = m.group(2)

def load_prompt_template():
    txt = open(PROMPT_MD).read()
    m = re.search(r"```\n(.*?)\n```", txt, re.S)
    if not m: sys.exit("could not extract prompt block")
    return m.group(1).strip()

def http_post(url, headers, payload, timeout=300):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

# ---- provider callers: return dict(model_returned, text, finish, usage, sent_params) ----
def call_anthropic(prompt):
    payload = {"model": "claude-opus-4-8", "max_tokens": MAX_OUT["anthropic"],
               "messages": [{"role": "user", "content": prompt}]}  # temperature omitted -> default
    d = http_post("https://api.anthropic.com/v1/messages",
                  {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
                   "content-type": "application/json"}, payload)
    return {"model_returned": d.get("model"),
            "text": "".join(b.get("text", "") for b in d.get("content", [])),
            "finish": d.get("stop_reason"), "usage": d.get("usage"),
            "sent_params": {"max_tokens": MAX_OUT["anthropic"], "temperature": "provider_default(omitted)"}}

def call_openai(prompt):
    payload = {"model": "gpt-5.5-2026-04-23", "max_completion_tokens": MAX_OUT["openai"],
               "messages": [{"role": "user", "content": prompt}]}  # temperature omitted -> default
    d = http_post("https://api.openai.com/v1/chat/completions",
                  {"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"], "content-type": "application/json"}, payload)
    ch = d["choices"][0]
    return {"model_returned": d.get("model"), "text": ch["message"].get("content", ""),
            "finish": ch.get("finish_reason"), "usage": d.get("usage"),
            "sent_params": {"max_completion_tokens": MAX_OUT["openai"], "temperature": "provider_default(omitted)"}}

def call_gemini(prompt):
    payload = {"contents": [{"parts": [{"text": prompt}]}],
               "generationConfig": {"maxOutputTokens": MAX_OUT["google"]}}  # temperature/topP/topK omitted -> default
    url = ("https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key="
           + os.environ["GOOGLE_API_KEY"])
    d = http_post(url, {"content-type": "application/json"}, payload)
    cand = (d.get("candidates") or [{}])[0]
    text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
    return {"model_returned": d.get("modelVersion"), "text": text,
            "finish": cand.get("finishReason"), "usage": d.get("usageMetadata"),
            "sent_params": {"maxOutputTokens": MAX_OUT["google"], "temperature": "provider_default(omitted)"}}

CALLERS = {"anthropic": call_anthropic, "openai": call_openai, "google": call_gemini}

def parse_refs(text):
    """Extract the JSON reference array (last ```json block, else last [...] array)."""
    status, refs = "fail", None
    blocks = re.findall(r"```json\s*(.*?)```", text, re.S) or re.findall(r"```\s*(\[.*?\])\s*```", text, re.S)
    cand = blocks[-1] if blocks else None
    if cand is None:
        m = re.findall(r"(\[\s*\{.*?\}\s*\])", text, re.S)
        cand = m[-1] if m else None
    if cand:
        try:
            refs = json.loads(cand)
            if isinstance(refs, list) and refs:
                status = "ok" if len(refs) == 30 else "partial_count(%d)" % len(refs)
        except Exception as e:
            status = "json_error"
    return status, refs

def one(model, topic, run, template):
    key = model["key"]; prov = model["provider"]
    out = os.path.join(RAW_DIR, f"{key}__{topic['slug']}__run{run:02d}.json")
    if os.path.exists(out) and is_good(out):
        return ("skip", out)
    prompt = template.replace("[TOPIC]", topic["prompt_topic"])
    err = None
    for attempt in range(RETRIES):
        try:
            res = CALLERS[prov](prompt)
            pstatus, refs = parse_refs(res["text"])
            rec = {"model_key": key, "model_requested": model["model_id"], "model_returned": res["model_returned"],
                   "provider": prov, "topic_slug": topic["slug"], "tier": topic["tier"],
                   "prompt_topic": topic["prompt_topic"], "run": run,
                   "timestamp": datetime.datetime.now().astimezone().isoformat(),
                   "decoding": res["sent_params"], "finish": res["finish"], "usage": res["usage"],
                   "parse_status": pstatus, "n_refs": (len(refs) if isinstance(refs, list) else 0),
                   "parsed_refs": refs, "raw_text": res["text"]}
            json.dump(rec, open(out, "w"), ensure_ascii=False, indent=1)
            return (pstatus, out)
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:300]
            err = f"HTTP {e.code}: {body}"
            if e.code in (429, 500, 502, 503, 529):
                time.sleep((2 ** attempt) + random.random()); continue
            break
        except Exception as e:
            err = repr(e); time.sleep((2 ** attempt) + random.random()); continue
    return ("ERROR", err)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="1 run per model (peripartum_cardiomyopathy) = 3 calls")
    ap.add_argument("--models", default="claude,gpt,gemini")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    load_env()
    os.makedirs(RAW_DIR, exist_ok=True)
    cfg = json.load(open(TOPICS))
    template = load_prompt_template()
    models = [m for m in cfg["models"] if m["key"] in args.models.split(",")]
    topics = cfg["topics"]; runs = cfg["runs_per_cell"]

    jobs = []
    if args.test:
        t = next(x for x in topics if x["slug"] == "peripartum_cardiomyopathy")
        for m in models: jobs.append((m, t, 1))
    else:
        for m in models:
            for t in topics:
                for r in range(1, runs + 1):
                    jobs.append((m, t, r))
    print(f"jobs: {len(jobs)} | workers: {args.workers}")
    done = {}
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(one, m, t, r, template): (m["key"], t["slug"], r) for m, t, r in jobs}
        for f in as_completed(futs):
            mk, ts, r = futs[f]
            status, info = f.result()
            done[status] = done.get(status, 0) + 1
            line = {"t": datetime.datetime.now().isoformat(), "cell": f"{mk}/{ts}/run{r}", "status": status}
            if status == "ERROR": line["err"] = info
            open(LOG, "a").write(json.dumps(line, ensure_ascii=False) + "\n")
            print(f"[{sum(done.values())}/{len(jobs)}] {mk}/{ts}/run{r:02d} -> {status}")
    print("SUMMARY:", json.dumps(done))

if __name__ == "__main__":
    main()
