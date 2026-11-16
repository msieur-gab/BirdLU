"""Decode one set of real recordings with a test voice and count errors (swapped, missing, extra).
The message of each recording is the Send preset closest to what was read (lab/real_test_v9.py).
Run:  .venv/bin/python lab/real_test_set.py test/recordings-v10 nightingale-f
"""
import glob, os, sys
import numpy as np, soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decode import load_voice, Decoder, ROOT
from real_test_v9 import sung, ops, PRESETS


def main(folder, voice):
    v, snd, sr = load_voice(os.path.join(ROOT, "birds", "voices", voice))
    dec, letters = Decoder(v, snd, sr), set(v["letters"])
    files = sorted(glob.glob(os.path.join(ROOT, folder, "*.wav")), key=lambda p: p.split("-heard-")[1])
    tot = np.zeros(4, int)
    for f in files:
        x, fs = sf.read(f)
        x = x.mean(axis=1) if x.ndim > 1 else x
        got, info = dec.decode(x, fs)
        want = min((sung(p, letters) for p in PRESETS), key=lambda w: sum(ops(w, got)))
        s, mi, ex = ops(want, got)
        n = len(want.replace(" ", ""))
        tot += [s, mi, ex, n]
        print(f"{os.path.basename(f).split('-heard-')[1][:13]}  echo {info.get('rt60') or 0:.2f} s\n"
              f"   sung  {want}\n   heard {got}\n   swapped {s} missing {mi} extra {ex}")
    s, mi, ex, n = tot
    print(f"\n{folder} with {voice}: {s + mi + ex} of {n} letters wrong ({100 * (s + mi + ex) / n:.1f} %): "
          f"swapped {s}, missing {mi}, extra {ex}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
