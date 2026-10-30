"use strict";
/* FlowMind front-end. Vanilla JS, zero build step, zero CDN dependencies. */

// ───────────────────────── icons & helpers
const ICONS = {
  home: '<path d="M3 11l9-8 9 8M5 10v10h14V10"/>',
  cal: '<rect x="3" y="4" width="18" height="17" rx="3"/><path d="M16 2v4M8 2v4M3 10h18"/>',
  board: '<rect x="3" y="4" width="5" height="16" rx="1.5"/><rect x="10" y="4" width="5" height="10" rx="1.5"/><rect x="17" y="4" width="4" height="13" rx="1.5"/>',
  book: '<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2zM4 19V5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>', x: '<path d="M18 6 6 18M6 6l12 12"/>', check: '<path d="M20 6 9 17l-5-5"/>',
  spark: '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9zM19 16l.7 1.8L21.5 18.5l-1.8.7L19 21l-.7-1.8-1.8-.7 1.8-.7z"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>', clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8"/>',
  bell: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0"/>',
  link: '<path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/>',
  moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="m9 12 2 2 4-4"/>',
  swap: '<path d="M17 2l4 4-4 4M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4M21 13v2a3 3 0 0 1-3 3H3"/>',
  doc: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5M9 13h6M9 17h6"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>', info: '<circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16.5v.01"/>',
  copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h8"/>', edit: '<path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
};
const ic = (n, cls = "") => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" class="${cls}" aria-hidden="true">${ICONS[n] || ""}</svg>`;
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const reduceMotion = () => window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const parseD = (s) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };
const todayD = () => { const t = new Date(); return new Date(t.getFullYear(), t.getMonth(), t.getDate()); };
const isoToday = (plus = 0) => { const d = todayD(); d.setDate(d.getDate() + plus); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
const daysFrom = (s) => Math.round((parseD(s) - todayD()) / 864e5);
const fmtDate = (s) => parseD(s).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
const fmtLong = (s) => parseD(s).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", year: "numeric" });
const relDay = (s) => { const n = daysFrom(s); return n === 0 ? "Today" : n === 1 ? "Tomorrow" : n === -1 ? "Yesterday" : n > 0 ? `In ${n} days` : `${-n} days ago`; };
const initials = (n) => n.split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
const hue = (n) => { let h = 0; for (const c of n) h = (h * 31 + c.charCodeAt(0)) % 360; return h; };
const avatar = (n, cls = "") => n ? `<span class="avatar ${cls}" title="${esc(n)}" style="background:linear-gradient(145deg,hsl(${hue(n)} 75% 58%),hsl(${(hue(n) + 40) % 360} 70% 46%))">${esc(initials(n))}</span>` : "";

const STATUS = { open: ["Open", "blue"], in_progress: ["In progress", "violet"], done: ["Done", "green"], dropped: ["Dropped", ""], carried: ["Carried forward", ""] };
const itemBadge = (s) => `<span class="badge ${STATUS[s][1]}"><i></i>${STATUS[s][0]}</span>`;
function dueBadge(it) {
  if (!it.due_date) return `<span class="badge">${ic("clock")}No date</span>`;
  if (["done", "dropped", "carried"].includes(it.status)) return `<span class="badge">${ic("clock")}${fmtDate(it.due_date)}</span>`;
  const n = daysFrom(it.due_date);
  if (n < 0) return `<span class="badge red">${ic("clock")}${-n}d overdue</span>`;
  if (n === 0) return `<span class="badge amber">${ic("clock")}Due today</span>`;
  if (n <= 3) return `<span class="badge amber">${ic("clock")}Due in ${n}d</span>`;
  return `<span class="badge">${ic("clock")}Due ${fmtDate(it.due_date)}</span>`;
}
const ownerBadge = (o) => o ? `<span class="badge">${avatar(o).replace('class="avatar ', 'style="width:18px;height:18px;font-size:9px;border:0" class="avatar ')}${esc(o)}</span>` : `<span class="badge amber">Unassigned</span>`;
const typeBadge = (t) => t === "handover" ? `<span class="badge violet">${ic("swap")}Handover</span>` : `<span class="badge blue">${ic("cal")}Meeting</span>`;
const mStatusBadge = (s) => `<span class="badge ${{ planned: "blue", held: "violet", closed: "" }[s]}"><i></i>${s[0].toUpperCase() + s.slice(1)}</span>`;
const empty = (t, s) => `<div class="empty"><b>${esc(t)}</b>${esc(s || "")}</div>`;
const field = (label, inner) => `<div class="field"><label>${esc(label)}</label>${inner}</div>`;

function aiBadge(m) {
  if (!m || (!m.ai_used && !m.fallback)) return "";
  if (m.ai_used) return `<div class="ai-note"><span class="badge violet">${ic("spark")}AI · ${esc(m.model)}</span><span class="faint">${(m.latency_ms / 1000).toFixed(1)}s</span></div>`;
  return `<div class="ai-note"><span class="badge amber">Rule-based result</span><span>${esc(m.notice || "AI is unavailable right now.")}</span></div>`;
}

// ───────────────────────── api / toast / sheets
async function api(path, opts = {}) {
  let res;
  const formData = opts.body instanceof FormData;
  try {
    res = await fetch("/api" + path, { method: opts.method || "GET",
      headers: opts.body && !formData ? { "Content-Type": "application/json" } : {},
      body: opts.body ? (formData ? opts.body : JSON.stringify(opts.body)) : undefined });
  } catch { throw new Error("Can't reach the server. Check your connection and try again."); }
  let data = null; try { data = await res.json(); } catch { /* non-json */ }
  if (!res.ok) { const e = new Error((data && data.error) || `Request failed (${res.status})`); e.requestId = data && data.request_id; e.status = res.status; throw e; }
  return data;
}
function toast(msg, kind = "ok") {
  const el = document.createElement("div"); el.className = `toast ${kind}`;
  el.innerHTML = `${ic(kind === "err" ? "info" : "check")}<span>${esc(msg)}</span>`;
  $("#toasts").appendChild(el);
  setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 360); }, kind === "err" ? 5200 : 2800);
}
async function busy(btn, fn) {
  if (btn) btn.classList.add("loading");
  try { return await fn(); }
  catch (e) { toast(e.requestId && e.status >= 500 ? `${e.message} (ref ${e.requestId})` : e.message, "err"); }
  finally { if (btn) btn.classList.remove("loading"); }
}
function openSheet(html, { wide = false } = {}) {
  closeSheet(true);
  const el = document.createElement("div"); el.className = "scrim";
  el.innerHTML = `<div class="sheet ${wide ? "wide" : ""}" role="dialog" aria-modal="true">${html}</div>`;
  el.addEventListener("mousedown", (e) => { if (e.target === el) closeSheet(); });
  $("#sheets").appendChild(el);
  const first = $("input:not([type=checkbox]):not([type=radio]), textarea, select", el); if (first && !matchMedia("(max-width:860px)").matches) setTimeout(() => first.focus(), 80);
  return $(".sheet", el);
}
function closeSheet(instant) {
  const el = $("#sheets .scrim"); if (!el) return;
  if (instant || reduceMotion()) { el.remove(); return; }
  el.classList.add("out"); setTimeout(() => el.remove(), 250);
}
const sheetHead = (title, sub) => `<div class="sheet-h"><div><h2>${esc(title)}</h2>${sub ? `<p class="muted small" style="margin-top:4px">${sub}</p>` : ""}</div><button class="x" data-act="close" type="button" aria-label="Close">${ic("x")}</button></div>`;
const peopleList = () => `<datalist id="people">${S.people.map((p) => `<option value="${esc(p)}">`).join("")}</datalist>`;

