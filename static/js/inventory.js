import { openWindow, close as closeWorkspaceWindow } from './workspaceWindowManager.js';

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
let windowEl = null;

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
  const isForm = typeof FormData !== 'undefined' && options.body instanceof FormData;
  const response = await fetch(path, {
    credentials: 'same-origin',
    headers: options.body && !isForm ? {'Content-Type': 'application/json'} : undefined,
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
  node.className = 'inventory-module';
  node.setAttribute('role', 'dialog');
  node.setAttribute('aria-modal', 'true');
  node.setAttribute('aria-labelledby', 'inventory-title');
  node.innerHTML = `
    <nav class="inventory-tabs" aria-label="Inventory views">
      <button data-tab="stock" class="active">Pantry · On hand</button>
      <button data-tab="fridge">Fridge</button>
      <button data-tab="grocery" aria-label="Grocery list · items to buy">Grocery · To buy</button>
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
      <button class="inventory-primary" data-action="new-item">+ Pantry item</button>
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
          ${item.domain === 'it' && item.item_kind === 'asset' ? '<button data-action="asset-details">Asset</button>' : ''}<button data-action="edit-item">Edit</button><button data-action="stock-add">Add</button><button data-action="stock-consume" ${total <= 0 ? 'disabled' : ''}>Use</button><button data-action="archive-item">Archive</button>
        </div></article>`;
    }).join('') : '<div class="inventory-state">No matching stock. Add an item or create a reviewed intake draft.</div>';
  } catch (error) { showInlineError(error); }
}

async function loadGrocery() {
  const generation = ++requestGeneration;
  const content = document.getElementById('inventory-content');
  if (!content) return;
  content.innerHTML = `<div class="inventory-toolbar"><div><h3>Grocery · To buy</h3><p>Items you do not currently have and plan to buy. Marking one bought adds owned stock and removes it from this queue.</p></div><button class="inventory-primary" data-action="new-grocery">+ Add to buy list</button></div><div id="inventory-grocery-list">${loading()}</div>`;
  try {
    const result = await api('/api/inventory/items?list_name=grocery');
    const candidates = result.items || [];
    const details = await Promise.all(candidates.map(item => api(`/api/inventory/items/${encodeURIComponent(item.id)}`)));
    if (generation !== requestGeneration) return;
    const rows = candidates.map((item, index) => ({item, total: stockTotal(details[index]?.lots || [])})).filter(row => row.item.shopping_list);
    const list = document.getElementById('inventory-grocery-list');
    list.innerHTML = rows.length ? rows.map(({item}) => `<article class="inventory-card" data-item-id="${escapeHtml(item.id)}"><div class="inventory-card-main"><span class="inventory-domain">To buy</span><h3>${escapeHtml(item.name)}</h3><p>${escapeHtml(item.category || 'Missing from owned stock')} · not counted as pantry stock</p></div><div class="inventory-card-actions"><button data-action="grocery-bought">Bought</button><button data-action="edit-item">Edit</button><button data-action="remove-grocery">Remove</button></div></article>`).join('') : '<div class="inventory-state">Your grocery queue is empty. Add items you need to buy.</div>';
  } catch (error) { showInlineError(error); }
}

async function loadStorageArea(area) {
  const generation = ++requestGeneration;
  const content = document.getElementById('inventory-content');
  if (!content) return;
  content.innerHTML = `<div class="inventory-toolbar"><div><h3>${area[0].toUpperCase()+area.slice(1)} · On hand</h3><p>Owned stock you already have. The grocery queue is separate and contains items to buy.</p></div><button class="inventory-primary" data-action="new-item">+ Add item</button></div><div id="inventory-storage-list">${loading()}</div>`;
  try {
    const {items = []} = await api(`/api/inventory/items?list_name=${encodeURIComponent(area)}`);
    if (generation !== requestGeneration) return;
    document.getElementById('inventory-storage-list').innerHTML = items.length ? items.map(item => `<article class="inventory-card" data-item-id="${escapeHtml(item.id)}"><div class="inventory-card-main"><span class="inventory-domain">${escapeHtml(item.storage_area || area)}</span><h3>${escapeHtml(item.name)}</h3><p>${escapeHtml(item.category || 'Household item')} · ${escapeHtml(item.default_unit || 'each')}</p></div><div class="inventory-card-actions"><button data-action="stock-add">Add stock</button><button data-action="stock-consume" ${Number(item.stock_quantity || 0) <= 0 ? 'disabled' : ''}>Use</button><button data-action="edit-item">Edit</button><button data-action="move-to-grocery">Add to grocery</button><button data-action="archive-item">Archive</button></div></article>`).join('') : `<div class="inventory-state">Your ${area} list is empty.</div>`;
  } catch (error) { showInlineError(error); }
}

