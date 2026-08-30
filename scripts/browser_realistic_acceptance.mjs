/* Synthetic populated UI acceptance. It never mutates canonical data. */
import fs from 'node:fs';
import process from 'node:process';
import { chromium } from 'playwright';

const baseURL = process.env.HADES_BROWSER_BASE_URL || 'http://127.0.0.1:7000';
const externalCredentialFile = process.env.HADES_BROWSER_EXTERNAL_CREDENTIAL_FILE || '';
const externalAcceptance = Boolean(externalCredentialFile);
if (externalAcceptance && (process.env.HADES_BROWSER_ACCEPTANCE_ENABLE !== 'true'
    || process.env.HADES_BROWSER_ISOLATED_ACCEPTANCE !== 'true'
    || !String(process.env.APP_DATA_DIR || '').trim())) {
  throw new Error('external visual acceptance requires explicit isolated acceptance settings');
}
const credentials = externalAcceptance
  ? JSON.parse(fs.readFileSync(externalCredentialFile, 'utf8'))
  : null;
const token = externalAcceptance
  ? null
  : Object.keys(JSON.parse(fs.readFileSync('data/sessions.json', 'utf8')))[0];
const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
const errors = [];
const fixture = `
  <div class="osint-fixture">
    <header class="hades-module-header fixture-header">
      <div class="hades-module-heading"><span class="hades-module-icon">OSINT</span><div><h2>OSINT</h2><p>Bounded public-source investigation workspace</p></div></div>
      <div class="hades-module-actions"><button class="hades-btn-primary" data-fixture-cta>New Investigation</button></div>
    </header>
    <nav class="hades-module-tabs fixture-nav" aria-label="Investigation sections">${Array.from({length: 10}, (_, i) => `<button class="hades-module-tab${i === 0 ? ' active' : ''}">${['Overview','Cases','Sources','Evidence','Claims','Relationships','Timeline','Corrections','Reports','History'][i]}</button>`).join('')}</nav>
    <section class="hades-overview-grid fixture-summary"><article class="hades-summary-card"><span>Sources</span><strong>50</strong><small>reviewed and tainted</small></article><article class="hades-summary-card"><span>Open questions</span><strong>17</strong><small>owner review required</small></article><article class="hades-summary-card"><span>Confidence</span><strong>Mixed</strong><small>evidence posture visible</small></article></section>
    <section class="fixture-cases"><h3>Recent Investigations</h3><article class="hades-record-card osint-case-card"><div><strong>Example Organization</strong><p>Company · deep research</p><small>50 sources · 34 claims · 17 open questions</small></div><button class="hades-btn-secondary">Open Case</button></article></section>
    <section class="hades-detail-section fixture-dossier"><h3>Known Information / Seed</h3><p class="fixture-seed">USER PROVIDED — ${'very-long-known-information '.repeat(80)}https://example.invalid/${'unbroken-segment-'.repeat(40)}</p></section>
    <section class="fixture-report"><h3>Report excerpt</h3><p>${'Long-form investigation prose remains readable, wrapped, and separated from controls. '.repeat(24)}</p></section>
  </div>`;

function box(page, selector) {
  return page.locator(selector).boundingBox();
}
function assertContained(inner, outer, label) {
  if (!inner || !outer || inner.left < outer.left - 1 || inner.top < outer.top - 1
      || inner.right > outer.right + 1 || inner.bottom > outer.bottom + 1) {
    throw new Error(`not contained: ${label}`);
  }
}
function assertOrdered(boxes, label) {
  for (let i = 1; i < boxes.length; i += 1) {
    if (!boxes[i - 1] || !boxes[i] || boxes[i - 1].bottom > boxes[i].top + 1) {
      throw new Error(`overlap: ${label}[${i - 1}] -> ${label}[${i}]`);
    }
  }
}

async function openPage(viewport) {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  let captureDiagnostics = !externalAcceptance;
  page.on('console', message => { if (captureDiagnostics && message.type() === 'error') errors.push(`console: ${message.text()}`); });
  page.on('pageerror', error => { if (captureDiagnostics) errors.push(`pageerror: ${error.message}`); });
  page.on('requestfailed', request => { if (captureDiagnostics) errors.push(`request: ${request.url()} ${request.failure()?.errorText || ''}`); });
  page.on('response', response => { if (captureDiagnostics && response.status() >= 500) errors.push(`http${response.status()}: ${response.url()}`); });
  if (externalAcceptance) {
    await page.goto(`${baseURL}/login`, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => document.querySelector('#submitBtn')?.textContent?.trim() === 'Sign In', { timeout: 30000 });
    await page.locator('#username').fill(credentials.username);
    await page.locator('#password').fill(credentials.password);
    await page.locator('#submitBtn').click();
    // Login may complete through SPA history manipulation without emitting a
    // navigation event. Accept an already-authenticated root shell while
    // still surfacing a genuine redirect failure.
    try {
      await page.waitForURL((url) => url.pathname === '/' || url.pathname === '', { timeout: 30000 });
    } catch (error) {
      const currentPath = new URL(page.url()).pathname;
      if (currentPath !== '/' && currentPath !== '') throw error;
    }
    captureDiagnostics = true;
  } else {
    await context.addCookies([{ name: 'odysseus_session', value: token, url: baseURL }]);
    await page.goto(`${baseURL}/`, { waitUntil: 'domcontentloaded' });
  }
  await page.waitForFunction(() => !!window.hadesWindowManager && !!document.querySelector('#icon-rail'));
  const sidebarEntries = page.locator('#sidebar .list-item[id^="tool-"]:visible');
  for (let i = 0; i < await sidebarEntries.count(); i += 1) {
    const entry = sidebarEntries.nth(i);
    const iconCount = await entry.evaluate(node => [...node.children].filter(child => child.tagName.toLowerCase() === 'svg').length);
    if (iconCount !== 1) throw new Error(`sidebar entry has duplicate/missing icon: ${await entry.getAttribute('id')}`);
  }
  if (await page.locator('#sidebar #tool-security-btn:visible').count() > 1 || await page.locator('#sidebar #tool-research-btn:visible').count() > 1) {
    throw new Error('duplicate Security or Deep Research navigation entry');
  }
  const pageMetrics = await page.evaluate(() => ({width: innerWidth, scrollWidth: document.documentElement.scrollWidth}));
  if (pageMetrics.scrollWidth > pageMetrics.width + 1) throw new Error('desktop navigation escapes viewport');
  return { context, page };
}

