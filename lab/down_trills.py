"""Version J: version D, with down-sweep trills where they help (MUSICOLOGY.md, step 14).

Gab, 16 Nov, after G, H and I ("R2D2", "a robot under the water"): "the best version we had so far is the
version D ... perhaps like tunes that repeat extremely fast, like this twiddle for specific letters ... going up,
going down, a bell curve or a bow curve". Research: ornithologists class trill notes the same way (up-sweep,
down-sweep, flat, chevron, U). On the page birds/variants/sweeps/ (D and five trills for the letters confused in
the real tests, and w): "I think mostly the down is working", then "the D and the bow are working as well"
and "by ear, I cannot make the difference between the X and the V".

A trill: four short notes (26 ms, every 33 ms) of the letter's own bird note, softer by 1 dB each, each note
sweeping down (down) or down then up (bow), about 3.6 semitones (0.15 octave each side).

Only the 12 letters of the sweeps page may change (r j t h b z p q g x v w); each keeps D's sound or becomes a
down or bow trill, and may move 0, ±2 or ±3 semitones (D's sound, transposed a little). All other letters stay as D.
Rule (Gab's ear and the real tests): in each pair confused by the phone or by ear (r/j, t/h, b/z, p/q, g/q, x/v)
the two letters differ in kind (D, down, bow) or sit at least 3 semitones apart, and look less than 0.6 alike to
the decoder (rare letters weigh little in the cost, so x/v needs this floor).
w always becomes a trill: "the W was something extremely bad" (Gab).
Cost, lowest wins: how alike every pair of letters looks to the decoder through a 1.0 s echo (lab/likeness.py),
weighted by how often the letters are used (as in G), plus 0.02 per letter changed and 0.01 per semitone moved,
so D changes only where it helps. Coordinate search from D and 20 seeded random starts.

Writes birds/variants/down/<letter>.wav, version "down" in birds/variants/variants.json, birds/down-trills.json.
Run:  .venv/bin/python lab/down_trills.py
"""
import json, os, sys, time
import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from variants import models, level, OUT, ROOT
from gestures import GROUP, gesture
from synth import sing, trim
from sketch import SR
from decode import match, load_voice
from likeness import room
from curves import picture

CHANGE = list("rjthbzpqgxvw")
SHIFTS = [0, -2, 2, -3, 3]
A = 0.15
U = np.linspace(0, 1, 48)
STARTS = 20
PAIRS = [("r", "j"), ("t", "h"), ("b", "z"), ("p", "q"), ("g", "q"), ("x", "v")]


SHAPE = {"down": np.linspace(A, -A, 48), "bow": A - 2 * A * np.sin(np.pi * U)}


def trill(m, hz, seed, kind):
    m = dict(m); own = np.array(m["shape"]); own = own - own.mean()
    m.update(notes=4, period=0.033, note_dur=0.026, shape=list(SHAPE[kind] + 0.1 * own),
             env=list(np.sin(np.pi * U) ** 0.6), pitch=hz, pitch_drift=0.0, level_drift=-1.0, accel=0.0)
    return level(trim(sing(m, seed=seed)))


