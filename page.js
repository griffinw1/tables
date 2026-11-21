// Client script for site/index.html (inlined by render.py). Data comes from <script id="data">.
const D = JSON.parse(document.getElementById('data').textContent);
let P = D.party; const dates = D.dates;
D.venues.forEach(v => { v._base = [v.slots, v.status, v.day_notes]; });
// Swap every venue's slots to the chosen party size (4 is the main check; others come from by_size).
const applyParty = n => {
  P = n; const src = n === D.party ? null : (D.by_size || {})[n];
  D.venues.forEach(v => {
    if (n === D.party) { [v.slots, v.status, v.day_notes] = v._base; return; }
    const x = src && src.v[v.name];
    if (x) { [v.slots, v.status, v.day_notes] = [x[0] || {}, x[1] || {}, x[2] || {}]; }
    else { v.slots = {}; v.status = Object.fromEntries(dates.map(d => [d, 'error:not checked yet'])); v.day_notes = {}; }
  });
  const pn = document.getElementById('pnum'); if (pn) pn.textContent = n;
};
const $ = (s, e = document) => e.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const dow = d => new Date(d + 'T12:00:00').toLocaleDateString('en-US', {weekday: 'short'});
const dnum = d => { const x = new Date(d + 'T12:00:00'); return (x.getMonth() + 1) + '/' + x.getDate(); };
const h24 = t => { const m = String(t).match(/(\d+):(\d+)\s*([AP]M)/i); if (!m) return null; let h = +m[1] % 12; if (/p/i.test(m[3])) h += 12; return String(h).padStart(2, '0') + ':' + m[2]; };
const mins = t => { const x = h24(t); return x ? (+x.slice(0, 2)) * 60 + (+x.slice(3)) : null; };
const short = t => t.replace(':00', '').replace(' PM', 'p').replace(' AM', 'a');
const ONLINE = ['resy', 'opentable', 'sevenrooms', 'tock'];
const WINDOWS = {any: [0, 1e9], early: [0, 18 * 60 + 59], prime: [19 * 60, 20 * 60 + 30], late: [20 * 60 + 31, 1e9]};

const KINDS = ['restaurant', 'bar', 'coffee'];
const CITY = D.city || {slug: 'dallas', name: 'Dallas'}, SKEY = 'tables:' + CITY.slug;
let state = {kind: 'restaurant', day: 'all', open: false, q: '', sort: 'score', when: 'any', hood: '', cuisine: '', vibe: '', online: false, view: 'cards'};
try { Object.assign(state, JSON.parse(localStorage.getItem(SKEY) || (CITY.slug === 'dallas' ? localStorage.getItem('drw3') : '') || '{}')); state.q = ''; localStorage.setItem('tablesCity', CITY.slug); } catch (e) {}
if (!KINDS.includes(state.kind)) state.kind = 'restaurant';
if (state.day !== 'all' && !dates.includes(state.day)) state.day = 'all';
if (!(state.party >= 2 && state.party <= 8)) state.party = D.party;
applyParty(state.party);
const sel = {};  // per-card chosen day

const slotsFor = (v, d) => { const [a, b] = WINDOWS[state.when] || WINDOWS.any; return (v.slots[d] || []).filter(t => { const m = mins(t); return m == null || (m >= a && m <= b); }); };
const isOnline = v => ONLINE.includes(v.platform) && !v.closed && v.kind !== 'coffee';
const nOpen = v => dates.reduce((s, d) => s + slotsFor(v, d).length, 0);
const firstOpen = v => dates.findIndex(d => slotsFor(v, d).length);
const scoreCol = a => a == null ? '#7a7368' : a >= 9 ? '#1f6b46' : a >= 8.5 ? '#2f7d55' : a >= 8 ? '#5b8a3a' : a >= 7 ? '#a07a20' : '#a2382b';
const cuisineOf = v => (v.cuisine || '').split(/[,\-·/]| and /)[0].trim();
// Vibe profile (vibes.json, optional). Filter buckets are derived from tags / energy / crowd / good_for.
const vtext = v => { const b = v.vibe || {}; return [b.vibe, b.energy, b.crowd, ...(b.tags || []), ...[].concat(b.good_for || [])].filter(Boolean).join(' ').toLowerCase(); };
const VIBES = {
  'Lively': v => /lively|buzz|loud|party|scene|energetic|high[- ]energy|bustling|dj|club|vibrant/.test(vtext(v)),
  'Chill': v => /chill|quiet|low[- ]key|relaxed|cozy|calm|laid[- ]back|mellow/.test(vtext(v)),
  'Date night': v => /date|romantic|intimate|candle/.test(vtext(v)),
  'Group-friendly': v => /group|shar|family|large part|big table|celebrat/.test(vtext(v)),
  'Younger crowd': v => /^younger/i.test((v.vibe || {}).crowd || ''),
};

