import { ALPHA, BANDS, SPAN, OPEN, CLOSE, symNote, sweep, build, Player, renderOffline, encodeWav, encodeMp3 } from "./chirp.js?v=3";

const $ = id => document.getElementById(id);
const msg = $("msg"), playBtn = $("play"), loopIn = $("loop"), stats = $("stats"), skippedEl = $("skipped");
const tempoIn = $("tempo"), pitchIn = $("pitch"), roomIn = $("room");
const wrap = $("wrap"), canvas = $("score"), grid = $("grid");
const player = new Player();
let sched = null, playing = null, loopTimer = null;

const params = () => ({ tempo: +tempoIn.value, pitch: +pitchIn.value, room: +roomIn.value });

function refresh() {
  const p = params();
  $("tempoOut").textContent = p.tempo.toFixed(2) + "×";
  $("pitchOut").textContent = (p.pitch >= 1 ? "+" : "") + Math.round((p.pitch - 1) * 100) + "%";
  $("roomOut").textContent = Math.round(p.room / 0.7 * 100) + "%";
  sched = build(msg.value, p.tempo);
  const lps = sched.letters ? (sched.letters / sched.total).toFixed(1) : "0";
  stats.textContent = `${sched.letters} letters · ${sched.pauses.length} pauses · ${sched.total.toFixed(1)} s · ${lps} letters/s`;
  skippedEl.textContent = sched.skipped.length ? "Not in the alphabet, left out: " + sched.skipped.join(" ") : "";
  player.setRoom(p.room);
  drawScore();
}

function play() {
  try {
    stop(true);
    const h = player.play(sched, params().pitch);
    playing = { ...h, total: sched.total };
    playBtn.textContent = "Stop"; playBtn.setAttribute("aria-pressed", "true");
    requestAnimationFrame(tick);
  } catch (e) {
    stats.textContent = "This browser could not start audio. Try another browser.";
  }
}
function stop(keepLoop) {
  if (playing) playing.stop();
  playing = null;
  if (!keepLoop) { clearTimeout(loopTimer); loopTimer = null; }
  playBtn.textContent = "Play"; playBtn.setAttribute("aria-pressed", "false");
  drawScore();
}
function tick() {
  if (!playing) return;
  const el = player.now() - playing.t0;
  if (el > playing.total + 0.4) {
    stop(true);
    if (loopIn.checked) { loopTimer = setTimeout(play, 3000); playBtn.textContent = "Stop"; playBtn.setAttribute("aria-pressed", "true"); }
    return;
  }
  drawScore(el);
  const x = xOf(Math.max(el, 0));
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!reduce && (x < wrap.scrollLeft + 40 || x > wrap.scrollLeft + wrap.clientWidth - 80)) wrap.scrollLeft = Math.max(0, x - wrap.clientWidth * 0.3);
  requestAnimationFrame(tick);
}

// ---------- drawing ----------
const PPS = 240, PAD = 28, H = 250, FMIN = 1000, FMAX = 8000;
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const xOf = t => PAD + t * PPS;
const yOf = f => { const top = 18, bot = H - 34; return bot - (f - FMIN) / (FMAX - FMIN) * (bot - top); };
const colorFor = kind => kind === "short" ? css("--short") : kind === "long" ? css("--long") : css("--frame");

