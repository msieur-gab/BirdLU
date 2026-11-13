"""Export the bird voice that the phone and the computer share: one WAV per letter, the two frame
notes, and the timing rules. Sender and listener read exactly these files, so what the listener
expects is exactly what the sender sings.

Writes birds/voice/<name>.wav and birds/voice/voice.json.
Run:  .venv/bin/python lab/export_voice.py
"""
import json, os, sys
import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(__file__))
from sketch import (VOWELS, CONSONANTS, GAP_IN_WORD, BRISK_WORD_GAP, OPEN_PATTERN, OPEN_PERIOD,
                    CLOSE_PATTERN, SR)
from synth import synth_pieces, synth_frames

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "birds", "voice")
SAFE = {"é": "e-acute", "è": "e-grave"}


def main():
    os.makedirs(OUT, exist_ok=True)
    pieces = synth_pieces(brisk=True)
    frames = synth_frames()
    letters, credits = {}, {}
    for ch, (y, src) in pieces.items():
        name = SAFE.get(ch, ch)
        sf.write(os.path.join(OUT, name + ".wav"), y, SR, subtype="PCM_16")
        letters[ch] = dict(file=name + ".wav", vowel=ch in VOWELS, dur=round(len(y) / SR, 4))
        credits.setdefault(src["source"], dict(species=src["species"], recordist=src["recordist"],
                                               licence=src["licence"], url=src["url"], letters=[]))["letters"].append(ch)
    notes = {}
    for k, (y, src) in frames.items():
        sf.write(os.path.join(OUT, k + ".wav"), y, SR, subtype="PCM_16")
        notes[k] = dict(file=k + ".wav", dur=round(len(y) / SR, 4))
        credits.setdefault(src["source"], dict(species=src["species"], recordist=src["recordist"],
                                               licence=src["licence"], url=src["url"], letters=[]))["letters"].append(k)
    voice = dict(
        note="Bird voice v3, made by lab/export_voice.py from models of real birds (lab/synth.py).",
        sample_rate=SR,
        letters=letters,
        frames=notes,
        timing=dict(
            lead=0.4,
            gap_in_word=GAP_IN_WORD, gap_jitter=[0.6, 1.4],
            word_gap=list(BRISK_WORD_GAP),
            open_pattern=OPEN_PATTERN, open_period=OPEN_PERIOD, after_open=0.35,
            close_pattern=[dict(note=n, gap=g, level=l) for n, g, l in CLOSE_PATTERN], before_close=0.3,
            level_jitter_db=2,
        ),
        credits=credits,
    )
    json.dump(voice, open(os.path.join(OUT, "voice.json"), "w"), ensure_ascii=False, indent=1)
    print(f"{len(letters)} letters, {len(notes)} frame notes → {OUT}")


if __name__ == "__main__":
    main()
