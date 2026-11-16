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

**Gab:** "the nightingale version with D bird gesture is the most enjoyable and appealing version."

## Step 9: the real test, laptop sings and phone listens (`lab/make_test_voice.py`, `lab/serve_https.py`)

**Test voices** (in `birds/voices/`)
- Both take the approved voice (signs, timing, credits) with the letters of version D and the
  nightingale opening 2.16 and closing 1.4:
  - `nightingale-d` uses the frames in the "notes" version;
  - `nightingale-d-lower` uses the frames in the "notes, lower" version.
- They are used as `send-bird.html?voice=<name>` on the laptop and `listen-bird.html?voice=<name>`
  on the phone.

**Send page**
- A "sing punctuation" box was added, unchecked.
- Two presets were added: "arrive belle Wasser carro little" (doubled letters) and "the quick brown
  fox jumps over the lazy dog" (all 26 letters).

**HTTPS.** `lab/serve_https.py` serves the repo on port 8443 with a self-signed certificate, because
the phone's microphone needs HTTPS.

**Clean check before the test** (Send page, `nightingale-d`)
- 6 of 7 presets read back correctly.
- "little" came back "litdle": the second t was read as d. In version D, t and d are both chips and
  sit only about 1 semitone apart. This is the doubled-letter problem, made worse by the gestures.

**Result, real test v9** (`test/recordings-v9`, `lab/real_test_v9.py`)

Gab played the 7 presets once per setup. The first set is taken as the Bluetooth one: its echo times
are longer (0.8–1.0 s against 0.5–0.8 s), and its sound has no laptop-speaker colouring. The 20 cm set
has "meet me…" twice and lacks "arrive belle…".

| Setup | Letters wrong | Swapped / missing / extra |
|---|---|---|
| Laptop speakers, 20 cm | 11 of 175 (6.3 %) | 11 / 0 / 0 |
| Bluetooth speaker, 2.5 m | 30 of 177 (16.9 %) | 26 / 1 / 3 |
| v8 for comparison: approved voice, 30 cm | 2.6 % | |

**Readings of the result**
- The laptop did sing the test voice. The approved voice's decoder reads nonsense from the recordings;
  the test voice's decoder reads them.
- D's letters are lower than today's: median 3.6 kHz against 4.1, top 5.9 kHz against 8.2, and nothing
  above 6 kHz against 16 % today.
- Gab heard the laptop as "high again", and he was right. At 20 cm, the 5–6 kHz band carries 28 % of
  the recorded sound against 13 % in the synthesized sound: the laptop speakers boost it. Through the
  Bluetooth speaker, the recording matches the synthesis.
- The errors are almost all swaps, and the same pairs every time. Squeezing the range (B) and giving
  groups the same gesture (D) left these pairs 0.1 to 2.2 semitones apart:

  | Swap | Pitch distance | Gestures |
  |---|---|---|
  | r → j | 0.1 st | roll / buzz |
  | t → h | 1.3 st | chip / buzz |
  | b → z | 1.3 st | chip / buzz |
  | p → q | 1.2 st | chip / chip |
  | g → q | 2.2 st | chip / chip |
  | x → v | 1.1 st | buzz / buzz |

- Doubled letters are not the main problem here. "arrive" → "arjive" and "carro" → "carjo" are the
  r → j swap, which also hits single r's ("wassej", "ovej", "jendez").

## Step 10: version F, version D placed again (`lab/placement_d.py`)

Gab: "yes, redo the placement with the 3 semitones rule".

**What moves.** Only the consonants' pitch. Gestures and timbre stay those of D; vowels, signs and
frames do not move.

**Rules**, on a semitone grid from F6 to F8 (1397–5588 Hz):
1. Consonants with the same gesture sit at least 3 semitones apart. The gestures are chip, buzz and
   hum; l, w and r each have a gesture of their own. This is Gab's rule.
2. No two consonants share a semitone. This was added because the test's worst swaps crossed
   gestures: r/j at 0.1 semitones and t/h at 1.3.

**Cost.** The step 3 cost (most used pairs pushed apart), plus 0.03 per semitone a consonant moves
from D. Search: 400 seeded starts, moving or swapping consonants.

**Penalty for moving.** Stronger values were tried and rejected:
- At 0.10 or 0.25, the letters move less, but t/h stays only 2 semitones apart, and t → h was the most
  frequent swap in test v9.
- 0.03 was kept, at the price of large moves: n and l go down about 19 semitones, r about 14.

**Result**

| Pairs sung | under 2 semitones apart | under 4 semitones | mean distance |
|---|---|---|---|
| D | 15.9 % | 37.4 % | 5.9 st |
| F | 5.0 % | 10.5 % | 10.3 st |