// ───────────────────────── state & router
const S = { people: [], route: null, meeting: null, readiness: {}, drafts: {}, mf: "all", mq: "", bf: "all", kq: "", first: true, user: null };
const NAV = [["#/overview", "home", "Overview"], ["#/meetings", "cal", "Meetings"], ["#/board", "board", "Action board"], ["#/knowledge", "book", "Knowledge"]];
const ROUTES = [[/^#\/(overview)?$/, viewOverview, "#/overview"], [/^#\/meetings$/, viewMeetings, "#/meetings"], [/^#\/meeting\/(\d+)$/, viewMeeting, "#/meetings"], [/^#\/board$/, viewBoard, "#/board"], [/^#\/knowledge$/, viewKB, "#/knowledge"]];
let navToken = 0;

function buildChrome() {
  $("#logo").innerHTML = ic("swap");
  $("#nav").innerHTML = NAV.map(([h, i, l]) => `<a href="${h}" data-nav="${h}">${ic(i)}<span>${l}</span></a>`).join("");
  setTheme(localStorageGet("theme") || "dark");
  $("#themeBtn").addEventListener("click", () => setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"));
}
function localStorageGet(k) { try { return localStorage.getItem(k); } catch { return null; } }
function setTheme(t) {
  document.documentElement.dataset.theme = t;
  try { localStorage.setItem("theme", t); } catch { /* private mode */ }
  $("#themeBtn").innerHTML = `${ic(t === "dark" ? "sun" : "moon")}<span>${t === "dark" ? "Light mode" : "Dark mode"}</span>`;
}

function authScreen(setupRequired, error = "") {
  const root = $("#auth"); root.hidden = false;
  root.innerHTML = `<div class="glass auth-card"><div class="brand"><span class="logo">${ic("swap")}</span>FlowMind</div>
    <span class="badge violet">${setupRequired ? "First-time setup" : "Team workspace"}</span>
    <h1 class="grad">${setupRequired ? "Create your admin account" : "Welcome back"}</h1>
    <p class="muted">${setupRequired ? "This account manages access for your FlowMind workspace." : "Sign in to continue to your team workspace."}</p>
    ${error ? `<div class="auth-error" role="alert">${esc(error)}</div>` : ""}
    <form data-auth-form="${setupRequired ? "setup" : "login"}" class="auth-form">
      ${setupRequired ? `<div class="field"><label for="auth-name">Your name</label><input id="auth-name" name="name" required minlength="2" maxlength="100" autocomplete="name" placeholder="Your name"></div>` : ""}
      <div class="field"><label for="auth-email">Email</label><input id="auth-email" name="email" required type="email" maxlength="254" autocomplete="email" placeholder="you@company.com"></div>
      <div class="field"><label for="auth-password">Password</label><input id="auth-password" name="password" required type="password" minlength="${setupRequired ? "12" : "1"}" maxlength="128" autocomplete="${setupRequired ? "new-password" : "current-password"}" placeholder="${setupRequired ? "At least 12 characters" : "Your password"}"></div>
      <button class="btn primary" type="submit">${setupRequired ? "Create admin account" : "Sign in"}${ic("arrow")}</button>
    </form><p class="xs faint">Passwords are stored as one-way salted hashes. Sessions use secure, HttpOnly cookies.</p>
  </div>`;
}
async function initializeAuth() {
  try {
    const status = await api("/auth/status");
    if (status.authenticated) { S.user = status.user; authReady(); }
    else authScreen(status.setup_required);
  } catch (e) { authScreen(false, `${e.message}. Refresh the page to retry.`); }
}
function authReady() {
  $("#auth").hidden = true;
  const account = $("#accountBox");
  account.innerHTML = `<div class="account-user"><span class="avatar">${esc(initials(S.user.name))}</span><span class="account-name"><b>${esc(S.user.name)}</b><small>${esc(S.user.role)} · ${esc(S.user.email)}</small></span></div>
    ${S.user.role === "admin" ? `<button class="btn sm account-manage" data-auth-action="users" type="button">${ic("users")}Manage accounts</button>` : ""}
    <button class="btn sm account-logout" data-auth-action="logout" type="button">Sign out</button>`;
  route();
}
document.addEventListener("submit", (e) => {
  const form = e.target.closest("[data-auth-form]"); if (!form) return;
  e.preventDefault(); const data = Object.fromEntries(new FormData(form));
  const endpoint = form.dataset.authForm === "setup" ? "/auth/setup" : "/auth/login";
  const button = $("[type=submit]", form); button.classList.add("loading");
  api(endpoint, { method: "POST", body: data }).then((user) => { S.user = user; authReady(); })
    .catch((err) => authScreen(form.dataset.authForm === "setup", err.message))
    .finally(() => button.classList.remove("loading"));
});
document.addEventListener("click", async (e) => {
  const action = e.target.closest("[data-auth-action]")?.dataset.authAction;
  if (action === "logout") {
    await api("/auth/logout", { method: "POST", body: {} }); S.user = null; authScreen(false);
  }
  if (action === "users") await openUserManager();
});
async function openUserManager() {
  const users = await api("/auth/users");
  const rows = users.map((u) => `<div class="user-row"><div class="grow"><b>${esc(u.name)}</b><div class="xs muted">${esc(u.email)} · ${esc(u.role)} · ${u.active ? "Active" : "Disabled"}</div></div>
    ${u.id === S.user.id ? `<span class="badge">You</span>` : `<button class="btn sm" data-user-toggle="${u.id}" data-active="${u.active}" type="button">${u.active ? "Disable" : "Enable"}</button>`}</div>`).join("");
  openSheet(`${sheetHead("Workspace accounts", "Admins can add or disable team accounts.")}
    <div class="user-list">${rows || empty("No accounts", "Create the first member account below.")}</div>
    <form data-auth-form="create-user" class="auth-form mt"><div class="grid-2"><div class="field"><label>Name</label><input name="name" required minlength="2" maxlength="100"></div><div class="field"><label>Email</label><input name="email" required type="email" maxlength="254"></div></div>
    <div class="grid-2 mt-s"><div class="field"><label>Temporary password</label><input name="password" required type="password" minlength="12" maxlength="128"></div><div class="field"><label>Role</label><select name="role"><option value="member">Member</option><option value="admin">Admin</option></select></div></div><button class="btn primary" type="submit">Create account</button></form>`, { wide: true });
}
document.addEventListener("submit", (e) => {
  const form = e.target.closest('[data-auth-form="create-user"]'); if (!form) return;
  e.preventDefault(); busy($("[type=submit]", form), async () => { await api("/auth/users", { method: "POST", body: Object.fromEntries(new FormData(form)) }); toast("Account created"); await openUserManager(); });
});
document.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-user-toggle]"); if (!btn) return;
  await busy(btn, async () => { await api(`/auth/users/${btn.dataset.userToggle}`, { method: "PATCH", body: { active: btn.dataset.active !== "true" } }); await openUserManager(); });
});

