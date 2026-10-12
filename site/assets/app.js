/* CoreBot-paneel — vanilla JS, geen externe scripts. Alle gebruikersdata gaat via textContent. */
(() => {
'use strict';

/* ---------- hulpjes ---------- */
const SVGNS = 'http://www.w3.org/2000/svg';
function el(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v === null || v === undefined) continue;
    if (k === 'class') e.className = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (k === 'value') e.value = v;
    else if (k === 'checked') e.checked = !!v;
    else e.setAttribute(k, v === true ? '' : v);
  }
  for (const c of kids.flat()) if (c !== null && c !== undefined && c !== false) e.append(c.nodeType ? c : document.createTextNode(String(c)));
  return e;
}
function svg(tag, attrs, ...kids) {
  const e = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v);
  for (const c of kids.flat()) if (c !== null && c !== undefined) e.append(c.nodeType ? c : document.createTextNode(String(c)));
  return e;
}
const $app = document.getElementById('app');
const show = (...nodes) => $app.replaceChildren(...nodes.flat().filter(Boolean));
let S = { me: null, csrf: '' };
let dirtyCheck = null;

async function api(action, opts = {}) {
  const { method = 'GET', body, params } = opts;
  const url = 'api.php?' + new URLSearchParams({ a: action, ...(params || {}) });
  const init = { method, headers: { Accept: 'application/json' }, credentials: 'same-origin' };
  if (method === 'POST') { init.headers['Content-Type'] = 'application/json'; init.headers['X-CSRF-Token'] = S.csrf; init.body = JSON.stringify(body || {}); }
  let res;
  try { res = await fetch(url, init); } catch { throw Object.assign(new Error('Geen verbinding met CoreBot. Controleer je internet en probeer opnieuw.'), { status: 0 }); }
  let j = {};
  try { j = await res.json(); } catch { /* leeg antwoord */ }
  if (!res.ok) throw Object.assign(new Error(j.error || 'Er ging iets mis.'), { status: res.status, data: j });
  return j;
}
let toastTimer = 0;
function toast(msg, bad = false) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.className = 'toast' + (bad ? ' bad' : ''); t.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { t.hidden = true; }, bad ? 6000 : 2600);
}
const num = (v) => (v === '' || v === null || v === undefined ? '' : String(v));

/* ---------- kop en voet ---------- */
function ava(src, name) { return src ? el('img', { class: 'ava', src, alt: '', width: 26, height: 26, referrerpolicy: 'no-referrer' }) : el('span', { class: 'ava' }); }
function gicon(g) {
  return g.icon ? el('img', { class: 'gicon', src: g.icon, alt: '', width: 44, height: 44, referrerpolicy: 'no-referrer' })
    : el('span', { class: 'gicon', 'aria-hidden': 'true' }, (g.name || '?').trim().slice(0, 1).toUpperCase());
}
function renderTop() {
  const cur = location.hash || '#/';
  const link = (href, text) => el('a', { href, 'aria-current': cur === href || (href !== '#/' && cur.startsWith(href)) ? 'page' : false }, text);
  const nav = el('nav', { class: 'nav', 'aria-label': 'Hoofdmenu' });
  if (S.me && S.me.user) {
    nav.append(link('#/', 'Servers'), link('#/voorkeuren', 'Voorkeuren'));
    if (S.me.user.admin) nav.append(link('#/platform', 'Platform'));
    nav.append(el('span', { class: 'who' }, ava(S.me.user.avatar), S.me.user.name),
      el('button', { type: 'button', onclick: logout }, 'Uitloggen'));
  } else {
    nav.append(el('a', { class: 'btn primary small', href: 'login.php' }, 'Inloggen met Discord'));
  }
  document.getElementById('top').replaceChildren(el('header', { class: 'top' }, el('div', { class: 'wrap' },
    el('a', { class: 'brand', href: '#/' }, el('img', { src: 'assets/logo.svg', alt: '', width: 30, height: 30 }), 'CoreBot'), nav)));
}
function renderFoot() {
  const m = S.me || {};
  document.getElementById('foot').replaceChildren(el('footer', { class: 'foot' }, el('div', { class: 'wrap' },
    el('a', { href: 'legal.php?p=privacy' }, 'Privacy'), el('a', { href: 'legal.php?p=voorwaarden' }, 'Voorwaarden'),
    m.contact ? el('a', { href: 'mailto:' + m.contact }, m.contact) : null, el('span', null, 'CoreBot ' + (m.version || '')))));
}
async function logout() {
  try { await api('logout', { method: 'POST' }); } catch { /* sessie was al weg */ }
  await loadMe(); location.hash = '#/'; route();
}

