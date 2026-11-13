"""Decoder prototype for the bird voice (v3), and its test in simulated rooms.

Written to be ported line by line to JavaScript (js/birdsong.js), so it stays simple:

features   a sound picture with 48 bands from 1 to 9 kHz, one column every 5 ms, in dB.
           Each column is compared by its shape (cosine of the dB values minus their mean), so loudness
           and distance do not matter; the column's level is kept apart to find silences.
frames     the opening call (chiff chaff chiff chaff) and the closing call are found by sliding
           their sound picture along the recording.
letters    between them, the decoder searches the best sequence of letters, short in-word gaps and
           word pauses that explains the sound picture (dynamic programming). Each letter is placed
           whole, so echo blurring the tiny gaps inside a word does not matter.

Run:  .venv/bin/python lab/decode.py [repeats]      (prints letter errors per room)
"""
import json, os, sys, unicodedata
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

sys.path.insert(0, os.path.dirname(__file__))
from channel import transmit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VOICE_DIR = os.path.join(ROOT, "birds", "voice")
HOP_S, WIN_S = 0.005, 0.0116
NB, F_LO, F_HI = 48, 1000, 9000


# ---------- the voice and the sender ----------

def load_voice():
    v = json.load(open(os.path.join(VOICE_DIR, "voice.json")))
    sr = v["sample_rate"]
    snd = {}
    for ch, d in v["letters"].items():
        snd[ch] = sf.read(os.path.join(VOICE_DIR, d["file"]))[0]
    for k, d in v["frames"].items():
        snd[k] = sf.read(os.path.join(VOICE_DIR, d["file"]))[0]
    return v, snd, sr


def normalize(text):
    out = ""
    for ch in text.lower():
        if ch in "éè":
            out += ch
            continue
        out += "".join(c for c in unicodedata.normalize("NFD", ch) if not unicodedata.combining(c))
    return out


def opening(v, snd):
    T = v["timing"]
    parts, t = [], 0.0
    for k, name in enumerate(T["open_pattern"]):
        parts.append((t, snd[name], 1.0))
        t = (k + 1) * T["open_period"] if k < len(T["open_pattern"]) - 1 else t + len(snd[name]) / v["sample_rate"]
    return parts, t


def closing(v, snd):
    parts, t = [], 0.0
    for c in v["timing"]["close_pattern"]:
        parts.append((t, snd[c["note"]], c["level"]))
        t += len(snd[c["note"]]) / v["sample_rate"] + c["gap"]
    return parts, t


def mix(parts, n):
    y = np.zeros(n)
    for t, x, g in parts:
        o = int(round(t))
        y[o:o + len(x)] += x[: max(0, n - o)] * g
    return y


def sing(text, v, snd, seed=0):
    """The message as the sender sings it. Returns the sound and the text actually sung."""
    rng = np.random.default_rng(seed)
    T, sr = v["timing"], v["sample_rate"]
    words = [[c for c in w if c in v["letters"]] for w in normalize(text).split()]
    words = [w for w in words if w]
    parts, t = [], T["lead"]
    op, dur = opening(v, snd)
    parts += [(t + a, x, g) for a, x, g in op]
    t += dur + T["after_open"]
    truth = []
    for wi, w in enumerate(words):
        for ci, c in enumerate(w):
            truth.append((c, t))
            parts.append((t, snd[c], 10 ** (rng.uniform(-1, 1) * T["level_jitter_db"] / 20)))
            t += len(snd[c]) / sr
            if ci < len(w) - 1:
                t += T["gap_in_word"] * rng.uniform(*T["gap_jitter"])
        if wi < len(words) - 1:
            t += rng.uniform(*T["word_gap"])
    t += T["before_close"]
    cl, dur = closing(v, snd)
    parts += [(t + a, x, g) for a, x, g in cl]
    t += dur + 0.5
    y = mix([(a * sr, x, g) for a, x, g in parts], int(t * sr))
    sing.truth = truth  # letter start times, for diagnosis
    return y / (np.max(np.abs(y)) or 1) * 0.9, " ".join("".join(w) for w in words)