function bookUrl(v, d, t) {
  const u = v.url; if (!u) return null; const hm = t ? h24(t) : null;
  try {
    switch (v.platform) {
      case 'resy': { const x = new URL(u); if (d) x.searchParams.set('date', d); x.searchParams.set('seats', P); return x + ''; }
      case 'opentable': { if (!v.id) return u; const x = new URL('https://www.opentable.com/restaurant/profile/' + v.id); x.searchParams.set('covers', P); if (d) x.searchParams.set('dateTime', d + 'T' + (hm || '19:00')); return x + ''; }
      case 'sevenrooms': { const x = new URL(u); if (d) x.searchParams.set('date', d); x.searchParams.set('party_size', P); if (hm) x.searchParams.set('start_time', hm); return x + ''; }
      case 'tock': { const x = new URL(u.replace(/\/$/, '') + '/search'); if (d) x.searchParams.set('date', d); x.searchParams.set('size', P); if (hm) x.searchParams.set('time', hm); return x + ''; }
      default: return u;
    }
  } catch (e) { return u; }
}

const SORTS = {
  score: (a, b) => (a.avg == null) - (b.avg == null) || (b.avg || 0) - (a.avg || 0) || (b.ratings || 0) - (a.ratings || 0) || (a.top25 || a.press_rank || 99) - (b.top25 || b.press_rank || 99),
  open: (a, b) => nOpen(b) - nOpen(a) || SORTS.score(a, b),
  soonest: (a, b) => { const x = firstOpen(a), y = firstOpen(b); return (x < 0) - (y < 0) || x - y || SORTS.score(a, b); },
  top25: (a, b) => (a.top25 || 99) - (b.top25 || 99) || SORTS.score(a, b),
  name: (a, b) => a.name.localeCompare(b.name),
};

function primaryBtn(v, d) {
  const plat = D.platforms[v.platform] || v.platform;
  if (v.closed) return `<span class="book ghost">Closed for now</span>`;
  if (ONLINE.includes(v.platform) && v.url) return `<a class="book" href="${esc(bookUrl(v, d))}" target="_blank" rel="noopener">Book on ${esc(plat)} <span aria-hidden="true">→</span></a>`;
  if (v.platform === 'phone' && v.phone) return `<a class="book" href="tel:${esc(v.phone)}">Call to book · ${esc(v.phone)}</a>`;
  if (v.platform === 'none' || v.kind === 'coffee') return `<span class="book ghost">Walk in · no reservations</span>`;
  if (v.platform === 'walkin') return `<span class="book ghost">Walk-in only · no reservations</span>`;
  if (v.url) return `<a class="book" href="${esc(v.url)}" target="_blank" rel="noopener">Book on their site <span aria-hidden="true">→</span></a>`;
  return `<span class="book ghost">No online booking</span>`;
}
function secondary(v) {
  return [v.menu ? `<a class="sbtn" href="${esc(v.menu)}" target="_blank" rel="noopener">Menu</a>` : '',
    v.website ? `<a class="sbtn" href="${esc(v.website)}" target="_blank" rel="noopener">Site</a>` : '',
    (v.phone && v.platform !== 'phone') ? `<a class="sbtn" href="tel:${esc(v.phone)}" title="${esc(v.phone)}">Call</a>` : ''].join('');
}
function timesHtml(v, d) {
  const s = slotsFor(v, d), nt = (v.day_notes || {})[d] || '', stale = /^stale/.test(nt);
  if (s.length) return s.map(t => `<a class="time${stale ? ' stale' : ''}" href="${esc(bookUrl(v, d, t))}" target="_blank" rel="noopener" title="Book ${dow(d)} ${dnum(d)} at ${esc(t)}${stale ? ' (older check)' : ''}">${esc(short(t))}</a>`).join('');
  const why = /closed/i.test(nt) ? 'closed' : /not checked/.test((v.status || {})[d] || '') ? 'not checked for ' + P + ' yet' : /error/.test((v.status || {})[d] || '') ? 'check failed' : (v.slots[d] || []).length ? 'nothing in this time range' : 'no tables for ' + P;
  return `<span class="empty">${dow(d)} ${dnum(d)}: ${why}</span>`;
}
function stripHtml(v, cur) {
  return '<div class="strip">' + dates.map(d => {
    const n = slotsFor(v, d).length, nt = (v.day_notes || {})[d] || '';
    const lab = n ? n : (/closed/i.test(nt) ? '–' : '0');
    return `<button data-d="${d}" class="${n ? 'has' : ''}${d === cur ? ' sel' : ''}" title="${esc(nt || (n + ' open times'))}">${dow(d)}<b>${lab}</b></button>`;
  }).join('') + '</div>';
}
// Coffee hours: {"mon":"7:00-18:00", ...} or "closed"; shown as open/closed now in the city's time zone.
const DAYK = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];
const hm2 = t => { const m = String(t).trim().match(/^(\d{1,2})(?::(\d\d))?\s*([ap]m)?$/i); if (!m) return null; let h = +m[1]; if (m[3]) { h %= 12; if (/p/i.test(m[3])) h += 12; } return h * 60 + +(m[2] || 0); };
const fmt12 = n => { const h = Math.floor(n / 60) % 24, mm = n % 60; return (h % 12 || 12) + (mm ? ':' + String(mm).padStart(2, '0') : '') + (h < 12 ? ' AM' : ' PM'); };
function hoursLine(v) {
  const now = new Date(new Date().toLocaleString('en-US', {timeZone: (D.city || {}).tz || 'America/Chicago'}));
  const h = (v.hours || {})[DAYK[now.getDay()]]; if (!h) return '';
  const r = String(h).split(/[-–]/).map(hm2), cur = now.getHours() * 60 + now.getMinutes();
  if (/closed/i.test(h) || r.length < 2 || r.some(x => x == null)) return `<p class="hrs"><i class="off"></i>Closed today</p>`;
  const open = cur >= r[0] && cur < r[1];
  return `<p class="hrs"><i class="${open ? 'on' : 'off'}"></i>${open ? `Open now · until ${fmt12(r[1])}` : cur < r[0] ? `Opens ${fmt12(r[0])} today` : `Closed now · ${fmt12(r[0])}–${fmt12(r[1])} today`}</p>`;
}
const mono = v => `<div class="mono serif">${esc(v.name.replace(/^the\s+/i, '')[0])}</div>`;
// A hot-linked photo failed: drop it; if none are left, fall back to the monogram; keep dots/arrows in sync.
window.imgGone = img => {
  const sl = img.parentElement; img.remove();
  if (!sl) return;
  if (sl.classList.contains('r-th')) { if (!sl.querySelector('img')) { sl.innerHTML = sl.dataset.mono || ''; sl.classList.remove('kit-load'); } return; }
  const ph = sl.closest('.ph'); if (!ph) return;
  const n = sl.querySelectorAll('img').length;
  const dots = ph.querySelector('.dots');
  if (!n) { sl.outerHTML = sl.dataset.mono || ''; ph.classList.remove('kit-load'); }
  if (n < 2) { if (dots) dots.remove(); ph.querySelectorAll('.nav').forEach(b => b.remove()); return; }
  if (dots) { dots.innerHTML = Array.from({length: n}, (_, i) => `<i class="${i ? '' : 'on'}"></i>`).join(''); sl.dispatchEvent(new Event('scroll')); }
};
function photos(v) {
  const imgs = (v.imgs || []).slice(0, 8);
  if (!imgs.length) return mono(v);
  const dots = imgs.length > 1 ? `<div class="dots">${imgs.map((_, i) => `<i class="${i ? '' : 'on'}"></i>`).join('')}</div>` : '';
  return `<div class="slides" data-mono="${esc(mono(v))}">${imgs.map((u, i) => `<img ${i ? 'loading="lazy" ' : ''}src="${esc(u)}" alt="${esc(v.name)} photo ${i + 1}" referrerpolicy="no-referrer" class="kit-img" onload="kitImg(this)" onerror="imgGone(this)">`).join('')}</div>${dots}`
    + (imgs.length > 1 ? `<button class="nav prev" aria-label="Previous photo">‹</button><button class="nav next" aria-label="Next photo">›</button>` : '');
}

