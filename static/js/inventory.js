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
let recipeQuery = '';
let recipeFilter = 'all';
let recipeCatalog = [];
let requestGeneration = 0;
let editingDraft = null;
let windowEl = null;

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[c]);
}

function displayQuantity(value) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return escapeHtml(value);
  return escapeHtml(amount.toLocaleString(undefined, {
    maximumFractionDigits: 3,
    useGrouping: false,
  }));
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
      <button data-tab="stock" class="active" aria-label="Pantry, on hand">Pantry</button>
      <button data-tab="fridge">Fridge</button>
      <button data-tab="freezer">Freezer</button>
      <button data-tab="grocery" aria-label="Grocery list, items to buy">Grocery</button>
      <button data-tab="recipes">Recipes</button>
      <button data-tab="sharing" aria-label="Household sharing">Sharing</button>
      <button data-tab="intake" aria-label="Add from text or media">Add</button>
    </nav>
    <main id="inventory-content" class="inventory-content"></main>`;
  node.addEventListener('click', onClick);
  node.addEventListener('submit', onSubmit);
  node.addEventListener('input', onInput);
  node.addEventListener('change', onChange);
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
  const areaHeadings = {pantry: 'Pantry · On hand', fridge: 'Fridge · On hand', freezer: 'Freezer · On hand'};
  const areaHeading = areaHeadings[area] || `${area[0].toUpperCase()+area.slice(1)} · On hand`;
  content.innerHTML = `<div class="inventory-toolbar"><div><h3>${areaHeading}</h3><p>Owned stock you already have. The grocery queue is separate and contains items to buy.</p></div><button class="inventory-primary" data-action="new-item">+ Add item</button></div><div id="inventory-storage-list">${loading()}</div>`;
  try {
    const {items = []} = await api(`/api/inventory/items?list_name=${encodeURIComponent(area)}`);
    if (generation !== requestGeneration) return;
    document.getElementById('inventory-storage-list').innerHTML = items.length ? items.map(item => `<article class="inventory-card" data-item-id="${escapeHtml(item.id)}"><div class="inventory-card-main"><span class="inventory-domain">${escapeHtml(item.storage_area || area)}</span><h3>${escapeHtml(item.name)}</h3><p>${escapeHtml(item.category || 'Household item')} · ${escapeHtml(item.default_unit || 'each')}</p></div><div class="inventory-card-actions"><button data-action="stock-add">Add stock</button><button data-action="stock-consume" ${Number(item.stock_quantity || 0) <= 0 ? 'disabled' : ''}>Use</button><button data-action="edit-item">Edit</button><button data-action="move-to-grocery">Add to grocery</button><button data-action="archive-item">Archive</button></div></article>`).join('') : `<div class="inventory-state">Your ${area} list is empty.</div>`;
  } catch (error) { showInlineError(error); }
}

async function loadSharing() {
  const content = document.getElementById('inventory-content');
  if (!content) return;
  content.innerHTML = `<div class="inventory-toolbar"><div><h3>Household sharing</h3><p>Share the kitchen inventory explicitly with household members. Shared access is read-only until member editing is deliberately enabled.</p></div></div><div id="inventory-sharing-list">${loading()}</div>`;
  try {
    const {households = []} = await api('/api/inventory/sharing');
    const list = document.getElementById('inventory-sharing-list');
    if (!households.length) {
      list.innerHTML = '<div class="inventory-state"><p>You are not in a household yet.</p><button class="inventory-primary" data-action="new-household">Create household</button></div>';
      return;
    }
    list.innerHTML = households.map(household => {
      const members = Array.isArray(household.members) ? household.members : [];
      const memberList = members.length
        ? `<ul class="inventory-sharing-members">${members.map(member => `<li><strong>${escapeHtml(member.user_id || 'Household member')}</strong><span>${escapeHtml(member.role || 'member')}</span>${household.can_manage && member.role !== 'owner' ? ` <button class="inventory-link-button" data-action="remove-member" data-household-id="${escapeHtml(household.household_id)}" data-user-id="${escapeHtml(member.user_id)}">Remove</button>` : ''}</li>`).join('')}</ul>`
        : '<p class="inventory-sharing-empty-members">No members are configured yet.</p>';
      const resources = [
        ['kitchen_inventory', 'Kitchen stock and Grocery', 'Members can see shared pantry, fridge, freezer, and to-buy items.', true],
        ['recipes', 'Recipes', 'Members can see saved recipes.', false],
      ];
      const controls = resources.map(([resource, label, description, supportsMutation]) => {
        const policy = household.resources?.[resource] || {};
        const enabled = Boolean(policy.enabled);
        const editable = Boolean(policy.allow_member_mutation);
        const accessDescription = enabled
          ? (editable ? `${description} Members can also edit shared stock.` : `${description} Members have read-only access.`)
          : 'Private to each member.';
        const status = enabled ? (editable ? 'Shared with edits' : 'Shared read-only') : 'Private';
        const control = household.can_manage
          ? `<button class="inventory-primary" data-action="toggle-sharing" data-resource="${resource}" data-household-id="${escapeHtml(household.household_id)}" data-enabled="${enabled ? 'true' : 'false'}">${enabled ? 'Stop sharing' : `Share ${label.toLowerCase()}`}</button>${supportsMutation && enabled ? `<button data-action="toggle-sharing-mutation" data-resource="${resource}" data-household-id="${escapeHtml(household.household_id)}" data-enabled="true" data-mutation="${editable ? 'true' : 'false'}">${editable ? 'Make members read-only' : 'Allow member edits'}</button>` : ''}`
          : '';
        return `<div class="inventory-sharing-row"><div class="inventory-sharing-copy"><div class="inventory-sharing-title"><strong>${label}</strong><span class="inventory-sharing-state ${enabled ? 'enabled' : 'private'}">${status}</span></div><p>${accessDescription}</p></div><div class="inventory-sharing-actions">${control}</div></div>`;
      }).join('');
      const addMember = household.can_manage ? `<button data-action="add-member" data-household-id="${escapeHtml(household.household_id)}">Add member</button>` : '';
      return `<article class="inventory-card"><div class="inventory-card-main"><span class="inventory-domain">${escapeHtml(household.role)}</span><h3>${escapeHtml(household.household_name)}</h3><div class="inventory-sharing-member-summary"><strong>Household members</strong>${memberList}</div><div class="inventory-card-actions">${addMember}</div>${controls}</div></article>`;
    }).join('');
  } catch (error) { showInlineError(error); }
}

function renderRecipesScaffold() {
  return `<section class="recipe-hero"><div><span class="recipe-eyebrow">COOKBOOK</span><h3>What can we cook?</h3><p>Plan from what is on hand. Missing ingredients can be queued for the next shop.</p></div><div class="recipe-hero-actions"><button data-action="import-recipe">Import recipe</button><button class="inventory-primary" data-action="new-recipe">+ New recipe</button></div></section><div class="recipe-guidance"><span class="recipe-guidance-mark" aria-hidden="true">✦</span><span><strong>Pantry is what you have.</strong> <b>Grocery is what you need to buy.</b> Cooking deducts owned stock only after you confirm.</span></div><div class="recipe-library-tools"><label class="recipe-search"><span class="sr-only">Search recipes</span><input id="recipe-search" type="search" maxlength="200" value="${escapeHtml(recipeQuery)}" placeholder="Search recipes or ingredients" aria-label="Search recipes or ingredients"></label><div class="recipe-filters" role="group" aria-label="Recipe filters">${[['all','All recipes'],['ready','Ready now'],['missing','Needs shopping']].map(([value, label]) => `<button type="button" data-recipe-filter="${value}" class="${recipeFilter === value ? 'active' : ''}">${label}</button>`).join('')}</div></div><div id="inventory-recipe-summary" class="recipe-summary" aria-live="polite"></div><div id="inventory-recipe-list" class="recipe-card-grid">${loading()}</div>`;
}

function renderRecipeCatalog() {
  const summary = document.getElementById('inventory-recipe-summary');
  const list = document.getElementById('inventory-recipe-list');
  if (!summary || !list) return;
  const readyCount = recipeCatalog.filter(entry => entry.plan.can_make).length;
  const missingCount = recipeCatalog.reduce((total, entry) => total + (entry.plan.shortages || []).length, 0);
  summary.innerHTML = `<div class="recipe-stat"><strong>${recipeCatalog.length}</strong><span>Saved</span></div><div class="recipe-stat recipe-stat-ready"><strong>${readyCount}</strong><span>Ready now</span></div><div class="recipe-stat recipe-stat-missing"><strong>${missingCount}</strong><span>To buy</span></div>`;
  const needle = recipeQuery.trim().toLowerCase();
  const filtered = recipeCatalog.filter(({recipe, plan}) => {
    if (recipeFilter === 'ready' && !plan.can_make) return false;
    if (recipeFilter === 'missing' && plan.can_make) return false;
    if (!needle) return true;
    const haystack = [recipe.name, ...(recipe.tags || []), ...(recipe.ingredients || []).map(ingredient => ingredient.name)].join(' ').toLowerCase();
    return haystack.includes(needle);
  });
  if (!recipeCatalog.length) {
    list.innerHTML = '<div class="inventory-state recipe-empty-state"><strong>Your cookbook is empty.</strong><p>Save a recipe or import one, then Hades will compare it with Pantry stock.</p><button class="inventory-primary" data-action="new-recipe">Create your first recipe</button></div>';
    return;
  }
  if (!filtered.length) {
    list.innerHTML = `<div class="inventory-state recipe-empty-state"><strong>No recipes match.</strong><p>Try another search or clear the current filter.</p><button data-action="clear-recipe-search">Show all recipes</button></div>`;
    return;
  }
  list.innerHTML = filtered.map(({recipe, plan}) => {
    const ingredients = recipe.ingredients || [];
    const shortageNames = new Set((plan.shortages || []).map(shortage => String(shortage.name || '').toLowerCase()));
    const preview = ingredients.slice(0, 5).map(ingredient => {
      const name = String(ingredient.name || '').trim();
      const missing = shortageNames.has(name.toLowerCase());
      const amount = `${displayQuantity(ingredient.quantity)} ${escapeHtml(ingredient.unit || '')}`.trim();
      return `<li class="${missing ? 'is-missing' : 'is-ready'}"><span class="recipe-dot" aria-label="${missing ? 'Missing' : 'On hand'}">${missing ? '!' : '✓'}</span><span class="recipe-ingredient-name">${escapeHtml(name)}</span><small>${amount}</small></li>`;
    }).join('');
    const more = ingredients.length > 5 ? `<span class="recipe-more">+${ingredients.length - 5} more</span>` : '';
    const shortages = (plan.shortages || []).slice(0, 3).map(shortage => escapeHtml(shortage.name)).join(', ');
    const shortageDetails = (plan.shortages || []).slice(0, 3).map(shortage => `${escapeHtml(shortage.name)} (${displayQuantity(shortage.missing)} ${escapeHtml(shortage.unit || '')})`).join(', ');
    const shortageMore = (plan.shortages || []).length > 3 ? ` +${(plan.shortages || []).length - 3} more` : '';
    const tags = (recipe.tags || []).slice(0, 4).map(tag => `<span>${escapeHtml(tag)}</span>`).join('');
    const status = plan.can_make ? 'Ready to make' : `${(plan.shortages || []).length} missing`;
    return `<article class="inventory-card inventory-recipe-card" data-recipe-id="${escapeHtml(recipe.id)}">
      <header class="recipe-card-header"><div><span class="recipe-eyebrow">RECIPE</span><h3>${escapeHtml(recipe.name)}</h3></div><span class="inventory-ready ${plan.can_make ? 'yes' : 'no'}"><i aria-hidden="true"></i>${status}</span></header>
      <p class="recipe-card-meta"><span>${escapeHtml(recipe.servings)} servings</span><span>${ingredients.length} ingredient${ingredients.length === 1 ? '' : 's'}</span></p>
      ${tags ? `<div class="recipe-tags" aria-label="Recipe tags">${tags}</div>` : ''}
      <div class="recipe-card-body"><section class="recipe-card-ingredients"><h4>Ingredient check</h4><ul class="recipe-preview">${preview || '<li class="recipe-empty-ingredients">No ingredients saved yet.</li>'}</ul>${more}</section><aside class="recipe-card-next"><span class="recipe-eyebrow">NEXT STEP</span>${plan.can_make ? '<strong>Everything is on hand.</strong><p>Use the saved recipe when you are ready.</p>' : `<strong>Shop for ${shortageDetails || shortages || 'the missing ingredients'}${shortageMore}</strong><p>Queue only these items; pantry stock stays unchanged.</p>`}</aside></div>
      <div class="recipe-card-actions"><button data-action="recipe-details">View recipe</button>${plan.can_make ? `<button class="inventory-primary" data-action="cook" data-servings="${escapeHtml(recipe.servings)}">Cook now</button>` : `<button class="inventory-primary" data-action="queue-missing" data-recipe-id="${escapeHtml(recipe.id)}">Add missing to Grocery</button>`}</div>
    </article>`;
  }).join('');
}

async function loadRecipes() {
  const content = document.getElementById('inventory-content');
  if (!content) return;
  content.innerHTML = renderRecipesScaffold();
  try {
    const {recipes = []} = await api('/api/recipes');
    const plans = await Promise.all(recipes.map(recipe => api(`/api/recipes/${encodeURIComponent(recipe.id)}/can-make`)));
    recipeCatalog = recipes.map((recipe, index) => ({recipe, plan: plans[index] || {}}));
    renderRecipeCatalog();
  } catch (error) { showInlineError(error); }
}

function intakeForm() {
  return `<form id="inventory-intake-form" class="inventory-form">
    <div class="inventory-callout"><strong>Review required.</strong> Text, voice transcripts, and receipt photos are untrusted. Nothing changes until the structured draft is ready and you explicitly confirm it.</div>
    <label>Source <select name="source_type"><option value="natural_language">Natural language</option><option value="voice">Voice transcript</option><option value="photo">Receipt or pantry photo</option><option value="telegram">Telegram</option></select></label>
    <label class="inventory-wide">What did you add or use?<textarea name="source_text" maxlength="4000" placeholder="For example: Added 2 kg of rice to the pantry"></textarea></label>
    <label class="inventory-wide" data-photo-input hidden>Photo <input name="photo" type="file" accept="image/*" capture="environment"><small class="inventory-muted">Upload a receipt or pantry photo. Hades will prepare a draft for review; it will not add stock automatically.</small></label>
    <label class="inventory-wide">Existing server upload ID <input name="attachment_ids" autocomplete="off" placeholder="Optional advanced attachment ID"></label>
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
  const cancel = kind === 'view' ? '' : '<button type="button" data-action="dismiss-dialog">Cancel</button>';
  modal.innerHTML = `<form class="inventory-dialog" data-kind="${kind}" data-id="${escapeHtml(id)}"><h3>${escapeHtml(title)}</h3>${body}<div class="inventory-dialog-actions">${cancel}<button class="inventory-primary" type="submit">${escapeHtml(submitLabel)}</button></div></form>`;
  document.body.appendChild(modal);
  modal.addEventListener('click', onClick);
  modal.addEventListener('submit', onSubmit);
  modal.querySelector('input')?.focus();
}

