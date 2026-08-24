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
  return `<article class="hades-record-card"><div><strong>${esc(item.title || item.query || 'Untitled investigation')}</strong><p>${esc(item.query || item.summary || 'Public-source investigation')}</p></div><div>${statusBadge(status, status === 'completed' ? 'success' : status === 'error' ? 'danger' : 'info')} ${provenanceBadge('IMPORTED')}</div><small>${esc(item.created_at || item.updated_at || item.session_id || '')}</small></article>`;
}

function renderIntake() {
  return `<section class="hades-intake-panel"><div class="hades-intake-intro"><h3>New Investigation</h3><p>Start with what you know. Hades will prepare a bounded public-source research run; external content remains tainted and results remain evidence-linked.</p></div><form id="osint-investigation-form"><div class="hades-intake-grid">${intakeField('Target type', '<select name="target_type"><option>Person</option><option>Company</option><option>Organization</option><option>Domain</option></select>')}${intakeField('Research depth', '<select name="depth"><option value="quick">Quick</option><option value="standard" selected>Standard</option><option value="deep">Deep Dive</option></select>')}${intakeField('Name', '<input name="name" autocomplete="off" placeholder="Optional">')}${intakeField('Aliases', '<input name="aliases" autocomplete="off" placeholder="Optional">')}${intakeField('Organization / company', '<input name="organization" autocomplete="off">')}${intakeField('Location', '<input name="location" autocomplete="off">')}${intakeField('Domain / website', '<input name="domain" autocomplete="url" placeholder="example.org">')}${intakeField('Public handles', '<input name="handles" autocomplete="off">')}</div>${intakeField('What I know', '<textarea name="known_information" rows="7" required placeholder="Names, context, public clues, questions, and anything else you already know…"></textarea>')}${intakeField('Related entities', '<textarea name="related_entities" rows="3" placeholder="People, organizations, domains, or relationships to examine"></textarea>')}${intakeField('Notes', '<textarea name="notes" rows="3"></textarea>')}<div class="hades-attachment-box"><strong>Attachments and URLs</strong><p>Attach context for review. URLs are included as public-source leads; local files remain staged for the existing document intake path.</p><input type="url" name="source_url" placeholder="https://public-source.example/article"><input type="file" name="attachments" multiple accept="image/*,.pdf,.txt,.md,.doc,.docx"></div><div class="hades-intake-footer"><span>${provenanceBadge('USER PROVIDED')} ${provenanceBadge('MODEL PROPOSED')} requires review before canonical linkage</span><button type="submit" class="hades-btn-primary">Investigate</button></div></form><div id="osint-intake-result" aria-live="polite"></div></section>`;
}

function renderOverview(cases) {
  return `<section class="hades-overview-grid"><article class="hades-summary-card"><span>Cases</span><strong>${cases.length}</strong><small>durable research records</small></article><article class="hades-summary-card"><span>Sources</span><strong>—</strong><small>populated from completed runs</small></article><article class="hades-summary-card"><span>Evidence posture</span><strong>Public only</strong><small>tainted external content</small></article></section><div class="hades-callout"><div><h3>Build a sourced dossier</h3><p>Give Hades a person, company, organization, or domain and choose a bounded research depth.</p></div><button id="osint-start-investigation" type="button" class="hades-btn-primary">New Investigation</button></div>${cases.length ? `<section><h3>Recent cases</h3><div class="hades-record-list">${cases.slice(0,5).map(caseCard).join('')}</div></section>` : emptyState('No investigations yet','Start with a public-source target and a research question.','New Investigation','osint-start-investigation-empty')}`;
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
}

async function startInvestigation(event, el) {
  event.preventDefault();
  const form = event.currentTarget; const data = Object.fromEntries(new FormData(form).entries());
  const depth = data.depth || 'standard'; const rounds = depth === 'quick' ? 4 : depth === 'deep' ? 20 : 10;
  const structured = Object.entries(data).filter(([key, value]) => value && !['known_information','depth','source_url','attachments'].includes(key)).map(([key,value]) => `${key}: ${value}`).join('\n');
  const query = [`OSINT target type: ${data.target_type}`, 'Known information:', data.known_information, structured && `Structured details:\n${structured}`, data.source_url && `Public source URL: ${data.source_url}`].filter(Boolean).join('\n\n');
  const result = form.parentElement.querySelector('#osint-intake-result');
  result.innerHTML = loadingState('Creating bounded investigation…');
  try { const created = await api('/api/research/start', {method:'POST', body:JSON.stringify({query, max_rounds:rounds, max_time: depth === 'deep' ? 900 : 300, category:'osint'})}); result.innerHTML = `<div class="hades-success-state"><strong>Investigation started</strong><p>Case ${esc(created.session_id)} is now running. It will appear in Cases and retain source/result provenance.</p><button type="button" class="hades-btn-secondary" id="osint-open-cases">Open Cases</button></div>`; result.querySelector('#osint-open-cases').onclick=()=>{currentTab='Cases';load(el);}; } catch (error) { result.innerHTML = errorState(error.message); }
}

export function openOsint() { const el=openView('osint', null, 'OSINT', loadingState()); load(el); return el; }
export function closeOsint() { closeWindow('osint:main'); }
registerView('osint', () => openOsint());
export default {openOsint, closeOsint};
