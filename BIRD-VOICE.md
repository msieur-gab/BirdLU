# Bird voice: where it stands (13 Nov 2026)

Letters sung as bird song by one device and read back by another, with no network. This file
records the bird voice built on 13 Nov: what exists, what was learned and what is still open. Work
is on branch `echo-tuning` (started from `bird-voice`). `main` holds Claude Web's earlier chirp
alphabet (`send.html`, `listen.html`).

## Pages

| Page | What it does |
|---|---|
| `send-bird.html` | Type a message; the bird voice sings it. Shows the sound picture with letters marked, a clean decode check, and saves WAV. `?voice=<name>` sings with a test voice. |
| `listen-bird.html` | Listens on the phone (needs HTTPS), waits for the opening call, decodes when the closing call is heard. Shows two readings (with and without echo removal), the echo time measured from the opening, and **"Sound lost"**. Saves each message as WAV; decodes uploaded recordings. |
| `sketch.html` | The listening sketch Gab rated "absolutely perfect bird sound": recorded, synthesized and synthesized-brisk versions, in the forest or birds only. |
| `signs.html` | Three candidate bird notes per sign, to choose by ear. |
| `voices.html` | Five consonant variants (13 Nov afternoon). No audible difference to Gab; kept only as a record. |
| `synth.html`, `bird-alphabets.html` | Earlier listening pages (original vs synthesized trills; alphabets A–D). |

Local test setup: `python3 -m http.server 8000` in the repo for the laptop; a self-signed HTTPS
server on port 8443 for the phone (`https://<laptop IP>:8443/listen-bird.html`).

## The voice

- **Every sound is synthesized.** No recording is played. Each letter is rebuilt from tones by
  `lab/synth.py`, from numbers measured on a real recording: pitch line, loudness, trill rhythm and
  overtones. The recordings are Wikimedia Commons / xeno-canto clips, credited in
  `birds/voice/CREDITS.md` (some CC BY-NC-SA: non-commercial).
- **Vowels** (a e i o u y é è) are bird trills (blue tit, nuthatch, wren, chaffinch).
- **Consonants** are short single notes (tits, robin, wren, thrush, blackbird).
- **The opening** is a chiffchaff "chiff-chaff-chiff-chaff". **The closing** is the same call
  reversed, slowing and softening (Gab chose "A").
- **Tempo:** about 25 ms between the letters of a word, 0.32–0.45 s between words.
- **Signs**, chosen by Gab's ear:
  - `.` falling blackbird call, `?` rising yellowhammer call, `!` chiffchaff;
  - `,` a soft song-thrush note, `-` and `@` song-thrush notes;
  - `'` `:` and `#` blackbird notes.
- **Digits** are sung as `#` then a–j (1–9, 0), as in Braille, and shown back as digits.
- **Accents** other than é and è are folded to the plain letter (à → a, ç → c, ü → u, ñ → n). Not
  yet supported: French accents (à â ç ê î ô û ë ï), Spanish ñ and ¿ ¡, German umlauts, and signs
  such as ° € % / ( ).
- The files are in `birds/voice/`. They are made by `lab/export_voice.py`, plus `lab/add_signs.py`
  for the signs.

## The decoder (`js/birdsong.js`, the same code as `lab/decode.py`)

There is no trained model. The decoder is hand-built:

1. **Sound picture.** 48 pitch bands from 1 to 9 kHz, one column every 5 ms. Columns are compared
   by their shape, not their loudness.
2. **Frame calls.** The opening and closing calls are found by sliding their known picture along
   the sound.
3. **Letters.** Between the two calls, a search (dynamic programming) finds the sequence of
   letters, short in-word gaps and word pauses that best explains the picture. Each letter is
   compared with its own picture.
   - A letter must start with a rise in sound (an echo only fades).
   - A repeated letter pays a small cost.
4. **Echo removal.**
   - The opening works as a tuning fork: how fast its echo fades gives the room's echo time.
   - The predicted late echo is then subtracted (Lebart et al. 2001).
   - On real recordings it helps a little (69 → 59 wrong letters on 10 old recordings).
   - The tuning fork misreads Bluetooth recordings (2.5 s instead of about 0.5 s).
5. **Where it runs.** On the phone, sound is recorded on the browser's audio thread (AudioWorklet)
   and decoded in a background thread (Web Worker).

## What 13 Nov taught

1. **The Listen page was losing sound.** Gab's hunch.
   - It recorded the microphone on the same thread that decoded. With that thread busy for 1.5 s,
     1,491 ms of sound was lost; recording on the audio thread loses about 30 ms.
   - Most of the day's "room echo" errors came from this.
   - After the fix, every message was read right at 30 cm and at 2.3 m.
2. **The Send page sounded metallic.** Gab's ear, confirmed by a second listener.
   - The 44.1 kHz voice was played through the browser's buffer player in a 48 kHz system, which
     added out-of-tune tones: a 6 kHz note gained 9.9 kHz (−32 dB) and 2.1 kHz (−37 dB).
   - Send now plays at 44.1 kHz.
   - The notes themselves were identical to the Sketch's (correlation 1.00).
3. **The "R2D2" voice** came from consonants chosen only to be distinct in a room. They were swapped
   in without Gab's ear, to fix errors that were really the broken listener. The original voice
   (commit 7e8df7b) is restored.
4. **Simulated rooms are not evidence.** Their settings were invented and too optimistic. Judge
   changes on Gab's real recordings and his ear.
5. **Reed-Solomon repair letters** fixed simulated rooms but not real errors, which are mostly
   missing or extra letters. Lab code in `lab/repair.py`; not used.
6. **A filter for broadband noise** (talking, knocks) gave no gain and was dropped. The two loud
   bursts in the corridor test were the phone itself vibrating on a notification.

## Real tests (phone listening; `test/recordings-v*`)

| Set | Setup | Voice | Result |
|---|---|---|---|
| v6 | 30 cm laptop speakers; 2.3 m Bluetooth | room-chosen ("R2D2") | 9 of 9 messages perfect |
| v7 | 6–7 m, corridor through a door, people and a smart speaker talking | room-chosen | 2 of 8 perfect, about 7% of letters wrong, all readable |
| v8 | 30 cm, voice restored, with signs | restored + signs | 8 of 12 perfect, 2.6% of letters wrong; every sign and number read |

Earlier sets (v3–v5) were recorded with the defective Listen page.

## Open

- **"arrive" fails:** the second "r" is misread. The "r" is a soft robin note at 4.1 kHz, near
  "p" and "j". "-" and "@" were moved away from it the same evening; the letter results need a
  rerun.
- **Accents and more signs** (French, Spanish, German). This needs a design, for example an
  accent call after the letter, like the number call.
- **The score.** Claude Web's style (`send.html` on `main`): coloured pitch strokes per letter on
  staff bands, letters underneath, a moving playhead, and a tappable alphabet table. Promised to Gab.
- **Check letters** (2–3 extra notes at the end, so that a misread message says "unsure"):
  proposed, not built. This works for any language, with no word lists.
- **Gab's idea: the opening as key signature.** It would carry the tuning fork and the language
  at once.
- **Merge** `echo-tuning` into `bird-voice` once the reruns confirm it.
