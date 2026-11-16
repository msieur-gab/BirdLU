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

## Step 3: a proposed placement (`lab/placement.py`, section on `score.html`)

**What may change.** Only which letter sings which sound. The sounds themselves stay the approved ones:
- the six vowel trills are shared out among the six vowels, so vowels stay trills;
- the consonant notes are shared out among the consonants, so consonants stay single notes;
- signs and frame calls do not move.

The w sound is out of the pool. Gab: "the sound of the W is unbearable, hence the WH is sounding
aggressive". w gets no sound, only the pitch where a new w would best sit, picked by the same rule from a
semitone grid over the voice's range.

**Rule.** Each pair of letters (both orders, xy + yx, the five languages averaged) costs its share of all
pairs times how much closer than half an octave its two letters sing:

    cost = sum over pairs of  share × max(0, 6 − semitones apart) / 6

Half an octave was chosen as the distance beyond which a pair is "apart enough". Rare pairs cost little,
so they may stay close.

**Search.** Swap the sounds of two letters whenever that lowers the cost, until no swap helps. This is
run from 300 random starts (seeded, so it can be repeated), and the best result is kept. It takes about
20 s.

**Result** (output in `birds/placement.json`)

| Pairs sung | under 2 semitones apart | under 4 semitones | mean distance |
|---|---|---|---|
| Today, five languages | 14.3 % | 29.4 % | 7.3 st |
| Proposed, five languages | 4.3 % | 9.0 % | 9.7 st |

- Every language improves:

  | Language | under 2 semitones, today → proposed |
  |---|---|
  | English | 16.3 → 4.7 % |
  | French | 14.6 → 3.5 % |
  | German | 16.2 → 2.8 % |
  | Spanish | 12.4 → 6.3 % |
  | Italian | 11.7 → 4.4 % |

