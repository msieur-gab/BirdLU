"""Move drawn letters apart in pitch only, where the decoder finds two of them alike (MUSICOLOGY.md, step 17).

Gab, 16 Nov: "make sure that there is no close friends at all ... if we need more difference between letters, feel
free, because now is the moment." Nothing is redrawn: a letter keeps Gab's pitch line, loudness, notes and timing and
is only moved up or down by whole semitones. A proposal to listen to, written beside the export.

Loop: take the most alike pair (the decoder's own comparison through a 0.6 s and a 1 s echo, lab/likeness.py, the
larger of the two); for each of its two letters try every move from -12 to +12 semitones that keeps the whole pitch
line between 1100 Hz and 5500 Hz (Gab's ceiling); keep the move with the lowest (letter's highest likeness to any
other letter + 0.004 per semitone moved). Stop when no pair is above TARGET or nothing improves.
Run:  .venv/bin/python lab/draw_spread.py <exported file>   → <exported file>-spread.json
"""
import json, os, sys
import numpy as np
from scipy.signal import fftconvolve

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decode import load_voice, features, shape, template, match, ROOT
from likeness import room
from synth import sing, trim
from variants import level

TARGET = float(os.environ.get("TARGET", "0.55"))
LOW, HIGH = 1100.0, 5500.0
AZ = "abcdefghijklmnopqrstuvwxyz"
MOVE = os.environ.get("MOVE")       # e.g. MOVE=".,?!'-:@#" moves only the signs; the letters stay where they are


def main(path):
    path = os.path.expanduser(path)
    doc = json.load(open(path))
    drawn = doc["letters"]
    base = json.load(open(os.path.join(ROOT, "birds", "draw", "models.json")))["letters"]
    AZ = list(base)                      # letters and signs
    movable = set(MOVE) if MOVE else set(AZ)
    M = {c: dict(drawn.get(c, base[c])) for c in AZ}
    sr = 44100
    rooms = [room(sr, 0.6), room(sr, 1.0)]
    pad = np.zeros(int(0.05 * sr))

    def look(m, c):
        y = level(trim(sing(m, seed=m.get("seed", ord(c)))))
        z = np.concatenate([pad, y, np.zeros(int(0.3 * sr))])
        return [shape(features(fftconvolve(z, h)[: len(z)], sr)[0]) for h in rooms], template(y, sr)

    def alike(a, b):
        return float(max(max(match(p, b[1]).max() for p in a[0]), max(match(p, a[1]).max() for p in b[0])))

    def fits(m, k):
        f = m["pitch"] * 2 ** (k / 12)
        lines = [f * 2 ** (m["pitch_drift"] * i + s) for i in range(m["notes"]) for s in (min(m["shape"]), max(m["shape"]))]
        return min(lines) >= LOW and max(lines) <= HIGH

    P = {c: look(M[c], c) for c in AZ}
    L = {tuple(sorted((a, b))): alike(P[a], P[b]) for i, a in enumerate(AZ) for b in AZ[i + 1:]}
    stuck = set()
    worst_of = lambda c: max(v for p, v in L.items() if c in p)
    moved = {}
    print("before:", ", ".join(f"{a}{b} {L[(a, b)]:.2f}" for a, b in sorted(L, key=L.get, reverse=True)[:10]))
    for _ in range(60):
        open_pairs = [p for p in L if p not in stuck and (p[0] in movable or p[1] in movable)]
        if not open_pairs:
            break
        a, b = max(open_pairs, key=L.get)
        if L[(a, b)] <= TARGET:
            break
        best = None
        for c in (x for x in (a, b) if x in movable):
            for k in range(-12, 13):
                if k == 0 or not fits(M[c], k):
                    continue
                m = dict(M[c], pitch=M[c]["pitch"] * 2 ** (k / 12))
                p = look(m, c)
                w = max(alike(p, P[o]) for o in AZ if o != c)
                cost = w + 0.004 * abs(k + moved.get(c, 0))
                if best is None or cost < best[0]:
                    best = (cost, w, c, k, m, p)
        cost, w, c, k, m, p = best
        if w >= L[(a, b)] - 0.005:
            print(f"   {a}/{b} {L[(a, b)]:.2f}: no move in pitch helps; this pair needs another shape")
            stuck.add((a, b))
            continue
        M[c], P[c] = m, p
        moved[c] = moved.get(c, 0) + k
        for o in AZ:
            if o != c:
                L[tuple(sorted((c, o)))] = alike(P[c], P[o])
        print(f"   {a}/{b}: {c} moved {k:+d} st (now around {m['pitch'] * 2 ** np.mean(m['shape']):.0f} Hz), its closest now {worst_of(c):.2f}")
    print("after: ", ", ".join(f"{a}{b} {L[(a, b)]:.2f}" for a, b in sorted(L, key=L.get, reverse=True)[:10]))
    print("moved:", {c: f"{k:+d} st" for c, k in moved.items() if k})
    for c, k in moved.items():
        if k:
            drawn[c] = M[c]
    doc["note"] = doc.get("note", "") + " Moved apart in pitch only by lab/draw_spread.py: " + ", ".join(f"{c} {k:+d} st" for c, k in moved.items() if k) + "."
    out = os.path.splitext(path)[0] + "-spread.json"
    json.dump(doc, open(out, "w"), ensure_ascii=False, indent=1)
    print("written:", out)


if __name__ == "__main__":
    main(sys.argv[1])
