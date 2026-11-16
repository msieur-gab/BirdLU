"""Fix the decoder's mix-ups without touching the sound: letter pairs and real words (MUSICOLOGY.md, step 16).

Gab, 16 Nov: after the partition voices ("birds from the jungle or monkeys"): "the D version was really good" and,
asked whether to try decoder-side fixes on the real recordings: "you just have to try".

Two helps, both from the five-language books already harvested (lab/corpus, lab/bigrams.py):
  1. letter pairs inside the decoder: when two letters fit the sound about equally, prefer the one that usually
     follows the previous letter (log probability, the five languages weighted equally; a word start uses the
     probability of starting a word);
  2. a word check after it: a decoded word that is not a known word (seen at least 3 times in the books) is replaced
     by the known word reachable with the fewest changes, where swapping two letters the decoder finds alike
     (lab/likeness.py, likeness > 0.65 for the voice: decided from the sounds, not from the test errors) costs 1,
     and any other single change (a letter added, dropped or swapped) costs 3; at most cost 4; ties go to the more
     frequent word. Words with # or @ (numbers) are left alone.
Measured on the real recordings, letter by letter (swapped, missing, extra), against the decoder alone.
Run:  .venv/bin/python lab/lm_test.py
"""
import glob, json, os, re, sys
from collections import Counter
import numpy as np, soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decode import load_voice, Decoder, normalize, ROOT
from real_test_v9 import sung, ops, PRESETS
from likeness import likeness, room

BOOKS = {"English": ["pg1342", "pg2701"], "French": ["pg14155", "pg17989"], "German": ["pg5323", "pg2229"],
         "Spanish": ["pg49836", "pg24536"], "Italian": ["pg45334", "pg52484"]}
AZ = "abcdefghijklmnopqrstuvwxyz"
MAXC = float(os.environ.get("MAXC", "4"))


def corpus():
    words, pairs = Counter(), {}
    for lang, books in BOOKS.items():
        wc = Counter()
        for b in books:
            t = normalize(open(os.path.join(ROOT, "lab", "corpus", b + ".txt"), encoding="utf-8", errors="ignore").read())
            wc.update(re.findall(r"[a-z]+", t))
        pc = Counter()
        for w, n in wc.items():
            s = "^" + w
            for a, b in zip(s, s[1:]):
                pc[(a, b)] += n
        tot = Counter()
        for (a, b), n in pc.items():
            tot[a] += n
        pairs[lang] = {(a, b): n / tot[a] for (a, b), n in pc.items()}
        words.update({w: n / sum(wc.values()) * 1e6 for w, n in wc.items()})   # per million, each language equal
    P = {}
    for a in "^" + AZ:
        for b in AZ:
            P[(a, b)] = np.log(np.mean([pairs[l].get((a, b), 0) for l in BOOKS]) + 1e-4)
    return words, P


def make_lm(P):
    def lm(prev, ch):
        if ch not in AZ:
            return 0.0
        a = prev if (prev is not None and prev in AZ) else "^"
        return float(P[(a, ch)])
    return lm


def corrector(words, alike):
    known = {w: n for w, n in words.items() if n >= 3 / 2.0}      # about 3 times in a 2-million-word language share
    by_len = {}
    for w in known:
        by_len.setdefault(len(w), []).append(w)

    def dist(a, b):
        n, m = len(a), len(b)
        D = np.zeros((n + 1, m + 1)); D[:, 0] = np.arange(n + 1) * 3; D[0, :] = np.arange(m + 1) * 3
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                x, y = a[i - 1], b[j - 1]
                sub = 0 if x == y else (1 if frozenset((x, y)) in alike else 3)
                D[i, j] = min(D[i - 1, j] + 3, D[i, j - 1] + 3, D[i - 1, j - 1] + sub)
        return D[n, m]

    def fix(text):
        out = []
        for w in text.split(" "):
            if not w or w in known or not w.isalpha() or not all(c in AZ for c in w):
                out.append(w); continue
            best = None
            for L in (len(w) - 1, len(w), len(w) + 1):
                for cand in by_len.get(L, []):
                    d = dist(w, cand)
                    if d <= MAXC and (best is None or (d, -known[cand]) < (best[0], -known[best[1]])):
                        best = (d, cand)
            out.append(best[1] if best else w)
        return " ".join(out)
    return fix


def score(files, dec, letters, **kw):
    fix = kw.pop("fix", None)
    tot = np.zeros(4, int); lines = []
    for f in files:
        x, fs = sf.read(f); x = x.mean(axis=1) if x.ndim > 1 else x
        got, _ = dec.decode(x, fs, **kw)
        got = re.sub(r"[.?!,'\-:]", " ", got); got = re.sub(r" +", " ", got).strip()
        if fix:
            got = fix(got)
        want = min((sung(p, letters) for p in PRESETS), key=lambda w: sum(ops(w, got)))
        s, mi, ex = ops(want, got)
        tot += [s, mi, ex, len(want.replace(" ", ""))]
        lines.append((want, got))
    return tot, lines


def main():
    words, P = corpus()
    lm = make_lm(P)
    sets = [("v9 D, 20 cm", "recordings-v9", "nightingale-d", slice(7, 14)),
            ("v9 D, 2.5 m", "recordings-v9", "nightingale-d", slice(0, 7)),
            ("v11 G, 20 cm", "recordings-v11", "nightingale-g", slice(None)),
            ("v11 G, 4–5 m", "recordings-v11-far", "nightingale-g", slice(None))]
    for label, folder, voice, part in sets:
        v, snd, sr = load_voice(os.path.join(ROOT, "birds", "voices", voice))
        dec, letters = Decoder(v, snd, sr), set(v["letters"])
        L = likeness(snd, sr, [c for c in v["letters"] if c.isalpha()], room(sr, 1.0))
        alike = {frozenset(p) for p, l in L.items() if l > 0.65}
        fix = corrector(words, alike)
        files = sorted(glob.glob(os.path.join(ROOT, "test", folder, "*.wav")), key=lambda p: p.split("-heard-")[1])[part]
        print(f"\n{label} ({len(files)} recordings)")
        for name, kw in (("decoder alone", {}), ("+ letter pairs", dict(lm=lm, lm_weight=1.0)),
                         ("+ letter pairs ×2", dict(lm=lm, lm_weight=2.0)),
                         ("+ word check", dict(fix=fix)), ("+ both", dict(lm=lm, lm_weight=1.0, fix=fix))):
            (s, mi, ex, n), lines = score(files, dec, letters, **kw)
            print(f"   {name:18s} {s + mi + ex:3d} of {n} wrong ({100 * (s + mi + ex) / n:4.1f} %)  swapped {s}, missing {mi}, extra {ex}")
            if name == "+ both":
                for want, got in lines:
                    if want != got:
                        print(f"        {want}  →  {got}")


if __name__ == "__main__":
    main()
