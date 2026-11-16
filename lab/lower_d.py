"""Version D, lower: the whole voice D moved down 5, 9 or 12 semitones (MUSICOLOGY.md, step 15).

Gab, 16 Nov: "perhaps what we use in terms of hertz is too narrow, because you told me it's only from 1 to 5
kilohertz, but actually we never tried it out. I think the main issue is when the sound is going too high in terms
of kilohertz. It's unbearable for the human ears." D spans 1.4–5.5 kHz, most letters above 2.5 kHz.
Every letter is built exactly as D (lab/gestures.py: same model, gesture, seed), only its pitch times 2^(−n/12).
Signs # and @ unchanged. Only for listening: the decoder hears 1–9 kHz today, so these are not decoded yet.
Writes birds/variants/d-<n>/<letter>.wav and versions "d-5", "d-9", "d-12" in birds/variants/variants.json.
Run:  .venv/bin/python lab/lower_d.py ; then lab/make_test_voice.py
"""
import json, os, sys
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from variants import models, level, OUT, ROOT
from gestures import GROUP, gesture
from synth import sing, trim
from sketch import SR

DOWN = (5, 9, 12)


def main():
    M = models()
    info = json.load(open(os.path.join(OUT, "variants.json")))
    Dv = info["versions"]["gesture"]
    score = {c: s["main"] for c, s in json.load(open(os.path.join(ROOT, "birds", "score.json")))["sounds"].items()}
    for n in DOWN:
        key = f"d-{n}"
        os.makedirs(os.path.join(OUT, key), exist_ok=True)
        info["versions"][key] = {}
        for ch, m in M.items():
            m = dict(m)
            if ch in GROUP:
                m = gesture(m, GROUP[ch])
            m["pitch"] = m["pitch"] * Dv[ch]["main"] / score[ch] * 2 ** (-n / 12)
            y = level(trim(sing(m, seed=ord(ch))))
            sf.write(os.path.join(OUT, key, f"{ch}.wav"), y, SR, subtype="PCM_16")
            info["versions"][key][ch] = dict(file=f"{key}/{ch}.wav", dur=round(len(y) / SR, 4),
                                             main=round(Dv[ch]["main"] * 2 ** (-n / 12)), changed=f"D, {-n} st")
        lo = min(v["main"] for v in info["versions"][key].values()); hi = max(v["main"] for v in info["versions"][key].values())
        print(f"{key}: {lo}–{hi} Hz")
    json.dump(info, open(os.path.join(OUT, "variants.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
