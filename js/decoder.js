// Chirp decoder — rule-based, runs in the browser (and in Node for tests).
// 1. Track the dominant pitch every few milliseconds (FFT peak).
// 2. Cut the track into calls at silences, loudness dips and pitch jumps.
// 3. Wait for the opening call; use it to calibrate pitch and tempo.
// 4. Measure band, direction, shape and length of each call and look up its letter.
// 5. Stop at the low closing trill (or after a long silence).

import { BANDS, SPAN, lookup } from "./chirp.js";

const OPEN_CENTERS = [5950, 5950, 5800];
const F_LO = 1200, F_HI = 7400;

function fft(re, im) {
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
        const tr = re[b] * cr - im[b] * ci, ti = re[b] * ci + im[b] * cr;
        re[b] = re[a] - tr; im[b] = im[a] - ti; re[a] += tr; im[a] += ti;
        const ncr = cr * wr - ci * wi; ci = cr * wi + ci * wr; cr = ncr;
      }
    }
  }
}

export class Decoder {
  constructor(sampleRate, opts = {}) {
    this.sr = sampleRate;
    this.N = sampleRate > 60000 ? 1024 : 512;
    this.hop = this.N / 4;
    this.dt = this.hop / sampleRate;
    this.win = new Float64Array(this.N).map((_, i) => 0.5 - 0.5 * Math.cos(2 * Math.PI * i / (this.N - 1)));
    this.re = new Float64Array(this.N); this.im = new Float64Array(this.N);
    this.kLo = Math.floor(F_LO * this.N / sampleRate);
    this.kHi = Math.ceil(F_HI * this.N / sampleRate);
    this.power = new Float64Array(this.kHi - this.kLo + 1);
    this.buf = new Float32Array(this.N * 8); this.bufLen = 0;
    this.frameIndex = 0;
    this.snrOn = opts.snrOn ?? 12;
    this.dip = opts.dip ?? 9;
    this.on = Object.assign({ state() {}, letter() {}, message() {}, segment() {}, frame() {} }, opts.on || {});
    this.reset();
  }

  reset() {
    this.seg = null; this.inactive = 0; this.levelRef = -200; this.levelRefT = 0;
    this.history = []; this.state = "idle"; this.cal = null; this.text = ""; this.letters = [];
    this.lastEnd = null;
  }

  get frequencies() { // bin centre frequencies of the spectrum passed to on.frame
    return Array.from(this.power, (_, i) => (this.kLo + i) * this.sr / this.N);
  }

  push(samples) {
    if (this.bufLen + samples.length > this.buf.length) {
      const nb = new Float32Array(Math.max(this.buf.length * 2, this.bufLen + samples.length));
      nb.set(this.buf.subarray(0, this.bufLen)); this.buf = nb;
    }
    this.buf.set(samples, this.bufLen); this.bufLen += samples.length;
    let pos = 0;
    while (this.bufLen - pos >= this.N) { this.frame(this.buf.subarray(pos, pos + this.N)); pos += this.hop; }
    this.buf.copyWithin(0, pos, this.bufLen); this.bufLen -= pos;
  }

  frame(x) {
    const { N, re, im, win, power, kLo } = this;
    for (let i = 0; i < N; i++) { re[i] = x[i] * win[i]; im[i] = 0; }
    fft(re, im);
    let kMax = 0, pMax = 0;
    for (let i = 0; i < power.length; i++) {
      const k = kLo + i, p = re[k] * re[k] + im[k] * im[k];
      power[i] = p; if (p > pMax) { pMax = p; kMax = i; }
    }
    const sorted = Float64Array.from(power).sort();
    const floor = sorted[sorted.length >> 1] + 1e-12;
    const eps = 1e-12;
    // parabolic interpolation on log power
    let delta = 0;
    if (kMax > 0 && kMax < power.length - 1) {
      const a = Math.log(power[kMax - 1] + eps), b = Math.log(power[kMax] + eps), c = Math.log(power[kMax + 1] + eps);
      const d = a - 2 * b + c; if (d < 0) delta = 0.5 * (a - c) / d;
    }
    const f = (kLo + kMax + delta) * this.sr / N;
    const db = 10 * Math.log10(pMax + eps), snr = db - 10 * Math.log10(floor);
    const t = (this.frameIndex++ * this.hop + N / 2) / this.sr;

    // level reference decays 15 dB/s so quieter senders are still heard later
    const ref = this.levelRef - 15 * (t - this.levelRefT);
    let active = snr > this.snrOn && db > ref - 14 && pMax > 1e-9;
    if (this.seg && db < this.seg.maxDb - this.dip) active = false; // loudness dip ends a call (echo tails)
    this.on.frame({ t, f, db, snr, active, power });
    this.track(t, f, db, active);
  }

