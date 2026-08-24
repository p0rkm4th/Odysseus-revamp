/* OSINT workspace: a visible, reviewable projection over the existing
 * public-source research service. Research remains tainted/provenance-bound;
 * this surface does not create a second crawler or bypass its policy gate.
 */
import { openView, close as closeWindow, registerView } from './workspaceWindowManager.js';
import { emptyState, errorState, intakeField, loadingState, moduleHeader, provenanceBadge, statusBadge } from './ui-components.js';

const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const api = async (path, options={}) => { const response = await fetch(path, {credentials:'same-origin', headers: options.body ? {'Content-Type':'application/json'} : undefined, ...options}); const data = await response.json().catch(() => ({})); if (!response.ok) throw Error(data.detail || `Request failed (${response.status})`); return data; };

const TABS = ['Overview','New Investigation','Cases','Targets','Research','Sources','Facts','Inferences','Relationships','Timeline','Evidence','Reports'];
let currentTab = 'Overview';

function tabBar() { return `<nav class="hades-module-tabs" aria-label="OSINT sections">${TABS.map(tab => `<button type="button" class="hades-module-tab${tab === currentTab ? ' active' : ''}" data-osint-tab="${esc(tab)}">${esc(tab)}</button>`).join('')}</nav>`; }
function caseCard(item) {
  const status = item.status || item.state || 'completed';
  const id = item.id || item.session_id;
  return `<button type="button" class="hades-record-card control-entity-card osint-case-card" data-osint-case="${esc(id)}"><div><strong>${esc(item.title || item.query || 'Untitled investigation')}</strong><p>${esc(item.query || item.summary || 'Public-source investigation')}</p></div><div>${statusBadge(status, status === 'completed' ? 'success' : status === 'error' ? 'danger' : 'info')} ${provenanceBadge('IMPORTED')}</div><small>${esc(item.created_at || item.updated_at || item.session_id || '')} · ${esc(item.source_count ?? '—')} source(s)</small></button>`;
}

