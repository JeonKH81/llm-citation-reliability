#!/usr/bin/env python3
"""Live progress for the confirmatory generation. Run anytime: python3 status.py"""
import os, glob, json, datetime, subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
ARM = os.environ.get("ARM_DIR", "main_websearch")  # or parametric_supp
RAW = os.path.join(ROOT, ARM, "raw")
LOG = os.path.join(ROOT, ARM, "gen_log.jsonl")
TOTAL_PER = 90
MODELS = ["claude", "gpt", "gemini"]
print(f"  [arm: {ARM}]")

def bar(done, total, width=34):
    filled = int(width * done / total) if total else 0
    return "█" * filled + "░" * (width - filled)

def good(path):
    try:
        r = json.load(open(path)); ps = r.get("parse_status", "")
        return (ps.startswith("ok") or ps.startswith("partial_count")) and r.get("finish") not in {"MAX_TOKENS", "length"}
    except Exception:
        return False

counts = {m: 0 for m in MODELS}
goodc = {m: 0 for m in MODELS}
for f in glob.glob(os.path.join(RAW, "*.json")):
    name = os.path.basename(f)
    m = name.split("__")[0]
    if m in counts:
        counts[m] += 1
        if good(f): goodc[m] += 1

total_good = sum(goodc.values())
print("\n  CONFIRMATORY GENERATION  —  3 models × 9 topics × 10 runs = 270 reviews\n")
for m in MODELS:
    print(f"  {m:7s} |{bar(goodc[m], TOTAL_PER)}| {goodc[m]:>3}/90")
print(f"  {'TOTAL':7s} |{bar(total_good, 270)}| {total_good:>3}/270  ({100*total_good/270:.0f}%)")

# moving or stuck?
proc = subprocess.run("ps aux | grep -E '[g]en(_ws)?\\.py' | wc -l", shell=True, capture_output=True, text=True)
running = int(proc.stdout.strip() or 0) > 0
last_t, errs = None, 0
if os.path.exists(LOG):
    lines = open(LOG).read().splitlines()
    errs = sum(1 for l in lines if '"ERROR"' in l)
    if lines:
        last_t = json.loads(lines[-1]).get("t")
print()
if last_t:
    dt = datetime.datetime.now() - datetime.datetime.fromisoformat(last_t)
    secs = int(dt.total_seconds())
    moving = "🟢 MOVING" if secs < 240 else "🟡 quiet (maybe long reasoning call)" if secs < 900 else "🔴 STALLED?"
    print(f"  process: {'running' if running else 'NOT running'} | last activity: {secs}s ago  {moving}")
print(f"  errors (transient, auto-refilled on resume): {errs}")
missing = 270 - total_good
print(f"  remaining to generate: {missing}\n")
