/* World Model workspace: an inspectable projection over CMDB/domain references. */
import { openView, registerView } from './workspaceWindowManager.js';
import { errorState, emptyState, loadingState, moduleHeader, provenanceBadge, statusBadge } from './ui-components.js';

const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const api = async (path, options={}) => { const r=await fetch(path,{credentials:'same-origin',headers:options.body?{'Content-Type':'application/json'}:undefined,...options}); const d=await r.json().catch(()=>({})); if(!r.ok) throw Error(d.detail||`Request failed (${r.status})`); return d; };

function edgeCard(edge) {
  const kind = edge.observation_kind === 'inferred' || edge.status === 'proposed' ? 'MODEL PROPOSED' : edge.observation_kind === 'observed' ? 'OBSERVED' : 'CONFIRMED';
  return `<article class="hades-record-card"><div><strong>${esc(edge.source_ref)}</strong><span class="world-edge-arrow"> ${esc(edge.relation)} → </span><strong>${esc(edge.target_ref)}</strong><p>${esc(edge.source || 'No provenance')} · ${esc(edge.confidence_class || 'unknown')}</p></div><div>${statusBadge(edge.status, edge.status === 'user_confirmed' ? 'success' : edge.status === 'contradicted' ? 'danger' : 'info')} ${provenanceBadge(kind)}</div></article>`;
}

async function load(el, focus='') {
  const body=el.querySelector('.hades-window-body'); body.innerHTML=loadingState('Loading World Model…');
  try {
    const [relationships, radius] = await Promise.all([api(`/api/work/world/relationships${focus ? `?entity_ref=${encodeURIComponent(focus)}` : ''}`), focus ? api(`/api/work/world/entities/${encodeURIComponent(focus)}/blast-radius`) : Promise.resolve(null)]);
    const edges=relationships.relationships||[];
    body.innerHTML=`${moduleHeader({icon:'network',title:'World Model',description:'Evidence-backed relationships across assets, services, and work.',primary:'Refresh',primaryId:'world-refresh'})}<form class="hades-list-toolbar" id="world-focus-form"><input name="focus" value="${esc(focus)}" placeholder="Focus entity, e.g. host:cerberus" aria-label="World Model focus"><button class="hades-btn-primary" type="submit">Focus</button></form><div class="hades-overview-grid"><article class="hades-summary-card"><span>Relationships</span><strong>${edges.length}</strong><small>owner-scoped active edges</small></article><article class="hades-summary-card"><span>Epistemic posture</span><strong>Evidence-linked</strong><small>inferences remain labeled</small></article><article class="hades-summary-card"><span>Focus</span><strong>${esc(focus || 'All')}</strong><small>bounded traversal only</small></article></div>${focus && radius ? `<section class="hades-callout"><div><h3>Blast radius</h3><p>Confirmed impact is separated from likely or unknown dependency impact.</p><p><strong>Confirmed:</strong> ${esc((radius.confirmed||[]).map(x=>x.entity).join(', ')||'None')}<br><strong>Likely:</strong> ${esc((radius.likely||[]).map(x=>x.entity).join(', ')||'None')}<br><strong>Unknown:</strong> ${esc((radius.unknown||[]).map(x=>x.entity).join(', ')||'None')}</p></div></section>`:''}<section><h3>Relationships</h3>${edges.length ? `<div class="hades-record-list">${edges.map(edgeCard).join('')}</div>` : emptyState('No relationship evidence','Add an observed or reviewable relationship through the canonical Work projection.')}</section>`;
    body.querySelector('#world-refresh').onclick=()=>load(el,focus);
    body.querySelector('#world-focus-form').onsubmit=e=>{e.preventDefault();load(el,new FormData(e.currentTarget).get('focus')||'');};
  } catch (error) { body.innerHTML=errorState(error.message,'world-retry'); body.querySelector('#world-retry')?.addEventListener('click',()=>load(el,focus)); }
}

export function openWorldModel(){const el=openView('world-model',null,'World Model',loadingState());load(el);return el;}
registerView('world-model', () => openWorldModel());
export default {openWorldModel};