async function caseDossier(sessionId) {
  const item = await api(`/api/research/detail/${encodeURIComponent(sessionId)}`);
  const result = item.result || {};
  const sources = item.sources || [];
  const findings = item.raw_findings || item.findings || [];
  const claimData = await api(`/api/research/${encodeURIComponent(sessionId)}/claims?include_inactive=true`).catch(() => ({claims:[]}));
  const claims = claimData.claims || [];
  const claimCard = claim => {
    const kind = String(claim.claim_class || 'UNKNOWN').replace(/([a-z])([A-Z])/g, '$1 $2').toUpperCase();
    const state = claim.provenance?.state === 'stale' ? 'STALE' : claim.status === 'superseded' ? 'SUPERSEDED' : claim.status === 'retracted' ? 'RETRACTED' : claim.provenance?.state === 'confirmed' ? 'CONFIRMED' : kind;
    const contradictionCount = (claim.contradicting_references || []).length;
    return `<article class="work-card osint-claim-card"><div class="work-card-heading"><strong>${esc(claim.predicate || 'Claim')}</strong><span>${provenanceBadge(state)}</span></div><p>${esc(typeof claim.value === 'string' ? claim.value : JSON.stringify(claim.value || {}))}</p><small>${esc(kind)} · ${esc(claim.source || 'Unknown source')} · confidence ${esc(claim.confidence ?? '—')}</small><small>Observed ${esc(claim.observed_at || 'unknown')} · valid ${esc(claim.valid_from || 'unknown')} → ${esc(claim.valid_until || claim.expires_at || 'open')} · recorded ${esc(claim.created_at || 'unknown')}</small>${(claim.evidence_references || []).length ? `<div class="hades-provenance-row">${provenanceBadge('EVIDENCE')} ${esc(claim.evidence_references.join(', '))}</div>` : ''}${contradictionCount ? `<small class="muted">${contradictionCount} competing claim(s) recorded; inspect lineage in Evidence Explorer.</small>` : ''}${claim.provenance?.resolution_status ? `<small class="muted">Correction status: ${esc(claim.provenance.resolution_status)}</small>` : ''}<div class="osint-claim-actions"><button type="button" class="hades-btn-secondary" data-osint-review="confirmed" data-claim-id="${esc(claim.id)}">Confirm</button><button type="button" class="hades-btn-secondary" data-osint-review="stale" data-claim-id="${esc(claim.id)}">Mark stale</button><button type="button" class="hades-btn-secondary" data-osint-review="retracted" data-claim-id="${esc(claim.id)}">Retract</button></div></article>`;
  };
  const ledger = claims.length ? claims.map(claimCard).join('') : '<p class="muted">No reviewed canonical claims are attached to this case yet. External report text is not silently promoted.</p>';
  return `<section class="control-inspector osint-dossier" data-osint-session="${esc(sessionId)}"><div class="work-header"><div><h2>OSINT Dossier</h2><p>${esc(item.query || sessionId)}</p></div>${statusBadge(item.status || 'completed', item.status === 'error' ? 'danger' : 'info')}</div><div class="hades-callout"><span>${provenanceBadge('IMPORTED')} External research remains tainted content; this dossier does not grant authority.</span></div><div class="work-grid"><section><h3>Summary / Report</h3><pre>${esc(result.report || result.summary || item.report || 'No report text recorded.')}</pre></section><section><h3>Sources</h3>${sources.map(source => `<article class="work-card"><strong>${esc(source.title || source.name || source.url || 'Source')}</strong><p>${esc(source.url || '')}</p><small>${provenanceBadge('OBSERVED')}</small></article>`).join('') || '<p class="muted">No sources recorded.</p>'}</section><section><h3>Findings / Evidence</h3>${findings.map(finding => `<article class="work-card"><strong>${esc(finding.title || finding.claim || finding.url || 'Finding')}</strong><p>${esc(finding.summary || finding.text || finding.content || '')}</p><small>${provenanceBadge('IMPORTED')} ${esc(finding.url || '')}</small></article>`).join('') || '<p class="muted">No per-source findings recorded.</p>'}</section><section><h3>Facts / Inferences</h3><p class="muted">Canonical, owner-scoped claims are shown below. Report text is not promoted into claims by the UI.</p><div class="osint-claim-ledger">${ledger}</div></section><section><h3>Research metadata</h3><pre>${esc(JSON.stringify({session_id:sessionId, status:item.status, category:item.category, stats:item.stats, started_at:item.started_at, completed_at:item.completed_at, source_count:sources.length, finding_count:findings.length, canonical_claim_count:claims.length},null,2))}</pre></section></div></section>`;
}

async function reviewClaimButton(button, body) {
  const decision = button.dataset.osintReview;
  if (decision === 'retracted' && !window.confirm('Retract this claim from the current projection? Prior evidence will be retained.')) return;
  const dossier = button.closest('[data-osint-session]');
  const sessionId = dossier?.dataset.osintSession;
  if (!sessionId) return;
  button.disabled = true;
  try {
    await api(`/api/research/${encodeURIComponent(sessionId)}/claims/${encodeURIComponent(button.dataset.claimId)}/review`, {method:'PATCH', body:JSON.stringify({decision})});
    body.querySelector('#osint-tab-content').innerHTML = await caseDossier(sessionId);
    body.querySelectorAll('[data-osint-review]').forEach(next => next.addEventListener('click', () => reviewClaimButton(next, body)));
  } catch (error) {
    button.disabled = false;
    button.title = error.message;
  }
}

