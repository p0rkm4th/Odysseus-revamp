let uiModule = null;
if (typeof window !== 'undefined') {
  import('./ui.js').then(m => { uiModule = m.default || m; }).catch(() => {});
}

const DOMAINS = ['all', 'it', 'kitchen', 'household'];
const UNITS = ['each', 'g', 'kg', 'ml', 'l', 'oz', 'lb'];
let open = false;
let tab = 'stock';
let domain = 'all';
let query = '';
let requestGeneration = 0;
let editingDraft = null;

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[c]);
}

export function opaqueAttachmentIds(value) {
  const ids = String(value || '').split(/[\s,]+/).map(v => v.trim()).filter(Boolean);
  if (ids.length > 20 || ids.some(id => !/^[0-9a-fA-F]{32}(?:\.[A-Za-z0-9]+)?$/.test(id))) {
    throw new Error('Attachments must be server-issued upload IDs, not paths or URLs.');
  }
  return [...new Set(ids)];
}

export function makeIdempotencyKey(prefix = 'inventory-ui') {
  const uuid = globalThis.crypto?.randomUUID?.();
  return `${prefix}:${uuid || `${Date.now()}-${Math.random().toString(16).slice(2)}`}`;
}

export function stockTotal(lots = []) {
  return lots.reduce((sum, lot) => sum + Number(lot.quantity || 0), 0);
}

export function assetPayload(data) {
  let specs = {};
  if (String(data.specs || '').trim()) {
    specs = JSON.parse(data.specs);
    if (!specs || Array.isArray(specs) || typeof specs !== 'object') throw new Error('Specifications must be a JSON object.');
  }
  const split = value => String(value || '').split(',').map(part => part.trim()).filter(Boolean);
  return {
    serial_number: data.serial_number || null, asset_tag: data.asset_tag || null,
    status: data.status || 'in_stock', condition: data.condition || null,
    hostname: data.hostname || null, assigned_to: data.assigned_to || null,
    parent_asset_id: data.parent_asset_id || null,
    mac_addresses: split(data.mac_addresses), ip_addresses: split(data.ip_addresses), specs,
  };
}

export function apiError(payload, status) {
  const detail = payload?.detail;
  if (typeof detail === 'string') return detail;
  if (detail?.message) {
    const shortage = (detail.shortages || []).map(s => `${s.name}: ${s.missing} ${s.unit}`).join(', ');
    return shortage ? `${detail.message} — ${shortage}` : detail.message;
  }
  return `Request failed (${status})`;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: 'same-origin',
    headers: options.body ? {'Content-Type': 'application/json'} : undefined,
    ...options,
  });
  let payload = null;
  try { payload = await response.json(); } catch {}
  if (!response.ok) throw new Error(apiError(payload, response.status));
  return payload;
}

function shell() {
  const node = document.createElement('section');
  node.id = 'inventory-pane';
  node.className = 'inventory-pane';
  node.setAttribute('role', 'dialog');
  node.setAttribute('aria-modal', 'true');
  node.setAttribute('aria-labelledby', 'inventory-title');
  node.innerHTML = `
    <header class="inventory-header">
      <div><h2 id="inventory-title">Home inventory</h2><p>IT assets, pantry, and household stock</p></div>
      <button class="inventory-icon-btn" data-close aria-label="Close inventory">×</button>
    </header>
    <nav class="inventory-tabs" aria-label="Inventory views">
      <button data-tab="stock" class="active">Stock</button>
      <button data-tab="recipes">Recipes</button>
      <button data-tab="intake">Add from text or media</button>
    </nav>
    <main id="inventory-content" class="inventory-content"></main>`;
  node.addEventListener('click', onClick);
  node.addEventListener('submit', onSubmit);
  node.addEventListener('input', onInput);
  return node;
}

function loading(label = 'Loading…') {
  return `<div class="inventory-state" role="status">${escapeHtml(label)}</div>`;
}