/* ---------- landing ---------- */
function ringsDiagram() {
  const t = (x, y, txt, cls) => svg('text', { x, y, 'text-anchor': 'middle', class: cls || '' }, txt);
  return svg('svg', { class: 'rings', viewBox: '0 0 480 440', role: 'img', 'aria-label': 'Drie lagen: standaard van CoreBot, jouw server en een kanaal. Elke laag past aan wat erboven staat en erft de rest.' },
    svg('circle', { class: 'ring r1', cx: 240, cy: 230, r: 200 }),
    svg('circle', { class: 'ring r2', cx: 240, cy: 275, r: 140 }),
    svg('circle', { class: 'ring r3', cx: 240, cy: 318, r: 82 }),
    t(240, 66, 'Standaard van CoreBot'), t(240, 85, 'vriendelijk, 20 berichten per uur', 'sub'),
    t(240, 168, 'Jouw server'), t(240, 187, 'zakelijk, botnaam Core', 'sub'),
    t(240, 305, '#vragen', 't3'), t(240, 324, 'speels, eigen naam Kees', 'sub sub3'), t(240, 342, 'rest erft van de server', 'sub sub3'));
}
function landing() {
  const m = S.me;
  const err = new URLSearchParams(location.search).get('auth_error');
  const errText = { sessie: 'De inlogpoging is verlopen. Probeer het opnieuw.', geweigerd: 'Je hebt de toestemming op Discord geweigerd. Zonder die toestemming kunnen we je servers niet tonen.', discord: 'Discord gaf een foutmelding. Probeer het zo nog eens.', fout: 'Inloggen is niet gelukt. Probeer het zo nog eens.' }[err];
  if (err) history.replaceState(null, '', location.pathname + location.hash);
  show(
    errText ? el('div', { class: 'note bad', role: 'alert' }, errText) : null,
    el('section', { class: 'hero' },
      el('div', null,
        el('h1', null, 'Eén bot, per kanaal een eigen toon.'),
        el('p', { class: 'lead' }, 'CoreBot beantwoordt vragen in de kanalen die jij kiest. Toon, botnaam, limieten en commando\'s stel je in per server en per kanaal. Gratis en in het Nederlands.'),
        el('div', { class: 'cta' },
          el('a', { class: 'btn primary', href: m.invite_url, target: '_blank', rel: 'noopener' }, 'Bot toevoegen aan Discord'),
          el('a', { class: 'btn', href: 'login.php' }, 'Inloggen met Discord'))),
      ringsDiagram()),
    el('section', { class: 'facts' },
      el('div', null, el('h3', null, 'Instellen per laag'), el('p', null, 'Je vult alleen in wat afwijkt. Een leeg veld betekent: neem over van de laag erboven.')),
      el('div', null, el('h3', null, 'Leden houden de regie'), el('p', null, 'Elk lid kiest een bijnaam, een eigen toon als de server dat toestaat, en of de bot iets onthoudt. Eén knop wist alles.')),
      el('div', null, el('h3', null, 'Berichten blijven op de eigen computer'), el('p', null, 'De AI draait op de computer van de beheerder. Berichten gaan niet naar een externe aanbieder en worden niet opgeslagen.'))),
    el('section', { class: 'stack' },
      el('h2', null, 'Veelgestelde vragen'),
      el('details', null, el('summary', null, 'Wat kost het?'), el('p', null, 'Niets. Elke server heeft wel een daglimiet aan antwoorden zodat de bot voor iedereen blijft werken.')),
      el('details', null, el('summary', null, 'Welke rechten vraagt de bot?'), el('p', null, 'Kanalen bekijken, berichten lezen en sturen, links insluiten en berichten in threads sturen. Hij kan geen leden verwijderen of rollen wijzigen.')),
      el('details', null, el('summary', null, 'Wie mag de instellingen wijzigen?'), el('p', null, 'Wie in Discord het recht Server beheren heeft, en de eigenaar van de server. Je logt in met Discord; we vragen geen e-mailadres.')),
      el('details', null, el('summary', null, 'Kan ik mijn gegevens laten wissen?'), el('p', null, 'Ja, onder Voorkeuren. Dat wist je account en voorkeuren, en de bot vergeet wat hij van je onthouden had.'))));
}

/* ---------- servers ---------- */
function badge(g) {
  if (g.suspended) return el('span', { class: 'chip bad' }, 'Geschorst');
  return g.bot_present ? el('span', { class: 'chip ok' }, 'Bot actief') : el('span', { class: 'chip warn' }, 'Bot nog niet toegevoegd');
}
async function dashboard() {
  const m = S.me;
  const mine = m.servers.filter((s) => s.can_manage), others = m.servers.filter((s) => !s.can_manage);
  const rows = el('div', { class: 'rows' });
  for (const g of mine) {
    rows.append(el('div', { class: 'row' }, gicon(g), el('div', { class: 'grow' }, el('div', { class: 'name' }, g.name), badge(g)),
      g.bot_present ? el('a', { class: 'btn primary small', href: '#/server/' + g.id }, 'Instellen')
        : el('a', { class: 'btn small', href: g.invite_url, target: '_blank', rel: 'noopener' }, 'Bot toevoegen')));
  }
  show(
    el('div', { class: 'head' }, el('h1', null, 'Jouw servers'), el('span', { class: 'grow' }),
      el('button', { class: 'btn small', type: 'button', onclick: refreshServers }, 'Servers vernieuwen')),
    mine.length ? rows : el('div', { class: 'panel' }, el('h2', null, 'Nog geen server om te beheren'),
      el('p', null, 'Je ziet hier servers waar jij het recht Server beheren hebt. Heb je net een server gemaakt of rechten gekregen, kies dan Servers vernieuwen.')),
    mine.some((s) => !s.bot_present) ? el('p', { class: 'hint mt' }, 'Heb je de bot net toegevoegd? Het duurt meestal een halve minuut voor de server op Bot actief staat. Kies dan Servers vernieuwen.') : null,
    others.length ? el('div', { class: 'stack mt2' }, el('h2', null, 'Servers waar je lid bent'),
      el('div', { class: 'rows' }, others.map((g) => el('div', { class: 'row' }, gicon(g), el('div', { class: 'grow' }, el('div', { class: 'name' }, g.name),
        el('span', { class: 'hint' }, 'Alleen beheerders wijzigen de serverinstellingen.')), badge(g)))),
      el('p', null, el('a', { href: '#/voorkeuren' }, 'Stel je eigen voorkeuren in'))) : null);
}
async function refreshServers() {
  try { await api('refresh', { method: 'POST' }); await loadMe(); route(); toast('Servers vernieuwd'); }
  catch (e) { if (e.data && e.data.relogin) location.href = 'login.php'; else { await loadMe(); route(); toast(e.message, true); } }
}