function renderIntake() {
  return `<section class="hades-intake-panel"><div class="hades-intake-intro"><h3>New Investigation</h3><p>Start with what you know. Hades will prepare a bounded public-source research run; external content remains tainted and results remain evidence-linked.</p></div><form id="osint-investigation-form"><div class="hades-intake-grid">${intakeField('Target type', '<select name="target_type"><option>Person</option><option>Company</option><option>Organization</option><option>Domain</option></select>')}${intakeField('Research depth', '<select name="depth"><option value="quick">Quick</option><option value="standard" selected>Standard</option><option value="deep">Deep Dive</option></select>')}${intakeField('Name', '<input name="name" autocomplete="off" placeholder="Optional">')}${intakeField('Aliases', '<input name="aliases" autocomplete="off" placeholder="Optional">')}${intakeField('Organization / company', '<input name="organization" autocomplete="off">')}${intakeField('Location', '<input name="location" autocomplete="off">')}${intakeField('Domain / website', '<input name="domain" autocomplete="url" placeholder="example.org">')}${intakeField('Public handles', '<input name="handles" autocomplete="off">')}</div>${intakeField('What I know', '<textarea name="known_information" rows="7" required placeholder="Names, context, public clues, questions, and anything else you already know…"></textarea>')}${intakeField('Related entities', '<textarea name="related_entities" rows="3" placeholder="People, organizations, domains, or relationships to examine"></textarea>')}${intakeField('Notes', '<textarea name="notes" rows="3"></textarea>')}<div class="hades-attachment-box"><strong>Attachments and URLs</strong><p>Attach context for review. URLs are included as public-source leads; local files remain staged for the existing document intake path.</p><input type="url" name="source_url" placeholder="https://public-source.example/article"><input type="file" name="attachments" multiple accept="image/*,.pdf,.txt,.md,.doc,.docx"></div><div class="hades-intake-footer"><span>${provenanceBadge('USER PROVIDED')} ${provenanceBadge('MODEL PROPOSED')} requires review before canonical linkage</span><button type="submit" class="hades-btn-primary">Investigate</button></div></form><div id="osint-intake-result" aria-live="polite"></div></section>`;
}

function renderOverview(cases) {
  const sourceCount = cases.reduce((sum, item) => sum + Number(item.source_count || 0), 0);
  return `<section class="hades-overview-grid"><article class="hades-summary-card"><span>Cases</span><strong>${cases.length}</strong><small>durable research records</small></article><article class="hades-summary-card"><span>Sources</span><strong>${sourceCount || '—'}</strong><small>recorded source references</small></article><article class="hades-summary-card"><span>Evidence posture</span><strong>Public only</strong><small>tainted external content</small></article></section><div class="hades-callout"><div><h3>Build a sourced dossier</h3><p>Give Hades a person, company, organization, or domain and choose a bounded research depth.</p></div><button id="osint-start-investigation" type="button" class="hades-btn-primary">New Investigation</button></div>${cases.length ? `<section><h3>Recent cases</h3><div class="hades-record-list">${cases.slice(0,5).map(caseCard).join('')}</div></section>` : emptyState('No investigations yet','Start with a public-source target and a research question.','New Investigation','osint-start-investigation-empty')}`;
}

function renderCases(cases) { return cases.length ? `<div class="hades-list-toolbar"><input id="osint-case-filter" placeholder="Search cases…" aria-label="Search OSINT cases"><span>${cases.length} case(s)</span></div><div class="hades-record-list" id="osint-case-list">${cases.map(caseCard).join('')}</div>` : emptyState('No OSINT cases','Your completed and active public-source investigations will appear here.','New Investigation','osint-start-investigation-empty'); }

function renderTab(cases) {
  if (currentTab === 'New Investigation') return renderIntake();
  if (currentTab === 'Cases' || currentTab === 'Research') return renderCases(cases);
  if (currentTab === 'Overview') return renderOverview(cases);
  return emptyState(`${currentTab} is ready for evidence`, `This section will be populated from canonical OSINT case records, research results, and provenance-linked evidence.`,'New Investigation','osint-start-investigation-empty');
}