function field(label, name, attrs = '') { return `<label>${label}<input name="${name}" ${attrs}></label>`; }

function unitOptions(selected) {
  const value = String(selected || '').trim();
  const units = value && !UNITS.includes(value) ? [value, ...UNITS] : UNITS;
  return units.map(unit => `<option value="${escapeHtml(unit)}"${unit === value ? ' selected' : ''}>${escapeHtml(unit)}</option>`).join('');
}

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
      if (data.source_type === 'photo') {
        const photo = form.querySelector('input[name="photo"]')?.files?.[0];
        if (!photo && !String(data.attachment_ids || '').trim()) throw new Error('Choose a receipt or pantry photo first.');
        let attachmentIds = opaqueAttachmentIds(data.attachment_ids);
        if (photo) {
          const upload = new FormData();
          upload.append('files', photo);
          const uploaded = await api('/api/upload', {method:'POST', body:upload});
          const id = uploaded.files?.[0]?.id;
          if (!id) throw new Error('The photo upload did not return an attachment.');
          attachmentIds = [id];
        }
        const extracted = await api('/api/inventory/intake/extract', {method:'POST', body:JSON.stringify({
          source_type: 'photo', source_text: data.source_text || null,
          attachment_ids: attachmentIds, idempotency_key: makeIdempotencyKey('intake-photo'),
        })});
        editingDraft = null;
        renderDraft(extracted);
        return;
      }
      if (editingDraft) {
        renderDraft(await api(`/api/inventory/intake/drafts/${encodeURIComponent(editingDraft.draft_id)}`, {method:'PUT', body:JSON.stringify({expected_revision:editingDraft.revision, source_text:data.source_text, candidates:[candidate]})}));
      } else {
        const payload = {source_type: data.source_type, source_text: data.source_text, attachment_ids: opaqueAttachmentIds(data.attachment_ids), idempotency_key: makeIdempotencyKey('intake'), candidates: [candidate]};
        renderDraft(await api('/api/inventory/intake/drafts', {method:'POST', body:JSON.stringify(payload)}));
      }
      return;
    }
    const kind = form.dataset.kind;
    if (kind === 'household') await api('/api/finance/households', {method:'POST', body:JSON.stringify({name:data.name})});
    if (kind === 'add-member') await api(`/api/finance/households/${encodeURIComponent(form.dataset.id)}/members`, {method:'POST', body:JSON.stringify({user_id:data.user_id})});
    if (kind === 'item' || kind === 'grocery') await api('/api/inventory/items', {method:'POST', body:JSON.stringify({name:data.name, domain:data.domain || 'kitchen', item_kind:data.domain === 'it' ? 'asset' : 'ingredient', default_unit:data.unit || 'each', category:data.category, shopping_list:kind === 'grocery' || data.shopping_list === 'on', storage_area:data.storage_area || null})});
    if (kind === 'edit-item') await api(`/api/inventory/items/${encodeURIComponent(form.dataset.id)}`, {method:'PATCH', body:JSON.stringify({name:data.name, category:data.category, default_unit:data.unit, shopping_list:data.shopping_list === 'on', storage_area:data.storage_area || null})});
    if (kind === 'asset') await api(`/api/inventory/assets/${encodeURIComponent(form.dataset.id)}`, {method:'PUT', body:JSON.stringify(assetPayload(data))});
    if (kind === 'stock') await api(`/api/inventory/items/${encodeURIComponent(form.dataset.id)}/stock`, {method:'POST', body:JSON.stringify({quantity:data.quantity, unit:data.unit, idempotency_key:makeIdempotencyKey('stock')})});
    if (kind === 'stock' && tab === 'grocery') await api(`/api/inventory/items/${encodeURIComponent(form.dataset.id)}`, {method:'PATCH', body:JSON.stringify({shopping_list:false})});
    if (kind === 'consume') await api(`/api/inventory/items/${encodeURIComponent(form.dataset.id)}/consume`, {method:'POST', body:JSON.stringify({quantity:data.quantity, unit:data.unit, reason:data.reason, idempotency_key:makeIdempotencyKey('consume')})});
    if (kind === 'recipe') {
      const ingredients = data.ingredients.split('\n').map(line => line.trim()).filter(Boolean).map(line => { const match = line.match(/^(.+?)\s*\|\s*([0-9.]+)\s*\|\s*([\w-]+)$/); if (!match) throw new Error('Use one ingredient per line: name | quantity | unit'); return {name:match[1].trim(), quantity:match[2], unit:match[3]}; });
      const tags = String(data.tags || '').split(',').map(tag => tag.trim()).filter(Boolean).slice(0, 12);
      await api('/api/recipes', {method:'POST', body:JSON.stringify({name:data.name, servings:data.servings, ingredients, instructions:data.instructions, source_url:data.source_url || null, tags})});
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
    if (kind === 'household' || kind === 'add-member') {
      await loadSharing();
    } else if (kind === 'recipe' || kind === 'recipe-import') {
      await loadRecipes();
      if (importedRecipeId) await showRecipe(importedRecipeId);
    } else if (tab === 'grocery') await loadGrocery();
    else if (tab === 'fridge' || tab === 'freezer') await loadStorageArea(tab);
    else await loadStock();
  } catch (error) { uiModule.showError?.(error.message); }
  finally { if (submit) submit.disabled = false; }
}

