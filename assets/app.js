/* Iceland trip browser. Static data in /data, no backend.
   Picks are per-viewer in localStorage — nothing is shared or sent anywhere. */

const $ = (s) => document.querySelector(s);
const D = { places: [], camps: [], fuel: [], routes: null };
let variant = localStorage.getItem('iceland.variant') || 'final';
const PICK_KEY = 'iceland.picks.v1';

/* ---------- picks (local to each viewer's browser) ---------- */
let picks = new Set();
try { picks = new Set(JSON.parse(localStorage.getItem(PICK_KEY) || '[]')); } catch (_) {}
function savePicks() {
  try { localStorage.setItem(PICK_KEY, JSON.stringify([...picks])); } catch (_) {}
  $('#pickCount').textContent = `${picks.size} picked`;
}
function togglePick(name) {
  picks.has(name) ? picks.delete(name) : picks.add(name);
  savePicks();
  document.querySelectorAll(`[data-pick="${CSS.escape(name)}"]`)
    .forEach((b) => b.classList.toggle('on', picks.has(name)));
}

/* ---------- map ---------- */
const map = L.map('map', { scrollWheelZoom: true }).setView([64.9, -18.6], 6);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 18, attribution: '&copy; OpenStreetMap contributors',
}).addTo(map);

const layers = {
  route: L.layerGroup().addTo(map),
  camps: L.layerGroup(),
  fuel: L.layerGroup(),
  places: L.layerGroup(),
};
const dot = (color, r = 5) => ({
  radius: r, color: '#fff', weight: 1.5, fillColor: color, fillOpacity: 1,
});
const markerIndex = new Map();

function focus(name, zoom = 11) {
  const m = markerIndex.get(name);
  if (!m) return;
  map.setView(m.getLatLng(), Math.max(map.getZoom(), zoom));
  m.openPopup();
}

/* ---------- rendering ---------- */
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function starBtn(name) {
  return `<button class="star ${picks.has(name) ? 'on' : ''}" data-pick="${esc(name)}"
    title="Pick this" aria-label="Pick ${esc(name)}">★</button>`;
}

const DAY_COLORS = ['#d1495b', '#e07a1f', '#c9a227', '#3f8f4a', '#1f6f6b', '#3b6ea5', '#7a4fa3'];

const COST_LABEL = {
  'free': 'free',
  'parking fee (per car)': 'car park',
  'ticket (per person)': 'ticket pp',
};

function costBadge(s) {
  if (!s.cost || s.cost === 'unknown') return '';
  const cls = s.cost === 'free' ? 'free' : s.cost.startsWith('ticket') ? 'ticket' : 'park';
  return `<span class="cost ${cls}" title="${esc(s.tickets || '')}">${COST_LABEL[s.cost]}</span>`;
}

