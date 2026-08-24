/* Reusable Hades desktop windows.
 * Domain modules supply canonical content; this layer owns only chrome,
 * geometry, focus, snapping, minimization, and owner-scoped layout state.
 */
const windows = new Map();
const restorers = new Map();
let topZ = 5000;
let owner = 'local';
let ownerReady = false;
let dock;
const mobile = () => window.matchMedia('(max-width: 768px)').matches;
const key = () => `hades-workspace-layout:${owner}`;
const clamp = (v, min, max) => Math.max(min, Math.min(max, v));
function ensureDock() {
  if (dock) return dock;
  dock = document.createElement('div'); dock.id='hades-window-dock'; dock.setAttribute('aria-label','Minimized Hades windows'); document.body.appendChild(dock); return dock;
}
function save() {
  const layout={}; for (const [id,w] of windows) { const r=w.el.getBoundingClientRect(); layout[id]={left:r.left,top:r.top,width:r.width,height:r.height,minimized:w.minimized,maximized:w.maximized,snap:w.snap,z:w.el.style.zIndex,view:w.view,title:w.title,entity:w.entity}; }
  try { localStorage.setItem(key(), JSON.stringify(layout)); } catch (_) {}
}
function focus(id) { const w=windows.get(id); if (!w) return; w.el.style.zIndex=String(++topZ); w.el.focus({preventScroll:true}); save(); }
function setRect(w, rect) { if (mobile()) { w.el.style.cssText += ''; w.el.style.left='0';w.el.style.top='0';w.el.style.width='100vw';w.el.style.height='100dvh';w.snap='mobile'; return; } w.el.style.left=`${rect.left}px`;w.el.style.top=`${rect.top}px`;w.el.style.width=`${Math.max(280,rect.width)}px`;w.el.style.height=`${Math.max(180,rect.height)}px`; }
function snap(id, where) {
  const w=windows.get(id); if (!w || mobile()) return;
  const sw=window.innerWidth, sh=window.innerHeight, l=window.innerWidth>768?Math.max(0,document.querySelector('.sidebar')?.getBoundingClientRect().right||0):0, W=sw-l;
  const halfW=W/2, halfH=sh/2; const rects={left:{left:l,top:0,width:halfW,height:sh},right:{left:l+halfW,top:0,width:halfW,height:sh},top:{left:l,top:0,width:W,height:halfH},bottom:{left:l,top:halfH,width:W,height:halfH},'top-left':{left:l,top:0,width:halfW,height:halfH},'top-right':{left:l+halfW,top:0,width:halfW,height:halfH},'bottom-left':{left:l,top:halfH,width:halfW,height:halfH},'bottom-right':{left:l+halfW,top:halfH,width:halfW,height:halfH},maximize:{left:l,top:0,width:W,height:sh}};
  const rect=rects[where]; if (!rect) return; setRect(w,rect); w.snap=where; w.maximized=where==='maximize'; focus(id); save();
}
function minimize(id) { const w=windows.get(id); if(!w)return; w.minimized=true; w.el.style.display='none'; renderDock(); save(); }
function restore(id) { const w=windows.get(id); if(!w)return; w.minimized=false; w.el.style.display='flex'; focus(id); renderDock(); save(); }
function close(id) { const w=windows.get(id); if(!w)return; w.el.remove(); windows.delete(id); renderDock(); save(); }
function renderDock() { const d=ensureDock(); d.innerHTML=''; for(const [id,w] of windows) if(w.minimized){const b=document.createElement('button');b.type='button';b.textContent=w.title;b.title=`Restore ${w.title}`;b.onclick=()=>restore(id);d.appendChild(b);} d.hidden=!d.children.length||mobile(); }
function drag(w, ev) { if(mobile()||ev.target.closest('button'))return; ev.preventDefault(); focus(w.id); const r=w.el.getBoundingClientRect(), sx=ev.clientX, sy=ev.clientY; const move=e=>{w.el.style.left=`${clamp(r.left+e.clientX-sx,0,Math.max(0,innerWidth-80))}px`;w.el.style.top=`${clamp(r.top+e.clientY-sy,0,Math.max(0,innerHeight-50))}px`;w.snap=null;}; const up=()=>{window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',up);save();}; window.addEventListener('pointermove',move);window.addEventListener('pointerup',up,{once:true}); }
export function openWindow({id,title,view='generic',content,entity=null}) {
  if(windows.has(id)){restore(id);return windows.get(id).el;}
  const el=document.createElement('section'); el.id=id; el.className='hades-workspace-window'; el.tabIndex=0; el.dataset.view=view; el.dataset.entity=entity||''; el.innerHTML=`<header class="hades-window-titlebar"><strong>${title}</strong><span class="hades-window-spacer"></span><button data-win="min" aria-label="Minimize">−</button><button data-win="max" aria-label="Maximize">□</button><button data-win="snap-left" aria-label="Snap left">◀</button><button data-win="snap-right" aria-label="Snap right">▶</button><button data-win="snap-top-left" aria-label="Snap top left">↖</button><button data-win="snap-top-right" aria-label="Snap top right">↗</button><button data-win="snap-bottom-left" aria-label="Snap bottom left">↙</button><button data-win="snap-bottom-right" aria-label="Snap bottom right">↘</button><button data-win="close" aria-label="Close">×</button></header><main class="hades-window-body"></main>`; document.body.appendChild(el);
  const w={id,title,view,entity,el,minimized:false,maximized:false,snap:null}; windows.set(id,w); const body=el.querySelector('.hades-window-body'); if(typeof content==='string')body.innerHTML=content; else if(content)body.append(content);
  el.querySelector('.hades-window-titlebar').addEventListener('pointerdown',e=>drag(w,e)); el.addEventListener('pointerdown',()=>focus(id));
  el.querySelectorAll('[data-win]').forEach(b=>b.addEventListener('click',()=>{const a=b.dataset.win;if(a==='min')minimize(id);else if(a==='max')snap(id,'maximize');else if(a==='close')close(id);else if(a.startsWith('snap-'))snap(id,a.slice(5));}));
  el.addEventListener('keyup',e=>{if(e.key==='Escape')close(id);});
  const r={left:Math.max(20,(innerWidth-720)/2),top:Math.max(20,(innerHeight-460)/2),width:720,height:460}; setRect(w,r); focus(id); restoreLayout(w); renderDock(); return el;
}
function savedLayout(){ let saved={}; try { saved=JSON.parse(localStorage.getItem(key())||'{}'); } catch (_) {} return saved; }
function savedFor(view, saved=savedLayout()){ return Object.entries(saved).filter(([,descriptor])=>!view || descriptor.view===view); }
function restoreRegistered(view, saved=savedLayout()){
  for (const [id, descriptor] of savedFor(view, saved)) {
    if (!restorers.has(descriptor.view)) continue;
    if (!windows.has(id)) openWindow({id, view:descriptor.view, entity:descriptor.entity||null, title:descriptor.title||descriptor.view, content:'<p>Restoring workspace…</p>'});
    restorers.get(descriptor.view)({id, entity:descriptor.entity||null, title:descriptor.title||descriptor.view});
  }
}
function restoreLayout(w){ try{const l=JSON.parse(localStorage.getItem(key())||'{}')[w.id];if(!l)return;if(!mobile())setRect(w,{left:clamp(l.left,0,innerWidth-120),top:clamp(l.top,0,innerHeight-80),width:l.width,height:l.height});if(l.snap)w.snap=l.snap;if(l.maximized)w.maximized=true;if(l.minimized)minimize(w.id);}catch(_){} }
export function setOwner(value){
  const next=String(value||'local');
  if (ownerReady && next===owner) return;
  for (const w of windows.values()) w.el.remove(); windows.clear(); renderDock();
  owner=next;
  ownerReady=true;
  const saved=savedLayout();
  for (const view of restorers.keys()) restoreRegistered(view, saved);
}
export function openView(view, entity, title, content){return openWindow({id:`${view}:${entity||'main'}`,view,entity,title,content});}
export function registerView(view, restore){
  if (typeof restore !== 'function') return;
  restorers.set(view, restore);
  if (ownerReady) restoreRegistered(view);
}
export { focus, minimize, restore, close, snap };
export function api(){return {openWindow,openView,focus,minimize,restore,close,snap,setOwner};}
window.hadesWindowManager=api();
window.addEventListener('resize',()=>{for(const w of windows.values())if(mobile()){w.el.style.left='0';w.el.style.top='0';w.el.style.width='100vw';w.el.style.height='100dvh';}renderDock();});
