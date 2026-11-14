// Bird voice v3: the sender (sing) and the listener (Decoder), shared by send-bird.html and
// listen-bird.html. A line-by-line port of lab/decode.py: keep the two in step.
//
// The voice is birds/voice/: one WAV per letter (synthesized from models of real birds) and
// voice.json (timing rules). Sender and listener read the same files.

export const HOP_S = 0.005, WIN_S = 0.0116, NB = 48, F_LO = 1000, F_HI = 9000, FLOOR_DB = 20;

// ---------- voice ----------

/** Read a WAV file (16-bit or 32-bit float PCM) exactly, first channel. The browser's own decoder
 *  alters samples slightly, which the decoder notices. Returns null for other formats. */
export function parseWav(ab) {
  const dv = new DataView(ab);
  const tag = o => String.fromCharCode(dv.getUint8(o), dv.getUint8(o + 1), dv.getUint8(o + 2), dv.getUint8(o + 3));
  if (ab.byteLength < 44 || tag(0) !== "RIFF" || tag(8) !== "WAVE") return null;
  let o = 12, fmt = null;
  while (o + 8 <= ab.byteLength) {
    const id = tag(o), size = dv.getUint32(o + 4, true), body = o + 8;
    if (id === "fmt ") fmt = { code: dv.getUint16(body, true), ch: dv.getUint16(body + 2, true), sr: dv.getUint32(body + 4, true), bits: dv.getUint16(body + 14, true) };
    if (id === "data" && fmt) {
      const bytes = fmt.bits / 8, n = Math.floor(Math.min(size, ab.byteLength - body) / (bytes * fmt.ch)), x = new Float32Array(n);
      const code = fmt.code === 0xFFFE ? (fmt.bits === 32 ? 3 : 1) : fmt.code;
      for (let i = 0; i < n; i++) {
        const p = body + i * bytes * fmt.ch;
        if (code === 1 && fmt.bits === 16) x[i] = dv.getInt16(p, true) / 32768;
        else if (code === 3 && fmt.bits === 32) x[i] = dv.getFloat32(p, true);
        else return null;
      }
      return { x, sr: fmt.sr };
    }
    o = body + size + (size & 1);
  }
  return null;
}

// Accents, one rule for every letter (Gab, 14 Nov): an accented letter is sung as its plain letter, then
// a short accent call (é = e + ´, ñ = n + ~, ç = c + ¸). If the call is lost, the letter is still there.
export const ACCENTS = { "\u0301": "´", "\u0300": "`", "\u0302": "^", "\u0308": "¨", "\u0303": "~", "\u0327": "¸" };
const MARKS = Object.fromEntries(Object.entries(ACCENTS).map(([k, v]) => [v, k]));

