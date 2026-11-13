"""Voice variants for a listening test: away from "R2D2", toward a melodic bird.

Same vowels (the trills Gab likes), same opening and closing; only the consonant notes change.
  today            the consonants chosen by the room today (the reference: "a small R2D2")
  earlier          the consonants from before (commit 7e8df7b), which Gab found more natural
  melodic          today's notes with gentler pitch sweeps, their pitch moved onto a pentatonic scale
                   tuned to the opening's chiff, so the phrase sounds like a melody
  melodic-alive    melodic, plus a less perfect line: more pitch wobble and a little overtone
  earlier-melodic  the earlier notes, made melodic and alive the same way

R2D2's sound is pure tones sweeping fast over wide ranges, at pitches with no relation to each
other. A bird's song keeps its notes in a scale-like set of pitches, glides less, and its line is
never perfectly clean.

Writes birds/voices/<name>/ (letters, frame notes, voice.json), read by the Send and Listen pages
with ?voice=<name>, and prints the clean decode check of each.
Run:  .venv/bin/python lab/voices.py
"""
import copy, json, os, sys
import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sketch import VOWELS, CONSONANTS, FRAMES, cut, SR
from synth import model_of, note_model, brisken, sing, trim, norm, synth_frames

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "birds", "voices")
SAFE = {"é": "e-acute", "è": "e-grave"}

EARLIER = {
    "t": "B16", "n": "B02", "s": "B15", "r": "B14", "l": ("XC541754", 15.375, 15.46), "d": "B06", "c": "B10", "m": "B07",
    "p": "B03", "h": ("XC461185", 13.29, 13.45), "v": "B12", "g": "R03", "f": "R01", "b": ("XC533763", 1.54, 1.69),
    "w": ("XC446151", 6.555, 6.65), "k": "B09", "j": "B11", "q": "B08", "x": "B13", "z": ("XC533763", 76.66, 76.82),
}
PENTATONIC = [0, 2, 4, 7, 9]      # degrees of a major pentatonic scale, in semitones


def on_scale(pitch, ref):
    """The nearest pitch of the pentatonic scale built on ref (the opening's chiff)."""
    st = 12 * np.log2(pitch / ref)
    octave = np.floor(st / 12)
    cands = [12 * (octave + o) + d for o in (-1, 0, 1) for d in PENTATONIC]
    best = min(cands, key=lambda c: abs(c - st))
    return ref * 2 ** (best / 12)


def melodic(m, ref, sweep=0.5, limit=0.35):
    """Gentler sweeps (a fraction of the bird's, at most ±limit octave) and the note on the scale."""
    m = dict(m)
    s = np.array(m["shape"]) * sweep
    m["shape"] = list(np.clip(s - np.mean(s), -limit, limit))
    m["pitch"] = round(on_scale(m["pitch"], ref))
    return m


def alive(m, overtone=0.12):
    m = dict(m)
    ov = list(m["overtones"])
    if ov:
        ov[0] = max(ov[0], overtone)
    m["overtones"] = ov
    return m


VARIANTS = {
    "today": dict(cons=CONSONANTS, melodic=False, alive=False),
    "earlier": dict(cons=EARLIER, melodic=False, alive=False),
    "melodic": dict(cons=CONSONANTS, melodic=True, alive=False),
    "melodic-alive": dict(cons=CONSONANTS, melodic=True, alive=True),
    "earlier-melodic": dict(cons=EARLIER, melodic=True, alive=True),
}


def level(y):
    loud = np.sort(np.abs(y))[-max(1, len(y) // 5):]
    return y / (np.sqrt(np.mean(loud ** 2)) + 1e-9) * 0.25


def build(name, spec, ref):
    pieces = {}
    for ch, s in {**VOWELS, **spec["cons"]}.items():
        x, src = cut(s)
        vowel = ch in VOWELS
        m = brisken(model_of(norm(x)) if vowel else note_model(norm(x)), vowel)
        if not vowel and spec["melodic"]:
            m = melodic(m, ref)
        if not vowel and spec["alive"]:
            m = alive(m)
        y = level(trim(sing(m, seed=ord(ch), wobble=0.010 if (spec["alive"] and not vowel) else 0.004)))
        pieces[ch] = (y, src)
    return pieces


def export(name, pieces, frames, base_voice):
    out = os.path.join(OUT, name)
    os.makedirs(out, exist_ok=True)
    v = copy.deepcopy(base_voice)
    v["note"] = f"Voice variant '{name}' (lab/voices.py)."
    v["letters"] = {}
    for ch, (y, _) in pieces.items():
        fn = SAFE.get(ch, ch) + ".wav"
        sf.write(os.path.join(out, fn), y, SR, subtype="PCM_16")
        v["letters"][ch] = dict(file=fn, vowel=ch in VOWELS, dur=round(len(y) / SR, 4))
    for k, (y, _) in frames.items():
        sf.write(os.path.join(out, k + ".wav"), y, SR, subtype="PCM_16")
    json.dump(v, open(os.path.join(out, "voice.json"), "w"), ensure_ascii=False, indent=1)
    return out


def main():
    from decode import load_voice, Decoder, sing as dsing, SENTENCES, edit_distance
    base = json.load(open(os.path.join(ROOT, "birds", "voice", "voice.json")))
    frames = synth_frames()
    ref = note_model(norm(cut(FRAMES["chiff"])[0]))["pitch"]
    for name, spec in VARIANTS.items():
        out = export(name, build(name, spec, ref), frames, base)
        v, snd, sr = load_voice(out)
        dec = Decoder(v, snd, sr)
        errs = n = 0
        for si, text in enumerate(SENTENCES):
            y, sung = dsing(text, v, snd, seed=si)
            got, _ = dec.decode(np.concatenate([y]), sr)
            errs += edit_distance(got, sung); n += len(sung)
        cons = sorted(round(len(snd[c]) / sr * 1000) for c in spec["cons"])
        print(f"{name:16s} clean decode check: {errs} of {n} letters wrong")
    index = [dict(name=k, about=VARIANTS_ABOUT[k]) for k in VARIANTS]
    json.dump(index, open(os.path.join(OUT, "index.json"), "w"), ensure_ascii=False, indent=1)


VARIANTS_ABOUT = {
    "today": "Today's consonants, chosen by the room (the reference: a small R2D2).",
    "earlier": "The consonants from before today's change.",
    "melodic": "Today's notes, gentler sweeps, pitches on a scale tuned to the opening.",
    "melodic-alive": "Melodic, with a less perfect line: more wobble, a little overtone.",
    "earlier-melodic": "The earlier notes, made melodic and alive.",
}

if __name__ == "__main__":
    main()