function card(v, rank) {
  const plat = D.platforms[v.platform] || v.platform;
  const online = isOnline(v);
  const cur = state.day !== 'all' ? state.day : (sel[v.name] || dates[Math.max(0, firstOpen(v))]);
  const score = v.avg != null ? `<div class="score"><div class="l"><b>Beli avg</b>${v.ratings_label ? esc(v.ratings_label) + ' ratings' : ''}</div><div class="n" style="--sc:${scoreCol(v.avg)}">${v.avg.toFixed(1)}</div></div>` : '';
  const t25 = v.top25 ? `<div class="tag25">Beli Top 25 · #${v.top25}</div>` : v.press_rank ? `<div class="tag25">Press pick · #${v.press_rank}</div>` : '';
  const sub = [v.cuisine, v.hood].filter(Boolean).map(esc).join(' · ');
  const vb = v.vibe || {};
  const vmeta = [vb.price ? `<span><b>${esc(vb.price)}</b></span>` : '', vb.crowd ? `<span>${esc(vb.crowd)} crowd</span>` : '', vb.energy ? `<span>${esc(vb.energy)}</span>` : ''].join('');
  const vtags = (vb.tags || []).filter(x => !/crowd$/i.test(x)).slice(0, 4).map(x => `<span class="vtag">${esc(x)}</span>`).join('');
  const dl = (v.dishes || []).filter(x => x.dish || x.name).slice(0, 3), dmax = Math.max(1, ...dl.map(x => x.count || 0));
  const dishes = dl.map((x, i) => `<div class="od${i === 0 && x.count ? ' first' : ''}" style="--w:${x.count ? Math.round(100 * x.count / dmax) : 0}%"><span>${esc(x.dish || x.name)}</span>${x.count ? `<i>${x.count} recs</i>` : ''}</div>`).join('');
  const el = document.createElement('article');
  el.className = 'card' + (v.closed ? ' closed' : '') + (v.kind === 'coffee' ? ' coffee' : '');
  el.dataset.name = v.name;
  el.innerHTML = `<div class="ph${(v.imgs || []).length ? ' kit-load' : ''}">${photos(v)}<div class="rank">${rank}</div>${t25}${score}</div>
  <div class="body"><div><h3 class="name serif">${esc(v.name)}</h3>${vb.food ? `<div class="food">${esc(vb.food)}</div>` : ''}<div class="sub">${sub}${sub ? ' · ' : ''}${esc(plat)}</div></div>
  ${vmeta ? `<div class="vmeta">${vmeta}</div>` : ''}
  ${v.note ? `<p class="blurb"><b>${esc(v.note)}</b></p>` : vb.vibe ? `<p class="blurb full">${esc(vb.vibe)}</p>` : v.blurb ? `<p class="blurb" title="Tap to read more" onclick="this.classList.toggle('full')">${esc(v.blurb)}</p>` : ''}
  ${vtags ? `<div class="vtags">${vtags}</div>` : ''}
  ${dishes ? `<div class="order" title="Most recommended on Beli"><div class="oh">Order this</div>${dishes}</div>` : ''}
  ${v.known_for ? `<p class="known"><b>Known for</b> ${esc(v.known_for)}</p>` : ''}
  ${v.hours ? hoursLine(v) : ''}
  ${online ? stripHtml(v, cur) + `<div class="times">${timesHtml(v, cur)}</div>` : ''}
  ${vb.heads_up ? `<p class="heads">${esc(vb.heads_up)}</p>` : ''}
  <div class="acts">${primaryBtn(v, online ? cur : null)}${secondary(v)}</div></div>`;
  el.querySelector('.ph').dataset.name = v.name;
  const sn = el.querySelector('.score .n'); if (sn) Kit.countOnce(sn, v.avg, 'c:' + v.name);
  if (online) el.querySelectorAll('.strip button').forEach(b => b.onclick = () => {
    sel[v.name] = b.dataset.d;
    el.querySelectorAll('.strip button').forEach(x => x.classList.toggle('sel', x === b));
    $('.times', el).innerHTML = timesHtml(v, b.dataset.d); Kit.reveal($('.times', el).children);
    const a = $('a.book', el); if (a) a.href = bookUrl(v, b.dataset.d);
  });
  const sl = $('.slides', el);
  if (sl) {
        sl.addEventListener('scroll', () => { const i = Math.round(sl.scrollLeft / (sl.clientWidth || 1)); el.querySelectorAll('.dots i').forEach((x, j) => x.classList.toggle('on', i === j)); }, {passive: true});
    el.querySelectorAll('.nav').forEach(b => b.onclick = e => {
      e.stopPropagation(); const s = el.querySelector('.slides'); if (!s) return;
      const w = s.clientWidth, n = s.querySelectorAll('img').length, i = Math.round(s.scrollLeft / w);
      const j = b.classList.contains('next') ? (i + 1) % n : (i - 1 + n) % n;   // wrap around
      s.scrollTo({left: j * w, behavior: 'smooth'});
    });
  }
  return el;
}