The swapped pairs of test v9 move apart:

| Pair | In D | In F |
|---|---|---|
| r/j | 0.1 st | 17 st |
| t/h | 1.3 st | 10 st |
| p/q | 1.2 st | 12 st |
| x/v | 1.1 st | 6 st |
| b/z | 1.3 st | 4 st |
| g/q | 2.2 st | 3 st |

**Test voice `nightingale-f`**
- Letters F, with the nightingale frames ("notes" version).
- No punctuation: it is not sung for now, so the listener should not expect it. On clean sound, "little"
  was first read as "li-tle", because t now sits on the hyphen's note. # and @ are kept.
- All 7 Send presets read back correctly on clean sound.

**Result, real test v10** (`test/recordings-v10`, `lab/real_test_set.py`)
- Setup: 7 recordings, taken to be the laptop at about 20 cm (the 5–6 kHz band is boosted as in v9's
  20 cm set). "you are not alone…" was played twice; "l'été…" is missing.
- **20 of 186 letters wrong (10.8 %)**, against 6.3 % for D at 20 cm. All are swaps but one.
- New swaps, all among the letters F moved to the bottom of the range, where eight consonants sit on
  eight neighbouring semitones (F6 to C7: n r b s l d z w):

  | Swap | Times | In F |
  |---|---|---|
  | r → n | 6 | F#6 roll / F6 hum, 1 semitone apart |
  | d → z | 5 | A#6 chip / B6 buzz, 1 semitone |
  | b → s | 4 | G6 chip / G#6 buzz, 1 semitone |

- The swaps of v9 (r/j, t/h, p/q) are gone.

**What it teaches**
- One semitone between different gestures is not enough. That rule was Claude's addition, and the
  search used it to pack the frequent letters into the empty bottom of the range.
- Gab: "pitch will not be enough. It should be pitch plus the envelope of the sound."
- The decoder reads the pitch line over time (where the sound sits, and how it bends), not the
  loudness. Letters that are close in pitch must therefore bend clearly differently.

## Step 11: note + curve, version G (`lab/likeness.py`, `lab/curves.py`)

Gab: "pitch will not be enough. It should be pitch plus the envelope of the sound" → "go ahead with
note + curve". The curves are his: "the trill is like a wave ... an arc going down, arc going up. A
line going up, a line going down".

**A guide that predicts the room** (`lab/likeness.py`)
- It measures how alike two letters look to the decoder itself: the sound picture, the shape of each
  5 ms column, and the template slid along. The sound first passes through a simple echo: the direct
  sound plus a fading noise tail of 0.6 s, at equal energy.
- Checked against the real tests, the pairs that actually swapped rank among the most alike of all 325
  pairs:
  - D (v9): b/z 1st, t/h 2nd, r/j 5th, p/q 7th, g/q 8th;
  - F (v10): b/s 1st, d/z 3rd, r/n 4th.
- It is a design guide, not a test.

**Design** (`lab/curves.py`)
- Each consonant keeps the texture of its D group:
  - chip: short, sharp attack;
  - buzz: four pulses;
  - hum: soft and round;
  - glide;
  - roll (r): three pulses.
- It also keeps its own bird's overtones, and 15 % of its own pitch line.
- On top it gets a **note** (G6–D8) and a **curve** spanning half an octave: rise, fall, arc, valley,
  flat or warble.
- The vowels, # and @ do not change.
- 2,400 candidates were made (20 consonants × 6 curves × 20 notes), and their likeness compared pair by
  pair: about 2 million pairs.
- Cost: the sum over letter pairs of (frequency of x + frequency of y) × (likeness − 0.5)², plus a
  little of the step 3 cost.
- The search ran from 12 seeded starts and took 11 minutes.

**Result**

| Voice | pairs above 0.75 | pairs above 0.65 | sum of (likeness − 0.5)² |
|---|---|---|---|
| approved (v8: 2.6 %) | 3 | 10 | 0.54 |
| D (v9: 6.3 %) | 6 | 23 | 1.42 |
| F (v10: 10.8 %) | 7 | 19 | 1.38 |
| **G** | **0** | **1** (a/o, vowels untouched) | **0.09** |

- G's most alike consonants: d/h 0.58, s/d 0.57, d/q 0.57.
- Caveat: G was chosen using this measure, so it scores well on it by design. The real test decides.
- Test voice `nightingale-g`: no punctuation, # and @ kept. All 7 Send presets read back correctly on
  clean sound.