/** Decoded text as people write it: "#c" back to "3", "e´" back to "é". */
export const readable = text => [...text.replace(/#([a-j])/g, (_, c) => String(DIGITS.indexOf(c)))]
  .map(c => MARKS[c] || c).join("").normalize("NFC");

export async function loadVoice(base = "birds/voice/", v = "6") {
  const voice = await (await fetch(`${base}voice.json?v=${v}`)).json();
  const sr = voice.sample_rate;
  const snd = {};
  const load = async (key, file) => {
    const ab = await (await fetch(`${base}${file}?v=${v}`)).arrayBuffer();
    snd[key] = parseWav(ab).x;
  };
  await Promise.all([
    ...Object.entries(voice.letters).map(([ch, d]) => load(ch, d.file)),
    ...Object.entries(voice.frames).map(([k, d]) => load(k, d.file)),
  ]);
  return { voice, snd, sr };
}

// a digit is sung as the number call "#" then a letter (0 → j, 1 → a … 9 → i), as in Braille
export const DIGITS = "jabcdefghi";

export function normalize(text) {
  let out = "";
  for (const ch of text.toLowerCase().replace(/ß/g, "ss").replace(/æ/g, "ae").replace(/œ/g, "oe")) {
    if (MARKS[ch]) continue;          // a mark typed on its own is not a letter's accent: not sung
    if (ch >= "0" && ch <= "9") { out += "#" + DIGITS[+ch]; continue; }
    for (const c of ch.normalize("NFD")) {
      if (!/[\u0300-\u036f]/.test(c)) out += c;
      else if (ACCENTS[c]) out += ACCENTS[c];
    }
  }
  return out;
}

function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function openingParts(voice, snd) {
  const T = voice.timing, sr = voice.sample_rate, parts = [];
  let t = 0;
  T.open_pattern.forEach((name, k) => {
    parts.push({ t, x: snd[name], g: 1 });
    t = k < T.open_pattern.length - 1 ? (k + 1) * T.open_period : t + snd[name].length / sr;
  });
  return { parts, dur: t };
}

function closingParts(voice, snd) {
  const sr = voice.sample_rate, parts = [];
  let t = 0;
  for (const c of voice.timing.close_pattern) {
    parts.push({ t, x: snd[c.note], g: c.level });
    t += snd[c.note].length / sr + c.gap;
  }
  return { parts, dur: t };
}

function mix(parts, n, sr) {
  const y = new Float32Array(n);
  for (const { t, x, g } of parts) {
    const o = Math.round(t * sr);
    for (let i = 0; i < x.length && o + i < n; i++) y[o + i] += x[i] * g;
  }
  return y;
}

/** The message as the sender sings it: samples, the text actually sung, and the timeline. */
export function sing(text, { voice, snd, sr }, seed = 1) {
  const R = rng(seed), T = voice.timing, between = (a, b) => a + (b - a) * R();
  const words = normalize(text).split(/\s+/).map(w => [...w].filter(c => voice.letters[c])).filter(w => w.length);
  const parts = [], marks = [];
  let t = T.lead;
  const op = openingParts(voice, snd);
  op.parts.forEach(p => parts.push({ ...p, t: t + p.t }));
  marks.push({ frame: "opening", t0: t, t1: t + op.dur });
  t += op.dur + T.after_open;
  words.forEach((w, wi) => {
    w.forEach((c, ci) => {
      const g = Math.pow(10, (R() * 2 - 1) * T.level_jitter_db / 20);
      parts.push({ t, x: snd[c], g });
      marks.push({ letter: c, t0: t, t1: t + snd[c].length / sr, vowel: voice.letters[c].vowel });
      t += snd[c].length / sr;
      if (ci < w.length - 1) t += T.gap_in_word * between(...T.gap_jitter);
    });
    if (wi < words.length - 1) t += between(...T.word_gap);
  });
  t += T.before_close;
  const cl = closingParts(voice, snd);
  cl.parts.forEach(p => parts.push({ ...p, t: t + p.t }));
  marks.push({ frame: "closing", t0: t, t1: t + cl.dur });
  t += cl.dur + 0.5;
  const y = mix(parts, Math.ceil(t * sr), sr);
  let peak = 0; for (const v of y) peak = Math.max(peak, Math.abs(v));
  if (peak) for (let i = 0; i < y.length; i++) y[i] *= 0.9 / peak;
  return { samples: y, sung: words.map(w => w.join("")).join(" "), marks, dur: t };
}

// ---------- features ----------

function fftPower(re, im) {
  // in-place radix-2 FFT; returns |X|^2 for bins 0..n/2
  const n = re.length;
  for (let i = 1, j = 0; i < n; i++) {
    let bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) { [re[i], re[j]] = [re[j], re[i]]; [im[i], im[j]] = [im[j], im[i]]; }
  }
  for (let len = 2; len <= n; len <<= 1) {
    const ang = -2 * Math.PI / len, wr = Math.cos(ang), wi = Math.sin(ang);
    for (let i = 0; i < n; i += len) {
      let cr = 1, ci = 0;
      for (let k = 0; k < len / 2; k++) {
        const a = i + k, b = a + len / 2;
        const xr = re[b] * cr - im[b] * ci, xi = re[b] * ci + im[b] * cr;
        re[b] = re[a] - xr; im[b] = im[a] - xi; re[a] += xr; im[a] += xi;
        const ncr = cr * wr - ci * wi; ci = cr * wi + ci * wr; cr = ncr;
      }
    }
  }
  const p = new Float64Array(n / 2 + 1);
  for (let k = 0; k <= n / 2; k++) p[k] = re[k] * re[k] + im[k] * im[k];
  return p;
}

/** Band levels in dB: db[b * T + t] (NB bands × T frames), and the frame level in dB. */
// rounds as Python does (half to even): at 44.1 kHz a 5 ms hop is 220.5 samples → 220
const roundEven = v => { const f = Math.floor(v), d = v - f; return d > 0.5 + 1e-9 ? f + 1 : d < 0.5 - 1e-9 ? f : (f % 2 === 0 ? f : f + 1); };

export function features(x, sr) {
  const hop = roundEven(sr * HOP_S), win = roundEven(sr * WIN_S);
  let nfft = 1; while (nfft < win) nfft <<= 1;
  const T = 1 + Math.max(0, Math.floor((x.length - win) / hop));
  const w = new Float64Array(win);
  for (let i = 0; i < win; i++) w[i] = 0.5 - 0.5 * Math.cos(2 * Math.PI * i / (win - 1));
  const edges = [];
  for (let i = 0; i <= NB; i++) edges.push(F_LO * Math.pow(F_HI / F_LO, i / NB));
  const bandOf = new Int16Array(nfft / 2 + 1).fill(-1);
  for (let k = 0; k <= nfft / 2; k++) {
    const f = k * sr / nfft;
    for (let b = 0; b < NB; b++) if (f >= edges[b] && f < edges[b + 1]) { bandOf[k] = b; break; }
  }
  const db = new Float32Array(NB * T), level = new Float32Array(T);
  const re = new Float64Array(nfft), im = new Float64Array(nfft), B = new Float64Array(NB);
  for (let t = 0; t < T; t++) {
    re.fill(0); im.fill(0);
    const o = t * hop;
    for (let i = 0; i < win; i++) re[i] = x[o + i] * w[i];
    const p = fftPower(re, im);
    B.fill(0);
    for (let k = 0; k <= nfft / 2; k++) if (bandOf[k] >= 0) B[bandOf[k]] += p[k];
    let sum = 0;
    for (let b = 0; b < NB; b++) { db[b * T + t] = 10 * Math.log10(B[b] + 1e-12); sum += B[b]; }
    level[t] = 10 * Math.log10(sum + 1e-12);
  }
  return { db, level, T };
}

/** Each column: within 20 dB of its peak, minus its mean, unit length. */
export function shape(db, T) {
  const S = new Float32Array(NB * T);
  for (let t = 0; t < T; t++) {
    let mx = -Infinity;
    for (let b = 0; b < NB; b++) mx = Math.max(mx, db[b * T + t]);
    let mean = 0;
    for (let b = 0; b < NB; b++) mean += Math.max(db[b * T + t], mx - FLOOR_DB);
    mean /= NB;
    let norm = 0;
    for (let b = 0; b < NB; b++) { const z = Math.max(db[b * T + t], mx - FLOOR_DB) - mean; S[b * T + t] = z; norm += z * z; }
    norm = Math.sqrt(norm) + 1e-9;
    for (let b = 0; b < NB; b++) S[b * T + t] /= norm;
  }
  return S;
}

export function template(x, sr) {
  const { db, level, T } = features(x, sr);
  let mx = -Infinity; for (const v of level) mx = Math.max(mx, v);
  let a = 0, b = T - 1;
  while (a < T && level[a] <= mx - 30) a++;
  while (b > a && level[b] <= mx - 30) b--;
  const n = b - a + 1;
  const sub = new Float32Array(NB * n);
  for (let bb = 0; bb < NB; bb++) for (let k = 0; k < n; k++) sub[bb * n + k] = db[bb * T + a + k];
  const weight = new Float32Array(n);
  let ws = 0;
  for (let k = 0; k < n; k++) { weight[k] = Math.min(1, Math.max(0, (level[a + k] - (mx - 30)) / 30)); ws += weight[k]; }
  for (let k = 0; k < n; k++) weight[k] /= ws;
  const first = new Float32Array(NB);
  let fmax = -Infinity;
  for (let bb = 0; bb < NB; bb++) {
    let m = -Infinity;
    for (let k = 0; k < Math.min(4, n); k++) m = Math.max(m, sub[bb * n + k]);
    first[bb] = m; fmax = Math.max(fmax, m);
  }
  const start = new Float32Array(NB);
  let ss = 0;
  for (let bb = 0; bb < NB; bb++) { start[bb] = Math.max(0, first[bb] - (fmax - 15)); ss += start[bb]; }
  for (let bb = 0; bb < NB; bb++) start[bb] /= ss + 1e-9;
  return { shape: shape(sub, n), weight, n, start };
}

/** Weighted cosine of the template slid along S: one score per start frame. */
export function match(S, T, tpl, from = 0, to = T) {
  const n = tpl.n, len = to - from, out = new Float32Array(len).fill(-1);
  if (len < n) return out;
  const m = len - n + 1, acc = new Float32Array(m);
  for (let k = 0; k < n; k++) {
    const w = tpl.weight[k];
    if (w <= 0) continue;
    for (let b = 0; b < NB; b++) {
      const tv = tpl.shape[b * n + k] * w;
      if (tv === 0) continue;
      const row = b * T + from + k;
      for (let s = 0; s < m; s++) acc[s] += tv * S[row + s];
    }
  }
  out.set(acc);
  return out;
}

/** Per band and frame: how much sound newly rises above the band's last 30 ms, in dB. */
function rises(db, T, from, to, look = 6) {
  const len = to - from, R = new Float32Array(NB * len);
  for (let b = 0; b < NB; b++) {
    for (let t = look; t < len; t++) {
      let prev = -Infinity;
      for (let k = 1; k <= look; k++) prev = Math.max(prev, db[b * T + from + t - k]);
      R[b * len + t] = Math.min(30, Math.max(0, db[b * T + from + t] - prev));
    }
  }
  return R;
}

// ---------- the opening as a tuning fork, and the echo taken away ----------

/** From the clean opening's picture: its frames trimmed as the template is, and which are loud. */
function openingReference(x, sr) {
  const { db, level, T } = features(x, sr);
  let mx = -Infinity; for (const v of level) mx = Math.max(mx, v);
  let a = 0, b = T - 1;
  while (a < T && level[a] <= mx - 30) a++;
  while (b > a && level[b] <= mx - 30) b--;
  const n = b - a + 1, sub = new Float32Array(NB * n), loud = new Uint8Array(n);
  let lmx = -Infinity; for (let k = 0; k < n; k++) lmx = Math.max(lmx, level[a + k]);
  for (let k = 0; k < n; k++) loud[k] = level[a + k] > lmx - 30 ? 1 : 0;
  for (let bb = 0; bb < NB; bb++) for (let k = 0; k < n; k++) sub[bb * n + k] = db[bb * T + a + k];
  return { db: sub, n, loud };
}

function percentile(arr, q) {
  const s = Float64Array.from(arr).sort(), i = q / 100 * (s.length - 1), lo = Math.floor(i), hi = Math.ceil(i);
  return s[lo] + (s[hi] - s[lo]) * (i - lo);
}

/** The room's reverberation time (s), from how the echo fades in the opening's silences. */
export function estimateRt60(db, T, start, ref, afterS = 0.15) {
  const n = ref.n, after = Math.floor(afterS / HOP_S), L = n + after;
  const floor = new Float64Array(NB);
  for (let b = 0; b < NB; b++) floor[b] = percentile(db.subarray(b * T, (b + 1) * T), 10);
  const top = new Float64Array(NB);
  let tmx = -Infinity;
  for (let b = 0; b < NB; b++) { let m = -Infinity; for (let k = 0; k < n; k++) m = Math.max(m, ref.db[b * n + k]); top[b] = m; tmx = Math.max(tmx, m); }
  const bands = [];
  for (let b = 0; b < NB; b++) if (top[b] > tmx - 15) bands.push(b);
  let num = 0, den = 0, count = 0, last = null, seg = [];
  const close = () => {
    if (seg.length < 4) return;
    for (const b of bands) {
      const ts = [], hs = [];
      for (const [tau, k] of seg) { const h = db[b * T + start + k]; if (h > floor[b] + 6) { ts.push(tau * HOP_S); hs.push(h); } }
      if (ts.length < 4) continue;
      let mt = 0, mh = 0; for (let i = 0; i < ts.length; i++) { mt += ts[i]; mh += hs[i]; }
      mt /= ts.length; mh /= ts.length;
      for (let i = 0; i < ts.length; i++) { num += (ts[i] - mt) * (hs[i] - mh); den += (ts[i] - mt) ** 2; }
      count += ts.length;
    }
  };
  for (let k = 0; k < Math.min(L, T - start); k++) {
    if (k < n && ref.loud[k]) { close(); seg = []; last = k; continue; }
    if (last === null) continue;
    const tau = k - last;
    if (tau >= 4 && tau <= 24) seg.push([tau, k]);
  }
  close();
  if (count < 20 || den === 0) return null;
  const slope = num / den;
  if (slope >= -1) return 2.5;
  return Math.min(2.5, Math.max(0.1, -60 / slope));
}

/** Take the late echo out of a picture (Lebart et al. 2001): the echo now is what was heard
 *  delayS ago, faded at the room's rate; it is subtracted, down to floorDb below. */
export function dereverb(db, T, rt60, delayS = 0.03, floorDb = 15) {
  const d = Math.round(delayS / HOP_S), fade = Math.exp(-2 * (3 * Math.log(10) / rt60) * delayS);
  const g0 = Math.pow(10, -floorDb / 10), out = new Float32Array(NB * T);
  for (let b = 0; b < NB; b++) for (let t = 0; t < T; t++) {
    const P = Math.pow(10, db[b * T + t] / 10);
    const R = t >= d ? Math.pow(10, db[b * T + t - d] / 10) * fade : 0;
    const G = Math.max(Math.min(1, Math.max(0, 1 - R / (P + 1e-20))), g0);
    out[b * T + t] = 10 * Math.log10(P * G + 1e-12);
  }
  return out;
}

// ---------- decoder ----------

export class Decoder {
  constructor({ voice, snd, sr }) {
    this.voice = voice;
    this.letters = Object.keys(voice.letters);
    // an accent call can only follow a plain letter (not a word start, a sign or another accent)
    this.accents = new Set(this.letters.filter(c => voice.letters[c].accent));
    this.bases = new Set(this.letters.filter(c => !voice.letters[c].accent && !voice.letters[c].sign));
    this.tpl = {};
    for (const c of this.letters) this.tpl[c] = template(snd[c], sr);
    const op = openingParts(voice, snd), cl = closingParts(voice, snd);
    this.tplOpen = template(mix(op.parts, Math.ceil((op.dur + 0.05) * sr), sr), sr);
    this.tplClose = template(mix(cl.parts, Math.ceil((cl.dur + 0.05) * sr), sr), sr);
    this.openDur = op.dur; this.closeDur = cl.dur;
    this.openRef = openingReference(mix(op.parts, Math.ceil((op.dur + 0.05) * sr), sr), sr);
  }

  /** Where the best opening and closing calls are in a stretch of sound (for live listening). */
  findFrames(x, sr) {
    const { db, T } = features(x, sr);
    const S = shape(db, T);
    const mo = match(S, T, this.tplOpen);
    let o = 0; for (let i = 1; i < mo.length; i++) if (mo[i] > mo[o]) o = i;
    const openEnd = o + this.tplOpen.n, fps = 1 / HOP_S;
    let c = -1, cs = -1;
    if (openEnd + 0.3 * fps < T) {
      const mc = match(S, T, this.tplClose);
      for (let i = Math.round(openEnd + 0.3 * fps); i < mc.length; i++) if (mc[i] > cs) { cs = mc[i]; c = i; }
    }
    return { open: o * HOP_S, openScore: mo[o], close: c >= 0 ? c * HOP_S : null, closeScore: cs,
             closeEnd: c >= 0 ? (c + this.tplClose.n) * HOP_S : null };
  }

  decode(x, sr, { biasRatio = 0.72, letterCost = 4.0, newCost = 0.5, onsetGain = 10.0, onsetFullDb = 8.0, repeatCost = 3.0,
                 echo = true, echoDelay = 0.03, echoFloor = 15 } = {}) {
    const { db, level, T } = features(x, sr);
    let S = shape(db, T);
    const fps = 1 / HOP_S, Tm = this.voice.timing;
    const mo = match(S, T, this.tplOpen);
    let o = 0; for (let i = 1; i < mo.length; i++) if (mo[i] > mo[o]) o = i;
    const openEnd = o + this.tplOpen.n;
    const mc = match(S, T, this.tplClose);
    let c = -1, cs = -Infinity;
    for (let i = openEnd + Math.round(0.3 * fps); i < mc.length; i++) if (mc[i] > cs) { cs = mc[i]; c = i; }
    const info = { open: o * HOP_S, openScore: mo[o], close: c * HOP_S, closeScore: cs };
    if (c < 0 || c - openEnd < 10) return { text: "", info };
    const bias = biasRatio * mo[o];
    // the opening as a tuning fork: how long this room's echo lasts; then the echo is taken out of
    // the picture the letters are read from (onsets still come from the sound as heard)
    info.rt60 = estimateRt60(db, T, o, this.openRef);
    if (echo && info.rt60) S = shape(dereverb(db, T, info.rt60, echoDelay, echoFloor), T);
    const lo = openEnd, hi = c, Tn = hi - lo;
    const Sseg = new Float32Array(NB * Tn);
    for (let b = 0; b < NB; b++) Sseg.set(S.subarray(b * T + lo, b * T + hi), b * Tn);
    const Rraw = rises(db, T, lo, hi);
    // a letter should start where sound rises in its own bands (±10 ms)
    const R = new Float32Array(NB * Tn);
    for (let b = 0; b < NB; b++) for (let t = 0; t < Tn; t++) {
      let m = 0;
      for (const k of [-2, -1, 0, 1]) { const tt = (t - k + Tn) % Tn; m = Math.max(m, Rraw[b * Tn + tt]); }
      R[b * Tn + t] = m;
    }
    // leaving NEW sound unexplained costs; an echo is old sound, free
    const loudCum = new Float64Array(Tn + 1);
    for (let t = 0; t < Tn; t++) {
      let m = 0; for (let b = 0; b < NB; b++) m = Math.max(m, Rraw[b * Tn + t]);
      loudCum[t + 1] = loudCum[t] + (m >= 8 ? newCost : 0);
    }
    const place = {};
    for (const ch of this.letters) {
      const tp = this.tpl[ch], m = match(Sseg, Tn, tp), p = new Float32Array(Tn);
      for (let t = 0; t < Tn; t++) {
        let rise = 0; for (let b = 0; b < NB; b++) rise += tp.start[b] * R[b * Tn + t];
        const bonus = onsetGain * (Math.min(rise, onsetFullDb) / onsetFullDb - 0.5);
        p[t] = (m[t] - bias) * tp.n - letterCost + bonus;
      }
      place[ch] = p;
    }
    const gIn = Math.round(Tm.gap_in_word * Tm.gap_jitter[1] * fps) + 3;
    const wLo = Math.floor(Tm.word_gap[0] * 0.6 * fps), wHi = Math.floor(Tm.word_gap[1] * 1.6 * fps);
    const leadMax = Math.floor((Tm.after_open + 0.4) * fps);
    const NEG = -1e9;
    const A = Array.from({ length: Tn + 1 }, () => []);
    const W = new Float64Array(Tn + 1).fill(NEG), backW = new Array(Tn + 1).fill(null);
    for (let t = Math.floor(Tm.after_open * 0.55 * fps); t <= Math.min(leadMax, Tn); t++) W[t] = 0;
    const push = (lst, score, ch, back) => {
      for (const e of lst) if (e[1] === ch) { if (score > e[0]) { e[0] = score; e[2] = back; lst.sort((a, b) => b[0] - a[0]); } return; }
      lst.push([score, ch, back]); lst.sort((a, b) => b[0] - a[0]); if (lst.length > 2) lst.length = 2;
    };
    for (let t = 0; t <= Tn; t++) {
      if (t >= wLo) {
        for (let s = Math.max(0, t - wHi); s <= t - wLo; s++) {
          if (A[s].length) {
            const sc = A[s][0][0] - (loudCum[t] - loudCum[s]);
            if (sc > W[t]) { W[t] = sc; backW[t] = [s, 0]; }
          }
        }
      }
      const preds = [];
      if (W[t] > NEG / 2) preds.push([W[t], null, ["W", t]]);
      for (let s = Math.max(0, t - gIn); s <= t; s++) {
        A[s].forEach((e, k) => push(preds, e[0] - (loudCum[t] - loudCum[s]), e[1], ["A", s, k]));
      }
      if (!preds.length) continue;
      for (const ch of this.letters) {
        const e = t + this.tpl[ch].n;
        if (e > Tn) continue;
        let best = NEG, prev = null;
        const acc = this.accents.has(ch);
        for (const [sc, lc, p] of preds) {
          if (acc && !this.bases.has(lc)) continue;
          const sc2 = lc === ch ? sc - repeatCost : sc;
          if (sc2 > best) { best = sc2; prev = p; }
        }
        if (prev === null) continue;
        push(A[e], best + place[ch][t], ch, [t, prev]);
      }
    }
    const endLo = Math.max(0, Tn - Math.floor((Tm.before_close + 0.4) * fps));
    const endHi = Math.max(endLo + 1, Tn - Math.floor(Tm.before_close * 0.4 * fps));
    let e = -1, eb = NEG;
    for (let t = endLo; t <= Math.min(endHi, Tn); t++) if (A[t].length && A[t][0][0] > eb) { eb = A[t][0][0]; e = t; }
    if (e < 0) return { text: "", info };
    const out = [];
    let t = e, k = 0;
    for (;;) {
      const [, ch, [, prev]] = A[t][k];
      out.push(ch);
      if (prev[0] === "W") {
        const bw = backW[prev[1]];
        if (!bw) break;
        out.push(" ");
        [t, k] = bw;
      } else { t = prev[1]; k = prev[2]; }
    }
    info.bias = bias;
    return { text: out.reverse().join("").trim(), info };
  }
}

// ---------- helpers ----------

export function encodeWav(samples, sr) {
  const n = samples.length, buf = new ArrayBuffer(44 + n * 2), v = new DataView(buf);
  const str = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  str(0, "RIFF"); v.setUint32(4, 36 + n * 2, true); str(8, "WAVE"); str(12, "fmt ");
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, sr, true); v.setUint32(28, sr * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  str(36, "data"); v.setUint32(40, n * 2, true);
  for (let i = 0; i < n; i++) v.setInt16(44 + i * 2, Math.max(-1, Math.min(1, samples[i])) * 32767, true);
  return new Blob([buf], { type: "audio/wav" });
}

/** Draw a sound picture of samples on a canvas (pitch up, time right), with optional marks. */
export function drawPicture(canvas, samples, sr, marks = [], pps = 140) {
  const { db, T } = features(samples, sr);
  const W = Math.max(1, Math.round(T * HOP_S * pps)), H = 200, dpr = window.devicePixelRatio || 1;
  canvas.width = W * dpr; canvas.height = H * dpr; canvas.style.width = W + "px"; canvas.style.height = H + "px";
  const c = canvas.getContext("2d"); c.setTransform(dpr, 0, 0, dpr, 0, 0);
  let mx = -Infinity; for (const v of db) mx = Math.max(mx, v);
  const img = c.createImageData(T, NB);
  for (let b = 0; b < NB; b++) for (let t = 0; t < T; t++) {
    const v = Math.max(0, Math.min(1, (db[b * T + t] - (mx - 55)) / 55));
    const i = ((NB - 1 - b) * T + t) * 4, g = 255 - Math.round(v * 235);
    img.data[i] = g; img.data[i + 1] = g; img.data[i + 2] = g; img.data[i + 3] = 255;
  }
  const off = document.createElement("canvas"); off.width = T; off.height = NB;
  off.getContext("2d").putImageData(img, 0, 0);
  c.imageSmoothingEnabled = true;
  c.fillStyle = "#fff"; c.fillRect(0, 0, W, H);
  c.drawImage(off, 0, 0, W, H - 30);
  c.font = "600 13px 'IBM Plex Mono', monospace"; c.textAlign = "center";
  for (const m of marks) {
    const x0 = m.t0 * pps, x1 = m.t1 * pps;
    c.fillStyle = m.frame ? "#7a6a8f" : m.vowel ? "#a8456a" : "#1f6f8b";
    c.fillRect(x0, H - 8, Math.max(2, x1 - x0 - 1), 5);
    if (m.letter) c.fillText(m.letter, (x0 + x1) / 2, H - 13);
    else { c.font = "italic 11px sans-serif"; c.textAlign = "left"; c.fillText(m.frame, x0, H - 13); c.font = "600 13px 'IBM Plex Mono', monospace"; c.textAlign = "center"; }
  }
  return { W, pps };
}