- r moves to the low blackbird note (A#6), out of the crowd around B7–C8 where "arrive" failed.
- A new w would sit best near F6 (about 1400 Hz), at the bottom of the range.
- The proposed voice still reads back correctly on clean sound: one sample sentence per language, read
  back with no room. This is a sanity check, not a real test.
- Limits: only the main pitch is used. Trills cover a range around it, and note shape and length are
  left for later.

## Step 4: what makes a note sound like a bird (`lab/variants.py`, `variants.html`)

**What Gab heard.** "The trill effect is the one sounding most like a bird, and short sounds with high
tune or frequencies are the ones sounding the most synthetic and harsh to the human ears."

**What the synthesizer does today**
- Every note gets:
  - the pitch line and the loudness curve measured from its real note;
  - two overtones;
  - a slow pitch wobble of 0.4 %;
  - 3 ms soft edges;
  - up to ±2 dB of loudness per letter.
- Vowels are trills: 3–4 repeats, each a little different in pitch (±0.6 %), loudness (±0.8 dB) and
  length (±3 %), with a drift from repeat to repeat.
- Consonants are a single note, with none of that variation.
- The shortest and highest consonants are t (6.5 kHz, 47 ms), l and h (7.1–7.2 kHz), d (6.2 kHz) and
  n (5.6 kHz).

**Three versions, to hear against today**

All three are made by the same synthesizer from the same models. Before any change, the rebuild of
today's letters was checked against the voice files: correlation 1.0.

| Version | Change |
|---|---|
| A · little trills | Every consonant shorter than 100 ms becomes two notes: t n s r l d p w. The two notes are 12 ms apart, and the second is 0.03 octave lower and 3 dB softer. Each note varies as the vowel repeats do. |
| B · lower range | The whole range is squeezed under 5.5 kHz. The lowest letter stays where it is, the highest (i) goes to 5.5 kHz, and the letters between move in proportion on a log scale, so their order is kept. Letters move down 1 to 5.6 semitones. |
| C · both | A and B together. |

Signs and frame calls are unchanged. Every version reads the five sample sentences back correctly on
clean sound.

**Known trade-offs, to judge by ear and by real tests**
- In A, a consonant made of two notes comes closer to a short vowel trill.
- In B, the letters are 18 % closer to each other in pitch, and some letters move nearer to signs and
  frame calls, which did not move.

**Gab's choice:** B and C, "because it's like lowering the high pitch, which is making the ears really
uncomfortable actually". The consonants still sound robotic in every version; the vowels are "just
perfect".

## Step 5: bird gestures for the consonants, and the letters on a scale (`lab/gestures.py`)

**Where the idea came from.**
- Claude first suggested phonemes (speech sounds) as the code. That was rejected: it needs a spelling
  dictionary per language, and reading back is ambiguous ("o", "au" and "eau" sound the same).
- What remained was the grouping that speech uses for consonants (stops, hissing, humming, flowing),
  as a guide for bird gestures. Gab: "we just need to try to make them sound like real birds ... since
  it's a combination of letters, that should make a nice melody."
- Gab also thought of the score as notes and curves. Curves: the trill as a wave, arcs up and down,
  lines up and down. Notes: do ré mi fa sol la si over two octaves.
- Two octaves hold 24 semitones, because sharps and flats overlap (do# = ré♭). Claude advised notes
  without sharps or flats, for two reasons: notes a semitone apart clash, and they are hard to tell
  apart in a room.

**Method.** Built on version B (the lower range). Vowels are unchanged. Each consonant keeps its own
bird's overtones and 30 % of its own pitch line, under the gesture of its group:

| Group | Letters | Gesture |
|---|---|---|
| chip | t p k b d g c q | short note, clear attack, slurring down (≤ 60 ms) |
| buzz | s f z v j x h | four tiny notes 26 ms apart |
| hum | m n | soft round arc, 110 ms, overtones halved |
| flow | l, w, r | l glides up and w glides down (0.36 octave); r is three quick notes, each sliding down |

| Version | What it is |
|---|---|
| D · bird gestures | B with the gestures above |
| E · on the scale | D, with every letter (vowels too) moved to the nearest note without sharps or flats (A4 = 440 Hz) |

**Clean read-back** (no room; a sanity check, not a real test)
- D read every test sentence back correctly: the five sample sentences, and two pangrams covering all
  26 letters.
- E misread the Italian "otto" as "otdo". On the scale, t and d both land on ré8, and both are chips.
- A scale gives fewer pitches than letters, so letters that share a note need different gestures.

**Gab, on D and E:** "getting to the right direction. It starts to sound really like a bird, and it's
extremely delighting to listen."

## Step 6: a new opening and closing, from the nightingale (`lab/nightingale.py`, `nightingale.html`)

Gab: "something we need to change also is the opening and the closing, which are not good. Perhaps we
should inspire ourselves from ... Rossignol?" He meant the nightingale of Andersen's tale, sung for the
Emperor of China. Its phrases often open with slow, soft notes that swell, and end with a rich flourish.

**Constraint.** The opening also works as the tuning fork that measures the room's echo. Whatever is
chosen must stay distinct from every letter. The decoder builds its templates from the sound files, so
it follows the change.

**Method**
- Three Common Nightingale recordings were added to `lab/fetch_sources.py`: XC138451, XC473316 and
  XC546043, all CC BY-SA 4.0 via xeno-canto and Wikimedia Commons.
- Each recording is cut into song phrases:
  - sound in the 1.2–9 kHz band counts when it is 12 dB above the recording's quiet 20 %;
  - the level is smoothed over about 0.1 s;
  - pieces less than 0.35 s apart are joined into one phrase.
- Phrases of 1.2 s or more are kept: 47 in all.
- They are cleaned like every other source: spectral gating, level matched, soft edges.
- Gab listens to the real phrases first and marks openings and closings. Synthesized versions come
  after his picks.

**Gab's picks:** opening = phrase 1.2 (XC138451 at 13.76 s, 1.7 s: sweeps, a buzzy high passage,
then six "jug" notes); closing = phrase 1.4 (XC138451 at 21.52 s, 1.1 s: a long soft whistle, then
three arched notes, each with a buzz).

**Through our synthesizer** (`lab/frames_ng.py`)

Three versions of each pick:

| Version | How it is built |
|---|---|
| copy | The strongest pitch line and its two overtones, measured every 1.45 ms and rebuilt. The nightingale sometimes sings two voices at once; only the stronger one is kept. |
| notes | The phrase is cut into its notes (36 in the opening, 18 in the closing). Each note is modelled like a letter and sung again at its own time and loudness. |
| notes, lower | The same as notes, with every note moved down like version B of the letters. |

- All versions are cut above 9 kHz with a 6th-order low-pass. The fast "jug" sweeps carried overtones
  up to 11 kHz, which is the harsh high top Gab's ear objects to. The listener only hears 1–9 kHz.
- They are level-matched like today's frame notes.
- On `nightingale.html`, each version can be played alone or around a whole message, with today's
  letters or the version D letters.
- Every version, and the recording itself, frames the French sample correctly on clean sound.
- Gab then asked to try phrase **2.16** for the opening (XC473316 at 102.54 s, 1.5 s, 21 notes). It
  replaces 1.2 on the page, and it also frames the French sample correctly on clean sound.

**Gab:** "the two versions, notes or notes lower, are working very well." He also wondered about
different openings and closings for different themes of message, to look at later.

## Step 7: punctuation left unsung (`js/birdsong.js`, `sing`)

Gab: "for now, we don't make the punctuation signs sing ... because I think that's what actually breaks
the melody."

**How it works**
- `sing(text, voice, seed, { punctuation: false })` leaves . ? ! , ' - : unsung.
- `#` stays, because it is the number call, and `@` is not punctuation.
- A sign inside a word ("l'été", "es-tu") leaves a word pause, so the words do not run together. The
  French sample reads back "l ete arrive ou es tu".
- On `variants.html` and `nightingale.html`, a "sing punctuation" switch controls this; it is off by
  default.
- The Send page and the approved voice are unchanged.

## Step 8: tests without the opening and closing (`sing`, option `frames`)

Gab: "for the tests, remove the entrance and the singing for the entry and the end of the message,
because they are very annoying ... or add a toggle."

- `sing(..., { frames: false })` sings the letters only. "the end" lasts 1.7 s instead of 5.5 s.
- On `variants.html`, a selector chooses the opening and closing: none (the default), nightingale
  (notes), nightingale (notes, lower), or chiffchaff (today).
- `score.html` plays its Today/Proposed comparison without frames.
- The listener needs an opening and a closing to find a message. So with none, the clean read-back
  checks the same letters, with the same timing, sung inside the chiffchaff frames.
- The Send page is unchanged.

## Next steps (to be agreed with Gab)

- Gab's ear on whether wide leaps still sound like a bird.
- Rising and falling shape as a second step.
- Real tests decide, as always.