function updateIntakeSourceVisibility(form) {
  const photoInput = form?.querySelector('[data-photo-input]');
  if (!photoInput) return;
  const isPhoto = form.elements.source_type?.value === 'photo';
  photoInput.hidden = !isPhoto;
  const file = form.elements.photo;
  if (!isPhoto && file) file.value = '';
  // Photo extraction supplies the candidate fields after analysis. Manual
  // intake still requires them before the draft can be created.
  ['name', 'quantity'].forEach(name => {
    const field = form.elements[name];
    if (field) field.required = !isPhoto;
  });
}

async function onClick(event) {
  const button = event.target.closest('button');
  if (!button) return;
  if (button.matches('[data-close]')) return closePanel();
  if (button.dataset.tab) { tab = button.dataset.tab; renderTab(); return; }
  if (button.dataset.recipeFilter) {
    recipeFilter = button.dataset.recipeFilter;
    renderTab();
    return;
  }
  if (button.dataset.domain) { domain = button.dataset.domain; loadStock(); return; }
  const action = button.dataset.action;
  if (action === 'retry') return renderTab();
  if (action === 'clear-recipe-search') {
    recipeQuery = '';
    recipeFilter = 'all';
    renderTab();
    return;
  }
  if (action === 'dismiss-dialog') return button.closest('.inventory-dialog-backdrop')?.remove();
  if (action === 'recipe-plan') {
    const form = button.closest('.inventory-dialog[data-kind="view"]');
    return showRecipe(form?.dataset.id || button.dataset.recipeId, form?.querySelector('[name="recipe-servings"]')?.value);
  }
  if (action === 'toggle-sharing') {
    button.disabled = true;
    try {
      const enabled = button.dataset.enabled !== 'true';
      await api(`/api/inventory/sharing/${encodeURIComponent(button.dataset.householdId)}`, {
        method: 'PUT', body: JSON.stringify({resource: button.dataset.resource, enabled}),
      });
      uiModule.showToast?.(enabled ? 'Household sharing enabled' : 'Household sharing disabled');
      await loadSharing();
    } catch (error) { uiModule.showError?.(error.message); button.disabled = false; }
    return;
  }
  if (action === 'new-household') return modalForm('Create household', `${field('Household name','name','required maxlength="200"')}`, 'Create', 'household');
  if (action === 'add-member') return modalForm('Add household member', `${field('Hades username','user_id','required maxlength="255"')}<p class="inventory-muted">The person must already have a Hades account. Adding them here grants only the resources you explicitly share below.</p>`, 'Add member', 'add-member', button.dataset.householdId);
  if (action === 'remove-member') {
    if (!window.confirm(`Remove ${button.dataset.userId} from this household? Their shared inventory and recipe access will be revoked.`)) return;
    button.disabled = true;
    try {
      await api(`/api/finance/households/${encodeURIComponent(button.dataset.householdId)}/members/${encodeURIComponent(button.dataset.userId)}`, {method:'DELETE'});
      uiModule.showToast?.('Household access revoked');
      await loadSharing();
    } catch (error) { uiModule.showError?.(error.message); button.disabled = false; }
    return;
  }
  if (action === 'toggle-sharing-mutation') {
    button.disabled = true;
    try {
      const enabled = button.dataset.mutation !== 'true';
      await api(`/api/inventory/sharing/${encodeURIComponent(button.dataset.householdId)}`, {
        method: 'PUT', body: JSON.stringify({resource: button.dataset.resource, enabled: true, allow_member_mutation: enabled}),
      });
      uiModule.showToast?.(enabled ? 'Member edits enabled' : 'Member edits disabled');
      await loadSharing();
    } catch (error) { uiModule.showError?.(error.message); button.disabled = false; }
    return;
  }
  if (action === 'queue-missing') {
    button.disabled = true;
    try {
      const servings = button.dataset.servingCount;
      const result = await api(`/api/recipes/${encodeURIComponent(button.dataset.recipeId)}/queue-missing`, {method:'POST', body:JSON.stringify(servings ? {servings} : {})});
      uiModule.showToast?.(`${result.count || 0} required item${result.count === 1 ? '' : 's'} added to grocery list`);
      button.textContent = 'Queued in Grocery';
      button.classList.remove('inventory-primary');
      button.disabled = true;
    } catch (error) { uiModule.showError?.(error.message); button.disabled = false; }
    return;
  }
  if (action === 'cook' && button.closest('.inventory-dialog[data-kind="view"]')) {
    return cookRecipe(button.closest('.inventory-dialog').dataset.id, button, button.dataset.servings);
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
  if (action === 'grocery-bought') {
    const {item} = await api(`/api/inventory/items/${encodeURIComponent(card.dataset.itemId)}`);
    return modalForm('Mark as bought', `${field('Quantity','quantity','required inputmode="decimal"')}<label>Unit<select name="unit">${unitOptions(item.default_unit)}</select></label>`, 'Add stock', 'stock', card.dataset.itemId);
  }
  if (action === 'asset-details') {
    try {
      const {asset = {}} = await api(`/api/inventory/items/${encodeURIComponent(card.dataset.itemId)}`);
      const body = `${field('Serial number','serial_number',`maxlength="160" value="${escapeHtml(asset?.serial_number || '')}"`)}${field('Asset tag','asset_tag',`maxlength="160" value="${escapeHtml(asset?.asset_tag || '')}"`)}<label>Status<select name="status">${['in_stock','deployed','repair','retired','disposed','lost'].map(value=>`<option value="${value}" ${asset?.status === value ? 'selected' : ''}>${value.replaceAll('_',' ')}</option>`).join('')}</select></label>${field('Condition','condition',`maxlength="80" value="${escapeHtml(asset?.condition || '')}"`)}${field('Hostname','hostname',`maxlength="253" value="${escapeHtml(asset?.hostname || '')}"`)}${field('Assigned to','assigned_to',`maxlength="255" value="${escapeHtml(asset?.assigned_to || '')}"`)}${field('Parent asset ID','parent_asset_id',`maxlength="255" value="${escapeHtml(asset?.parent_asset_id || '')}"`)}${field('MAC addresses (comma separated)','mac_addresses',`value="${escapeHtml((asset?.mac_addresses || []).join(', '))}"`)}${field('IP addresses (comma separated)','ip_addresses',`value="${escapeHtml((asset?.ip_addresses || []).join(', '))}"`)}<label>Specifications (JSON object)<textarea name="specs">${escapeHtml(JSON.stringify(asset?.specs || {}, null, 2))}</textarea></label>`;
      return modalForm('Hardware asset details', body, 'Save asset', 'asset', card.dataset.itemId);
    } catch (error) { uiModule.showError?.(error.message); return; }
  }
  if (action === 'stock-add' || action === 'stock-consume') {
    const {item} = await api(`/api/inventory/items/${encodeURIComponent(card.dataset.itemId)}`);
    return modalForm(action === 'stock-add' ? 'Add stock' : 'Use stock', `${field('Quantity','quantity','required inputmode="decimal"')}<label>Unit<select name="unit">${unitOptions(item.default_unit)}</select></label>${action === 'stock-consume' ? field('Reason','reason','maxlength="200"') : ''}`, action === 'stock-add' ? 'Add' : 'Use', action === 'stock-add' ? 'stock' : 'consume', card.dataset.itemId);
  }
  if (action === 'new-recipe') return modalForm('New recipe', `${field('Name','name','required maxlength="200"')}${field('Servings','servings','required inputmode="decimal"')}<label>Ingredients <small>one per line: name | quantity | unit</small><textarea name="ingredients" placeholder="spaghetti | 400 | g\ntomato sauce | 1 | jar" required></textarea></label>${field('Tags (optional)','tags','maxlength="400" placeholder="weeknight, freezer"')}${field('Source URL (optional)','source_url','type="url" maxlength="4000"')}<label>Instructions<textarea name="instructions"></textarea></label>`, 'Save recipe', 'recipe');
  if (action === 'import-recipe') return modalForm('Import recipe', `<p class="inventory-muted">Paste a recipe, provide a public URL, or choose a PDF. Import only saves the recipe; stock and groceries change only when you explicitly queue missing items.</p>${field('Recipe name (optional)','name','maxlength="200"')}${field('Public recipe URL (optional)','url','type="url" maxlength="4000"')}<label>Paste recipe text<textarea name="source_text" maxlength="24000" placeholder="Ingredients:\n2 cups tomato sauce\n400 g spaghetti\n\nDirections:\n..."></textarea></label><label>PDF recipe (optional)<input type="file" name="pdf" accept="application/pdf,.pdf"></label>`, 'Import recipe', 'recipe-import');
  if (action === 'recipe-details') return showRecipe(recipeCard.dataset.recipeId);
  if (action === 'cook') return cookRecipe(recipeCard.dataset.recipeId, button, button.dataset.servings);
  if (action === 'confirm-draft') {
    const draft = button.closest('[data-draft-id]');
    return confirmDraft(draft.dataset.draftId, draft.dataset.revision, button);
  }
}

let searchTimer;
function onInput(event) {
  if (event.target.id === 'recipe-search') {
    recipeQuery = event.target.value;
    renderRecipeCatalog();
    return;
  }
  if (event.target.id !== 'inventory-search') return;
  query = event.target.value;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadStock, 250);
}