function drawScore(playT) {
  if (!sched) return;
  const dpr = devicePixelRatio || 1;
  const W = Math.max(wrap.clientWidth, Math.ceil(xOf(sched.total)) + PAD);
  if (canvas.width !== Math.round(W * dpr) || canvas.height !== Math.round(H * dpr)) {
    canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    canvas.style.width = W + "px"; canvas.style.height = H + "px";
  }
  const c = canvas.getContext("2d");
  c.setTransform(dpr, 0, 0, dpr, 0, 0);
  c.clearRect(0, 0, W, H);
  const pitch = +pitchIn.value, line = css("--line"), muted = css("--muted"), ink = css("--ink");

  c.font = "10px " + css("--mono");
  BANDS.forEach((b, i) => {
    const yTop = yOf((b + SPAN / 2) * pitch), yBot = yOf((b - SPAN / 2) * pitch);
    c.fillStyle = line; c.globalAlpha = 0.45; c.fillRect(0, yTop, W, yBot - yTop);
    c.globalAlpha = 1; c.fillStyle = muted;
    c.fillText("B" + (i + 1) + " " + (b * pitch / 1000).toFixed(1) + "k", 4, yBot - 3);
  });
  c.strokeStyle = line; c.lineWidth = 1;
  c.beginPath(); c.moveTo(0, H - 28.5); c.lineTo(W, H - 28.5); c.stroke();
  c.fillStyle = muted;
  sched.pauses.forEach(t => c.fillRect(xOf(t) - 6, H - 30, 12, 3));

  c.lineCap = "round";
  sched.events.forEach(e => {
    const done = playT === undefined || playT >= e.t;
    const now = playT !== undefined && playT >= e.t && playT <= e.t + e.dur;
    c.globalAlpha = done ? 1 : 0.4;
    c.strokeStyle = colorFor(e.kind); c.lineWidth = now ? 5 : 3;
    c.beginPath();
    for (let i = 0; i <= 24; i++) {
      const u = i / 24, x = xOf(e.t + e.dur * u), y = yOf(sweep(e.f0, e.f1, e.shape, u) * pitch);
      if (i === 0) c.moveTo(x, y); else c.lineTo(x, y);
    }
    c.stroke();
    if (e.kind !== "frame") {
      c.fillStyle = now ? colorFor(e.kind) : ink;
      c.font = (now ? "600 " : "500 ") + "13px " + css("--mono");
      c.textAlign = "center"; c.fillText(e.label, xOf(e.t + e.dur / 2), H - 10); c.textAlign = "start";
    } else if (e.label) {
      c.fillStyle = muted; c.font = "11px " + css("--body"); c.fillText(e.label, xOf(e.t), H - 10);
    }
  });
  c.globalAlpha = 1;
  if (playT !== undefined && playT >= 0) {
    c.strokeStyle = ink; c.globalAlpha = 0.55; c.lineWidth = 1;
    c.beginPath(); c.moveTo(xOf(playT) + 0.5, 6); c.lineTo(xOf(playT) + 0.5, H - 28); c.stroke();
    c.globalAlpha = 1;
  }
}

function drawGlyph(cv, notes, kind, w) {
  const dpr = devicePixelRatio || 1, h = 40;
  cv.width = w * dpr; cv.height = h * dpr;
  const c = cv.getContext("2d"); c.setTransform(dpr, 0, 0, dpr, 0, 0); c.clearRect(0, 0, w, h);
  const fmin = kind === "frame" ? 1200 : 1950, fmax = kind === "frame" ? 6600 : 5250;
  let total = 0; notes.forEach(n => total += n.gap || n.dur);
  const scale = (w - 8) / Math.max(total, 0.13);
  const y = f => h - 4 - (f - fmin) / (fmax - fmin) * (h - 8);
  c.strokeStyle = colorFor(kind); c.lineWidth = 2.5; c.lineCap = "round";
  let t = 0;
  notes.forEach(n => {
    if (n.gap) { t += n.gap; return; }
    c.beginPath();
    for (let i = 0; i <= 20; i++) {
      const u = i / 20, x = 4 + (t + n.dur * u) * scale, yy = y(sweep(n.f0, n.f1, n.shape, u));
      if (i === 0) c.moveTo(x, yy); else c.lineTo(x, yy);
    }
    c.stroke(); t += n.dur;
  });
}

