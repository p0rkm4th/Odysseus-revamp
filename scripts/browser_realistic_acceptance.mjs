/* Synthetic populated UI acceptance. It never mutates canonical data. */
import fs from 'node:fs';
import process from 'node:process';
import { chromium } from 'playwright';

const sessions = JSON.parse(fs.readFileSync('data/sessions.json', 'utf8'));
const token = Object.keys(sessions)[0];
const baseURL = process.env.HADES_BROWSER_BASE_URL || 'http://127.0.0.1:7000';
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
  await context.addCookies([{ name: 'odysseus_session', value: token, url: baseURL }]);
  const page = await context.newPage();
  page.on('console', message => { if (message.type() === 'error') errors.push(`console: ${message.text()}`); });
  page.on('pageerror', error => errors.push(`pageerror: ${error.message}`));
  page.on('requestfailed', request => errors.push(`request: ${request.url()} ${request.failure()?.errorText || ''}`));
  page.on('response', response => { if (response.status() >= 500) errors.push(`http${response.status()}: ${response.url()}`); });
  await page.goto(`${baseURL}/`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => !!window.hadesWindowManager && !!document.querySelector('#icon-rail'));
  return { context, page };
}

const desktop = await openPage({ width: 1440, height: 900 });
await desktop.page.evaluate(content => window.hadesWindowManager.openView('osint-fixture', null, 'OSINT realistic fixture', content), fixture);
const desktopWindow = desktop.page.locator('[data-view="osint-fixture"]');
await desktopWindow.waitFor();
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