function onChange(event) {
  if (event.target.matches('#inventory-intake-form select[name="source_type"]')) {
    updateIntakeSourceVisibility(event.target.form);
  }
}

async function showRecipe(id, requestedServings = '') {
  try {
    document.querySelector('.inventory-dialog-backdrop .inventory-dialog[data-kind="view"]')?.closest('.inventory-dialog-backdrop')?.remove();
    const {recipe} = await api(`/api/recipes/${encodeURIComponent(id)}`);
    const baseServings = Number(recipe.servings);
    const parsedServings = Number(requestedServings);
    const servings = Number.isFinite(parsedServings) && parsedServings > 0 ? parsedServings : baseServings;
    const servingsText = displayQuantity(servings);
    const plan = await api(`/api/recipes/${encodeURIComponent(id)}/can-make?servings=${encodeURIComponent(servingsText)}`);
    const shortageNames = new Set((plan.shortages || []).map(s => String(s.name || '').trim().toLowerCase()));
    const availableCount = (recipe.ingredients || []).filter(ingredient => !shortageNames.has(String(ingredient.name || '').trim().toLowerCase())).length;
    const scale = Number.isFinite(baseServings) && baseServings > 0 ? servings / baseServings : 1;
    const ingredients = (recipe.ingredients || []).map(ingredient => {
      const name = String(ingredient.name || '').trim();
      const missing = shortageNames.has(name.toLowerCase());
      const quantity = Number(ingredient.quantity);
      const amount = `${displayQuantity(Number.isFinite(quantity) ? quantity * scale : ingredient.quantity)} ${escapeHtml(ingredient.unit)}`;
      return `<li class="recipe-ingredient ${missing ? 'missing' : 'available'}"><span class="recipe-detail-state">${missing ? 'Missing' : 'On hand'}</span><span class="recipe-detail-name">${escapeHtml(name)}</span><strong>${amount}</strong></li>`;
    }).join('');
    const shortages = (plan.shortages || []).map(s => `<li>${escapeHtml(s.name)}: need ${displayQuantity(s.missing)} ${escapeHtml(s.unit)} more${s.optional ? ' (optional)' : ''}</li>`).join('');
    const queue = plan.can_make ? '' : `<button type="button" class="inventory-primary" data-action="queue-missing" data-recipe-id="${escapeHtml(id)}" data-serving-count="${escapeHtml(servingsText)}">Add required missing items to grocery list</button>`;
    const shortageBlock = plan.can_make ? '' : `<section class="recipe-detail-shortage"><div><h4>Ingredients to buy</h4><p>${(plan.shortages || []).length} ingredient${(plan.shortages || []).length === 1 ? '' : 's'} still needed. Queue them without changing pantry stock.</p></div><ul>${shortages}</ul>${queue}</section>`;
    const status = plan.can_make ? '<span class="inventory-ready yes"><i aria-hidden="true"></i>Ready to cook</span>' : `<span class="inventory-ready no"><i aria-hidden="true"></i>${(plan.shortages || []).length} missing</span>`;
    const cook = plan.can_make ? `<button type="button" class="inventory-primary" data-action="cook" data-servings="${escapeHtml(servingsText)}">Cook ${escapeHtml(servingsText)} servings</button>` : '';
    const intro = `<div class="recipe-detail-intro"><div><span class="recipe-eyebrow">${escapeHtml(servingsText)} servings · ${(recipe.ingredients || []).length} ingredients</span>${status}</div><div class="recipe-serving-control"><label for="recipe-serving-count">Make for</label><input id="recipe-serving-count" name="recipe-servings" type="number" min="0.1" step="0.1" value="${escapeHtml(servingsText)}"><span>people</span><button type="button" data-action="recipe-plan" data-recipe-id="${escapeHtml(id)}">Update check</button><small>Base recipe: ${escapeHtml(recipe.servings)} servings</small></div><p>${escapeHtml(recipe.instructions || 'No instructions saved yet.')}</p></div>`;
    const checkLabel = plan.can_make ? 'Everything is on hand.' : `${availableCount} of ${(recipe.ingredients || []).length} ingredients on hand.`;
    modalForm(recipe.name, `${intro}<section class="recipe-detail-check"><div class="recipe-detail-section-heading"><h4>Ingredient check</h4><span>${checkLabel}</span></div><ul class="recipe-ingredient-list">${ingredients || '<li>No ingredients saved.</li>'}</ul></section>${shortageBlock}${cook ? `<div class="recipe-detail-actions">${cook}</div>` : ''}`, 'Close', 'view', id);
    const form = document.querySelector('.inventory-dialog[data-kind="view"]');
    const closeButton = form?.querySelector('[type=submit]');
    if (closeButton) {
      closeButton.type = 'button';
      closeButton.dataset.action = 'dismiss-dialog';
    }
  } catch (error) { uiModule.showError?.(error.message); }
}