const glyphs = [];
function addCell(label, code, notes, kind, w, aria, isFrame) {
  const b = document.createElement("button");
  b.className = "cell" + (isFrame ? " frame" : ""); b.type = "button"; b.setAttribute("aria-label", aria);
  const cv = document.createElement("canvas");
  const lbl = document.createElement("b"); lbl.textContent = label;
  if (isFrame) { lbl.style.fontFamily = "var(--body)"; lbl.style.fontSize = ".9rem"; }
  const small = document.createElement("small"); small.textContent = code;
  b.append(cv, lbl, small);
  b.addEventListener("click", () => { try { player.playNotes(notes, params().pitch); } catch (e) { /* no audio */ } });
  grid.appendChild(b);
  glyphs.push({ cv, notes, kind, w });
}
ALPHA.forEach(s => addCell(s.ch, `B${s.band + 1} ${s.dir === "up" ? "↑" : "↓"} ${s.shape}`, [symNote(s)], s.len, 76, "Play the call for " + s.ch));
addCell("Opening call", "above 5 kHz", OPEN, "frame", 160, "Play the opening call", true);
addCell("Closing call", "below 2 kHz", CLOSE, "frame", 160, "Play the closing call", true);
const drawGlyphs = () => glyphs.forEach(g => drawGlyph(g.cv, g.notes, g.kind, g.w));

// ---------- export ----------
function fileName(ext) {
  const slug = sched.text.trim().split(/\s+/).slice(0, 5).join("-").replace(/[^a-z0-9-]/g, "") || "letter";
  return `birdlu-${slug}.${ext}`;
}
async function save(kind) {
  const note = $("saveNote"), p = params();
  note.textContent = "Rendering…";
  let blob, name;
  try {
    const { samples, sampleRate } = await renderOffline(sched, { pitch: p.pitch, room: p.room, sampleRate: 44100 });
    if (kind === "mp3") {
      try { blob = encodeMp3(samples, sampleRate); }
      catch (e) { console.error(e); kind = "wav"; blob = encodeWav(samples, sampleRate); }
    } else blob = encodeWav(samples, sampleRate);
    name = fileName(kind);
  } catch (e) {
    console.error(e);
    note.textContent = "Could not render the audio: " + (e && e.message ? e.message : e);
    return;
  }
  const url = URL.createObjectURL(blob);
  const file = new File([blob], name, { type: blob.type });
  // A visible link always works, even where the browser blocks automatic downloads.
  note.textContent = "";
  const a = document.createElement("a");
  a.href = url; a.download = name; a.textContent = `Download ${name} (${Math.round(blob.size / 1024)} KB)`;
  note.append(a);
  if (navigator.canShare && navigator.canShare({ files: [file] })) {
    const sh = document.createElement("button");
    sh.className = "secondary"; sh.type = "button"; sh.textContent = "Share or save to Files";
    sh.style.marginLeft = "12px";
    sh.addEventListener("click", () => navigator.share({ files: [file], title: name }).catch(() => {}));
    note.append(sh);
  }
  try { a.click(); } catch (e) { /* the link stays for a manual tap */ }
}
$("saveMp3").addEventListener("click", () => save("mp3"));
$("saveWav").addEventListener("click", () => save("wav"));

playBtn.addEventListener("click", () => { if (playing || loopTimer) stop(); else play(); });
msg.addEventListener("input", () => { stop(); refresh(); });
msg.addEventListener("keydown", e => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); play(); } });
[tempoIn, pitchIn, roomIn].forEach(el => el.addEventListener("input", refresh));

const redraw = () => { drawScore(); drawGlyphs(); };
try { matchMedia("(prefers-color-scheme: dark)").addEventListener("change", redraw); } catch (e) { /* old Safari */ }
new MutationObserver(redraw).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
if ("ResizeObserver" in window) new ResizeObserver(() => { if (!playing) drawScore(); }).observe(wrap);
if (document.fonts && document.fonts.ready) document.fonts.ready.then(redraw);

refresh();
drawGlyphs();
