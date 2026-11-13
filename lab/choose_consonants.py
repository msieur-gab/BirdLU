"""Choose the consonants again, judged by a real room.

Every clean single note (the 19 original syllables and single notes found in the 16 Commons
recordings) is synthesized as the voice does it, sent through the room echoes measured from Gab's
recordings (lab/rooms/), and compared with every other note. The 20 notes that stay most distinct
from each other, from the 8 vowel trills and from the frame calls are kept. The most robust ones
go to the most frequent consonants.

Writes lab/out/consonants.json (the choice and its margins) and prints a table.
Run:  .venv/bin/python lab/choose_consonants.py
"""
import json, os, sys, glob
import numpy as np
import soundfile as sf
from scipy.signal import fftconvolve, resample_poly

sys.path.insert(0, os.path.dirname(__file__))
from decode import load_voice, features, shape, template, match, ROOT
from synth import note_model, sing as synth_sing, norm, trim, brisken
from sketch import cut, denoise, noise_profile, fade, CONSONANTS, VOWELS

SR = 44100
FREQ_ORDER = list("tnsrldcmphvgfbqjwkxz")   # most frequent consonants first (English and French mixed)


def level(y):
    loud = np.sort(np.abs(y))[-max(1, len(y) // 5):]
    return y / (np.sqrt(np.mean(loud ** 2)) + 1e-9) * 0.25


def synth_note(x):
    m = brisken(note_model(norm(x)), vowel=False)
    return level(trim(synth_sing(m, seed=11)))


def pool():
    items = []
    meta = {s["id"]: s for s in json.load(open(os.path.join(ROOT, "birds", "syllables.json")))}
    for sid in meta:
        x, src = cut(sid)
        items.append((f"{sid} ({src['species']})", ("syllable", sid), synth_note(x)))
    els = json.load(open(os.path.join(ROOT, "lab", "out", "elements.json")))
    sources = {r["id"]: r for r in json.load(open(os.path.join(ROOT, "lab", "sources", "sources.json")))}
    for rid, d in els.items():
        x_all, _ = sf.read(os.path.join(ROOT, "lab", "sources", "wav", rid + ".wav"))
        prof = noise_profile(x_all)
        for e in d["singles"]:
            dur = e["t1"] - e["t0"]
            if not (0.03 < dur < 0.16 and e["snr"] > 22):
                continue
            a, b = e["t0"] - 0.005, e["t1"] + 0.02
            x = fade(denoise(x_all[int(a * SR):int(b * SR)], prof))
            y = synth_note(x)
            if len(y) < 0.02 * SR:
                continue
            items.append((f"{rid} {a:.2f} ({sources[rid]['species']})", ("cut", rid, round(a, 3), round(b, 3)), y))
    return items


def heard_pictures(y, rooms):
    out = []
    pad = np.zeros(int(0.05 * SR))
    for h in rooms:
        x = resample_poly(np.concatenate([pad, y, np.zeros(int(0.4 * SR))]), 160, 147)
        z = fftconvolve(x, h)[: len(x)]
        z += np.random.default_rng(0).normal(0, np.sqrt(np.mean(z ** 2)) * 10 ** (-30 / 20), len(z))
        out.append(shape(features(z, 48000)[0]))
    return out


def main():
    v, snd, _ = load_voice()
    rooms = [np.load(p) for p in sorted(glob.glob(os.path.join(ROOT, "lab", "rooms", "*.npy")))]
    items = pool()
    fixed = [(f"vowel {c}", ("vowel", c), snd[c]) for c in VOWELS] + [(f"frame {k}", ("frame", k), snd[k]) for k in ("chiff", "chaff")]
    allx = fixed + items
    print(f"{len(items)} candidate notes, {len(fixed)} fixed sounds, {len(rooms)} measured rooms")
    tpl = [template(y, SR) for _, _, y in allx]
    pics = [heard_pictures(y, rooms) for _, _, y in allx]
    n = len(allx)
    M = np.zeros((n, n))   # M[a, b]: how well b's template matches a as heard (mean over rooms)
    for a in range(n):
        for b in range(n):
            M[a, b] = np.mean([match(P, tpl[b]).max() for P in pics[a]])
    margin = lambda a, b: min(M[a, a] - M[a, b], M[b, b] - M[b, a])
    chosen = list(range(len(fixed)))
    cons = []
    cand = list(range(len(fixed), n))
    while len(cons) < 20:
        best = max(cand, key=lambda c: min(margin(c, s) for s in chosen))
        chosen.append(best); cons.append(best); cand.remove(best)
    # current consonants, for comparison
    out = []
    for c in cons:
        worst = min((margin(c, s), allx[s][0]) for s in chosen if s != c)
        out.append(dict(name=allx[c][0], spec=allx[c][1], self=round(float(M[c, c]), 3),
                        worst_margin=round(float(worst[0]), 3), closest=worst[1]))
    out.sort(key=lambda o: -o["self"] - o["worst_margin"])   # sturdiest first
    for letter, o in zip(FREQ_ORDER, out):
        o["letter"] = letter
        print(f"{letter}: {o['name']:42s} heard-self {o['self']:.2f}  worst margin {o['worst_margin']:+.2f} (vs {o['closest']})")
    vm = min(min(margin(a, b) for b in range(len(fixed)) if b != a) for a in range(len(fixed)))
    print(f"vowels and frames among themselves: worst margin {vm:+.2f}")
    json.dump(out, open(os.path.join(ROOT, "lab", "out", "consonants.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
