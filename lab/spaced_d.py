"""Version I: the sound of version D, on the spaced notes of version H (MUSICOLOGY.md, step 13).

Gab, 16 Nov: G and H "sound like R2D2 ... the best version was the version D". The drawn curves (rise, arc,
valley, warble on a pure note) are what made them robotic. The far test (v11 far) showed what has to change:
in a long echo, letters 0–1 semitone apart swap.

So each consonant is exactly D's (lab/gestures.py: its own bird's pitch line, overtones and gesture), only moved
to another note, as in version F (lab/placement_d.py), on H's grid:
  - the 13 most used consonants (n s t r l d c h m p g b v) each on a note of their own, whole tones from E6 to
    E8 (1319–5274 Hz), so at least 2 semitones apart;
  - the 7 rarest (f w q z k j x) share one of those notes with a more used letter.
Which letter goes where: the same cost as G and H (lab/curves.py): how alike letters look to the decoder through
a 1.0 s echo (lab/likeness.py), weighted by how often they are used, plus a little of the step-3 rule (most used
neighbours apart), plus 0.03 per semitone a letter moves from its place in D (as in F), so the melody of D
changes only where the spacing needs it. 40 seeded random starts; the best is kept.

Writes birds/variants/dspaced/<letter>.wav, version "dspaced" in birds/variants/variants.json, birds/spaced-d.json.
Run:  .venv/bin/python lab/spaced_d.py   (after lab/gestures.py)
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
from curves import picture, note_name
from curves_h import SLOTS, RARE

RT60 = 1.0
MOVE = 0.03
STARTS = 40


def main():
    t0 = time.time()
    h = room(SR, RT60)
    M = models()
    score = json.load(open(os.path.join(ROOT, "birds", "score.json")))["sounds"]
    cons = sorted(GROUP)
    used = [c for c in cons if c not in RARE]

    def build(c, n):
        m = gesture(dict(M[c]), GROUP[c])
        m["pitch"] = m["pitch"] * 440 * 2 ** ((n - 69) / 12) / score[c]["main"]
        return level(trim(sing(m, seed=ord(c))))

    vd, snd_d, _ = load_voice(os.path.join(ROOT, "birds", "voices", "nightingale-d"))
    fixed = list("aeiouy") + ["#", "@"]
    cand, pics, tpls = [], [], []
    for c in cons:
        for n in SLOTS:
            P, T = picture(build(c, n), h)
            cand.append((c, n)); pics.append(P); tpls.append(T)
    fpics, ftpls = zip(*[picture(snd_d[f], h) for f in fixed])
    N = len(cand)
    at = {cn: i for i, cn in enumerate(cand)}
    like = lambda P1, T1, P2, T2: max(match(P1, T2).max(), match(P2, T1).max())
    LF = np.array([[like(pics[i], tpls[i], fpics[j], ftpls[j]) for j in range(len(fixed))] for i in range(N)])
    LC = np.zeros((N, N))
    for i in range(N):
        for j in range(i + 1, N):
            if cand[i][0] != cand[j][0]:
                LC[i, j] = LC[j, i] = like(pics[i], tpls[i], pics[j], tpls[j])
    print(f"{N} candidates and likeness table in {time.time() - t0:.0f} s", flush=True)

    B = json.load(open(os.path.join(ROOT, "birds", "bigrams.json")))
    fr = lambda x: B["letters"].get(x, 0.002)
    share = {}
    for p in B["pairs"]:
        a, b = p["pair"]
        if a != b:
            share[(a, b)] = share.get((a, b), 0) + p["mean"]; share[(b, a)] = share.get((b, a), 0) + p["mean"]
    info = json.load(open(os.path.join(OUT, "variants.json")))
    Dv = info["versions"]["gesture"]
    vow_note = {c: 69 + 12 * np.log2(Dv[c]["main"] / 440) for c in "aeiouy"}
    here = {c: 69 + 12 * np.log2(Dv[c]["main"] / 440) for c in Dv}
    pen = lambda L: 100 * max(0.0, L - 0.5) ** 2

    def cost(pos):
        total = 0.0
        for a_i, a in enumerate(cons):
            i = at[(a, pos[a])]
            total += sum((fr(a) + fr(f)) * pen(LF[i, j]) for j, f in enumerate(fixed))
            for b in cons[a_i + 1:]:
                j = at[(b, pos[b])]
                total += (fr(a) + fr(b)) * pen(LC[i, j])
                total += 0.1 * share.get((a, b), 0) * max(0, 6 - abs(pos[a] - pos[b])) / 6
            for v in "aeiouy":
                total += 0.1 * share.get((a, v), 0) * max(0, 6 - abs(pos[a] - vow_note[v])) / 6
        return total + MOVE * sum(abs(pos[c] - here[c]) for c in cons)

    def moved(pos, c, n):
        p = dict(pos)
        if c in used:
            for b in used:
                if b != c and p[b] == n:
                    p[b] = pos[c]
        p[c] = n
        return p

    rng = np.random.default_rng(13)
    best = None
    for st in range(STARTS):
        pos = dict(zip(used, (int(n) for n in rng.permutation(SLOTS))))
        pos.update({c: int(rng.choice(SLOTS)) for c in RARE})
        cur = cost(pos)
        improved = True
        while improved:
            improved = False
            for c in rng.permutation(cons):
                for n in SLOTS:
                    p2 = moved(pos, c, n)
                    c2 = cost(p2)
                    if c2 < cur - 1e-9:
                        cur, pos, improved = c2, p2, True
        if best is None or cur < best[0]:
            best = (cur, dict(pos))
    cur, pos = best
    assert sorted(pos[c] for c in used) == SLOTS
    print(f"best cost {cur:.3f}", flush=True)

    os.makedirs(os.path.join(OUT, "dspaced"), exist_ok=True)
    info["versions"]["dspaced"] = {}
    for ch in M:
        if ch in GROUP:
            y = build(ch, pos[ch])
            changed = f"{GROUP[ch]}, {note_name(pos[ch])} ({pos[ch] - here[ch]:+.1f} st from D)"
            main_hz = round(440 * 2 ** ((pos[ch] - 69) / 12))
        else:
            y = sf.read(os.path.join(OUT, Dv[ch]["file"]))[0]
            changed, main_hz = "as D", Dv[ch]["main"]
        sf.write(os.path.join(OUT, "dspaced", f"{ch}.wav"), y, SR, subtype="PCM_16")
        info["versions"]["dspaced"][ch] = dict(file=f"dspaced/{ch}.wav", dur=round(len(y) / SR, 4), main=main_hz, changed=changed)
    json.dump(info, open(os.path.join(OUT, "variants.json"), "w"), ensure_ascii=False, indent=1)
    out = {c: dict(group=GROUP[c], note=note_name(pos[c]), from_D=note_name(round(here[c])), rare=c in RARE) for c in cons}
    json.dump(dict(cost=round(cur, 3), rt60=RT60, slots=[note_name(n) for n in SLOTS], consonants=out),
              open(os.path.join(ROOT, "birds", "spaced-d.json"), "w"), ensure_ascii=False, indent=1)
    for c in sorted(cons, key=lambda c: (pos[c], c in RARE)):
        print(f"  {c}  {out[c]['note']:4s} (D: {out[c]['from_D']:4s}) {GROUP[c]}{'  rare' if c in RARE else ''}")
    print(f"done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