function row(v, rank) {
  const online = isOnline(v);
  const cur = state.day !== 'all' ? state.day : dates[Math.max(0, firstOpen(v))];
  const el = document.createElement('div');
  el.className = 'row' + (v.closed ? ' closed' : '');
  const th = (v.imgs || [])[0];
  el.innerHTML = `<div class="r-rank">${rank}</div>
  <div class="r-th${th ? ' kit-load' : ''}" data-mono="${esc(mono(v))}" data-name="${esc(v.name)}">${th ? `<img loading="lazy" src="${esc(th)}" alt="" referrerpolicy="no-referrer" class="kit-img" onload="kitImg(this)" onerror="imgGone(this)">` : mono(v)}</div>
  <div class="r-main"><div class="r-name serif">${esc(v.name)}</div><div class="sub">${[(v.vibe || {}).food || v.cuisine, v.hood, D.platforms[v.platform]].filter(Boolean).map(esc).join(' · ')}</div>${(v.vibe || {}).price || (v.vibe || {}).energy ? `<div class="r-vibe">${[(v.vibe || {}).price, (v.vibe || {}).energy].filter(Boolean).map(esc).join(' · ')}</div>` : ''}</div>
  <div class="r-score">${v.avg != null ? `<span class="pill" style="--sc:${scoreCol(v.avg)}">${v.avg.toFixed(1)}</span>` : ''}</div>
  <div class="r-days">${online ? dates.map(d => { const n = slotsFor(v, d).length; return `<a class="mini${n ? ' has' : ''}" ${n ? `href="${esc(bookUrl(v, d))}" target="_blank" rel="noopener"` : ''} title="${dow(d)} ${dnum(d)}: ${n} open${n ? ' · tap to book' : ''}"><small>${dow(d).slice(0, 2)}</small>${n || '·'}</a>`; }).join('') : `<span class="empty">${v.closed ? 'closed' : v.platform === 'walkin' ? 'walk-in' : v.platform === 'phone' ? 'call' : 'their site'}</span>`}</div>
  <div class="r-act">${primaryBtn(v, online ? cur : null).replace('class="book', 'class="book sm').replace(' · no reservations', '').replace(/Call to book · [^<]*/, 'Call to book')}</div>`;
  const pl = el.querySelector('.pill'); if (pl) Kit.countOnce(pl, v.avg, 'r:' + v.name);
  return el;
}

