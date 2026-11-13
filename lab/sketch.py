"""A sound sketch: words sung as phrases. Vowels are real trills, consonants are short notes.

Not a decoder-ready alphabet: a test by ear of the shape "word = one phrase, pause between words".
- Vowels: a natural trill cut whole from a recording, so it keeps the bird's own pace.
- Consonants: a short single note leading into (or out of) the trill.
- Inside a word nothing pauses; between words the bird stops, like a real song.

Writes, per sentence, birds/sketch/<n>.wav, <n>.png (the score: sound picture with the letters
under it) and birds/sketch/sketch.json (letter times for the page's playhead, and credits).

Run:  .venv/bin/python lab/sketch.py
"""
import json, os, sys, unicodedata
import numpy as np
import soundfile as sf
from scipy.signal import stft
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))
from elements import elements

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 44100
OUT = os.path.join(ROOT, "birds", "sketch")
SENTENCES = ["you are not alone on this train", "l'été arrive, où es-tu ?", "the quick brown fox jumps over the lazy dog"]

# vowels: (recording, start s, end s), cut at the nearest element edges inside the range
VOWELS = {
    "e": "B05",                # blue tit trill (Gab's favourite: "the trill is fantastic")
    "a": ("XC433160", 9.15, 9.95),             # nuthatch, rising "tui tui tui"
    "o": ("XC433160", 1.95, 2.65),             # nuthatch, fast low "dididi"
    "i": ("XC543697", 15.15, 15.75),           # wren, high trill
    "u": ("XC543697", 16.05, 16.6),            # wren, middle trill
    "é": ("XC543697", 17.85, 18.25),           # wren, short bright trill
    "y": ("XC538310", 15.55, 16.15),           # chaffinch, high section
    "è": ("XC538310", 16.85, 17.4),            # chaffinch, middle section
}
# consonants (13 Nov evening: restored after a few hours of room-chosen notes that sounded like "a small
# R2D2"; the errors they were meant to fix came from the Listen page losing sound): short single notes, existing syllables (blue tit, great tit, robin), and three low
# blackbird notes for b, w and z (13 Nov: the nuthatch notes first used for b and w were the very note
# the "a" trill repeats, and B04 is the B03 look-alike a room confuses; the blackbird sits alone,
# below 2.2 kHz)
CONSONANTS = {
    "t": "B16", "n": "B02", "s": "B15", "r": "B14", "l": ("XC541754", 15.375, 15.46), "d": "B06", "c": "B10", "m": "B07",
    "p": "B03", "h": ("XC461185", 13.29, 13.45), "v": "B12", "g": "R03", "f": "R01", "b": ("XC533763", 1.54, 1.69),
    "w": ("XC446151", 6.555, 6.65), "k": "B09", "j": "B11", "q": "B08", "x": "B13", "z": ("XC533763", 76.66, 76.82),
}
GAP_IN_WORD = 0.025
WORD_GAP = (0.55, 0.85)
BRISK_WORD_GAP = (0.32, 0.45)

# Frame calls: a message opens with a chiffchaff saying its name (high and low notes alternating:
# no letter alternates) and closes with the same call reversed and slowing, a little softer each
# time, like a bird settling (Gab chose it on 13 Nov over a falling cadence and a chaffinch flourish;
# the yellowhammer's long note sounded like "a balloon … emptying his air").
FRAMES = {
    "chiff": ("XC478019", 2.15, 2.33),   # Common Chiffchaff, high note 5.6 kHz
    "chaff": ("XC478019", 2.52, 2.70),   # Common Chiffchaff, low note 4.7 kHz
}
OPEN_PATTERN = ["chiff", "chaff", "chiff", "chaff"]
OPEN_PERIOD = 0.27
CLOSE_PATTERN = [("chaff", 0.16, 1.0), ("chiff", 0.22, 0.85), ("chaff", 0.30, 0.7), ("chiff", 0.0, 0.55)]  # note, pause after, level


def normalize(text):
    out = ""
    for ch in text.lower():
        if ch in "éè":
            out += ch
            continue
        out += "".join(c for c in unicodedata.normalize("NFD", ch) if not unicodedata.combining(c))
    return out


_cache = {}