/* ---------- serverinstellingen ---------- */
const FIELDS = ['tone', 'name', 'extra_prompt', 'cooldown', 'per_hour', 'max_input', 'memory'];
function toProfile(p, isServer) {
  const d = { tone: '', name: '', extra_prompt: '', cooldown: '', per_hour: '', max_input: '', memory: '', commands: [], mode: 'chat', enabled: true };
  for (const k of FIELDS) if (p && p[k] !== undefined) d[k] = num(p[k]);
  d.commands = ((p && p.commands) || []).map((c) => ({ name: c.name, reply: c.reply, on: !!c.on }));
  if (p && p.mode) d.mode = p.mode;
  if (isServer && p && p.enabled === false) d.enabled = false;
  return d;
}
function fromProfile(d, isServer) {
  const o = {};
  for (const k of FIELDS) if (String(d[k]).trim() !== '') o[k] = d[k];
  const cmds = d.commands.filter((c) => c.name.trim() !== '' || c.reply.trim() !== '');
  if (cmds.length) o.commands = cmds;
  if (isServer && !d.enabled) o.enabled = false;
  if (!isServer && d.mode !== 'chat') o.mode = d.mode;
  return o;
}
function toDraft(cfg) {
  const cc = {};
  for (const [id, p] of Object.entries(cfg.channel_cfg || {})) cc[id] = toProfile(p, false);
  const fb = cfg.fallback || {};
  return { server: toProfile(cfg.server, true), channels: [...(cfg.channels || [])], channel_cfg: cc, allow_member_tone: cfg.allow_member_tone !== false,
    faq: (cfg.faq || []).map((f) => ({ q: f.q, a: f.a, on: !!f.on })), fallback: { faq: fb.faq !== false, cache: fb.cache !== false, templates: fb.templates !== false } };
}
function fromDraft(d) {
  const cc = {};
  for (const [id, p] of Object.entries(d.channel_cfg)) { const o = fromProfile(p, false); if (Object.keys(o).length) cc[id] = o; }
  return { server: fromProfile(d.server, true), channels: [...d.channels], channel_cfg: cc, allow_member_tone: d.allow_member_tone,
    faq: d.faq.filter((f) => f.q.trim() !== '' || f.a.trim() !== ''), fallback: { ...d.fallback } };
}

function field(label, input, hint) { return el('label', { class: 'f' }, label, input, hint ? el('small', null, hint) : null); }
function txt(obj, key, ph, max) { return el('input', { type: 'text', value: obj[key], placeholder: ph || '', maxlength: max || false, oninput: (e) => { obj[key] = e.target.value; G.touch(); } }); }
function numIn(obj, key, ph, lim) { return el('input', { type: 'number', inputmode: 'numeric', value: obj[key], placeholder: ph, min: lim ? lim.min : false, max: lim ? lim.max : false, oninput: (e) => { obj[key] = e.target.value; G.touch(); } }); }
function toneSelect(obj, key, inheritLabel) {
  const s = el('select', { onchange: (e) => { obj[key] = e.target.value; G.touch(); } }, el('option', { value: '' }, inheritLabel),
    S.me.tones.map((t) => el('option', { value: t.key }, t.label + ': ' + t.hint)));
  s.value = obj[key]; return s;
}
function sw(label, checked, onchange, hint) {
  return el('label', { class: 'sw' }, el('input', { type: 'checkbox', checked, onchange: (e) => onchange(e.target.checked) }), el('span', null, label, hint ? el('div', { class: 'hint' }, hint) : null));
}
function limitsGrid(obj, lim, inherit) {
  const L = (k) => lim[k] || {};
  return el('div', { class: 'grid2' },
    field('Wachttijd tussen berichten (seconden)', numIn(obj, 'cooldown', inherit, L('cooldown')), `Tussen ${L('cooldown').min} en ${L('cooldown').max}`),
    field('Berichten per uur per lid', numIn(obj, 'per_hour', inherit, L('per_hour')), `Tussen ${L('per_hour').min} en ${L('per_hour').max}`),
    field('Maximale lengte van een vraag (tekens)', numIn(obj, 'max_input', inherit, L('max_input')), `Tussen ${L('max_input').min} en ${L('max_input').max}`),
    field('Aantal berichten dat de bot onthoudt', numIn(obj, 'memory', inherit, L('memory')), `Tussen ${L('memory').min} en ${L('memory').max}; 0 = niets onthouden`));
}
function cmdEditor(list) {
  const box = el('div');
  const draw = () => {
    box.replaceChildren(...list.map((c, i) => el('div', { class: 'cmd' },
      el('input', { type: 'checkbox', checked: c.on, 'aria-label': 'Commando aan', onchange: (e) => { c.on = e.target.checked; G.touch(); } }),
      el('input', { type: 'text', value: c.name, placeholder: '!regels', maxlength: 21, 'aria-label': 'Naam van het commando', oninput: (e) => { c.name = e.target.value; G.touch(); } }),
      el('textarea', { placeholder: 'Antwoord van de bot', maxlength: 800, 'aria-label': 'Antwoord', oninput: (e) => { c.reply = e.target.value; G.touch(); } }, c.reply),
      el('button', { class: 'btn small danger', type: 'button', onclick: () => { list.splice(i, 1); draw(); G.touch(); } }, 'Verwijder'))),
      el('button', { class: 'btn small', type: 'button', onclick: () => { list.push({ name: '', reply: '', on: true }); draw(); G.touch(); } }, 'Commando toevoegen'));
  };
  draw(); return box;
}

