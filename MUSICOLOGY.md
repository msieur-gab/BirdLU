# Musicology: placing the bird alphabet on a score

Branch `musicology`, started 16 Nov 2026 from `accents`. This file records the approach and the method,
step by step, so the build can be explained later. It is updated as each step is done.

## Why this branch

The accent calls can only be designed once the rest of the voice is fixed: an accent call has to stay
apart from every letter, sign and frame call. Before fixing the voice, Gab asked to see how the letters
spread in pitch. He put it this way: "I am almost certain that music theory could help us achieve what
we want to deliver."

The assumptions tested here:

1. A small speaker and a phone microphone handle about 2 to 3 octaves. The alphabet should use that
   range on purpose instead of crowding part of it.
2. **Letters often sung one after the other should sit far apart in pitch** (Gab: "identify the most
   used combination of letters like th in English and try to use it as a rule to make each sound sit on
   opposite side of the spectrum"). A letter lands in the echo of the one before it, and a different
   pitch keeps the two apart.
3. Rising and falling notes, note shape and length help as well. They come as a second step.

Rule kept from earlier work: the voice is not changed until Gab has heard and chosen. Every step below
measures; any new placement of the letters is offered to his ear first, then tested in a real room.

## Step 1: every sound on one staff (`score.html`, `lab/score.py`)

**Method**
- For each letter, sign and frame call of the voice (`birds/voice/`), the pitch line is measured with
  the synthesizer's own tracker (`lab/synth.py`, `track`): the strongest pitch every 1.45 ms, with the
  loudness of the note.
- Only the sounding part is kept (louder than −30 dB below the note's peak).
- **Main pitch:** the average of the pitch line on a log scale, weighted by loudness.
- **Range:** the 5th to 95th percentile of the pitch line.
- Pitches are given as note names, with A4 = 440 Hz.
- Output: `birds/score.json`. The page draws each pitch line on a staff (thicker means louder) and lists
  the sounds sharing a semitone.

**Result (voice of 14 Nov)**
- The voice spans E6 to C9 (1339–8155 Hz): 2.6 octaves of the 3.2 the listener hears (1–9 kHz).
- 37 sounds (26 letters, 9 signs, 2 frame calls) in about 31 semitones, unevenly spread:
  - g r j p c within B7–C#8, where "arrive" failed (the second r read as p or j);
  - a o @ f x , v - within F7–G7 (a and o on the same note);
  - ten sounds within D8–F8;
  - E6–B6 and F8–C9 almost empty.

## Step 2: the most used letter pairs (`lab/bigrams.py`, section on `score.html`)

**Corpus.** Two public-domain novels per language, from Project Gutenberg. They are downloaded once into
`lab/corpus/`, which is not in git.

| Language | Books |
|---|---|
| English | Pride and Prejudice (1342), Moby Dick (2701) |
| French | Madame Bovary (14155), Le comte de Monte-Cristo I (17989) |
| German | Effi Briest (5323), Faust I (2229) |
| Spanish | Niebla (49836), Los cuatro jinetes del apocalipsis (24536) |
| Italian | I promessi sposi (45334), Le avventure di Pinocchio (52484) |

Rejected: Don Quijote (Spanish of 1605) and two bilingual readers. Novels were chosen over word lists
because they give running text, as people write it.

**Method**
1. Keep only the book's text, between Gutenberg's START and END lines.
2. Lower case; ß → ss, æ → ae, œ → oe. Accents are folded to the plain letter (é → e), because an
   accent is sung as its own call after the letter, so the letter itself is the plain one.
3. A word is a run of the letters a–z. Every pair of neighbouring letters inside a word is counted.
   - Pairs across words are not counted: there is a 0.3 s pause between words, against 25 ms inside a
     word.
   - Doubled letters (ll, ss) are counted but kept apart, because they are a separate problem.
4. Each language's counts become shares (% of its pairs). The five languages are averaged with equal
   weight, so a long book or a wordy language does not count more.
5. Each pair is set against the pitch distance between its two letters today: the main pitches from
   step 1, in semitones. A pair closer than 2 semitones is flagged.

Output: `birds/bigrams.json`. The page lists the top pairs for all five languages or one language, and
plays each pair as it is sung (two letters 25 ms apart).

**Result**
- Top pairs per language:
  - English: th he in er an re;
  - French: es le re ai en de;
  - German: ch en er ei in ie;
  - Spanish: en de es os er la;
  - Italian: er on re to an co.
- The most used pair across the five languages, **en** (2.4 % of all pairs), sings only 1.6 semitones
  apart. So do **ne** and **un**; **nd** sings 1.9 apart.
- In English, **th** (3.9 % of pairs, the most used) is 1.6 semitones apart. **hi** is 1.0 apart.
- Of the 100 most used pairs (76 % of all pairs), 14 sing less than 2 semitones apart: 11.4 % of all
  the pairs sung.

## Next steps (to be agreed with Gab)

- A placement that pushes the most used pairs apart, weighted by how often they are used. With 26
  letters and 2.6 to 3 octaves, not every pair can be far apart. Rare pairs can stay close.
- Gab's ear on whether wide leaps still sound like a bird.
- Rising and falling shape as a second step.
- Real tests decide, as always.
