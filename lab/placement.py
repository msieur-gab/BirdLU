"""A proposed placement of the letters on the score: the most used letter pairs pushed apart in pitch
(MUSICOLOGY.md, step 3). Measures and proposes only; the voice is not changed.

The sounds stay the approved ones: only WHICH letter sings WHICH sound changes. Vowels stay trills
(the six vowel sounds are shared among the six vowels), consonants stay single notes. The "w" sound is
out of the pool (Gab, 16 Nov: "the sound of the W is unbearable"); w gets no sound, only the pitch where a
new w would best sit, chosen by the same rule on a semitone grid over the voice's range.

Rule: a pair of letters (both orders, xy + yx, five languages averaged) costs its share of all pairs
times how much closer than half an octave (6 semitones) its two letters sing:
    cost = sum over pairs of  share × max(0, 6 − distance) / 6
Search: swap two letters' sounds whenever it lowers the cost, until no swap helps; 300 random starts,
the best kept (seeded, so the result is repeatable).

Writes birds/placement.json. Run:  .venv/bin/python lab/placement.py   (after lab/score.py, lab/bigrams.py)
"""
import json, os
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = 6.0          # semitones: half an octave; a pair at least this far apart costs nothing
STARTS = 300
VOWELS = list("aeiouy")
CONS = [c for c in "bcdfghjklmnpqrstvwxz"]
FREE = "w"       # no sound kept: gets a pitch slot only


def main():
    S = json.load(open(os.path.join(ROOT, "birds", "score.json")))["sounds"]
    B = json.load(open(os.path.join(ROOT, "birds", "bigrams.json")))
    langs = B["languages"]
    letters = VOWELS + CONS
    idx = {c: i for i, c in enumerate(letters)}
    n = len(letters)
    # symmetric pair weights (% of pairs), all five languages averaged and per language
    W = np.zeros((n, n)); WL = {l: np.zeros((n, n)) for l in langs}
    for p in B["pairs"]:
        a, b = p["pair"]
        if a == b or a not in idx or b not in idx:
            continue
        i, j = idx[a], idx[b]
        W[i, j] += p["mean"]; W[j, i] += p["mean"]
        for l in langs:
            WL[l][i, j] += p["by_lang"][l]; WL[l][j, i] += p["by_lang"][l]
    semi = lambda hz: 12 * np.log2(hz / 440) + 69
    # the sounds to share out: each vowel trill, each consonant note except w's
    vowel_sounds = VOWELS[:]
    cons_sounds = [c for c in CONS if c != FREE]
    lo = min(semi(S[c]["main"]) for c in letters); hi = max(semi(S[c]["main"]) for c in letters)
    grid = list(np.arange(np.floor(lo), np.ceil(hi) + 1))          # where a new w may sit
    today = np.array([semi(S[c]["main"]) for c in letters])

    def cost_of(pitch, Wm=W):
        d = np.abs(pitch[:, None] - pitch[None, :])
        return float((Wm * np.maximum(0, D - d) / D).sum() / 2)

    def stats(pitch, Wm):
        d = np.abs(pitch[:, None] - pitch[None, :])
        tot = Wm.sum() / 2
        under = lambda x: float((Wm * (d < x)).sum() / 2)
        return dict(under2=round(under(2), 2), under4=round(under(4), 2),
                    mean_apart=round(float((Wm * d).sum() / 2 / tot), 2))

    rng = np.random.default_rng(16)
    best = None
    for s in range(STARTS):
        v = list(rng.permutation(vowel_sounds))
        # consonant letters other than w take the 19 consonant sounds; w takes a grid pitch
        cl = [c for c in CONS if c != FREE]
        cs = list(rng.permutation(cons_sounds))
        assign = dict(zip(VOWELS, v)); assign.update(zip(cl, cs))
        wp = float(rng.choice(grid))

        def pitches(assign, wp):
            return np.array([wp if c == FREE else semi(S[assign[c]]["main"]) for c in letters])
        cur = cost_of(pitches(assign, wp))
        improved = True
        while improved:
            improved = False
            for group in (VOWELS, cl):
                for a in range(len(group)):
                    for b in range(a + 1, len(group)):
                        x, y = group[a], group[b]
                        assign[x], assign[y] = assign[y], assign[x]
                        c2 = cost_of(pitches(assign, wp))
                        if c2 < cur - 1e-9:
                            cur, improved = c2, True
                        else:
                            assign[x], assign[y] = assign[y], assign[x]
            for g in grid:
                c2 = cost_of(pitches(assign, g))
                if c2 < cur - 1e-9:
                    cur, wp, improved = c2, g, True
        if best is None or cur < best[0]:
            best = (cur, dict(assign), wp)
    cost, assign, wp = best
    prop = np.array([wp if c == FREE else semi(S[assign[c]]["main"]) for c in letters])
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    nm = lambda m: f"{names[int(round(m)) % 12]}{int(round(m)) // 12 - 1}"
    out = dict(rule=f"cost = sum of share x max(0, {D:g} - semitones apart) / {D:g}; see MUSICOLOGY.md",
               cost_today=round(cost_of(today), 3), cost_proposed=round(cost, 3),
               w_pitch=dict(note=nm(wp), hz=round(440 * 2 ** ((wp - 69) / 12))),
               sound_of={c: (None if c == FREE else assign[c]) for c in letters},
               today=dict(all=stats(today, W), **{l: stats(today, WL[l]) for l in langs}),
               proposed=dict(all=stats(prop, W), **{l: stats(prop, WL[l]) for l in langs}))
    json.dump(out, open(os.path.join(ROOT, "birds", "placement.json"), "w"), ensure_ascii=False, indent=1)
    print(f"cost today {out['cost_today']}  proposed {out['cost_proposed']}")
    print("letter -> sings the sound of (note)")
    for c in letters:
        src = assign.get(c)
        print(f"  {c} -> {src or '(new sound)'}  {S[src]['main_note'] if src else out['w_pitch']['note']}"
              f"   (today {S[c]['main_note']})")
    print("\n% of all pairs sung <2 st / <4 st apart, and mean distance (st):")
    for k in ["all"] + langs:
        t, p = out["today"][k], out["proposed"][k]
        print(f"  {k:8} today {t['under2']:5.1f} / {t['under4']:5.1f} / {t['mean_apart']:4.1f}"
              f"   proposed {p['under2']:5.1f} / {p['under4']:5.1f} / {p['mean_apart']:4.1f}")


if __name__ == "__main__":
    main()