const G = { touch() {} }; // wordt per serverpagina vervangen

async function serverView(id) {
  show(el('p', { class: 'muted' }, 'Laden…'));
  let g;
  try { g = (await api('guild', { params: { id } })); }
  catch (e) {
    const inv = e.data && e.data.invite_url;
    show(el('div', { class: 'panel' }, el('h2', null, e.status === 404 ? 'De bot zit nog niet in deze server' : 'Geen toegang'), el('p', null, e.message),
      inv ? el('a', { class: 'btn primary', href: inv, target: '_blank', rel: 'noopener' }, 'Bot toevoegen') : null, ' ', el('a', { class: 'btn', href: '#/' }, 'Terug naar servers')));
    return;
  }
  let draft = toDraft(g.config), rev = g.rev, saved = JSON.stringify(fromDraft(draft));
  const isAdmin = !!g.admin; const lim = g.limits;
  let tab = sessionStorageGet('tab:' + id) || 'algemeen';
  const saveBar = el('div', { class: 'save', hidden: true }, el('div', { class: 'wrap' }, el('span', { class: 'grow' }, 'Niet-opgeslagen wijzigingen'),
    el('button', { class: 'btn', type: 'button', onclick: () => { draft = toDraft(JSON.parse(saved)); G.touch(); drawTab(); } }, 'Terugzetten'),
    el('button', { class: 'btn primary', type: 'button', id: 'savebtn', onclick: save }, 'Opslaan')));
  const sums = new Map();
  const isDirty = () => JSON.stringify(fromDraft(draft)) !== saved;
  G.touch = () => {
    saveBar.hidden = !isDirty();
    for (const [cid, node] of sums) node.textContent = summary(cid);
  };
  dirtyCheck = isDirty;
  function summary(cid) {
    const p = draft.channel_cfg[cid]; if (!p) return '';
    const o = fromProfile(p, false); const parts = [];
    if (o.tone) parts.push('toon ' + (S.me.tones.find((t) => t.key === o.tone) || {}).label);
    if (o.name) parts.push('naam ' + o.name);
    if (o.mode === 'commands') parts.push('alleen commando\'s');
    if (o.extra_prompt) parts.push('eigen instructie');
    if (o.cooldown || o.per_hour || o.max_input || o.memory) parts.push('eigen limieten');
    if (o.commands) parts.push(o.commands.length + ' commando\'s');
    return parts.join(', ');
  }
  async function save() {
    const b = document.getElementById('savebtn'); b.disabled = true;
    try {
      const r = await api('guild_save', { method: 'POST', body: { id, rev, config: fromDraft(draft) } });
      rev = r.guild.rev; draft = toDraft(r.guild.config); saved = JSON.stringify(fromDraft(draft)); g = r.guild;
      G.touch(); drawTab(); toast('Opgeslagen');
    } catch (e) { toast(e.message, true); }
    b.disabled = false;
  }
  const content = el('div');
  const tabs = el('div', { class: 'tabs', role: 'tablist' });
  const tabDefs = [['algemeen', 'Algemeen'], ['kanalen', 'Kanalen'], ['commandos', 'Commando\'s'], ['faq', 'Veelgestelde vragen'], ['gebruik', 'Gebruik'], ...(isAdmin ? [['beheer', 'Beheer']] : [])];
  function drawTabs() {
    tabs.replaceChildren(...tabDefs.map(([k, label]) => el('button', { type: 'button', role: 'tab', 'aria-selected': k === tab ? 'true' : 'false', onclick: () => { tab = k; sessionStoragePut('tab:' + id, k); drawTabs(); drawTab(); } }, label)));
  }
  function drawTab() {
    sums.clear();
    const f = { algemeen: tabAlgemeen, kanalen: tabKanalen, commandos: tabCommandos, faq: tabFaq, gebruik: tabGebruik, beheer: tabBeheer }[tab];
    content.replaceChildren(f());
  }
  function tabAlgemeen() {
    const s = draft.server;
    return el('div', { class: 'stack panel' },
      sw('Bot aan in deze server', s.enabled, (v) => { s.enabled = v; G.touch(); }, 'Uit betekent dat de bot hier nergens antwoordt, ook niet in kanalen die je hieronder kiest.'),
      field('Toon van de bot', toneSelect(s, 'tone', 'Standaard van CoreBot'), 'Kanalen kunnen een eigen toon kiezen.'),
      field('Naam van de bot', txt(s, 'name', 'CoreBot', 32), 'De naam waarmee de bot zichzelf noemt.'),
      field('Extra instructie', el('textarea', { maxlength: 400, placeholder: 'Bijvoorbeeld: Dit is de server van onze gilde. Verwijs voor regels naar #regels.', oninput: (e) => { s.extra_prompt = e.target.value; G.touch(); cnt.textContent = e.target.value.length + ' van 400'; } }, s.extra_prompt), 'Wordt toegevoegd aan de basisregels van de bot. Die regels kun je er niet mee overschrijven.'),
      (cnt = el('div', { class: 'hint' }, s.extra_prompt.length + ' van 400')),
      el('h3', null, 'Limieten voor deze server'), el('p', { class: 'hint' }, 'Laat een veld leeg om de standaard van CoreBot te gebruiken.'),
      limitsGrid(s, lim, 'Standaard'),
      sw('Leden mogen hun eigen toon kiezen', draft.allow_member_tone, (v) => { draft.allow_member_tone = v; G.touch(); }, 'Een lid kan onder Voorkeuren een toon kiezen die voor hem of haar de toon van de server of het kanaal vervangt.'));
  }
  let cnt;
  function tabKanalen() {
    const chans = g.channels.filter((c) => c.type === 0 || c.type === 5);
    if (!chans.length) return el('div', { class: 'panel' }, el('p', null, 'CoreBot heeft de kanalen van deze server nog niet doorgekregen. Dat gebeurt zodra de bot online is. Ververs deze pagina over een halve minuut.'));
    const serverTone = () => { const t = S.me.tones.find((x) => x.key === draft.server.tone); return t ? t.label : 'Standaard van CoreBot'; };
    return el('div', null, el('p', { class: 'hint' }, 'Zet een kanaal aan om de bot daar te laten antwoorden. Kies Eigen instellingen om een kanaal af te laten wijken van de server.'),
      el('div', { class: 'rows' }, chans.map((c) => {
        const on = draft.channels.includes(c.id);
        const open = el('div', { class: 'open', hidden: true });
        const sum = el('span', { class: 'hint' }, summary(c.id)); sums.set(c.id, sum);
        const btn = el('button', { class: 'btn small', type: 'button', 'aria-expanded': 'false', onclick: () => {
          const show = open.hidden; open.hidden = !show; btn.setAttribute('aria-expanded', String(show));
          if (show && !open.firstChild) fill();
        } }, 'Eigen instellingen');
        function fill() {
          const p = draft.channel_cfg[c.id] || (draft.channel_cfg[c.id] = toProfile({}, false));
          const mode = el('select', { onchange: (e) => { p.mode = e.target.value; G.touch(); } }, el('option', { value: 'chat' }, 'De AI antwoordt op vragen'), el('option', { value: 'commands' }, 'Alleen commando\'s (geen AI)'));
          mode.value = p.mode;
          open.append(el('div', { class: 'stack' },
            field('Wat doet de bot hier?', mode),
            field('Toon', toneSelect(p, 'tone', 'Zoals de server (' + serverTone() + ')')),
            field('Naam van de bot in dit kanaal', txt(p, 'name', draft.server.name || 'Zoals de server', 32)),
            field('Extra instructie voor dit kanaal', el('textarea', { maxlength: 400, placeholder: 'Komt na de instructie van de server', oninput: (e) => { p.extra_prompt = e.target.value; G.touch(); } }, p.extra_prompt)),
            limitsGrid(p, lim, 'Zoals de server'),
            el('h3', null, 'Commando\'s in dit kanaal'), cmdEditor(p.commands)));
        }
        return el('div', { class: 'chan' }, el('div', { class: 'bar' },
          el('label', { class: 'sw cn' }, el('input', { type: 'checkbox', checked: on, 'aria-label': 'Bot antwoordt in ' + c.name, onchange: (e) => {
            const i = draft.channels.indexOf(c.id);
            if (e.target.checked && i < 0) draft.channels.push(c.id); else if (!e.target.checked && i >= 0) draft.channels.splice(i, 1);
            G.touch(); } }), el('span', null, '#' + c.name)),
          sum, btn), open);
      })));
  }
  function tabCommandos() {
    return el('div', { class: 'panel stack' }, el('p', null, 'Commando\'s die in elk antwoordkanaal werken. Een kanaal kan een commando met dezelfde naam zelf overnemen. Leden typen bijvoorbeeld !regels. Het commando !help bestaat al en toont deze lijst.'),
      cmdEditor(draft.server.commands));
  }
  const FAQ_MAX = 30, FAQ_EXAMPLES = [
    ['Hoe kom ik aan een rol?', '(pas dit antwoord aan) Je kiest zelf een rol in het kanaal voor rollen. Vraag het een beheerder als je er niet uitkomt.'],
    ['Waar vind ik de regels?', '(pas dit antwoord aan) De regels staan vastgepind in het kanaal met de serverregels.'],
    ['Wie zijn de beheerders?', '(pas dit antwoord aan) Zet hier de namen van de beheerders of verwijs naar een kanaal waar ze te vinden zijn.'],
  ];
  function tabFaq() {
    const list = draft.faq, fbk = draft.fallback;
    const rows = el('div', { class: 'faqlist' });
    const counter = (v, max) => el('span', { class: 'hint' }, v.length + ' van ' + max);
    const draw = () => {
      if (!list.length) rows.replaceChildren(el('p', { class: 'hint' }, 'Nog geen vragen. Voeg er een toe of begin met de voorbeelden.'));
      else rows.replaceChildren(...list.map((f, i) => {
        const cq = counter(f.q, 120), ca = counter(f.a, 600);
        return el('div', { class: 'faq' },
          el('label', { class: 'sw faqon' }, el('input', { type: 'checkbox', checked: f.on, 'aria-label': 'Vraag aan', onchange: (e) => { f.on = e.target.checked; G.touch(); } })),
          el('div', { class: 'faqbody stack' },
            el('input', { type: 'text', value: f.q, maxlength: 120, placeholder: 'Vraag van een lid', 'aria-label': 'Vraag', oninput: (e) => { f.q = e.target.value; cq.textContent = f.q.length + ' van 120'; G.touch(); } }), cq,
            el('textarea', { maxlength: 600, placeholder: 'Het antwoord van de bot', 'aria-label': 'Antwoord op de vraag', oninput: (e) => { f.a = e.target.value; ca.textContent = f.a.length + ' van 600'; G.touch(); } }, f.a), ca),
          el('button', { class: 'btn small danger faqdel', type: 'button', onclick: () => { list.splice(i, 1); draw(); G.touch(); } }, 'Verwijder'));
      }));
      add.disabled = list.length >= FAQ_MAX;
      count.textContent = list.length + ' van ' + FAQ_MAX;
    };
    const count = el('span', { class: 'hint' });
    const add = el('button', { class: 'btn small', type: 'button', onclick: () => { if (list.length < FAQ_MAX) { list.push({ q: '', a: '', on: true }); draw(); G.touch(); } } }, 'Vraag toevoegen');
    const examples = el('button', { class: 'btn small', type: 'button', onclick: () => {
      const have = new Set(list.map((f) => f.q.trim().toLowerCase()));
      const fresh = FAQ_EXAMPLES.filter(([q]) => !have.has(q.toLowerCase())).slice(0, FAQ_MAX - list.length);
      if (!fresh.length) { toast('De voorbeelden staan er al, of de lijst is vol.', true); return; }
      for (const [q, a] of fresh) list.push({ q, a, on: false });
      draw(); G.touch(); toast('Voorbeelden toegevoegd, nog uit. Pas de antwoorden aan en zet ze aan.');
    } }, 'Voorbeelden toevoegen');
    draw();
    return el('div', { class: 'stack' },
      el('div', { class: 'panel stack' },
        el('p', null, 'Dit zijn antwoorden die de bot geeft als de AI even niet bereikbaar is. De bot herkent de vraag aan de woorden, ook bij typefouten. Zolang de AI werkt, antwoordt de AI zelf en blijft deze lijst ongebruikt.'),
        sw('Veelgestelde vragen gebruiken', fbk.faq, (v) => { fbk.faq = v; G.touch(); }, 'Uit betekent dat de bot de lijst hieronder nooit gebruikt.'),
        sw('Recent antwoord opnieuw gebruiken', fbk.cache, (v) => { fbk.cache = v; G.touch(); }, 'Stelt iemand dezelfde vraag als net, dan geeft de bot het eerdere antwoord. Dit staat alleen in het werkgeheugen van de bot, maximaal 24 uur, en verdwijnt bij een herstart.'),
        sw('Vaste antwoorden op groeten', fbk.templates, (v) => { fbk.templates = v; G.touch(); }, 'Bijvoorbeeld een groet terug op "hoi" of een reactie op "bedankt".')),
      el('div', { class: 'panel stack' }, el('h3', null, 'Jouw vragen'), rows,
        el('div', { class: 'faqbtns' }, add, examples, count)));
  }
  function tabGebruik() {
    const u = g.usage; const pct = u.cap > 0 ? Math.min(100, Math.round(u.today / u.cap * 100)) : 0;
    const meterFill = el('i'); meterFill.style.width = pct + '%';
    const week = fillWeek(u.week);
    const max = Math.max(1, ...week.map((d) => d.answered));
    return el('div', { class: 'stack panel' }, el('h3', null, 'Antwoorden vandaag'),
      el('div', null, el('strong', null, String(u.today)), u.cap > 0 ? ' van ' + u.cap : ' (geen daglimiet)', u.cap > 0 ? el('div', { class: 'meter' + (pct >= 90 ? ' hot' : ''), role: 'img', 'aria-label': pct + ' procent van de daglimiet' }, meterFill) : null),
      el('p', { id: 'fbtoday' }, 'Antwoorden via terugval vandaag: ', el('strong', null, String(u.fallback_today || 0))),
      el('h3', null, 'Laatste 7 dagen'),
      el('div', { class: 'bars' }, week.map((d) => { const bar = el('i', { title: d.day + ': ' + d.answered }); bar.style.height = Math.round(d.answered / max * 90) + 'px'; return el('div', null, String(d.answered), bar, d.day.slice(8) + '/' + d.day.slice(5, 7)); })),
      el('p', { class: 'hint' }, 'Alleen aantallen. De inhoud van berichten wordt niet bewaard.'));
  }
  function tabBeheer() {
    const a = { ...g.admin };
    const model = el('select', { onchange: (e) => { a.model = e.target.value; } }, el('option', { value: '' }, 'Standaardmodel van de bot'), a.models_allowed.map((m) => el('option', { value: m }, m)));
    model.value = a.model;
    return el('div', { class: 'panel stack' }, el('div', { class: 'note info' }, 'Dit tabblad zie alleen jij als beheerder van CoreBot. Serverbeheerders zien geen modellen.'),
      field('Model voor deze server', model, a.models_allowed.length ? null : 'Nog geen modellen toegestaan. Zet ze onder Platform > Instellingen.'),
      sw('Server schorsen', a.suspended, (v) => { a.suspended = v; }, 'De bot antwoordt dan niet meer in deze server.'),
      field('Daglimiet antwoorden (leeg = standaard, 0 = geen limiet)', el('input', { type: 'number', min: 0, max: 100000, value: a.daily_cap === null ? '' : a.daily_cap, oninput: (e) => { a.daily_cap = e.target.value === '' ? null : Number(e.target.value); } })),
      el('div', null, el('button', { class: 'btn primary', type: 'button', onclick: async () => {
        try { const r = await api('admin_guild', { method: 'POST', body: { id, model: a.model, suspended: a.suspended, daily_cap: a.daily_cap } }); g.admin = r.guild.admin; g.warnings = r.guild.warnings; drawWarn(); toast('Opgeslagen'); }
        catch (e) { toast(e.message, true); }
      } }, 'Opslaan')));
  }
  const warnBox = el('div');
  function drawWarn() { warnBox.replaceChildren(...g.warnings.map((w) => el('div', { class: 'note', role: 'status' }, w))); }
  drawWarn(); drawTabs(); drawTab();
  show(
    el('div', { class: 'head' }, gicon(g), el('h1', null, g.name), el('span', { class: 'grow' }), el('a', { class: 'btn small', href: '#/' }, 'Alle servers')),
    warnBox, tabs, content, saveBar);
}
function fillWeek(rows) {
  const map = new Map(rows.map((r) => [r.day, Number(r.answered)])); const out = [];
  for (let i = 6; i >= 0; i--) { const d = new Date(); d.setDate(d.getDate() - i); const key = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); out.push({ day: key, answered: map.get(key) || 0 }); }
  return out;
}
function sessionStorageGet(k) { try { return sessionStorage.getItem(k); } catch { return null; } }
function sessionStoragePut(k, v) { try { sessionStorage.setItem(k, v); } catch { /* privévenster */ } }

