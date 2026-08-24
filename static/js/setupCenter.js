import { openView, registerView } from './workspaceWindowManager.js';
import { errorState, loadingState, moduleHeader, statusBadge } from './ui-components.js';

const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const api = async (path, options={}) => { const response=await fetch(path,{credentials:'same-origin',headers:options.body?{'Content-Type':'application/json'}:undefined,...options}); const data=await response.json().catch(()=>({})); if(!response.ok) throw Error(data.detail||`Request failed (${response.status})`); return data; };

async function load(el) {
  const body=el.querySelector('.hades-window-body'); body.innerHTML=loadingState('Loading Setup Center…');
  try {
    const [projection, integrations]=await Promise.all([api('/api/setup-center/state'),api('/api/setup-center/integrations')]);
    const categories=Object.entries(projection.categories||{}).map(([category,modules])=>`<section class="setup-center-category"><h3>${esc(category)}</h3><div class="hades-record-list">${modules.map(module=>`<article class="hades-record-card setup-center-module"><div><strong>${esc(module.title)}</strong><p>${esc(module.description)}</p><small>${esc(module.status_reason)} · dependencies: ${esc((module.dependencies||[]).join(', ')||'none')}</small></div><div>${statusBadge(module.status,module.status==='CONFIGURED'?'success':module.status==='NEEDS_ATTENTION'||module.status==='DEGRADED'?'warning':'info')}${['communications.telegram','communications.email','communications.calendar','communications.contacts','home.smart-home'].includes(module.id)?`<button type="button" class="setup-health-button" data-health-id="${esc(module.id)}">Validate</button>`:''}<button type="button" class="setup-skip-button" data-setup-id="${esc(module.id)}" data-setup-status="${module.status==='SKIPPED'?'NOT_CONFIGURED':'SKIPPED'}">${module.status==='SKIPPED'?'Resume':'Skip'}</button></div></article>`).join('')}</div></section>`).join('');
    const integrationCards=(integrations.integrations||[]).map(item=>`<article class="hades-record-card"><div><strong>${esc(item.title)}</strong><p>${esc(item.capabilities.join(', ')||'No capabilities recorded')}</p></div><div>${statusBadge(item.connection,item.connection==='CONNECTED'?'success':item.connection==='DEGRADED'?'warning':'info')}</div></article>`).join('');
    body.innerHTML=`${moduleHeader({icon:'settings',title:'Setup Center',description:'Resumable module setup, dependency visibility, and safe health state. Setup never grants authority.',primary:'Refresh',primaryId:'setup-center-refresh'})}<p class="muted">${projection.secrets_exposed?'Secret exposure detected — contact an administrator.':'Secret values are never displayed here.'}</p><section class="setup-center-category"><h3>Integration readiness</h3><div class="hades-record-list">${integrationCards}</div></section>${categories}`;
    body.querySelector('#setup-center-refresh').onclick=()=>load(el);
    body.querySelectorAll('.setup-skip-button').forEach(button=>button.onclick=async()=>{button.disabled=true;try{await api(`/api/setup-center/modules/${encodeURIComponent(button.dataset.setupId)}`,{method:'PATCH',body:JSON.stringify({status:button.dataset.setupStatus})});await load(el);}catch(error){button.disabled=false;body.insertAdjacentHTML('afterbegin',errorState(error.message));}});
    body.querySelectorAll('.setup-health-button').forEach(button=>button.onclick=async()=>{button.disabled=true;button.textContent='Checking…';try{const result=await api(`/api/setup-center/modules/${encodeURIComponent(button.dataset.healthId)}/health`,{method:'POST'});button.insertAdjacentHTML('afterend',`<small>${esc(result.detail)}</small>`);}catch(error){button.insertAdjacentHTML('afterend',`<small class="security-error">${esc(error.message)}</small>`);}finally{button.disabled=false;button.textContent='Validate';}});
  } catch(error) { body.innerHTML=errorState(error.message,'setup-center-retry'); body.querySelector('#setup-center-retry')?.addEventListener('click',()=>load(el)); }
}

export function openSetupCenter(){const el=openView('setup-center',null,'Setup Center',loadingState());load(el);return el;}
registerView('setup-center',()=>openSetupCenter());
export default {openSetupCenter};