function renderStockScaffold() {
  return `
    <div class="inventory-toolbar">
      <input id="inventory-search" type="search" maxlength="200" value="${escapeHtml(query)}" placeholder="Search stock" aria-label="Search stock">
      <div class="inventory-domain-filter">${DOMAINS.map(d => `<button data-domain="${d}" class="${domain === d ? 'active' : ''}">${d === 'all' ? 'All' : d}</button>`).join('')}</div>
      <button class="inventory-primary" data-action="new-item">+ Item</button>
    </div>
    <div id="inventory-stock-list">${loading()}</div>`;
}

async function loadStock() {
  const generation = ++requestGeneration;
  const content = document.getElementById('inventory-content');
  if (!content) return;
  content.innerHTML = renderStockScaffold();
  const params = new URLSearchParams();
  if (domain !== 'all') params.set('domain', domain);
  let path = '/api/inventory/items';
  if (query.trim()) { path += '/search'; params.set('q', query.trim()); }
  try {
    const result = await api(`${path}?${params}`);
    const items = result.items || [];
    const details = await Promise.all(items.map(item => api(`/api/inventory/items/${encodeURIComponent(item.id)}`)));
    if (generation !== requestGeneration) return;
    const list = document.getElementById('inventory-stock-list');
    if (!list) return;
    list.innerHTML = items.length ? items.map((item, index) => {
      const lots = details[index]?.lots || [];
      const asset = details[index]?.asset;
      const components = details[index]?.components || [];
      const total = stockTotal(lots);
      return `<article class="inventory-card" data-item-id="${escapeHtml(item.id)}">
        <div class="inventory-card-main"><span class="inventory-domain">${escapeHtml(item.domain)}</span>
          <h3>${escapeHtml(item.name)}</h3><p>${escapeHtml(asset?.serial_number || item.category || item.item_kind || '')}${components.length ? ` · ${components.length} component${components.length === 1 ? '' : 's'}` : ''}</p></div>
        <strong class="inventory-quantity">${escapeHtml(total)} <small>${escapeHtml(item.default_unit)}</small></strong>
        <div class="inventory-card-actions">
          ${item.domain === 'it' && item.item_kind === 'asset' ? '<button data-action="asset-details">Asset</button>' : ''}<button data-action="stock-add">Add</button><button data-action="stock-consume" ${total <= 0 ? 'disabled' : ''}>Use</button>
        </div></article>`;
    }).join('') : '<div class="inventory-state">No matching stock. Add an item or create a reviewed intake draft.</div>';
  } catch (error) { showInlineError(error); }
}

function renderRecipesScaffold() {
  return `<div class="inventory-toolbar"><div><h3>Recipes</h3><p>Check live stock before cooking.</p></div><button class="inventory-primary" data-action="new-recipe">+ Recipe</button></div><div id="inventory-recipe-list">${loading()}</div>`;
}

async function loadRecipes() {
  const content = document.getElementById('inventory-content');
  if (!content) return;
  content.innerHTML = renderRecipesScaffold();
  try {
    const {recipes = []} = await api('/api/recipes');
    const plans = await Promise.all(recipes.map(recipe => api(`/api/recipes/${encodeURIComponent(recipe.id)}/can-make`)));
    const list = document.getElementById('inventory-recipe-list');
    list.innerHTML = recipes.length ? recipes.map((recipe, i) => `<article class="inventory-card inventory-recipe" data-recipe-id="${escapeHtml(recipe.id)}">
      <div class="inventory-card-main"><h3>${escapeHtml(recipe.name)}</h3><p>${escapeHtml(recipe.servings)} servings · ${(recipe.ingredients || []).length} ingredients</p></div>
      <span class="inventory-ready ${plans[i].can_make ? 'yes' : 'no'}">${plans[i].can_make ? 'Ready to make' : `${plans[i].shortages.length} shortage${plans[i].shortages.length === 1 ? '' : 's'}`}</span>
      <button data-action="recipe-details">Details</button>${plans[i].can_make ? '<button class="inventory-primary" data-action="cook">Cook</button>' : ''}
    </article>`).join('') : '<div class="inventory-state">No recipes yet.</div>';
  } catch (error) { showInlineError(error); }
}

