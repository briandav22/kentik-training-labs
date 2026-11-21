// The lab site's page: every lab as a tile, a page per lab (its ticket, steps and controls), your portal's
// details, and the reset. Plain JavaScript: no build step, no libraries, no inline handlers (the server's
// Content-Security-Policy runs only this file and art.js). It talks to klab/web.py's JSON API and sends the
// key the terminal printed as X-Lab-Key on every call.
(() => {
  'use strict';

  // ------------------------------------------------------------------ helpers
  const $ = (sel, root = document) => root.querySelector(sel);

  // h('div', { class, on: { click }, ...attributes }, ...children). Strings become text, never HTML; only
  // `html` (used for the drawings in art.js, which are ours) is parsed.
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === 'on') for (const [ev, fn] of Object.entries(v)) el.addEventListener(ev, fn);
      else if (k === 'class') el.className = v;
      else if (k === 'html') el.innerHTML = v;
      else el.setAttribute(k, v === true ? '' : String(v));
    }
    put(el, kids);
    return el;
  }

  // Append children, flattening arrays and skipping null and false. (No .flat() or .replaceChildren():
  // the lab host's browser may be an older Firefox.)
  function put(el, kids) {
    for (const kid of kids) {
      if (kid == null || kid === false) continue;
      if (Array.isArray(kid)) put(el, kid);
      else el.appendChild(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    }
    return el;
  }

  function fill(el, ...kids) {
    while (el.firstChild) el.removeChild(el.firstChild);
    return put(el, kids);
  }

  // The catalog's text marks: **bold** and `code`.
  function rich(text) {
    const frag = document.createDocumentFragment();
    const re = /\*\*(.+?)\*\*|`([^`]+)`/g;
    let last = 0, m;
    text = String(text || '');
    while ((m = re.exec(text))) {
      if (m.index > last) frag.append(text.slice(last, m.index));
      frag.append(m[1] != null ? h('b', null, m[1]) : h('code', null, m[2]));
      last = re.lastIndex;
    }
    if (last < text.length) frag.append(text.slice(last));
    return frag;
  }

  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private window: fine */ } },
    del(k) { try { localStorage.removeItem(k); } catch (e) { /* fine */ } },
  };

  function dur(s) {
    s = Math.max(0, Math.round(s || 0));
    if (s >= 3600) return Math.floor(s / 3600) + 'h ' + String(Math.floor((s % 3600) / 60)).padStart(2, '0') + 'm';
    if (s >= 90) return Math.round(s / 60) + ' min';
    if (s >= 60) return '1 min';
    return s + ' s';
  }

  // ------------------------------------------------------------------ the key
  // The terminal prints http://127.0.0.1:8090/?key=…; keep the key in this browser and take it off the address.
  const KEY = (() => {
    const u = new URL(location.href);
    const k = u.searchParams.get('key');
    if (k) {
      store.set('klab.key', k);
      u.searchParams.delete('key');
      history.replaceState(null, '', u.pathname + u.search + u.hash);
      return k;
    }
    return store.get('klab.key', '');
  })();

  // ------------------------------------------------------------------ state
  const S = {
    cat: null,          // GET /api/catalog: tracks, labs, the customer's questions
    status: null,       // GET /api/status, every few seconds
    keyProblem: false,  // the server wants a key we don't have: show how to open the site
    offline: false,     // the server stopped answering
    bootError: '',
    busy: '',           // the action running now, one at a time, as in one terminal
    chats: {},          // lab id -> [{ q, a, who }]
    hints: {},          // lab id -> [{ n, of, text }]
    log: {},            // lab id -> [{ kind, text }]: what the host printed
    root: {},           // lab id -> { cmd, terminal }: a command to run yourself (no sudo here, or the class copy)
    answers: {},        // lab id -> { answer, reveal }: instructor view
    plan: null,         // GET /api/reset: what a reset takes out
    resetResult: null,
    portalMsg: null,    // { kind, text } under the portal form
  };

  const progressAll = () => store.get('klab.progress', {});
  const progress = id => Object.assign({ steps: [], done: false, hints: 0 }, progressAll()[id] || {});
  function saveProgress(id, p) { const all = progressAll(); all[id] = p; store.set('klab.progress', all); }
  // The class copy (lab.py ui --classroom) runs on the instructor's machine: it runs nothing, and every button
  // gives the command for your own lab host's terminal. Only the instructor has the key, for the answers.
  const classroom = () => !!(S.status && S.status.classroom);
  const instructor = () => !!store.get('klab.instructor', false) && (!classroom() || !!KEY);
  const labById = id => (S.cat ? S.cat.labs.find(l => l.id === id) : null);

  // ------------------------------------------------------------------ the API
  async function api(path, body) {
    const opts = { method: body === undefined ? 'GET' : 'POST', headers: { 'X-Lab-Key': KEY }, cache: 'no-store' };
    if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    let r;
    try {
      r = await fetch(path, opts);
    } catch (e) {
      if (!S.offline) { S.offline = true; renderTop(); }
      throw new Error('The lab site stopped answering. Is python3 lab.py ui still running in a terminal?');
    }
    if (S.offline) { S.offline = false; renderTop(); }
    let data = {};
    try { data = await r.json(); } catch (e) { /* not JSON */ }
    if (r.status === 403 && data.error === 'instructor') throw new Error('instructor');
    if (r.status === 403 && data.error === 'key') {
      if (!S.keyProblem) { S.keyProblem = true; render(); }
      throw new Error('key');
    }
    if (!r.ok) throw new Error(data.error || ('The site answered with an error (' + r.status + ').'));
    return data;
  }

  // ------------------------------------------------------------------ routes
  function route() {
    const parts = location.hash.replace(/^#\/?/, '').split('/');
    if (parts[0] === 'lab' && parts[1]) return { page: 'lab', id: decodeURIComponent(parts[1]) };
    if (parts[0] === 'portal') return { page: 'portal' };
    if (parts[0] === 'reset') return { page: 'reset' };
    return { page: 'home' };
  }

  function render(keepScroll) {
    const y = window.scrollY;
    const r = route();
    document.querySelectorAll('[data-nav]').forEach(a => {
      const on = a.dataset.nav === r.page || (r.page === 'lab' && a.dataset.nav === 'home');
      a.classList.toggle('on', on);
      if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
    });
    const main = $('#main');
    fill(main);
    if (S.keyProblem) main.append(keyPage());
    else if (!S.cat) main.append(S.bootError ? offlinePage() : h('p', { class: 'loading' }, 'Loading the labs…'));
    else if (r.page === 'lab') main.append(labPage(r.id));
    else if (r.page === 'portal') main.append(portalPage());
    else if (r.page === 'reset') main.append(resetPage());
    else main.append(homePage());
    const lab = r.page === 'lab' && labById(r.id);
    document.title = lab ? lab.label + ': ' + lab.title + ' · Kentik labs'
      : r.page === 'portal' ? 'Your portal · Kentik labs' : r.page === 'reset' ? 'Reset · Kentik labs' : 'Kentik labs';
    renderTop();
    if (keepScroll) window.scrollTo(0, y);
  }

  // ------------------------------------------------------------------ top bar
  function pill(kind, text, href, title) {
    return h(href ? 'a' : 'span', { class: 'pill ' + (kind || ''), href, title }, h('i', { 'aria-hidden': 'true' }), text);
  }

  function renderTop() {
    const el = $('#topStatus');
    if (!el) return;
    fill(el);
    if (S.keyProblem) return;
    if (S.offline) { el.append(pill('warn', 'Site not answering', null, 'Is python3 lab.py ui still running?')); return; }
    const st = S.status;
    if (!st) return;
    const toggle = $('.foot-toggle');
    if (toggle) toggle.hidden = !!st.classroom && !KEY;
    if (st.classroom) {
      el.append(pill('lab', 'Class copy', null, 'Each lab’s commands run in your own lab host’s terminal'));
      if (KEY) el.append(pill('warn', 'Instructor link', null, 'This link shows the answers: keep it off the projector'));
      return;
    }
    const open = st.open_id && labById(st.open_id);
    if (open) el.append(pill('lab', open.label + ' open', '#/lab/' + open.id, 'Go to the open lab'));
    el.append(pill(st.network ? 'good' : '', st.network ? 'Lab network running' : 'Lab network stopped', null,
      st.network ? 'The made-up devices are sending flow' : 'Launch a lab to start it'));
    el.append(pill(st.listening ? 'good' : 'warn', st.listening ? 'Agent on UDP ' + st.agent_port : 'Nothing on UDP ' + st.agent_port,
      null, st.listening ? 'A program, your agent, is listening for flow' : 'Is your Universal Agent installed and running?'));
    const pc = st.portal || {};
    el.append(pill(pc.connected ? 'good' : 'warn', pc.connected ? 'Portal saved' : 'Portal not connected', '#/portal'));
    if (!st.root) el.append(pill('warn', 'Read only', null, 'Started without sudo: labs can be read, not launched'));
  }

  // ------------------------------------------------------------------ shared pieces
  function cmdBox(cmd) {
    const btn = h('button', { type: 'button', title: 'Copy the command' }, 'Copy');
    btn.addEventListener('click', () => copy(cmd, btn));
    return h('div', { class: 'cmd' }, h('code', null, cmd), btn);
  }

  async function copy(text, btn) {
    let ok = false;
    try {
      await navigator.clipboard.writeText(text);
      ok = true;
    } catch (e) {                                   // no clipboard API off localhost: the old way
      const ta = h('textarea', { 'aria-hidden': 'true', class: 'offscreen' });
      ta.value = text;
      document.body.append(ta);
      ta.select();
      try { ok = document.execCommand('copy'); } catch (e2) { ok = false; }
      ta.remove();
    }
    btn.textContent = ok ? 'Copied' : 'Select it';
    setTimeout(() => { btn.textContent = 'Copy'; }, 1600);
  }

  function notice(kind, body, action) {
    return h('div', { class: 'notice ' + (kind || '') }, h('div', { class: 'grow' }, body), action || null);
  }

  function caseText(c, armed) {
    if (!c) return '';
    if (c.finished) return 'The traffic has finished. What it sent stays in your portal.';
    if (c.running) return 'The traffic is running: ' + dur(c.ends_in) + ' left.';
    return (armed ? 'Armed: it starts in ' : 'The traffic starts in ') + dur(c.starts_in) + '.';
  }

  // Capitalize a list item, but never a device name (core-sw-01 stays as it's written).
  const cap = s => (/^[a-z]+(?=[\s'’])/.test(s) ? s.charAt(0).toUpperCase() + s.slice(1) : s);

  function stat(big, small) {
    return h('div', { class: 'stat' }, h('b', null, big), h('span', null, small));
  }

  // ------------------------------------------------------------------ home: the tiles
  function homePage() {
    const st = S.status || {};
    const all = S.cat.labs;
    const P = progressAll();
    const done = all.filter(l => (l.page === 'portal' ? (st.portal || {}).connected : P[l.id] && P[l.id].done)).length;
    const wrap = h('div', { class: 'home' });
    wrap.append(h('div', { class: 'hero' },
      h('div', null,
        h('h1', null, 'Labs'),
        h('p', null, st.classroom
          ? 'In each lab a customer has a problem and you are the SE. Read it here, run its commands in your lab host’s '
            + 'terminal, and work in your own Kentik portal. Take them in the order your instructor calls.'
          : 'In each lab a customer has a problem and you are the SE. Launch it here, work in your own '
            + 'Kentik portal, and check your work here. Take them in the order your instructor calls, or any order you like.')),
      h('div', { class: 'hero-stats' },
        stat(done + ' of ' + all.length, 'done in this browser'),
        st.classroom ? null : stat(st.network ? 'Running' : 'Stopped', 'lab network'))));
    wrap.append(...homeNotices());
    for (const t of S.cat.tracks) {
      const items = all.filter(l => l.track === t.id);
      wrap.append(h('section', { class: 'track', 'aria-labelledby': 'tr-' + t.id },
        h('div', { class: 'track-head' }, h('h2', { id: 'tr-' + t.id }, t.title), h('span', null, t.sub)),
        h('div', { class: 'tiles' }, items.map(tile))));
    }
    return wrap;
  }

  function homeNotices() {
    const st = S.status || {};
    const out = [];
    if (st.classroom) {
      out.push(notice('lab', [h('b', null, 'The class copy. '), 'Read each lab here, ask the customer and take hints. '
        + 'Its commands run in your own lab host’s terminal: each one has a Copy button.']));
      out.push(notice('', [h('b', null, 'Your portal. '), 'Save your own Kentik email and API token on your lab host, in its terminal: ',
        h('code', null, 'python3 lab.py portal set')], h('a', { class: 'btn small', href: '#/portal' }, 'How')));
      return out;
    }
    const open = st.open_id && labById(st.open_id);
    if (open) {
      out.push(notice('lab', [h('b', null, 'Open now: ' + open.label + ', ' + open.title + (/[.?!]$/.test(open.title) ? ' ' : '. ')),
        st.case ? caseText(st.case, open.arm) : 'Its fault is live on this host.'],
        h('a', { class: 'btn primary small', href: '#/lab/' + open.id }, 'Go to it')));
    }
    if (st.linux === false) {
      out.push(notice('warn', [h('b', null, 'This isn’t your lab host. '),
        'The labs run on your Linux lab host; here you can read them, but not launch them.']));
    } else if (st.root === false) {
      out.push(notice('warn', [h('b', null, 'Read only. '), 'The site isn’t running with sudo, so it can’t launch labs. '
        + 'Stop it with Ctrl-C and start it again with ', h('code', null, 'sudo python3 lab.py ui'), '.']));
    }
    if (!(st.portal || {}).connected) {
      out.push(notice('', [h('b', null, 'Connect your portal. '), 'Save your Kentik email and API token here, so the '
        + 'site can check them now, and set labs up and clean them away for you later.'],
        h('a', { class: 'btn small', href: '#/portal' }, 'Your portal')));
    }
    return out;
  }

  function tile(l) {
    const st = S.status || {};
    const isOpen = st.open_id === l.id;
    const done = l.page === 'portal' ? (st.portal || {}).connected : progress(l.id).done;
    return h('a', { class: 'tile' + (l.page ? ' page' : ''), href: l.page ? '#/' + l.page : '#/lab/' + l.id },
      h('div', { class: 'tile-art', 'aria-hidden': 'true', html: window.KlabArt ? KlabArt.draw(l.art) : '' }),
      isOpen ? h('span', { class: 'tile-flag open' }, 'Open now') : done ? h('span', { class: 'tile-flag done' }, 'Done') : null,
      h('div', { class: 'tile-body' },
        h('span', { class: 'tile-label' }, l.label),
        h('span', { class: 'tile-title' }, l.title),
        h('span', { class: 'tile-line' }, l.line),
        h('span', { class: 'tile-meta' }, h('span', null, l.time + ' min'), h('span', null, '·'), h('span', null, l.level))));
  }

  // ------------------------------------------------------------------ a lab's page
  function labPage(id) {
    const l = labById(id);
    if (!l) {
      return h('div', null, h('a', { class: 'crumb', href: '#/' }, '← All labs'),
        h('div', { class: 'page-head' }, h('h1', null, 'No lab called “' + id + '”'), h('p', null, 'Pick one from the list.')));
    }
    if (l.page) { setTimeout(() => { location.hash = '#/' + l.page; }); return h('div'); }
    const p = progress(l.id);
    const st = S.status || {};
    const track = S.cat.tracks.find(t => t.id === l.track);
    restoreHints(l);
    const wrap = h('div', { class: 'lab' });
    wrap.append(h('a', { class: 'crumb', href: '#/' }, '← All labs'));
    wrap.append(h('div', { class: 'lab-head' },
      h('div', { class: 'lab-head-art', 'aria-hidden': 'true', html: window.KlabArt ? KlabArt.draw(l.art) : '' }),
      h('div', null,
        h('span', { class: 'tile-label' }, l.label + (track ? ' · ' + track.title : '')),
        h('h1', null, l.title),
        h('p', { class: 'lab-goal' }, rich(l.goal)),
        h('div', { class: 'chips', id: 'labChips' }, chips(l, p, st)))));
    const mainCol = h('div', { class: 'lab-main' });
    if (l.ticket) mainCol.append(ticketCard(l));
    else if (l.find && l.find.length) {
      mainCol.append(h('section', { class: 'card' }, h('h3', null, 'What to find out'),
        h('ul', { class: 'find' }, l.find.map(f => h('li', null, rich(f))))));
    }
    mainCol.append(h('section', { class: 'card' }, h('h3', null, 'Steps'),
      h('ol', { class: 'steps' }, l.steps.map((s, i) => stepItem(l, s, i)))));
    mainCol.append(h('div', { class: 'pair' },
      h('section', { class: 'card look' }, h('h3', null, 'What success looks like'), h('p', null, rich(l.look))),
      h('section', { class: 'card stuck' }, h('h3', null, 'If you’re stuck'), h('p', null, rich(l.stuck)))));
    mainCol.append(doneBlock(l, p));
    const side = h('aside', { class: 'side', 'aria-label': 'Run the lab' },
      runCard(l),
      l.asks ? askCard(l) : null,
      l.hints ? hintCard(l) : null,
      portalCard(l),
      instructor() ? instructorCard(l) : null,
      classroom() ? null : h('section', { class: 'card' }, h('h3', null, 'What the host said'),
        h('pre', { class: 'console', id: 'console', 'aria-live': 'polite' }, logLines(l.id))));
    wrap.append(h('div', { class: 'lab-grid' }, mainCol, side));
    return wrap;
  }

  function chips(l, p, st) {
    return [
      h('span', { class: 'chip' }, 'About ' + l.time + ' minutes'),
      h('span', { class: 'chip' }, l.level),
      st.open_id === l.id ? h('span', { class: 'chip open' }, 'Open now') : null,
      p.done ? h('span', { class: 'chip done' }, 'Done') : null,
    ];
  }

  function ticketCard(l) {
    const [who, ...role] = String(S.cat.customer || 'The customer').split(', ');
    return h('section', { class: 'card ticket' },
      h('h3', null, l.arm ? 'The ticket (it arrives the morning after you arm the lab)' : 'The ticket'),
      h('div', { class: 'ticket-from' }, h('span', { class: 'avatar', 'aria-hidden': 'true' }, who.charAt(0)),
        h('div', null, h('b', null, who), h('span', null, role.join(', ')))),
      h('p', { class: 'ticket-body' }, rich(l.ticket.lines.join(' '))),
      l.find && l.find.length ? [h('h3', { class: 'find-h' }, 'What you have to find'),
        h('ul', { class: 'find' }, l.find.map(f => h('li', null, rich(f))))] : null);
  }

  function stepItem(l, s, i) {
    const text = typeof s === 'string' ? s : s.text;
    const li = h('li', { class: 'step' });
    const btn = h('button', { class: 'step-n', type: 'button' });
    const paint = () => {
      const on = !!progress(l.id).steps[i];
      li.classList.toggle('ticked', on);
      btn.textContent = on ? '✓' : String(i + 1);
      btn.setAttribute('aria-pressed', String(on));
      btn.title = on ? 'Done. Click to untick.' : 'Tick it off when it’s done';
      btn.setAttribute('aria-label', 'Step ' + (i + 1) + (on ? ', done' : ''));
    };
    btn.addEventListener('click', () => {
      const p = progress(l.id);
      p.steps[i] = !p.steps[i];
      saveProgress(l.id, p);
      paint();
    });
    paint();
    li.append(btn, h('div', { class: 'step-text' }, rich(text), typeof s === 'object' && s.cmd ? cmdBox(s.cmd) : null));
    return li;
  }

  function doneBlock(l, p) {
    const next = nextLab(l);
    const btn = h('button', { class: 'btn' + (p.done ? '' : ' primary'), type: 'button' }, p.done ? 'Mark as not done' : 'Mark as done');
    btn.addEventListener('click', () => setDone(l, !progress(l.id).done));
    return h('div', { class: 'done-block' },
      p.done && l.key ? h('section', { class: 'card debrief' }, h('h3', null, 'The takeaway'), h('p', null, rich(l.key))) : null,
      h('div', { class: 'done-row' }, btn,
        p.done && next ? h('a', { class: 'btn ghost', href: '#/lab/' + next.id }, 'Next: ' + next.label + ', ' + next.title + ' →') : null,
        !p.done ? h('span', { class: 'muted' }, 'Marking it done shows the takeaway. It’s kept in this browser only.') : null));
  }

  function setDone(l, on) {
    const p = progress(l.id);
    p.done = on;
    saveProgress(l.id, p);
    render(true);
  }

  function nextLab(l) {
    const list = S.cat.labs.filter(x => !x.page);
    const i = list.findIndex(x => x.id === l.id);
    return list.slice(i + 1).find(x => !progress(x.id).done) || null;
  }

  // ---- the panel on the right: run it
  // A command with what it does, for the class copy's run card.
  function cmdRow(label, cmd) {
    return h('div', { class: 'cmd-row' }, h('p', { class: 'cmd-label' }, label), cmdBox(cmd));
  }

  function classRunCard(l) {
    const card = h('section', { class: 'card run', id: 'run' }, h('h3', null, 'Run it in your lab host’s terminal'));
    if (l.engine == null) {
      card.append(h('p', { class: 'muted' }, 'Nothing to run on your host for this one: it all happens in your portal. Follow the steps.'));
      return card;
    }
    if (l.arm) {
      card.append(cmdRow('Arm it for tonight, and leave the lab network running', 'sudo python3 lab.py start 9'),
        cmdRow('Or a dry run that starts in 5 minutes', 'sudo python3 lab.py start 9 --in 5'));
    } else {
      card.append(cmdRow(l.engine === 0 ? 'Put the network back to healthy' : 'Open this lab', 'sudo python3 lab.py start ' + l.engine));
    }
    if (l.engine > 0) {
      card.append(cmdRow('Check your work', 'sudo python3 lab.py check'), cmdRow('Back to healthy', 'sudo python3 lab.py start 0'));
    }
    card.append(h('p', { class: 'muted small run-note' }, 'First lab of the day? Start the lab network once: ',
      h('code', null, 'sudo python3 lab.py up'), '. At the end: ', h('code', null, 'sudo python3 lab.py down'), '.'));
    return card;
  }

  function runCard(l) {
    if (classroom()) return classRunCard(l);
    const st = S.status || {};
    const card = h('section', { class: 'card run', id: 'run' });
    card.append(h('h3', null, 'Run it on this host'));
    if (l.engine == null) {
      card.append(h('p', { class: 'muted' }, 'Nothing to launch for this one: it all happens in your portal. Follow the steps.'));
      return card;
    }
    const isOpen = l.engine > 0 && st.open === l.engine;
    const openLab = st.open_id && labById(st.open_id);
    let dot = '', line = '';
    if (!st.network) { line = 'The lab network is stopped. Launching starts it.'; }
    else if (l.engine === 0) {
      if (!st.open) { dot = 'good'; line = 'Running and healthy: ready for this lab.'; }
      else { dot = 'warn'; line = (openLab ? openLab.label : 'Another lab') + ' is open. Launching puts the network back to healthy.'; }
    } else if (isOpen) {
      dot = 'lab'; line = 'This lab is open on this host.' + (st.case ? ' ' + caseText(st.case, l.arm) : '');
    } else if (st.open) {
      dot = 'warn'; line = (openLab ? openLab.label + ' is open' : 'Another lab is open') + '. Launching this one replaces it.';
    } else { dot = 'good'; line = 'Running and healthy. Launch to open this lab.'; }
    if (st.network && st.sending_for) line += ' The devices have been sending for ' + dur(st.sending_for) + '.';
    card.append(h('div', { class: 'run-state' }, h('span', { class: 'dot ' + dot, 'aria-hidden': 'true' }), h('span', null, line)));

    const B = (kind, label, cls, fn, disabled, title) => {
      const b = h('button', { class: 'btn ' + (cls || ''), type: 'button', disabled: !!S.busy || disabled, title },
        S.busy === kind ? h('span', { class: 'spin', 'aria-hidden': 'true' }) : null, label);
      b.addEventListener('click', fn);
      return b;
    };
    if (l.arm) {
      card.append(B('launch', isOpen ? 'Arm it again for tonight' : 'Arm for tonight', 'primary wide', () => launch(l, 'tonight')));
      card.append(h('div', { class: 'run-row' }, B('soon', 'Dry run: start in 5 minutes', '', () => launch(l, 'soon'))));
    } else {
      card.append(B('launch', l.engine === 0 ? 'Put the network back to healthy' : isOpen ? 'Launch it again' : 'Launch this lab',
        'primary wide', () => launch(l)));
    }
    const row = h('div', { class: 'run-row' });
    if (l.engine > 0) {
      row.append(B('check', 'Check my work', '', () => check(l), !isOpen, isOpen ? null : 'Launch this lab first'));
    }
    if (st.network && st.open) row.append(B('healthy', 'Back to healthy', '', () => healthy(l)));
    if (row.childNodes.length) card.append(row);
    if (st.network) {
      card.append(h('div', { class: 'run-row' }, B('stop', 'Stop the lab network', 'ghost', () => stop(l))));
    }
    if (S.root[l.id]) {
      card.append(h('div', { class: 'root-box' },
        h('p', null, S.root[l.id].terminal ? 'Run this in your lab host’s terminal:'
          : 'The site isn’t running with sudo, so run this in a terminal on this host:'), cmdBox(S.root[l.id].cmd)));
    }
    return card;
  }

  function refreshRun(l) {
    const old = $('#run');
    if (old) old.replaceWith(runCard(l));
    const chipsEl = $('#labChips');
    if (chipsEl) fill(chipsEl, chips(l, progress(l.id), S.status || {}));
  }

  function logLines(id) {
    return (S.log[id] || []).map(x => h('span', { class: x.kind }, x.text + '\n'));
  }

  function log(id, text, kind) {
    if (!text) return;
    const list = S.log[id] || (S.log[id] = []);
    list.push({ kind: kind || 'say', text: text.trim() });
    if (list.length > 30) list.shift();
    const el = $('#console');
    if (el && route().id === id) {
      fill(el, logLines(id));
      el.scrollTop = el.scrollHeight;
    }
  }

  async function act(l, kind, path, body, after) {
    if (S.busy) return null;
    S.busy = kind;
    refreshRun(l);
    let result = null;
    try {
      result = await api(path, body);
      if (result.needs_root || result.terminal) S.root[l.id] = { cmd: result.cmd, terminal: !!result.terminal };
      else delete S.root[l.id];
      log(l.id, result.output || (result.ok ? 'Done.' : ''), result.ok ? 'say' : 'err');
      if (after) after(result);
    } catch (e) {
      if (e.message !== 'key') log(l.id, e.message, 'err');
    } finally {
      S.busy = '';
      await poll(true);
      if (route().id === l.id) refreshRun(l);
    }
    return result;
  }

  function launch(l, when) {
    const st = S.status || {};
    const openLab = st.open_id && labById(st.open_id);
    if (l.engine > 0 && st.open && st.open !== l.engine && openLab
        && !window.confirm(openLab.label + ' (' + openLab.title + ') is open. Close it and launch ' + l.label + ' instead?')) return;
    act(l, when === 'soon' ? 'soon' : 'launch', '/api/launch', { id: l.id, when: when || null });
  }

  function check(l) {
    act(l, 'check', '/api/check', {}, r => {
      if (r.ok && /^Solved/.test(r.output || '') && !progress(l.id).done) setDone(l, true);
    });
  }

  function healthy(l) { act(l, 'healthy', '/api/healthy', {}); }

  function stop(l) {
    if (!window.confirm('Stop the lab network? The made-up devices stop sending and the open lab closes. Your agent keeps running.')) return;
    act(l, 'stop', '/api/stop', {});
  }

  // ---- ask the customer
  function askCard(l) {
    const order = Object.keys(S.cat.questions).filter(t => l.asks.includes(t));
    const chat = h('div', { class: 'chat', id: 'chat' }, (S.chats[l.id] || []).map(bubbles));
    return h('section', { class: 'card ask' },
      h('h3', null, 'Ask the customer'),
      h('div', { class: 'ask-topics' }, order.map(t => {
        const b = h('button', { type: 'button' }, S.cat.questions[t]);
        b.addEventListener('click', () => ask(l, t));
        return b;
      })),
      chat,
      l.track === 'flow' ? tellForm(l) : null);
  }

  function bubbles(m) {
    return [h('div', { class: 'bubble q' }, m.q), h('div', { class: 'bubble a' }, h('small', null, m.who), rich(m.a))];
  }

  function addChat(l, m) {
    (S.chats[l.id] || (S.chats[l.id] = [])).push(m);
    const el = $('#chat');
    if (el) {
      el.append(...bubbles(m));
      el.lastChild.scrollIntoView({ block: 'nearest' });
    }
  }

  async function ask(l, topic) {
    try {
      const r = await api('/api/ask', { id: l.id, topic });
      addChat(l, r);
    } catch (e) {
      if (e.message !== 'key') log(l.id, e.message, 'err');
    }
  }

  function tellForm(l) {
    const port = h('input', { type: 'number', min: 1, max: 65535, placeholder: 'port', 'aria-label': 'UDP port' });
    const dev = h('input', { type: 'text', placeholder: 'device name', 'aria-label': 'Device name', spellcheck: 'false' });
    const where = h('select', { 'aria-label': 'Export from' },
      h('option', { value: 'loopback' }, 'its loopback'), h('option', { value: 'interface' }, 'an interface'));
    const b1 = h('button', { class: 'btn small', type: 'button' }, 'Ask');
    const b2 = h('button', { class: 'btn small', type: 'button' }, 'Ask');
    const who = String(S.cat.customer || '').split(',')[0];
    const out = h('div', { class: 'tell-out' });
    const send = async (request, question) => {
      if (classroom()) {                           // nothing runs here: the customer answers in your terminal
        fill(out, h('p', { class: 'muted small' }, 'Run this in your lab host’s terminal. The customer answers there.'),
          cmdBox('sudo python3 lab.py tell ' + request.join(' ')));
        return;
      }
      const r = await act(l, 'tell', '/api/tell', { request });
      if (r && r.ok) addChat(l, { q: question, a: (r.output || '').replace(new RegExp('^' + who + ':\\s*'), ''), who });
    };
    b1.addEventListener('click', () => {
      const v = port.value.trim();
      if (!/^\d+$/.test(v)) { port.focus(); return; }
      send(['port', v], 'Please export to UDP ' + v + '.');
    });
    b2.addEventListener('click', () => {
      const d = dev.value.trim();
      if (!d) { dev.focus(); return; }
      send(['source', d, where.value], 'Please make ' + d + ' export from ' + (where.value === 'loopback' ? 'its loopback.' : 'an interface.'));
    });
    return h('details', { class: 'tell' },
      h('summary', null, 'Ask the customer to change something'),
      h('div', { class: 'tell-row' }, 'Export to UDP', port, b1),
      h('div', { class: 'tell-row' }, dev, 'exports from', where, b2),
      h('p', { class: 'muted small' }, 'Only when you know what to ask for. The customer does what you say, right or wrong.'),
      out);
  }

  // ---- hints
  function hintCard(l) {
    const shown = S.hints[l.id] || [];
    const card = h('section', { class: 'card hints', id: 'hints' }, h('h3', null, 'Hints'));
    if (!shown.length) card.append(h('p', { class: 'muted' }, 'Each one is more specific than the last. Try the steps first.'));
    shown.forEach(x => card.append(h('div', { class: 'hint' }, h('b', null, 'Hint ' + x.n + ' of ' + x.of + ': '), rich(x.text))));
    if (shown.length < l.hints) {
      const b = h('button', { class: 'btn small', type: 'button' }, shown.length ? 'A more specific hint' : 'Show a hint');
      b.addEventListener('click', () => hint(l, shown.length + 1));
      card.append(h('div', { class: 'run-row' }, b));
    } else {
      card.append(h('p', { class: 'muted small' }, 'That was the last hint. Ask your instructor.'));
    }
    return card;
  }

  async function hint(l, n) {
    try {
      const r = await api('/api/hint?id=' + encodeURIComponent(l.id) + '&n=' + n);
      const list = S.hints[l.id] || (S.hints[l.id] = []);
      if (!list.some(x => x.n === r.n)) list.push(r);
      list.sort((a, b) => a.n - b.n);
      const p = progress(l.id);
      p.hints = Math.max(p.hints || 0, r.n);
      saveProgress(l.id, p);
      const old = $('#hints');
      if (old && route().id === l.id) old.replaceWith(hintCard(l));
    } catch (e) {
      if (e.message !== 'key') log(l.id, e.message, 'err');
    }
  }

  function restoreHints(l) {                       // hints already seen come back after a reload
    const want = progress(l.id).hints || 0;
    const have = (S.hints[l.id] || []).length;
    if (!l.hints || want <= have) return;
    (async () => { for (let n = have + 1; n <= Math.min(want, l.hints); n++) await hint(l, n); })();
  }

  // ---- what the portal needs and gets
  function portalCard(l) {
    if (!l.needs.length && !l.adds.length) return null;
    const b = h('button', { class: 'btn small', type: 'button', disabled: true,
      title: 'Coming next: the site will add these for you through the Kentik API' }, 'Set it up for me');
    return h('section', { class: 'card' },
      h('h3', null, 'Your portal'),
      l.needs.length ? [h('p', { class: 'list-h' }, 'Before you start, it needs'),
        h('ul', { class: 'needs' }, l.needs.map(n => h('li', null, h('span', { class: 'dot', 'aria-hidden': 'true' }), S.cat.adds[n])))] : null,
      l.adds.length ? [h('p', { class: 'list-h' }, 'This lab adds'),
        h('ul', { class: 'needs' }, l.adds.map(a => h('li', null, h('span', { class: 'dot lab', 'aria-hidden': 'true' }), S.cat.adds[a])))] : null,
      h('div', { class: 'run-row soon-row' }, b, h('span', { class: 'soon' }, 'Coming next')),
      h('p', { class: 'muted small' }, 'Done with the labs? ', h('a', { href: '#/reset' }, 'Reset'), ' lists what they added, so you can take it out.'));
  }

  // ---- instructor view
  function instructorCard(l) {
    const a = S.answers[l.id];
    const card = h('section', { class: 'card instructor', id: 'answer' }, h('h3', null, 'Instructor: the answer'));
    if (a) {
      card.append(h('p', null, rich(a.answer || 'No answer written for this one.')));
      if (a.reveal) card.append(h('pre', { class: 'console' }, a.reveal));
    } else {
      const b = h('button', { class: 'btn small', type: 'button' }, 'Show the answer');
      b.addEventListener('click', async () => {
        try {
          S.answers[l.id] = await api('/api/answer?id=' + encodeURIComponent(l.id));
          const old = $('#answer');
          if (old) old.replaceWith(instructorCard(l));
        } catch (e) {
          if (e.message === 'instructor') fill(b.parentNode, h('h3', null, 'Instructor: the answer'),
            h('p', { class: 'muted small' }, 'The answers need the instructor link the terminal printed.'));
          else if (e.message !== 'key') log(l.id, e.message, 'err');
        }
      });
      card.append(h('p', { class: 'muted small' }, 'Keep this off a shared screen.'), b);
    }
    if (l.course) card.append(h('p', { class: 'muted small' }, 'In the course: ', h('code', null, '#/' + l.course)));
    return card;
  }

  // ------------------------------------------------------------------ your portal
  // On the class copy, the portal details stay on each student's own host, entered in its terminal.
  function classPortalPage() {
    return h('div', { class: 'narrow' },
      h('div', { class: 'page-head' }, h('h1', null, 'Your portal'),
        h('p', null, 'Each of you uses your own Kentik portal and your own API token. They stay on your own lab host, '
          + 'never on this class copy: the labs read them there.')),
      h('div', { class: 'two' },
        h('section', { class: 'card' }, h('h3', null, 'In your lab host’s terminal'),
          cmdRow('Save your email, API token and region, and test them', 'python3 lab.py portal set'),
          cmdRow('See what’s saved, and test it again', 'python3 lab.py portal'),
          cmdRow('Remove them from the host', 'python3 lab.py portal forget')),
        h('section', { class: 'card' }, h('h3', null, 'Where things stand'),
          h('ul', { class: 'facts' },
            h('li', null, h('b', null, 'Kept in: '), h('code', null, '~/.kentik.env'),
              ' on your lab host, readable only by you. The token never shows again once it’s saved.'),
            h('li', null, h('b', null, 'Your API token: '), 'from your own user settings in the portal. Ask your instructor if you can’t find it.'),
            h('li', null, h('b', null, 'What the labs do with it: '), 'today, one read-only call, your device list, to test it. '
              + 'Next, set each lab up in your portal, and take out what the labs added when you reset.')))));
  }

  function portalPage() {
    if (classroom()) return classPortalPage();
    const pc = (S.status && S.status.portal) || {};
    const email = h('input', { type: 'email', name: 'email', autocomplete: 'off', value: pc.email || '',
      placeholder: 'you@example.com', required: true, spellcheck: 'false' });
    const token = h('input', { type: 'password', name: 'token', autocomplete: 'new-password', spellcheck: 'false',
      placeholder: pc.token_set ? 'Saved' + (pc.token_end ? ', ends …' + pc.token_end : '') + '. Leave empty to keep it.' : 'Paste your API token' });
    const region = pc.region || 'us';
    const radios = h('div', { class: 'radios', role: 'radiogroup', 'aria-label': 'Region' },
      [['us', 'US'], ['eu', 'EU']].map(([v, t]) => h('label', null,
        h('input', { type: 'radio', name: 'region', value: v, checked: region === v }), t)));
    const msg = h('div', { id: 'pMsg' }, portalMsg());
    const save = h('button', { class: 'btn primary', type: 'submit' }, 'Save');
    const testB = h('button', { class: 'btn', type: 'button', disabled: !pc.connected }, 'Test the connection');
    const forget = h('button', { class: 'btn ghost', type: 'button', disabled: !pc.email && !pc.token_set }, 'Forget them');
    const form = h('form', { class: 'form', autocomplete: 'off' },
      h('label', { class: 'field' }, h('span', null, 'Email'), email, h('small', null, 'The one you sign in to your Kentik portal with.')),
      h('label', { class: 'field' }, h('span', null, 'API token'), token,
        h('small', null, 'Yours, from your user settings in the portal. Ask your instructor if you can’t find it.')),
      h('div', { class: 'field' }, h('span', null, 'Region'), radios, h('small', null, 'Where your portal lives: US unless you were told EU.')),
      h('div', { class: 'run-row' }, save, testB, forget), msg);
    form.addEventListener('submit', async e => {
      e.preventDefault();
      const r = form.querySelector('input[name=region]:checked');
      try {
        const saved = await api('/api/portal', { email: email.value, token: token.value, region: r ? r.value : 'us' });
        if (S.status) S.status.portal = saved;
        S.portalMsg = { kind: 'good', text: 'Saved on this host. Test the connection to check them.' };
      } catch (err) {
        if (err.message === 'key') return;
        S.portalMsg = { kind: 'bad', text: err.message };
      }
      render(true);
    });
    testB.addEventListener('click', async () => {
      testB.disabled = true;
      fill(testB, h('span', { class: 'spin', 'aria-hidden': 'true' }), 'Testing…');
      try {
        const r = await api('/api/portal/test', {});
        S.portalMsg = { kind: r.ok ? 'good' : 'bad', text: r.message };
      } catch (err) {
        if (err.message === 'key') return;
        S.portalMsg = { kind: 'bad', text: err.message };
      }
      await poll(true);
      render(true);
    });
    forget.addEventListener('click', async () => {
      if (!window.confirm('Remove your email and API token from this host?')) return;
      try {
        const r = await api('/api/portal/forget', {});
        if (S.status) S.status.portal = r;
        S.portalMsg = { kind: 'good', text: 'Removed from this host.' };
      } catch (err) {
        if (err.message === 'key') return;
        S.portalMsg = { kind: 'bad', text: err.message };
      }
      render(true);
    });

    const tested = pc.tested && pc.tested.at ? pc.tested : null;
    const facts = h('section', { class: 'card', id: 'pFacts' }, h('h3', null, 'Where things stand'),
      h('ul', { class: 'facts' },
        h('li', null, h('b', null, 'Connection: '), !pc.connected ? 'not saved yet.'
          : tested ? (tested.ok ? 'working, ' : 'not working, ') + 'last tested ' + new Date(tested.at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + '. ' + tested.message
            : 'saved, not tested yet.'),
        h('li', null, h('b', null, 'Kept in: '), h('code', null, pc.file || '~/.kentik.env'),
          ', on this host, readable only by you. Never in the repo, and never sent back to this page: it shows only the token’s last four characters.'),
        h('li', null, h('b', null, 'What the site does with them: '), 'today, one read-only call, your device list, to test them. '
          + 'Next, it sets each lab up in your portal and takes out what the labs added when you reset.'),
        h('li', null, h('b', null, 'Changes to your portal: '), pc.writes ? 'on.' : 'off for now. Until they are tested '
          + 'against a real portal, the site tells you what to add and remove, and you click.')));

    const todo = instructor() ? h('section', { class: 'card instructor' }, h('h3', null, 'Instructor: still to decide'),
      h('ul', { class: 'facts' },
        h('li', null, 'Who gives each student an API token: their own user in their own portal, or one made for the class.'),
        h('li', null, 'Whether a student’s token may change their portal (add the lab devices, remove them on reset), or only read.'),
        h('li', null, 'Where the token lives between classes: kept on the lab host, or entered each time.'),
        h('li', null, 'Kentik SE team: confirm the API calls for adding and removing devices, and whether an agent can be removed by API.'))) : null;

    return h('div', { class: 'narrow' },
      h('div', { class: 'page-head' }, h('h1', null, 'Your portal'),
        h('p', null, 'The labs run in your own Kentik portal. Save its email and API token here so the site can check them now, '
          + 'and later add each lab’s devices for you and clean them away when you reset.')),
      h('div', { class: 'two' }, h('section', { class: 'card' }, h('h3', null, 'Connection details'), form), h('div', null, facts, todo)));
  }

  function portalMsg() {
    const m = S.portalMsg;
    return m ? h('div', { class: 'result ' + m.kind, role: 'status' }, m.text) : null;
  }

  // ------------------------------------------------------------------ reset
  function resetPage() {
    if (!S.plan) {
      api('/api/reset').then(plan => { S.plan = plan; if (route().page === 'reset') render(true); })
        .catch(() => { /* shown by the top bar */ });
      return h('p', { class: 'loading' }, 'Working out what a reset takes out…');
    }
    const plan = S.plan;
    const r = S.resetResult;
    const lists = [
      h('p', { class: 'list-h' }, classroom() ? 'On your lab host' : 'On this host'),
      h('ul', { class: 'list' }, plan.host.map(x => h('li', null, h('span', null, x)))),
      h('p', { class: 'list-h' }, 'In your portal'),
      h('ul', { class: 'list portal' }, plan.portal.map(x => h('li', null, h('span', null, cap(x.what), x.how ? h('small', null, x.how) : null)))),
      h('p', { class: 'list-h' }, 'Stays'),
      h('ul', { class: 'list keep' }, plan.keep.map(x => h('li', null, h('span', null, x))))];
    let action;
    if (classroom()) {
      const clear = h('button', { class: 'btn', type: 'button' }, 'Clear my progress in this browser');
      clear.addEventListener('click', () => {
        if (!window.confirm('Clear the steps you ticked and the labs you marked done, in this browser?')) return;
        store.del('klab.progress');
        S.hints = {}; S.chats = {};
        S.resetResult = { cleared: true };
        render();
      });
      action = [h('p', { class: 'list-h' }, 'Run it'), cmdRow('In your lab host’s terminal', 'sudo python3 lab.py down'), h('div', { class: 'run-row' }, clear)];
    } else {
      const b = h('button', { class: 'btn primary', type: 'button', disabled: !!S.busy }, 'Reset the labs');
      b.addEventListener('click', async () => {
        if (!window.confirm('Reset the labs on this host? Your agent stays.')) return;
        b.disabled = true;
        fill(b, h('span', { class: 'spin', 'aria-hidden': 'true' }), 'Working…');
        try {
          S.resetResult = await api('/api/reset', {});
          store.del('klab.progress');
          S.hints = {}; S.chats = {}; S.answers = {}; S.root = {};
        } catch (err) {
          if (err.message === 'key') return;
          S.resetResult = { error: err.message };
        }
        await poll(true);
        render();
        window.scrollTo(0, 0);
      });
      action = h('div', { class: 'run-row' }, b);
    }
    return h('div', { class: 'narrow' },
      h('div', { class: 'page-head' }, h('h1', null, 'Reset'),
        h('p', null, 'Take out what the labs added, so a lab can start again from clean. Your Universal Agent always stays: the labs need it.')),
      r ? resetDone(r) : null,
      plan.note ? notice('warn', plan.note) : null,
      h('section', { class: 'card reset-card' }, lists, action));
  }

  function resetDone(r) {
    if (r.error) return notice('bad', [h('b', null, 'The reset didn’t run. '), r.error]);
    if (r.cleared) return notice('', [h('b', null, 'Cleared. '), 'Your progress in this browser is gone. Stop the lab network in your host’s terminal, and take the portal items out by hand.']);
    const host = r.host || {};
    const plan = r.plan || { portal: [] };
    return h('section', { class: 'card reset-done' },
      h('h3', null, 'Reset: what happened'),
      host.needs_root ? [h('p', null, 'The site isn’t running with sudo, so stop the lab network yourself:'), cmdBox(host.cmd)]
        : h('pre', { class: 'console' }, host.output || 'The lab network is stopped.'),
      h('p', null, 'Progress in this browser is cleared. ' + (plan.writes ? '' : 'Now take these out of your portal by hand:')),
      plan.writes ? null : h('ul', { class: 'list portal' }, plan.portal.map(x => h('li', null, h('span', null, cap(x.what), h('small', null, x.how))))));
  }

  // ------------------------------------------------------------------ when the site can't be reached
  function keyPage() {
    return h('div', { class: 'narrow' },
      h('div', { class: 'page-head' }, h('h1', null, 'Open the link from the terminal'),
        h('p', null, 'The lab site only answers a page that carries its key, so no other page in your browser can drive your lab host. '
          + 'When you started the site, the terminal printed a link with the key in it: open that link. '
          + 'If you started the site again since, the key changed, so use the new link.')),
      h('section', { class: 'card' }, h('h3', null, 'Start the site'),
        h('p', null, 'On your lab host, in the kentik-training-labs folder:'), cmdBox('sudo python3 lab.py ui'),
        h('p', { class: 'muted small' }, 'In a class, your instructor may run a class copy for the room: open the address they give you.')));
  }

  function offlinePage() {
    return h('div', { class: 'narrow' },
      h('div', { class: 'page-head' }, h('h1', null, 'The lab site isn’t answering'), h('p', null, S.bootError)),
      h('section', { class: 'card' }, h('h3', null, 'Start it again'), cmdBox('sudo python3 lab.py ui'),
        h('p', { class: 'muted small' }, 'Then open the new link it prints.')));
  }

  // ------------------------------------------------------------------ status, every few seconds
  function sig(st) {
    if (!st) return '';
    const c = st.case;
    return JSON.stringify([st.root, st.linux, st.network, st.open, st.open_id, st.listening,
      Math.floor((st.sending_for || 0) / 60),
      c ? [c.running, c.finished, Math.ceil(c.starts_in / 60), Math.ceil(c.ends_in / 60)] : null,
      st.portal ? [st.portal.connected, st.portal.email, (st.portal.tested || {}).at] : null]);
  }

  async function poll(quiet) {
    let st;
    try { st = await api('/api/status'); } catch (e) { return; }
    if (!S.cat) {                                   // the site came back after failing at the start
      try { S.cat = await api('/api/catalog'); S.bootError = ''; S.status = st; render(); } catch (e) { /* next time */ }
      return;
    }
    const changed = sig(st) !== sig(S.status);
    S.status = st;
    renderTop();
    if (!changed || quiet) return;
    const r = route();
    if (r.page === 'home') render(true);
    else if (r.page === 'lab') { const l = labById(r.id); if (l && !S.busy) refreshRun(l); }
  }

  let timer = null;
  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      if (!document.hidden && !S.keyProblem) await poll();
      schedule();
    }, 4000);
  }

  // ------------------------------------------------------------------ theme, colors, instructor view
  function initTools() {
    const root = document.documentElement;
    const theme = store.get('klab.theme', null);
    if (theme === 'dark' || theme === 'light') root.dataset.theme = theme;
    if (store.get('klab.brand', null) === 'infoblox') root.dataset.brand = 'infoblox';
    const tBtn = $('#btnTheme'), bBtn = $('#btnBrand');
    const dark = () => (root.dataset.theme ? root.dataset.theme === 'dark'
      : window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
    const label = () => {
      tBtn.textContent = dark() ? 'Light' : 'Dark';
      tBtn.setAttribute('aria-pressed', String(dark()));
      bBtn.textContent = root.dataset.brand === 'infoblox' ? 'Kentik colors' : 'Infoblox colors';
    };
    tBtn.addEventListener('click', () => {
      const next = dark() ? 'light' : 'dark';
      root.dataset.theme = next;
      store.set('klab.theme', next);
      label();
    });
    bBtn.addEventListener('click', () => {
      if (root.dataset.brand === 'infoblox') { delete root.dataset.brand; store.del('klab.brand'); }
      else { root.dataset.brand = 'infoblox'; store.set('klab.brand', 'infoblox'); }
      label();
    });
    label();

    const box = $('#instructor');
    box.checked = instructor();
    box.addEventListener('change', () => {
      if (box.checked && !window.confirm('Instructor view shows each lab’s answer on its page. Turn it on?')) {
        box.checked = false;
        return;
      }
      store.set('klab.instructor', box.checked);
      render(true);
    });
  }

  // ------------------------------------------------------------------ start
  async function boot() {
    initTools();
    window.addEventListener('hashchange', () => {
      render();
      window.scrollTo(0, 0);
      $('#main').focus({ preventScroll: true });
    });
    document.addEventListener('visibilitychange', () => { if (!document.hidden && !S.keyProblem) poll(); });
    try {
      const [cat, st] = await Promise.all([api('/api/catalog'), api('/api/status')]);
      S.cat = cat;
      S.status = st;
    } catch (e) {
      if (e.message !== 'key') S.bootError = e.message;
    }
    render();
    schedule();
  }

  boot();
})();
