// Chirp alphabet v2 — shared by the sender, the listener and the tests.
//
// Consonants are single calls: pitch band (4) × direction (up/down) × texture (sweep/trill) × length (short/long).
// Vowels are their own family: a two-note call ("chi-wee" / "pee-oo"), pitch band × direction.
// The most common letters sit in the middle bands (3.6 and 4.3 kHz), which small speakers carry best.

export const BANDS = [2900, 3600, 4300, 5000]; // band centres in Hz (B1..B4)
export const SPAN = 500;                          // sweep width of a consonant in Hz
export const DUR = {
  sweep: { short: 0.080, long: 0.140 },
  trill: { short: 0.100, long: 0.160 },
  note: 0.045, noteGap: 0.018
};
export const TRILL = { rate: 30, depth: 200 };    // wobble in Hz/s and ±Hz
export const PAIR = { offset: 330, glide: 60 };   // vowel notes sit at centre ± offset
export const GAP = 0.060, PAUSE = 0.220, FRAME_GAP = 0.14;

const CONSONANTS = ["t","n","s","r","h","l","d","c","m","f","p","g","w","b","v","k",".",",","j","x","z","q","?","!","'","-"];
const VOWELS = [["e",1,"up"],["a",2,"up"],["i",1,"down"],["o",2,"down"],["u",0,"up"],["y",3,"up"],["é",0,"down"],["è",3,"down"]];

function consonantSlots() {
  const slots = [];
  for (const len of ["short", "long"])
    for (const texture of ["sweep", "trill"])
      for (const group of [[1, 2], [0, 3]])
        for (const band of group)
          for (const dir of ["up", "down"]) slots.push({ len, texture, band, dir });
  return slots;
}

export const ALPHA = [
  ...VOWELS.map(([ch, band, dir]) => ({ ch, kind: "vowel", texture: "pair", band, dir, len: "short" })),
  ...consonantSlots().slice(0, CONSONANTS.length).map((s, i) => ({ ch: CONSONANTS[i], kind: s.len, ...s }))
];
export const BY_CH = Object.fromEntries(ALPHA.map(s => [s.ch, s]));
export const ORDER = ALPHA.map(s => s.ch);

/** Find the letter for measured properties. */
export function lookup(texture, band, dir, len) {
  return ALPHA.find(s => s.texture === texture && s.band === band && s.dir === dir && (texture === "pair" || s.len === len)) || null;
}

/** The notes that make up a letter (one for consonants, two for vowels). */
export function symbolNotes(s) {
  const c = BANDS[s.band], up = s.dir === "up";
  if (s.texture === "pair") {
    const lo = c - PAIR.offset, hi = c + PAIR.offset, g = PAIR.glide;
    const a = up ? { f0: lo - g, f1: lo + g } : { f0: hi + g, f1: hi - g };
    const b = up ? { f0: hi - g, f1: hi + g } : { f0: lo + g, f1: lo - g };
    return [{ ...a, dur: DUR.note }, { gap: DUR.noteGap }, { ...b, dur: DUR.note }];
  }
  const f0 = up ? c - SPAN / 2 : c + SPAN / 2, f1 = up ? c + SPAN / 2 : c - SPAN / 2;
  return [{ f0, f1, dur: DUR[s.texture][s.len], trill: s.texture === "trill" }];
}
export const symNote = s => symbolNotes(s)[0];

// Frame calls sit outside the letter bands: opening above 5.5 kHz, closing below 2.5 kHz.
export const OPEN = [
  { f0: 5800, f1: 6400, dur: 0.045 }, { gap: 0.035 },
  { f0: 5800, f1: 6400, dur: 0.045 }, { gap: 0.035 },
  { f0: 6400, f1: 5600, dur: 0.160 }
];
export const OPEN_CENTERS = [6100, 6100, 6000];
export const CLOSE = [
  { f0: 2300, f1: 2000, dur: 0.060 }, { gap: 0.040 },
  { f0: 2200, f1: 1900, dur: 0.060 }, { gap: 0.040 },
  { f0: 2100, f1: 1800, dur: 0.090 }
];
export const CLOSE_BELOW = 2500;

/** Frequency of a note at position u (0..1). */
export function freqAt(n, u) {
  const f = n.f0 + (n.f1 - n.f0) * u;
  return n.trill ? f + TRILL.depth * Math.sin(2 * Math.PI * TRILL.rate * u * n.dur) : f;
}
/** Kept for older callers: plain sweep. */
export function sweep(f0, f1, shape, u) { return f0 + (f1 - f0) * u; }