def main():
    t0 = time.time()
    h = room(SR, 1.0)
    M = models()
    score = json.load(open(os.path.join(ROOT, "birds", "score.json")))["sounds"]
    info = json.load(open(os.path.join(OUT, "variants.json")))
    Dv = info["versions"]["gesture"]
    v, snd, _ = load_voice(os.path.join(ROOT, "birds", "voices", "nightingale-d"))
    letters = [c for c in v["letters"] if c.isalpha()] + ["#", "@"]

    def build(c, kind, s):
        if (kind, s) == ("D", 0):
            return snd[c]
        hz = Dv[c]["main"] * 2 ** (s / 12)
        if kind in SHAPE:
            return trill(M[c], hz, ord(c), kind)
        m = gesture(dict(M[c]), GROUP[c]); m["pitch"] = m["pitch"] * hz / score[c]["main"]
        return level(trim(sing(m, seed=ord(c))))

    # w: "something extremely bad" in D (Gab) -> always a trill
    opts = {c: [("D", 0)] + ([(k, s) for k in ("D", "down", "bow") for s in SHIFTS if (k, s) != ("D", 0)] if c in CHANGE else [])
            for c in letters}
    pic = {(c, o): picture(build(c, *o), h) for c in letters for o in opts[c]}
    opts["w"] = [o for o in opts["w"] if o[0] != "D"]
    print(f"{len(pic)} sounds in {time.time() - t0:.0f} s", flush=True)
    LK = {}

    def like(a, oa, b, ob):
        k = (a, oa, b, ob)
        if k not in LK:
            (P1, T1), (P2, T2) = pic[(a, oa)], pic[(b, ob)]
            LK[k] = LK[(b, ob, a, oa)] = max(match(P1, T2).max(), match(P2, T1).max())
        return LK[k]

    B = json.load(open(os.path.join(ROOT, "birds", "bigrams.json")))
    fr = lambda x: B["letters"].get(x, 0.002)
    pen = lambda L: 100 * max(0.0, L - 0.5) ** 2
    note = {c: 12 * np.log2(Dv[c]["main"] / 440) for c in CHANGE}

    def cost(sel):
        tot = 0.0
        for i, a in enumerate(letters):
            for b in letters[i + 1:]:
                if a in CHANGE or b in CHANGE:
                    tot += (fr(a) + fr(b)) * pen(like(a, sel[a], b, sel[b]))
        for a, b in PAIRS:
            if sel[a][0] == sel[b][0] and abs(note[a] + sel[a][1] - note[b] - sel[b][1]) < 3:
                tot += 10
            if like(a, sel[a], b, sel[b]) > 0.6:
                tot += 10
        return tot + sum(0.02 * (sel[c] != ("D", 0)) + 0.01 * abs(sel[c][1]) for c in CHANGE)

    rng = np.random.default_rng(14)
    D0 = {c: ("D", 0) for c in letters}
    start0 = {**D0, "w": ("down", 0)}
    best = None
    for st in range(STARTS + 1):
        sel = dict(start0) if st == 0 else {**D0, **{c: opts[c][rng.integers(len(opts[c]))] for c in CHANGE}}
        cur = cost(sel)
        improved = True
        while improved:
            improved = False
            for c in rng.permutation(CHANGE):
                for o in opts[c]:
                    s2 = {**sel, c: o}; c2 = cost(s2)
                    if c2 < cur - 1e-9:
                        sel, cur, improved = s2, c2, True
        if best is None or cur < best[0]:
            best = (cur, dict(sel))
    cur, sel = best
    print(f"cost: D {cost(D0):.3f} -> J {cur:.3f}  ({time.time() - t0:.0f} s)")

    os.makedirs(os.path.join(OUT, "down"), exist_ok=True)
    info["versions"]["down"] = {}
    for ch in M:
        if ch in CHANGE and sel[ch] != ("D", 0):
            k, s = sel[ch]
            y = build(ch, k, s)
            changed = (f"{k} trill" if k in SHAPE else GROUP[ch]) + (f", {s:+d} st" if s else "")
            main_hz = round(Dv[ch]["main"] * 2 ** (s / 12))
        else:
            y = sf.read(os.path.join(OUT, Dv[ch]["file"]))[0]
            changed, main_hz = "as D", Dv[ch]["main"]
        sf.write(os.path.join(OUT, "down", f"{ch}.wav"), y, SR, subtype="PCM_16")
        info["versions"]["down"][ch] = dict(file=f"down/{ch}.wav", dur=round(len(y) / SR, 4), main=main_hz, changed=changed)
    json.dump(info, open(os.path.join(OUT, "variants.json"), "w"), ensure_ascii=False, indent=1)
    json.dump(dict(cost_D=round(cost(D0), 3), cost=round(cur, 3), letters={c: dict(kind=sel[c][0], shift_st=sel[c][1]) for c in CHANGE}),
              open(os.path.join(ROOT, "birds", "down-trills.json"), "w"), indent=1)
    for c in CHANGE:
        print(f"  {c}: {sel[c][0]:4s} {sel[c][1]:+d} st")
    for a, b in PAIRS:
        print(f"  {a}/{b}: {sel[a][0]}/{sel[b][0]}, {abs(note[a] + sel[a][1] - note[b] - sel[b][1]):.1f} st apart, likeness {like(a, sel[a], b, sel[b]):.2f}")
    worst = sorted(((like(a, sel[a], b, sel[b]), a + b) for i, a in enumerate(letters) for b in letters[i + 1:]), reverse=True)[:10]
    print("  most alike now:", ", ".join(f"{p} {l:.2f}" for l, p in worst))


if __name__ == "__main__":
    main()