function matches(v) {
  const has = state.day === 'all' ? nOpen(v) > 0 : slotsFor(v, state.day).length > 0;
  if (state.open && !has) return false;
  if (state.online && !ONLINE.includes(v.platform)) return false;
  if (state.hood && v.hood !== state.hood) return false;
  if (state.cuisine && cuisineOf(v) !== state.cuisine) return false;
  if (state.vibe && !(VIBES[state.vibe] && VIBES[state.vibe](v))) return false;
  if (state.q) { const b = v.vibe || {}; const s = (v.name + ' ' + (v.cuisine || '') + ' ' + (v.hood || '') + ' ' + (v.dishes || []).map(x => x.dish).join(' ') + ' ' + [b.food, b.vibe, b.dress, b.heads_up].filter(Boolean).join(' ') + ' ' + vtext(v)).toLowerCase(); if (!s.includes(state.q)) return false; }
  return true;
}

function fillSelect(id, values, label) {
  const s = $(id), cur = s.value;
  s.innerHTML = `<option value="">${label}</option>` + values.map(x => `<option>${esc(x)}</option>`).join('');
  s.value = values.includes(cur) ? cur : '';
}

function render() {
  document.querySelectorAll('[data-k]').forEach(b => b.classList.toggle('on', b.dataset.k === state.kind));
  document.querySelectorAll('[data-view]').forEach(b => b.classList.toggle('on', b.dataset.view === state.view));
  document.querySelectorAll('[data-when]').forEach(b => b.classList.toggle('on', b.dataset.when === state.when));
  document.querySelectorAll('[data-p]').forEach(b => b.classList.toggle('on', +b.dataset.p === P));
  $('#days').innerHTML = `<button data-d="all" class="${state.day === 'all' ? 'on' : ''}">All<small>9 days</small></button>` + dates.map(d => {
    const n = D.venues.filter(v => slotsFor(v, d).length && v.kind === state.kind).length;
    return `<button data-d="${d}" class="${state.day === d ? 'on' : ''}">${dow(d)} ${dnum(d)}<small>${n} open</small></button>`;
  }).join('');
  document.querySelectorAll('#days button').forEach(b => b.onclick = () => { state.day = b.dataset.d; render(); });
  $('#only').checked = state.open; $('#onl').checked = state.online; $('#sort').value = state.sort;
  const pool = D.venues.filter(v => v.kind === state.kind);
  KINDS.forEach(k => { const c = $('#c-' + k); if (c) c.textContent = D.venues.filter(v => v.kind === k).length || ''; });
  document.querySelectorAll('.bar .when, #days, #only, #onl, .seg.party').forEach(x => (x.closest('label') || x).classList.toggle('hide', state.kind === 'coffee'));
  fillSelect('#hood', [...new Set(pool.map(v => v.hood).filter(Boolean))].sort(), 'Any area');
  fillSelect('#cuisine', [...new Set(pool.map(cuisineOf).filter(Boolean))].sort(), 'Any food');
  if (![...$('#hood').options].some(o => o.value === state.hood)) state.hood = '';
  if (![...$('#cuisine').options].some(o => o.value === state.cuisine)) state.cuisine = '';
  $('#hood').value = state.hood; $('#cuisine').value = state.cuisine;
  const vopts = Object.keys(VIBES).filter(k => pool.some(VIBES[k]));
  fillSelect('#vibe', vopts, 'Any vibe'); $('#vibe').classList.toggle('hide', !vopts.length);
  if (!vopts.includes(state.vibe)) state.vibe = '';
  $('#vibe').value = state.vibe;
  let shown = 0; const fresh = [];
  KINDS.forEach(k => {
    const sec = $('#s-' + k), on = state.kind === k;
    sec.classList.toggle('hide', !on);
    const all = D.venues.filter(v => v.kind === k);
    const scoreRank = new Map(all.filter(v => !v.closed).sort(SORTS.score).map((v, i) => [v.name, i + 1]));  // closed places get no number
    const list = all.filter(matches).sort((a, b) => (a.closed - b.closed) || SORTS[state.sort](a, b));
    const g = $('#g-' + k); g.className = state.view === 'list' ? 'list' : 'grid'; g.innerHTML = '';
    list.forEach(v => { const el = state.view === 'list' ? row(v, scoreRank.get(v.name) || '–') : card(v, scoreRank.get(v.name) || '–'); g.appendChild(el); if (on) fresh.push(el); });
    $('#n-' + k).textContent = `${list.length} of ${all.length} · numbered by Beli average`;
    $('#e-' + k).classList.toggle('hide', list.length > 0);
    if (on) shown += list.length;
  });
  Kit.reveal(fresh);
  document.querySelectorAll('.bar .seg').forEach(s => Kit.slide(s)); Kit.slide($('#days'));
  const nf = [state.open, state.online, state.hood, state.cuisine, state.vibe, state.q, state.when !== 'any'].filter(Boolean).length;
  $('#fcount').textContent = nf || '';
  $('#reset').classList.toggle('hide', !(nf || state.day !== 'all'));
  try { const {q, ...keep} = state; localStorage.setItem(SKEY, JSON.stringify(keep)); } catch (e) {}
  tonight();
}

