"""Three candidate closing calls, heard at the end of a short brisk phrase.

A  the opening reversed and slowing: chaff… chiff… chaff… chiff, a little softer each time
B  three "chiff" notes, each lower and slower: a falling cadence
C  the chaffinch's final flourish (how a real chaffinch ends every song), rebuilt clean

Writes birds/sketch/closing-{A,B,C}.wav and .png, and closings.json.
Run:  .venv/bin/python lab/closings.py
"""
import json, os, sys
import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(__file__))
from sketch import build, score, FRAMES, BRISK_WORD_GAP, cut, OUT, SR
from synth import synth_pieces, synth_frames, note_model, copy_of, sing, norm

FLOURISH = ("XC538310", 17.40, 17.82)  # Common Chaffinch, end of a song


def level(y):
    loud = np.sort(np.abs(y))[-max(1, len(y) // 5):]
    return y / (np.sqrt(np.mean(loud ** 2)) + 1e-9) * 0.25


def sequence(notes):
    """notes: list of (sound, gap after it in s, gain)."""
    total = sum(len(x) / SR + gap for x, gap, _ in notes)
    y = np.zeros(int(total * SR) + 1)
    t = 0
    for x, gap, g in notes:
        o = int(t * SR)
        y[o:o + len(x)] += x * g
        t += len(x) / SR + gap
    return y


def variants():
    chiff = note_model(norm(cut(FRAMES["chiff"])[0]))
    chaff = note_model(norm(cut(FRAMES["chaff"])[0]))
    lower = lambda m, k: dict(m, pitch=m["pitch"] * k)
    sing1 = lambda m, seed: level(sing(m, seed=seed))
    a = sequence([(sing1(chaff, 1), 0.16, 1.0), (sing1(chiff, 2), 0.22, 0.85),
                  (sing1(chaff, 3), 0.30, 0.7), (sing1(chiff, 4), 0.0, 0.55)])
    b = sequence([(sing1(chiff, 5), 0.17, 1.0), (sing1(lower(chiff, 0.89), 6), 0.25, 0.85),
                  (sing1(lower(chiff, 0.79), 7), 0.0, 0.7)])
    x, src = cut(FLOURISH)
    c = level(copy_of(norm(x)))
    chiffsrc = cut(FRAMES["chiff"])[1]
    return {
        "A": (a, dict(chiffsrc, kind="synth"), "The opening reversed and slowing, a little softer each time"),
        "B": (b, dict(chiffsrc, kind="synth"), "Three chiffs, each lower and slower: a falling cadence"),
        "C": (c, dict(src, kind="synth"), "The chaffinch's final flourish, how a real chaffinch ends its song"),
    }


def main():
    pieces = synth_pieces(brisk=True)
    frames = synth_frames()
    out = {}
    for key, (y_close, src, idea) in variants().items():
        fr = dict(frames, close=(y_close, src))
        y, y_bed, marks, credits = build("this train", seed=7, pieces=pieces, frames=fr, word_gap=BRISK_WORD_GAP)
        # only the end matters here: drop the opening call, keep the words and the closing
        start = next(m["t1"] for m in marks if m.get("frame") == "opening") + 0.1
        cut_at = int(start * SR)
        y, y_bed = y[cut_at:], y_bed[cut_at:]
        marks = [dict(m, t0=round(m["t0"] - start, 3), t1=round(m["t1"] - start, 3)) for m in marks if m.get("frame") != "opening"]
        sf.write(os.path.join(OUT, f"closing-{key}.mp3"), y_bed, SR, format="MP3")
        x0, x1 = score(y, marks, os.path.join(OUT, f"closing-{key}.png"))
        out[key] = dict(idea=idea, wav=f"closing-{key}.mp3", png=f"closing-{key}.png", dur=round(len(y) / SR, 2), plot=[x0, x1])
        print(key, f"{len(y_close) / SR:.2f} s closing  ({idea})")
    json.dump(out, open(os.path.join(OUT, "closings.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