/* ---------- voorkeuren van een lid ---------- */
async function prefsView() {
  const { prefs } = await api('prefs');
  const p = { nick: prefs.nick || '', tone: prefs.tone || '', memory: prefs.memory !== false };
  const tone = el('select', { onchange: (e) => { p.tone = e.target.value; } }, el('option', { value: '' }, 'Geen voorkeur: de toon van de server of het kanaal'),
    S.me.tones.map((t) => el('option', { value: t.key }, t.label + ': ' + t.hint)));
  tone.value = p.tone;
  const confirmBox = el('div');
  const askForget = () => {
    confirmBox.replaceChildren(el('div', { class: 'note bad', role: 'alert' }, 'Dit wist je account, je serverlijst en je voorkeuren. De bot vergeet wat hij van je onthouden had. Dit kan niet ongedaan worden.'),
      el('button', { class: 'btn danger', type: 'button', onclick: async () => {
        try { await api('forget_me', { method: 'POST' }); await loadMe(); location.hash = '#/'; route(); toast('Je gegevens zijn gewist'); } catch (e) { toast(e.message, true); }
      } }, 'Ja, wis alles'), ' ', el('button', { class: 'btn', type: 'button', onclick: () => confirmBox.replaceChildren() }, 'Annuleren'));
  };
  show(el('div', { class: 'head' }, el('h1', null, 'Jouw voorkeuren')),
    el('div', { class: 'panel stack' },
      el('p', null, 'Deze voorkeuren gelden in alle servers waar CoreBot zit. Een serverbeheerder kan het kiezen van een eigen toon uitzetten.'),
      field('Bijnaam waarmee de bot je aanspreekt', el('input', { type: 'text', value: p.nick, maxlength: 32, placeholder: S.me.user.name, oninput: (e) => { p.nick = e.target.value; } }), 'Leeg = je naam in Discord.'),
      field('Eigen toon', tone),
      sw('De bot mag onthouden wat ik zeg', p.memory, (v) => { p.memory = v; }, 'Uit betekent dat de bot elk bericht van jou los beantwoordt.'),
      el('div', null, el('button', { class: 'btn primary', type: 'button', onclick: async () => {
        try { await api('prefs_save', { method: 'POST', body: { prefs: p } }); toast('Opgeslagen'); } catch (e) { toast(e.message, true); }
      } }, 'Opslaan'))),
    el('div', { class: 'panel stack mt2' }, el('h2', null, 'Je gegevens'),
      el('p', null, 'Wat we bewaren lees je in de ', el('a', { href: 'legal.php?p=privacy' }, 'privacyverklaring'), '.'),
      el('div', null, el('button', { class: 'btn danger', type: 'button', onclick: askForget }, 'Verwijder mijn gegevens')), confirmBox));
}

