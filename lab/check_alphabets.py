"""Step 2 check: how many letters of each candidate alphabet survive a room?

Builds the same messages as bird-alphabets.html (same file, same timings, same clip preparation),
sends them through the simulated sound path, then matches every syllable to the nearest clean
syllable of that alphabet. Unlike lab/distinct.py, each call now carries the echo of the call
before it. A letter is wrong if any of its syllables is.

Limits: the cut positions are known (ideal cutter), so "sung twice" is never mistaken for two
letters here. That is for the real decoder to prove.

Writes birds/alphabets-check.json (shown on the page).
Run:  .venv/bin/python lab/check_alphabets.py [repeats]
"""
import json, os, sys, unicodedata
import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(__file__))
from channel import transmit, SR
from features import picture, active, similarity

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SENTENCES = ["you are not alone on this train", "l'été arrive, où es-tu ?",
             "the quick brown fox jumps over the lazy dog"]
QUIET = [("hiss", 35)]
CONDITIONS = {
    "room 1.5 m": dict(distance=1.5, rt60=0.5, critical=0.6, noise=QUIET),
    "room 3 m":   dict(distance=3.0, rt60=0.5, critical=0.6, noise=QUIET),
    "hall 3 m":   dict(distance=3.0, rt60=1.6, critical=2.5, noise=QUIET),
    "station 2 m": dict(distance=2.0, rt60=1.2, critical=2.0, noise=[("traffic", 12), ("voices", 18), ("hiss", 35)]),
}


def normalize(text):
    out = ""
    for ch in text.lower():
        if ch in "éè":
            out += ch
            continue
        ch = ch.replace("ß", "ss").replace("æ", "ae").replace("œ", "oe")
        out += "".join(c for c in unicodedata.normalize("NFD", ch) if not unicodedata.combining(c))
    return out


def schedule(text, letters, timing, lens, lead=0.3):
    words = [[c for c in w if c in letters] for w in normalize(text).split()]
    words = [w for w in words if w]
    items, t = [], lead
    for wi, w in enumerate(words):
        for ci, c in enumerate(w):
            sylls = []
            for k, sid in enumerate(letters[c]):
                sylls.append((sid, t))
                t += lens[sid]
                if k < len(letters[c]) - 1:
                    t += timing["double_gap"]
            items.append((c, sylls))
            last_of_word = ci == len(w) - 1
            if not (last_of_word and wi == len(words) - 1):
                t += timing["word_gap"] if last_of_word else timing["letter_gap"]
    return items, t + 0.5


def prepare(x, fade_ms):
    x = x / (np.max(np.abs(x)) or 1) * 0.8
    n = int(round(fade_ms / 1000 * SR))
    e = np.ones(len(x))
    e[:n] = np.arange(n) / n
    e[-n:] = (len(x) - 1 - np.arange(len(x) - n, len(x))) / n
    return x * e


def main(repeats=2):
    data = json.load(open(os.path.join(ROOT, "birds", "alphabets.json")))
    meta = {s["id"]: s for s in json.load(open(os.path.join(ROOT, "birds", "syllables.json")))}
    clips = {}
    for sid, s in meta.items():
        x, sr = sf.read(os.path.join(ROOT, "birds", s["file"]))
        clips[sid] = prepare(x if x.ndim == 1 else x.mean(axis=1), data["fade_ms"])
    lens = {k: len(v) / SR for k, v in clips.items()}

    result = {"note": "Simulated letter errors in %, ideal cutting. Made by lab/check_alphabets.py.",
              "sentences": SENTENCES, "versions": {}}
    for key, v in data["versions"].items():
        if v.get("style"):
            continue  # loose-timed versions (D) are not checked yet
        used = sorted({s for seq in v["letters"].values() for s in seq})
        ref = {s: active(picture(clips[s])) for s in used}
        result["versions"][key] = {}
        for speed, timing in data["timing"].items():
            row = {}
            for cname, cond in CONDITIONS.items():
                wrong = total = 0
                for r in range(repeats):
                    for si, text in enumerate(SENTENCES):
                        items, dur = schedule(text, v["letters"], timing, lens)
                        y = np.zeros(int(dur * SR) + 1)
                        for _, sylls in items:
                            for sid, t in sylls:
                                o = int(round(t * SR))
                                y[o:o + len(clips[sid])] += clips[sid]
                        h = transmit(y, cond, SR, seed=100 * r + si)
                        for c, sylls in items:
                            ok = True
                            for sid, t in sylls:
                                a, b = int((t - 0.005) * SR), int((t + lens[sid] + 0.015) * SR)
                                P = active(picture(h[a:b]))
                                best = max(used, key=lambda s: similarity(P, ref[s]))
                                ok &= best == sid
                            wrong += not ok
                            total += 1
                row[cname] = 100 * wrong / total
            result["versions"][key][speed] = row
            print(f"{key} {speed:6s} " + "  ".join(f"{c} {e:4.1f}%" for c, e in row.items()), flush=True)

    path = os.path.join(ROOT, "birds", "alphabets-check.json")
    json.dump(result, open(path, "w"), indent=1)
    print("wrote", path)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2)
