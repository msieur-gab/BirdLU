"""Which letters a voice confuses: every Send preset, sung and decoded, clean and through simulated rooms.
A guide before the real test (simulated rooms are not evidence; real recordings decide).
Run:  .venv/bin/python lab/confusions.py partition3 partition3-double nightingale-d
"""
import os, sys
from collections import Counter
import numpy as np
from scipy.signal import fftconvolve
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decode import load_voice, Decoder, sing_js, ROOT
from likeness import room, likeness
from real_test_v9 import sung, PRESETS


def align(a, b):
    """Swaps (sung letter -> heard letter), missing and extra, by edit distance."""
    n, m = len(a), len(b)
    D = np.zeros((n + 1, m + 1), int); D[:, 0] = range(n + 1); D[0, :] = range(m + 1)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i, j] = min(D[i - 1, j] + 1, D[i, j - 1] + 1, D[i - 1, j - 1] + (a[i - 1] != b[j - 1]))
    i, j, out = n, m, []
    while i or j:
        if i and j and D[i, j] == D[i - 1, j - 1] + (a[i - 1] != b[j - 1]):
            if a[i - 1] != b[j - 1]: out.append((a[i - 1], b[j - 1]))
            i -= 1; j -= 1
        elif i and D[i, j] == D[i - 1, j] + 1:
            out.append((a[i - 1], "∅")); i -= 1
        else:
            out.append(("∅", b[j - 1])); j -= 1
    return out


def main(names):
    for name in names:
        v, snd, sr = load_voice(os.path.join(ROOT, "birds", "voices", name))
        dec, letters = Decoder(v, snd, sr), set(v["letters"])
        L = likeness(snd, sr, [c for c in v["letters"] if c.isalpha()], room(sr, 1.0))
        top = sorted(L, key=L.get, reverse=True)[:6]
        print(f"\n{name}  (band {v.get('decoder', {}).get('f_lo', 1000)}–{v.get('decoder', {}).get('f_hi', 9000)} Hz)")
        print("   most alike to the decoder:", ", ".join(f"{a}{b} {L[(a, b)]:.2f}" for a, b in top))
        for label, rt in (("clean", None), ("echo 0.6 s", 0.6), ("echo 1.0 s", 1.0)):
            errs, n = Counter(), 0
            for k, p in enumerate(PRESETS):
                y = sing_js(p, v, snd)
                if rt:
                    y = fftconvolve(y, room(sr, rt, seed=5 + k))[: len(y) + sr]
                    y = y + np.random.default_rng(k).normal(0, 0.003, len(y))
                got, _ = dec.decode(y, sr)
                keep = lambda s: "".join(ch for ch in s if ch.isalnum() or ch in "#@")
                want = keep(sung(p, letters)); got = keep(got)
                n += len(want)
                errs.update(f"{a}→{b}" for a, b in align(want, got))
            tot = sum(errs.values())
            print(f"   {label:10s} {tot:3d} of {n} letters wrong ({100 * tot / n:.1f} %)" + (": " + ", ".join(f"{k}×{c}" if c > 1 else k for k, c in errs.most_common(10)) if tot else ""))


if __name__ == "__main__":
    main(sys.argv[1:])