function intakeForm() {
  return `<form id="inventory-intake-form" class="inventory-form">
    <div class="inventory-callout"><strong>Review required.</strong> Text, voice transcripts, and photo descriptions are untrusted. Nothing changes until the structured draft is ready and you explicitly confirm it.</div>
    <label>Source <select name="source_type"><option value="natural_language">Natural language</option><option value="voice">Voice transcript</option><option value="photo">Photo</option><option value="telegram">Telegram</option></select></label>
    <label class="inventory-wide">What did you add or use?<textarea name="source_text" maxlength="4000" placeholder="For example: Added 2 kg of rice to the pantry"></textarea></label>
    <label class="inventory-wide">Server upload IDs <input name="attachment_ids" autocomplete="off" placeholder="Optional opaque upload ID"></label>
    <fieldset class="inventory-candidate"><legend>Reviewed operation</legend>
      <label>Action <select name="action"><option value="add">Add</option><option value="remove">Remove</option></select></label>
      <label>Area <select name="domain"><option value="kitchen">Kitchen</option><option value="household">Household</option><option value="it">IT hardware</option></select></label>
      <label class="inventory-wide">Item name <input name="name" required maxlength="160"></label>
      <label>Exact quantity <input name="quantity" required inputmode="decimal"></label>
      <label>Unit <select name="unit">${UNITS.map(u => `<option>${u}</option>`).join('')}</select></label>
      <label>Category <input name="category" maxlength="80"></label><label>Brand / maker <input name="brand" maxlength="120"></label>
      <label>Manufacturer <input name="manufacturer" maxlength="120"></label><label>Model <input name="model" maxlength="160"></label>
      <label>Serial number <input name="serial_number" maxlength="160"></label><label>Part number <input name="part_number" maxlength="160"></label>
      <label>Condition <input name="condition" maxlength="80"></label>
    </fieldset>
    <button class="inventory-primary" type="submit">Create review draft</button>
  </form><div id="inventory-draft-review"></div>`;
}

function renderDraft(draft) {
  const review = document.getElementById('inventory-draft-review');
  if (!review) return;
  const ready = draft.status === 'ready_for_confirmation';
  editingDraft = draft;
  review.innerHTML = `<section class="inventory-draft" data-draft-id="${escapeHtml(draft.draft_id)}" data-revision="${escapeHtml(draft.revision || '')}">
    <h3>Review draft</h3><span class="inventory-ready ${ready ? 'yes' : 'no'}">${escapeHtml(draft.status.replaceAll('_', ' '))}</span>
    ${(draft.operations || []).map(op => `<div class="inventory-operation"><strong>${escapeHtml(op.action)} ${escapeHtml(op.quantity || '?')} ${escapeHtml(op.unit || '')} ${escapeHtml(op.item?.name || '')}</strong><small>${escapeHtml(op.domain || '')}</small>
      ${(op.errors || []).map(e => `<p class="inventory-error">${escapeHtml(e)}</p>`).join('')}${(op.warnings || []).map(w => `<p class="inventory-warning">${escapeHtml(w)}</p>`).join('')}</div>`).join('')}
    <p class="inventory-muted">Draft ${escapeHtml(draft.draft_id)}. Creating this draft did not alter stock.</p>
    <p>Correct the fields in the form above, then revalidate this draft before confirming.</p>
    ${ready ? '<button class="inventory-danger" data-action="confirm-draft">Confirm and apply exactly these changes</button>' : ''}
  </section>`;
  const form = document.getElementById('inventory-intake-form');
  const operation = draft.operations?.[0];
  if (form && operation) {
    const values = {...operation.item, action:operation.action, domain:operation.domain, quantity:operation.quantity || '', unit:operation.unit || '', source_text:draft.source?.text || ''};
    Object.entries(values).forEach(([name, value]) => { if (form.elements[name]) form.elements[name].value = value ?? ''; });
    form.querySelector('[type=submit]').textContent = 'Correct and revalidate draft';
  }
}

