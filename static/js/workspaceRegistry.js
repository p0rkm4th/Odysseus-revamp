/*
 * Canonical user-facing information architecture.
 *
 * A workspace is a product destination; its modules are projections of
 * independent backend domains.  Backend ownership must not be inferred from
 * this registry.  Legacy DOM ids remain explicit compatibility bindings until
 * their callers are migrated.
 */
export const WORKSPACE_DEFINITIONS = Object.freeze([
  {
    id: 'hades', label: 'Hades', icon: 'hades', defaultModule: 'hades',
    modules: ['hades', 'memory', 'attention', 'automations', 'models', 'improvements'],
  },
  {
    id: 'today', label: 'Today', icon: 'attention', defaultModule: 'calendar',
    modules: ['calendar', 'tasks', 'attention'],
  },
  {
    id: 'research', label: 'Research', icon: 'deepResearch', defaultModule: 'osint',
    modules: ['osint', 'deepResearch', 'securityResearch', 'researchSources'],
  },
  {
    id: 'infrastructure', label: 'Infrastructure', icon: 'network', defaultModule: 'assets',
    modules: ['inventory', 'assets', 'network', 'homelab', 'security', 'worldModel', 'incidents', 'changes'],
  },
  {
    id: 'home', label: 'Home', icon: 'household', defaultModule: 'household',
    modules: ['household', 'smartHome', 'recipes', 'shopping'],
  },
  {
    id: 'communications', label: 'Communications', icon: 'communications', defaultModule: 'communications',
    modules: ['communications', 'email', 'calendar', 'contacts', 'telegram', 'notifications'],
  },
  {
    id: 'work', label: 'Work', icon: 'work', defaultModule: 'work',
    modules: ['work', 'goals', 'projects', 'tasks', 'missions', 'business', 'career', 'commitments'],
  },
  {
    id: 'knowledge', label: 'Knowledge', icon: 'documents', defaultModule: 'library',
    modules: ['library', 'documents', 'notes', 'gallery', 'compare', 'cookbook', 'search'],
  },
  {
    id: 'system', label: 'System', icon: 'settings', defaultModule: 'controlCenter',
    modules: ['setupCenter', 'integrations', 'permissions', 'controlCenter', 'developer', 'appearance', 'settings'],
  },
]);

export const MODULE_DEFINITIONS = Object.freeze([
  ['hades', 'Hades', 'hades', 'tool-hades-btn'],
  ['memory', 'Memory', 'memory', 'tool-memory-btn'],
  ['attention', 'Attention', 'attention', null],
  ['automations', 'Automations', 'automations', null],
  ['models', 'Models', 'models', null],
  ['improvements', 'Improvements', 'improvements', null],
  ['calendar', 'Calendar', 'calendar', 'tool-calendar-btn'],
  ['tasks', 'Tasks', 'work', 'tool-tasks-btn'],
  ['osint', 'OSINT', 'osint', 'tool-osint-btn'],
  ['deepResearch', 'Deep Research', 'deepResearch', 'tool-research-btn'],
  ['securityResearch', 'Security Research', 'security', null],
  ['researchSources', 'Sources', 'documents', null],
  ['inventory', 'Inventory', 'household', 'tool-inventory-btn'],
  ['assets', 'IT Assets', 'itAssets', 'tool-it-assets-btn'],
  ['network', 'Network', 'network', 'tool-network-btn'],
  ['homelab', 'Homelab', 'homelab', 'tool-homelab-btn'],
  ['security', 'Security', 'security', 'tool-security-btn'],
  ['worldModel', 'World Model', 'worldModel', 'tool-world-model-btn'],
  ['incidents', 'Incidents', 'security', null],
  ['changes', 'Changes', 'work', null],
  ['household', 'Household', 'household', 'tool-household-btn'],
  ['smartHome', 'Smart Home', 'smartHome', 'tool-smart-home-btn'],
  ['recipes', 'Recipes', 'documents', null],
  ['shopping', 'Shopping', 'household', null],
  ['communications', 'Communications', 'communications', 'tool-communications-btn'],
  ['email', 'Email', 'email', null],
  ['contacts', 'Contacts', 'contacts', null],
  ['telegram', 'Telegram', 'telegram', 'tool-telegram-btn'],
  ['notifications', 'Notifications', 'attention', null],
  ['work', 'Work', 'work', 'tool-work-btn'],
  ['goals', 'Goals', 'work', null],
  ['projects', 'Projects', 'work', null],
  ['missions', 'Missions', 'work', null],
  ['business', 'Business', 'business', null],
  ['career', 'Career', 'career', null],
  ['commitments', 'Commitments', 'work', null],
  ['library', 'Documents', 'documents', 'tool-library-btn'],
  ['documents', 'Documents', 'documents', null],
  ['gallery', 'Gallery', 'documents', 'tool-gallery-btn'],
  ['notes', 'Notes', 'documents', 'tool-notes-btn'],
  ['compare', 'Compare', 'models', 'tool-compare-btn'],
  ['cookbook', 'Cookbook', 'documents', 'tool-cookbook-btn'],
  ['search', 'Search', 'documents', null],
  ['setupCenter', 'Setup Center', 'settings', 'tool-setup-center-btn'],
  ['integrations', 'Integration Center', 'integrations', 'tool-integrations-center-btn'],
  ['permissions', 'Permissions', 'security', null],
  ['developer', 'Developer', 'developer', 'tool-developer-btn'],
  ['controlCenter', 'Control Center', 'controlCenter', 'tool-control-center-btn'],
  ['appearance', 'Appearance', 'settings', null],
  ['settings', 'Settings', 'settings', 'rail-settings'],
]);

export const MODULE_BY_ID = Object.freeze(Object.fromEntries(
  MODULE_DEFINITIONS.map(([id, label, icon, navId]) => [id, { id, label, icon, navId }])
));

export const WORKSPACE_BY_ID = Object.freeze(Object.fromEntries(
  WORKSPACE_DEFINITIONS.map(workspace => [workspace.id, workspace])
));

export function workspaceForModule(moduleId) {
  return WORKSPACE_DEFINITIONS.find(workspace => workspace.modules.includes(moduleId)) || null;
}
