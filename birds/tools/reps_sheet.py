import json, sys, importlib.util
import numpy as np
spec = importlib.util.spec_from_file_location("syl", "tools/syllables.py"); syl = importlib.util.module_from_spec(spec); spec.loader.exec_module(syl)
cands = json.load(open("out/candidates.json"))
for s in cands:
    s["quality"] = round((min(s["snr"], 45) / 45) * 0.4 + (min(s["tonality"], 30) / 30) * 0.2 + s["concentration"] * 0.2 + syl.speaker_score(s) * 0.2, 3)
pool = sorted(cands, key=lambda s: -s["quality"])
reps = []
for s in pool:
    if all(syl.distance(s, r) > 0.6 for r in reps): reps.append(s)
# how many renditions does each type have (a type the bird repeats is a stable, typical syllable)
for r in reps: r["count"] = sum(1 for s in cands if syl.distance(s, r) <= 0.6 and s["source"] == r["source"])
for i, r in enumerate(reps):
    r["id"] = f"T{i+1:02d}"; name, sci, rec = syl.SOURCES[r["source"]]
    r.update(species=name, scientific=sci, recordist=rec, licence=syl.LICENCE, url=f"https://xeno-canto.org/{r['source'][2:]}")
json.dump(reps, open("out/types.json", "w"), indent=1, ensure_ascii=False)
print(len(reps), "types")
for r in reps: print(r["id"], r["species"][:10], r["source"], f"{r['t0']:.2f}", int(r["dur"]*1000), "ms", r["fmean"], "Hz x", r["count"], "q", r["quality"])
