/* Shared Hades product grammar. Modules provide data; these helpers provide
 * consistent headers, states, badges, intake framing, and provenance language.
 */
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

export const ICONS = Object.freeze({
  hades: '<path d="m12 3 1.6 5.4L19 10l-5.4 1.6L12 17l-1.6-5.4L5 10l5.4-1.6Z"/>',
  chat: '<path d="M4 5h16v11H8l-4 4Z"/>',
  attention: '<path d="M12 4v8"/><circle cx="12" cy="17" r="1"/>',
  life: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="2"/>',
  work: '<rect x="4" y="5" width="16" height="14" rx="2"/><path d="M8 9h8M8 13h5"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 10h18"/>',
  email: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/>',
  contacts: '<circle cx="12" cy="8" r="3"/><path d="M5 20a7 7 0 0 1 14 0"/>',
  telegram: '<path d="m4 11 16-7-4 16-5-5-4 3 1-5Z"/><path d="m7 14 9-7"/>',
  documents: '<path d="M6 3h8l4 4v14H6zM14 3v5h5M9 13h6M9 17h5"/>',
  household: '<path d="m4 11 8-7 8 7v9H4zM9 20v-6h6v6"/>',
  assets: '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M8 8h8v8H8z"/>',
  network: '<circle cx="5" cy="12" r="2"/><circle cx="19" cy="6" r="2"/><circle cx="19" cy="18" r="2"/><path d="m7 11 10-4M7 13l10 4"/>',
  homelab: '<path d="M5 4h14v5H5zM5 11h14v5H5zM8 7h.01M8 14h.01M5 18h14"/>',
  security: '<path d="m12 3 8 3v5c0 5-3.4 8.4-8 10-4.6-1.6-8-5-8-10V6z"/><path d="m9 12 2 2 4-4"/>',
  osint: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5M10.5 7v7M7 10.5h7"/>',
  business: '<path d="M4 20V7h16v13M8 7V4h8v3M8 11h2M14 11h2M8 15h2M14 15h2"/>',
  memory: '<path d="M8 6a4 4 0 0 1 8 0v12a4 4 0 0 1-8 0z"/><path d="M8 10h8M8 14h8"/>',
  automations: '<path d="M4 12a8 8 0 1 0 3-6"/><path d="M4 5v5h5"/>',
  voice: '<path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3Z"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
  smartHome: '<path d="m4 11 8-7 8 7M6 10v10h12V10M10 20v-6h4v6"/>',
  improvements: '<path d="m5 19 4-4 3 3 7-8"/><path d="M15 10h4v4"/>',
  models: '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v6c0 2 3 3 7 3s7-1 7-3V6M5 12v6c0 2 3 3 7 3s7-1 7-3v-6"/>',
  developer: '<path d="m8 8-4 4 4 4M16 8l4 4-4 4M14 5l-4 14"/>',
  integrations: '<path d="M8 12h8M12 8v8"/><circle cx="12" cy="12" r="8"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.2-1.6l2-1.2-2-3.4-2.1 1.2A7 7 0 0 0 15 6l-.2-2.4h-4.0L10.5 6a7 7 0 0 0-1.7 1L6.7 5.8l-2 3.4 2 1.2A7 7 0 0 0 6.5 12c0 .6.1 1.1.2 1.6l-2 1.2 2 3.4 2.1-1.2a7 7 0 0 0 1.7 1l.2 2.4h4l.2-2.4a7 7 0 0 0 1.7-1l2.1 1.2 2-3.4-2-1.2c.2-.5.3-1 .3-1.6Z"/>',
});

export function moduleHeader({icon='hades', title, description='', status='', primary='', primaryId='', onAsk=false}) {
  return `<header class="hades-module-header"><div class="hades-module-heading"><span class="hades-module-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${ICONS[icon] || ICONS.hades}</svg></span><div><h2>${esc(title)}</h2><p>${esc(description)}</p>${status ? `<span class="hades-status-line">${esc(status)}</span>` : ''}</div></div><div class="hades-module-actions">${onAsk ? '<button type="button" class="hades-btn-secondary">Ask Hades</button>' : ''}${primary ? `<button type="button" class="hades-btn-primary"${primaryId ? ` id="${esc(primaryId)}"` : ''}>${esc(primary)}</button>` : ''}</div></header>`;
}

export function statusBadge(value, kind='neutral') {
  return `<span class="hades-badge hades-badge-${esc(kind)}">${esc(value || 'unknown')}</span>`;
}

export function emptyState(title, message, action='', actionId='') {
  return `<div class="hades-empty-state"><div class="hades-empty-icon">○</div><h3>${esc(title)}</h3><p>${esc(message)}</p>${action ? `<button type="button" class="hades-btn-primary"${actionId ? ` id="${esc(actionId)}"` : ''}>${esc(action)}</button>` : ''}</div>`;
}

export function loadingState(label='Loading…') { return `<div class="hades-loading-state" role="status"><span class="hades-loading-dot"></span>${esc(label)}</div>`; }
export function errorState(message, retryId='') { return `<div class="hades-error-state" role="alert"><strong>Something needs attention</strong><p>${esc(message)}</p>${retryId ? `<button type="button" class="hades-btn-secondary" id="${esc(retryId)}">Retry</button>` : ''}</div>`; }
export function provenanceBadge(kind='OBSERVED') { return `<span class="hades-provenance hades-provenance-${esc(kind.toLowerCase().replace(/[^a-z0-9]+/g, '-'))}">${esc(kind)}</span>`; }
export function intakeField(label, control) { return `<label class="hades-intake-field"><span>${esc(label)}</span>${control}</label>`; }
