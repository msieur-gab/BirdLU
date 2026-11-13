// Chirp alphabet — shared by the sender, the listener and the tests.
// Every letter is one bird-like call defined by four properties:
// pitch band (4), direction (up/down), shape (straight/hook), length (short/long).

export const ORDER = "etaoinsrhldcumfpgwybvkxjqz.,?!'-".split("");
export const BANDS = [2400, 3200, 4000, 4800]; // band centres in Hz (B1..B4)
export const SPAN = 700;                          // sweep width in Hz
export const DUR = { short: 0.070, long: 0.130 }; // seconds
export const GAP = 0.045, PAUSE = 0.200, FRAME_GAP = 0.14;
export const HOOK_AT = 0.72, HOOK_BACK = 0.45;

function makeSym(i) {
  const j = i % 16;
  return {
    ch: ORDER[i], index: i, len: i < 16 ? "short" : "long", band: j >> 2,
    dir: ((j >> 1) & 1) ? "down" : "up", shape: (j & 1) ? "hook" : "straight"
  };
}
export const ALPHA = ORDER.map((_, i) => makeSym(i));
export const BY_CH = Object.fromEntries(ALPHA.map(s => [s.ch, s]));

/** Find the symbol for measured properties. */
export function lookup(band, dir, shape, len) {
  return ALPHA.find(s => s.band === band && s.dir === dir && s.shape === shape && s.len === len) || null;
}

export function symNote(s) {
  const c = BANDS[s.band];
  const f0 = s.dir === "up" ? c - SPAN / 2 : c + SPAN / 2;
  const f1 = s.dir === "up" ? c + SPAN / 2 : c - SPAN / 2;
  return { f0, f1, shape: s.shape, dur: DUR[s.len] };
}

// Frame calls sit outside the letter bands: opening above 5 kHz, closing below 2 kHz.
export const OPEN = [
  { f0: 5600, f1: 6300, shape: "straight", dur: 0.045 }, { gap: 0.035 },
  { f0: 5600, f1: 6300, shape: "straight", dur: 0.045 }, { gap: 0.035 },
  { f0: 6300, f1: 5300, shape: "straight", dur: 0.160 }
];
export const CLOSE = [
  { f0: 1900, f1: 1600, shape: "straight", dur: 0.060 }, { gap: 0.040 },
  { f0: 1800, f1: 1500, shape: "straight", dur: 0.060 }, { gap: 0.040 },
  { f0: 1700, f1: 1400, shape: "straight", dur: 0.090 }
];
export const OPEN_LAST_DUR = 0.160;

/** Frequency of a call at position u (0..1). */
export function sweep(f0, f1, shape, u) {
  if (shape === "hook") {
    if (u < HOOK_AT) { const p = 1 - Math.pow(1 - u / HOOK_AT, 2); return f0 + (f1 - f0) * p; }
    const v = (u - HOOK_AT) / (1 - HOOK_AT);
    return f1 - (f1 - f0) * HOOK_BACK * Math.sin(v * Math.PI / 2);
  }
  return f0 + (f1 - f0) * u;
}

export function envelope(u) { return Math.pow(Math.sin(Math.PI * u), 0.7); }

export function normalize(text) {
  return text.toLowerCase()
    .replace(/ß/g, "ss").replace(/æ/g, "ae").replace(/œ/g, "oe")
    .normalize("NFD").replace(/[̀-ͯ]/g, "")
    .replace(/[’‘`´]/g, "'").replace(/[–—]/g, "-");
}

/** Turn text into a timed list of calls. */
export function build(text, tempo = 1) {
  const events = [], pauses = [], skipped = [];
  let t = 0;
  const push = (n, kind, label) => {
    events.push({ f0: n.f0, f1: n.f1, shape: n.shape, dur: n.dur / tempo, t, kind, label });
    t += n.dur / tempo;
  };
  const frame = (notes, label) => notes.forEach((n, i) => {
    if (n.gap) t += n.gap / tempo; else push(n, "frame", i === 0 ? label : "");
  });

  frame(OPEN, "opening");
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
    push(symNote(s), s.len, s.ch);
  }
  t += FRAME_GAP / tempo;
  frame(CLOSE, "closing");
  return { events, pauses, skipped, letters, total: t, text: sent };
}

/** Pure-JS synthesis (used for simulation and tests). Returns a Float32Array. */
export function renderSamples(sched, sr, pitch = 1, lead = 0.3, tail = 0.5) {
  const out = new Float32Array(Math.ceil((lead + sched.total + tail) * sr));
  for (const e of sched.events) {
    const start = Math.round((lead + e.t) * sr), n = Math.round(e.dur * sr);
    let phase = 0, phase2 = 0;
    for (let i = 0; i < n; i++) {
      const u = i / (n - 1);
      const f = sweep(e.f0, e.f1, e.shape, u) * pitch;
      phase += 2 * Math.PI * f / sr; phase2 += 4 * Math.PI * f / sr;
      out[start + i] += envelope(u) * (Math.sin(phase) + 0.06 * Math.sin(phase2)) * 0.45;
    }
  }
  return out;
}

/** WebAudio player shared by the pages. */
export class Player {
  constructor() { this.ctx = null; this.room = 0.25; }
  ensure() {
    if (this.ctx) return this.ctx;
    const AC = window.AudioContext || window.webkitAudioContext;
    const ctx = this.ctx = new AC();
    this.master = ctx.createGain(); this.master.gain.value = 0.45;
    this.dry = ctx.createGain(); this.wet = ctx.createGain();
    const conv = ctx.createConvolver(); conv.buffer = this.makeIR(1.8);
    const comp = ctx.createDynamicsCompressor();
    this.master.connect(this.dry); this.master.connect(conv); conv.connect(this.wet);
    this.dry.connect(comp); this.wet.connect(comp); comp.connect(ctx.destination);
    this.setRoom(this.room);
    return ctx;
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
  setRoom(r) { this.room = r; if (this.ctx) { this.wet.gain.value = r; this.dry.gain.value = 1 - r * 0.45; } }
  note(dest, n, t0, pitch) {
    const ctx = this.ctx, N = 64, ny = ctx.sampleRate / 2 - 200;
    const fc = new Float32Array(N), fh = new Float32Array(N), env = new Float32Array(N);
    for (let i = 0; i < N; i++) {
      const u = i / (N - 1), f = sweep(n.f0, n.f1, n.shape, u) * pitch;
      fc[i] = f; fh[i] = Math.min(f * 2, ny); env[i] = envelope(u);
    }
    const o = ctx.createOscillator(), o2 = ctx.createOscillator(), g = ctx.createGain(), h = ctx.createGain();
    g.gain.value = 0; h.gain.value = 0.06;
    o.frequency.setValueCurveAtTime(fc, t0, n.dur);
    o2.frequency.setValueCurveAtTime(fh, t0, n.dur);
    g.gain.setValueCurveAtTime(env, t0, n.dur);
    o.connect(g); o2.connect(h); h.connect(g); g.connect(dest);
    o.start(t0); o2.start(t0); o.stop(t0 + n.dur + 0.02); o2.stop(t0 + n.dur + 0.02);
  }
  /** Play a schedule; returns { t0, stop() }. */
  play(sched, pitch = 1) {
    this.ensure(); this.ctx.resume();
    const bus = this.ctx.createGain(); bus.connect(this.master);
    const t0 = this.ctx.currentTime + 0.08;
    sched.events.forEach(e => this.note(bus, e, t0 + e.t, pitch));
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
