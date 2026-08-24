/* World Model workspace: an inspectable projection over CMDB/domain references. */
import { openView, registerView } from './workspaceWindowManager.js';
import { errorState, emptyState, loadingState, moduleHeader, provenanceBadge, statusBadge } from './ui-components.js';

const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const api = async (path, options={}) => { const r=await fetch(path,{credentials:'same-origin',headers:options.body?{'Content-Type':'application/json'}:undefined,...options}); const d=await r.json().catch(()=>({})); if(!r.ok) throw Error(d.detail||`Request failed (${r.status})`); return d; };

function edgeCard(edge) {
  const kind = edge.observation_kind === 'inferred' || edge.status === 'proposed' ? 'MODEL PROPOSED' : edge.observation_kind === 'observed' ? 'OBSERVED' : 'CONFIRMED';
  const validity = `${edge.valid_from || 'open'} → ${edge.valid_until || 'open'}`;
  const activity = edge.activity_state || (['stale','superseded','contradicted'].includes(edge.status) ? 'historical' : 'active');
  return `<article class="hades-record-card"><div><strong>${esc(edge.source_ref)}</strong><span class="world-edge-arrow"> ${esc(edge.relation)} → </span><strong>${esc(edge.target_ref)}</strong><p>${esc(edge.source || 'No provenance')} · confidence ${esc(edge.confidence_class || 'unknown')} · ${esc(edge.observation_kind || 'unknown')}</p><small>Activity: ${esc(activity)} · validity: ${esc(validity)} · recorded ${esc(edge.recorded_at || 'unknown')} · evidence ${(edge.evidence_references || []).length}</small></div><div>${statusBadge(edge.status, edge.status === 'user_confirmed' ? 'success' : edge.status === 'contradicted' ? 'danger' : edge.status === 'stale' ? 'warning' : 'info')} ${provenanceBadge(kind)}</div></article>`;
}

function impactList(items, empty) {
  return items?.length ? `<ul>${items.map(item => `<li><strong>${esc(item.entity || 'Unknown')}</strong> · ${esc(item.relation || 'dependency')} · confidence ${esc(item.confidence || 'unknown')} · ${esc(item.source || 'no provenance')}</li>`).join('')}</ul>` : `<p class="muted">${esc(empty)}</p>`;
}

async function load(el, focus='', filters={}) {
  const body=el.querySelector('.hades-window-body'); body.innerHTML=loadingState('Loading World Model…');
  try {
    const params = new URLSearchParams();
    if (focus) params.set('entity_ref', focus);
    if (filters.relation) params.set('relation', filters.relation);
    if (filters.status) params.set('status', filters.status);
    const query = params.toString() ? `?${params.toString()}` : '';
    const [relationships, radius, neighbors] = await Promise.all([api(`/api/work/world/relationships${query}`), focus ? api(`/api/work/world/entities/${encodeURIComponent(focus)}/blast-radius`) : Promise.resolve(null), focus ? api(`/api/work/world/entities/${encodeURIComponent(focus)}/neighbors?depth=2`) : Promise.resolve(null)]);
    const edges=relationships.relationships||[];
    const relationOptions=['','RUNS_ON','DEPENDS_ON','USES','POINTS_TO','CONNECTED_TO','BACKED_UP_BY','OWNS','CONTAINS'].map(value=>`<option value="${value}" ${filters.relation===value?'selected':''}>${value || 'All relations'}</option>`).join('');
    const statusOptions=['','observed','user_confirmed','proposed','contradicted','stale','superseded'].map(value=>`<option value="${value}" ${filters.status===value?'selected':''}>${value || 'All statuses'}</option>`).join('');
    body.innerHTML=`${moduleHeader({icon:'network',title:'World Model',description:'Evidence-backed relationships across assets, services, and work.',primary:'Refresh',primaryId:'world-refresh'})}<form class="hades-list-toolbar" id="world-focus-form"><input name="focus" value="${esc(focus)}" placeholder="Focus entity, e.g. host:cerberus" aria-label="World Model focus"><select name="relation" aria-label="Relationship type">${relationOptions}</select><select name="status" aria-label="Relationship status">${statusOptions}</select><button class="hades-btn-primary" type="submit">Focus</button></form><div class="hades-overview-grid"><article class="hades-summary-card"><span>Relationships</span><strong>${edges.length}</strong><small>owner-scoped projection</small></article><article class="hades-summary-card"><span>Epistemic posture</span><strong>Evidence-linked</strong><small>inferences remain labeled</small></article><article class="hades-summary-card"><span>Focus</span><strong>${esc(focus || 'All')}</strong><small>bounded traversal only</small></article></div>${focus && radius ? `<section class="hades-callout"><div><h3>Blast radius</h3><p>Confirmed impact is separated from likely or unknown dependency impact; unknown gaps are not inferred.</p><h4>Confirmed impact</h4>${impactList(radius.confirmed, 'None evidenced.')}<h4>Likely / inferred impact</h4>${impactList(radius.likely, 'None evidenced.')}<h4>Unknown dependency gaps</h4>${impactList(radius.unknown, 'None reported.')}</div></section><section><h3>Bounded neighbors</h3><p class="muted">${esc((neighbors?.entities || []).length)} entities within two hops; inactive or contradicted edges are excluded.</p>${(neighbors?.relationships || []).length ? `<div class="hades-record-list">${neighbors.relationships.map(edgeCard).join('')}</div>` : '<p class="muted">No neighbor evidence.</p>'}</section>`:''}<section><h3>Relationships</h3>${edges.length ? `<div class="hades-record-list">${edges.map(edgeCard).join('')}</div>` : emptyState('No relationship evidence','Add an observed or reviewable relationship through the canonical Work projection.')}</section>`;
    const syncButton=document.createElement('button'); syncButton.type='button'; syncButton.className='hades-btn-secondary'; syncButton.id='world-sync-cmdb'; syncButton.textContent='Sync CMDB'; body.querySelector('#world-focus-form')?.append(syncButton);
    syncButton.onclick=async()=>{syncButton.disabled=true;syncButton.textContent='Syncing…';try{await api('/api/work/world/relationships/sync-cmdb',{method:'POST',body:'{}'});await load(el,focus,filters);}catch(error){syncButton.disabled=false;syncButton.textContent='Sync CMDB';window.alert(error.message);}};
    body.querySelector('#world-refresh').onclick=()=>load(el,focus,filters);
    body.querySelector('#world-focus-form').onsubmit=e=>{e.preventDefault();const form=new FormData(e.currentTarget);load(el,form.get('focus')||'',{relation:form.get('relation')||'',status:form.get('status')||''});};
  } catch (error) { body.innerHTML=errorState(error.message,'world-retry'); body.querySelector('#world-retry')?.addEventListener('click',()=>load(el,focus)); }
}

export function openWorldModel(){const el=openView('world-model',null,'World Model',loadingState());load(el);return el;}
registerView('world-model', () => openWorldModel());
export default {openWorldModel};