function renderRoute() {
  const all = D.routes.variants;
  const r = all[variant];
  const el = $('#view-route');
  el.innerHTML = `
    <div class="variants">
      ${Object.entries(all).sort((a, b) => a[1].version.localeCompare(b[1].version))
        .map(([k, v]) => `
        <button class="vbtn ${k === variant ? 'is-on' : ''}" data-variant="${esc(k)}">
          <b class="vtag">${esc(v.version)}</b> ${esc(v.label)}
          <small>${v.total_km.toLocaleString()} km · ${v.total_stops} stops ·
            longest day ${v.longest_day_hours} h</small>
        </button>`).join('')}
    </div>
    <p class="count">${r.total_km.toLocaleString()} km · ${r.total_driving_hours} h driving ·
      ${r.total_stops} stops · ${r.paid_parking_stops} paid car parks ·
      ${r.per_person_ticket_stops} per-person ticket${r.per_person_ticket_stops === 1 ? '' : 's'}
      · ${r.nights} nights. Flight home ${esc(r.flight)}.</p>
    <p class="note">${esc(r.note)}</p>

    <p class="note">"Day" adds an estimate of time on the ground to the driving.
      Days start at 07:00. The sun sets about 20:20 on the 12th and 20:00 on the 18th,
      so anything flagged red finishes in the dark — fine on Route 1, less fun on gravel.</p>
    ${r.days.map((d, i) => `
      <details class="day" ${i === 0 ? 'open' : ''}>
        <summary>
          <span class="day-n" style="color:${DAY_COLORS[i % DAY_COLORS.length]}">Day ${d.day}</span>
          <span class="day-date">${esc(d.date_label)}</span>
          <span class="day-t">${esc(d.title)}</span>
          <span class="day-km">${d.km} km · ${d.driving_hours} h drive ·
            <b class="${d.over_daylight ? 'over' : d.long_day ? 'long' : ''}">${
              esc(d.starts)}–${esc(d.finishes)}</b></span>
        </summary>
        <div class="day-body">
          <p>${esc(d.summary)}</p>
          ${d.note ? `<p class="note">${esc(d.note)}</p>` : ''}
          ${d.split ? renderSplit(d.split) : ''}
          <ul class="stops">
            ${d.stops.map((s) => `
              <li><span class="k">${esc(s.kind)}</span>
              <span class="li-name" data-focus="${esc(s.name)}">${esc(s.name)}</span>
              ${costBadge(s)}</li>`).join('')}
          </ul>
          ${d.night_offcard ? `
            <div class="night warn"><strong>Night ${d.day} — off the card:</strong>
              ${esc(d.night_offcard)}</div>` : ''}
          ${d.night ? `
            <div class="night${d.night_open === false ? ' warn' : ''}">
              <strong>Night ${d.day} (${esc(d.date_label)})${
                d.night_open === false ? ' — CLOSED on this date' : ''}:</strong>
              <span class="li-name" data-focus="${esc(d.night.name)}">${esc(d.night.name)}</span>
              — open ${esc(d.night.open || '—')}
              ${d.night.tel ? ` · ${esc(d.night.tel)}` : ''}
              <div class="alts">Nearest alternatives open that night:
                ${d.nearby_campsites.filter((c) => c.name !== d.night.name).slice(0, 3)
                  .map((c) => `${esc(c.name)} (${c.km} km)`).join(' · ')}</div>
            </div>` : `<div class="night"><strong>${
              d.no_drive ? 'Your own beds — no driving today.' : 'Back in Reykjavík.'}</strong></div>`}
        </div>
      </details>`).join('')}`;

  layers.route.clearLayers();
  r.days.forEach((d, i) => {
    const color = DAY_COLORS[i % DAY_COLORS.length];
    if (d.geometry.length) {
      L.polyline(d.geometry, { color, weight: 4, opacity: .85 })
        .bindPopup(`<b>Day ${d.day}</b> — ${esc(d.title)}<br>${d.km} km · ${d.driving_hours} h`)
        .addTo(layers.route);
    }
    d.stops.forEach((s) => {
      const m = L.circleMarker([s.lat, s.lon], dot(color, s.kind === 'optional' ? 4 : 6))
        .bindPopup(`<b>${esc(s.name)}</b><br>Day ${d.day} · ${esc(s.kind)}${
          s.cost && s.cost !== 'unknown' ? `<br>${esc(s.tickets)}` : ''}`);
      m.addTo(layers.route);
      markerIndex.set(s.name, m);
    });
    if (d.night) {
      const m = L.marker([d.night.lat, d.night.lon], { title: d.night.name })
        .bindPopup(`<b>${esc(d.night.name)}</b><br>Night ${d.day}<br>Open: ${esc(d.night.open)}`);
      m.addTo(layers.route);
      markerIndex.set(d.night.name, m);
    }
  });
}

function renderSplit(s) {
  return `<div class="split">
    <h4>Party splits here — ${esc(s.where)}</h4>
    ${s.options.map((o) => `<div class="split-opt"><strong>${esc(o.what)}</strong>
      (${esc(o.duration)}) — ${esc(o.where)}. ${esc(o.book)}</div>`).join('')}
    <div class="alts">${esc(s.note)}</div>
  </div>`;
}

function fillSelect(sel, values) {
  sel.insertAdjacentHTML('beforeend',
    [...new Set(values)].filter(Boolean).sort()
      .map((v) => `<option value="${esc(v)}">${esc(v)}</option>`).join(''));
}

function renderPlaces() {
  const q = $('#q').value.trim().toLowerCase();
  const cat = $('#fCategory').value, reg = $('#fRegion').value, only = $('#fPicked').checked;
  const rows = D.places.filter((p) =>
    (!q || p.name.toLowerCase().includes(q)) &&
    (!cat || p.category === cat) && (!reg || p.region === reg) &&
    (!only || picks.has(p.name)));

  $('#placesCount').textContent = `${rows.length} of ${D.places.length} sights`;
  $('#placesList').innerHTML = rows.map((p) => `
    <li>${starBtn(p.name)}
      <div class="li-main">
        <div class="li-name" data-focus="${esc(p.name)}">${esc(p.name)}
          ${p.confidence === 'curated' ? '<span class="badge curated">curated</span>' : ''}</div>
        <div class="li-meta">${esc(p.category)}${p.region && p.region !== 'Not assessed'
          ? ' · ' + esc(p.region) : ''}${p.locality ? ' · ' + esc(p.locality) : ''}</div>
      </div></li>`).join('') || '<li>No sights match.</li>';

  layers.places.clearLayers();
  rows.forEach((p) => {
    if (!p.lat) return;
    const m = L.circleMarker([p.lat, p.lon], dot(picks.has(p.name) ? '#c9a227' : '#8894a5', 4))
      .bindPopup(`<b>${esc(p.name)}</b><br>${esc(p.category)}<br>
        <a href="${esc(p.maps_url)}" target="_blank" rel="noopener">Open in Maps</a>`);
    m.addTo(layers.places);
    markerIndex.set(p.name, m);
  });
}