**Result, real test v11** (`test/recordings-v11`, `lab/real_test_set.py`): laptop at about 20 cm, the 7
Send presets. **1 of 177 letters wrong (0.6 %)**, against 6.3 % for D (v9) and 10.8 % for F (v10) in the
same setup, and 2.6 % for the approved voice at 30 cm (v8). The only error: "little" heard as "liptle",
t read as p. Both sit on D8 (t arc, p rise); the guide gave them 0.56, just under its most alike pairs (0.58). Echo measured 0.62–0.91 s.

**Result, real test v11 far** (`test/recordings-v11-far`): speaker at 4–5 m in the living room, echo measured
0.84–1.00 s. **19 of 187 letters wrong (10.2 %)**: swapped 15, missing 3, extra 1. D made 16.9 % at 2.5 m (v9).
Every consonant swap was between letters 0 or 1 semitone apart: t→p three times (both D8), d→q (both F7),
s→d and q→h (F#7/F7), c→f (C#8/D8), r→l (A6/A#6). In an echo this long the curve alone no longer keeps two
letters on the same note apart. The guide (at 0.6 s or 1.0 s echo) ranked t/p, d/q, s/d among its 7 most alike,
but q/h, c/f, r/l only 25th–37th: it does not see one-semitone neighbours as a risk.

## Step 12: version H, G spaced for an echoing room (`lab/curves_h.py`)

Real test v11 far showed that in a long echo (about 1 s) the curve is smeared and only the note keeps letters
apart: every swap was between letters 0 or 1 semitone apart. Gab: "yes, commit G then build H".

- The 13 most used consonants (n s t r l d c h m p g b v, five languages) each get a note of their own on a
  whole-tone grid from E6 to E8 (1319–5274 Hz, under Gab's 5.5 kHz), so any two are at least 2 semitones apart.
- The 7 rarest (f w q z k j x; f is slightly rarer than v, 1.31 % against 1.37 %) share one of those notes with
  a more used letter, told apart by curve and texture.
- Textures and curves as in G. Chosen with the same cost as G, the guide's echo set to 1.0 s.

| Note | Letters (rare in brackets) |
|---|---|
| E6 | n flat |
| F#6 | r flat |
| G#6 | l flat |
| A#6 | s flat |
| C7 | b fall (z flat) |
| D7 | g fall |
| E7 | d arc |
| F#7 | m flat (q rise) |
| G#7 | t valley |
| A#7 | c rise |
| C8 | p valley (w arc) |
| D8 | v arc (x fall) |
| E8 | h warble (f arc, j flat, k rise) |

- Guide: sum 0.07 (G 0.09), most alike consonants d/q 0.57, f/k 0.55, h/v 0.54 (at 1.0 s echo).
- Every letter reads back on clean sound. With a simulated 1 s echo, 4 of 177 wrong (G 7): a guide only,
  simulated rooms are not evidence.
- Test voice `nightingale-h`.
- Watch: E8 carries four letters (h and three rare ones).

## Step 13: back to the birds (`lab/birdsong_stats.py`, `lab/spaced_d.py`)

Gab heard G and H as "R2D2 ... the best version was the version D", and asked whether Claude still had a feeling
of what a bird song is, and why the research was not used. The research (dolphin and whale covert modems) keeps
the animal's own calls and chooses among them; G and H drew new shapes instead.

Measured on the 19 recordings (first minute each) and on our voices singing the 7 presets, with the same note
cutter (median per species):

| | note length | pitch movement inside a note | leap to next note | leaps over 7 st | gap |
|---|---|---|---|---|---|
| 9 species (range) | 22–46 ms | 0.3–1.4 st | 1.5–4.3 st | 10–30 % | 3–10 ms |
| our D | 29 ms | 1.6 st | 0.8 st | 9 % | 1 ms |
| our G / H | 54 ms | 2.3 / 1.8 st | 3.9 st | 17–19 % | 17 ms |

- A bird's note is short and nearly steady; the melody comes from many short notes moving 2–4 semitones, with
  wide leaps now and then. G and H sing long notes that slide (the drawn curves span half an octave): R2D2.
- Wide spacing between letters is not unbirdlike in itself: thrush and nightingale leap over 7 semitones in
  27–30 % of their notes.
- Version I (`lab/spaced_d.py`, page only): D's own sounds, moved onto H's spaced notes, 0.03 per semitone moved.
  Some letters move far (r −28 st, s −13, h −8).

## Step 14–15 in short: versions J, K, L, the partition (16 Nov, afternoon)

- J (`lab/down_trills.py`), K (`lab/trill_voice.py`), L (`lab/two_note.py`): D with trills, own places + trills,
  two notes per letter. Gab: still robotic; "It's not about the envelope itself. It's the sound itself".
- Spectrograms of L against real birds (`lab/out/robot-vs-birds*.png`): birds repeat one syllable many times
  and their sweeps are big and steep; L hops between flat pitch steps, every note different.
- D on a staff (`lab/out/partition-d.png`): several letters share one note (a o f x on D♯7, g r j on G♯7, m e u
  on B7). The partition (`lab/partition.py`, Gab's rule only: most used pairs and confused letters on opposite
  sides) over three octaves C5–C8, as sound (`lab/partition_voice.py`, test voices `partition3`,
  `partition3-double`, decoder band per voice, `setBand` in `js/birdsong.js`): Gab, "too down ... birds from the
  jungle or monkeys". Bug found by Gab's ear: voice names with digits were refused by the pages (fixed).

## Step 16: keep D's sound, fix the mix-ups in the decoder (`lab/lm_test.py`)

Gab: "the D version was really good". The sound stays; the decoder corrects its own mix-ups with words from the
five-language books (lab/corpus), like a phone keyboard: a decoded word that is not a known word is replaced by
a known word reachable by swapping letters the decoder finds alike (likeness > 0.65 for the voice, decided from
the sounds, not from the test errors). Measured on the real recordings of D (v9), nothing re-recorded:

| | decoder alone | + word check (only alike swaps) | + word check (also one other change) |
|---|---|---|---|
| D, 20 cm | 6.3 % | **2.9 %** | 3.4 % |
| D, 2.5 m | 15.8 % | **6.8 %** | 5.6 % |

- What is left: mix-ups that give another real word (at→ah, bin→zin, tu→hu); a check of word pairs could take
  some of them.
- Letter pairs inside the decoder (log probability of the next letter) made it drop letters: not kept.
- On G far (v11) the word check did not help: its errors were mostly missing letters and real-word swaps.
- Caveat: the presets are common words; names and rare words get no help, and a rare word one alike-swap away
  from a common one could be changed.

## Step 17: a page to draw a letter (`draw.html`, `js/synth.js`, `lab/draw_models.py`, `lab/draw_check.py`)

Gab: "a small drawing application to let me draw the [notes], which are not behaving properly ... a partition with the
letters in the alphabetic order. And then below a place to draw letters ... test them into a context. Which means A
within different words in different language, so then I can feel how it sounds, before we commit to it."

- `lab/draw_models.py` writes D's 26 letters as synthesizer numbers (`birds/draw/models.json`; sung back by
  `lab/synth.py` they match D's sound files, correlation 1.00) and words holding each letter in the five languages
  (`birds/draw/words.json`, from the books).
- `js/synth.js` is `sing` in the browser: same steps, another random wobble. To the decoder its letters match D's
  files at 0.91–1.00.
- `draw.html`: the partition (D's letters in alphabetical order, their note and their pitch line), then for the
  chosen letter a pitch line and a loudness line to draw, sliders (notes, length, silence, drift, overtones), the
  letter heard at once, inside words (with the drawn letters, or D as it is), a quick clean-sound likeness against
  the other letters, export and import. Drawings stay in the browser; the voice is not touched.
- `lab/draw_check.py <exported file>` makes test voice `drawn` (D with the drawn letters) and runs the conflict
  scripts (likeness through a 1 s echo, presets clean and in simulated rooms) for D and for it. A guide; then a
  real test with `?voice=drawn`.
- The page's "Does it clash?" uses the script's measure (each letter heard through a 0.6 s and a 1 s echo, then
  the decoder's comparison), live, with the closest pairs of the whole alphabet.
- Gab drew 25 letters (all but y) over four exports (`birds/draw/mine/`). Version 5 = his version 3 with t moved
  2 semitones down and a new n (two round notes, the second 2 semitones higher, around 3270 Hz, D's hum shape):
  no pair above 0.65 (closest q/x 0.61), presets 0 of 177 wrong clean, 0.6 s and 1 s simulated echo (D: 1, 9, 7).
  Gab: "sounds and feel near perfect". `5-short`: vowels 15 % shorter, consonants at most 150 ms, same clean
  sheet, sentences as long as D's. `lab/draw_spread.py` moves alike letters apart in pitch only (a proposal file).
- Next (Gab): numbers, the most common signs and punctuation, then accents. The nine approved signs are on the
  page as synthesizer numbers fitted from their sounds (likeness to the files 0.78–0.93); against version 5's
  letters 16 pairs are above 0.65 (e/- 0.82, b/' 0.82, a/' 0.78, ,/- 0.76 ...), so the signs need redrawing.
- Signs: Gab redrew the nine over versions 6 to 8; version 9 = his 8 with @ one semitone up and the hyphen
  lengthened to 70 ms (same line, same place): among the 35 sounds no pair above 0.65 (closest #/s, #/@ 0.64;
  the page's own echo gives @/t 0.66, borderline), presets 0 of 177 wrong in the three conditions.
  `lab/draw_spread.py` with `MOVE=".,?!'-:@#"` moves only the signs.
- Numbers stay "# + letter" (1 = a ... 9 = i, 0 = j), a row of digits on the page.
- Accents (Gab: "like the numbers"): the plain letter, then one accent call `*`, then a letter naming the accent by
  its English name: a acute, g grave, c circumflex, d diaeresis (tréma), t tilde, z cedilla. Rejected for the call:
  @, - and ' (they already stand between two letters: "es-tu", "gab@home"). On the Draw page only; Send, Listen
  and the decoders still use one call per accent (14 Nov) and are to be ported once the sound is approved.
- The accent rule is now in the phone code and its twin (`js/birdsong.js`, `lab/decode.py`) for a voice that
  declares it (voice.json `accent_call`: call and codes); other voices keep the 14 Nov rule. After the call the
  decoder accepts only a letter that names an accent. Test voice `v9` = D with version 9's letters and signs and
  the accent call as the page starts it (not redrawn by Gab yet). Ten sentences with punctuation, numbers and
  accents (three new Send presets: ça va très bien, mañana, grüße), sung and decoded: 0 of 267 sounds wrong
  clean, with a simulated 0.6 s and 1 s echo, in Python and in the browser. `lab/real_test_any.py <voice> <folder>`
  scores real recordings with the decoder alone (no word check).
- The opening and closing calls as synthesizer numbers (`birds/draw/frames.json`, 21 and 18 notes, each a model
  like a letter with its start time and level; `frameSound` in `js/synth.js`, `frame_sound` in
  `lab/draw_models.py`). No filter: an overtone that would rise above 9 kHz is left out. Rebuilt in Python they
  are 0.99 alike to the files in the voice; from the browser synthesizer 0.94 and 0.96.
- Everything from numbers, nothing from a file: the ten sentences sung with all 36 sounds and both calls made
  live by the browser synthesizer, decoded by the `v9` decoder: 0 of 267 sounds wrong (clean sound).
- No real test of version 9 yet.

## Handover, end of 16 Nov (for a fresh session)

Where things stand, in Gab's words where possible:
- **D is the reference sound** ("the best version we had so far is the version D"). Test voice `nightingale-d`.
  Every attempt to change the sound today was rejected: G, H ("R2D2"), I ("a robot under the water"), J, K, L,
  the letter-by-letter page ("It's not about the envelope itself. It's the sound itself, which is terrible"), and
  the three-octave partition ("too down ... birds from the jungle or monkeys"). D moved down 5/9/12 semitones was
  heard only after a page bug was fixed (voice names with digits were refused).
- **D's problem is on the staff** (`lab/out/partition-d.png`): several letters share one note (a o f x, g r j,
  m e u, p c, q y, l h), and half the alphabet sits in the harsh top octave. Gab: "That's why it's wrong since
  the beginning."
- **Gab still hears some letters as very bad sounds** (w above all). His proposal: a small interface where he
  draws a simple shape (pitch line, loudness) for a letter and hears it at once, "giving a special feeling".
- **Constraint** (Gab): the receiving device has no room to store sounds, so letters must come from a
  synthesizer; and he wants to hear exactly what the device will produce ("you go straight with the synthesizer,
  then I know what I'm testing and checking is what I will get"). So the drawing tool should synthesize in the
  browser with the same synthesizer the device would run (a JS port of `lab/synth.py` `sing`).
- **Good idea for later, not now** (Gab: "the word fixing is a good idea, but we need first to solve the sound
  problem"): the word check (step 16), 6.3 → 2.9 % at 20 cm and 15.8 → 6.8 % at 2.5 m on the real D recordings.
- **Question Gab asked**: could a small model solve the encoder/decoder problem? Claude's view: a small trained
  decoder (letters from sound pictures, trained on synthesized letters through simulated and real rooms) could
  replace template matching later; it cannot choose the sounds, which is Gab's ear.
- Committed in 77806d9 (branch `musicology`, 16 Nov 17:45): versions H to L, the partition voices, the listening
  pages, the lab scripts of steps 12–16, the per-voice decoder band and the voice-name fix. Left untracked:
  `bird-letter.wav`, `bird-letter (1).wav` and `download/` (four `heard-*.wav` recordings from 13 Nov).
- Real tests still decide; Gab's ear decides the sound.
