#!/usr/bin/env python3
"""Generate index.html from data/wvs-synthetic.csv (standard library only).

Usage: python3 build.py     (deterministic: fixed seed, same output every run)
"""
import csv, json, random, os
from collections import Counter

SEED = 42
HERE = os.path.dirname(os.path.abspath(__file__))
rows = list(csv.DictReader(open(os.path.join(HERE, "data/wvs-synthetic.csv"), encoding="utf-8-sig")))
cols = list(rows[0].keys())
N_RAW = len(rows)

# ---- schema: type + non-empty count (on raw data) ----
def is_num(v):
    try: float(v); return True
    except ValueError: return False
schema = []
for c in cols:
    vals = [r[c].strip() for r in rows if r[c] is not None and r[c].strip() != ""]
    if c == "respondent_id": typ = "Identifier (integer)"
    elif all(is_num(v) for v in vals):
        typ = "Integer" if all(float(v) == int(float(v)) for v in vals) and c not in ("emancipative_values", "secular_values") else "Numeric (decimal)"
        if c in ("emancipative_values", "secular_values"): typ = "Numeric index (0–1)"
    else:
        typ = "Categorical (%d levels)" % len(set(vals))
    schema.append({"name": c, "type": typ, "n": len(vals), "missing": N_RAW - len(vals)})

# ---- duplicates ----
full_dups = N_RAW - len({tuple(r.values()) for r in rows})
id_counts = Counter(r["respondent_id"] for r in rows)
id_dups = sum(v - 1 for v in id_counts.values() if v > 1)

# ---- missing: drop any row with a blank cell ----
clean = [r for r in rows if all(r[c].strip() != "" for c in cols)]
rows_removed = N_RAW - len(clean)
rows_with_missing_by_col = {c: sum(1 for r in rows if r[c].strip() == "") for c in cols}

COUNTRIES = ["China", "Singapore", "Turkey", "India", "Kazakhstan"]
f = lambda r, k: float(r[k])
by = {c: [r for r in clean if r["country"] == c] for c in COUNTRIES}
mean = lambda xs: sum(xs) / len(xs)

summary = {}
for c in COUNTRIES:
    g = by[c]
    summary[c] = {
        "n": len(g),
        "secular": mean([f(r, "secular_values") for r in g]),
        "emancipative": mean([f(r, "emancipative_values") for r in g]),
        "radar": [
            mean([f(r, "life_satisfaction") for r in g]) / 10,
            sum(r["trust_people"] == "Trusted" for r in g) / len(g),
            mean([f(r, "importance_of_god") for r in g]) / 10,
            mean([f(r, "emancipative_values") for r in g]),
            mean([f(r, "secular_values") for r in g]),
            mean([f(r, "financial_satisfaction") for r in g]) / 10,
        ],
    }
rows_per_country_raw = Counter(r["country"] for r in rows)

rng = random.Random(SEED)
sample = {}
for c in ("China", "India"):
    s = rng.sample(by[c], 300)
    sample[c] = [[round(f(r, "secular_values"), 4), round(f(r, "emancipative_values"), 4)] for r in s]

grid = [[0] * 10 for _ in range(10)]
for r in by["Singapore"]:
    grid[int(f(r, "life_satisfaction")) - 1][int(f(r, "financial_satisfaction")) - 1] += 1
sg_corr = None
xs = [f(r, "life_satisfaction") for r in by["Singapore"]]; ys = [f(r, "financial_satisfaction") for r in by["Singapore"]]
mx, my = mean(xs), mean(ys)
sg_corr = sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / (sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys)) ** 0.5

# overlap of China/India clouds: share of India points within China's 5th–95th pct on both axes
def pct(v, p): v = sorted(v); return v[int(p * (len(v) - 1))]
cn, ind = by["China"], by["India"]
def inside(a, b):
    ok = 0
    for r in b:
        if all(pct([f(x, k) for x in a], .05) <= f(r, k) <= pct([f(x, k) for x in a], .95) for k in ("secular_values", "emancipative_values")): ok += 1
    return ok / len(b)
_cache = {k: sorted(f(x, k) for x in cn) for k in ("secular_values", "emancipative_values")}
def inside_cn(r):
    return all(_cache[k][int(.05 * (len(cn) - 1))] <= f(r, k) <= _cache[k][int(.95 * (len(cn) - 1))] for k in _cache)
overlap = sum(inside_cn(r) for r in ind) / len(ind)

data = {
    "countries": COUNTRIES, "summary": summary, "sample": sample, "grid": grid,
    "axes": ["Life satisfaction", "Trust in others", "Importance of God", "Emancipative values", "Secular values", "Financial satisfaction"],
    "sg_corr": sg_corr, "overlap": overlap,
}
meta = {
    "n_raw": N_RAW, "n_clean": len(clean), "removed": rows_removed, "full_dups": full_dups, "id_dups": id_dups,
    "schema": [s for s in schema if s["name"] != "respondent_id"],
    "raw_country": rows_per_country_raw,
}

TEMPLATE = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
html = TEMPLATE.replace("/*DATA*/null", json.dumps(data, separators=(",", ":"))).replace("/*META*/null", json.dumps(meta, separators=(",", ":")))
open(os.path.join(HERE, "index.html"), "w", encoding="utf-8").write(html)
print("rows raw/clean:", N_RAW, len(clean), "| dups:", full_dups, id_dups, "| overlap:", round(overlap, 2), "| sg r:", round(sg_corr, 2))
