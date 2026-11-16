"""Version F: the bird gestures of version D, with the consonants placed again (MUSICOLOGY.md, step 10).

Real test v9 showed the errors were swaps of pairs left 0–2 semitones apart (r/j, t/h, b/z, p/q, g/q, x/v).
Gab, 16 Nov: "yes, redo the placement with the 3 semitones rule".

What changes: only the pitch of each consonant. Its gesture and timbre stay those of version D
(lab/gestures.py). Vowels do not move ("the vowels are just perfect"). Signs and frames do not move.

Rules, on a grid of semitones from F6 to F8 (1397–5588 Hz, the lower range Gab chose):
  1. consonants with the same gesture (chip, buzz, hum; l, w, r are each alone) sit at least 3 semitones
     apart (Gab's rule);
  2. no two consonants on the same semitone (added: the test's r/j and t/h swaps were across gestures, at
     0.1 and 1.3 semitones).
Cost, lowest wins (as in step 3, lab/placement.py):
  sum over letter pairs of  share × max(0, 6 − semitones apart) / 6     (pairs both ways, 5 languages)
  + 0.03 per semitone a consonant moves from its place in D (so letters move only when it helps).
Search: move one consonant to another allowed semitone, or swap two, whenever it lowers the cost, from
400 random starts (seeded); the best is kept.

Writes birds/variants/placed/<letter>.wav, adds version "placed" to birds/variants/variants.json, and
birds/placement-d.json. Run:  .venv/bin/python lab/placement_d.py   (after lab/gestures.py)
"""
import json, os, sys
import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from variants import models, level, OUT, ROOT
from gestures import GROUP, gesture
from synth import sing, trim
from sketch import SR

D = 6.0
MOVE = 0.03
GAP_SAME = 3
LO, HI = 89, 113            # MIDI notes: F6 .. F8
STARTS = 400
VOWELS = list("aeiouy")


def midi(hz):
    return 69 + 12 * np.log2(hz / 440)


def main():
    info = json.load(open(os.path.join(OUT, "variants.json")))
    Dv = info["versions"]["gesture"]
    B = json.load(open(os.path.join(ROOT, "birds", "bigrams.json")))
    cons = sorted(GROUP)
    letters = VOWELS + cons
    idx = {c: i for i, c in enumerate(letters)}
    W = np.zeros((len(letters),) * 2)
    for p in B["pairs"]:
        a, b = p["pair"]
        if a != b and a in idx and b in idx:
            W[idx[a], idx[b]] += p["mean"]; W[idx[b], idx[a]] += p["mean"]
    here = {c: midi(Dv[c]["main"]) for c in letters}          # where each letter sings in version D
    vow = np.array([here[c] for c in VOWELS])
    grid = list(range(LO, HI + 1))
    group = {c: GROUP[c] if GROUP[c] in ("chip", "buzz", "hum") else c for c in cons}

    def cost(pos):
        p = np.concatenate([vow, [pos[c] for c in cons]])
        d = np.abs(p[:, None] - p[None, :])
        return float((W * np.maximum(0, D - d) / D).sum() / 2) + MOVE * sum(abs(pos[c] - here[c]) for c in cons)

    def ok(pos, c, n):
        for o in cons:
            if o == c or o not in pos:      # not placed yet (random start)
                continue
            if pos[o] == n or (group[o] == group[c] and abs(pos[o] - n) < GAP_SAME):
                return False
        return True

    rng = np.random.default_rng(10)
    best = None
    for s in range(STARTS):
        pos = {}
        for c in rng.permutation(cons):          # a random allowed start
            free = [n for n in grid if ok(pos, c, n)]
            if not free:
                break
            pos[c] = int(rng.choice(free))
        if len(pos) < len(cons):
            continue
        cur = cost(pos)
        improved = True
        while improved:
            improved = False
            for c in cons:
                for n in grid:
                    if n == pos[c] or not ok(pos, c, n):
                        continue
                    old = pos[c]; pos[c] = n
                    c2 = cost(pos)
                    if c2 < cur - 1e-9:
                        cur, improved = c2, True
                    else:
                        pos[c] = old
            for i, a in enumerate(cons):
                for b in cons[i + 1:]:
                    pos[a], pos[b] = pos[b], pos[a]
                    if ok(pos, a, pos[a]) and ok(pos, b, pos[b]):
                        c2 = cost(pos)
                        if c2 < cur - 1e-9:
                            cur, improved = c2, True
                            continue
                    pos[a], pos[b] = pos[b], pos[a]
        if best is None or cur < best[0]:
            best = (cur, dict(pos))
    cur, pos = best

    def stats(p_of):
        p = np.array([p_of[c] for c in letters])
        d = np.abs(p[:, None] - p[None, :]); tot = W.sum() / 2
        return dict(under2=round(float((W * (d < 2)).sum() / 2), 2), under4=round(float((W * (d < 4)).sum() / 2), 2),
                    mean_apart=round(float((W * d).sum() / 2 / tot), 2))
    placed = {**{c: here[c] for c in VOWELS}, **pos}
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    nm = lambda m: f"{names[int(round(m)) % 12]}{int(round(m)) // 12 - 1}"
    print(f"cost {cur:.2f}; pairs: D {stats(here)}  ->  placed {stats(placed)}")
    # the swapped pairs of test v9, before and after
    for a, b in [("r", "j"), ("t", "h"), ("b", "z"), ("p", "q"), ("g", "q"), ("x", "v")]:
        print(f"  {a}/{b}: {abs(here[a] - here[b]):.1f} st -> {abs(placed[a] - placed[b]):.0f} st")

    # build the voice
    M = models()
    os.makedirs(os.path.join(OUT, "placed"), exist_ok=True)
    info["versions"]["placed"] = {}
    for ch, m in M.items():
        m = dict(m)
        f_b = Dv[ch]["main"] / json.load(open(os.path.join(ROOT, "birds", "score.json")))["sounds"][ch]["main"]
        changed = []
        if ch in GROUP:
            m = gesture(m, GROUP[ch])
            f = f_b * 2 ** ((pos[ch] - here[ch]) / 12)
            changed = [GROUP[ch], nm(pos[ch]) + (f" ({pos[ch] - here[ch]:+.1f} st)" if abs(pos[ch] - here[ch]) > 0.05 else "")]
        else:
            f = f_b
            changed = ["as D"]
        m["pitch"] = m["pitch"] * f
        y = level(trim(sing(m, seed=ord(ch))))
        sf.write(os.path.join(OUT, "placed", f"{ch}.wav"), y, SR, subtype="PCM_16")
        info["versions"]["placed"][ch] = dict(file=f"placed/{ch}.wav", dur=round(len(y) / SR, 4),
                                              main=round(440 * 2 ** ((placed[ch] - 69) / 12)), changed=", ".join(changed))
        if ch in GROUP:
            print(f"  {ch} {GROUP[ch]:10s} {nm(here[ch])} -> {nm(pos[ch])}")
    json.dump(info, open(os.path.join(OUT, "variants.json"), "w"), ensure_ascii=False, indent=1)
    json.dump(dict(rules=dict(same_gesture_min_st=GAP_SAME, distinct_semitones=True, grid=["F6", "F8"], move_cost=MOVE),
                   cost=round(cur, 3), D=stats(here), placed=stats(placed),
                   consonants={c: dict(group=GROUP[c], from_note=nm(here[c]), to_note=nm(pos[c]), moved_st=round(pos[c] - here[c], 1))
                               for c in cons}),
              open(os.path.join(ROOT, "birds", "placement-d.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