# ---------- features ----------

def features(x, sr):
    """Band levels in dB (NB × frames) and the frame level in dB."""
    hop, win = int(round(sr * HOP_S)), int(round(sr * WIN_S))
    nfft = 1 << (win - 1).bit_length()
    w = np.hanning(win)
    n = 1 + max(0, (len(x) - win) // hop)
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    X = np.abs(np.fft.rfft(x[idx] * w, nfft)) ** 2
    f = np.fft.rfftfreq(nfft, 1 / sr)
    edges = np.geomspace(F_LO, F_HI, NB + 1)
    B = np.stack([X[:, (f >= edges[i]) & (f < edges[i + 1])].sum(axis=1) for i in range(NB)], axis=1)
    db = 10 * np.log10(B + 1e-12)
    level = 10 * np.log10(B.sum(axis=1) + 1e-12)
    return db.T, level


FLOOR_DB = 20


def shape(db):
    """Each column: only what lies within 20 dB of its peak, minus its mean, unit length.
    Comparing these ignores loudness, and the floor keeps broad edges from making all whistles
    look alike."""
    db = np.maximum(db, db.max(axis=0, keepdims=True) - FLOOR_DB)
    z = db - db.mean(axis=0, keepdims=True)
    return z / (np.linalg.norm(z, axis=0, keepdims=True) + 1e-9)


def template(x, sr):
    db, level = features(x, sr)
    on = level > level.max() - 30
    a, b = np.where(on)[0][[0, -1]]
    db, level = db[:, a:b + 1], level[a:b + 1]
    weight = np.clip((level - (level.max() - 30)) / 30, 0, 1)  # loud frames count more; silent ones not at all
    first = db[:, :4].max(axis=1)
    start_bands = np.clip(first - (first.max() - 15), 0, None)    # the bands where the letter begins
    return dict(shape=shape(db), weight=weight / weight.sum(), n=b - a + 1, start=start_bands / (start_bands.sum() + 1e-9))


def match(S, tpl):
    """Weighted cosine of the template slid along S (shape matrix): one score per start frame."""
    n, T = tpl["n"], S.shape[1]
    out = np.full(T, -1.0)
    if T < n:
        return out
    acc = np.zeros(T - n + 1)
    for k in range(n):
        if tpl["weight"][k] > 0:
            acc += tpl["weight"][k] * (tpl["shape"][:, k] @ S[:, k:k + T - n + 1])
    out[: T - n + 1] = acc
    return out


def rises(db, look=6):
    """How much sound newly rises, per band and frame, in dB: the rise above the band's highest
    level of the previous 30 ms. A letter starts with a rise in its own bands; an echo only fades."""
    prev = np.full_like(db, -np.inf)
    for k in range(1, look + 1):
        prev[:, k:] = np.maximum(prev[:, k:], db[:, :-k])
    rise = np.clip(db - prev, 0, 30)
    rise[:, :look] = 0
    return rise


# ---------- decoding ----------

class Decoder:
    def __init__(self, v, snd, sr_tpl):
        self.v = v
        self.letters = list(v["letters"])
        self.tpl = {c: template(snd[c], sr_tpl) for c in self.letters}
        op, d = opening(v, snd)
        self.tpl_open = template(mix([(a * sr_tpl, x, g) for a, x, g in op], int((d + 0.05) * sr_tpl)), sr_tpl)
        cl, d = closing(v, snd)
        self.tpl_close = template(mix([(a * sr_tpl, x, g) for a, x, g in cl], int((d + 0.05) * sr_tpl)), sr_tpl)

    def decode(self, x, sr, bias_ratio=0.72, letter_cost=1.0, new_cost=0.5, onset_gain=6.0, onset_full_db=8.0, repeat_cost=3.0, verbose=False):
        db, level = features(x, sr)
        S = shape(db)
        fps = 1 / HOP_S
        mo = match(S, self.tpl_open)
        o = int(np.argmax(mo))
        open_end = o + self.tpl_open["n"]
        mc = match(S, self.tpl_close)
        mc[: open_end + int(0.3 * fps)] = -1
        c = int(np.argmax(mc))
        if verbose:
            print(f"  opening at {o / fps:.2f} s (score {mo[o]:.2f}), closing at {c / fps:.2f} s (score {mc[c]:.2f})")
        # how well a known call survived this room sets the bar a letter must clear
        bias = bias_ratio * float(mo[o])
        if verbose:
            print(f"  bar for letters: {bias:.2f}")
        lo, hi = open_end, c
        if hi - lo < 10:
            return "", dict(open=float(mo[o]), close=float(mc[c]))
        seg_S = S[:, lo:hi]
        seg_level = level[lo:hi]
        Tn = hi - lo
        ref = np.percentile(seg_level, 95)
        R_raw = rises(db[:, lo:hi])
        # a letter should start where sound rises in its own bands (echo only fades)
        R = np.maximum.reduce([np.roll(R_raw, k, axis=1) for k in (-2, -1, 0, 1)])  # allow ±10 ms
        # leaving NEW sound unexplained costs (a letter cannot just vanish); an echo is old sound, free
        new = (R_raw.max(axis=0) >= 8) * new_cost
        loud_cum = np.concatenate([[0], np.cumsum(new)])
        # per letter: score of placing it at each start = its length × (match − bias)
        place = {}
        for ch in self.letters:
            m = match(seg_S, self.tpl[ch])
            rise = self.tpl[ch]["start"] @ R
            bonus = onset_gain * (np.minimum(rise, onset_full_db) / onset_full_db - 0.5)
            place[ch] = (m - bias) * self.tpl[ch]["n"] - letter_cost + bonus
        g_in = int(round(self.v["timing"]["gap_in_word"] * self.v["timing"]["gap_jitter"][1] * fps)) + 3
        w_lo = int(self.v["timing"]["word_gap"][0] * 0.6 * fps)
        w_hi = int(self.v["timing"]["word_gap"][1] * 1.6 * fps)
        T_after = self.v["timing"]["after_open"]
        lead_max = int((T_after + 0.4) * fps)
        NEG = -1e9
        # A[t]: the two best paths whose last letter ends at t, with different last letters, as
        # [score, letter, back]. Keeping two lets a repeated letter be judged against the best
        # path that does NOT end in the same letter (an echo tends to repeat its letter).
        A = [[] for _ in range(Tn + 1)]
        W = np.full(Tn + 1, NEG)      # best path that ends with a word pause at t (or the start)
        back_W = [None] * (Tn + 1)
        # the first letter comes after the opening's echo has had time to fade
        W[int(T_after * 0.55 * fps): min(lead_max, Tn) + 1] = 0.0

        def push(lst, score, ch, back):
            for i, (sc, lc, _) in enumerate(lst):
                if lc == ch:
                    if score > sc:
                        lst[i] = [score, ch, back]
                        lst.sort(key=lambda z: -z[0])
                    return
            lst.append([score, ch, back])
            lst.sort(key=lambda z: -z[0])
            del lst[2:]

        for t in range(Tn + 1):
            # a word pause ending at t: from a letter end at s, as long as a word pause can be
            if t >= w_lo:
                for s in range(max(0, t - w_hi), t - w_lo + 1):
                    if A[s]:
                        sc = A[s][0][0] - (loud_cum[t] - loud_cum[s])
                        if sc > W[t]:
                            W[t], back_W[t] = sc, (s, 0)
            # predecessors of a letter starting at t: the two best with different last letters
            preds = []
            if W[t] > NEG / 2:
                preds.append([W[t], None, ("W", t)])
            for s in range(max(0, t - g_in), t + 1):
                for k, (sc, lc, _) in enumerate(A[s]):
                    push(preds, sc - (loud_cum[t] - loud_cum[s]), lc, ("A", s, k))
            if not preds:
                continue
            for ch in self.letters:
                n = self.tpl[ch]["n"]
                e = t + n
                if e > Tn:
                    continue
                best, prev = NEG, None
                for sc, lc, p in preds:
                    sc2 = sc - repeat_cost if lc == ch else sc
                    if sc2 > best:
                        best, prev = sc2, p
                push(A[e], best + place[ch][t], ch, (t, prev))
        end_lo = max(0, Tn - int((self.v["timing"]["before_close"] + 0.4) * fps))
        end_hi = max(end_lo + 1, Tn - int(self.v["timing"]["before_close"] * 0.4 * fps))
        ends = [(A[t][0][0], t) for t in range(end_lo, end_hi + 1) if A[t]]
        if not ends:
            return "", dict(open=float(mo[o]), close=float(mc[c]))
        _, e = max(ends)
        out = []
        t, k = e, 0
        while True:
            _, ch, (s, prev) = A[t][k]
            out.append(ch)
            if prev[0] == "W":
                bw = back_W[prev[1]]
                if bw is None:
                    break
                out.append(" ")
                t, k = bw
            else:
                t, k = prev[1], prev[2]
        return "".join(reversed(out)).strip(), dict(open=float(mo[o]), close=float(mc[c]))


def edit_distance(a, b):
    d = np.arange(len(b) + 1)
    for i, ca in enumerate(a, 1):
        prev, d[0] = d[0], i
        for j, cb in enumerate(b, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (ca != cb))
    return d[len(b)]


SENTENCES = ["you are not alone on this train", "l'été arrive, où es-tu ?",
             "the quick brown fox jumps over the lazy dog", "meet me at the old bridge at noon",
             "ich bin gleich wieder da", "merci pour la lettre"]
QUIET = [("hiss", 35)]
CONDITIONS = {
    "clean":        dict(speaker=False, distance=0.3, noise=[]),
    "near 0.4 m":   dict(distance=0.4, rt60=0.5, critical=0.6, noise=QUIET),
    "room 1 m":     dict(distance=1.0, rt60=0.5, critical=0.6, noise=QUIET),
    "room 1.5 m":   dict(distance=1.5, rt60=0.5, critical=0.6, noise=QUIET),
    "room 3 m":     dict(distance=3.0, rt60=0.5, critical=0.6, noise=QUIET),
    "hall 3 m":     dict(distance=3.0, rt60=1.6, critical=2.5, noise=QUIET),
    "street 1.5 m": dict(distance=1.5, rt60=0.3, critical=3.0, noise=[("traffic", 15), ("hiss", 35)]),
    "station 2 m":  dict(distance=2.0, rt60=1.2, critical=2.0, noise=[("traffic", 12), ("voices", 18), ("hiss", 35)]),
}


def main(repeats=1, verbose=False):
    v, snd, sr = load_voice()
    dec = Decoder(v, snd, sr)
    total_err = total_n = 0
    for cname, cond in CONDITIONS.items():
        err = n = 0
        for r in range(repeats):
            for si, text in enumerate(SENTENCES):
                y, sung = sing(text, v, snd, seed=10 * r + si)
                h = transmit(y, cond, sr, seed=100 * r + si)
                h = resample_poly(h, 160, 147)  # the phone records at 48 kHz
                got, info = dec.decode(h, 48000)
                e = edit_distance(got, sung)
                err += e; n += len(sung)
                if verbose or e:
                    print(f"  [{cname}] {sung!r}\n  {'':{len(cname) + 2}} {got!r}  ({e} errors)")
        total_err += err; total_n += n
        print(f"{cname:14s} {100 * err / n:5.1f}% characters wrong", flush=True)
    print(f"{'all':14s} {100 * total_err / total_n:5.1f}%")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1, "-v" in sys.argv)