function renderRecipesScaffold() {
  return `<div class="inventory-toolbar"><div><h3>Recipes</h3><p>Check live stock before cooking.</p></div><div><button data-action="import-recipe">Import</button><button class="inventory-primary" data-action="new-recipe">+ Recipe</button></div></div><div id="inventory-recipe-list">${loading()}</div>`;
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
    let importedRecipeId = null;
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
    if (kind === 'item' || kind === 'grocery') await api('/api/inventory/items', {method:'POST', body:JSON.stringify({name:data.name, domain:data.domain || 'kitchen', item_kind:data.domain === 'it' ? 'asset' : 'ingredient', default_unit:data.unit || 'each', category:data.category, shopping_list:kind === 'grocery' || data.shopping_list === 'on', storage_area:data.storage_area || null})});
    if (kind === 'edit-item') await api(`/api/inventory/items/${encodeURIComponent(form.dataset.id)}`, {method:'PATCH', body:JSON.stringify({name:data.name, category:data.category, default_unit:data.unit, shopping_list:data.shopping_list === 'on', storage_area:data.storage_area || null})});
    if (kind === 'asset') await api(`/api/inventory/assets/${encodeURIComponent(form.dataset.id)}`, {method:'PUT', body:JSON.stringify(assetPayload(data))});
    if (kind === 'stock') await api(`/api/inventory/items/${encodeURIComponent(form.dataset.id)}/stock`, {method:'POST', body:JSON.stringify({quantity:data.quantity, unit:data.unit, idempotency_key:makeIdempotencyKey('stock')})});
    if (kind === 'stock' && tab === 'grocery') await api(`/api/inventory/items/${encodeURIComponent(form.dataset.id)}`, {method:'PATCH', body:JSON.stringify({shopping_list:false})});
    if (kind === 'consume') await api(`/api/inventory/items/${encodeURIComponent(form.dataset.id)}/consume`, {method:'POST', body:JSON.stringify({quantity:data.quantity, unit:data.unit, reason:data.reason, idempotency_key:makeIdempotencyKey('consume')})});
    if (kind === 'recipe') {
      const ingredients = data.ingredients.split('\n').map(line => line.trim()).filter(Boolean).map(line => { const match = line.match(/^(.+?)\s*\|\s*([0-9.]+)\s*\|\s*([\w-]+)$/); if (!match) throw new Error('Use one ingredient per line: name | quantity | unit'); return {name:match[1].trim(), quantity:match[2], unit:match[3]}; });
      await api('/api/recipes', {method:'POST', body:JSON.stringify({name:data.name, servings:data.servings, ingredients, instructions:data.instructions, source_url:data.source_url || null})});
    }
    if (kind === 'recipe-import') {
      const payload = {name:data.name || null, source_text:data.source_text || null, url:data.url || null};
      const pdf = form.querySelector('input[name="pdf"]')?.files?.[0];
      if (pdf) {
        const upload = new FormData();
        upload.append('files', pdf);
        const uploaded = await api('/api/upload', {method:'POST', body:upload});
        payload.source_text = null;
        payload.attachment_ids = [uploaded.files[0].id];
        payload.url = null;
      }
      const result = await api('/api/recipes/import', {method:'POST', body:JSON.stringify(payload)});
      importedRecipeId = result.recipe?.id || null;
      uiModule.showToast?.(`${result.recipe?.name || 'Recipe'} saved; review missing ingredients before adding to grocery`);
    }
    form.closest('.inventory-dialog-backdrop')?.remove();
    uiModule.showToast?.('Inventory updated');
    if (kind === 'recipe' || kind === 'recipe-import') {
      await loadRecipes();
      if (importedRecipeId) await showRecipe(importedRecipeId);
    } else if (tab === 'grocery') await loadGrocery();
    else if (tab === 'fridge') await loadStorageArea('fridge');
    else await loadStock();
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
  if (action === 'queue-missing') {
    button.disabled = true;
    try {
      const result = await api(`/api/recipes/${encodeURIComponent(button.dataset.recipeId)}/queue-missing`, {method:'POST', body:JSON.stringify({})});
      uiModule.showToast?.(`${result.count || 0} required item${result.count === 1 ? '' : 's'} added to grocery list`);
      button.textContent = 'Added to grocery list';
    } catch (error) { uiModule.showError?.(error.message); button.disabled = false; }
    return;
  }
  if (action === 'new-item' || action === 'new-grocery') return modalForm(action === 'new-grocery' ? 'Add item to grocery · To buy' : 'Add pantry item · On hand', `${action === 'new-grocery' ? '<p class="inventory-muted">This queues an item to buy; it does not add owned stock.</p>' : ''}${field('Name','name','required maxlength="200"')}<label>Area<select name="domain"><option value="kitchen">Kitchen</option><option value="household">Household</option><option value="it">IT</option></select></label>${action === 'new-grocery' ? '' : '<label>Storage<select name="storage_area"><option value="">Unassigned</option><option value="pantry">Pantry</option><option value="fridge">Fridge</option><option value="freezer">Freezer</option></select></label>'}<label>Unit<select name="unit">${UNITS.map(u=>`<option>${u}</option>`).join('')}</select></label>${field('Category','category','maxlength="80"')}${action === 'new-grocery' ? '<input type="hidden" name="shopping_list" value="on">' : '<label><input type="checkbox" name="shopping_list"> Also queue to buy (does not add stock)</label>'}`, action === 'new-grocery' ? 'Add to buy list' : 'Add item', action === 'new-grocery' ? 'grocery' : 'item');
  const card = button.closest('[data-item-id]');
  const recipeCard = button.closest('[data-recipe-id]');
  if (['edit-item', 'remove-grocery', 'move-to-grocery', 'archive-item', 'grocery-bought', 'asset-details', 'stock-add', 'stock-consume'].includes(action) && !card) {
    uiModule.showError?.('This inventory action is no longer attached to an item. Refresh and try again.');
    return;
  }
  if (['recipe-details', 'cook'].includes(action) && !recipeCard) {
    uiModule.showError?.('This recipe is no longer attached to the current view. Refresh and try again.');
    return;
  }
  if (action === 'edit-item') {
    const {item} = await api(`/api/inventory/items/${encodeURIComponent(card.dataset.itemId)}`);
    return modalForm('Edit inventory item', `${field('Name','name',`required maxlength="200" value="${escapeHtml(item.name)}"`)}${field('Category','category',`maxlength="80" value="${escapeHtml(item.category || '')}"`)}<label>Storage<select name="storage_area"><option value="">Unassigned</option>${['pantry','fridge','freezer'].map(area=>`<option value="${area}" ${item.storage_area === area ? 'selected' : ''}>${area[0].toUpperCase()+area.slice(1)}</option>`).join('')}</select></label><label>Unit<select name="unit">${UNITS.map(u=>`<option ${item.default_unit === u ? 'selected' : ''}>${u}</option>`).join('')}</select></label><label><input type="checkbox" name="shopping_list" ${item.shopping_list ? 'checked' : ''}> Queue to buy (does not change owned stock)</label>`, 'Save', 'edit-item', card.dataset.itemId);
  }
  if (action === 'remove-grocery') { await api(`/api/inventory/items/${encodeURIComponent(card.dataset.itemId)}`, {method:'PATCH', body:JSON.stringify({shopping_list:false})}); return loadGrocery(); }
  if (action === 'move-to-grocery') { await api(`/api/inventory/items/${encodeURIComponent(card.dataset.itemId)}`, {method:'PATCH', body:JSON.stringify({shopping_list:true})}); uiModule.showToast?.('Added to grocery list'); return loadStorageArea(tab); }
  if (action === 'archive-item') { if (!window.confirm('Archive this item? Its history stays available.')) return; await api(`/api/inventory/items/${encodeURIComponent(card.dataset.itemId)}/archive`, {method:'POST'}); return tab === 'grocery' ? loadGrocery() : loadStock(); }
  if (action === 'grocery-bought') return modalForm('Mark as bought', `${field('Quantity','quantity','required inputmode="decimal"')}<label>Unit<select name="unit">${UNITS.map(u=>`<option>${u}</option>`).join('')}</select></label>`, 'Add stock', 'stock', card.dataset.itemId);
  if (action === 'asset-details') {
    try {
      const {asset = {}} = await api(`/api/inventory/items/${encodeURIComponent(card.dataset.itemId)}`);
      const body = `${field('Serial number','serial_number',`maxlength="160" value="${escapeHtml(asset?.serial_number || '')}"`)}${field('Asset tag','asset_tag',`maxlength="160" value="${escapeHtml(asset?.asset_tag || '')}"`)}<label>Status<select name="status">${['in_stock','deployed','repair','retired','disposed','lost'].map(value=>`<option value="${value}" ${asset?.status === value ? 'selected' : ''}>${value.replaceAll('_',' ')}</option>`).join('')}</select></label>${field('Condition','condition',`maxlength="80" value="${escapeHtml(asset?.condition || '')}"`)}${field('Hostname','hostname',`maxlength="253" value="${escapeHtml(asset?.hostname || '')}"`)}${field('Assigned to','assigned_to',`maxlength="255" value="${escapeHtml(asset?.assigned_to || '')}"`)}${field('Parent asset ID','parent_asset_id',`maxlength="255" value="${escapeHtml(asset?.parent_asset_id || '')}"`)}${field('MAC addresses (comma separated)','mac_addresses',`value="${escapeHtml((asset?.mac_addresses || []).join(', '))}"`)}${field('IP addresses (comma separated)','ip_addresses',`value="${escapeHtml((asset?.ip_addresses || []).join(', '))}"`)}<label>Specifications (JSON object)<textarea name="specs">${escapeHtml(JSON.stringify(asset?.specs || {}, null, 2))}</textarea></label>`;
      return modalForm('Hardware asset details', body, 'Save asset', 'asset', card.dataset.itemId);
    } catch (error) { uiModule.showError?.(error.message); return; }
  }
  if (action === 'stock-add' || action === 'stock-consume') return modalForm(action === 'stock-add' ? 'Add stock' : 'Use stock', `${field('Quantity','quantity','required inputmode="decimal"')}<label>Unit<select name="unit">${UNITS.map(u=>`<option>${u}</option>`).join('')}</select></label>${action === 'stock-consume' ? field('Reason','reason','maxlength="200"') : ''}`, action === 'stock-add' ? 'Add' : 'Use', action === 'stock-add' ? 'stock' : 'consume', card.dataset.itemId);
  if (action === 'new-recipe') return modalForm('New recipe', `${field('Name','name','required maxlength="200"')}${field('Servings','servings','required inputmode="decimal"')}<label>Ingredients <small>one per line: name | quantity | unit</small><textarea name="ingredients" placeholder="spaghetti | 400 | g\ntomato sauce | 1 | jar" required></textarea></label>${field('Source URL (optional)','source_url','type="url" maxlength="4000"')}<label>Instructions<textarea name="instructions"></textarea></label>`, 'Save recipe', 'recipe');
  if (action === 'import-recipe') return modalForm('Import recipe', `<p class="inventory-muted">Paste a recipe, provide a public URL, or choose a PDF. Import only saves the recipe; stock and groceries change only when you explicitly queue missing items.</p>${field('Recipe name (optional)','name','maxlength="200"')}${field('Public recipe URL (optional)','url','type="url" maxlength="4000"')}<label>Paste recipe text<textarea name="source_text" maxlength="24000" placeholder="Ingredients:\n2 cups tomato sauce\n400 g spaghetti\n\nDirections:\n..."></textarea></label><label>PDF recipe (optional)<input type="file" name="pdf" accept="application/pdf,.pdf"></label>`, 'Import recipe', 'recipe-import');
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
    const shortageNames = new Set((plan.shortages || []).map(s => String(s.name || '').trim().toLowerCase()));
    const ingredients = (recipe.ingredients || []).map(ingredient => {
      const name = String(ingredient.name || '').trim();
      const missing = shortageNames.has(name.toLowerCase());
      const amount = `${escapeHtml(ingredient.quantity)} ${escapeHtml(ingredient.unit)}`;
      return `<li class="recipe-ingredient ${missing ? 'missing' : 'available'}"><span>${missing ? 'Missing' : 'On hand'}</span> ${escapeHtml(name)} · ${amount}</li>`;
    }).join('');
    const shortages = (plan.shortages || []).map(s => `<li>${escapeHtml(s.name)}: need ${escapeHtml(s.missing)} ${escapeHtml(s.unit)} more${s.optional ? ' (optional)' : ''}</li>`).join('');
    const queue = plan.can_make ? '' : `<button type="button" class="inventory-primary" data-action="queue-missing" data-recipe-id="${escapeHtml(id)}">Add required missing items to grocery list</button>`;
    const shortageBlock = plan.can_make ? '' : `<h4>Missing stock</h4><ul>${shortages}</ul>`;
    modalForm(recipe.name, `<p>${escapeHtml(recipe.instructions || 'No instructions saved.')}</p><h4>Ingredient check</h4><ul class="recipe-ingredient-list">${ingredients || '<li>No ingredients saved.</li>'}</ul>${shortageBlock}${queue}`, 'Close', 'view', id);
    const form = document.querySelector('.inventory-dialog[data-kind="view"]');
    const closeButton = form?.querySelector('[type=submit]');
    if (closeButton) {
      closeButton.type = 'button';
      closeButton.dataset.action = 'dismiss-dialog';
    }
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
  else if (tab === 'fridge') { editingDraft = null; loadStorageArea('fridge'); }
  else if (tab === 'grocery') { editingDraft = null; loadGrocery(); }
  else if (tab === 'recipes') { editingDraft = null; loadRecipes(); }
  else document.getElementById('inventory-content').innerHTML = intakeForm();
}

export function openPanel() {
  if (open) return;
  open = true;
  windowEl = openWindow({id:'inventory-window', view:'inventory', title:'Pantry & grocery', content:''});
  windowEl.querySelector('.hades-window-body').appendChild(shell());
  windowEl.querySelector('[data-win="close"]')?.addEventListener('click', () => {
    open = false;
    editingDraft = null;
    requestGeneration++;
    document.querySelectorAll('.inventory-dialog-backdrop').forEach(el => el.remove());
    document.body.classList.remove('inventory-view');
    document.getElementById('tool-inventory-btn')?.classList.remove('active');
  }, {once: true});
  document.body.classList.add('inventory-view');
  document.getElementById('tool-inventory-btn')?.classList.add('active');
  renderTab();
}

export function closePanel() {
  open = false;
  editingDraft = null;
  requestGeneration++;
  closeWorkspaceWindow('inventory-window');
  windowEl = null;
  document.querySelectorAll('.inventory-dialog-backdrop').forEach(el => el.remove());
  document.body.classList.remove('inventory-view');
  document.getElementById('tool-inventory-btn')?.classList.remove('active');
}

export function togglePanel() { open ? closePanel() : openPanel(); }

export default {openPanel, closePanel, togglePanel};
