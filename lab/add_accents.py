"""Accents in the voice, one rule for every letter (Gab, 14 Nov): an accented letter is sung as its plain
letter, then a short accent call. é = e + acute, è = e + grave, ñ = n + tilde, ç = c + cedilla … If the
call is lost, the plain letter is still there.

é and è lose their own trills: Gab, "I don't want to start making different rules. The rules should
apply to every single letter."

The calls come from birds/accents/candidates.json (lab/accents.py). CHOICE is PROVISIONAL (candidate 1
of each) until Gab chooses by ear on accents.html. Run after export_voice.py and add_signs.py.
Run:  .venv/bin/python lab/add_accents.py
"""
import json, os, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VOICE = os.path.join(ROOT, "birds", "voice")
CHOICE = {"´": 1, "`": 1, "^": 1, "¨": 1, "~": 1, "¸": 1}   # PROVISIONAL: Gab chooses by ear
DROP = ["é", "è"]                                          # now e + acute, e + grave


def main():
    c = json.load(open(os.path.join(ROOT, "birds", "accents", "candidates.json")))
    vp = os.path.join(VOICE, "voice.json")
    v = json.load(open(vp))
    meta = {r["id"]: r for r in json.load(open(os.path.join(ROOT, "lab", "sources", "sources.json")))}
    for ch in DROP:
        d = v["letters"].pop(ch, None)
        if d and os.path.exists(os.path.join(VOICE, d["file"])):
            os.remove(os.path.join(VOICE, d["file"]))
        for cr in v["credits"].values():
            if ch in cr["letters"]:
                cr["letters"].remove(ch)
    v["credits"] = {k: cr for k, cr in v["credits"].items() if cr["letters"]}
    for acc, k in CHOICE.items():
        cand = c["candidates"][acc][k - 1]
        fn = "accent-" + c["names"][acc] + ".wav"
        shutil.copy(os.path.join(ROOT, "birds", "accents", cand["file"]), os.path.join(VOICE, fn))
        v["letters"][acc] = dict(file=fn, vowel=False, accent=True, name=c["names"][acc], dur=cand["dur"],
                                 source=cand["source"], candidate=k)
        rid = cand["source"].split()[0]
        if rid in meta:
            m = meta[rid]
            cr = v["credits"].setdefault(rid, dict(species=m["species"], recordist=m["recordist"], licence=m["licence"],
                                                  url=m["commons"], letters=[]))
            if acc not in cr["letters"]:
                cr["letters"].append(acc)
        print(acc, fn, cand["source"], "credited" if rid in meta else "NOT CREDITED")
    # the accent marks as they combine with a letter (Unicode), for the sender and the decoder
    v["accents"] = {"´": "́", "`": "̀", "^": "̂", "¨": "̈", "~": "̃", "¸": "̧"}
    json.dump(v, open(vp, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
