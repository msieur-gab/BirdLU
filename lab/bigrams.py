"""Which letters follow each other most often, in five languages, and how far apart they sing today
(Gab, 16 Nov: "identify the most used combination of letters like th in english and try to use it as a
rule to make each sound sit on opposite side of the spectrum").

Corpus: two public-domain novels per language from Project Gutenberg (list below), downloaded once into
lab/corpus/ (not in git). Method, as written in MUSICOLOGY.md:
  1. Keep the book's text only (between the Gutenberg START and END lines).
  2. Lower case; ß → ss, æ → ae, œ → oe; accents folded to the plain letter (é → e), because an accent is
     sung as its own call after the letter, so the letter itself is the plain one.
  3. Words = runs of the letters a–z. Count every pair of neighbouring letters inside a word (letters
     inside a word are 25 ms apart; between words there is a 0.3 s pause, so pairs across words are not
     counted). A doubled letter (ll, ss) is counted too, apart: it is a separate problem.
  4. Each language's counts become shares (% of its pairs); the five languages are averaged with equal
     weight, so a long book or a wordy language does not count more.
  5. Each pair is put next to the pitch distance between its two letters today (main pitch from
     birds/score.json, in semitones).

Writes birds/bigrams.json. Run:  .venv/bin/python lab/bigrams.py   (after lab/score.py)
"""
import json, os, re, unicodedata, urllib.request
from collections import Counter
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(ROOT, "lab", "corpus")
BOOKS = {
    "English": [(1342, "Pride and Prejudice"), (2701, "Moby Dick")],
    "French": [(14155, "Madame Bovary"), (17989, "Le comte de Monte-Cristo I")],
    "German": [(5323, "Effi Briest"), (2229, "Faust I")],
    "Spanish": [(49836, "Niebla"), (24536, "Los cuatro jinetes del apocalipsis")],
    "Italian": [(45334, "I promessi sposi"), (52484, "Le avventure di Pinocchio")],
}
LETTERS = "abcdefghijklmnopqrstuvwxyz"


def book(n):
    path = os.path.join(CORPUS, f"pg{n}.txt")
    if not os.path.exists(path):
        os.makedirs(CORPUS, exist_ok=True)
        req = urllib.request.Request(f"https://www.gutenberg.org/cache/epub/{n}/pg{n}.txt",
                                     headers={"User-Agent": "text-stats-script"})
        open(path, "wb").write(urllib.request.urlopen(req).read())
    t = open(path, encoding="utf-8", errors="replace").read()
    a = re.search(r"\*\*\* ?START OF.*?\*\*\*", t)
    b = re.search(r"\*\*\* ?END OF", t)
    return t[a.end() if a else 0: b.start() if b else len(t)]


def plain(text):
    t = text.lower().replace("ß", "ss").replace("æ", "ae").replace("œ", "oe")
    return "".join(c for c in unicodedata.normalize("NFD", t) if not unicodedata.combining(c))


def count(text):
    pairs, singles = Counter(), Counter()
    for w in re.findall(f"[{LETTERS}]+", plain(text)):
        singles.update(w)
        pairs.update(w[i:i + 2] for i in range(len(w) - 1))
    return pairs, singles


def main():
    score = json.load(open(os.path.join(ROOT, "birds", "score.json")))["sounds"]
    semis = lambda a, b: abs(12 * np.log2(score[a]["main"] / score[b]["main"]))
    per_lang, single_lang = {}, {}
    for lang, books in BOOKS.items():
        P, S = Counter(), Counter()
        for n, _ in books:
            p, s = count(book(n))
            P += p; S += s
        tp, ts = sum(P.values()), sum(S.values())
        per_lang[lang] = {k: v / tp for k, v in P.items()}
        single_lang[lang] = {k: v / ts for k, v in S.items()}
        print(f"{lang}: {ts:,} letters, {tp:,} pairs; top", " ".join(k for k, _ in P.most_common(12)))
    langs = list(BOOKS)
    allp = sorted({k for d in per_lang.values() for k in d})
    rows = []
    for k in allp:
        share = {l: per_lang[l].get(k, 0.0) for l in langs}
        rows.append(dict(pair=k, mean=float(np.mean(list(share.values()))), by_lang=share,
                         double=k[0] == k[1], semitones=round(float(semis(k[0], k[1])), 2)))
    rows.sort(key=lambda r: -r["mean"])
    singles = {c: float(np.mean([single_lang[l].get(c, 0) for l in langs])) for c in LETTERS}
    out = dict(method="see MUSICOLOGY.md", languages=langs,
               books={l: [dict(id=n, title=t) for n, t in b] for l, b in BOOKS.items()},
               letters=singles, pairs=[dict(r, mean=round(r["mean"] * 100, 4),
                                            by_lang={l: round(v * 100, 4) for l, v in r["by_lang"].items()})
                                       for r in rows if r["mean"] >= 0.0001])
    json.dump(out, open(os.path.join(ROOT, "birds", "bigrams.json"), "w"), ensure_ascii=False)
    print("\nTop 30 pairs, five languages averaged (% of pairs), and their pitch distance today:")
    for r in rows[:30]:
        flag = "  <-- under 2 semitones" if r["semitones"] < 2 and not r["double"] else ""
        print(f"  {r['pair']}  {r['mean'] * 100:5.2f}%  {r['semitones']:5.1f} st{flag}")


if __name__ == "__main__":
    main()
