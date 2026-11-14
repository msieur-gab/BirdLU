# BirdLU ideas: accents, distance, and a path to a trained model

For Claude Code, working in `msieur-gab/BirdLU`.
Start from branch `echo-tuning`. Read `BIRD-VOICE.md` first: it is the current state and these ideas build on it.

## The aim

Messages sung in the bird voice should be read correctly in more languages, farther away and in rooms with more echo. A trained model is one way to get there, but it comes last. It is built only once the alphabet is fixed and real data exists to train it.

## Working rules

1. **Real recordings decide.** Simulated rooms gave false confidence on 13 Nov. Every change is judged on recordings made by a phone in a real place.
2. **Gab's ear chooses every new sound.** For any new note (accent calls, the language note), make 3 candidates on a listening page like `signs.html` and wait for Gab's choice. Don't swap sounds in to fix decoding errors. That is how the "R2D2" voice happened.
3. **Change one thing at a time.** Re-run the benchmark after each change and log the result in `BIRD-VOICE.md`.
4. **The current decoder stays as the baseline.** Anything new has to beat it on recordings it has never seen.

## How results are measured

Every result is reported the same way:

| Measure | Meaning |
|---|---|
| Letters wrong | % of letters wrong, split into **swapped**, **missing** and **extra** |
| Perfect messages | % of messages read with no error |
| Readable messages | % of messages a person can still understand (judged by Gab) |
| Lost messages | opening or closing not found, so nothing decoded |

**Benchmark sentences:** a fixed set of about 20 short messages, kept in `test/benchmark.txt`:
- English, French, German and Spanish sentences;
- the known hard words ("arrive", "the quick brown fox");
- every accent, sign and digit at least twice.

**Today's baseline** (from `BIRD-VOICE.md`): 2.6 % of letters wrong at 30 cm (v8), about 7 % at 6–7 m through a door with people talking (v7). Most real errors are missing or extra letters.

---

## Phase 1: accents and the language note

**Goal:** French, Spanish, German and Portuguese text is sung and read back with its accents.

**Work**
- **Accent calls**, built like the number call: six short notes for grave, acute, circumflex, diaeresis, tilde and cedilla, each sung right after its letter (à = a + grave, ñ = n + tilde, ç = c + cedilla). Gab chooses the notes by ear.
- **The six accent notes must be clearly different from each other**, not just pleasant. If two sound alike, a misread gives a wrong accent (à read as â) instead of a missing one.
- **é and è: a choice for Gab, by ear and by test.** Today they are their own trills, so a misread é can turn into another vowel ("o", "u") instead of falling back to "e". Build both versions and compare them on the benchmark:
  - **A. Keep their own trills** (current). Shorter French messages.
  - **B. Sing them as e + acute and e + grave**, like every other accent. Every accent then fails the same way, back to the plain letter, but French messages get longer.
  - Report letters wrong on é and è, how often they come back as a vowel other than "e", and how much longer French benchmark messages get. Gab decides.
- **ß, œ, æ** stay folded to ss, oe, ae.
- **New signs:** ¿ ¡ € % / ( ), chosen the same way as the existing signs.
- **Accent rule in the decoder:** an accent call is accepted only right after a letter that can take it (vowels, c, n). Anywhere else it costs as much as a wrong letter. This blocks stray notes from being read as extra letters.
- **Doubled letters** (rr, ll, ss, tt, ee…): the second letter lands in the echo of the first, which is why "arrive" fails on its second "r". Make 2–3 versions for Gab to choose by ear, for example:
  - the second letter sung an octave higher;
  - the letter followed by a short "repeat" note.

  Test them on "arrive", "belle", "Wasser", "carro" and "little". The decoder learns the chosen rule.