document.querySelectorAll('[data-k]').forEach(b => b.onclick = () => { state.kind = b.dataset.k; state.hood = ''; state.cuisine = ''; render(); });
document.querySelectorAll('[data-view]').forEach(b => b.onclick = () => { state.view = b.dataset.view; render(); });
document.querySelectorAll('[data-when]').forEach(b => b.onclick = () => { state.when = b.dataset.when; render(); });
document.querySelectorAll('[data-p]').forEach(b => b.onclick = () => { state.party = +b.dataset.p; applyParty(state.party); render(); });
$('#only').onchange = e => { state.open = e.target.checked; render(); };
$('#onl').onchange = e => { state.online = e.target.checked; render(); };
$('#sort').onchange = e => { state.sort = e.target.value; render(); };
$('#hood').onchange = e => { state.hood = e.target.value; render(); };
$('#cuisine').onchange = e => { state.cuisine = e.target.value; render(); };
$('#vibe').onchange = e => { state.vibe = e.target.value; render(); };
let qt; $('#q').oninput = e => { clearTimeout(qt); qt = setTimeout(() => { state.q = e.target.value.trim().toLowerCase(); render(); }, 120); };
$('#reset').onclick = () => { Object.assign(state, {day: 'all', open: false, online: false, hood: '', cuisine: '', vibe: '', when: 'any', q: ''}); $('#q').value = ''; render(); };
$('#fbtn').onclick = () => { const b = $('.bar'), o = !b.classList.contains('open'); b.classList.toggle('open', o); $('#fbtn').setAttribute('aria-expanded', o); if (o) Kit.slide($('.seg.when'), null, false); };
// Tap a photo (card carousel or list thumb) -> full-screen viewer with caption + credit.
document.querySelector('main').addEventListener('click', e => {
  const img = e.target.closest('.slides img, .r-th img'); if (!img) return;
  const box = img.closest('.ph, .r-th'), name = box.dataset.name, v = D.venues.find(x => x.name === name); if (!v) return;
  const live = [...(box.querySelectorAll('.slides img').length ? box.querySelectorAll('.slides img') : [])].map(x => x.getAttribute('src'));
  const srcs = live.length ? live : (v.imgs || []).slice(0, 8);
  const i = Math.max(0, srcs.indexOf(img.getAttribute('src')));
  const via = v.img_src || D.platforms[v.platform] || '';
  Kit.open(srcs, i, {title: v.name, credit: [v.name, via ? 'via ' + via : ''].filter(Boolean).join(' '), href: v.url || v.website});
});

