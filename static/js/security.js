// Small authenticated Security workspace for bounded assessment records.

let pane = null;

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

async function api(path, options = {}) {
  const response = await fetch(path, {credentials: 'same-origin', headers: options.body ? {'Content-Type': 'application/json'} : undefined, ...options});
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data;
}

function render(data) {
  const rows = (data.engagements || []).map(item => `
    <article class="security-card" data-id="${esc(item.id)}">
      <div><strong>${esc(item.name)}</strong><span class="security-state">${esc(item.authorization_status)} · ${esc(item.status)}</span></div>
      <small>${esc(item.assessment_type)} · revision ${esc(item.revision)}</small>
      <button class="security-open" data-id="${esc(item.id)}">Open assessment</button>
    </article>`).join('');
  pane.innerHTML = `<div class="security-header"><div><h2>Security Assessments</h2><p>Authorized, bounded assessment records and evidence.</p></div><button id="security-close">Close</button></div>
    <div class="security-actions"><button id="security-new">New engagement</button><button id="security-refresh">Refresh</button></div>
    <div id="security-message" role="status"></div><div class="security-list">${rows || '<p class="muted">No engagements yet.</p>'}</div>`;
  pane.querySelector('#security-close').onclick = () => pane.remove();
  pane.querySelector('#security-refresh').onclick = load;
  pane.querySelector('#security-new').onclick = create;
  pane.querySelectorAll('.security-open').forEach(button => button.onclick = () => openDetail(button.dataset.id));
}

async function load() {
  try { render(await api('/api/security/engagements')); }
  catch (error) { if (pane) pane.innerHTML = `<p class="security-error">${esc(error.message)}</p>`; }
}

async function create() {
  const name = window.prompt('Engagement name');
  if (!name?.trim()) return;
  try { await api('/api/security/engagements', {method: 'POST', body: JSON.stringify({name: name.trim(), assessment_type: 'security_review'})}); await load(); }
  catch (error) { window.alert(error.message); }
}

async function openDetail(id) {
  try {
    const item = await api(`/api/security/engagements/${encodeURIComponent(id)}`);
    pane.innerHTML = `<div class="security-header"><div><h2>${esc(item.name)}</h2><p>${esc(item.authorization_status)} · ${esc(item.status)} · revision ${esc(item.revision)}</p></div><button id="security-back">Back</button></div>
      <div class="security-detail-grid"><section><h3>Authorization</h3><p>${esc(item.authorization_reference || 'Not authorized')}</p><button id="security-authorize">Authorize bounded test</button></section>
      <section><h3>Scope</h3><pre>${esc(JSON.stringify(item.scopes || [], null, 2))}</pre></section><section><h3>Targets</h3><pre>${esc(JSON.stringify(item.targets || [], null, 2))}</pre></section>
      <section><h3>Runs</h3><pre>${esc(JSON.stringify(item.runs || [], null, 2))}</pre></section><section><h3>Findings</h3><pre>${esc(JSON.stringify(item.findings || [], null, 2))}</pre></section></div>`;
    pane.querySelector('#security-back').onclick = load;
    pane.querySelector('#security-authorize').onclick = async () => {
      try { await api(`/api/security/engagements/${encodeURIComponent(id)}/authorize`, {method:'POST', body: JSON.stringify({reference:'operator-confirmed dogfood scope', notes:'Bounded local test only', expires_at: new Date(Date.now()+3600000).toISOString()})}); await openDetail(id); }
      catch (error) { window.alert(error.message); }
    };
  } catch (error) { window.alert(error.message); }
}

export function togglePanel() {
  if (pane) { pane.remove(); pane = null; return; }
  pane = document.createElement('section'); pane.id = 'security-pane'; pane.className = 'security-pane';
  document.body.appendChild(pane); load();
}

export default {togglePanel};
