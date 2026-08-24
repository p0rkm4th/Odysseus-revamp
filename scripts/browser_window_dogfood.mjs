/* Development-only browser dogfood. Run with PLAYWRIGHT_MODULE pointing at a
 * temporary host-side Playwright install; never add it to the production image. */
import fs from 'node:fs';
import process from 'node:process';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');

const sessions = JSON.parse(fs.readFileSync('data/sessions.json', 'utf8'));
const token = Object.keys(sessions)[0];
const baseURL = process.env.HADES_BROWSER_BASE_URL || 'http://127.0.0.1:7000';
const browser = await chromium.launch({ headless: true, executablePath: '/usr/bin/chromium', args: ['--no-sandbox'] });

async function desktop() {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.addCookies([{ name: 'odysseus_session', value: token, url: baseURL }]);
  const page = await context.newPage();
  await page.goto(`${baseURL}/`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => !!window.hadesWindowManager);
  await page.evaluate(() => {
    window.hadesWindowManager.openView('network', 'cmdb-test-1', 'Network device', '<p>device</p>');
    window.hadesWindowManager.openView('network', 'cmdb-test-1', 'Network device', '<p>duplicate</p>');
    window.hadesWindowManager.openView('it-asset', 'cmdb-test-1', 'IT Asset', '<p>asset</p>');
    window.hadesWindowManager.openView('network-panel', null, 'Network Map', '<p>map</p>');
  });
  if (await page.locator('[data-view="network"][data-entity="cmdb-test-1"]').count() !== 1) throw new Error('entity reuse failed');
  if (await page.locator('[data-view="it-asset"][data-entity="cmdb-test-1"]').count() !== 1) throw new Error('cross-domain window failed');
  const w = page.locator('[data-view="network"][data-entity="cmdb-test-1"]');
  await page.evaluate(() => window.hadesWindowManager.focus('network:cmdb-test-1'));
  await w.getByLabel('Snap left').click({ force: true });
  await w.getByLabel('Minimize').click();
  if (await w.isVisible()) throw new Error('minimize failed');
  await page.getByRole('button', { name: 'Network device' }).click();
  if (!await w.isVisible()) throw new Error('restore failed');
  await w.getByLabel('Maximize').click();
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => !!window.hadesWindowManager);
  await page.waitForTimeout(500);
  if (await page.locator('[data-view="network-panel"]').count() !== 1) throw new Error('reload restore failed');
  await context.close();
}

async function mobile() {
  const context = await browser.newContext({ viewport: { width: 375, height: 812 } });
  await context.addCookies([{ name: 'odysseus_session', value: token, url: baseURL }]);
  const page = await context.newPage();
  await page.goto(`${baseURL}/`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => !!window.hadesWindowManager);
  await page.evaluate(() => window.hadesWindowManager.openView('network', 'mobile-test-1', 'Mobile network', '<p>mobile</p>'));
  const box = await page.locator('[data-view="network"][data-entity="mobile-test-1"]').boundingBox();
  if (!box || box.width !== 375 || box.height !== 812) throw new Error(`mobile fallback failed: ${JSON.stringify(box)}`);
  await context.close();
}

await desktop();
await mobile();
await browser.close();
console.log('browser_window_dogfood: PASS');