function modalForm(title, body, submitLabel, kind, id = '') {
  const modal = document.createElement('div');
  modal.className = 'inventory-dialog-backdrop';
  modal.innerHTML = `<form class="inventory-dialog" data-kind="${kind}" data-id="${escapeHtml(id)}"><h3>${escapeHtml(title)}</h3>${body}<div class="inventory-dialog-actions"><button type="button" data-action="dismiss-dialog">Cancel</button><button class="inventory-primary" type="submit">${escapeHtml(submitLabel)}</button></div></form>`;
  document.body.appendChild(modal);
  modal.addEventListener('click', onClick);
  modal.addEventListener('submit', onSubmit);
  modal.querySelector('input')?.focus();
}

function field(label, name, attrs = '') { return `<label>${label}<input name="${name}" ${attrs}></label>`; }

async function onSubmit(event) {
  const form = event.target;
  if (!form.matches('#inventory-intake-form, .inventory-dialog')) return;
  event.preventDefault();
  const data = Object.fromEntries(new FormData(form));
  const submit = form.querySelector('[type=submit]');
  if (submit) submit.disabled = true;
  try {
    if (form.id === 'inventory-intake-form') {
      const candidate = {action:data.action, domain:data.domain, name:data.name, quantity:data.quantity, unit:data.unit, category:data.category, brand:data.brand, manufacturer:data.manufacturer, model:data.model, serial_number:data.serial_number, part_number:data.part_number, condition:data.condition};
      if (editingDraft) {
        renderDraft(await api(`/api/inventory/intake/drafts/${encodeURIComponent(editingDraft.draft_id)}`, {method:'PUT', body:JSON.stringify({expected_revision:editingDraft.revision, source_text:data.source_text, candidates:[candidate]})}));
      } else {
        const payload = {source_type: data.source_type, source_text: data.source_text, attachment_ids: opaqueAttachmentIds(data.attachment_ids), idempotency_key: makeIdempotencyKey('intake'), candidates: [candidate]};
        renderDraft(await api('/api/inventory/intake/drafts', {method:'POST', body:JSON.stringify(payload)}));
      }
      return;
    }
    const kind = form.dataset.kind;
    if (kind === 'item') await api('/api/inventory/items', {method:'POST', body:JSON.stringify({name:data.name, domain:data.domain, item_kind:data.domain === 'it' ? 'asset' : data.domain === 'kitchen' ? 'ingredient' : 'consumable', default_unit:data.unit, category:data.category})});
    if (kind === 'asset') await api(`/api/inventory/assets/${encodeURIComponent(form.dataset.id)}`, {method:'PUT', body:JSON.stringify(assetPayload(data))});
    if (kind === 'stock') await api(`/api/inventory/items/${encodeURIComponent(form.dataset.id)}/stock`, {method:'POST', body:JSON.stringify({quantity:data.quantity, unit:data.unit, idempotency_key:makeIdempotencyKey('stock')})});
    if (kind === 'consume') await api(`/api/inventory/items/${encodeURIComponent(form.dataset.id)}/consume`, {method:'POST', body:JSON.stringify({quantity:data.quantity, unit:data.unit, reason:data.reason, idempotency_key:makeIdempotencyKey('consume')})});
    if (kind === 'recipe') {
      const ingredients = data.ingredients.split('\n').filter(Boolean).map(line => { const match = line.trim().match(/^(.+?)\s*\|\s*([0-9.]+)\s*\|\s*(\w+)$/); if (!match) throw new Error('Use one ingredient per line: item ID | quantity | unit'); return {item_id:match[1].trim(), quantity:match[2], unit:match[3]}; });
      await api('/api/recipes', {method:'POST', body:JSON.stringify({name:data.name, servings:data.servings, ingredients, instructions:data.instructions})});
    }
    form.closest('.inventory-dialog-backdrop')?.remove();
    uiModule.showToast?.('Inventory updated');
    kind === 'recipe' ? await loadRecipes() : await loadStock();
  } catch (error) { uiModule.showError?.(error.message); }
  finally { if (submit) submit.disabled = false; }
}

