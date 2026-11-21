// The lab site's tile drawings. One per lab, in the course's colors: devices teal, people and the outside gray,
// servers and clouds blue, Kentik and flow records purple, warnings amber, problems red. Each shows the symptom
// the customer sees, never the cause: a tile must not give its lab away, any more than its ticket does.
// KlabArt.draw(key) returns an SVG string. Sizes are in the drawing's own units (300 by 130).
window.KlabArt = (() => {
  const W = 300, H = 130;
  const st = o => Object.entries(o).map(([k, v]) => `${k}:${v}`).join(';');
  const rect = (x, y, w, h, o = {}) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${o.rx != null ? o.rx : 7}" style="${st({ fill: o.f || 'none', stroke: o.s || 'none', 'stroke-width': (o.sw || 1) + 'px', ...(o.dash ? { 'stroke-dasharray': o.dash } : {}), ...(o.op != null ? { opacity: o.op } : {}) })}"/>`;
  const box = (x, y, w, h, c, rx = 6) => rect(x, y, w, h, { f: `var(--${c}-f)`, s: `var(--${c}-s)`, rx });
  const path = (d, o = {}) => `<path d="${d}" style="${st({ fill: o.f || 'none', stroke: o.s || 'var(--border-strong)', 'stroke-width': (o.sw || 1.5) + 'px', 'stroke-linecap': 'round', 'stroke-linejoin': 'round', ...(o.dash ? { 'stroke-dasharray': o.dash } : {}), ...(o.op != null ? { opacity: o.op } : {}) })}"/>`;
  const circle = (cx, cy, r, o = {}) => `<circle cx="${cx}" cy="${cy}" r="${r}" style="${st({ fill: o.f || 'none', stroke: o.s || 'none', 'stroke-width': (o.sw || 1) + 'px', ...(o.op != null ? { opacity: o.op } : {}) })}"/>`;
  const text = (x, y, s, o = {}) => `<text x="${x}" y="${y}" text-anchor="${o.a || 'middle'}" dominant-baseline="central" style="${st({ font: `${o.w || 400} ${o.size || 12}px ${o.mono ? 'var(--mono)' : 'var(--font)'}`, fill: o.c || 'var(--text-2)' })}">${s}</text>`;
  const sq = (x, y, s = 7) => rect(x - s / 2, y - s / 2, s, s, { f: 'var(--c-purple)', rx: 1.5 });

  // Pieces used in several drawings
  const router = (x, y) => box(x, y, 44, 22, 'teal', 6) + path(`M${x + 10} ${y + 11} h24 M${x + 28} ${y + 6} l6 5 -6 5`, { s: 'var(--teal-s)', sw: 1.4 });
  const agent = (cx, cy) => circle(cx, cy, 17, { f: 'var(--purple-f)', s: 'var(--purple-s)', sw: 1.2 }) + text(cx, cy + 0.5, 'UA', { size: 11, w: 500, c: 'var(--purple-h)' });
  const win = (x, y, w, h) => rect(x, y, w, h, { f: 'var(--surface-1)', s: 'var(--border-strong)', rx: 8 })
    + path(`M${x} ${y + 15} h${w}`, { s: 'var(--border)' }) + [0, 1, 2].map(k => circle(x + 10 + k * 8, y + 7.5, 2.4, { f: 'var(--border-strong)' })).join('');
  const bars = (x, y, w, h, vals, c = 'var(--c-blue)') => {
    const bw = w / vals.length;
    return vals.map((v, k) => rect(x + k * bw + 1, y + h - v * h, bw - 2.5, v * h, { f: c, rx: 1.5 })).join('');
  };
  const server = (x, y, w = 46, h = 30) => box(x, y, w, h, 'blue', 6) + [0, 1].map(k => path(`M${x + 8} ${y + 10 + k * 10} h${w - 22}`, { s: 'var(--blue-s)', sw: 1.2 })).join('') + circle(x + w - 9, y + 10, 2, { f: 'var(--blue-s)' });
  const bell = (cx, cy, c = 'amber') => path(`M${cx - 11} ${cy + 7} q2 -3 2 -10 q0 -9 9 -10 q9 1 9 10 q0 7 2 10 z`, { f: `var(--${c}-f)`, s: `var(--${c}-s)`, sw: 1.3 })
    + path(`M${cx - 3} ${cy + 10} q3 3 6 0`, { s: `var(--${c}-s)`, sw: 1.3 });

  const ART = {
    setup: () => win(20, 18, 128, 92)
      + text(30, 46, '$ install the', { a: 'start', mono: true, size: 11, c: 'var(--text-2)' })
      + text(30, 62, '  agent…', { a: 'start', mono: true, size: 11, c: 'var(--text-2)' })
      + rect(30, 74, 7, 12, { f: 'var(--c-purple)', rx: 1 })
      + path('M154 64 h34', { s: 'var(--c-purple)', sw: 1.6, dash: '4 4' })
      + agent(210, 64)
      + path('M228 64 h18', { s: 'var(--c-purple)', sw: 2 })
      + rect(246, 46, 46, 36, { f: 'var(--purple-f)', s: 'var(--purple-s)', rx: 10 })
      + text(269, 64, 'Kentik', { size: 11, w: 500, c: 'var(--purple-h)' }),

    portal: () => win(20, 16, 168, 98)
      + text(32, 44, 'Email', { a: 'start', size: 11, c: 'var(--text-3)' }) + rect(32, 52, 144, 16, { f: 'var(--surface-0)', s: 'var(--border)', rx: 4 })
      + text(32, 80, 'API token', { a: 'start', size: 11, c: 'var(--text-3)' }) + rect(32, 88, 144, 16, { f: 'var(--surface-0)', s: 'var(--border)', rx: 4 })
      + [0, 1, 2, 3, 4, 5, 6].map(k => circle(42 + k * 9, 96, 2.2, { f: 'var(--text-3)' })).join('')
      + circle(238, 60, 16, { s: 'var(--amber-s)', sw: 3 }) + circle(238, 60, 5, { f: 'var(--amber-f)', s: 'var(--amber-s)', sw: 1.5 })
      + path('M254 60 h32 m-8 0 v9 m-10 -9 v7', { s: 'var(--amber-s)', sw: 3 }),

    'first-flows': () => [22, 54, 86].map(y => router(16, y - 11)).join('')
      + [22, 54, 86].map(y => path(`M62 ${y} C 100 ${y}, 104 64, 130 64`, { s: 'var(--c-purple)', sw: 1.4, dash: '4 4' })).join('')
      + sq(90, 31) + sq(96, 58) + sq(90, 82)
      + agent(150, 64)
      + path('M168 64 h22', { s: 'var(--c-purple)', sw: 2 })
      + win(190, 22, 96, 86) + rect(202, 46, 72, 50, { s: 'var(--border-strong)', dash: '4 4', rx: 6 })
      + text(238, 71, '?', { size: 26, w: 500, c: 'var(--text-3)' }),

    'still-nothing': () => [22, 54, 86].map(y => router(16, y - 11)).join('')
      + [22, 54, 86].map(y => path(`M62 ${y} C 100 ${y}, 104 64, 132 64`, { s: 'var(--c-purple)', sw: 1.4, dash: '4 4' })).join('')
      + sq(84, 27) + sq(100, 56) + sq(84, 85) + sq(120, 64)
      + win(150, 18, 136, 94)
      + ['edge', 'core', 'branch'].map((n, k) => text(160, 48 + k * 22, n, { a: 'start', size: 11, c: 'var(--text-3)' })
        + path(`M206 ${48 + k * 22} h70`, { s: 'var(--border-strong)', sw: 1.5 })).join('')
      + text(276, 104, '0', { a: 'end', size: 11, c: 'var(--text-3)' }),

    'one-missing': () => win(20, 12, 262, 104)
      + [['edge-rtr-01', null], ['core-sw-01', [.4, .6, .5, .8, .7, .9, .6, .8]], ['branch-rtr-01', [.3, .5, .4, .6, .5, .7, .5, .6]]]
        .map(([n, v], k) => {
          const y = 44 + k * 24;
          return text(34, y, n, { a: 'start', size: 11, w: 500, c: v ? 'var(--text-2)' : 'var(--amber-t)' })
            + (v ? bars(140, y - 9, 124, 18, v) : path(`M140 ${y} h124`, { s: 'var(--amber-s)', sw: 1.6, dash: '5 4' }) + circle(272, y, 6, { f: 'var(--amber-f)', s: 'var(--amber-s)' }) + text(272, y + 0.5, '!', { size: 10, w: 500, c: 'var(--amber-h)' }));
        }).join(''),

    yesterday: () => rect(18, 20, 126, 92, { f: 'var(--surface-1)', s: 'var(--border-strong)', rx: 8 })
      + text(28, 34, 'Yesterday', { a: 'start', size: 11, w: 500, c: 'var(--text-2)' })
      + bars(28, 48, 106, 52, [.5, .6, .55, .7, .65, .8, .7, .75])
      + rect(156, 20, 126, 92, { f: 'var(--surface-1)', s: 'var(--border-strong)', rx: 8 })
      + text(166, 34, 'Today', { a: 'start', size: 11, w: 500, c: 'var(--text-2)' })
      + path('M166 99 h106', { s: 'var(--border-strong)', sw: 1.5 })
      + circle(266, 34, 7, { f: 'var(--red-f)', s: 'var(--red-s)' }) + path('M263 31 l6 6 m0 -6 l-6 6', { s: 'var(--red-h)', sw: 1.3 }),

    numbers: () => path('M60 22 h180', { s: 'var(--border-strong)' }) + path('M60 22 v6 M240 22 v6', { s: 'var(--border-strong)' })
      + text(150, 14, 'the same users', { size: 11, c: 'var(--text-3)' })
      + rect(64, 34, 52, 70, { f: 'var(--c-blue)', rx: 4 }) + text(90, 116, 'edge-rtr-01', { size: 11, c: 'var(--text-2)' })
      + rect(184, 92, 52, 12, { f: 'var(--c-blue)', rx: 3 }) + text(210, 116, 'core-sw-01', { size: 11, c: 'var(--text-2)' })
      + text(150, 70, '≠', { size: 28, w: 500, c: 'var(--amber-t)' }),

    questions: () => win(18, 14, 186, 102)
      + [.95, .72, .55, .4, .26].map((v, k) => rect(30, 38 + k * 15, 160 * v, 9, { f: k ? 'var(--c-blue)' : 'var(--c-purple)', rx: 2, op: k ? 0.85 : 1 })).join('')
      + circle(246, 58, 24, { f: 'var(--surface-1)', s: 'var(--text-2)', sw: 3 }) + path('M263 75 l18 18', { s: 'var(--text-2)', sw: 5 })
      + text(246, 59, '?', { size: 22, w: 500, c: 'var(--purple-t)' }),

    crawling: () => router(14, 54)
      + rect(66, 50, 164, 30, { f: 'var(--amber-f)', s: 'var(--amber-s)', rx: 15 })
      + Array.from({ length: 22 }, (_, k) => circle(78 + (k % 11) * 14.5, 59 + Math.floor(k / 11) * 12, 3.6, { f: 'var(--c-amber)' })).join('')
      + box(238, 50, 50, 30, 'gray', 15) + text(263, 65.5, 'ISP', { size: 11, w: 500, c: 'var(--gray-h)' })
      + text(148, 32, '100%', { size: 16, w: 500, c: 'var(--amber-t)' })
      + text(148, 100, 'the internet link', { size: 11, c: 'var(--text-3)' }),

    'dns-alert': () => rect(26, 56, 70, 44, { f: 'var(--gray-f)', s: 'var(--gray-s)', rx: 5 }) + path('M16 104 h90', { s: 'var(--gray-s)', sw: 4 })
      + text(61, 78, '.77', { size: 11, mono: true, c: 'var(--gray-h)' })
      + bell(140, 40) + circle(152, 26, 7, { f: 'var(--c-red)' }) + text(152, 26.5, '1', { size: 10, w: 500, c: 'var(--surface-1)' })
      + path('M104 78 C 160 78, 190 70, 232 70', { s: 'var(--border-strong)', sw: 1.4, dash: '4 5' })
      + circle(256, 70, 22, { f: 'var(--gray-f)', s: 'var(--gray-s)' }) + path('M234 70 h44 M256 48 q-12 22 0 44 q12 -22 0 -44', { s: 'var(--gray-s)', sw: 1.2 })
      + text(256, 106, '?', { size: 16, w: 500, c: 'var(--text-3)' }),

    attack: () => Array.from({ length: 9 }, (_, k) => {
      const y = 14 + k * 13;
      return path(`M14 ${y} C 90 ${y}, 140 66, 206 66`, { s: 'var(--c-red)', sw: 1.2, op: 0.75 }) + circle(14, y, 2.6, { f: 'var(--c-red)' });
    }).join('') + server(210, 46, 64, 40) + circle(274, 44, 8, { f: 'var(--red-f)', s: 'var(--red-s)' }) + text(274, 44.5, '!', { size: 11, w: 500, c: 'var(--red-h)' }),

    overnight: () => path('M54 22 a22 22 0 1 0 22 30 a17 17 0 1 1 -22 -30 z', { f: 'var(--amber-f)', s: 'var(--amber-s)', sw: 1.3 })
      + [[110, 24], [146, 40], [190, 18], [232, 34], [270, 20], [96, 50]].map(([x, y]) => circle(x, y, 1.8, { f: 'var(--text-3)' })).join('')
      + server(110, 78) + server(164, 78) + server(218, 78)
      + path('M18 116 h264', { s: 'var(--border)' }),

    'cold-case': () => path('M40 34 h56 l10 10 h110 v66 h-176 z', { f: 'var(--amber-f)', s: 'var(--amber-s)', sw: 1.3 })
      + rect(56, 58, 92, 7, { f: 'var(--surface-1)', rx: 2, op: 0.8 }) + rect(56, 72, 70, 7, { f: 'var(--surface-1)', rx: 2, op: 0.8 }) + rect(56, 86, 82, 7, { f: 'var(--surface-1)', rx: 2, op: 0.8 })
      + circle(214, 70, 26, { f: 'var(--surface-1)', s: 'var(--text-2)', sw: 3 }) + path('M233 89 l22 22', { s: 'var(--text-2)', sw: 5 })
      + text(214, 71, '?', { size: 24, w: 500, c: 'var(--purple-t)' }),

    alerting: () => path('M20 104 h200', { s: 'var(--border-strong)' }) + path('M20 60 h200', { s: 'var(--amber-s)', sw: 1.4, dash: '5 4' })
      + path('M20 96 L 52 92 L 80 94 L 108 88 L 132 50 L 156 30 L 184 34 L 210 40', { s: 'var(--c-blue)', sw: 2.2 })
      + circle(156, 30, 4, { f: 'var(--c-red)' }) + text(30, 52, 'your line', { a: 'start', size: 11, c: 'var(--amber-t)' })
      + bell(258, 54) + path('M240 30 l-6 -6 M276 30 l6 -6', { s: 'var(--amber-s)', sw: 1.6 }),

    nms: () => server(26, 34, 84, 62) + text(68, 108, '127.0.0.1', { size: 11, mono: true, c: 'var(--text-2)' })
      + [['CPU', 156], ['Memory', 236]].map(([n, x]) => path(`M${x - 26} 78 a26 26 0 0 1 52 0`, { s: 'var(--border-strong)', sw: 6 })
        + path(`M${x} 78 l-12 -14`, { s: 'var(--text-3)', sw: 1.6 }) + text(x, 96, n, { size: 11, c: 'var(--text-3)' })).join('')
      + rect(124, 14, 48, 18, { f: 'var(--teal-f)', s: 'var(--teal-s)', rx: 9 }) + text(148, 23.5, 'SNMP', { size: 10, w: 500, c: 'var(--teal-h)' }),

    synthetics: () => agent(34, 72)
      + path('M51 72 C 90 72, 96 46, 130 46 S 170 82, 206 72 S 236 60, 252 64', { s: 'var(--border-strong)', sw: 1.5, dash: '2 5' })
      + [[92, 58], [130, 46], [170, 66], [206, 72]].map(([x, y]) => circle(x, y, 5, { f: 'var(--teal-f)', s: 'var(--teal-s)' })).join('')
      + circle(268, 64, 18, { f: 'var(--blue-f)', s: 'var(--blue-s)' }) + path('M250 64 h36 M268 46 q-10 18 0 36 q10 -18 0 -36', { s: 'var(--blue-s)', sw: 1.1 })
      + text(268, 100, 'example.com', { size: 11, c: 'var(--text-2)' })
      + rect(104, 16, 52, 18, { f: 'var(--green-f)', s: 'var(--green-s)', rx: 9 }) + text(130, 25.5, '12 ms', { size: 10.5, w: 500, c: 'var(--green-h)' }),

    ai: () => rect(18, 18, 150, 44, { f: 'var(--gray-f)', s: 'var(--gray-s)', rx: 12 }) + path('M40 62 l-6 12 l16 -12', { f: 'var(--gray-f)', s: 'var(--gray-s)' })
      + path('M32 34 h118 M32 46 h84', { s: 'var(--gray-s)', sw: 2.4 })
      + rect(112, 68, 170, 48, { f: 'var(--purple-f)', s: 'var(--purple-s)', rx: 12 })
      + path('M128 84 h134 M128 96 h112 M128 108 h70', { s: 'var(--purple-s)', sw: 2.4, op: 0.8 })
      + path('M262 30 l4 10 l10 4 l-10 4 l-4 10 l-4 -10 l-10 -4 l10 -4 z', { f: 'var(--c-purple)' }),
  };

  return {
    keys: Object.keys(ART),
    draw(key) {
      const body = (ART[key] || ART.questions)();
      return `<svg viewBox="0 0 ${W} ${H}" role="presentation" aria-hidden="true" focusable="false">${body}</svg>`;
    },
  };
})();