def recording(rid):
    if rid not in _cache:
        x, sr = sf.read(os.path.join(ROOT, "lab", "sources", "wav", rid + ".wav"))
        assert sr == SR
        _cache[rid] = (x, elements(x, sr))
    return _cache[rid]


def fade(x, ms=5):
    n = int(ms / 1000 * SR)
    x = x.copy()
    x[:n] *= np.linspace(0, 1, n)
    x[-n:] *= np.linspace(1, 0, n)
    return x


def denoise(x, noise_mag, strength=2.0, floor=0.03):
    """Spectral gating: keep what stands above the recording's own background, soften the rest.
    noise_mag is the background level per frequency (same STFT settings)."""
    from scipy.signal import istft
    f, t, Z = stft(x, SR, nperseg=1024, noverlap=768)
    mag = np.abs(Z)
    gain = np.clip(1 - strength * noise_mag[:, None] / (mag + 1e-12), floor, 1.0)
    # smooth the mask a little over time so it does not chirp
    k = np.ones(3) / 3
    gain = np.apply_along_axis(lambda g: np.convolve(g, k, mode="same"), 1, gain)
    gain[f < 1000] = floor  # nothing of ours lives below 1 kHz: drop wind and rumble
    _, y = istft(Z * gain, SR, nperseg=1024, noverlap=768)
    return y[: len(x)]


def noise_profile(x):
    """Background level per frequency: the quiet 20 % of frames."""
    f, t, Z = stft(x, SR, nperseg=1024, noverlap=768)
    return np.percentile(np.abs(Z), 20, axis=1)