async function onClick(event) {
  const button = event.target.closest('button');
  if (!button) return;
  if (button.matches('[data-close]')) return closePanel();
  if (button.dataset.tab) { tab = button.dataset.tab; renderTab(); return; }
  if (button.dataset.domain) { domain = button.dataset.domain; loadStock(); return; }
  const action = button.dataset.action;
  if (action === 'retry') return renderTab();
  if (action === 'dismiss-dialog') return button.closest('.inventory-dialog-backdrop')?.remove();
  if (action === 'new-item') return modalForm('Add item', `${field('Name','name','required maxlength="200"')}<label>Area<select name="domain"><option value="kitchen">Kitchen</option><option value="household">Household</option><option value="it">IT</option></select></label><label>Unit<select name="unit">${UNITS.map(u=>`<option>${u}</option>`).join('')}</select></label>${field('Category','category','maxlength="80"')}`, 'Add item', 'item');
  const card = button.closest('[data-item-id]');
  if (action === 'asset-details') {
    try {
      const {asset = {}} = await api(`/api/inventory/items/${encodeURIComponent(card.dataset.itemId)}`);
      const body = `${field('Serial number','serial_number',`maxlength="160" value="${escapeHtml(asset?.serial_number || '')}"`)}${field('Asset tag','asset_tag',`maxlength="160" value="${escapeHtml(asset?.asset_tag || '')}"`)}<label>Status<select name="status">${['in_stock','deployed','repair','retired','disposed','lost'].map(value=>`<option value="${value}" ${asset?.status === value ? 'selected' : ''}>${value.replaceAll('_',' ')}</option>`).join('')}</select></label>${field('Condition','condition',`maxlength="80" value="${escapeHtml(asset?.condition || '')}"`)}${field('Hostname','hostname',`maxlength="253" value="${escapeHtml(asset?.hostname || '')}"`)}${field('Assigned to','assigned_to',`maxlength="255" value="${escapeHtml(asset?.assigned_to || '')}"`)}${field('Parent asset ID','parent_asset_id',`maxlength="255" value="${escapeHtml(asset?.parent_asset_id || '')}"`)}${field('MAC addresses (comma separated)','mac_addresses',`value="${escapeHtml((asset?.mac_addresses || []).join(', '))}"`)}${field('IP addresses (comma separated)','ip_addresses',`value="${escapeHtml((asset?.ip_addresses || []).join(', '))}"`)}<label>Specifications (JSON object)<textarea name="specs">${escapeHtml(JSON.stringify(asset?.specs || {}, null, 2))}</textarea></label>`;
      return modalForm('Hardware asset details', body, 'Save asset', 'asset', card.dataset.itemId);
    } catch (error) { uiModule.showError?.(error.message); return; }
  }
  if (action === 'stock-add' || action === 'stock-consume') return modalForm(action === 'stock-add' ? 'Add stock' : 'Use stock', `${field('Quantity','quantity','required inputmode="decimal"')}<label>Unit<select name="unit">${UNITS.map(u=>`<option>${u}</option>`).join('')}</select></label>${action === 'stock-consume' ? field('Reason','reason','maxlength="200"') : ''}`, action === 'stock-add' ? 'Add' : 'Use', action === 'stock-add' ? 'stock' : 'consume', card.dataset.itemId);
  if (action === 'new-recipe') return modalForm('New recipe', `${field('Name','name','required maxlength="200"')}${field('Servings','servings','required inputmode="decimal"')}<label>Ingredients <small>item ID | quantity | unit</small><textarea name="ingredients" required></textarea></label><label>Instructions<textarea name="instructions"></textarea></label>`, 'Save recipe', 'recipe');
  const recipeCard = button.closest('[data-recipe-id]');
  if (action === 'recipe-details') return showRecipe(recipeCard.dataset.recipeId);
  if (action === 'cook') return cookRecipe(recipeCard.dataset.recipeId, button);
  if (action === 'confirm-draft') {
    const draft = button.closest('[data-draft-id]');
    return confirmDraft(draft.dataset.draftId, draft.dataset.revision, button);
  }
}

let searchTimer;
function onInput(event) {
  if (event.target.id !== 'inventory-search') return;
  query = event.target.value;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadStock, 250);
}

