// Compare candidate bird alphabets by ear.
// Reads birds/alphabets.json (made by lab/make_alphabets.py) and builds each message from the
// syllable clips. lab/check_alphabets.py builds the same messages the same way; keep them in step.

const V = "3";
const SR = 44100; // clips are decoded and messages built at this rate; the browser resamples on play
const $ = id => document.getElementById(id);
const statusEl = $("status");

let ctx = null, data = null, syl = {}, clips = {}, check = null;
let playing = null; // { src, raf, card }

export function normalize(text) {
  let out = "";
  for (const ch of text.toLowerCase()) {
    if (ch === "é" || ch === "è") { out += ch; continue; }
    out += ch.replace(/ß/g, "ss").replace(/æ/g, "ae").replace(/œ/g, "oe")
      .normalize("NFD").replace(/[̀-ͯ]/g, "");
  }
  return out;
}

/** Small seeded random numbers, so the same message always sounds the same. */
function rng(seedText) {
  let a = 2166136261;
  for (const ch of seedText) a = Math.imul(a ^ ch.codePointAt(0), 16777619);
  return () => {
    a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** "A message coming from the forest": every letter a trill, every species in its own place. */
function forestSchedule(text, version, lens) {
  const L = version.letters, T = version.trill, G = version.gaps, rand = rng(text);
  const between = ([a, b]) => a + (b - a) * rand();
  const words = normalize(text).split(/\s+/).map(w => [...w].filter(c => L[c])).filter(w => w.length);
  const items = [];
  let t = 0.3;
  words.forEach((w, wi) => {
    w.forEach((c, ci) => {
      const id = L[c][0], slow = L[c].length > 1, len = lens[id];
      const voice = version.voices[syl[id].species] || { gain: 0.8, wet: 0.4, pan: 0 };
      let reps = len >= 0.3 ? 1 : len >= 0.15 ? 2 : Math.max(2, Math.min(5, Math.round(T.target / (len + T.fast_gap))));
      if (slow) reps = Math.max(2, reps - 1);
      const level = voice.gain * (0.85 + 0.3 * rand());
      const start = t;
      for (let k = 0; k < reps; k++) {
        const swell = 0.8 + 0.2 * Math.sin(Math.PI * (k + 0.5) / reps);
        items.push({ id, t, gain: level * swell * (0.9 + 0.2 * rand()), pan: voice.pan, wet: voice.wet });
        t += len;
        if (k < reps - 1) t += (slow ? T.slow_gap : T.fast_gap) * (1 - 0.08 * k) * (0.85 + 0.3 * rand());
      }
      items.push({ letter: c, start, end: t, word: wi });
      const lastOfWord = ci === w.length - 1, last = lastOfWord && wi === words.length - 1;
      if (!last) t += between(lastOfWord ? G.word : G.letter);
    });
  });
  return { items, dur: t + 1.2, letters: items.filter(x => x.letter).length, words: words.length };
}

/** Words → letters → syllables, with times. Unknown characters are skipped. */
export function schedule(text, version, timing, lens) {
  if (version.style === "forest") return forestSchedule(text, version, lens);
  const L = version.letters, lead = 0.3;
  const words = normalize(text).split(/\s+/).map(w => [...w].filter(c => L[c])).filter(w => w.length);
  const items = [];
  let t = lead;
  words.forEach((w, wi) => {
    w.forEach((c, ci) => {
      const start = t;
      L[c].forEach((id, k) => {
        items.push({ id, t });
        t += lens[id];
        if (k < L[c].length - 1) t += timing.double_gap;
      });
      items.push({ letter: c, start, end: t, word: wi });
      const lastOfWord = ci === w.length - 1, last = lastOfWord && wi === words.length - 1;
      if (!last) t += lastOfWord ? timing.word_gap : timing.letter_gap;
    });
  });
  return { items, dur: t + 0.5, letters: items.filter(x => x.letter).length, words: words.length };
}

function prepare(buf) {
  // mono, peak 0.8, short fades so clip edges do not click
  const x = Float32Array.from(buf.getChannelData(0));
  let peak = 0; for (const v of x) peak = Math.max(peak, Math.abs(v));
  const g = peak ? 0.8 / peak : 1, n = Math.round(data.fade_ms / 1000 * buf.sampleRate);
  for (let i = 0; i < x.length; i++) {
    let e = 1;
    if (i < n) e = i / n; else if (i >= x.length - n) e = (x.length - 1 - i) / n;
    x[i] *= g * e;
  }
  return x;
}

function render(sched, sr) {
  const out = new Float32Array(Math.ceil(sched.dur * sr));
  for (const it of sched.items) {
    if (!it.id) continue;
    const c = clips[it.id], o = Math.round(it.t * sr);
    for (let i = 0; i < c.length && o + i < out.length; i++) out[o + i] += c[i];
  }
  let peak = 0; for (const v of out) peak = Math.max(peak, Math.abs(v));
  if (peak > 0.95) for (let i = 0; i < out.length; i++) out[i] *= 0.9 / peak;
  return out;
}

/** Stereo dry signal plus a mono send to the forest echo, for versions with placed voices. */
function renderPlaced(sched, sr) {
  const n = Math.ceil(sched.dur * sr), L = new Float32Array(n), R = new Float32Array(n), W = new Float32Array(n);
  for (const it of sched.items) {
    if (!it.id) continue;
    const c = clips[it.id], o = Math.round(it.t * sr), g = it.gain ?? 1, p = it.pan ?? 0, w = it.wet ?? 0;
    const gl = g * Math.cos((p + 1) * Math.PI / 4), gr = g * Math.sin((p + 1) * Math.PI / 4);
    for (let i = 0; i < c.length && o + i < n; i++) { L[o + i] += c[i] * gl; R[o + i] += c[i] * gr; W[o + i] += c[i] * g * w; }
  }
  let peak = 0; for (let i = 0; i < n; i++) peak = Math.max(peak, Math.abs(L[i]), Math.abs(R[i]));
  if (peak > 0.9) { const k = 0.85 / peak; for (let i = 0; i < n; i++) { L[i] *= k; R[i] *= k; W[i] *= k; } }
  return { L, R, W };
}

/** A soft, dark, wide echo: trees, not walls. Two decorrelated tails for left and right. */
function forestIR(sr, rt60 = 1.3) {
  const n = Math.round(sr * rt60 * 1.1), pre = Math.round(0.018 * sr), b = ctx.createBuffer(2, n, sr);
  const a = Math.exp(-2 * Math.PI * 3500 / sr);
  for (let ch = 0; ch < 2; ch++) {
    const ir = new Float32Array(n); let lp = 0, e = 0;
    for (let i = pre; i < n; i++) {
      lp = (1 - a) * (Math.random() * 2 - 1) + a * lp;
      ir[i] = lp * Math.pow(10, -3 * ((i - pre) / sr) / rt60); e += ir[i] * ir[i];
    }
    const k = 1 / Math.sqrt(e); for (let i = 0; i < n; i++) ir[i] *= k;
    b.copyToChannel(ir, ch);
  }
  return b;
}

function roomIR(sr, rt60 = 0.5, distance = 2, critical = 0.6) {
  // direct sound + exponentially decaying noise tail; same idea as lab/channel.py
  const n = Math.round(sr * rt60 * 1.2), ir = new Float32Array(n);
  let e = 0;
  for (let i = Math.round(0.004 * sr); i < n; i++) {
    ir[i] = (Math.random() * 2 - 1) * Math.pow(10, -3 * (i / sr) / rt60);
    e += ir[i] * ir[i];
  }
  const tailGain = (distance / critical) / Math.sqrt(e);
  let lp = 0; const a = Math.exp(-2 * Math.PI * 6000 / sr);
  for (let i = 1; i < n; i++) { lp = (1 - a) * ir[i] * tailGain + a * lp; ir[i] = lp; }
  ir[0] = 1;
  const b = ctx.createBuffer(1, n, sr); b.copyToChannel(ir, 0);
  return b;
}

function stop() {
  if (!playing) return;
  for (const s of playing.sources || [playing.src]) { try { s.stop(); } catch (e) {} }
  cancelAnimationFrame(playing.raf);
  playing.card.classList.remove("playing");
  playing.card.querySelectorAll(".lt.on").forEach(e => e.classList.remove("on"));
  playing.btn.textContent = "Play"; playing.btn.setAttribute("aria-pressed", "false");
  playing = null;
}

async function play(key, card, btn) {
  const was = playing && playing.card === card;
  stop();
  if (was) return;
  if (!ctx) ctx = new AudioContext();
  await ctx.resume();
  const timing = data.timing[speed()];
  const lens = Object.fromEntries(Object.entries(clips).map(([k, c]) => [k, c.length / SR]));
  const sched = schedule(text(), data.versions[key], timing, lens);
  if (!sched.letters) { statusEl.textContent = "Type a few letters first."; return; }
  const master = ctx.createGain();
  if ($("room").checked) {
    const conv = ctx.createConvolver(); conv.normalize = false; conv.buffer = roomIR(ctx.sampleRate);
    const g = ctx.createGain(); g.gain.value = 0.5;
    master.connect(conv).connect(g).connect(ctx.destination);
  } else master.connect(ctx.destination);
  const src = ctx.createBufferSource(), sources = [src];
  if (sched.items.some(x => x.pan !== undefined)) {
    const { L, R, W } = renderPlaced(sched, SR);
    const buf = ctx.createBuffer(2, L.length, SR); buf.copyToChannel(L, 0); buf.copyToChannel(R, 1);
    src.buffer = buf; src.connect(master);
    const wet = ctx.createBufferSource(), wb = ctx.createBuffer(1, W.length, SR); wb.copyToChannel(W, 0);
    wet.buffer = wb;
    const conv = ctx.createConvolver(); conv.normalize = false; conv.buffer = forestIR(ctx.sampleRate);
    const wg = ctx.createGain(); wg.gain.value = 0.35;
    wet.connect(conv).connect(wg).connect(master);
    sources.push(wet);
  } else {
    const samples = render(sched, SR);
    const buf = ctx.createBuffer(1, samples.length, SR);
    buf.copyToChannel(samples, 0);
    src.buffer = buf; src.connect(master);
  }
  const t0 = ctx.currentTime + 0.05;
  sources.forEach(s => s.start(t0));
  drawStrip(card, sched);
  const chips = [...card.querySelectorAll(".lt")], letters = sched.items.filter(x => x.letter);
  playing = { src, sources, card, btn, raf: 0 };
  card.classList.add("playing");
  btn.textContent = "Stop"; btn.setAttribute("aria-pressed", "true");
  const tick = () => {
    const now = ctx.currentTime - t0;
    letters.forEach((l, i) => chips[i].classList.toggle("on", now >= l.start && now < l.end + 0.03));
    if (playing && playing.src === src) playing.raf = requestAnimationFrame(tick);
  };
  tick();
  src.onended = () => { if (playing && playing.src === src) stop(); };
}

function drawStrip(card, sched) {
  const strip = card.querySelector(".strip");
  let html = "", lastWord = 0;
  for (const it of sched.items) {
    if (!it.letter) continue;
    if (it.word !== lastWord) { html += `<span class="sp" aria-hidden="true"></span>`; lastWord = it.word; }
    html += `<span class="lt">${it.letter}</span>`;
  }
  strip.innerHTML = html;
  const perLetter = (sched.dur - 0.8) / sched.letters;
  card.querySelector(".dur").textContent =
    `${sched.dur.toFixed(1)} s for ${sched.letters} letters · ${perLetter.toFixed(2)} s per letter`;
}

const text = () => $("text").value;
const speed = () => document.querySelector("input[name=speed]:checked").value;

function letterTable(v) {
  const order = "aeiouyéèbcdfghjklmnpqrstvwxz";
  return order.split("").filter(c => v.letters[c]).map(c => {
    const ids = v.letters[c], s = syl[ids[0]];
    const name = s.species.replace("Eurasian ", "").replace("European ", "");
    return `<li><b>${c}</b> <button type="button" class="hear" data-ids="${ids.join(" ")}">${ids[0]}${ids.length > 1 ? " ×2" : ""}</button> <small>${name}</small></li>`;
  }).join("");
}

function checkLine(key) {
  if (!check || !check.versions[key]) return "Not checked yet.";
  const r = check.versions[key][speed()];
  if (!r) return "Not checked yet.";
  return "Simulated letter errors: " + Object.entries(r).map(([c, e]) => `${c} ${e.toFixed(0)}%`).join(" · ");
}

function refresh() {
  for (const card of document.querySelectorAll(".alpha")) {
    card.querySelector(".score").textContent = checkLine(card.dataset.key);
    const lens = Object.fromEntries(Object.entries(clips).map(([k, c]) => [k, c.length / SR]));
    drawStrip(card, schedule(text(), data.versions[card.dataset.key], data.timing[speed()], lens));
  }
}

async function hear(ids) {
  stop();
  if (!ctx) ctx = new AudioContext();
  await ctx.resume();
  const lens = Object.fromEntries(Object.entries(clips).map(([k, c]) => [k, c.length / SR]));
  const items = []; let t = 0.05;
  ids.forEach((id, k) => { items.push({ id, t }); t += lens[id] + (k < ids.length - 1 ? data.timing[speed()].double_gap : 0); });
  const samples = render({ items, dur: t + 0.2 }, SR);
  const buf = ctx.createBuffer(1, samples.length, SR); buf.copyToChannel(samples, 0);
  const src = ctx.createBufferSource(); src.buffer = buf; src.connect(ctx.destination); src.start();
}

async function main() {
  try {
    data = await (await fetch(`birds/alphabets.json?v=${V}`)).json();
    for (const s of await (await fetch(`birds/syllables.json?v=${V}`)).json()) syl[s.id] = s;
  } catch (e) { statusEl.textContent = "Could not load the alphabets."; return; }
  try { check = await (await fetch(`birds/alphabets-check.json?v=${V}`)).json(); } catch (e) { check = null; }

  statusEl.textContent = "Loading the bird syllables…";
  const used = new Set(Object.values(data.versions).flatMap(v => Object.values(v.letters).flat()));
  const tmp = new OfflineAudioContext(1, 1, SR);
  await Promise.all([...used].map(async id => {
    const ab = await (await fetch(`birds/${syl[id].file}?v=${V}`)).arrayBuffer();
    clips[id] = prepare(await tmp.decodeAudioData(ab));
  }));
  statusEl.textContent = "";

  const list = $("alphas");
  for (const [key, v] of Object.entries(data.versions)) {
    const card = document.createElement("article");
    card.className = "alpha"; card.dataset.key = key;
    const [title, sub] = v.name.split(" · ");
    card.innerHTML = `
      <div class="head"><h2>${title}</h2><span>${sub}</span></div>
      <p>${v.idea}</p>
      <div class="row"><button class="primary" type="button" aria-pressed="false">Play</button><span class="stats dur"></span></div>
      <div class="strip" aria-label="Letters of the message"></div>
      <p class="stats score"></p>
      <details><summary>Which bird sings which letter</summary><ul class="letters">${letterTable(v)}</ul></details>`;
    const btn = card.querySelector("button.primary");
    btn.addEventListener("click", () => play(key, card, btn));
    card.querySelectorAll(".hear").forEach(b => b.addEventListener("click", () => hear(b.dataset.ids.split(" "))));
    list.appendChild(card);
  }
  document.querySelectorAll(".preset").forEach(b => b.addEventListener("click", () => { $("text").value = b.textContent; stop(); refresh(); }));
  $("text").addEventListener("input", () => { stop(); refresh(); });
  document.querySelectorAll("input[name=speed]").forEach(r => r.addEventListener("change", () => { stop(); refresh(); }));
  $("room").addEventListener("change", stop);
  refresh();
}

main();
