"""Add the signs Gab chose by ear (13 Nov: ". 1 · ? 1 · ! 3 · , 2 · ' 1 · - 2 · : 1 · @ 2 · # 2") to the
voice. The letters are left exactly as they are; only the sign files are added and listed in voice.json.
Run:  .venv/bin/python lab/add_signs.py
"""
import json, os, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHOICE = {".": 1, "?": 1, "!": 3, ",": 2, "'": 1, "-": 2, ":": 1, "@": 2, "#": 2}


def main():
    c = json.load(open(os.path.join(ROOT, "birds", "signs", "candidates.json")))
    vp = os.path.join(ROOT, "birds", "voice", "voice.json")
    v = json.load(open(vp))
    for sign, k in CHOICE.items():
        cand = c["candidates"][sign][k - 1]
        fn = "sign-" + c["names"][sign] + ".wav"
        shutil.copy(os.path.join(ROOT, "birds", "signs", cand["file"]), os.path.join(ROOT, "birds", "voice", fn))
        v["letters"][sign] = dict(file=fn, vowel=False, sign=True, dur=cand["dur"], source=cand["source"])
        rid = cand["source"].split()[0]
        meta = {r["id"]: r for r in json.load(open(os.path.join(ROOT, "lab", "sources", "sources.json")))}
        if rid in meta:
            m = meta[rid]
            cr = v["credits"].setdefault(rid, dict(species=m["species"], recordist=m["recordist"], licence=m["licence"],
                                                  url=m["commons"], letters=[]))
            if sign not in cr["letters"]:
                cr["letters"].append(sign)
        print(sign, fn, cand["source"], "credited" if rid in meta else "NOT CREDITED")
    v["digits"] = "jabcdefghi"   # a digit is sung as "#" then this letter (0 → j, 1 → a … 9 → i), as in Braille
    json.dump(v, open(vp, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