  track(t, f, db, active) {
    const s = this.seg;
    if (active) {
      if (s && Math.abs(f - s.frames[s.frames.length - 1].f) > 450) { this.close(); }
      if (!this.seg) this.seg = { frames: [], maxDb: -200 };
      this.seg.frames.push({ t, f, db });
      if (db > this.seg.maxDb) this.seg.maxDb = db;
      this.inactive = 0;
    } else if (s) {
      if (++this.inactive >= 2) this.close();
    }
    if (this.state === "receiving" && !this.seg && this.lastEnd !== null && t - this.lastEnd > 7 * this.cal.d3) {
      this.finish(false);
    }
  }

  close() {
    const s = this.seg; this.seg = null; this.inactive = 0;
    if (!s || s.frames.length < 3) return;
    const fr = s.frames;
    const fs = fr.map((p, i) => { // median of 3 smoothing
      const a = fr[Math.max(0, i - 1)].f, b = p.f, c = fr[Math.min(fr.length - 1, i + 1)].f;
      return Math.max(Math.min(a, b), Math.min(Math.max(a, b), c));
    });
    let iMin = 0, iMax = 0;
    fs.forEach((v, i) => { if (v < fs[iMin]) iMin = i; if (v > fs[iMax]) iMax = i; });
    const tail = fs.slice(-3).sort((a, b) => a - b)[1];
    const seg = {
      t0: fr[0].t, t1: fr[fr.length - 1].t, dur: fr[fr.length - 1].t - fr[0].t + this.dt,
      fmin: fs[iMin], fmax: fs[iMax], center: (fs[iMin] + fs[iMax]) / 2,
      dir: iMax > iMin ? "up" : "down", tail, maxDb: s.maxDb
    };
    seg.turn = seg.dir === "up" ? seg.fmax - tail : tail - seg.fmin;
    if (seg.maxDb > this.levelRef - 15 * (seg.t1 - this.levelRefT)) { this.levelRef = seg.maxDb; this.levelRefT = seg.t1; }
    this.on.segment(seg);
    if (this.state === "idle") this.seekOpening(seg); else this.readLetter(seg);
  }

  seekOpening(seg) {
    const h = this.history; h.push(seg); if (h.length > 3) h.shift();
    if (h.length < 3) return;
    const [a, b, c] = h;
    const ok = a.dir === "up" && b.dir === "up" && c.dir === "down"
      && a.dur / c.dur > 0.12 && a.dur / c.dur < 0.45 && b.dur / c.dur > 0.12 && b.dur / c.dur < 0.45
      && b.t0 - a.t1 < 0.6 * c.dur && c.t0 - b.t1 < 0.6 * c.dur
      && Math.abs(a.center - b.center) / a.center < 0.12
      && c.center / a.center > 0.85 && c.center / a.center < 1.1
      && a.center > 4300;
    if (!ok) return;
    const pitch = (a.center + b.center + c.center) / OPEN_CENTERS.reduce((x, y) => x + y);
    this.cal = { pitch, d3: c.dur };
    this.state = "receiving"; this.text = ""; this.letters = []; this.lastEnd = c.t1; this.history = [];
    this.on.state("receiving", this.cal);
  }

  readLetter(seg) {
    const { pitch, d3 } = this.cal;
    if (seg.dur < 0.2 * d3) return; // click or blip
    if (seg.center < 2050 * pitch) { this.finish(true); return; } // closing trill
    const gap = seg.t0 - this.lastEnd;
    if (gap < 0.15 * d3 && seg.dur < 0.45 * d3) { this.lastEnd = seg.t1; return; } // echo fragment of the previous call
    this.lastEnd = seg.t1;
    const rel = seg.center / pitch;
    let band = 0;
    BANDS.forEach((c, i) => { if (Math.abs(rel - c) < Math.abs(rel - BANDS[band])) band = i; });
    const offBand = Math.abs(rel - BANDS[band]) > SPAN * 0.75;
    const shape = seg.turn > 0.2 * SPAN * pitch ? "hook" : "straight";
    const len = seg.dur > 0.62 * d3 ? "long" : "short";
    const sym = offBand || seg.dur > 1.6 * d3 ? null : lookup(band, seg.dir, shape, len);
    const ch = sym ? sym.ch : "•";
    const space = this.letters.length > 0 && gap > 0.8 * d3;
    if (space) this.text += " ";
    this.text += ch;
    const info = { ch, space, band, dir: seg.dir, shape, len, seg };
    this.letters.push(info);
    this.on.letter(ch, info, this.text);
  }