const desktop = await openPage({ width: 1440, height: 900 });
await desktop.page.locator('#tool-inventory-btn').click();
const inventoryPane = desktop.page.locator('#inventory-pane');
await inventoryPane.waitFor();
if (!await inventoryPane.evaluate(node => node.classList.contains('hades-workspace-window'))) throw new Error('inventory does not use shared window shell');
if (await inventoryPane.locator('.hades-window-titlebar').count() !== 1 || await inventoryPane.locator('.hades-module-tabs').count() !== 1) throw new Error('inventory shared chrome is incomplete');
const inventoryBox = await inventoryPane.boundingBox();
if (!inventoryBox || inventoryBox.left < 0 || inventoryBox.top < 0 || inventoryBox.right > 1440 || inventoryBox.bottom > 900) throw new Error('inventory window escapes viewport');
await inventoryPane.locator('[data-tab="recipes"]').click();
await inventoryPane.locator('#inventory-recipe-list').waitFor();
const recipeStates = inventoryPane.locator('#inventory-recipe-list .hades-empty-state, #inventory-recipe-list .hades-record-card');
await recipeStates.first().waitFor();
if (await recipeStates.count() < 1) throw new Error('recipe view lacks shared empty/list state');
await inventoryPane.locator('[data-close]').click();
await desktop.page.evaluate(content => window.hadesWindowManager.openView('osint-fixture', null, 'OSINT realistic fixture', content), fixture);
const desktopWindow = desktop.page.locator('[data-view="osint-fixture"]');
await desktopWindow.waitFor();
const desktopBox = await desktopWindow.boundingBox();
if (!desktopBox || desktopBox.left < 0 || desktopBox.top < 0 || desktopBox.right > 1440 || desktopBox.bottom > 900) throw new Error('desktop window escapes viewport');
if (!await desktop.page.locator('[data-fixture-cta]').isVisible()) throw new Error('primary CTA hidden');
assertOrdered(await Promise.all(['.fixture-header', '.fixture-nav', '.fixture-summary', '.fixture-cases', '.fixture-dossier', '.fixture-report'].map(s => box(desktop.page, s))), 'desktop regions');
assertContained(await box(desktop.page, '.fixture-seed'), await box(desktop.page, '.fixture-dossier'), 'seed');
await desktop.page.screenshot({ path: '/tmp/hades-osint-realistic-desktop.png', fullPage: false });

await desktop.page.evaluate(() => document.getElementById('hamburger-btn').click());
const workspaceButtons = desktop.page.locator('#icon-rail .workspace-icon-rail-btn');
if (await workspaceButtons.count() !== 9) throw new Error('workspace compact coverage incomplete');
for (let i = 0; i < await workspaceButtons.count(); i += 1) {
  if (!await workspaceButtons.nth(i).isVisible()) throw new Error(`workspace icon ${i} hidden`);
}
await desktop.context.close();

const narrow = await openPage({ width: 390, height: 844 });
await narrow.page.evaluate(content => window.hadesWindowManager.openView('osint-fixture-narrow', null, 'OSINT narrow fixture', content), fixture);
await narrow.page.locator('[data-view="osint-fixture-narrow"]').waitFor();
const tabs = narrow.page.locator('[data-view="osint-fixture-narrow"] .hades-module-tabs');
const tabMetrics = await tabs.evaluate(node => ({ clientWidth: node.clientWidth, scrollWidth: node.scrollWidth, overflowX: getComputedStyle(node).overflowX }));
if (tabMetrics.scrollWidth > tabMetrics.clientWidth && tabMetrics.overflowX === 'hidden') throw new Error('tabs clipped in constrained width');
const narrowMetrics = await narrow.page.evaluate(() => ({width: innerWidth, scrollWidth: document.documentElement.scrollWidth}));
if (narrowMetrics.scrollWidth > narrowMetrics.width + 1) throw new Error('narrow layout escapes viewport');
assertContained(await box(narrow.page, '.fixture-seed'), await box(narrow.page, '.fixture-dossier'), 'narrow seed');
await narrow.page.screenshot({ path: '/tmp/hades-osint-realistic-narrow.png', fullPage: false });
await narrow.context.close();

const mobile = await openPage({ width: 375, height: 812 });
await mobile.page.evaluate(content => window.hadesWindowManager.openView('osint-fixture-mobile', null, 'OSINT mobile fixture', content), fixture);
const mobileWindow = mobile.page.locator('[data-view="osint-fixture-mobile"]');
await mobileWindow.waitFor();
const mobileBox = await mobileWindow.boundingBox();
if (!mobileBox || mobileBox.width !== 375 || mobileBox.height !== 812) throw new Error(`mobile window contract failed: ${JSON.stringify(mobileBox)}`);
await mobile.page.screenshot({ path: '/tmp/hades-osint-realistic-mobile.png', fullPage: false });
await mobile.context.close();

await browser.close();
if (errors.length) throw new Error(`browser diagnostics: ${errors.join(' | ')}`);
console.log('browser_realistic_acceptance: PASS');