async function route() {
  const token = ++navToken, hash = location.hash || "#/overview";
  const hit = ROUTES.find(([re]) => re.test(hash));
  const [, handler, navKey] = hit || ROUTES[0];
  const m = hit ? hash.match(hit[0]) : [];
  $$("#nav a").forEach((a) => { const on = a.dataset.nav === navKey; a.classList.toggle("active", on); if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
  const v = $("#view");
  if (!S.first) { v.classList.add("leaving"); await sleep(reduceMotion() ? 0 : 170); }
  S.route = () => handler(m);
  try {
    const out = await handler(m);
    if (token !== navToken) return;
    v.innerHTML = out.html; v.classList.remove("leaving", "entering"); void v.offsetWidth; v.classList.add("entering");
    window.scrollTo({ top: 0 }); out.after && out.after();
  } catch (e) {
    if (token !== navToken) return;
    v.classList.remove("leaving");
    v.innerHTML = `<div class="glass card mt">${empty("We couldn't load this page", e.message)}<div class="row" style="justify-content:center"><button class="btn primary" data-act="retry" type="button">Try again</button></div></div>`;
  }
  S.first = false;
}
async function rerender() { // refresh current view in place (no page transition)
  if (!S.route) return;
  const y = window.scrollY;
  try { const out = await S.route(); $("#view").innerHTML = out.html; window.scrollTo({ top: y }); out.after && out.after(); } catch (e) { toast(e.message, "err"); }
}
const mutated = async (msg) => { S.readiness = {}; if (msg) toast(msg); await rerender(); };

// ───────────────────────── shared bits
function countUp(root = document) {
  $$("[data-count]", root).forEach((el) => {
    const to = +el.dataset.count; if (reduceMotion() || to === 0) { el.textContent = to; return; }
    const t0 = performance.now(), dur = 1100;
    const tick = (t) => { const p = Math.min(1, (t - t0) / dur); el.textContent = Math.round(to * (1 - Math.pow(2, -10 * p))); if (p < 1) requestAnimationFrame(tick); else el.textContent = to; };
    requestAnimationFrame(tick);
  });
}
function placeThumb(seg) {
  const on = $("button.on", seg), th = $(".thumb", seg); if (!on || !th) return;
  th.style.width = on.offsetWidth + "px"; th.style.transform = `translateX(${on.offsetLeft}px)`;
}
const segHTML = (name, opts, cur) => `<div class="seg" data-seg="${name}"><span class="thumb"></span>${opts.map(([v, l]) => `<button type="button" class="${v === cur ? "on" : ""}" data-act="seg" data-name="${name}" data-v="${v}">${l}</button>`).join("")}</div>`;
function updateAIChip(ai) {
  $("#aiChip").innerHTML = ai.configured ? `<span class="dot on"></span><span>AI ready · ${esc(ai.model)}</span>` : `<span class="dot warn"></span><span>AI key missing · rule-based mode</span>`;
}
const personSelect = (id, sel = "", blank = "Anyone") => `<select id="${id}"><option value="">${blank}</option>${S.people.map((p) => `<option ${p === sel ? "selected" : ""}>${esc(p)}</option>`).join("")}</select>`;

// ───────────────────────── Overview
async function viewOverview() {
  const [d, people] = await Promise.all([api("/dashboard"), api("/people")]);
  S.people = people; updateAIChip(d.ai);
  const hr = new Date().getHours(), hello = hr < 12 ? "Good morning." : hr < 18 ? "Good afternoon." : "Good evening.";
  const stat = (n, label, c) => `<div class="glass stat" style="--c:${c}"><div class="num" data-count="${n}">0</div><div class="lbl">${label}</div></div>`;
  const max = Math.max(1, ...d.by_owner.map((o) => o.count));
  const html = `
  <section class="hero"><p class="muted">${new Date().toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" })}</p>
    <h1 class="grad" style="margin-top:8px">${hello}<br>Here’s where work stands.</h1>
    <p class="sub">Every decision and open item across your team, in one place, with nothing falling through the cracks.</p>
    <div class="row wrap mt"><button class="btn primary" data-act="new-meeting" type="button">${ic("plus")}New meeting</button><a class="btn" href="#/board">${ic("board")}Open action board</a></div></section>
  <div class="stats stagger">${stat(d.open, "Open items", "var(--blue)")}${stat(d.overdue, "Overdue", "var(--red)")}${stat(d.unowned, "Without an owner", "var(--amber)")}${stat(d.done, "Closed with an outcome", "var(--green)")}</div>
  <div class="cols">
    <div class="glass card"><div class="sec-h"><h2>Needs attention</h2><span class="badge ${d.attention.length ? "amber" : "green"}">${d.attention.length ? d.attention.length + " items" : "All clear"}</span></div>
      ${d.attention.length ? d.attention.map((i) => `<div class="item-line" data-act="item" data-id="${i.id}" style="cursor:pointer"><div class="grow"><div class="t-title">${esc(i.title)}</div><div class="xs muted" style="margin-top:3px">${esc(i.meeting_title)}</div></div><div class="hide-m">${dueBadge(i)}</div>${ownerBadge(i.owner)}${i.owner ? `<button class="btn sm icon" data-act="nudge" data-id="${i.id}" type="button" title="Draft a reminder" aria-label="Draft a reminder">${ic("bell")}</button>` : ""}</div>`).join("") : empty("Nothing is slipping", "Every open item has an owner and is on schedule.")}</div>
    <div class="glass card"><div class="sec-h"><h2>Open work by person</h2></div>
      ${d.by_owner.length ? d.by_owner.map((o) => `<div class="item-line">${avatar(o.owner, "lg")}<div class="grow"><div class="row between"><b>${esc(o.owner)}</b><span class="muted small">${o.count} open</span></div><div class="bar mt-s"><i style="--w:${(o.count / max) * 100}%" data-w="${(o.count / max) * 100}"></i></div></div>${o.owner !== "Unassigned" ? `<button class="btn sm" data-act="handover" data-owner="${esc(o.owner)}" type="button" title="Out of office? Move their work to someone else">${ic("swap")}Hand over</button>` : ""}</div>`).join("") : empty("No open work", "Create a meeting to get started.")}</div>
  </div>`;
  return { html, after: () => { countUp($("#view")); requestAnimationFrame(() => $$(".bar > i").forEach((b) => (b.style.width = b.dataset.w + "%"))); } };
}

// ───────────────────────── Meetings list
async function viewMeetings() {
  const list = await api("/meetings"); S.meetingsAll = list;
  const html = `<div class="head"><div><h1 class="grad">Meetings</h1><p class="sub">Meetings and handovers, with everything decided and still open.</p></div>
    <div class="row wrap"><div class="search">${ic("search")}<input id="mq" placeholder="Search meetings" value="${esc(S.mq)}" aria-label="Search meetings"></div><button class="btn primary" data-act="new-meeting" type="button">${ic("plus")}New</button></div></div>
    <div style="margin-bottom:22px">${segHTML("mf", [["all", "All"], ["planned", "Planned"], ["held", "Held"], ["closed", "Closed"]], S.mf)}</div>
    <div class="mgrid stagger" id="mlist"></div>`;
  return { html, after: () => { renderMeetingList(); placeThumb($('[data-seg="mf"]')); } };
}
function renderMeetingList() {
  const q = S.mq.trim().toLowerCase();
  const list = (S.meetingsAll || []).filter((m) => (S.mf === "all" || m.status === S.mf) && (!q || m.title.toLowerCase().includes(q)));
  $("#mlist").innerHTML = list.length ? list.map((m, i) => {
    const pct = m.total_items ? Math.round(((m.total_items - m.open_items) / m.total_items) * 100) : 0;
    return `<a class="glass hover mcard" href="#/meeting/${m.id}" style="--i:${Math.min(i, 10)}">
      <div class="row between"><div class="row">${typeBadge(m.type)}</div>${mStatusBadge(m.status)}</div>
      <div><h3>${esc(m.title)}</h3><p class="muted small" style="margin-top:6px">${fmtLong(m.date)} · ${relDay(m.date)}</p></div>
      <div class="foot"><span class="muted small">${m.open_items} open · ${m.decision_count} decision${m.decision_count === 1 ? "" : "s"}</span><span class="muted small">${m.participant_count} ${ic("users").replace("<svg", '<svg style="width:14px;vertical-align:-2px"')}</span></div>
      ${m.total_items ? `<div class="bar"><i style="width:${pct}%"></i></div>` : ""}</a>`;
  }).join("") : `<div class="glass card" style="grid-column:1/-1">${empty("No meetings match", "Try another filter, or create a new meeting.")}</div>`;
}

// ───────────────────────── Meeting detail
async function viewMeeting([, id]) {
  const [m, people, all] = await Promise.all([api(`/meetings/${id}`), api("/people"), api("/meetings")]);
  S.people = people; S.meeting = m; S.meetingsAll = all;
  return { html: meetingHTML(m), after: () => afterMeeting(m) };
}
const STEPS = ["planned", "held", "closed"];
function meetingHTML(m) {
  const si = STEPS.indexOf(m.status), next = STEPS[si + 1];
  const open = m.action_items.filter((i) => ["open", "in_progress"].includes(i.status));
  const stepper = `<div class="stepper">${STEPS.map((s, i) => `${i ? '<span class="bar-s"></span>' : ""}<span class="s ${i < si ? "done" : i === si ? "on" : ""}"><i></i>${s[0].toUpperCase() + s.slice(1)}</span>`).join("")}</div>`;
  const items = m.action_items.map(taskHTML).join("") || empty("No action items yet", "Add one below, or generate them from your notes.");
  const draft = S.drafts[m.id] ?? m.notes;
  return `${peopleList()}
  <a class="back" href="#/meetings">${ic("arrow")}All meetings</a>
  <div class="head"><div><div class="row wrap" style="margin-bottom:12px">${typeBadge(m.type)}${stepper}</div>
      <h1 class="grad" style="font-size:clamp(1.9rem,4vw,2.9rem)">${esc(m.title)}</h1><p class="sub" style="margin-top:8px">${fmtLong(m.date)} · ${relDay(m.date)}</p></div>
    <div class="row wrap"><button class="btn ai" data-act="brief" type="button">${ic("spark")}Catch-up brief</button>
      ${open.length ? `<button class="btn" data-act="carry" type="button">${ic("arrow")}Carry forward</button>` : ""}
      <button class="btn icon" data-act="edit-meeting" type="button" title="Edit details" aria-label="Edit details">${ic("edit")}</button>
      ${next ? `<button class="btn primary" data-act="advance" data-to="${next}" type="button">${next === "held" ? "Mark as held" : "Close meeting"}</button>` : ""}</div></div>
  <div class="detail"><div class="stagger">
    <section class="glass sec"><div class="sec-h"><h2>Overview</h2></div>
      ${m.summary ? `<p>${esc(m.summary)}</p>` : `<p class="muted">No summary yet. Paste your notes below and let AI write one.</p>`}
      ${m.agenda ? `<h3 class="muted small mt">Agenda</h3><p class="pre mt-s">${esc(m.agenda)}</p>` : ""}</section>
    <section class="glass sec"><div class="sec-h"><div><h2>Notes → structured recap</h2><p class="muted small">Paste raw notes, chat or a transcript. You review everything before it’s saved.</p></div></div>
      <textarea id="notes" data-draft="${m.id}" placeholder="e.g. Priya will send the beta build by Friday. We decided to ship refunds behind a flag…" style="min-height:150px">${esc(draft)}</textarea>
      <div class="row between wrap mt-s"><div class="row wrap"><input id="notes-upload" type="file" accept=".txt,.md,.pdf,.zip" multiple hidden>
        <label class="btn sm" for="notes-upload">${ic("doc")}Upload rough notes</label><span class="xs muted">TXT, MD, PDF or a ZIP bundle</span></div>
        <button class="btn ai" data-act="recap" type="button">${ic("spark")}Generate recap</button></div></section>
    <section class="glass sec"><div class="sec-h"><h2>Decisions</h2><span class="badge">${m.decisions.length}</span></div>
      ${m.decisions.map((d) => `<div class="dec">${ic("check")}<div class="grow">${esc(d.text)}</div><button class="x" data-act="del-decision" data-id="${d.id}" type="button" aria-label="Remove decision">${ic("x")}</button></div>`).join("") || `<p class="muted">Nothing recorded yet.</p>`}
      <form data-form="add-decision" class="row mt-s"><input name="text" placeholder="Record a decision" required minlength="3" aria-label="New decision"><button class="btn" type="submit">${ic("plus")}Add</button></form></section>
    <section class="glass sec"><div class="sec-h"><h2>Action items</h2><span class="badge blue">${open.length} open</span></div>${items}
      <form data-form="add-item" class="grid-2 mt-s" style="grid-template-columns:1.6fr 1fr 1fr 1fr auto;align-items:end">
        <div class="field"><label>New action item</label><input name="title" required minlength="3" placeholder="What needs to happen?"></div>
        <div class="field"><label>Owner</label><input name="owner" list="people" placeholder="Who?"></div>
        <div class="field"><label>Due</label><input name="due_date" type="date" min="${isoToday()}"></div>
        <div class="field"><label>Priority</label><select name="priority"><option value="medium">Medium</option><option value="low">Low</option><option value="high">High</option><option value="urgent">Urgent</option></select></div>
        <button class="btn primary" type="submit">${ic("plus")}Add</button>
        <div class="field" style="grid-column:1/-1"><label>Blocker / handover context (optional)</label><input name="blocker" maxlength="1000" placeholder="What is blocking progress or what should the next person know?"></div></form></section>
  </div>
  <div class="side-col">
    <section class="glass sec" id="ready-card">${S.readiness[m.id] ? readinessHTML(S.readiness[m.id]) : readinessEmpty()}</section>
    <section class="glass sec"><div class="sec-h"><h2>People</h2><span class="badge">${m.participants.length}</span></div>
      ${m.participants.map((p) => `<div class="person">${avatar(p.name, "lg")}<div class="grow"><b>${esc(p.name)}</b><div><button class="badge ${{ accepted: "green", declined: "red", pending: "" }[p.rsvp]}" data-act="rsvp" data-id="${p.id}" data-v="${p.rsvp}" type="button" style="cursor:pointer" title="Click to change RSVP">${p.rsvp}</button></div></div><div class="col" style="align-items:center;gap:3px"><button class="switch ${p.attended ? "on" : ""}" role="switch" aria-checked="${p.attended}" aria-label="Attended: ${esc(p.name)}" data-act="attend" data-id="${p.id}" data-v="${p.attended}" type="button"></button><span class="xs faint">attended</span></div></div>`).join("") || `<p class="muted">No participants yet.</p>`}
      <form data-form="add-person" class="row mt-s"><input name="name" placeholder="Add a person" required list="people" aria-label="Add participant"><button class="btn icon" type="submit" aria-label="Add participant">${ic("plus")}</button></form></section>
  </div></div>`;
}
function taskHTML(i) {
  const closed = ["done", "dropped"].includes(i.status);
  return `<div class="task ${closed ? "closed" : ""} ${i.status === "carried" ? "carried" : ""}" data-act="item" data-id="${i.id}">
    ${i.status === "carried" ? "" : `<button class="check ${i.status === "done" ? "done" : ""}" data-act="toggle" data-id="${i.id}" data-s="${i.status}" type="button" aria-label="${i.status === "done" ? "Reopen" : "Mark done"}">${ic("check")}</button>`}
    <div class="grow"><div class="t-title">${esc(i.title)}</div><div class="t-meta">${ownerBadge(i.owner)}${dueBadge(i)}${priorityBadge(i.priority)}${itemBadge(i.status)}
      ${i.carried ? `<span class="badge">${ic("arrow")}Carried over</span>` : ""}${i.links.length ? `<span class="badge violet">${ic("link")}${i.links.length} doc${i.links.length > 1 ? "s" : ""}</span>` : ""}</div>
      ${i.outcome ? `<p class="xs muted" style="margin-top:6px">Outcome: ${esc(i.outcome)}</p>` : ""}</div></div>`;
}
function priorityBadge(p) { const labels = { urgent: "Urgent", high: "High priority", medium: "Medium", low: "Low" }; return `<span class="badge priority-${p || "medium"}">${labels[p] || "Medium"}</span>`; }
function afterMeeting(m) {
  if (S.readiness[m.id]) animateRing($("#ready-card"));
}
const readinessEmpty = () => `<div class="sec-h"><h2>Context Health</h2></div><p class="muted small">Checks ownership, dates, blockers, carry-forward history, decisions, links and scope. AI suggests what to fix first.</p><button class="btn ai mt-s" data-act="ready" type="button" style="width:100%">${ic("shield")}Check context health</button>`;
function readinessHTML(r) {
  const col = r.score < 50 ? "var(--red)" : r.score < 80 ? "var(--amber)" : "var(--green)";
  const a = r.advice;
  return `<div class="sec-h"><h2>Context Health</h2><button class="btn sm" data-act="ready" type="button">Re-check</button></div>
  <div class="ring-wrap" style="--ring-c:${col}"><svg class="ring" viewBox="0 0 128 128" aria-hidden="true"><circle class="track" cx="64" cy="64" r="56"/><circle class="prog" cx="64" cy="64" r="56" stroke="${col}" data-score="${r.score}"/></svg>
    <div class="ring-num"><b data-count="${r.score}">0</b><span>out of 100</span></div></div>
  <p style="font-weight:600;text-align:center;margin:8px 0 12px">${esc(a.verdict)}</p>${aiBadge(a)}
  ${r.checks.map((c) => `<div class="chk ${c.ok ? "ok" : "bad"}">${ic(c.ok ? "check" : "info")}<div class="grow">${esc(c.label)}${!c.ok && c.detail ? `<div class="xs faint">${esc(c.detail)}</div>` : ""}</div><span class="xs faint">${c.earned}/${c.weight}</span></div>`).join("")}
  ${a.fixes.length ? `<h3 class="small muted mt">Fix first</h3>${a.fixes.map((f, i) => `<div class="fix"><b>${i + 1}.</b> ${esc(f)}</div>`).join("")}` : ""}`;
}
function animateRing(card) {
  if (!card) return; const p = $(".prog", card); if (!p) return;
  const C = 2 * Math.PI * 56, score = +p.dataset.score;
  p.style.strokeDasharray = C; p.style.strokeDashoffset = C;
  requestAnimationFrame(() => requestAnimationFrame(() => { p.style.strokeDashoffset = C * (1 - score / 100); }));
  countUp(card);
}

// ───────────────────────── Board
async function viewBoard() {
  const [items, people] = await Promise.all([api("/action-items"), api("/people")]);
  S.people = people; S.boardItems = items.filter((i) => i.status !== "carried");
  const owners = ["all", ...new Set(S.boardItems.map((i) => i.owner).filter(Boolean))];
  const html = `${peopleList()}<div class="head"><div><h1 class="grad">Action board</h1><p class="sub">Drag cards between columns. Closing an item asks for its outcome.</p></div><div class="row wrap"><a class="btn" href="/api/reports/action-items.csv">Export tasks CSV</a><a class="btn" href="/api/reports/meetings.csv">Export meetings CSV</a></div></div>
    <div class="chips" style="margin-bottom:20px">${owners.map((o) => `<button class="chip ${S.bf === o ? "on" : ""}" data-act="bf" data-v="${esc(o)}" type="button">${o === "all" ? "Everyone" : esc(o)}</button>`).join("")}</div><div class="board stagger" id="board"></div>`;
  return { html, after: renderBoard };
}
const LANES = [["open", "Open", "blue"], ["in_progress", "In progress", "violet"], ["done", "Done", "green"], ["dropped", "Dropped", ""]];
function renderBoard() {
  const list = S.boardItems.filter((i) => S.bf === "all" || i.owner === S.bf);
  $("#board").innerHTML = LANES.map(([k, label, c], li) => {
    const col = list.filter((i) => i.status === k);
  return `<div class="glass lane" data-lane="${k}" style="--i:${li}"><h3>${label}<span class="badge ${c}">${col.length}</span></h3>
      ${col.map((i) => `<div class="kc" draggable="true" data-act="item" data-id="${i.id}"><div class="t-title" style="font-size:14px">${esc(i.title)}</div><div class="row wrap" style="margin:5px 0 10px">${priorityBadge(i.priority)}${i.blocker ? '<span class="badge amber">Blocked</span>' : ''}</div><div class="xs faint" style="margin:4px 0 10px">${esc(i.meeting_title)}</div><div class="row between">${i.owner ? avatar(i.owner) : '<span class="badge amber">Unassigned</span>'}${dueBadge(i)}</div></div>`).join("") || `<p class="xs faint" style="padding:10px 6px">Drop items here</p>`}</div>`;
  }).join("");
}

// ───────────────────────── Knowledge
async function viewKB() {
  const docs = await api("/kb"); S.kb = docs;
  const html = `<div class="head"><div><h1 class="grad">Knowledge</h1><p class="sub">Ask questions across team documents and closed meetings. Answers show the passages they came from.</p></div>
    <div class="row wrap"><div class="search">${ic("search")}<input id="kq" placeholder="Search knowledge" value="${esc(S.kq)}" aria-label="Search knowledge"></div><button class="btn primary" data-act="new-kb" type="button">${ic("plus")}Add document</button></div></div>
    <section class="glass card kb-ask"><div class="row between wrap"><div><h2>Ask FlowMind</h2><p class="muted small">Answers are grounded in retrieved knowledge base passages.</p></div><span class="badge violet">RAG · semantic search</span></div>
      <form data-form="ask-kb" class="row wrap mt-s"><div class="field grow"><label for="kb-question">Your question</label><input id="kb-question" name="question" required minlength="3" maxlength="1200" placeholder="Where can I find the billing retry policy?"></div><button class="btn ai" type="submit">${ic("spark")}Ask</button></form>
      <div id="kb-answer" class="kb-answer" aria-live="polite"></div></section><div class="mgrid stagger" id="klist"></div>`;
  return { html, after: renderKB };
}
function renderKB() {
  const q = S.kq.trim().toLowerCase();
  const list = S.kb.filter((d) => !q || (d.title + d.content).toLowerCase().includes(q));
  $("#klist").innerHTML = list.length ? list.map((d, i) => `<div class="glass hover mcard" data-act="kb-open" data-id="${d.id}" style="--i:${Math.min(i, 10)}"><div class="row between"><span class="ic">${ic(d.type === "doc" ? "doc" : "cal")}</span><span class="badge ${d.type === "doc" ? "blue" : "violet"}">${d.type === "doc" ? "Document" : "Past meeting"}</span></div>
    <div><h3>${esc(d.title)}</h3><p class="muted small" style="margin-top:8px;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden">${esc(d.content)}</p></div><div class="foot"><span class="muted small">${d.linked_items} linked item${d.linked_items === 1 ? "" : "s"}</span></div></div>`).join("") : `<div class="glass card" style="grid-column:1/-1">${empty("Nothing found", "Add a document to grow your team’s memory.")}</div>`;
}

// ───────────────────────── Sheets: item, outcome, nudge
async function openItem(id) {
  const it = await api(`/action-items/${id}`);
  const closed = ["done", "dropped"].includes(it.status);
  const sheet = openSheet(`${sheetHead(it.title, `${esc(it.meeting_title)} · ${itemBadge(it.status)}`)}${peopleList()}
    <form data-form="save-item" data-id="${it.id}"><div class="grid-2">${field("Owner", `<input name="owner" list="people" value="${esc(it.owner)}" placeholder="Unassigned">`)}${field("Due date", `<input name="due_date" type="date" value="${it.due_date || ""}">`)}</div>
      <div class="grid-2 mt-s">${field("Priority", `<select name="priority">${["low", "medium", "high", "urgent"].map((p) => `<option value="${p}" ${p === it.priority ? "selected" : ""}>${p[0].toUpperCase() + p.slice(1)}</option>`).join("")}</select>`)}${field("Blocker / handover context", `<input name="blocker" maxlength="1000" value="${esc(it.blocker || "")}" placeholder="What should the next person know?">`)}</div>
      <div class="grid-2 mt-s">${field("Status", `<select name="status">${["open", "in_progress", "done", "dropped"].map((s) => `<option value="${s}" ${s === it.status ? "selected" : ""}>${STATUS[s][0]}</option>`).join("")}</select>`)}${field("Note for history (optional)", `<input name="note" maxlength="500" placeholder="e.g. Kabir on leave">`)}</div>
      <div class="mt-s">${field("Outcome (required to close)", `<textarea name="outcome" style="min-height:76px" placeholder="What happened? e.g. Shipped in v2.3, approved by finance">${esc(it.outcome)}</textarea>`)}</div>
      <div class="sheet-f">${!closed && it.owner ? `<button class="btn" data-act="nudge" data-id="${it.id}" type="button">${ic("bell")}Draft reminder</button>` : ""}<button class="btn" data-act="linkkb" data-id="${it.id}" type="button">${ic("link")}Find related docs</button><button class="btn primary" type="submit">Save changes</button></div></form>
    <div id="kb-links" class="mt">${kbLinksHTML(it.links)}</div>
    <h3 class="mt muted small">History</h3><div class="tl">${it.history.map((h) => `<div class="ev ${h.event}"><b>${esc(h.event.replace(/_/g, " "))}</b>${h.old || h.new ? ` <span class="muted">${esc(h.old)}${h.old && h.new ? " → " : ""}${esc(h.new)}</span>` : ""}${h.note ? `<div class="xs muted">${esc(h.note)}</div>` : ""}<div class="xs faint">${new Date(h.at + "Z").toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</div></div>`).join("")}</div>`, { wide: true });
  sheet.dataset.itemId = it.id;
}
const kbLinksHTML = (links) => links.length ? `<h3 class="muted small">Related knowledge</h3>${links.map((l) => `<div class="fix"><b>${esc(l.title)}</b> <span class="badge ${l.source === "ai" ? "violet" : ""}">${l.source === "ai" ? "Gemini" : l.source === "semantic" ? "Semantic" : "Keyword"}</span><div class="xs muted" style="margin-top:3px">${esc(l.reason)}</div></div>`).join("")}` : "";
function outcomeSheet(it, status) {
  openSheet(`${sheetHead(status === "done" ? "Close this item" : "Drop this item", esc(it.title))}
    <form data-form="close-item" data-id="${it.id}" data-status="${status}">${field("What was the outcome?", `<textarea name="outcome" required minlength="3" style="min-height:96px" placeholder="A few words is enough, e.g. Shipped behind a flag; finance approved the limit."></textarea>`)}
    <div class="sheet-f"><button class="btn" data-act="close" type="button">Cancel</button><button class="btn primary" type="submit">${status === "done" ? "Mark done" : "Drop item"}</button></div></form>`);
}
async function nudgeFlow(id, btn) {
  const r = await busy(btn, () => api(`/action-items/${id}/nudge`, { method: "POST" })); if (!r) return;
  openSheet(`${sheetHead("Reminder draft", "Edit it, then copy it into chat or email.")}${aiBadge(r)}<textarea id="nudge-text" style="min-height:140px">${esc(r.message)}</textarea>
    <div class="sheet-f"><button class="btn" data-act="close" type="button">Close</button><button class="btn primary" data-act="copy" type="button">${ic("copy")}Copy message</button></div>`);
}

// ───────────────────────── Sheets: meeting create/edit, recap, brief, carry, handover, kb
function newMeetingSheet() {
  openSheet(`${sheetHead("New meeting or handover", "Capture the agenda now; add notes and decisions afterwards.")}
  <form data-form="new-meeting"><div class="col">${field("Title", `<input name="title" required minlength="3" maxlength="200" placeholder="e.g. Sprint 43 planning">`)}
    <div class="grid-2">${field("Type", `<select name="type"><option value="meeting">Meeting</option><option value="handover">Work handover</option></select>`)}${field("Date", `<input name="date" type="date" required value="${isoToday(1)}">`)}</div>
    ${field("Agenda", `<textarea name="agenda" style="min-height:90px" placeholder="What will you cover?"></textarea>`)}
    ${field("Participants (comma separated)", `<input name="people" placeholder="Aarav, Priya, Rohan">`)}</div>
    <div class="sheet-f"><button class="btn" data-act="close" type="button">Cancel</button><button class="btn primary" type="submit">Create</button></div></form>`);
}
function editMeetingSheet() {
  const m = S.meeting;
  openSheet(`${sheetHead("Edit details")}<form data-form="edit-meeting"><div class="col">${field("Title", `<input name="title" required minlength="3" value="${esc(m.title)}">`)}${field("Date", `<input name="date" type="date" required value="${m.date}">`)}
    ${field("Agenda", `<textarea name="agenda" style="min-height:90px">${esc(m.agenda)}</textarea>`)}${field("Summary", `<textarea name="summary" style="min-height:90px">${esc(m.summary)}</textarea>`)}</div>
    <div class="sheet-f"><button class="btn" data-act="close" type="button">Cancel</button><button class="btn primary" type="submit">Save</button></div></form>`);
}
function recapSheet(r) {
  const rc = r.recap;
  const row = (i = {}) => `<div class="edit-row"><input class="rv-t" value="${esc(i.title || "")}" placeholder="Action item" aria-label="Action item"><input class="rv-o" list="people" value="${esc(i.owner || "")}" placeholder="Owner" aria-label="Owner"><input class="rv-d" type="date" value="${i.due_date || ""}" aria-label="Due date"><button class="x" data-act="rm-row" type="button" aria-label="Remove">${ic("x")}</button></div>`;
  const dec = (t = "") => `<div class="row" style="margin-bottom:8px"><input class="rv-dec" value="${esc(t)}" placeholder="Decision" aria-label="Decision"><button class="x" data-act="rm-row" type="button" aria-label="Remove">${ic("x")}</button></div>`;
  openSheet(`${sheetHead("Review the recap", "Nothing is saved until you confirm. Edit anything.")}${peopleList()}${aiBadge(r)}
    ${field("Summary", `<textarea id="rv-summary" style="min-height:90px">${esc(rc.summary)}</textarea>`)}
    <h3 class="mt muted small">Decisions</h3><div id="rv-decs" class="mt-s">${rc.decisions.map(dec).join("")}</div><button class="btn sm" data-act="add-dec-row" type="button">${ic("plus")}Add decision</button>
    <h3 class="mt muted small">Action items</h3><div id="rv-items" class="mt-s">${rc.action_items.map(row).join("")}</div><button class="btn sm" data-act="add-item-row" type="button">${ic("plus")}Add item</button>
    <div class="sheet-f"><button class="btn" data-act="close" type="button">Discard</button><button class="btn primary" data-act="apply-recap" type="button">Save to meeting</button></div>`, { wide: true });
  S._rowTpl = row; S._decTpl = dec;
}
async function briefSheet() {
  const m = S.meeting, names = [...new Set([...m.participants.map((p) => p.name), ...S.people])];
  openSheet(`${sheetHead("Catch-up brief", "A short, personal summary for someone who missed this or is taking over.")}
    ${field("Who is this for?", `<select id="brief-for"><option value="">Someone new to this work</option>${names.map((n) => `<option>${esc(n)}</option>`).join("")}</select>`)}<div id="brief-body" class="brief mt"></div>`, { wide: true });
  await loadBrief();
}
async function loadBrief() {
  const m = S.meeting, who = $("#brief-for").value, body = $("#brief-body");
  body.innerHTML = `<span class="think">${ic("spark")}Writing your brief…</span><div class="skeleton"></div><div class="skeleton" style="width:80%"></div><div class="skeleton" style="width:60%"></div>`;
  try {
    const r = await api(`/meetings/${m.id}/brief?for_person=${encodeURIComponent(who)}`), b = r.brief;
    const sec = (t, a) => a.length ? `<h3>${t}</h3><ul>${a.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : "";
    body.innerHTML = `${aiBadge(r)}<p class="headline">${esc(b.headline)}</p>${sec("What was decided", b.what_was_decided)}${sec("Still open", b.still_open)}${sec(who ? `${esc(who)}’s actions` : "Your actions", b.your_actions)}${sec("Watch out for", b.watch_out)}`;
  } catch (e) { body.innerHTML = empty("Couldn't build the brief", e.message); }
}
function carrySheet() {
  const m = S.meeting, open = m.action_items.filter((i) => ["open", "in_progress"].includes(i.status));
  const targets = (S.meetingsAll || []).filter((x) => x.id !== m.id && x.status !== "closed");
  openSheet(`${sheetHead("Carry open items forward", "Items move to the next meeting with their full history. The originals are marked as carried.")}
  <form data-form="carry"><div class="seg" style="margin-bottom:16px" data-seg="ct"><span class="thumb"></span><button type="button" class="on" data-act="ct" data-v="new">New follow-up</button><button type="button" data-act="ct" data-v="existing">Existing meeting</button></div>
    <div id="ct-new" class="grid-2">${field("Title", `<input name="new_title" value="Follow-up: ${esc(m.title)}">`)}${field("Date", `<input name="new_date" type="date" value="${isoToday(7)}" min="${isoToday()}">`)}</div>
    <div id="ct-existing" hidden>${field("Meeting", `<select name="target"><option value="">Choose a meeting…</option>${targets.map((t) => `<option value="${t.id}">${esc(t.title)} (${fmtDate(t.date)})</option>`).join("")}</select>`)}</div>
    <h3 class="mt muted small">Items to carry</h3><div class="mt-s">${open.map((i) => `<label class="row" style="padding:7px 4px;cursor:pointer"><input type="checkbox" name="ids" value="${i.id}" checked style="width:18px;height:18px"><span class="grow">${esc(i.title)}</span>${ownerBadge(i.owner)}</label>`).join("")}</div>
    <div class="sheet-f"><button class="btn" data-act="close" type="button">Cancel</button><button class="btn primary" type="submit">Carry forward</button></div></form>`);
  requestAnimationFrame(() => placeThumb($('[data-seg="ct"]')));
}
function handoverSheet(owner) {
  openSheet(`${sheetHead(`Hand over ${esc(owner)}’s work`, "Every open item they own moves to a new owner, with a history entry on each.")}
  <form data-form="handover"><input type="hidden" name="from" value="${esc(owner)}"><div class="col">${field("New owner", `<select name="to" required><option value="">Choose a person…</option>${S.people.filter((p) => p !== owner).map((p) => `<option>${esc(p)}</option>`).join("")}</select>`)}${field("Reason", `<input name="note" value="Owner on leave" maxlength="300">`)}</div>
    <div class="sheet-f"><button class="btn" data-act="close" type="button">Cancel</button><button class="btn primary" type="submit">Reassign all</button></div></form>`);
}
function kbSheet() {
  openSheet(`${sheetHead("Add to knowledge base", "Runbooks, policies, how-tos. Anything the team should be able to find.")}
  <form data-form="new-kb"><div class="col">${field("Title", `<input name="title" required minlength="3" maxlength="200">`)}${field("Type", `<select name="type"><option value="doc">Document</option><option value="past_meeting">Past meeting</option></select>`)}${field("Content", `<textarea name="content" required minlength="20" style="min-height:160px" placeholder="Paste the text (at least 20 characters)"></textarea>`)}</div>
    <div class="sheet-f"><button class="btn" data-act="close" type="button">Cancel</button><button class="btn primary" type="submit">Add</button></div></form>`);
}

// ───────────────────────── actions (click delegation)
const A = {
  close: () => closeSheet(),
  retry: () => route(),
  seg(el) { const { name, v } = el.dataset; if (name === "mf") S.mf = v; $$("button", el.parentElement).forEach((b) => b.classList.toggle("on", b === el)); placeThumb(el.parentElement); renderMeetingList(); },
  ct(el) { $$("button", el.parentElement).forEach((b) => b.classList.toggle("on", b === el)); placeThumb(el.parentElement); $("#ct-new").hidden = el.dataset.v !== "new"; $("#ct-existing").hidden = el.dataset.v !== "existing"; },
  bf(el) { S.bf = el.dataset.v; $$(".chip").forEach((c) => c.classList.toggle("on", c === el)); renderBoard(); },
  "new-meeting": newMeetingSheet, "edit-meeting": editMeetingSheet, carry: carrySheet, "new-kb": kbSheet,
  item: (el) => openItem(el.dataset.id),
  nudge: (el) => nudgeFlow(el.dataset.id, el),
  handover: (el) => handoverSheet(el.dataset.owner),
  brief: () => briefSheet(),
  copy(el) { const t = $("#nudge-text"); (navigator.clipboard ? navigator.clipboard.writeText(t.value) : Promise.reject()).then(() => toast("Copied to clipboard"), () => { t.select(); toast("Press Ctrl+C to copy", "err"); }); },
  async toggle(el) {
    const id = el.dataset.id, s = el.dataset.s;
    if (s === "done" || s === "dropped") return busy(el, async () => { await api(`/action-items/${id}`, { method: "PATCH", body: { status: "open" } }); await mutated("Reopened"); });
    const it = (S.meeting?.action_items || S.boardItems || []).find((i) => i.id == id); outcomeSheet(it, "done");
  },
  async advance(el) { await busy(el, async () => { await api(`/meetings/${S.meeting.id}`, { method: "PATCH", body: { status: el.dataset.to } }); await mutated(el.dataset.to === "held" ? "Marked as held" : "Meeting closed and saved to knowledge"); }); },
  async rsvp(el) { const nx = { pending: "accepted", accepted: "declined", declined: "pending" }[el.dataset.v]; await busy(el, async () => { await api(`/participants/${el.dataset.id}`, { method: "PATCH", body: { rsvp: nx } }); await mutated(); }); },
  async attend(el) { await busy(el, async () => { await api(`/participants/${el.dataset.id}`, { method: "PATCH", body: { attended: el.dataset.v !== "true" } }); await mutated(); }); },
  async "del-decision"(el) { await busy(el, async () => { await api(`/decisions/${el.dataset.id}`, { method: "DELETE" }); await mutated("Decision removed"); }); },
  async ready(el) {
    const m = S.meeting; const card = $("#ready-card");
    await busy(el, async () => { const r = await api(`/meetings/${m.id}/readiness`); S.readiness[m.id] = r; card.innerHTML = readinessHTML(r); animateRing(card); });
  },
  async recap(el) {
    const txt = $("#notes").value.trim(); if (txt.length < 20) return toast("Add a few more lines of notes first (at least 20 characters)", "err");
    await busy(el, async () => { const r = await api(`/meetings/${S.meeting.id}/recap`, { method: "POST", body: { raw_text: txt } }); delete S.drafts[S.meeting.id]; recapSheet(r); });
  },
  "add-dec-row": () => $("#rv-decs").insertAdjacentHTML("beforeend", S._decTpl()),
  "add-item-row": () => $("#rv-items").insertAdjacentHTML("beforeend", S._rowTpl()),
  "rm-row": (el) => el.parentElement.remove(),
  async "apply-recap"(el) {
    const body = { summary: $("#rv-summary").value.trim(), decisions: $$(".rv-dec").map((i) => i.value.trim()).filter(Boolean),
      action_items: $$("#rv-items .edit-row").map((r) => ({ title: $(".rv-t", r).value.trim(), owner: $(".rv-o", r).value.trim(), due_date: $(".rv-d", r).value || null })).filter((i) => i.title) };
    if (body.action_items.some((i) => i.title.length < 3)) return toast("Action item titles need at least 3 characters", "err");
    await busy(el, async () => { await api(`/meetings/${S.meeting.id}/recap/apply`, { method: "POST", body }); closeSheet(); await mutated("Recap saved to the meeting"); });
  },
  async linkkb(el) {
    await busy(el, async () => { const r = await api(`/action-items/${el.closest(".sheet").dataset.itemId}/link-kb`, { method: "POST" });
      $("#kb-links").innerHTML = aiBadge(r) + (r.links.length ? kbLinksHTML(r.links) : `<p class="muted small">${esc(r.notice || "No related documents found.")}</p>`); S.readiness = {}; });
  },
  "kb-open"(el) { const d = S.kb.find((x) => x.id == el.dataset.id); openSheet(`${sheetHead(d.title, `<span class="badge ${d.type === "doc" ? "blue" : "violet"}">${d.type === "doc" ? "Document" : "Past meeting"}</span>`)}<p class="pre" style="color:var(--text)">${esc(d.content)}</p>`, { wide: true }); },
};
document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-act]"); if (!el || !A[el.dataset.act]) return;
  e.stopPropagation(); A[el.dataset.act](el, e);
});

// ───────────────────────── forms (submit delegation)
const F = {
  async "ask-kb"(f, btn) {
    const result = await api("/kb/ask", { method: "POST", body: { question: new FormData(f).get("question") } });
    const sources = result.sources.map((s) => `<article class="kb-source"><div class="row between wrap"><b>${esc(s.title)}</b><span class="badge">${Math.round(s.score * 100)}% match</span></div><p class="small muted mt-s">${esc(s.excerpt)}</p></article>`).join("");
    $("#kb-answer").innerHTML = `${aiBadge(result)}<p class="kb-answer-text">${esc(result.answer)}</p>${sources ? `<h3 class="small muted mt-s">Sources</h3><div class="kb-sources">${sources}</div>` : ""}`;
  },
  async "new-meeting"(f, btn) {
    const d = Object.fromEntries(new FormData(f));
    const participants = (d.people || "").split(",").map((s) => s.trim()).filter(Boolean).map((name) => ({ name }));
    const m = await api("/meetings", { method: "POST", body: { title: d.title, type: d.type, date: d.date, agenda: d.agenda, participants } });
    closeSheet(); toast("Meeting created"); location.hash = `#/meeting/${m.id}`;
  },
  async "edit-meeting"(f) { const d = Object.fromEntries(new FormData(f)); await api(`/meetings/${S.meeting.id}`, { method: "PATCH", body: d }); closeSheet(); await mutated("Details updated"); },
  async "add-decision"(f) { await api(`/meetings/${S.meeting.id}/decisions`, { method: "POST", body: { text: new FormData(f).get("text") } }); await mutated("Decision recorded"); },
  async "add-person"(f) { await api(`/meetings/${S.meeting.id}/participants`, { method: "POST", body: { name: new FormData(f).get("name") } }); await mutated("Person added"); },
  async "add-item"(f) { const d = Object.fromEntries(new FormData(f)); await api(`/meetings/${S.meeting.id}/action-items`, { method: "POST", body: { title: d.title, owner: d.owner, due_date: d.due_date || null, priority: d.priority, blocker: d.blocker } }); await mutated("Action item added"); },
  async "save-item"(f) {
    const d = Object.fromEntries(new FormData(f)), id = f.dataset.id;
    await api(`/action-items/${id}`, { method: "PATCH", body: { owner: d.owner, due_date: d.due_date || null, priority: d.priority, blocker: d.blocker, status: d.status, outcome: d.outcome, note: d.note } });
    closeSheet(); await mutated(["done", "dropped"].includes(d.status) ? "Item closed with outcome" : "Saved");
  },
  async "close-item"(f) {
    await api(`/action-items/${f.dataset.id}`, { method: "PATCH", body: { status: f.dataset.status, outcome: new FormData(f).get("outcome") } });
    closeSheet(); await mutated("Item closed with outcome");
  },
  async carry(f) {
    const fd = new FormData(f), existing = !$("#ct-existing").hidden, ids = fd.getAll("ids").map(Number);
    if (!ids.length) throw new Error("Select at least one item to carry forward");
    const body = { item_ids: ids };
    if (existing) { if (!fd.get("target")) throw new Error("Choose a meeting to carry the items into"); body.target_meeting_id = +fd.get("target"); } else { body.new_title = fd.get("new_title"); body.new_date = fd.get("new_date"); }
    const r = await api(`/meetings/${S.meeting.id}/carry-forward`, { method: "POST", body });
    closeSheet(); toast(`${r.carried} item${r.carried > 1 ? "s" : ""} carried forward`); location.hash = `#/meeting/${r.target_meeting_id}`;
  },
  async handover(f) {
    const d = Object.fromEntries(new FormData(f)); const r = await api("/people/reassign", { method: "POST", body: { from_owner: d.from, to_owner: d.to, note: d.note } });
    closeSheet(); await mutated(`${r.reassigned} item${r.reassigned > 1 ? "s" : ""} reassigned to ${d.to}`);
  },
  async "new-kb"(f) { const d = Object.fromEntries(new FormData(f)); await api("/kb", { method: "POST", body: d }); closeSheet(); await mutated("Added to knowledge base"); },
};
document.addEventListener("submit", (e) => {
  const f = e.target.closest("[data-form]"); if (!f || !F[f.dataset.form]) return;
  e.preventDefault(); const btn = $("[type=submit]", f);
  busy(btn, () => F[f.dataset.form](f, btn));
});

// ───────────────────────── misc listeners
document.addEventListener("input", (e) => {
  if (e.target.id === "mq") { S.mq = e.target.value; renderMeetingList(); }
  if (e.target.id === "kq") { S.kq = e.target.value; renderKB(); }
  if (e.target.dataset && e.target.dataset.draft) S.drafts[e.target.dataset.draft] = e.target.value;
});
document.addEventListener("change", (e) => {
  if (e.target.id === "brief-for") loadBrief();
  if (e.target.id === "notes-upload" && e.target.files && e.target.files.length) {
    const files = [...e.target.files], meetingId = S.meeting.id, form = new FormData();
    form.append("notes", $("#notes").value);
    files.forEach((file) => form.append("files", file));
    const button = $('label[for="notes-upload"]'); e.target.value = "";
    busy(button, async () => {
      const result = await api(`/meetings/${meetingId}/notes/upload`, { method: "POST", body: form });
      delete S.drafts[meetingId];
      await mutated(`Added notes from ${result.files_uploaded} file${result.files_uploaded === 1 ? "" : "s"}. Generate a recap to extract decisions and actions.`);
    });
  }
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeSheet(); });
document.addEventListener("dragstart", (e) => { const c = e.target.closest && e.target.closest(".kc"); if (!c) return; e.dataTransfer.setData("text/plain", c.dataset.id); e.dataTransfer.effectAllowed = "move"; c.classList.add("drag"); });
document.addEventListener("dragend", (e) => { $$(".kc.drag").forEach((c) => c.classList.remove("drag")); $$(".lane.over").forEach((l) => l.classList.remove("over")); });
document.addEventListener("dragover", (e) => { const l = e.target.closest && e.target.closest(".lane"); if (!l) return; e.preventDefault(); $$(".lane.over").forEach((x) => x !== l && x.classList.remove("over")); l.classList.add("over"); });
document.addEventListener("drop", async (e) => {
  const l = e.target.closest && e.target.closest(".lane"); if (!l) return; e.preventDefault(); l.classList.remove("over");
  const id = e.dataTransfer.getData("text/plain"), to = l.dataset.lane, it = S.boardItems.find((i) => i.id == id);
  if (!it || it.status === to) return;
  if (["done", "dropped"].includes(to)) return outcomeSheet(it, to);
  try { await api(`/action-items/${id}`, { method: "PATCH", body: { status: to } }); await mutated(`Moved to ${STATUS[to][0]}`); } catch (err) { toast(err.message, "err"); }
});
let raf = 0;
window.addEventListener("pointermove", (e) => {
  if (reduceMotion() || raf) return;
  raf = requestAnimationFrame(() => { raf = 0; const r = document.documentElement.style, x = (e.clientX / innerWidth - .5) * 40, y = (e.clientY / innerHeight - .5) * 40; r.setProperty("--px", x + "px"); r.setProperty("--py", y + "px"); });
});
window.addEventListener("resize", () => $$(".seg").forEach(placeThumb));
window.addEventListener("hashchange", route);
window.addEventListener("unhandledrejection", (e) => { console.error(e.reason); toast("Something went wrong. Please try again.", "err"); });

buildChrome();
initializeAuth();
