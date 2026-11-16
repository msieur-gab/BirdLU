"""Score a real test of any test voice: the laptop sings the Send presets, the phone's Listen page hears them and
saves each as WAV. Each recording is decoded by the Python twin of the phone's decoder (lab/decode.py) with that
voice, and nothing else: no word check, no dictionary. The message is the Send preset closest to what was read;
errors are counted sound by sound (letters, signs, the number call, the accent call: swapped, missing, extra), and the
swaps are listed. Works with punctuation sung or unsung.
Run:  .venv/bin/python lab/real_test_any.py <voice> <folder or WAV files>
      e.g. .venv/bin/python lab/real_test_any.py drawn9 test/recordings-drawn9-20cm
"""
import glob, os, sys
from collections import Counter
import soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import decode
from decode import load_voice, Decoder, ROOT
from real_test_v9 import sung, ops, PRESETS
from confusions import align

# the Send page's presets, and three more with accents (16 Nov)
SENTENCES = PRESETS + ["ça va très bien, à bientôt", "mañana por la mañana", "grüße aus köln, schön"]


def main(name, paths):
    v, snd, sr = load_voice(os.path.join(ROOT, "birds", "voices", name))
    dec, letters = Decoder(v, snd, sr), set(v["letters"])
    files = sorted(f for p in paths for f in (glob.glob(os.path.join(p, "*.wav")) if os.path.isdir(p) else [p]))
    flat = lambda s: s.replace(" ", "")
    # each sentence as sung with punctuation unsung, and as sung with it (the Send page's tick box)
    wants = [w for p in SENTENCES for w in (sung(p, letters), " ".join("".join(c for c in w if c in letters) for w in decode.normalize(p).split()))]
    tot, swaps = [0, 0, 0, 0], Counter()
    for f in files:
        x, fs = sf.read(f)
        x = x.mean(axis=1) if x.ndim > 1 else x
        got, info = dec.decode(x, fs)
        want = min(wants, key=lambda w: sum(ops(flat(w), flat(got))))
        s, mi, ex = ops(flat(want), flat(got))
        n = len(flat(want))
        tot = [tot[0] + s, tot[1] + mi, tot[2] + ex, tot[3] + n]
        swaps.update(f"{a}→{b}" for a, b in align(flat(want), flat(got)))
        print(f"{os.path.basename(f)}  echo {info.get('rt60') or 0:.2f} s\n   sung  {want}\n   heard {got}\n   reads {decode.readable(got)}\n   swapped {s} missing {mi} extra {ex}")
    s, mi, ex, n = tot
    if n:
        print(f"\n{name}, {len(files)} recordings: {s + mi + ex} of {n} sounds wrong ({100 * (s + mi + ex) / n:.1f} %): swapped {s}, missing {mi}, extra {ex}")
        print("   " + ", ".join(f"{k}×{c}" if c > 1 else k for k, c in swaps.most_common(15)))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2:])