async function cookRecipe(id, button, servings = '') {
  if (!window.confirm('Cook this recipe and deduct its ingredients from stock?')) return;
  button.disabled = true;
  try { await api(`/api/recipes/${encodeURIComponent(id)}/cook`, {method:'POST', body:JSON.stringify({servings: servings || undefined, idempotency_key:makeIdempotencyKey('cook')})}); uiModule.showToast?.('Recipe cooked and stock updated'); await loadRecipes(); }
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
  else if (tab === 'freezer') { editingDraft = null; loadStorageArea('freezer'); }
  else if (tab === 'grocery') { editingDraft = null; loadGrocery(); }
  else if (tab === 'recipes') { editingDraft = null; loadRecipes(); }
  else if (tab === 'sharing') { editingDraft = null; loadSharing(); }
  else {
    document.getElementById('inventory-content').innerHTML = intakeForm();
    updateIntakeSourceVisibility(document.getElementById('inventory-intake-form'));
  }
}

export function openPanel() {
  if (open) return;
  open = true;
  const compact = window.matchMedia('(max-width: 768px)').matches;
  const initialRect = compact ? null : {
    left: Math.max(24, Math.round((window.innerWidth - Math.min(980, Math.max(620, window.innerWidth - 300))) / 2)),
    top: Math.max(24, Math.round((window.innerHeight - Math.min(760, Math.max(480, window.innerHeight - 72))) / 2)),
    width: Math.min(980, Math.max(620, window.innerWidth - 300)),
    height: Math.min(760, Math.max(480, window.innerHeight - 72)),
  };
  windowEl = openWindow({id:'inventory-window', view:'inventory', title:'Pantry & grocery', content:'', initialRect});
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
