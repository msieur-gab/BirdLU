"""The partition as sound: version D's letters on the three-octave partition (MUSICOLOGY.md, step 15).

Gab, 16 Nov: "I need to test the sound and checking for confusion patterns. for 3 octaves." Each letter is built
exactly as in D (lab/gestures.py: its own bird model and gesture, same synthesizer, same seed), only placed on its
note of birds/partition.json (lab/partition.py: every letter its own place, C5–C8, 1.44 semitones apart, most used
pairs and confused letters far apart).
  p3     the partition
  p3x2   the partition, each consonant sung twice (12 ms apart, the second 1 dB softer): Gab, "we can try
         doubling the letter or giving them variation like the trill we added to the vowels"
Writes birds/variants/<version>/<letter>.wav and the versions in birds/variants/variants.json.
Run:  .venv/bin/python lab/partition_voice.py  (after lab/partition.py), then lab/make_test_voice.py
"""
import json, os, sys
import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from variants import models, level, OUT, ROOT
from gestures import GROUP, gesture
from synth import sing, trim
from sketch import SR

DECODER = dict(f_lo=450, f_hi=8000, bands=64, nfft=4096)   # the band a C5–C8 voice is heard in


def main():
    M = models()
    P = json.load(open(os.path.join(ROOT, "birds", "partition.json")))["hz"]
    score = {c: s["main"] for c, s in json.load(open(os.path.join(ROOT, "birds", "score.json")))["sounds"].items()}
    info = json.load(open(os.path.join(OUT, "variants.json")))
    Dv = info["versions"]["gesture"]
    for key in ("p3", "p3x2"):
        os.makedirs(os.path.join(OUT, key), exist_ok=True)
        info["versions"][key] = {}
        for ch, m in M.items():
            if ch in P:
                m = dict(m)
                if ch in GROUP:
                    m = gesture(m, GROUP[ch])
                m["pitch"] = m["pitch"] * P[ch] / score[ch]
                y = trim(sing(m, seed=ord(ch)))
                if key == "p3x2" and ch in GROUP:
                    y = np.concatenate([y, np.zeros(int(0.012 * SR)), y * 10 ** (-1 / 20)])
                y = level(y)
                changed, hz = f"partition {P[ch]} Hz" + (", twice" if key == "p3x2" and ch in GROUP else ""), P[ch]
            else:
                y = sf.read(os.path.join(OUT, Dv[ch]["file"]))[0]
                changed, hz = "as D", Dv[ch]["main"]
            sf.write(os.path.join(OUT, key, f"{ch}.wav"), y, SR, subtype="PCM_16")
            info["versions"][key][ch] = dict(file=f"{key}/{ch}.wav", dur=round(len(y) / SR, 4), main=hz, changed=changed)
    info["decoder_p3"] = DECODER
    json.dump(info, open(os.path.join(OUT, "variants.json"), "w"), ensure_ascii=False, indent=1)
    print("built p3, p3x2")


if __name__ == "__main__":
    main()
