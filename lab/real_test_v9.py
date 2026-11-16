"""Real test v9 (16 Nov): the test voice nightingale-d (letters D, nightingale opening and closing, punctuation
unsung) sung by the laptop, heard by the phone's Listen page, saved as WAV. Two setups (Gab): the laptop's own
speakers 20 cm from the phone, and a Bluetooth speaker about 2.5 m away.

Each recording is decoded by the Python twin of the phone's decoder (lab/decode.py) with the test voice
(checked: the approved voice's decoder reads nonsense from them, so the test voice was the one sung). The message is the Send preset closest to
what was read. Errors are counted letter by letter: swapped, missing, extra.
Run:  .venv/bin/python lab/real_test_v9.py
"""
import glob, os, sys
import numpy as np, soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decode import load_voice, Decoder, normalize, ROOT

PRESETS = ["you are not alone on this train", "l'été arrive, où es-tu ?", "meet me at the old bridge at noon",
           "ich bin gleich wieder da", "Rendez-vous à 18h30, quai n°2 !", "arrive belle Wasser carro little",
           "the quick brown fox jumps over the lazy dog"]
PUNCT = set(".?!,'-:")


def sung(text, letters):
    """What the Send page sings with punctuation unsung (js/birdsong.js sing, punctuation: false)."""
    plain = "".join(" " if c in PUNCT else c for c in normalize(text))
    return " ".join("".join(c for c in w if c in letters) for w in plain.split() if any(c in letters for c in w))


def ops(a, b):
    """Levenshtein alignment of b (heard) against a (sung): (swapped, missing, extra)."""
    n, m = len(a), len(b)
    D = np.zeros((n + 1, m + 1), int); D[:, 0] = range(n + 1); D[0, :] = range(m + 1)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i, j] = min(D[i - 1, j] + 1, D[i, j - 1] + 1, D[i - 1, j - 1] + (a[i - 1] != b[j - 1]))
    i, j, s, mi, ex = n, m, 0, 0, 0
    while i or j:
        if i and j and D[i, j] == D[i - 1, j - 1] + (a[i - 1] != b[j - 1]):
            s += a[i - 1] != b[j - 1]; i -= 1; j -= 1
        elif i and D[i, j] == D[i - 1, j] + 1:
            mi += 1; i -= 1
        else:
            ex += 1; j -= 1
    return s, mi, ex


def main():
    decs = {}
    for name in ("nightingale-d",):
        v, snd, sr = load_voice(os.path.join(ROOT, "birds", "voices", name))
        decs[name] = (Decoder(v, snd, sr), v)
    files = sorted(glob.glob(os.path.join(ROOT, "test", "recordings-v9", "*.wav")), key=lambda p: p.split("-heard-")[1])
    tot = {"2.5 m Bluetooth": np.zeros(4, int), "20 cm laptop": np.zeros(4, int)}
    for k, f in enumerate(files):
        setup = "2.5 m Bluetooth" if k < 7 else "20 cm laptop"   # Gab played the 7 presets once per setup, Bluetooth first
        x, fs = sf.read(f)
        x = x.mean(axis=1) if x.ndim > 1 else x
        best = "nightingale-d"     # both test voices share the letters; their frames differ only in pitch
        got, info = decs[best][0].decode(x, fs)
        letters = set(decs[best][1]["letters"])
        want = min((sung(p, letters) for p in PRESETS), key=lambda w: ops(w, got) and sum(ops(w, got)))
        s, mi, ex = ops(want, got)
        n = len(want.replace(" ", ""))
        tot[setup] += [s, mi, ex, n]
        print(f"{os.path.basename(f).split('-heard-')[1][:13]}  {best:20s} echo {info.get('rt60') or 0:.2f} s  "
              "\n"
              f"   sung  {want}\n   heard {got}\n   swapped {s} missing {mi} extra {ex}")
    for setup, (s, mi, ex, n) in tot.items():
        print(f"{setup}: {s + mi + ex} of {n} letters wrong ({100 * (s + mi + ex) / n:.1f} %): swapped {s}, missing {mi}, extra {ex}")


if __name__ == "__main__":
    main()