def cut(spec):
    """A piece of sound, cleaned of its recording's background, level-matched, with soft edges."""
    if isinstance(spec, str):  # an existing syllable clip: its background is estimated from itself
        meta = {s["id"]: s for s in json.load(open(os.path.join(ROOT, "birds", "syllables.json")))}
        x, _ = sf.read(os.path.join(ROOT, "birds", meta[spec]["file"]))
        x = denoise(x, noise_profile(x), strength=1.5)
        src = dict(kind="syllable", id=spec, species=meta[spec]["species"], recordist=meta[spec]["recordist"],
                   source=meta[spec]["source"], licence=meta[spec]["licence"], url=meta[spec]["url"])
    else:
        rid, t0, t1 = spec
        x_all, els = recording(rid)
        inside = [e for e in els if e["t0"] >= t0 - 0.02 and e["t1"] <= t1 + 0.02]
        a = inside[0]["t0"] - 0.005 if inside else t0
        b = inside[-1]["t1"] + 0.03 if inside else t1
        x = denoise(x_all[int(a * SR): int(b * SR)], noise_profile(x_all))
        m = {r["id"]: r for r in json.load(open(os.path.join(ROOT, "lab", "sources", "sources.json")))}[rid]
        src = dict(kind="cut", id=f"{rid} {a:.2f}–{b:.2f} s", species=m["species"], recordist=m["recordist"],
                   source=rid, licence=m["licence"], url=m["commons"])
    loud = np.sort(np.abs(x))[-max(1, len(x) // 5):]
    x = x / (np.sqrt(np.mean(loud ** 2)) + 1e-9) * 0.25
    return fade(x), src


def syllables_of(word):
    """Written syllables: a vowel group is the core; one consonant between vowels starts the next
    syllable, two or more are split. Only for drawing the score; the sound follows the letters."""
    V = set("aeiouyéè")
    groups, cur = [], ""
    i = 0
    while i < len(word):
        cur += word[i]
        if word[i] in V and (i + 1 == len(word) or word[i + 1] not in V):
            j = i + 1
            while j < len(word) and word[j] not in V:
                j += 1
            cons = word[i + 1:j]
            if j == len(word):
                cur += cons
                i = j
                break
            split = 0 if len(cons) <= 1 else 1
            cur += cons[:split]
            groups.append(cur)
            cur = ""
            i += 1 + split
            continue
        i += 1
    if cur:
        groups.append(cur)
    return groups


def recorded_pieces():
    return {ch: cut(spec) for ch, spec in {**VOWELS, **CONSONANTS}.items()}


def recorded_frames():
    return {k: cut(spec) for k, spec in FRAMES.items()}


def closing_call(frames):
    """The closing: chaff… chiff… chaff… chiff, slowing and softening. Built from the frame notes."""
    total = sum(len(frames[n][0]) / SR + gap for n, gap, _ in CLOSE_PATTERN)
    y, t = np.zeros(int(total * SR) + 1), 0.0
    for n, gap, g in CLOSE_PATTERN:
        x = frames[n][0]
        o = int(t * SR)
        y[o:o + len(x)] += x * g
        t += len(x) / SR + gap
    return y


def add_frame_open(parts, marks, frames, t):
    t0 = t
    for k, name in enumerate(OPEN_PATTERN):
        x, _ = frames[name]
        parts.append((t, x))
        t = t0 + (k + 1) * OPEN_PERIOD if k < len(OPEN_PATTERN) - 1 else t + len(x) / SR
    marks.append(dict(frame="opening", t0=round(t0, 3), t1=round(t, 3)))
    return t


def add_frame_close(parts, marks, frames, t):
    x = frames["close"][0] if "close" in frames else closing_call(frames)
    parts.append((t, x))
    marks.append(dict(frame="closing", t0=round(t, 3), t1=round(t + len(x) / SR, 3)))
    return t + len(x) / SR


def build(text, seed=0, pieces=None, frames=None, word_gap=WORD_GAP):
    """pieces: letter -> (sound, source). Recorded cuts by default; lab/synth.py passes synthesized ones.
    frames: opening/closing sounds; when given, the message is framed."""
    rng = np.random.default_rng(seed)
    pieces = pieces or recorded_pieces()
    words = [[c for c in w if c in pieces] for w in normalize(text).split()]
    words = [w for w in words if w]
    t, parts, marks = 0.4, [], []
    if frames:
        t = add_frame_open(parts, marks, frames, t) + 0.35
    for wi, w in enumerate(words):
        word_start = t
        for c in w:
            x, src = pieces[c]
            g = 10 ** (rng.uniform(-2, 2) / 20)
            parts.append((t, x * g))
            marks.append(dict(letter=c, t0=round(t, 3), t1=round(t + len(x) / SR, 3), vowel=c in VOWELS, word=wi))
            t += len(x) / SR + GAP_IN_WORD * rng.uniform(0.6, 1.4)
        marks.append(dict(word_text="".join(w), syllables=syllables_of("".join(w)), t0=round(word_start, 3), t1=round(t, 3)))
        if wi < len(words) - 1:
            t += rng.uniform(*word_gap)
    if frames:
        t = add_frame_close(parts, marks, frames, t + 0.3)
    y = np.zeros(int((t + 0.6) * SR))
    for t0, x in parts:
        o = int(t0 * SR)
        y[o:o + len(x)] += x
    y = y / (np.max(np.abs(y)) or 1) * 0.89
    bed = ambience(len(y))
    y_bed = y + bed
    y_bed = y_bed / (np.max(np.abs(y_bed)) or 1) * 0.89
    credits = {}
    for ch, (_, src) in pieces.items():
        if any(m.get("letter") == ch for m in marks):
            credits.setdefault(src["source"], dict(species=src["species"], recordist=src["recordist"],
                                                   licence=src["licence"], url=src["url"], letters=[]))["letters"].append(ch)
    for name, (_, src) in (frames or {}).items():
        label = "closing call" if name == "close" else "opening call"
        c = credits.setdefault(src["source"], dict(species=src["species"], recordist=src["recordist"],
                                                   licence=src["licence"], url=src["url"], letters=[]))
        if label not in c["letters"]:
            c["letters"].append(label)
    m = {r["id"]: r for r in json.load(open(os.path.join(ROOT, "lab", "sources", "sources.json")))}[AMBIENCE[0]]
    credits.setdefault(AMBIENCE[0], dict(species=m["species"], recordist=m["recordist"], licence=m["licence"],
                                         url=m["commons"], letters=[]))["letters"].append("forest background")
    return y, y_bed, marks, credits


AMBIENCE = ("XC543697", 19.2, 25.0)  # a quiet stretch of the wren recording: leaves, distance, air


def ambience(n, level_db=-34):
    """One continuous forest background under the whole message, looped with crossfades."""
    rid, a, b = AMBIENCE
    x_all, _ = recording(rid)
    x = x_all[int(a * SR): int(b * SR)]
    x = x - np.mean(x)
    xf = int(0.5 * SR)
    out = np.zeros(n + len(x))
    pos = 0
    while pos < n:
        seg = x.copy()
        seg[:xf] *= np.linspace(0, 1, xf)
        seg[-xf:] *= np.linspace(1, 0, xf)
        out[pos:pos + len(seg)] += seg
        pos += len(seg) - xf
    out = out[:n]
    rms = np.sqrt(np.mean(out ** 2)) + 1e-12
    return out / rms * 10 ** (level_db / 20)


def score(y, marks, path):
    """The score: the sound picture, the letters under it (vowels as trills, coloured), words above."""
    dur = len(y) / SR
    fig, ax = plt.subplots(figsize=(max(8, dur * 1.6), 3.4))
    f, t, Z = stft(y, SR, nperseg=512, noverlap=384)
    S = 20 * np.log10(np.abs(Z) + 1e-9)
    ax.pcolormesh(t, f / 1000, S, vmin=S.max() - 65, vmax=S.max(), cmap="Greys", shading="auto")
    ax.set_ylim(0.3, 10)
    ax.set_xlim(0, dur)
    for m in marks:
        if "letter" in m:
            col = "#a8456a" if m["vowel"] else "#1f6f8b"
            ax.axvspan(m["t0"], m["t1"], ymin=0, ymax=0.06, color=col, alpha=0.9, lw=0)
            ax.text((m["t0"] + m["t1"]) / 2, 0.9, m["letter"], ha="center", va="bottom", fontsize=13,
                    color=col, family="monospace", weight="bold")
        elif "frame" in m:
            ax.axvspan(m["t0"], m["t1"], ymin=0, ymax=0.06, color="#7a6a8f", alpha=0.9, lw=0)
            ax.text(m["t0"], 0.9, m["frame"], ha="left", va="bottom", fontsize=10, color="#7a6a8f", style="italic")
        else:
            ax.text(m["t0"], 9.3, " · ".join(m["syllables"]), ha="left", va="center", fontsize=10, color="#5f6b64")
    ax.set_yticks([2, 4, 6, 8]); ax.set_ylabel("kHz")
    ax.set_xlabel("seconds")
    for s in ax.spines.values():
        s.set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=90)
    box = ax.get_position()  # where time 0 and the end sit, as fractions of the image width
    plt.close(fig)
    return round(box.x0, 4), round(box.x1, 4)


def main():
    os.makedirs(OUT, exist_ok=True)
    index = {"note": "Made by lab/sketch.py. Vowels: real trills; consonants: short notes; a word is one phrase.",
             "sentences": []}
    from synth import synth_pieces, synth_frames  # here, not at the top: synth.py imports this file
    kinds = {
        "": (recorded_pieces(), recorded_frames(), WORD_GAP),
        "-synth": (synth_pieces(), synth_frames(), WORD_GAP),
        "-brisk": (synth_pieces(brisk=True), synth_frames(), BRISK_WORD_GAP),
    }
    for n, text in enumerate(SENTENCES, 1):
        entry = dict(n=n, text=text)
        for suffix, (pieces, frames, gap) in kinds.items():
            y, y_bed, marks, credits = build(text, seed=n, pieces=pieces, frames=frames, word_gap=gap)
            sf.write(os.path.join(OUT, f"{n}{suffix}.mp3"), y, SR, format="MP3")
            sf.write(os.path.join(OUT, f"{n}{suffix}-forest.mp3"), y_bed, SR, format="MP3")
            x0, x1 = score(y, marks, os.path.join(OUT, f"{n}{suffix}.png"))
            entry[suffix.strip("-") or "recorded"] = dict(wav=f"{n}{suffix}.mp3", wav_forest=f"{n}{suffix}-forest.mp3",
                                                         png=f"{n}{suffix}.png", dur=round(len(y) / SR, 2),
                                                         plot=[x0, x1], marks=marks, credits=credits)
            letters = sum(1 for m in marks if "letter" in m)
            print(f"{n}{suffix:7s}: {len(y) / SR:5.1f} s, {letters} letters, {len(y) / SR / letters:.2f} s per letter  ({text})")
        index["sentences"].append(entry)
    json.dump(index, open(os.path.join(OUT, "sketch.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