async function load(el) {
  const body = el.querySelector('.hades-window-body');
  body.innerHTML = loadingState('Loading OSINT workspace…');
  let cases = [];
  try { const data = await api('/api/research/library?limit=100'); cases = data.research || []; } catch (_) { /* The intake remains usable if the library is unavailable. */ }
  body.innerHTML = `${moduleHeader({icon:'osint', title:'OSINT', description:'Public-source investigations with evidence, provenance, and bounded depth.', primary:'New Investigation', primaryId:'osint-new-header'})}${tabBar()}<div id="osint-tab-content">${renderTab(cases)}</div>`;
  body.querySelectorAll('[data-osint-tab]').forEach(button => button.addEventListener('click', () => { currentTab = button.dataset.osintTab; load(el); }));
  body.querySelector('#osint-new-header')?.addEventListener('click', () => { currentTab='New Investigation'; load(el); });
  body.querySelector('#osint-start-investigation')?.addEventListener('click', () => { currentTab='New Investigation'; load(el); });
  body.querySelector('#osint-start-investigation-empty')?.addEventListener('click', () => { currentTab='New Investigation'; load(el); });
  body.querySelector('#osint-investigation-form')?.addEventListener('submit', event => startInvestigation(event, el));
  body.querySelector('#osint-case-filter')?.addEventListener('input', event => { const q=event.target.value.toLowerCase(); body.querySelectorAll('#osint-case-list .hades-record-card').forEach(card => { card.hidden=!card.textContent.toLowerCase().includes(q); }); });
  body.querySelectorAll('[data-osint-case]').forEach(button => button.addEventListener('click', async () => { const content=body.querySelector('#osint-tab-content'); content.innerHTML=loadingState('Loading OSINT dossier…'); try { content.innerHTML=await caseDossier(button.dataset.osintCase); } catch (error) { content.innerHTML=errorState(error.message); } }));
  body.querySelectorAll('[data-osint-review]').forEach(button => button.addEventListener('click', () => reviewClaimButton(button, body)));
}

async function startInvestigation(event, el) {
  event.preventDefault();
  const form = event.currentTarget; const data = Object.fromEntries(new FormData(form).entries());
  const result = form.parentElement.querySelector('#osint-intake-result');
  result.innerHTML = loadingState('Preparing bounded investigation…');
  const attachmentInput = form.querySelector('input[name="attachments"]');
  let attachmentIds = [];
  try {
    if (attachmentInput?.files?.length) {
      const uploadBody = new FormData();
      [...attachmentInput.files].slice(0, 5).forEach(file => uploadBody.append('files', file, file.name));
      const uploadResponse = await fetch('/api/upload', {method:'POST', credentials:'same-origin', body:uploadBody});
      const uploadResult = await uploadResponse.json().catch(() => ({}));
      if (!uploadResponse.ok) throw Error(uploadResult.detail || 'Attachment upload failed');
      attachmentIds = (uploadResult.files || []).map(file => file.id).filter(Boolean).slice(0, 5);
    }
  } catch (error) {
    result.innerHTML = errorState(error.message);
    return;
  }
  const depth = data.depth || 'standard'; const rounds = depth === 'quick' ? 4 : depth === 'deep' ? 20 : 10;
  const structured = Object.entries(data).filter(([key, value]) => value && !['known_information','depth','source_url','attachments'].includes(key)).map(([key,value]) => `${key}: ${value}`).join('\n');
  const query = [`OSINT target type: ${data.target_type}`, 'Known information:', data.known_information, structured && `Structured details:\n${structured}`, data.source_url && `Public source URL: ${data.source_url}`].filter(Boolean).join('\n\n');
  result.innerHTML = loadingState('Creating bounded investigation…');
  try { const created = await api('/api/research/start', {method:'POST', body:JSON.stringify({query, attachment_ids:attachmentIds, max_rounds:rounds, max_time: depth === 'deep' ? 900 : 300, category:'osint'})}); result.innerHTML = `<div class="hades-success-state"><strong>Investigation started</strong><p>Case ${esc(created.session_id)} is now running. Uploaded files were passed through bounded extraction as untrusted evidence.</p><button type="button" class="hades-btn-secondary" id="osint-open-cases">Open Cases</button></div>`; result.querySelector('#osint-open-cases').onclick=()=>{currentTab='Cases';load(el);}; } catch (error) { result.innerHTML = errorState(error.message); }
}

export function openOsint() { const el=openView('osint', null, 'OSINT', loadingState()); load(el); return el; }
export function closeOsint() { closeWindow('osint:main'); }
registerView('osint', () => openOsint());
export default {openOsint, closeOsint};