/** Crisp bird-like envelope: ~10 ms attack, ~15 ms release. */
export function envelope(u, dur = 0.1) {
  const t = u * dur, a = Math.min(0.010, dur * 0.25), r = Math.min(0.015, dur * 0.3);
  if (t < a) return Math.pow(Math.sin(Math.PI / 2 * t / a), 2);
  if (t > dur - r) return Math.pow(Math.sin(Math.PI / 2 * Math.max(0, dur - t) / r), 2);
  return 1;
}

export function normalize(text) {
  let out = "";
  for (const ch of text.toLowerCase()) {
    if (ch === "é" || ch === "è") { out += ch; continue; }
    out += ch.replace(/ß/g, "ss").replace(/æ/g, "ae").replace(/œ/g, "oe")
      .normalize("NFD").replace(/[̀-ͯ]/g, "")
      .replace(/[’‘`´]/g, "'").replace(/[–—]/g, "-");
  }
  return out;
}

/** Turn text into a timed list of notes. */
export function build(text, tempo = 1) {
  const events = [], pauses = [], skipped = [];
  let t = 0;
  const push = (n, kind, label, span) => {
    events.push({ f0: n.f0, f1: n.f1, trill: !!n.trill, dur: n.dur / tempo, t, kind, label, span: span ? span / tempo : 0 });
    t += n.dur / tempo;
  };
  const seq = (notes, kind, label) => {
    const span = notes.reduce((a, n) => a + (n.gap || n.dur), 0);
    notes.forEach((n, i) => { if (n.gap) t += n.gap / tempo; else push(n, kind, i === 0 ? label : "", i === 0 ? span : 0); });
  };
  seq(OPEN, "frame", "opening");
  t += FRAME_GAP / tempo;
  let first = true, pendingPause = false, letters = 0, sent = "";
  for (const ch of normalize(text)) {
    if (/\s/.test(ch)) { if (!first) pendingPause = true; continue; }
    const s = BY_CH[ch];
    if (!s) { if (!skipped.includes(ch)) skipped.push(ch); continue; }
    if (!first) {
      if (pendingPause) { pauses.push(t + PAUSE / tempo / 2); t += PAUSE / tempo; sent += " "; }
      else t += GAP / tempo;
    }
    pendingPause = false; first = false; letters++; sent += s.ch;
    seq(symbolNotes(s), s.kind, s.ch);
  }
  t += FRAME_GAP / tempo;
  seq(CLOSE, "frame", "closing");
  return { events, pauses, skipped, letters, total: t, text: sent };
}

/** Pure-JS synthesis (used for simulation and tests). Returns a Float32Array. */
export function renderSamples(sched, sr, pitch = 1, lead = 0.3, tail = 0.5) {
  const out = new Float32Array(Math.ceil((lead + sched.total + tail) * sr));
  for (const e of sched.events) {
    const start = Math.round((lead + e.t) * sr), n = Math.round(e.dur * sr);
    let phase = 0, phase2 = 0;
    for (let i = 0; i < n; i++) {
      const u = i / (n - 1), f = freqAt(e, u) * pitch;
      phase += 2 * Math.PI * f / sr; phase2 += 4 * Math.PI * f / sr;
      out[start + i] += envelope(u, e.dur) * (Math.sin(phase) + 0.06 * Math.sin(phase2)) * 0.45;
    }
  }
  return out;
}

/** WebAudio player shared by the pages. Pass an OfflineAudioContext to render to a file. */
export class Player {
  constructor(ctx = null) { this.ctx = ctx; this.room = 0.25; if (ctx) this.wire(); }
  ensure() {
    if (this.ctx) return this.ctx;
    const AC = window.AudioContext || window.webkitAudioContext;
    this.ctx = new AC();
    this.wire();
    return this.ctx;
  }
  wire() {
    const ctx = this.ctx;
    this.master = ctx.createGain(); this.master.gain.value = 0.45;
    this.dry = ctx.createGain(); this.wet = ctx.createGain();
    const conv = ctx.createConvolver(); conv.buffer = this.makeIR(1.8);
    const comp = ctx.createDynamicsCompressor();
    this.master.connect(this.dry); this.master.connect(conv); conv.connect(this.wet);
    this.dry.connect(comp); this.wet.connect(comp); comp.connect(ctx.destination);
    this.setRoom(this.room);
  }
  makeIR(sec) {
    const ctx = this.ctx, len = Math.floor(ctx.sampleRate * sec);
    const b = ctx.createBuffer(2, len, ctx.sampleRate);
    for (let c = 0; c < 2; c++) {
      const d = b.getChannelData(c);
      for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 3.2) * 0.6;
    }
    return b;
  }
  setRoom(r) { this.room = r; if (this.wet) { this.wet.gain.value = r; this.dry.gain.value = 1 - r * 0.45; } }
  note(dest, n, t0, pitch) {
    const ctx = this.ctx, N = n.trill ? 256 : 96, ny = ctx.sampleRate / 2 - 200;
    const fc = new Float32Array(N), fh = new Float32Array(N), env = new Float32Array(N);
    for (let i = 0; i < N; i++) {
      const u = i / (N - 1), f = freqAt(n, u) * pitch;
      fc[i] = f; fh[i] = Math.min(f * 2, ny); env[i] = envelope(u, n.dur);
    }
    const o = ctx.createOscillator(), o2 = ctx.createOscillator(), g = ctx.createGain(), h = ctx.createGain();
    g.gain.value = 0; h.gain.value = 0.06;
    o.frequency.setValueCurveAtTime(fc, t0, n.dur);
    o2.frequency.setValueCurveAtTime(fh, t0, n.dur);
    g.gain.setValueCurveAtTime(env, t0, n.dur);
    o.connect(g); o2.connect(h); h.connect(g); g.connect(dest);
    o.start(t0); o2.start(t0); o.stop(t0 + n.dur + 0.02); o2.stop(t0 + n.dur + 0.02);
  }
  /** Schedule a whole message from time t0 on a fresh bus; returns the bus. */
  schedule(sched, pitch, t0) {
    const bus = this.ctx.createGain(); bus.connect(this.master);
    sched.events.forEach(e => this.note(bus, e, t0 + e.t, pitch));
    return bus;
  }
  /** Play a schedule; returns { t0, stop() }. */
  play(sched, pitch = 1) {
    this.ensure(); this.ctx.resume();
    const t0 = this.ctx.currentTime + 0.08;
    const bus = this.schedule(sched, pitch, t0);
    return { t0, stop() { try { bus.disconnect(); } catch (e) { /* already stopped */ } } };
  }
  /** Play raw notes (with gaps) once, e.g. a single letter. */
  playNotes(notes, pitch = 1) {
    this.ensure(); this.ctx.resume();
    const bus = this.ctx.createGain(); bus.connect(this.master);
    let t = this.ctx.currentTime + 0.05;
    notes.forEach(n => { if (n.gap) t += n.gap; else { this.note(bus, n, t, pitch); t += n.dur; } });
  }
  now() { return this.ctx ? this.ctx.currentTime : 0; }
}

/** Render a message to samples exactly as it plays (same synth, same room). */
export async function renderOffline(sched, { pitch = 1, room = 0, sampleRate = 44100, lead = 0.5, tail = 0.8 } = {}) {
  const OAC = window.OfflineAudioContext || window.webkitOfflineAudioContext;
  const len = Math.ceil((lead + sched.total + tail + (room > 0 ? 1.8 : 0)) * sampleRate);
  const ctx = new OAC(1, len, sampleRate);
  const p = new Player(ctx);
  p.setRoom(room);
  p.schedule(sched, pitch, lead);
  const buf = await ctx.startRendering();
  return { samples: buf.getChannelData(0), sampleRate };
}

function toInt16(samples) {
  const out = new Int16Array(samples.length);
  for (let i = 0; i < samples.length; i++) { const v = Math.max(-1, Math.min(1, samples[i])); out[i] = v < 0 ? v * 0x8000 : v * 0x7fff; }
  return out;
}

/** 16-bit mono WAV (exact, larger). */
export function encodeWav(samples, sampleRate) {
  const pcm = toInt16(samples), buf = new ArrayBuffer(44 + pcm.length * 2), v = new DataView(buf);
  const str = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  str(0, "RIFF"); v.setUint32(4, 36 + pcm.length * 2, true); str(8, "WAVE");
  str(12, "fmt "); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, sampleRate, true); v.setUint32(28, sampleRate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  str(36, "data"); v.setUint32(40, pcm.length * 2, true);
  new Int16Array(buf, 44).set(pcm);
  return new Blob([buf], { type: "audio/wav" });
}

/** MP3 (smaller, plays everywhere). Needs js/vendor/lame.min.js loaded (global lamejs). */
export function encodeMp3(samples, sampleRate, kbps = 160) {
  const lame = globalThis.lamejs;
  if (!lame || !lame.Mp3Encoder) throw new Error("MP3 encoder not loaded");
  const enc = new lame.Mp3Encoder(1, sampleRate, kbps), pcm = toInt16(samples), parts = [];
  for (let i = 0; i < pcm.length; i += 1152) { const b = enc.encodeBuffer(pcm.subarray(i, i + 1152)); if (b.length) parts.push(b); }
  const end = enc.flush(); if (end.length) parts.push(end);
  return new Blob(parts, { type: "audio/mpeg" });
}
