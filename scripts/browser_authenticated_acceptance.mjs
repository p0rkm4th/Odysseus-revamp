/*
 * Authenticated owner-facing browser acceptance.
 *
 * This is development/acceptance tooling only.  It uses the normal login and
 * chat routes with the explicitly gated, non-privileged acceptance principal.
 * No owner cookie, profile, session, or state is read.  Tracing starts only
 * after login so credentials cannot enter a Playwright trace.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';
import { spawnSync } from 'node:child_process';
import { chromium } from 'playwright';

const baseURL = (process.env.HADES_BROWSER_BASE_URL || 'http://127.0.0.1:7000').replace(/\/$/, '');
if (process.env.HADES_BROWSER_ACCEPTANCE_ENABLE !== 'true') {
  throw new Error('Refusing browser acceptance: set HADES_BROWSER_ACCEPTANCE_ENABLE=true explicitly');
}

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'hades-browser-e2e-'));
const credentialFile = path.join(root, 'credentials.json');
const diagnosticsFile = path.join(root, 'diagnostics.json');
const traceFile = path.join(root, 'trace.zip');
const screenshotFile = path.join(root, 'failure.png');
const python = process.env.HADES_PYTHON || './venv/bin/python';
const composeEnv = { ...process.env, HADES_ACCEPTANCE_PRINCIPAL_ENABLED: 'true' };
const cleanupEnv = { ...process.env, HADES_ACCEPTANCE_PRINCIPAL_ENABLED: 'false' };

function run(command, args, env = process.env) {
  const result = spawnSync(command, args, { cwd: process.cwd(), env, encoding: 'utf8' });
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(' ')} failed (${result.status}): ${String(result.stderr || '').slice(-1000)}`);
  }
  return result.stdout || '';
}

function provision() {
  run('docker', ['compose', 'up', '-d', '--no-build', 'odysseus'], composeEnv);
  run(python, ['-m', 'scripts.create_acceptance_principal', '--credential-file', credentialFile, '--ttl', '600'], composeEnv);
  return JSON.parse(fs.readFileSync(credentialFile, 'utf8'));
}

function disableAndRevoke() {
  try {
    run(python, ['-m', 'scripts.create_acceptance_principal', '--auth-path', 'data/auth.json', '--revoke'], process.env);
  } finally {
    // Compose config is the deployment-controlled feature gate.  The image is
    // unchanged; this only removes the temporary acceptance facility.
    run('docker', ['compose', 'up', '-d', '--no-build', 'odysseus'], cleanupEnv);
  }
}

async function waitForHealth(timeoutMs = 60000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${baseURL}/api/health`);
      if (response.ok && (await response.json()).status === 'healthy') return;
    } catch (_) {
      // Compose may still be replacing the container; retry with a bounded
      // delay rather than racing the login page against startup.
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`Hades did not become healthy at ${baseURL} within ${timeoutMs}ms`);
}

function assistantCount(page) {
  return page.locator('#chat-history .msg-ai').evaluateAll((nodes) => nodes.filter((node) => {
    if (node.classList.contains('agent-thinking-dots') || node.classList.contains('streaming')) return false;
    const body = node.querySelector('.body');
    return !!body && !!body.innerText.trim();
  }).length);
}

function visibleMessages(page) {
  return page.locator('#chat-history .msg').evaluateAll((nodes) => nodes.map((node) => ({
    role: node.classList.contains('msg-user') ? 'user' : 'assistant',
    text: (node.querySelector('.body')?.innerText || node.innerText || '').trim().slice(0, 1000),
    classes: node.className,
  })));
}

async function waitForAnswer(page, beforeAssistant, streamIndex, prompt) {
  await page.waitForFunction(() => !document.querySelector('#chat-history .msg-ai.streaming'));
  await page.waitForFunction(({ before }) => {
    const answers = [...document.querySelectorAll('#chat-history .msg-ai')].filter((node) => {
      if (node.classList.contains('agent-thinking-dots') || node.classList.contains('streaming')) return false;
      return !!node.querySelector('.body')?.innerText.trim();
    });
    return answers.length > before;
  }, { before: beforeAssistant }, { timeout: 120000 });
  await page.waitForFunction((index) => {
    const stream = window.__hadesE2EStreams?.[index];
    return !!stream && (stream.doneCount === 1 || stream.abruptEOF);
  }, streamIndex, { timeout: 30000 });
  const stream = await page.evaluate((index) => window.__hadesE2EStreams?.[index] || null, streamIndex);
  if (!stream || stream.doneCount !== 1 || stream.abruptEOF) {
    throw new Error(`transport invariant failed for ${prompt}: ${JSON.stringify(stream)}`);
  }
  if (page.getByText('Stream connection ended. Composer unlocked; send again if needed.').count) {
    const warning = page.getByText('Stream connection ended. Composer unlocked; send again if needed.');
    if (await warning.count()) throw new Error(`stream warning rendered for ${prompt}`);
  }
}

async function send(page, prompt) {
  const beforeAssistant = await assistantCount(page);
  const beforeStreams = await page.evaluate(() => window.__hadesE2EStreams?.length || 0);
  const composer = page.locator('textarea#message:visible').first();
  await composer.fill(prompt);
  await page.locator('.send-btn').click();
  await page.waitForFunction((text) => [...document.querySelectorAll('#chat-history .msg-user')]
    .some((node) => (node.querySelector('.body')?.innerText || node.innerText || '').includes(text)), prompt);
  await waitForAnswer(page, beforeAssistant, beforeStreams, prompt);
  const afterAssistant = await assistantCount(page);
  if (afterAssistant !== beforeAssistant + 1) {
    throw new Error(`expected one assistant answer for ${prompt}, got ${afterAssistant - beforeAssistant}`);
  }
}

async function main() {
  const credentials = provision();
  await waitForHealth();
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  let context;
  let page;
  let tracing = false;
  let cleanupDone = false;
  const diagnostics = { baseURL, principal: credentials.username, prompts: [], errors: [], unexpectedErrors: [], failedRequests: [], http5xx: [] };
  try {
    context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    page = await context.newPage();
    page.on('console', (message) => { if (message.type() === 'error') diagnostics.errors.push(message.text().slice(0, 500)); });
    page.on('pageerror', (error) => diagnostics.unexpectedErrors.push(`pageerror: ${error.message}`));
    page.on('requestfailed', (request) => diagnostics.failedRequests.push(`${request.method()} ${request.url()} ${request.failure()?.errorText || ''}`));
    page.on('response', (response) => { if (response.status() >= 500) diagnostics.http5xx.push(`${response.status()} ${response.url()}`); });

    // Observe stream completion in memory without recording request bodies.
    await page.addInitScript(() => {
      window.__hadesE2EStreams = [];
      const originalFetch = window.fetch.bind(window);
      window.fetch = async (...args) => {
        const response = await originalFetch(...args);
        const url = typeof args[0] === 'string' ? args[0] : args[0]?.url || '';
        if (url.includes('/api/chat_stream')) {
          const record = { doneCount: 0, abruptEOF: false, terminalCount: 0, deltaCount: 0 };
          window.__hadesE2EStreams.push(record);
          response.clone().text().then((body) => {
            record.doneCount = (body.match(/data: \[DONE\]/g) || []).length;
            record.terminalCount = (body.match(/data: \[DONE\]/g) || []).length;
            record.deltaCount = (body.match(/"delta"/g) || []).length;
          }).catch(() => { record.abruptEOF = true; });
        }
        return response;
      };
    });

    await page.goto(`${baseURL}/login`, { waitUntil: 'domcontentloaded' });
    await page.locator('#username').fill(credentials.username);
    await page.locator('#password').fill(credentials.password);
    await page.locator('#authForm').evaluate((form) => form.requestSubmit());
    await page.waitForURL((url) => url.pathname === '/' || url.pathname === '', { timeout: 30000 });
    await page.locator('textarea#message:visible').first().waitFor({ state: 'visible', timeout: 30000 });

    // Start tracing only after the login response, so the password cannot be
    // present in trace network metadata.
    await context.tracing.start({ screenshots: true, snapshots: true, sources: false });
    tracing = true;

    const prompts = [
      'tell me about my network',
      'tell me about my homelab',
      'what do you know about me',
      'what computers do i have',
      'tell me about the first one',
      'what GPUs does it have?',
      'what work is outstanding?',
    ];
    for (const prompt of prompts) {
      await send(page, prompt);
      diagnostics.prompts.push(prompt);
    }

    const beforeReload = await assistantCount(page);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.locator('#chat-history .msg').first().waitFor({ timeout: 30000 });
    const afterReload = await assistantCount(page);
    if (afterReload < beforeReload) throw new Error(`conversation did not persist across reload: ${beforeReload} -> ${afterReload}`);
    await send(page, 'what about its RAM?');

    // The acceptance account owns only disposable test conversations. Remove
    // them through the normal owner-scoped session API before revocation so a
    // passing run cannot leave synthetic chat state behind.
    const deletedSessions = await page.evaluate(async () => {
      const response = await fetch('/api/sessions', { credentials: 'same-origin' });
      if (!response.ok) throw new Error(`could not enumerate acceptance sessions (${response.status})`);
      const payload = await response.json();
      const sessions = Array.isArray(payload) ? payload : (payload.sessions || []);
      let deleted = 0;
      for (const session of sessions) {
        const id = String(session.id || '').trim();
        if (!id) continue;
        const result = await fetch(`/api/session/${encodeURIComponent(id)}`, {
          method: 'DELETE', credentials: 'same-origin',
        });
        if (result.ok) deleted += 1;
      }
      return deleted;
    });
    diagnostics.deletedSessions = deletedSessions;

    await page.locator('#user-bar-settings').click();
    await page.locator('.settings-nav-item[data-settings-tab="account"]').click();
    await page.locator('#settings-logout-btn').click();
    await page.waitForURL((url) => url.pathname.endsWith('/login'), { timeout: 30000 });

    // Revoke the account and disable the facility before checking that the
    // normal login route can no longer authenticate it.
    disableAndRevoke();
    cleanupDone = true;
    await waitForHealth();
    await page.goto(`${baseURL}/login`, { waitUntil: 'domcontentloaded' });
    await page.locator('#username').fill(credentials.username);
    await page.locator('#password').fill(credentials.password);
    await page.locator('#authForm').evaluate((form) => form.requestSubmit());
    await page.waitForTimeout(1000);
    if (!page.url().endsWith('/login')) throw new Error('acceptance principal authenticated after cleanup');

    await context.tracing.stop();
    tracing = false;
    await context.close();
    await browser.close();
    console.log(JSON.stringify({ status: 'PASS', prompts: diagnostics.prompts.length, streams: diagnostics.prompts.length + 1 }));
  } catch (error) {
    diagnostics.failure = String(error?.stack || error);
    if (page) {
      diagnostics.visibleMessages = await visibleMessages(page).catch(() => []);
      await page.screenshot({ path: screenshotFile, fullPage: true }).catch(() => {});
    }
    fs.writeFileSync(diagnosticsFile, JSON.stringify(diagnostics, null, 2), { mode: 0o600 });
    if (tracing && context) await context.tracing.stop({ path: traceFile }).catch(() => {});
    throw error;
  } finally {
    if (context) await context.close().catch(() => {});
    await browser.close().catch(() => {});
    if (!cleanupDone) disableAndRevoke();
    try { fs.unlinkSync(credentialFile); } catch (_) {}
  }
}

await main();
