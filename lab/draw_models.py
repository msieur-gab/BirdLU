"""What the drawing page (draw.html) starts from: version D's letters as synthesizer numbers, and words to hear a
letter in (MUSICOLOGY.md, step 17).

Gab, 16 Nov: "a small interface" where he draws a letter's shape and hears it at once, through the synthesizer the
device will run ("you go straight with the synthesizer, then I know what I'm testing and checking is what I will get").

birds/draw/models.json  for each letter a–z (and each of the nine signs, fitted from its approved sound), the model lab/gestures.py gives to lab/synth.py `sing` for version D
                        (pitch, one note's pitch line and loudness at 48 points, overtones, how many notes, how fast,
                        drift), and the seed it is sung with. js/synth.js sings the same numbers in the browser.
birds/draw/words.json   for each letter, the most used words holding it in each of the five languages (lab/corpus),
                        3 to 8 letters long, the letter at the start, inside and at the end when possible.
Run:  .venv/bin/python lab/draw_models.py   (needs lab/sources and lab/corpus, not in git)
"""
import json, os, re, sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from variants import models, ROOT
from gestures import gesture, GROUP
from sketch import VOWELS, SR
from decode import normalize
from lm_test import BOOKS

OUT = os.path.join(ROOT, "birds", "draw")
PER_LANG = 6


def d_models():
    """Exactly the loop of lab/gestures.py for version "gesture" (D)."""
    M = models()
    V = json.load(open(os.path.join(ROOT, "birds", "variants", "variants.json")))["versions"]["cap"]
    today = {c: s["main"] for c, s in json.load(open(os.path.join(ROOT, "birds", "score.json")))["sounds"].items()}
    out = {}
    for ch, m in M.items():
        m = dict(m)
        f = V[ch]["main"] / today[ch]
        if ch in GROUP:
            m = gesture(m, GROUP[ch])
        m["pitch"] = m["pitch"] * f
        out[ch] = dict(vowel=ch in VOWELS, seed=ord(ch), gesture=GROUP.get(ch, "trill"),
                       notes=int(m["notes"]), period=float(m["period"]), note_dur=float(m["note_dur"]),
                       pitch=round(float(m["pitch"]), 1),
                       shape=[round(float(v), 4) for v in m["shape"]], env=[round(float(v), 3) for v in m["env"]],
                       overtones=[round(float(v), 3) for v in m["overtones"]],
                       pitch_drift=float(m["pitch_drift"]), level_drift=float(m["level_drift"]), accel=float(m["accel"]))
    return out


def sign_models():
    """The nine approved signs (birds/voices/nightingale-d, notes cut from real birds) as synthesizer numbers, so they
    can be heard and redrawn through the synthesizer too. A fit, not the recording: Gab's ear decides again."""
    import soundfile as sf
    from synth import note_model, norm
    vd = os.path.join(ROOT, "birds", "voices", "nightingale-d")
    out = {}
    for ch, d in json.load(open(os.path.join(vd, "voice.json")))["letters"].items():
        if not d.get("sign"):
            continue
        x, _ = sf.read(os.path.join(vd, d["file"]))
        m = note_model(norm(x))
        out[ch] = dict(vowel=False, sign=True, seed=ord(ch), gesture=d.get("source", "sign"),
                       notes=1, period=float(m["period"]), note_dur=float(m["note_dur"]), pitch=float(m["pitch"]),
                       shape=m["shape"], env=m["env"], overtones=m["overtones"], pitch_drift=0.0, level_drift=0.0, accel=0.0)
    return out


def accent_call():
    """The accent call "*" (Gab, 16 Nov: accents "like the numbers"): an accented letter is its plain letter, then
    this call, then a letter that names the accent by its English name: a acute, g grave, c circumflex, d diaeresis
    (tréma), t tilde, z cedilla ("little z"). A starting sound for Gab to redraw: one note rising 6 semitones, 70 ms,
    around 3250 Hz, the place where it is least like the 35 sounds of his version 9 (closest: k 0.58)."""
    import numpy as np
    u = np.linspace(0, 1, 48)
    return dict(vowel=False, sign=True, seed=42, gesture="accent call", notes=1, period=0.07, note_dur=0.07, pitch=3249.0,
                shape=[round(float(v), 4) for v in np.linspace(-0.25, 0.25, 48)],
                env=[round(float(v), 3) for v in np.sin(np.pi * u) ** 0.8], overtones=[0.05, 0.02],
                pitch_drift=0.0, level_drift=0.0, accel=0.0)


def words():
    out = {c: {} for c in "abcdefghijklmnopqrstuvwxyz"}
    for lang, books in BOOKS.items():
        wc = Counter()
        for b in books:
            t = open(os.path.join(ROOT, "lab", "corpus", b + ".txt"), encoding="utf-8", errors="ignore").read()
            t = re.split(r"\*\*\* ?END OF", re.split(r"\*\*\* ?START OF[^\n]*", t, 1)[-1], 1)[0].lower()   # the book, not its licence
            wc.update(w for w in re.findall(r"[^\W\d_]+", t) if 3 <= len(w) <= 8 and not re.fullmatch(r"[ivxlc]+", w))   # no roman numerals
        ranked = [w for w, n in wc.most_common() if n >= 3]
        for c in out:
            has = [w for w in ranked if c in normalize(w)]
            pick = []
            for where in (lambda w: normalize(w)[0] == c, lambda w: c in normalize(w)[1:-1], lambda w: normalize(w)[-1] == c):
                pick += [w for w in has if where(w) and w not in pick][:2]
            pick += [w for w in has if w not in pick][:PER_LANG - len(pick)]
            out[c][lang] = pick[:PER_LANG]
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    M = d_models()
    M.update(sign_models())
    M["*"] = accent_call()
    json.dump(dict(note="Version D's letters as synthesizer numbers (lab/draw_models.py). shape: octaves from pitch; "
                        "env: loudness 0–1; period, note_dur: seconds; pitch_drift: octaves per note; level_drift: dB per note.",
                   sample_rate=SR, letters=M), open(os.path.join(OUT, "models.json"), "w"), ensure_ascii=False)
    W = words()
    json.dump(W, open(os.path.join(OUT, "words.json"), "w"), ensure_ascii=False, indent=0)
    print(len(M), "letters and signs;", {c: (m["notes"], round(m["pitch"])) for c, m in M.items()})
    print("w:", W["w"])


if __name__ == "__main__":
    main()