// ---- v2: Tonight, Greatest hits, city picker, Surprise me ----------------------------
const RM = matchMedia('(prefers-reduced-motion: reduce)').matches;
const tzToday = () => new Date().toLocaleDateString('en-CA', {timeZone: CITY.tz || 'America/Chicago'});
const tzNowMin = () => { const p = new Date().toLocaleTimeString('en-GB', {timeZone: CITY.tz || 'America/Chicago', hour: '2-digit', minute: '2-digit', hour12: false}).split(':'); return +p[0] * 60 + +p[1]; };
const nightOf = () => dates.find(d => d >= tzToday());
const laterSlots = (v, d) => { const cut = d === tzToday() ? tzNowMin() + 30 : -1; return slotsFor(v, d).filter(t => { const m = mins(t); return m == null || m >= cut; }); };
function goTo(v) {
  if (state.kind !== v.kind) state.kind = v.kind;
  if (!matches(v)) Object.assign(state, {day: 'all', open: false, online: false, hood: '', cuisine: '', vibe: '', when: 'any', q: ''}), $('#q').value = '';
  render();
  const el = [...document.querySelectorAll('#g-' + v.kind + ' > *')].find(x => x.dataset.name === v.name || (x.querySelector('[data-name]') || {}).dataset?.name === v.name);
  if (!el) return null;
  el.scrollIntoView({behavior: RM ? 'auto' : 'smooth', block: 'center'});
  el.classList.remove('picked'); void el.offsetWidth; el.classList.add('picked');
  setTimeout(() => el.classList.remove('picked'), 1800);
  return el;
}
function tonight() {
  const box = $('#tonight'); if (!box) return;
  const d = nightOf(); if (!d || state.kind === 'coffee') { box.innerHTML = ''; return; }
  const pool = D.venues.filter(v => v.kind === state.kind && isOnline(v) && laterSlots(v, d).length);
  const isTonight = d === tzToday(), when = isTonight ? 'tonight' : dow(d) + ' ' + dnum(d);
  const top = [...pool].sort(SORTS.score).slice(0, 6);
  box.innerHTML = `<div class="tn-h"><span class="tn-big">${pool.length}</span><span class="tn-l">${state.kind === 'bar' ? 'bars' : 'restaurants'} with a table for ${P} ${when}<small>Best-rated first · tap a time to book it on their page</small></span></div>`
    + (top.length ? `<div class="tn-row">${top.map(v => `<div class="tn" role="button" tabindex="0" data-n="${esc(v.name)}"><div class="th">${(v.imgs || [])[0] ? `<img src="${esc(v.imgs[0])}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">` : esc(v.name[0])}</div>
      <div><b>${esc(v.name)}</b><div class="tt">${laterSlots(v, d).slice(0, 4).map(t => `<a href="${esc(bookUrl(v, d, t))}" target="_blank" rel="noopener">${esc(short(t))}</a>`).join('')}</div></div>
      ${v.avg != null ? `<span class="sc" style="--sc:${scoreCol(v.avg)}">${v.avg.toFixed(1)}</span>` : ''}</div>`).join('')}</div>` : '');
  box.querySelectorAll('.tn').forEach(t => { const go = e => { if (e.target.closest('a')) return; const v = D.venues.find(x => x.name === t.dataset.n); if (v) goTo(v); }; t.onclick = go; t.onkeydown = e => { if (e.key === 'Enter') go(e); }; });
}
(function hits() {
  const box = $('#hits'); if (!box) return;
  const all = [];
  D.venues.forEach(v => (v.dishes || []).forEach(x => { if (x.count && (x.dish || x.name)) all.push({v, dish: x.dish || x.name, n: x.count}); }));
  all.sort((a, b) => b.n - a.n);
  const per = {}, pick = all.filter(x => (per[x.v.name] = (per[x.v.name] || 0) + 1) <= 1).slice(0, 12);
  if (pick.length < 3) return;
  box.innerHTML = `<h3>Most ordered in ${esc(CITY.name)}</h3><div class="hrow">${pick.map(x => `<button class="hit" data-n="${esc(x.v.name)}"><b>${esc(x.dish)}</b><small>${esc(x.v.name)} · <i>${x.n}</i> recs</small></button>`).join('')}</div>`;
  box.querySelectorAll('.hit').forEach(b => b.onclick = () => { const v = D.venues.find(x => x.name === b.dataset.n); if (v) goTo(v); });
})();
(function picker() {
  const btn = $('#citypick'), sh = $('#sheet'); if (!btn || !sh) return;
  const cities = D.cities || [CITY];
  $('#clist').innerHTML = cities.map(c => {
    const cur = c.slug === CITY.slug, soon = c.status === 'soon';
    const inner = `<span class="cm">${esc(c.name[0])}</span><span><b>${esc(c.name)}</b><small>${esc(soon ? 'Coming soon · scores being pulled' : (c.tagline || (c.state || '')))}</small></span>${cur ? '<span class="here">You’re here</span>' : ''}`;
    return soon ? `<div class="ccard" style="--cc:${esc(c.accent || '#888')};opacity:.6">${inner}</div>` : `<a class="ccard${cur ? ' cur' : ''}" style="--cc:${esc(c.accent || '#888')}" href="../${esc(c.slug)}/">${inner}</a>`;
  }).join('');
  const open = o => { sh.classList.toggle('hide', !o); btn.setAttribute('aria-expanded', o); document.documentElement.classList.toggle('kit-lock', o); if (o) $('#sheetx').focus(); };
  btn.onclick = () => open(true); $('#sheetx').onclick = () => open(false);
  sh.onclick = e => { if (e.target === sh) open(false); };
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && !sh.classList.contains('hide')) open(false); });
})();
(function surprise() {
  const b = $('#surprise'); if (!b) return;
  b.onclick = () => {
    const d = nightOf(), k = state.kind;
    let pool = D.venues.filter(v => v.kind === k && !v.closed && (v.avg || 0) >= 8.5 && (k === 'coffee' || (d && laterSlots(v, d).length)));
    if (!pool.length) pool = D.venues.filter(v => v.kind === k && !v.closed && (k === 'coffee' || nOpen(v)));
    if (!pool.length) pool = D.venues.filter(v => v.kind === k && !v.closed);
    if (!pool.length) return;
    const v = pool[Math.floor(Math.random() * pool.length)];
    b.classList.remove('spin'); void b.offsetWidth; b.classList.add('spin');
    const el = goTo(v); if (!el || RM) return;
    setTimeout(() => {
      const r = el.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + Math.min(r.height / 2, innerHeight / 2);
      const cols = [getComputedStyle(document.documentElement).getPropertyValue('--city').trim() || '#b4532a', '#d9b25e', '#1f6b46', '#f3eee6'];
      for (let i = 0; i < 28; i++) { const c = document.createElement('i'); c.className = 'confetti'; const a = Math.random() * Math.PI * 2, s = 80 + Math.random() * 160;
        c.style.cssText = `left:${cx}px;top:${cy}px;background:${cols[i % 4]};--x:${Math.cos(a) * s}px;--y:${Math.sin(a) * s + 60}px;--r:${Math.random() * 720 - 360}deg`;
        document.body.appendChild(c); setTimeout(() => c.remove(), 1100); }
    }, 450);
  };
})();
Kit.buzzOn('.time, .book, .mini.has, .strip button, .days button, .seg button');
render();