/* ---------- platform (alleen beheerder van CoreBot) ---------- */
async function platformView() {
  const a = await api('admin');
  const st = { ...a.settings };
  const secretOut = el('div');
  const when = (ts) => { if (!ts) return 'nog nooit'; const s = Math.max(0, Math.round(Date.now() / 1000 - ts)); return s < 90 ? 'zojuist' : s < 5400 ? Math.round(s / 60) + ' minuten geleden' : s < 172800 ? Math.round(s / 3600) + ' uur geleden' : Math.round(s / 86400) + ' dagen geleden'; };
  const online = a.hub_last && Date.now() / 1000 - a.hub_last.at < 900;
  const clock = (ts) => { const d = new Date(ts * 1000), t = d.toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit' }); return d.toDateString() === new Date().toDateString() ? t : d.toLocaleDateString('nl-NL', { day: 'numeric', month: 'short' }) + ' ' + t; };
  const ai = a.hub_last && a.hub_last.ai;
  const aiLine = !ai ? el('span', { class: 'chip warn' }, 'AI-status onbekend')
    : ai.up ? el('span', { class: 'chip ok' }, 'AI bereikbaar')
      : el('span', { class: 'chip bad' }, 'AI niet bereikbaar sinds ' + clock(ai.since));
  show(
    el('div', { class: 'head' }, el('h1', null, 'Platform'), el('span', { class: 'grow' }), st.sbwebui_url ? el('a', { class: 'btn small', href: st.sbwebui_url, target: '_blank', rel: 'noopener' }, 'Open SBWebUI') : null),
    el('div', { class: 'stats' }, [['Servers met bot', a.stats.present + ' van ' + a.stats.servers], ['Gebruikers', a.stats.users], ['Antwoorden vandaag', a.stats.today], ['Antwoorden 7 dagen', a.stats.week]].map(([l, v]) => el('div', null, el('b', null, String(v)), l))),
    el('div', { class: 'panel stack' }, el('h2', null, 'Bot-verbinding'),
      el('div', null, online ? el('span', { class: 'chip ok' }, 'Bot online') : el('span', { class: 'chip bad' }, 'Bot niet gezien'), ' laatste sync ', when(a.hub_last && a.hub_last.at), a.hub_last && a.hub_last.version ? ' (versie ' + a.hub_last.version + ')' : ''),
      el('div', { id: 'aistatus' }, aiLine, ai && !ai.up && ai.fails > 0 ? ' ' + ai.fails + ' mislukte pogingen op rij' : '', !ai ? ' De bot meldt dit nog niet.' : ''),
      el('p', null, 'Hub-adres voor de bot: ', el('code', null, a.hub_url)),
      el('p', null, 'Redirect-adressen voor het Discord Developer Portal (OAuth2 > Redirects), zet ze allemaal erin:'), el('ul', null, a.redirect_uris.map((u) => el('li', null, el('code', null, u)))),
      a.canonical_host ? el('p', { class: 'hint' }, 'Alle andere domeinen sturen door naar ' + a.canonical_host + '.') : el('p', { class: 'hint' }, 'Er is nog geen hoofddomein ingesteld: elk toegestaan domein werkt los. Zet canonical_host in config.php als corebot.info live is.'),
      el('div', null, el('button', { class: 'btn small', type: 'button', onclick: async () => {
        try { const r = await api('admin_secret', { method: 'POST' }); secretOut.replaceChildren(el('p', null, 'Zet dit in het .env-bestand van de bot als COREBOT_SECRET (deel het met niemand):'), el('code', null, r.hub_secret)); } catch (e) { toast(e.message, true); }
      } }, 'Toon bot-sleutel'), secretOut)),
    el('div', { class: 'panel stack mt2' }, el('h2', null, 'Instellingen'),
      field('Modellen die je per server mag toekennen (kommagescheiden)', el('input', { type: 'text', value: st.models_allowed, placeholder: 'qwen3:4b, llama3.1:8b', oninput: (e) => { st.models_allowed = e.target.value; } }), 'Dit zijn namen van modellen op jouw Ollama. Gebruikers zien ze nooit.'),
      field('Standaard daglimiet antwoorden per server (0 = geen)', el('input', { type: 'number', min: 0, max: 100000, value: st.default_cap, oninput: (e) => { st.default_cap = Number(e.target.value); } })),
      field('Adres van SBWebUI (alleen voor de knop hierboven)', el('input', { type: 'text', value: st.sbwebui_url, placeholder: 'https://sbwebui.scriptspace.nl', oninput: (e) => { st.sbwebui_url = e.target.value; } })),
      sw('Nieuwe servers mogen de bot gebruiken', st.signups, (v) => { st.signups = v; }, 'Uit: nieuwe servers starten geschorst tot jij ze vrijgeeft.'),
      el('div', null, el('button', { class: 'btn primary', type: 'button', onclick: async () => {
        try { await api('admin_settings', { method: 'POST', body: st }); toast('Opgeslagen'); } catch (e) { toast(e.message, true); }
      } }, 'Opslaan'))),
    el('h2', { class: 'mt2' }, 'Alle servers'),
    el('div', { class: 'tablewrap' }, el('table', null,
      el('thead', null, el('tr', null, ['Server', 'Leden', 'Status', 'Model', 'Vandaag', 'Via terugval', ''].map((h) => el('th', null, h)))),
      el('tbody', null, a.guilds.map((g) => el('tr', null, el('td', null, g.name || g.id), el('td', null, String(g.members)),
        el('td', null, g.suspended ? el('span', { class: 'chip bad' }, 'Geschorst') : g.bot_present ? el('span', { class: 'chip ok' }, 'Actief') : el('span', { class: 'chip warn' }, 'Weg')),
        el('td', null, g.model || '-'), el('td', null, g.today + (g.daily_cap ? ' / ' + g.daily_cap : '')), el('td', null, String(g.fallback)),
        el('td', null, el('a', { href: '#/server/' + g.id }, 'Openen'))))))));
}

/* ---------- router ---------- */
async function loadMe() {
  S.me = await api('me'); S.csrf = S.me.csrf;
}
async function route() {
  if (dirtyCheck) dirtyCheck = null;
  G.touch = () => {};
  renderTop(); renderFoot();
  const h = location.hash || '#/';
  document.title = 'CoreBot';
  try {
    if (!S.me.user) { landing(); return; }
    if (h.startsWith('#/server/')) await serverView(h.slice(9).replace(/[^0-9]/g, ''));
    else if (h === '#/voorkeuren') await prefsView();
    else if (h === '#/platform' && S.me.user.admin) await platformView();
    else await dashboard();
  } catch (e) {
    if (e.status === 401) { await loadMe(); landing(); return; }
    show(el('div', { class: 'note bad', role: 'alert' }, e.message));
  }
  $app.focus({ preventScroll: true });
}
window.addEventListener('hashchange', () => { route(); window.scrollTo(0, 0); });
window.addEventListener('beforeunload', (e) => { if (dirtyCheck && dirtyCheck()) { e.preventDefault(); e.returnValue = ''; } });
document.addEventListener('click', (e) => {
  const a = e.target.closest && e.target.closest('a[href^="#/"]');
  if (a && dirtyCheck && dirtyCheck() && !confirmLeave()) e.preventDefault();
}, true);
function confirmLeave() { return window.confirm('Je hebt wijzigingen die nog niet zijn opgeslagen. Toch verlaten?'); }

(async () => {
  try { await loadMe(); } catch (e) { show(el('div', { class: 'note bad', role: 'alert' }, e.message)); return; }
  route();
})();
})();