function renderSimple(listEl, rows, layer, color, meta, popup) {
  listEl.innerHTML = rows.map((r) => `
    <li>${starBtn(r.name)}
      <div class="li-main">
        <div class="li-name" data-focus="${esc(r.name)}">${esc(r.name)}</div>
        <div class="li-meta">${meta(r)}</div>
      </div></li>`).join('');
  layer.clearLayers();
  rows.forEach((r) => {
    if (!r.lat) return;
    const m = L.circleMarker([+r.lat, +r.lon], dot(color, 5)).bindPopup(popup(r));
    m.addTo(layer);
    markerIndex.set(r.name, m);
  });
}

/* ---------- sortable table ---------- */
const TCOLS = ['name', 'category', 'region', 'tourist_area', 'locality', 'tier', 'accessibility',
  'open_in_september', 'needs_hiking', 'duration', 'tickets', 'popularity',
  'spots_within_25km', 'confidence'];
let sortCol = 'name', sortDir = 1;

function tableRows() {
  const q = $('#tq').value.trim().toLowerCase();
  const conf = $('#tConfidence').value;
  return D.places
    .filter((p) => (!conf || p.confidence === conf) &&
      (!q || TCOLS.some((c) => String(p[c] ?? '').toLowerCase().includes(q))))
    .sort((a, b) => {
      const x = a[sortCol] ?? '', y = b[sortCol] ?? '';
      const nx = parseFloat(x), ny = parseFloat(y);
      if (!isNaN(nx) && !isNaN(ny)) return (nx - ny) * sortDir;
      return String(x).localeCompare(String(y), 'is') * sortDir;
    });
}

function renderTable() {
  const rows = tableRows();
  $('#tableCount').textContent =
    `${rows.length} rows · ${rows.filter((r) => r.confidence === 'curated').length} curated. ` +
    `Click a header to sort, a name to find it on the map.`;
  $('#grid thead').innerHTML = `<tr>${TCOLS.map((c) =>
    `<th data-col="${c}">${c.replace(/_/g, ' ')}${sortCol === c
      ? ` <span class="dir">${sortDir > 0 ? '▲' : '▼'}</span>` : ''}</th>`).join('')}</tr>`;
  $('#grid tbody').innerHTML = rows.map((r) => `<tr>${TCOLS.map((c) => {
    const v = r[c] ?? '';
    const dim = v === 'Not assessed' || v === 'Unranked' || v === '';
    return `<td class="${dim ? 'dim' : ''}"${c === 'name' ? ` data-focus="${esc(r.name)}"` : ''}>${
      esc(v === '' ? '—' : v)}</td>`;
  }).join('')}</tr>`).join('');
}

function downloadCSV() {
  const rows = tableRows();
  const cell = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const csv = [TCOLS.join(','), ...rows.map((r) => TCOLS.map((c) => cell(r[c])).join(','))].join('\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
  a.download = 'iceland_places_filtered.csv';
  a.click();
  URL.revokeObjectURL(a.href);
}

/* ---------- wiring ---------- */
const VIEWS = ['route', 'places', 'table', 'camps', 'fuel'];

function showView(name, push = true) {
  if (!VIEWS.includes(name)) name = 'route';
  if (push && location.hash.slice(1) !== name) location.hash = name;
  document.body.dataset.view = name;
  document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('is-on', t.dataset.view === name));
  document.querySelectorAll('.view').forEach((v) => { v.hidden = v.id !== `view-${name}`; });
  const auto = { places: 'lyPlaces', camps: 'lyCamps', fuel: 'lyFuel', route: 'lyRoute' }[name];
  if (auto && !$(`#${auto}`).checked) { $(`#${auto}`).checked = true; $(`#${auto}`).dispatchEvent(new Event('change')); }
  if (name === 'table') renderTable();
  setTimeout(() => map.invalidateSize(), 50);
}

