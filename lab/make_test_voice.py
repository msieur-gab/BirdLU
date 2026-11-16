"""Test voices for the real test, laptop sings, phone listens (Gab, 16 Nov: "the nightingale version with D
bird gesture is the most enjoyable and appealing version ... let us try now these different messages
decoded from the phone while played from the laptop").

Each is the approved voice (birds/voice/voice.json: signs, timing, credits) with
  - the letters a–z of version D (lab/gestures.py: version B's lower range + bird gestures), and
  - the nightingale opening (phrase 2.16) and closing (phrase 1.4) through the synthesizer
    (lab/frames_ng.py), as single frame notes.
  nightingale-d        frames in the "notes" version
  nightingale-d-lower  frames in the "notes, lower" version
Writes birds/voices/<name>/ (voice.json and WAVs) and lists them in birds/voices/index.json.
Used as send-bird.html?voice=<name> and listen-bird.html?voice=<name>.
Run:  .venv/bin/python lab/make_test_voice.py   (after lab/gestures.py and lab/frames_ng.py)
"""
import copy, json, os, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VOICE = os.path.join(ROOT, "birds", "voice")
VOICES = os.path.join(ROOT, "birds", "voices")
VERSIONS = {"nightingale-d": ("gesture", "notes"), "nightingale-d-lower": ("gesture", "notes-lower"),
            "nightingale-f": ("placed", "notes"),
            "nightingale-g": ("curves", "notes")}   # 16 Nov: letters G, note + curve (lab/curves.py)   # 16 Nov: letters F (lab/placement_d.py), after real test v9


def main():
    base = json.load(open(os.path.join(VOICE, "voice.json")))
    VI = json.load(open(os.path.join(ROOT, "birds", "variants", "variants.json")))["versions"]
    F = json.load(open(os.path.join(ROOT, "birds", "frames-ng", "frames.json")))
    index = json.load(open(os.path.join(VOICES, "index.json")))
    for name, (lv, fv) in VERSIONS.items():
        D = VI[lv]
        out = os.path.join(VOICES, name)
        os.makedirs(out, exist_ok=True)
        v = copy.deepcopy(base)
        v["note"] = (f"Test voice {name} (16 Nov): letters of version {dict(gesture='D', placed='F', curves='G')[lv]} (lower range + bird gestures"
                     f"{dict(gesture='', placed=', placed again: same gesture 3 semitones apart', curves=', each consonant a note and a curve')[lv]}), "
                     f"{'signs as approved' if lv == 'gesture' else 'no punctuation (# and @ kept)'}, "
                     f"nightingale opening 2.16 and closing 1.4 ({fv}). Made by lab/make_test_voice.py.")
        if lv in ("placed", "curves"):
            # punctuation is not sung for now (Gab, 16 Nov), so this voice has none: the listener cannot read a
            # letter as a sign it never hears (the clean check read "little" as "li-tle", t now sits on "-"'s note)
            for c in ".?!,'-:":
                v["letters"].pop(c, None)
        for ch, d in v["letters"].items():
            src = os.path.join(ROOT, "birds", "variants", D[ch]["file"]) if ch in D else os.path.join(VOICE, d["file"])
            fn = d["file"]
            shutil.copy(src, os.path.join(out, fn))
            if ch in D:
                d["dur"] = D[ch]["dur"]; d["gesture"] = D[ch]["changed"]
        v["frames"] = {}
        for k, which in (("ngopen", "opening"), ("ngclose", "closing")):
            fn = F[which]["versions"][fv]["file"]
            shutil.copy(os.path.join(ROOT, "birds", "frames-ng", fn), os.path.join(out, k + ".wav"))
            v["frames"][k] = dict(file=k + ".wav", dur=F[which]["versions"][fv]["dur"],
                                  source=f"Common Nightingale {F[which]['source']} (XC138451/XC473316, CC BY-SA 4.0)")
        v["timing"]["open_pattern"] = ["ngopen"]
        v["timing"]["open_period"] = 0
        v["timing"]["close_pattern"] = [dict(note="ngclose", gap=0, level=1.0)]
        for rid, who in (("XC473316", "Marie-Lan Taÿ Pamart"), ("XC138451", "Sander Pieterse")):
            v["credits"][rid] = dict(species="Common Nightingale", recordist=who, licence="CC BY-SA 4.0",
                                     url=f"https://xeno-canto.org/{rid[2:]}", letters=["opening" if rid == "XC473316" else "closing"])
        json.dump(v, open(os.path.join(out, "voice.json"), "w"), ensure_ascii=False, indent=1)
        index = [e for e in index if e["name"] != name] + [dict(
            name=name, about=f"Letters {dict(gesture='D', placed='F', curves='G')[lv]} (lower range + bird gestures"
                             f"{dict(gesture='', placed=', placed again', curves=', note + curve')[lv]}), nightingale opening and closing ({fv}).")]
        print(name, len(v["letters"]), "letters and signs,", list(v["frames"]))
    json.dump(index, open(os.path.join(VOICES, "index.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