// ---- Last pull + "Pull again" -------------------------------------------------------------
// The button posts to a private ntfy.sh topic; scripts/pull_listener.py on the Mac hears it,
// runs publish.sh, and reports back on <topic>-s (started / busy / cooldown / done / failed).
(() => {
  const T = D.pull_topic, box = $('#pull'), txt = $('#ptxt'), btn = $('#pbtn'), msg = $('#pmsg');
  if (!T || !box) return;
  const NT = 'https://ntfy.sh/';
  const clock = d => d.toLocaleTimeString('en-US', {hour: 'numeric', minute: '2-digit', timeZone: 'America/Chicago'});
  const day = d => d.toLocaleDateString('en-US', {weekday: 'short', timeZone: 'America/Chicago'});
  const ago = d => { const m = Math.round((Date.now() - d) / 60000);
    if (m < 1) return 'just now'; if (m < 60) return m + ' min ago';
    const h = Math.floor(m / 60), r = m % 60; return h + ' hr' + (r && h < 6 ? ' ' + r + ' min' : '') + ' ago'; };
  const atFor = () => { const s = P === D.party ? D.generated_at : ((D.by_size || {})[P] || {}).at; return s ? new Date(s) : null; };
  let busy = false;
  const paint = () => {
    const d = atFor();
    if (!d) { txt.innerHTML = 'Party of ' + P + ' <b>not pulled yet</b>'; box.classList.add('stale'); return; }
    txt.innerHTML = 'Last pull <b>' + ago(d) + '</b> · ' + day(d) + ' ' + clock(d) + ' CT' + (P !== D.party ? ' · for ' + P : '');
    box.classList.toggle('stale', Date.now() - d > 3.5 * 3600e3);
  };
  const say = (t, cls = '') => { msg.textContent = t; msg.className = 'pmsg ' + cls; };
  const setBusy = b => { busy = b; box.classList.toggle('busy', b); btn.disabled = b; btn.querySelector('span').textContent = b ? 'Pulling…' : 'Pull again'; };
  paint(); setInterval(paint, 30e3);
  document.querySelectorAll('[data-p]').forEach(b => b.addEventListener('click', () => setTimeout(paint)));

  // Once the Mac has pushed, wait for GitHub Pages to serve the new data, then reload.
  const waitForSite = (at) => {
    const want = new Date(at || Date.now() - 6e4), t0 = Date.now();
    say('Pulled. Publishing the new times (about a minute)…');
    const tick = async () => {
      try { const r = await fetch('../cities/' + CITY.slug + '/results/p' + D.party + '.json?t=' + Date.now(), {cache: 'no-store'}); const j = await r.json();
        if (new Date(j.generated_at) >= want - 1000) { say('✓ Updated. Reloading…', 'ok'); setTimeout(() => location.reload(), 600); return; } } catch (e) {}
      if (Date.now() - t0 > 4 * 60e3) { setBusy(false); say('Pulled, but the site hasn\'t refreshed yet. Reload the page in a minute.', 'err'); return; }
      setTimeout(tick, 8e3);
    };
    tick();
  };
  let es, noReply;
  const listen = () => {
    if (es) return;
    es = new EventSource(NT + T + '-s/sse');
    es.onmessage = e => {
      let m; try { m = JSON.parse(JSON.parse(e.data).message); } catch (x) { return; }
      if (!m || !m.state) return;
      clearTimeout(noReply);
      if (m.state === 'started') { setBusy(true); say('The Mac is pulling fresh times now. This usually takes 3–6 minutes. You can leave this page open.'); }
      else if (m.state === 'busy') { setBusy(true); say('A pull is already running on the Mac. Watching it…'); }
      else if (m.state === 'cooldown') { setBusy(false); say('Not pulled: the last pull was only ' + (m.mins ?? 'a few') + ' min ago. Try again after ' + clock(new Date(m.next)) + '.', 'err'); close(); }
      else if (m.state === 'failed') { setBusy(false); say('✗ The pull failed on the Mac. The times shown are still from the last pull.', 'err'); close(); }
      else if (m.state === 'done') { close(); waitForSite(m.at); }
    };
  };
  const close = () => { if (es) { es.close(); es = null; } };
  btn.onclick = async () => {
    if (busy) return;
    setBusy(true); say('Asking the Mac to pull…'); listen();
    try { await fetch(NT + T, {method: 'POST', body: JSON.stringify({party: P, city: CITY.slug})}); }
    catch (e) { setBusy(false); close(); say('✗ Couldn\'t send the request (no connection?). Nothing was pulled.', 'err'); return; }
    noReply = setTimeout(() => { setBusy(false); close();
      say('✗ The Mac didn\'t answer, so nothing was pulled. It\'s probably asleep or offline. Pulls resume automatically when it wakes.', 'err'); }, 45e3);
  };
  // A pull someone else started in the last 15 min? Show it.
  fetch(NT + T + '-s/json?poll=1&since=15m').then(r => r.text()).then(t => {
    const last = t.trim().split('\n').filter(Boolean).map(l => { try { return JSON.parse(JSON.parse(l).message); } catch (e) { return null; } }).filter(Boolean).pop();
    if (last && (last.state === 'started' || last.state === 'busy')) { setBusy(true); say('A pull is running on the Mac right now…'); listen(); }
  }).catch(() => {});
})();
