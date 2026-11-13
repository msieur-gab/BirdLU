"""Decode Gab's real recordings with decoder variants (the only judge besides his ear).
test/recordings-v3: old voice (commit 7e8df7b), Bluetooth speaker, living room, 2 m.
test/recordings-v4: current voice, laptop speakers, phone listening, 30 cm and 2.5 m.
All are the Send page's "meet me at the old bridge at noon".
Run:  .venv/bin/python lab/real_test.py OLD_VOICE_DIR
"""
import glob, os, sys
import numpy as np, soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decode import load_voice, Decoder, edit_distance, ROOT

TEXT = "meet me at the old bridge at noon"
VARIANTS = {
    "as today": dict(),
    "echo out, delay 30 ms": dict(dereverb=True, rises_from="raw", echo_delay=0.03),
    "delay 30 + weight .1-.5": dict(dereverb=True, rises_from="raw", echo_delay=0.03, echo_weight=(0.1, 0.5)),
    "delay 30, echo 0.5 s fixed": dict(dereverb=True, rises_from="raw", echo_delay=0.03, rt60=0.5),
    "delay 20 ms": dict(dereverb=True, rises_from="raw", echo_delay=0.02),
}


def main(old_dir):
    sets = [(sorted(glob.glob(os.path.join(ROOT, "test", "recordings-v3", "*.wav"))), Decoder(*load_voice(old_dir))),
            (sorted(glob.glob(os.path.join(ROOT, "test", "recordings-v4", "*.wav"))), Decoder(*load_voice()))]
    tot = {k: 0 for k in VARIANTS}
    for files, dec in sets:
        for f in files:
            x, fs = sf.read(f)
            x = x.mean(axis=1) if x.ndim > 1 else x
            print(os.path.basename(f))
            for name, kw in VARIANTS.items():
                got, info = dec.decode(x, fs, **kw)
                e = edit_distance(got, TEXT)
                tot[name] += e
                print(f"   {name:30s} {e:2d}  {got!r}   (echo {info.get('rt60') or 0:.2f} s)")
    print("\nletters wrong over all recordings:")
    for name, e in tot.items():
        print(f"   {name:30s} {e}")


if __name__ == "__main__":
    main(sys.argv[1])