async function showRecipe(id) {
  try {
    const [{recipe}, plan] = await Promise.all([api(`/api/recipes/${encodeURIComponent(id)}`), api(`/api/recipes/${encodeURIComponent(id)}/can-make`)]);
    const shortages = (plan.shortages || []).map(s => `<li>${escapeHtml(s.name)}: need ${escapeHtml(s.missing)} ${escapeHtml(s.unit)} more</li>`).join('');
    modalForm(recipe.name, `<p>${escapeHtml(recipe.instructions || 'No instructions saved.')}</p><h4>${plan.can_make ? 'You have everything' : 'Missing stock'}</h4><ul>${shortages}</ul>`, 'Close', 'view');
    const form = document.querySelector('.inventory-dialog[data-kind="view"]');
    form.querySelector('[type=submit]').type = 'button'; form.querySelector('[type=submit]').dataset.action = 'dismiss-dialog';
  } catch (error) { uiModule.showError?.(error.message); }
}

async function cookRecipe(id, button) {
  if (!window.confirm('Cook this recipe and deduct its ingredients from stock?')) return;
  button.disabled = true;
  try { await api(`/api/recipes/${encodeURIComponent(id)}/cook`, {method:'POST', body:JSON.stringify({idempotency_key:makeIdempotencyKey('cook')})}); uiModule.showToast?.('Recipe cooked and stock updated'); await loadRecipes(); }
  catch (error) { uiModule.showError?.(error.message); button.disabled = false; }
}

async function confirmDraft(id, revision, button) {
  if (!window.confirm('Apply exactly the reviewed operations shown? This will change stock.')) return;
  button.disabled = true;
  try {
    const result = await api(`/api/inventory/intake/drafts/${encodeURIComponent(id)}/confirm`, {method:'POST', body:JSON.stringify({confirm:true,expected_revision:revision})});
    const receipt = result.receipt || {};
    button.closest('.inventory-draft').innerHTML = `<h3>Applied</h3><p>Stock was updated${result.replayed ? ' (already applied earlier)' : ''}.</p><dl><dt>Receipt</dt><dd>${escapeHtml(receipt.id || id)}</dd><dt>Authority</dt><dd>${escapeHtml(receipt.authority || 'explicit confirmation')}</dd><dt>Changes</dt><dd>${escapeHtml(receipt.operation_count ?? '')}</dd></dl><p class="inventory-muted">${escapeHtml(receipt.recovery || '')}</p>`;
    uiModule.showToast?.('Draft applied');
    editingDraft = null;
  }
  catch (error) {
    if (/already in progress/i.test(error.message) && window.confirm('The previous apply may have been interrupted. Resume the same idempotent draft?')) {
      try { await api(`/api/inventory/intake/drafts/${encodeURIComponent(id)}/confirm`, {method:'POST', body:JSON.stringify({confirm:true,resume:true})}); uiModule.showToast?.('Draft resumed and applied'); await loadStock(); } catch (resumeError) { uiModule.showError?.(resumeError.message); }
    } else uiModule.showError?.(error.message);
    button.disabled = false;
  }
}

function showInlineError(error) {
  const content = document.getElementById('inventory-content');
  if (content) content.innerHTML = `<div class="inventory-state inventory-error">${escapeHtml(error.message)} <button data-action="retry">Retry</button></div>`;
}

function renderTab() {
  document.querySelectorAll('.inventory-tabs [data-tab]').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  if (tab === 'stock') { editingDraft = null; loadStock(); }
  else if (tab === 'recipes') { editingDraft = null; loadRecipes(); }
  else document.getElementById('inventory-content').innerHTML = intakeForm();
}

export function openPanel() {
  if (open) return;
  open = true;
  document.body.appendChild(shell());
  document.body.classList.add('inventory-view');
  document.getElementById('tool-inventory-btn')?.classList.add('active');
  renderTab();
}

export function closePanel() {
  open = false;
  editingDraft = null;
  requestGeneration++;
  document.getElementById('inventory-pane')?.remove();
  document.querySelectorAll('.inventory-dialog-backdrop').forEach(el => el.remove());
  document.body.classList.remove('inventory-view');
  document.getElementById('tool-inventory-btn')?.classList.remove('active');
}

export function togglePanel() { open ? closePanel() : openPanel(); }

export default {openPanel, closePanel, togglePanel};