document.addEventListener('click', (e) => {
  const tab = e.target.closest('.tab');
  if (tab) return showView(tab.dataset.view);
  const star = e.target.closest('[data-pick]');
  if (star) { togglePick(star.dataset.pick); if (!$('#view-places').hidden) renderPlaces(); return; }
  const f = e.target.closest('[data-focus]');
  if (f) return focus(f.dataset.focus);
  const vb = e.target.closest('[data-variant]');
  if (vb) {
    variant = vb.dataset.variant;
    try { localStorage.setItem('iceland.variant', variant); } catch (_) {}
    renderRoute();
    const b = L.latLngBounds(D.routes.variants[variant].days.flatMap((d) => d.geometry));
    if (b.isValid()) map.fitBounds(b, { padding: [24, 24] });
    return;
  }
  const th = e.target.closest('th[data-col]');
  if (th) {
    sortDir = sortCol === th.dataset.col ? -sortDir : 1;
    sortCol = th.dataset.col;
    renderTable();
  }
});

['#q', '#fCategory', '#fRegion', '#fPicked'].forEach((s) =>
  $(s).addEventListener('input', renderPlaces));
['#tq', '#tConfidence'].forEach((s) => $(s).addEventListener('input', renderTable));
$('#tDownload').addEventListener('click', downloadCSV);

[['lyRoute', 'route'], ['lyCamps', 'camps'], ['lyFuel', 'fuel'], ['lyPlaces', 'places']]
  .forEach(([id, key]) => $(`#${id}`).addEventListener('change', (e) => {
    e.target.checked ? layers[key].addTo(map) : map.removeLayer(layers[key]);
  }));

$('#copyPicks').addEventListener('click', async () => {
  if (!picks.size) return alert('Nothing picked yet. Star a few sights first.');
  const byCat = {};
  D.places.filter((p) => picks.has(p.name))
    .forEach((p) => (byCat[p.category] ||= []).push(p.name));
  D.camps.filter((c) => picks.has(c.name)).forEach((c) => (byCat['Campsites'] ||= []).push(c.name));
  const text = Object.entries(byCat)
    .map(([c, n]) => `${c}:\n` + n.map((x) => `  - ${x}`).join('\n')).join('\n\n');
  try {
    await navigator.clipboard.writeText(text);
    $('#copyPicks').textContent = 'Copied';
    setTimeout(() => ($('#copyPicks').textContent = 'Copy picks'), 1500);
  } catch (_) { prompt('Copy your picks:', text); }
});

window.addEventListener('hashchange', () => showView(location.hash.slice(1), false));

$('#clearPicks').addEventListener('click', () => {
  if (!picks.size || !confirm('Clear all your picks?')) return;
  picks.clear(); savePicks(); renderPlaces();
  document.querySelectorAll('.star').forEach((b) => b.classList.remove('on'));
});

/* ---------- boot ---------- */
const j = (p) => fetch(p).then((r) => { if (!r.ok) throw new Error(`${p}: ${r.status}`); return r.json(); });

Promise.all([
  j('data/iceland_places_ranked.json'),
  j('data/iceland_campsites_all.json'),
  j('data/iceland_gas_stations.json'),
  j('data/routes.json'),
]).then(([places, camps, fuel, routes]) => {
  D.places = places; D.camps = camps; D.fuel = fuel; D.routes = routes;
  if (!routes.variants[variant]) variant = routes.default;

  fillSelect($('#fCategory'), places.map((p) => p.category));
  fillSelect($('#fRegion'), places.map((p) => p.region).filter((r) => r && r !== 'Not assessed'));

  renderRoute();
  renderPlaces();
  renderSimple($('#campsList'), camps, layers.camps, '#3f8f4a',
    (c) => `${c.on_card ? 'on the camping card · ' : ''}${
      esc(c.card_open || c.opening_hours || 'season not recorded')}`,
    (c) => `<b>${esc(c.name)}</b>${c.on_card ? ' <i>(camping card)</i>' : ''}<br>
      ${esc(c.card_open || c.opening_hours || 'season not recorded')}<br>
      ${c.phone ? esc(c.phone) + '<br>' : ''}
      <a href="${esc(c.website || c.osm)}" target="_blank" rel="noopener">Details</a>`);
  renderSimple($('#fuelList'), fuel.map((f) => ({ ...f, name: f.brand })), layers.fuel, '#3b6ea5',
    (f) => esc(f.locality || 'rural — no locality in OSM'),
    (f) => `<b>${esc(f.brand)}</b><br>${esc(f.locality || 'rural')}`);

  savePicks();
  showView(location.hash.slice(1) || 'route', false);
  const b = L.latLngBounds(routes.variants[variant].days.flatMap((d) => d.geometry));
  map.fitBounds(b, { padding: [24, 24] });
}).catch((err) => {
  $('#view-route').innerHTML =
    `<p class="note">Couldn't load the trip data (${esc(err.message)}).
     If you're opening this file directly, run a local server instead:
     <code>python3 -m http.server</code></p>`;
});