  finish(complete) {
    if (this.state !== "receiving") return;
    const msg = { text: this.text, complete, pitch: this.cal.pitch, letters: this.letters };
    this.state = "idle"; this.history = []; this.lastEnd = null;
    this.on.state("idle");
    this.on.message(msg);
  }

  /** Flush at end of a recording. */
  end() {
    if (this.seg) this.close();
    if (this.state === "receiving") this.finish(false);
  }
}

/** Decode a whole buffer at once (simulation, uploaded recordings). */
export function decodeBuffer(samples, sampleRate, opts = {}) {
  const messages = [];
  const on = Object.assign({}, opts.on || {});
  const userMsg = on.message;
  on.message = m => { messages.push(m); if (userMsg) userMsg(m); };
  const d = new Decoder(sampleRate, { ...opts, on });
  for (let i = 0; i < samples.length; i += 4096) d.push(samples.subarray(i, Math.min(samples.length, i + 4096)));
  d.end();
  return messages;
}

/** Character error rate between two strings (edit distance / length). */
export function cer(ref, hyp) {
  const m = ref.length, n = hyp.length;
  if (!m) return n ? 1 : 0;
  let prev = Array.from({ length: n + 1 }, (_, j) => j);
  for (let i = 1; i <= m; i++) {
    const cur = [i];
    for (let j = 1; j <= n; j++) cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ref[i - 1] === hyp[j - 1] ? 0 : 1));
    prev = cur;
  }
  return prev[n] / m;
}

// ---------- simulation helpers (noise, echo) ----------
function rng(seed) { let s = seed >>> 0; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); }

/** Add a Schroeder reverb (mix 0..1) — a stand-in for a real room. */
export function addEcho(x, sr, mix = 0.3, rt = 1.2) {
  if (mix <= 0) return x;
  const combs = [29.7, 37.1, 41.1, 43.7].map(ms => Math.round(ms * sr / 1000));
  const out = new Float32Array(x.length);
  for (const d of combs) {
    const g = Math.pow(10, -3 * d / (rt * sr)), buf = new Float32Array(d); let p = 0;
    for (let i = 0; i < x.length; i++) { const y = buf[p]; buf[p] = x[i] + y * g; out[i] += y * 0.25; p = (p + 1) % d; }
  }
  for (const [ms, g] of [[5, 0.7], [1.7, 0.7]]) {
    const d = Math.round(ms * sr / 1000), buf = new Float32Array(d); let p = 0;
    for (let i = 0; i < x.length; i++) { const z = buf[p], v = out[i] + g * z; out[i] = z - g * v; buf[p] = v; p = (p + 1) % d; }
  }
  const res = new Float32Array(x.length);
  for (let i = 0; i < x.length; i++) res[i] = x[i] * (1 - mix * 0.5) + out[i] * mix;
  return res;
}

/** Add background noise. kind: "white" | "voices" (300–3000 Hz babble) | "rumble" (train). snrDb vs signal RMS. */
export function addNoise(x, sr, kind = "white", snrDb = 20, seed = 1) {
  const r = rng(seed); let sig = 0, cnt = 0;
  for (const v of x) if (Math.abs(v) > 1e-4) { sig += v * v; cnt++; }
  const sigRms = Math.sqrt(sig / Math.max(cnt, 1));
  const n = new Float32Array(x.length);
  if (kind === "white") for (let i = 0; i < n.length; i++) n[i] = r() * 2 - 1;
  else {
    // band-limited noise via two one-pole filters (high-pass then low-pass)
    const lo = kind === "voices" ? 300 : 30, hi = kind === "voices" ? 3000 : 400;
    const aH = Math.exp(-2 * Math.PI * lo / sr), aL = Math.exp(-2 * Math.PI * hi / sr);
    let hpPrevIn = 0, hpPrev = 0, lp = 0, lp2 = 0;
    for (let i = 0; i < n.length; i++) {
      const w = r() * 2 - 1;
      const hp = aH * (hpPrev + w - hpPrevIn); hpPrevIn = w; hpPrev = hp;
      lp = (1 - aL) * hp + aL * lp; lp2 = (1 - aL) * lp + aL * lp2;
      const syll = kind === "voices" ? 0.35 + 0.65 * Math.max(0, Math.sin(2 * Math.PI * 4.3 * i / sr + 3 * Math.sin(2 * Math.PI * 0.7 * i / sr))) : 1;
      n[i] = lp2 * syll;
    }
  }
  let nr = 0; for (const v of n) nr += v * v; nr = Math.sqrt(nr / n.length);
  const g = sigRms / (nr * Math.pow(10, snrDb / 20));
  const out = new Float32Array(x.length);
  for (let i = 0; i < x.length; i++) out[i] = x[i] + n[i] * g;
  return out;
}
