"""
Generates a self-contained interactive HTML dashboard from the business list.
All user state (status changes, outreach log, notes) is persisted in localStorage.
"""

import json
import os
from datetime import datetime


HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Business Outreach Tracker — {city}, {state}</title>
<style>
  :root{{
    --bg:#0f172a;--surface:#1e293b;--surface2:#273348;--border:#334155;
    --text:#e2e8f0;--muted:#94a3b8;--accent:#38bdf8;--accent2:#0ea5e9;
    --green:#22c55e;--yellow:#f59e0b;--blue:#3b82f6;--red:#ef4444;
    --purple:#a855f7;--orange:#f97316;
  }}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh}}
  a{{color:var(--accent);text-decoration:none}}
  a:hover{{text-decoration:underline}}

  /* ── Layout ── */
  header{{background:var(--surface);border-bottom:1px solid var(--border);padding:16px 24px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}}
  header h1{{font-size:1.25rem;font-weight:700;color:var(--accent)}}
  header .subtitle{{font-size:.8rem;color:var(--muted);margin-top:2px}}
  .header-right{{display:flex;gap:10px;align-items:center;flex-wrap:wrap}}

  .stats-bar{{display:flex;gap:12px;padding:16px 24px;flex-wrap:wrap}}
  .stat-chip{{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:8px 16px;display:flex;flex-direction:column;align-items:center;min-width:110px}}
  .stat-chip .num{{font-size:1.6rem;font-weight:700;line-height:1}}
  .stat-chip .label{{font-size:.72rem;color:var(--muted);margin-top:2px}}

  .tabs{{display:flex;gap:0;padding:0 24px;border-bottom:1px solid var(--border)}}
  .tab{{padding:12px 20px;cursor:pointer;font-size:.85rem;font-weight:600;border-bottom:2px solid transparent;color:var(--muted);transition:all .15s;user-select:none}}
  .tab.active{{color:var(--accent);border-bottom-color:var(--accent)}}
  .tab .badge{{display:inline-block;background:var(--surface2);border-radius:999px;padding:1px 7px;font-size:.72rem;margin-left:6px}}

  .toolbar{{display:flex;gap:10px;padding:16px 24px;align-items:center;flex-wrap:wrap}}
  .toolbar input{{background:var(--surface);border:1px solid var(--border);border-radius:6px;color:var(--text);padding:7px 12px;font-size:.85rem;width:260px;outline:none}}
  .toolbar input:focus{{border-color:var(--accent)}}
  .toolbar select{{background:var(--surface);border:1px solid var(--border);border-radius:6px;color:var(--text);padding:7px 10px;font-size:.85rem;outline:none;cursor:pointer}}

  .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:16px;padding:0 24px 32px}}

  /* ── Cards ── */
  .card{{background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden;display:flex;flex-direction:column;transition:box-shadow .15s}}
  .card:hover{{box-shadow:0 4px 20px rgba(0,0,0,.4)}}
  .card-header{{padding:14px 16px 10px;border-bottom:1px solid var(--border);display:flex;align-items:flex-start;justify-content:space-between;gap:8px}}
  .card-header .name{{font-size:1rem;font-weight:700;line-height:1.3}}
  .card-header .cat{{font-size:.7rem;background:var(--surface2);border:1px solid var(--border);border-radius:4px;padding:2px 7px;color:var(--muted);white-space:nowrap;flex-shrink:0}}
  .card-body{{padding:12px 16px;display:flex;flex-direction:column;gap:8px;flex:1}}
  .info-row{{display:flex;gap:8px;align-items:flex-start;font-size:.82rem}}
  .info-row .icon{{color:var(--muted);flex-shrink:0;margin-top:1px}}
  .info-row .val{{color:var(--text);word-break:break-word}}
  .info-row .val.muted{{color:var(--muted);font-style:italic}}
  .desc{{font-size:.8rem;color:var(--muted);line-height:1.5;border-top:1px solid var(--border);padding-top:8px;margin-top:2px}}

  .card-footer{{padding:10px 16px;border-top:1px solid var(--border);display:flex;flex-direction:column;gap:8px}}

  /* outreach history */
  .outreach-list{{display:flex;flex-direction:column;gap:4px}}
  .outreach-item{{background:var(--surface2);border-radius:6px;padding:6px 10px;font-size:.77rem;display:flex;gap:6px;align-items:flex-start}}
  .outreach-item .otype{{font-weight:700;color:var(--accent);flex-shrink:0}}
  .outreach-item .odate{{color:var(--muted);flex-shrink:0}}
  .outreach-item .onote{{color:var(--text);flex:1;word-break:break-word}}
  .outreach-count{{font-size:.75rem;color:var(--muted)}}

  /* notes textarea */
  .notes-area{{width:100%;background:var(--surface2);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:.8rem;padding:8px;resize:vertical;min-height:60px;font-family:inherit;outline:none}}
  .notes-area:focus{{border-color:var(--accent)}}

  /* action buttons */
  .btn-row{{display:flex;gap:6px;flex-wrap:wrap}}
  .btn{{border:none;border-radius:6px;padding:5px 11px;font-size:.75rem;font-weight:600;cursor:pointer;transition:opacity .1s}}
  .btn:hover{{opacity:.85}}
  .btn-primary{{background:var(--accent2);color:#fff}}
  .btn-ghost{{background:var(--surface2);color:var(--text);border:1px solid var(--border)}}
  .btn-green{{background:#15803d;color:#fff}}
  .btn-yellow{{background:#b45309;color:#fff}}
  .btn-red{{background:#b91c1c;color:#fff}}
  .btn-sm{{padding:3px 8px;font-size:.72rem}}

  /* status badges */
  .status-badge{{display:inline-flex;align-items:center;gap:4px;font-size:.72rem;font-weight:600;padding:2px 8px;border-radius:999px}}
  .status-not_contacted{{background:#1e3a5f;color:#7dd3fc}}
  .status-contacted{{background:#3b2a0c;color:#fbbf24}}
  .status-working{{background:#14532d;color:#86efac}}

  /* modal */
  .modal-backdrop{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:100;align-items:center;justify-content:center}}
  .modal-backdrop.open{{display:flex}}
  .modal{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:24px;width:min(480px,92vw);display:flex;flex-direction:column;gap:14px}}
  .modal h2{{font-size:1rem;font-weight:700}}
  .modal label{{font-size:.82rem;color:var(--muted);display:flex;flex-direction:column;gap:4px}}
  .modal input,.modal select,.modal textarea{{background:var(--surface2);border:1px solid var(--border);border-radius:6px;color:var(--text);padding:8px 10px;font-size:.85rem;font-family:inherit;outline:none;width:100%}}
  .modal input:focus,.modal select:focus,.modal textarea:focus{{border-color:var(--accent)}}
  .modal textarea{{resize:vertical;min-height:80px}}
  .modal-footer{{display:flex;gap:8px;justify-content:flex-end}}

  /* import modal */
  .import-area{{width:100%;background:var(--surface2);border:2px dashed var(--border);border-radius:8px;padding:16px;text-align:center;cursor:pointer;transition:border-color .15s;font-size:.85rem;color:var(--muted)}}
  .import-area:hover{{border-color:var(--accent)}}

  .empty-state{{text-align:center;color:var(--muted);padding:48px 24px;font-size:.9rem}}

  footer{{text-align:center;padding:20px;font-size:.75rem;color:var(--border)}}
</style>
</head>
<body>

<header>
  <div>
    <h1>Business Outreach Tracker</h1>
    <div class="subtitle">{city}, {state} &mdash; Generated {date}</div>
  </div>
  <div class="header-right">
    <button class="btn btn-ghost" onclick="exportData()">Export JSON</button>
    <button class="btn btn-ghost" onclick="openImport()">Import JSON</button>
    <button class="btn btn-primary" onclick="loadFreshData()">Reload Agent Data</button>
  </div>
</header>

<div class="stats-bar" id="statsBar"></div>

<div class="tabs" id="tabBar">
  <div class="tab active" data-tab="not_contacted" onclick="switchTab(this)">Not Contacted <span class="badge" id="badge-not_contacted">0</span></div>
  <div class="tab" data-tab="contacted" onclick="switchTab(this)">Contacted — No Response <span class="badge" id="badge-contacted">0</span></div>
  <div class="tab" data-tab="working" onclick="switchTab(this)">Working With <span class="badge" id="badge-working">0</span></div>
  <div class="tab" data-tab="all" onclick="switchTab(this)">All Businesses</div>
</div>

<div class="toolbar">
  <input type="text" id="searchInput" placeholder="Search by name, category, phone…" oninput="renderGrid()"/>
  <select id="sortSelect" onchange="renderGrid()">
    <option value="name">Sort: Name A–Z</option>
    <option value="outreach_desc">Sort: Most Outreach</option>
    <option value="outreach_asc">Sort: Least Outreach</option>
    <option value="category">Sort: Category</option>
  </select>
</div>

<div class="grid" id="bizGrid"></div>

<!-- Add Outreach Modal -->
<div class="modal-backdrop" id="outreachModal">
  <div class="modal">
    <h2>Log Outreach</h2>
    <label>Type
      <select id="mo-type">
        <option value="Call">Phone Call</option>
        <option value="Email">Email</option>
        <option value="Text">Text / SMS</option>
        <option value="Visit">In-Person Visit</option>
        <option value="Social DM">Social Media DM</option>
        <option value="Other">Other</option>
      </select>
    </label>
    <label>Date
      <input type="date" id="mo-date"/>
    </label>
    <label>Notes (optional)
      <textarea id="mo-notes" placeholder="What happened? Any follow-up needed?"></textarea>
    </label>
    <div class="modal-footer">
      <button class="btn btn-ghost" onclick="closeModal('outreachModal')">Cancel</button>
      <button class="btn btn-primary" onclick="saveOutreach()">Save</button>
    </div>
  </div>
</div>

<!-- Import Modal -->
<div class="modal-backdrop" id="importModal">
  <div class="modal">
    <h2>Import businesses.json</h2>
    <p style="font-size:.82rem;color:var(--muted)">Paste the contents of <code>businesses.json</code> below, or drop the file.</p>
    <textarea id="importText" style="min-height:160px;font-family:monospace;font-size:.75rem;background:var(--surface2);border:1px solid var(--border);border-radius:6px;color:var(--text);padding:10px;width:100%;resize:vertical" placeholder='[{{"id":"...","name":"...",...}}]'></textarea>
    <div class="modal-footer">
      <button class="btn btn-ghost" onclick="closeModal('importModal')">Cancel</button>
      <button class="btn btn-primary" onclick="doImport()">Import</button>
    </div>
  </div>
</div>

<footer>Local Business Discovery Agent &mdash; data saved in browser localStorage</footer>

<script>
// ── Seed data from agent ─────────────────────────────────────────────────────
const SEED_DATA = {seed_json};

// ── State ────────────────────────────────────────────────────────────────────
const LS_KEY = 'biz_tracker_v1';
let state = {{}};          // keyed by business id
let currentTab = 'not_contacted';
let pendingBizId = null;   // for outreach modal

function loadState() {{
  try {{
    const raw = localStorage.getItem(LS_KEY);
    if (raw) state = JSON.parse(raw);
  }} catch(e) {{ state = {{}}; }}
  mergeSeed(SEED_DATA);
}}

function mergeSeed(list) {{
  for (const biz of list) {{
    if (!state[biz.id]) {{
      state[biz.id] = biz;
    }} else {{
      // back-fill any new fields from seed without overwriting user data
      const s = state[biz.id];
      for (const f of ['email','description','phone','address','hours','category','lat','lon']) {{
        if (!s[f] && biz[f]) s[f] = biz[f];
      }}
    }}
  }}
  persist();
}}

function persist() {{
  localStorage.setItem(LS_KEY, JSON.stringify(state));
}}

// ── Helpers ──────────────────────────────────────────────────────────────────
function allBiz() {{ return Object.values(state); }}

function statusLabel(s) {{
  return {{not_contacted:'Not Contacted',contacted:'Contacted — No Response',working:'Working With'}}[s] || s;
}}

function outreachTypeColor(t) {{
  const map = {{Call:'var(--green)',Email:'var(--accent)',Text:'var(--purple)',Visit:'var(--orange)','Social DM':'var(--yellow)',Other:'var(--muted)'}};
  return map[t] || 'var(--muted)';
}}

function esc(s) {{
  return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}

// ── Stats & badges ───────────────────────────────────────────────────────────
function updateStats() {{
  const all = allBiz();
  const nc  = all.filter(b=>b.status==='not_contacted').length;
  const ct  = all.filter(b=>b.status==='contacted').length;
  const wk  = all.filter(b=>b.status==='working').length;
  const withEmail = all.filter(b=>b.email).length;
  const withPhone = all.filter(b=>b.phone).length;

  document.getElementById('statsBar').innerHTML = `
    <div class="stat-chip"><div class="num">${{all.length}}</div><div class="label">Total Found</div></div>
    <div class="stat-chip"><div class="num" style="color:var(--accent)">${{nc}}</div><div class="label">Not Contacted</div></div>
    <div class="stat-chip"><div class="num" style="color:var(--yellow)">${{ct}}</div><div class="label">No Response</div></div>
    <div class="stat-chip"><div class="num" style="color:var(--green)">${{wk}}</div><div class="label">Working With</div></div>
    <div class="stat-chip"><div class="num" style="color:var(--purple)">${{withPhone}}</div><div class="label">Have Phone</div></div>
    <div class="stat-chip"><div class="num" style="color:var(--orange)">${{withEmail}}</div><div class="label">Have Email</div></div>
  `;

  document.getElementById('badge-not_contacted').textContent = nc;
  document.getElementById('badge-contacted').textContent = ct;
  document.getElementById('badge-working').textContent = wk;
}}

// ── Tabs ─────────────────────────────────────────────────────────────────────
function switchTab(el) {{
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  currentTab = el.dataset.tab;
  renderGrid();
}}

// ── Grid rendering ───────────────────────────────────────────────────────────
function filteredBiz() {{
  let list = allBiz();
  if (currentTab !== 'all') list = list.filter(b=>b.status===currentTab);

  const q = document.getElementById('searchInput').value.toLowerCase();
  if (q) {{
    list = list.filter(b =>
      (b.name||'').toLowerCase().includes(q) ||
      (b.category||'').toLowerCase().includes(q) ||
      (b.phone||'').includes(q) ||
      (b.address||'').toLowerCase().includes(q)
    );
  }}

  const sort = document.getElementById('sortSelect').value;
  if (sort==='name')          list.sort((a,b)=>a.name.localeCompare(b.name));
  if (sort==='category')      list.sort((a,b)=>(a.category||'').localeCompare(b.category||''));
  if (sort==='outreach_desc') list.sort((a,b)=>(b.outreach||[]).length-(a.outreach||[]).length);
  if (sort==='outreach_asc')  list.sort((a,b)=>(a.outreach||[]).length-(b.outreach||[]).length);

  return list;
}}

function renderGrid() {{
  updateStats();
  const list = filteredBiz();
  const grid = document.getElementById('bizGrid');

  if (list.length===0) {{
    grid.innerHTML = '<div class="empty-state">No businesses match the current filter.</div>';
    return;
  }}

  grid.innerHTML = list.map(b => cardHTML(b)).join('');
}}

function cardHTML(b) {{
  const statusClass = b.status==='not_contacted'?'status-not_contacted':b.status==='contacted'?'status-contacted':'status-working';

  const phoneRow = b.phone
    ? `<div class="info-row"><span class="icon">📞</span><span class="val"><a href="tel:${{esc(b.phone)}}">${{esc(b.phone)}}</a></span></div>`
    : `<div class="info-row"><span class="icon">📞</span><span class="val muted">No phone found</span></div>`;

  const emailRow = b.email
    ? `<div class="info-row"><span class="icon">✉️</span><span class="val"><a href="mailto:${{esc(b.email)}}">${{esc(b.email)}}</a></span></div>`
    : `<div class="info-row"><span class="icon">✉️</span><span class="val muted">No email found</span></div>`;

  const addrRow = b.address
    ? `<div class="info-row"><span class="icon">📍</span><span class="val">${{esc(b.address)}}</span></div>`
    : '';

  const hoursRow = b.hours
    ? `<div class="info-row"><span class="icon">🕐</span><span class="val">${{esc(b.hours)}}</span></div>`
    : '';

  const desc = b.description
    ? `<div class="desc">${{esc(b.description)}}</div>`
    : '';

  const outreachItems = (b.outreach||[]).map(o => `
    <div class="outreach-item">
      <span class="otype" style="color:${{outreachTypeColor(o.type)}}">${{esc(o.type)}}</span>
      <span class="odate">${{esc(o.date)}}</span>
      <span class="onote">${{esc(o.notes||'')}}</span>
    </div>`).join('');

  const outreachSection = (b.outreach||[]).length > 0
    ? `<div class="outreach-list">${{outreachItems}}</div>`
    : '';

  const outreachCount = (b.outreach||[]).length;
  const countLabel = outreachCount===0 ? 'No outreach yet' : `${{outreachCount}} outreach contact${{outreachCount>1?'s':''}}`;

  const statusOptions = ['not_contacted','contacted','working']
    .map(s=>`<option value="${{s}}" ${{b.status===s?'selected':''}}>${{statusLabel(s)}}</option>`)
    .join('');

  return `
<div class="card" id="card-${{b.id}}">
  <div class="card-header">
    <div class="name">${{esc(b.name)}}</div>
    <div class="cat">${{esc(b.category||'business')}}</div>
  </div>
  <div class="card-body">
    ${{phoneRow}}${{emailRow}}${{addrRow}}${{hoursRow}}${{desc}}
  </div>
  <div class="card-footer">
    ${{outreachSection}}
    <div class="btn-row" style="align-items:center">
      <span class="outreach-count">${{countLabel}}</span>
      <button class="btn btn-primary btn-sm" onclick="openOutreach('${{b.id}}')">+ Log Outreach</button>
    </div>
    <textarea class="notes-area" placeholder="Notes…" oninput="saveNote('${{b.id}}',this.value)">${{esc(b.notes||'')}}</textarea>
    <div class="btn-row" style="align-items:center;gap:8px">
      <span style="font-size:.75rem;color:var(--muted)">Move to:</span>
      <select class="btn btn-ghost btn-sm" style="cursor:pointer" onchange="moveStatus('${{b.id}}',this.value)">
        ${{statusOptions}}
      </select>
    </div>
  </div>
</div>`;
}}

// ── Actions ──────────────────────────────────────────────────────────────────
function saveNote(id, val) {{
  if (!state[id]) return;
  state[id].notes = val;
  persist();
  updateStats();
}}

function moveStatus(id, newStatus) {{
  if (!state[id]) return;
  state[id].status = newStatus;
  persist();
  renderGrid();
}}

function openOutreach(id) {{
  pendingBizId = id;
  const today = new Date().toISOString().slice(0,10);
  document.getElementById('mo-date').value = today;
  document.getElementById('mo-notes').value = '';
  document.getElementById('mo-type').value = 'Call';
  document.getElementById('outreachModal').classList.add('open');
}}

function saveOutreach() {{
  const id = pendingBizId;
  if (!state[id]) return;
  const entry = {{
    type: document.getElementById('mo-type').value,
    date: document.getElementById('mo-date').value,
    notes: document.getElementById('mo-notes').value.trim(),
  }};
  if (!state[id].outreach) state[id].outreach = [];
  state[id].outreach.push(entry);
  // Auto-advance status: if still "not_contacted" → "contacted"
  if (state[id].status === 'not_contacted') state[id].status = 'contacted';
  persist();
  closeModal('outreachModal');
  renderGrid();
}}

function closeModal(id) {{ document.getElementById(id).classList.remove('open'); }}

function openImport() {{ document.getElementById('importModal').classList.add('open'); }}

function doImport() {{
  try {{
    const raw = document.getElementById('importText').value.trim();
    const list = JSON.parse(raw);
    if (!Array.isArray(list)) throw new Error('Expected a JSON array');
    mergeSeed(list);
    closeModal('importModal');
    renderGrid();
    alert(`Imported ${{list.length}} businesses.`);
  }} catch(e) {{ alert('Import failed: ' + e.message); }}
}}

function exportData() {{
  const data = JSON.stringify(Object.values(state), null, 2);
  const blob = new Blob([data], {{type:'application/json'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'businesses_export.json';
  a.click();
}}

function loadFreshData() {{
  if (!confirm('This will merge the latest agent data into your tracker. Your notes and outreach history will be preserved. Continue?')) return;
  mergeSeed(SEED_DATA);
  renderGrid();
  alert('Reloaded agent data.');
}}

// Close modals on backdrop click
document.querySelectorAll('.modal-backdrop').forEach(el => {{
  el.addEventListener('click', e => {{ if (e.target===el) el.classList.remove('open'); }});
}});

// ── Boot ─────────────────────────────────────────────────────────────────────
loadState();
renderGrid();
</script>
</body>
</html>
"""


def generate_dashboard(
    businesses: list[dict],
    output_path: str,
    city: str,
    state: str,
) -> None:
    """Render the HTML dashboard with the given businesses embedded as seed data."""
    seed_json = json.dumps(businesses, ensure_ascii=False)
    date_str = datetime.now().strftime("%B %d, %Y %I:%M %p")

    html = HTML_TEMPLATE.format(
        city=city,
        state=state,
        date=date_str,
        seed_json=seed_json,
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = os.path.getsize(output_path) / 1024
    print(f"[dashboard] Generated {output_path} ({len(businesses)} businesses, {size_kb:.1f} KB)")