- **Language note** (Gab's "key signature" idea): one short note right after the chiffchaff opening. The opening itself stays the same for every language, because it frames the message and measures the echo.
  - The note tells the decoder which accents to expect after which letters (after "u": diaeresis in German, acute or diaeresis in Spanish). These are small biases, not word lists.
  - If the note is missed, decoding goes on without the biases. The message is not lost.
- **The closing stays the same for every language.** Its slot is kept for the check letters already proposed in `BIRD-VOICE.md`.

**Expected outcome**
- Accented letters are read about as well as plain letters at 30 cm.
- A lost accent call gives the plain letter ("ecole"), never a broken word.

**Done when**
- At 30 cm, on the benchmark: accented letters wrong ≤ plain letters wrong + 1 point.
- The language note is found in ≥ 95 % of messages.
- No rise in errors on plain-letter messages.
- The "arrive" fix (from `BIRD-VOICE.md`) is re-run and recorded.
- The é/è comparison (A vs B) is recorded and Gab has chosen.
- The doubled-letter words are read right at 30 cm and 2–3 m.

---

## Phase 2: tempo for distance

**Goal:** fewer missing and extra letters at 3–7 m and in rooms with echo, without a model.

**Why:** letters in a word are about 25 ms apart, and a hall's echo lasts 0.5–2 s. At distance, each letter smears into the next. That matches the errors we see.

**Work**
- Add a slower **station timing** to the voice (`gap_in_word`, `word_gap` in `lab/export_voice.py`). Test two or three gap lengths.
- The decoder takes its gap windows from the voice timing, so it must know which timing was sung. Either use one voice file per timing, or let the language note also carry the tempo, like a tempo marking next to a key signature. Propose both and let Gab choose.
- Gab listens to each tempo too: slower must still sound like a bird.

**Expected outcome:** a clear drop in missing and extra letters at 6–7 m, at the cost of longer messages.

**Done when**
- The benchmark has been recorded at 30 cm, 2–3 m and 6–7 m for each tempo, and errors and message length are compared in a table.
- Gab has picked a station tempo, or decided against one.

---

## Proposition: neighbouring letters on different heights of the score

**A fallback experiment, not part of the plan.** Explore it only if Phase 2, with the doubled-letter rule from Phase 1, still leaves too many missing or extra letters at distance. It changes the voice Gab likes, so it has to earn its place.

**The idea** (Gab's): think of the message as a score for an instrument. Letters that often follow each other in a word sit at different heights on the staff. Each new letter then starts in quiet space instead of inside the echo of the one before. Radio does the same in echoey places, hopping to a different frequency for each symbol.

**How it would work**
- **Fixed heights:** each letter keeps one place on the staff, chosen from letter-pair counts in English, French, German and Spanish so the most common pairs (es, en, th, ou, er, ch, ie…) sit far apart. Heights never move with context; only the doubled-letter rule depends on the letter before.
- **Height is a second difference, never the only one.** Letters still differ by shape (contour, trill rhythm, length).
- **Octave as a safeguard only:** phones and small speakers carry only about 2.5 octaves (roughly 1.5–8 kHz), and bird overtones at twice the pitch make octave mix-ups a common error. No two letters may differ only by octave.
- Every note must still sound like the bird it came from. Gab's ear decides.

**Free first step, doable any time:** score the current voice. For the 50 most common letter pairs, how far apart are the two letters in pitch? Report it as a short table. It shows whether the idea has room to help before any sound changes.

**If it is explored**
- Reassign heights, make a listening page, and wait for Gab's approval of the sound.
- Sing the benchmark at 6–7 m and compare missing and extra letters with the Phase 2 result.

**Kept if:** missing plus extra letters at 6–7 m drop clearly, and Gab still likes the sound.

---

## Phase 3: a recording setup that labels its own data

**Goal:** hours of real recordings where the correct text is known, with no hand labelling.

**Work**
- **Sender:** a `rig.html` page plays an endless series of random messages and writes a log file (one line per message: text, start time, voice version, tempo, language).
  - Mix real words (EN, FR, DE, ES), random letter strings so rare letters, accents, signs and digits appear often, and the benchmark sentences.
- **Listener:** the phone records one long session. A script finds each opening call, cuts the session into messages and matches them to the log by order and time.
- **Room echo:** at the start of each session the rig plays a frequency sweep, so each place's real echo response is recorded. This replaces the invented rooms.
- **Notes on each session:** place, distance, speaker, phone, background noise.
- **Places:** at least 5 (Gab's room, the corridor, a stairwell, outdoors near traffic, a hall if possible), each at 30 cm, 2–3 m and 6–7 m.
- **Keep one whole place out of all training.** It is the test of whether a model works in a room it has never heard.

**Expected outcome:** about 300–500 messages per place and distance, from roughly an hour of playback each.

**Done when**
- At least 2,000 labelled real messages exist across 5 places.
- One place is set aside, untouched, for testing.

---

## Phase 4: a small trained letter scorer inside the decoder

**Goal:** better letter reading at distance and in echo, while keeping the parts of the decoder that already work.

**What stays:** finding the opening and closing calls, the search that cuts the sound into letters, gaps and pauses, the accent rule and the language biases.

**What changes:** the step that compares each stretch of sound with a letter's template picture is replaced by a small trained model.
- **Input:** the 48-band sound picture around a candidate letter.
- **Output:** a score for every letter, plus a "not a letter / echo" score.

**Work**
- **Training labels for free:** run the current search with the known text forced on it. It returns where each letter starts and ends in the real recording.
- **Training data:** the Phase 3 recordings, plus clean messages played through the recorded echo responses of real places and mixed with real background noise. No invented rooms.
- **Size:** a small convolutional network, int8, under 100 KB.
  - It must decode a message on a phone faster than the message lasts.
  - Later it should run on an ESP32-S3 (TFLite Micro or ESP-DL).
- **Training** in Python in `lab/`. Export so it runs in the Web Worker (`js/decode-worker.js`).
- **The confusion table** (which letters it still mixes up) goes back to Gab as input for the next alphabet change.

**Expected outcome:** the biggest gains at 6–7 m and in echo; little change at 30 cm, which is already nearly perfect.

**Done when**, measured on the place kept out of training:
- letters wrong at 6–7 m are at most half the current decoder's;
- no place or distance gets worse;
- it runs in the PWA within the size and time limits.

If it does not beat the current decoder, it is not used. Report the confusion table and what it shows instead.

---

## Phase 5 (only if needed): a model that reads letters straight from the sound

Consider this only if Phase 4 stops improving and most errors are still missing or extra letters.

A sequence model trained with CTC reads letter sequences straight from the sound picture and handles missing and extra letters by design. It needs much more data, is harder to fit on an ESP32, and loses the accent and language rules unless they are added back. It needs Gab's go-ahead before any work starts.

---

## What to deliver at each phase

- The code on a branch from `echo-tuning`, one phase per branch or clear commit series.
- Listening pages for every sound Gab has to choose.
- An updated `BIRD-VOICE.md`: what changed, the benchmark table (letters wrong split into swapped, missing and extra; perfect, readable and lost messages) and what is still open.
- Stop and check with Gab at each "Done when" before starting the next phase.
