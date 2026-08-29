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
const externalCredentialFile = process.env.HADES_BROWSER_EXTERNAL_CREDENTIAL_FILE || '';
const externalAcceptance = Boolean(externalCredentialFile);
const isolatedAcceptance = process.env.HADES_BROWSER_ISOLATED_ACCEPTANCE === 'true';
const householdAcceptance = process.env.HADES_BROWSER_HOUSEHOLD_ACCEPTANCE === 'true';
const journeyFile = process.env.HADES_BROWSER_JOURNEY_FILE || '';
if (householdAcceptance && !externalAcceptance) {
  throw new Error('Household browser acceptance requires an external isolated acceptance deployment');
}
const composeEnv = { ...process.env, HADES_ACCEPTANCE_PRINCIPAL_ENABLED: 'true' };
const cleanupEnv = { ...process.env, HADES_ACCEPTANCE_PRINCIPAL_ENABLED: 'false' };

function run(command, args, env = process.env) {
  const result = spawnSync(command, args, { cwd: process.cwd(), env, encoding: 'utf8' });
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(' ')} failed (${result.status}): ${String(result.stderr || '').slice(-1000)}`);
  }
  return result.stdout || '';
}

function loadJourneyScenarios() {
  if (!journeyFile) return null;
  const payload = JSON.parse(fs.readFileSync(journeyFile, 'utf8'));
  if (!Array.isArray(payload.scenarios)) throw new Error('owner journey file has no scenarios array');
  const requested = process.env.HADES_BROWSER_SCENARIOS
    ? new Set(process.env.HADES_BROWSER_SCENARIOS.split(',').map((value) => value.trim()).filter(Boolean))
    : null;
  const scenarios = payload.scenarios.filter((scenario) => !requested || requested.has(scenario.id));
  if (!scenarios.length) throw new Error('owner journey selection is empty');
  const fixtureProfiles = [...new Set(scenarios.map((scenario) => String(scenario.fixture_profile || '').trim()).filter(Boolean))];
  if (fixtureProfiles.length !== 1) {
    throw new Error(
      `owner journey run must use exactly one isolated fixture_profile; selected: ${fixtureProfiles.join(', ') || 'none'}`
    );
  }
  const environments = [...new Set(scenarios.map((scenario) => scenario.environment))];
  if (environments.length !== 1) {
    throw new Error(
      `owner journey run must use exactly one environment; selected: ${environments.join(', ')}`
    );
  }
  const hasMutation = scenarios.some((scenario) => scenario.turns.some((turn) =>
    ['CREATE', 'UPDATE', 'DELETE', 'EXECUTE'].includes(String(turn.expected?.operation || '').toUpperCase())));
  if (hasMutation && !externalAcceptance) {
    throw new Error('refusing owner-instance browser run: mutation journeys require an isolated external acceptance deployment');
  }
  if (scenarios.some((scenario) => scenario.environment !== 'actual_owner_read_only') &&
      (!externalAcceptance || !isolatedAcceptance)) {
    throw new Error('synthetic owner journeys require HADES_BROWSER_ISOLATED_ACCEPTANCE=true and an external isolated acceptance deployment');
  }
  if (scenarios.some((scenario) => scenario.environment === 'actual_owner_read_only') && !externalAcceptance) {
    throw new Error('actual_owner_read_only journeys require an explicitly supplied owner session credential');
  }
  return scenarios;
}

function provision() {
  if (externalAcceptance) {
    return JSON.parse(fs.readFileSync(externalCredentialFile, 'utf8'));
  }
  run('docker', ['compose', 'up', '-d', '--no-build', 'odysseus'], composeEnv);
  run(python, ['-m', 'scripts.create_acceptance_principal', '--credential-file', credentialFile, '--ttl', '600'], composeEnv);
  // AuthManager loads its account index at process startup.  The operator
  // utility intentionally writes through the normal durable store, so
  // restart the disposable app once to make that newly issued principal
  // visible to the normal login route.  This never touches the owner lane.
  run('docker', ['compose', 'restart', 'odysseus'], composeEnv);
  return JSON.parse(fs.readFileSync(credentialFile, 'utf8'));
}

function disableAndRevoke() {
  if (externalAcceptance) return;
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

async function seedHouseholdAcceptanceState(page) {
  // Seed only the disposable, already-authenticated acceptance principal via
  // the normal owner-scoped API.  This is setup for browser reads, not a
  // second persistence path and never runs against the owner instance.
  return page.evaluate(async () => {
    const suffix = Date.now().toString(36);
    const create = await fetch('/api/inventory/items', {
      method: 'POST', credentials: 'same-origin',
      headers: {'content-type': 'application/json'},
      body: JSON.stringify({
        name: `Acceptance Milk ${suffix}`,
        domain: 'kitchen', item_kind: 'ingredient', default_unit: 'l',
        category: 'dairy', reorder_point: 0.5,
      }),
    });
    if (!create.ok) throw new Error(`household acceptance item setup failed (${create.status})`);
    const item = (await create.json()).item;
    if (!item?.id) throw new Error('household acceptance item setup returned no item id');
    const stock = await fetch(`/api/inventory/items/${encodeURIComponent(item.id)}/stock`, {
      method: 'POST', credentials: 'same-origin',
      headers: {'content-type': 'application/json'},
      body: JSON.stringify({
        quantity: 2, unit: 'l', idempotency_key: `browser-acceptance-${suffix}`,
      }),
    });
    if (!stock.ok) throw new Error(`household acceptance stock setup failed (${stock.status})`);
    const overview = await fetch('/api/inventory/overview?expiry_days=30', {credentials: 'same-origin'});
    if (!overview.ok) throw new Error(`household acceptance readback failed (${overview.status})`);
    const projection = await overview.json();
    const readback = (projection.items || []).find((candidate) => candidate.id === item.id);
    if (!readback || String(readback.stock_quantity) !== '2000.000000') {
      throw new Error(`household acceptance stock readback was not canonical: ${JSON.stringify(readback)}`);
    }
    return {itemId: item.id, itemName: item.name, stockQuantity: readback.stock_quantity};
  });
}

async function seedWorkAcceptanceState(page) {
  // These owner-scoped calls establish prerequisite state only. The tested
  // read still enters through natural-language chat on the disposable owner.
  return page.evaluate(async () => {
    const suffix = Date.now().toString(36);
    const projectResponse = await fetch('/api/work/projects', {
      method: 'POST', credentials: 'same-origin',
      headers: {'content-type': 'application/json'},
      body: JSON.stringify({title: `Acceptance infrastructure ${suffix}`, domain: 'homelab'}),
    });
    if (!projectResponse.ok) throw new Error(`work acceptance project setup failed (${projectResponse.status})`);
    const project = await projectResponse.json();
    if (!project?.id) throw new Error('work acceptance project setup returned no id');
    const taskResponse = await fetch('/api/work/tasks', {
      method: 'POST', credentials: 'same-origin',
      headers: {'content-type': 'application/json'},
      body: JSON.stringify({
        project_id: project.id,
        title: 'Record acceptance service migration',
        status: 'pending',
      }),
    });
    if (!taskResponse.ok) throw new Error(`work acceptance task setup failed (${taskResponse.status})`);
    const task = await taskResponse.json();
    const overviewResponse = await fetch('/api/work/overview', {credentials: 'same-origin'});
    if (!overviewResponse.ok) throw new Error(`work acceptance readback failed (${overviewResponse.status})`);
    const overview = await overviewResponse.json();
    if (!(overview.tasks || []).some((row) => row.id === task.id)) {
      throw new Error('work acceptance task was not present in canonical overview');
    }
    return {projectId: project.id, taskId: task.id, taskTitle: task.title};
  });
}

function seedCanonicalAssetFixture(scenarios) {
  const setups = [...new Set(scenarios.map((scenario) => scenario.fixture_setup).filter(Boolean))];
  const assetSetups = setups.filter((setup) => ['canonical_asset_atlas_erebus', 'canonical_asset_no_4090'].includes(setup));
  if (!assetSetups.length) return null;
  if (setups.length !== 1 || assetSetups.length !== 1) {
    throw new Error(`unsupported or mixed canonical asset fixture setup: ${setups.join(', ')}`);
  }
  const database = String(process.env.HADES_BROWSER_CANONICAL_ASSET_DB || '').trim();
  if (!database || !externalAcceptance) {
    throw new Error('canonical asset browser fixtures require an explicit disposable external acceptance database');
  }
  const assets = assetSetups[0] === 'canonical_asset_atlas_erebus'
    ? [
      ['acceptance-atlas', 'Atlas', '64 GB', 'RTX Fixture A'],
      ['acceptance-erebus', 'Erebus', '128 GB', 'RTX Fixture B'],
    ]
    : [
      ['acceptance-messy-atlas', 'Atlas', '64 GB', 'RTX 2080'],
      ['acceptance-messy-erebus', 'Erebus', null, null],
      ['acceptance-messy-erebus-copy', 'Erebus (stale)', null, 'RTX 2080'],
    ];
  for (const [id, name, ram, gpu] of assets) {
    const attributes = {fixture: true};
    if (ram) attributes.ram = ram;
    if (gpu) attributes.gpu = gpu;
    const result = spawnSync(python, [
      '-m', 'src.asset_inventory', 'add', '--id', id, '--name', name,
      '--type', 'computer', '--status', 'deployed', '--manufacturer', 'Acceptance Labs',
      '--model', 'Fixture Host', '--source', 'acceptance-fixture', '--owner', credentialsOwner(),
      '--attributes', JSON.stringify(attributes, Object.keys(attributes).sort()),
    ], {
      cwd: process.cwd(),
      env: {...process.env, ODY_ASSET_DB: database},
      encoding: 'utf8',
    });
    if (result.status !== 0) throw new Error(`canonical asset fixture setup failed for ${id}`);
  }
  return {setup: setups[0], assets: assets.length};
}

function credentialsOwner() {
  return 'hades-acceptance';
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
    toolNodes: node.querySelectorAll('.agent-thread-node').length,
    rawOutputs: node.querySelectorAll('.agent-tool-output').length,
  })));
}

function finalAnswerSnapshot(page) {
  return page.locator('#chat-history').evaluate((history) => {
    const messages = [...history.querySelectorAll('.msg-ai')]
      .filter((node) => !node.classList.contains('agent-thinking-dots') && !node.classList.contains('streaming'))
      .map((node) => {
        const body = node.querySelector(':scope > .body');
        const text = (body?.innerText || '').trim();
        const raw = String(node.dataset.raw || '').trim();
        const toolOutput = [...node.querySelectorAll('.agent-tool-output pre')].map((el) => el.innerText).join('\n');
        return { text: text.slice(0, 2000), raw: raw.slice(0, 2000), toolOutput: toolOutput.slice(0, 2000), classes: node.className };
      });
    const threads = [...history.querySelectorAll('.agent-thread')].map((thread) => ({
      text: (thread.innerText || '').trim().slice(0, 2000),
      openNodes: thread.querySelectorAll('.agent-thread-node.open').length,
      outputBlocks: thread.querySelectorAll('.agent-tool-output').length,
    }));
    return { messages, threads };
  });
}

async function latestTurnAnswers(page) {
  return page.locator('#chat-history').evaluate((history) => {
    const users = [...history.querySelectorAll('.msg-user')];
    const user = users.at(-1);
    if (!user) return { answers: [], tools: [] };
    const answers = [];
    const tools = [];
    for (let node = user.nextElementSibling; node; node = node.nextElementSibling) {
      if (node.classList.contains('msg-ai') && !node.classList.contains('streaming')) {
        const body = node.querySelector(':scope > .body');
        const text = (body?.innerText || '').trim();
        if (text) answers.push({ text: text.slice(0, 3000), raw: String(node.dataset.raw || '').slice(0, 3000) });
      }
      if (node.classList.contains('agent-thread')) {
        tools.push({
          text: (node.innerText || '').trim().slice(0, 1000),
          outputBlocks: node.querySelectorAll('.agent-tool-output').length,
          openNodes: node.querySelectorAll('.agent-thread-node.open').length,
          openOutputs: node.querySelectorAll('.agent-tool-output[open]').length,
          rawOutput: [...node.querySelectorAll('.agent-tool-output pre')]
            .map((el) => el.innerText).join('\n').slice(0, 3000),
        });
      }
    }
    return { answers, tools };
  });
}

function assertHumanCanonicalAnswer(turn, prompt) {
  if (!turn || turn.answers.length !== 1) {
    throw new Error(`expected exactly one final assistant answer for ${prompt}, got ${turn?.answers?.length || 0}`);
  }
  const text = turn.answers[0].text.trim();
  if (text.length < 12 || /^(done|successfully completed)[.!]?$/i.test(text)) {
    throw new Error(`tool-backed turn has no useful human-readable final answer for ${prompt}`);
  }
  if (/^\s*[\[{]/.test(text) || /(?:asset_id|observation_id|provenance|freshness|relationships)\s*[:=]/i.test(text)) {
    throw new Error(`final answer appears to be raw structured tool output for ${prompt}`);
  }
  return text;
}

function isDiagnosticToolOutput(value) {
  const text = String(value || '').trim();
  if (!text) return false;
  if (/^\s*[\[{]/.test(text)) return true;
  return /(?:asset_id|observation_id|relationships|serial(?:_number)?|system_identifiers|lsblk|result_projection)\s*[:=]/i.test(text);
}

function literalPattern(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

async function verifyScenarioReadback(page, scenario, phase = 'before-reload') {
  const spec = scenario?.expected?.readback;
  if (!spec) return null;
  // Readback is deliberately a small allowlisted assertion vocabulary.  The
  // browser still performs the mutation through chat; these GETs only inspect
  // the resulting canonical owner state independently of the rendered answer.
  const result = await page.evaluate(async (readback) => {
    const response = await fetch(readback.endpoint, {credentials: 'same-origin'});
    const payload = await response.json().catch(() => ({}));
    return {ok: response.ok, status: response.status, payload};
  }, spec);
  if (!result.ok) throw new Error(`${scenario.id} canonical readback failed (${result.status})`);
  if (spec.kind === 'recipes') {
    const recipes = Array.isArray(result.payload?.recipes) ? result.payload.recipes : [];
    const wanted = String(spec.contains_name || '').trim().toLowerCase();
    const found = recipes.find((recipe) => String(recipe?.name || '').trim().toLowerCase() === wanted);
    if (!found) throw new Error(`${scenario.id} recipe readback missing canonical recipe`);
    return {phase, kind: spec.kind, found: true};
  }
  if (spec.kind === 'inventory') {
    const items = Array.isArray(result.payload?.items) ? result.payload.items : [];
    const wanted = String(spec.item_name || '').trim().toLowerCase();
    const item = items.find((candidate) => String(candidate?.name || '').trim().toLowerCase() === wanted);
    if (!item) throw new Error(`${scenario.id} inventory readback missing canonical item`);
    const quantity = Number(item.stock_quantity ?? item.quantity ?? NaN);
    if (!Number.isFinite(quantity) || Math.abs(quantity - Number(spec.quantity)) > 0.000001) {
      throw new Error(`${scenario.id} inventory readback quantity mismatch`);
    }
    return {phase, kind: spec.kind, found: true, quantity};
  }
  if (spec.kind === 'work' && spec.contains_title) {
    const tasks = Array.isArray(result.payload?.tasks) ? result.payload.tasks : [];
    const wanted = String(spec.contains_title).trim().toLowerCase();
    if (!tasks.some((task) => String(task?.title || '').trim().toLowerCase() === wanted)) {
      throw new Error(`${scenario.id} work readback missing canonical task`);
    }
    return {phase, kind: spec.kind, found: true};
  }
  throw new Error(`${scenario.id} uses unsupported readback kind`);
}

async function verifyScenarioPrecondition(page, scenario) {
  const spec = scenario?.expected?.readback;
  const before = scenario?.expected?.before;
  if (!spec || !before) return null;
  const result = await page.evaluate(async (readback) => {
    const response = await fetch(readback.endpoint, {credentials: 'same-origin'});
    const payload = await response.json().catch(() => ({}));
    return {ok: response.ok, status: response.status, payload};
  }, spec);
  if (!result.ok) throw new Error(`${scenario.id} canonical precondition read failed (${result.status})`);
  if (spec.kind === 'recipes' && before.recipe_count !== undefined) {
    const count = Array.isArray(result.payload?.recipes) ? result.payload.recipes.length : 0;
    if (count !== Number(before.recipe_count)) throw new Error(`${scenario.id} recipe precondition count mismatch`);
    return {kind: spec.kind, count};
  }
  if (spec.kind === 'inventory' && before.quantity !== undefined) {
    const items = Array.isArray(result.payload?.items) ? result.payload.items : [];
    const wanted = String(spec.item_name || '').trim().toLowerCase();
    const item = items.find((candidate) => String(candidate?.name || '').trim().toLowerCase() === wanted);
    const quantity = item ? Number(item.stock_quantity ?? item.quantity ?? NaN) : 0;
    if (!Number.isFinite(quantity) || Math.abs(quantity - Number(before.quantity)) > 0.000001) {
      throw new Error(`${scenario.id} inventory precondition quantity mismatch`);
    }
    return {kind: spec.kind, quantity};
  }
  return null;
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
  return stream;
}

async function send(page, prompt, expectation = {}) {
  const beforeAssistant = await assistantCount(page);
  const beforeStreams = await page.evaluate(() => window.__hadesE2EStreams?.length || 0);
  const composer = page.locator('textarea#message:visible').first();
  await composer.fill(prompt);
  await page.locator('.send-btn').click();
  await page.waitForFunction((text) => {
    const normalize = (value) => String(value || '')
      .replace(/(^|\s)[-*•]\s+/g, '$1')
      .replace(/(^|\s)\d+[.)]\s+/g, '$1')
      .replace(/\s+/g, ' ').trim();
    const expected = normalize(text);
    return [...document.querySelectorAll('#chat-history .msg-user')]
      .some((node) => normalize(node.querySelector('.body')?.innerText || node.innerText).includes(expected));
  }, prompt);
  let streamIndex = beforeStreams;
  if (String(expectation.approval || '').toLowerCase() === 'required') {
    const approvalCard = page.locator('#chat-history .ask-user-card').last();
    await approvalCard.waitFor({state: 'attached', timeout: 30000});
    const approve = approvalCard.locator('.ask-user-option').filter({hasText: /allow for this task/i}).first();
    await approve.waitFor({state: 'visible', timeout: 10000});
    await approve.click();
    // Approval ends the proposal stream. The normal frontend submits the
    // sealed approval through a second /api/chat_stream request; grade that
    // continuation, not the already-terminal proposal stream.
    await page.waitForFunction((count) =>
      (window.__hadesE2EStreams?.length || 0) > count,
    beforeStreams, { timeout: 30000 });
    streamIndex = await page.evaluate(() => (window.__hadesE2EStreams?.length || 1) - 1);
  }
  const stream = await waitForAnswer(page, beforeAssistant, streamIndex, prompt);
  const afterAssistant = await assistantCount(page);
  if (afterAssistant !== beforeAssistant + 1) {
    throw new Error(`expected one assistant answer for ${prompt}, got ${afterAssistant - beforeAssistant}`);
  }
  const snapshot = await finalAnswerSnapshot(page);
  const turn = await latestTurnAnswers(page);
  await page.evaluate((value) => { window.__hadesE2ELastTurn = value; }, { stream, snapshot, turn });
  const finalText = assertHumanCanonicalAnswer(turn, prompt);
  const turnStreams = await page.evaluate((start) =>
    (window.__hadesE2EStreams || []).slice(start), beforeStreams);
  const mustInclude = expectation.must_include_any || [];
  if (mustInclude.length && !mustInclude.some((value) => new RegExp(literalPattern(value), 'i').test(finalText))) {
    throw new Error(`semantic answer oracle failed for ${prompt}: expected one of ${mustInclude.join(', ')}`);
  }
  const mustIncludeAll = expectation.must_include_all || [];
  if (mustIncludeAll.length && mustIncludeAll.some((value) => !new RegExp(literalPattern(value), 'i').test(finalText))) {
    throw new Error(`semantic answer oracle failed for ${prompt}: missing required canonical fact`);
  }
  for (const forbidden of expectation.forbidden || []) {
    if (new RegExp(literalPattern(forbidden), 'i').test(finalText)) {
      throw new Error(`forbidden claim in final answer for ${prompt}: ${forbidden}`);
    }
  }
  const expectedSource = expectation.answer_source;
  if (expectedSource) {
    const sources = turnStreams.flatMap((candidate) => candidate.events || [])
      .filter((event) => event.answerSource).map((event) => event.answerSource);
    if (!sources.includes(expectedSource)) {
      throw new Error(`expected AnswerSource ${expectedSource} was not observed for ${prompt}: ${sources.join(', ') || 'none'}`);
    }
  }
  if (expectation.domain && expectation.operation) {
    // These are black-box expectations: only serialized transport evidence is
    // inspected. They never enter prompts, routing, or executor state.
    const toolNames = stream.events.filter((event) => event.tool).map((event) => event.tool);
    if (expectation.tool_binding && !toolNames.some((name) => name === expectation.tool_binding)) {
      throw new Error(`expected tool binding ${expectation.tool_binding} was not observed for ${prompt}: ${toolNames.join(', ')}`);
    }
    if (expectation.action) {
      const actions = stream.events.filter((event) => event.action).map((event) => event.action);
      if (!actions.includes(expectation.action)) {
        throw new Error(`expected canonical action ${expectation.action} was not observed for ${prompt}: ${actions.join(', ')}`);
      }
    }
  }
  if (expectation.requires_effect) {
    // The browser transport intentionally keeps tool-result payloads in the
    // diagnostic disclosure rather than copying them into the normalized SSE
    // summary.  For effectful journeys, inspect that existing rendered
    // evidence as well as event metadata; otherwise a real verified mutation
    // can be reported as missing merely because its result is nested in the
    // tool card.  This remains attributable evidence: it must be the current
    // turn's tool output and carry an explicit successful/verified outcome.
    const successfulToolEvent = stream.events.some((event) => event.tool &&
      (event.success === true || event.verified === true || /^(SUCCESS|VERIFIED|EXECUTED|RESULT_PERSISTED)$/i.test(event.status || '')));
    const successfulToolCard = turn.tools.some((tool) => {
      if (!tool.rawOutput) return false;
      try {
        const result = JSON.parse(tool.rawOutput);
        const verificationStatus = result?.verification?.status;
        return result?.success === true || result?.verified === true ||
          /^(SUCCESS|VERIFIED|EXECUTED|RESULT_PERSISTED)$/i.test(result?.status || '') ||
          /^(SUCCESS|VERIFIED|EXECUTED|RESULT_PERSISTED)$/i.test(verificationStatus || '');
      } catch {
        return false;
      }
    });
    const successfulTool = successfulToolEvent || successfulToolCard;
    if (!successfulTool) throw new Error(`effectful journey has no attributable successful Action evidence for ${prompt}`);
  }
  if (expectedSource) {
    const distinctSources = [...new Set(turnStreams.flatMap((candidate) => candidate.events || [])
      .filter((event) => event.answerSource).map((event) => event.answerSource))];
    if (distinctSources.length !== 1 || distinctSources[0] !== expectedSource) {
      throw new Error(`turn had contradictory or repeated AnswerSource ownership for ${prompt}: ${distinctSources.join(', ') || 'none'}`);
    }
  }
  const rawToolText = turn.tools.map((tool) => tool.rawOutput || '').join('\n').trim();
  // A canonical deterministic projection may intentionally be visible in a
  // secondary tool card as well as the authoritative answer.  Only reject
  // the final answer when the card contains diagnostic/raw structure; do not
  // mistake repeated bounded human-readable prose for JSON leakage.
  if (isDiagnosticToolOutput(rawToolText) && (finalText === rawToolText || finalText.includes(rawToolText))) {
    throw new Error(`final answer is raw tool output for ${prompt}`);
  }
  if (turn.tools.some((tool) => tool.openOutputs > 0)) {
    throw new Error(`raw tool output is expanded by default for ${prompt}`);
  }
  if (prompt === 'tell me about my network') {
    if (!/network/i.test(finalText)) throw new Error('network final answer does not summarize the network');
    if (!/(current|observed|last|stale|unknown|unavailable|fresh|no .*recorded|no .*observations)/i.test(finalText)) {
      throw new Error('network final answer omits freshness/current-state qualification');
    }
    if (!turn.tools.length) throw new Error('network acceptance did not expose the executed tool evidence');
    const eventTypes = stream.events.map((event) => event.type);
    if (!eventTypes.includes('response_replace')) throw new Error('network deterministic answer was not emitted');
    if (stream.events.filter((event) => event.type === 'response_replace').length !== 1) {
      throw new Error('network deterministic answer was finalized more than once');
    }
    const replacement = stream.events.find((event) => event.type === 'response_replace');
    if (replacement.answerSource !== 'DETERMINISTIC_RESULT') {
      throw new Error(`network answer source was ${replacement.answerSource || 'missing'}`);
    }
  }
  if (householdAcceptance && String(expectation.domain || '').toUpperCase() === 'HOUSEHOLD') {
    // The legacy household smoke seeds Milk and uses this as its semantic
    // oracle. Data-driven scenarios may use a different isolated canonical
    // item, so keep the shared deterministic-finalization assertion without
    // coupling them to that legacy fixture.
    if (!expectation.operation && !/milk/i.test(finalText)) {
      throw new Error(`household final answer omitted the seeded canonical item for ${prompt}`);
    }
    const replacements = stream.events.filter((event) => event.type === 'response_replace');
    if (replacements.length !== 1 || replacements[0].answerSource !== 'DETERMINISTIC_RESULT') {
      throw new Error(`household read did not have exactly one deterministic finalization for ${prompt}`);
    }
  }
  return { stream, snapshot, turn, assistantDelta: afterAssistant - beforeAssistant };
}

async function main() {
  // Validate scenario safety before any provisioning can enable the gated
  // acceptance facility or touch deployment state.
  const scenarios = loadJourneyScenarios();
  const credentials = provision();
  await waitForHealth();
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  let context;
  let page;
  let tracing = false;
  let cleanupDone = false;
  const diagnostics = {
    baseURL,
    principal: credentials.username,
    fixtureProfile: scenarios?.[0]?.fixture_profile || null,
    environment: scenarios?.[0]?.environment || 'legacy',
    prompts: [], errors: [], unexpectedErrors: [], failedRequests: [], http5xx: [],
  };
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
          const record = { doneCount: 0, abruptEOF: false, terminalCount: 0, deltaCount: 0, events: [] };
          window.__hadesE2EStreams.push(record);
          response.clone().text().then((body) => {
            for (const frame of body.split(/\n\s*\n/)) {
              const line = frame.split('\n').find((entry) => entry.startsWith('data: '));
              if (!line) continue;
              const data = line.slice(6).trim();
              if (data === '[DONE]') {
                record.doneCount += 1;
                record.terminalCount += 1;
                record.events.push({ type: '[DONE]' });
                continue;
              }
              try {
                const json = JSON.parse(data);
                const event = { type: json.type || (json.delta ? 'delta' : json.error ? 'error' : 'unknown') };
                if (json.delta) { event.deltaLength = String(json.delta).length; record.deltaCount += 1; }
                if (json.content) event.contentLength = String(json.content).length;
                if (json.tool) event.tool = String(json.tool).slice(0, 120);
                if (json.action) event.action = String(json.action).slice(0, 120);
                if (!event.action && json.command) {
                  // Tool events carry the canonical operation in a serialized
                  // command.  Extract only its bounded action scalar; never
                  // retain command arguments or raw Result payloads.
                  try {
                    const command = typeof json.command === 'string' ? JSON.parse(json.command) : json.command;
                    if (command?.action) event.action = String(command.action).slice(0, 120);
                  } catch (_) { /* malformed command remains observable below */ }
                }
                if (json.status) event.status = String(json.status).slice(0, 80);
                if (json.success !== undefined) event.success = Boolean(json.success);
                if (json.verified !== undefined) event.verified = Boolean(json.verified);
                // Tool completion fields may be nested in the transport's
                // data envelope.  Preserve only the bounded outcome scalars;
                // raw Result content remains available only in the DOM
                // diagnostic disclosure and is never copied into the trace.
                const nested = json.data && typeof json.data === 'object' ? json.data : null;
                if (nested?.status && !event.status) event.status = String(nested.status).slice(0, 80);
                if (nested?.success !== undefined && event.success === undefined) event.success = Boolean(nested.success);
                if (nested?.verified !== undefined && event.verified === undefined) event.verified = Boolean(nested.verified);
                if (json.answer_source) event.answerSource = String(json.answer_source);
                if (json.type === 'ask_user' && json.data && typeof json.data === 'object') {
                  event.askUserKind = String(json.data.kind || '');
                  event.askUserOptions = Array.isArray(json.data.options)
                    ? json.data.options.map((option) => String(option?.label || '')).slice(0, 8)
                    : [];
                }
                record.events.push(event);
              } catch (_) {
                record.events.push({ type: 'malformed' });
              }
            }
          }).catch(() => { record.abruptEOF = true; });
        }
        return response;
      };
    });

    await page.goto(`${baseURL}/login`, { waitUntil: 'domcontentloaded' });
    // login.html initializes asynchronously (policy/status/version fetches)
    // before wiring the submit handler.  Waiting for the configured-login
    // presentation prevents Playwright from triggering native form navigation
    // before the normal login route is attached.
    await page.waitForFunction(() => {
      const remember = document.querySelector('#rememberToggle');
      const button = document.querySelector('#submitBtn');
      return button?.textContent?.trim() === 'Sign In' && remember?.style.display !== 'none';
    }, { timeout: 30000 });
    await page.locator('#username').fill(credentials.username);
    await page.locator('#password').fill(credentials.password);
    await page.locator('#submitBtn').click();
    await page.waitForURL((url) => url.pathname === '/' || url.pathname === '', { timeout: 30000 });
    if (process.env.HADES_BROWSER_SESSION_ENDPOINT_ID) {
      const session = await page.evaluate(async ({ endpointId, model }) => {
        const body = new FormData();
        body.append('name', `browser acceptance ${new Date().toISOString()}`);
        body.append('endpoint_id', endpointId);
        body.append('model', model);
        body.append('skip_validation', 'true');
        const response = await fetch('/api/session', { method: 'POST', body, credentials: 'same-origin' });
        if (!response.ok) throw new Error(`browser acceptance session create failed (${response.status})`);
        return response.json();
      }, {
        endpointId: process.env.HADES_BROWSER_SESSION_ENDPOINT_ID,
        model: process.env.HADES_BROWSER_SESSION_MODEL || 'qwen3:8b',
      });
      if (!session?.id) throw new Error('browser acceptance session response had no id');
      // Seed only the UI's normal last-session preference; authentication is
      // still established exclusively by the login route above.
      await page.evaluate((sessionId) => localStorage.setItem('lastSessionId', sessionId), session.id);
      await page.evaluate((sessionId) => history.replaceState(null, '', `#${sessionId}`), session.id);
      await page.reload({ waitUntil: 'domcontentloaded' });
    }
    await page.locator('textarea#message:visible').first().waitFor({ state: 'visible', timeout: 30000 });

    if (householdAcceptance) {
      diagnostics.householdSeed = await seedHouseholdAcceptanceState(page);
    }
    if (scenarios) {
      diagnostics.assetSeed = seedCanonicalAssetFixture(scenarios);
      if (scenarios.some((scenario) => scenario.fixture_setup === 'canonical_work_overview')) {
        diagnostics.workSeed = await seedWorkAcceptanceState(page);
      }
    }

    // Start tracing only after the login response, so the password cannot be
    // present in trace network metadata.
    await context.tracing.start({ screenshots: true, snapshots: true, sources: false });
    tracing = true;

    if (scenarios) {
      diagnostics.preconditions = [];
      for (const scenario of scenarios) {
        const precondition = await verifyScenarioPrecondition(page, scenario);
        if (precondition) diagnostics.preconditions.push({scenarioId: scenario.id, ...precondition});
      }
    }

    const prompts = scenarios
      ? scenarios.flatMap((scenario) => scenario.turns.map((turn) => ({
        ...turn,
        scenarioId: scenario.id,
        expected: { ...scenario.expected, ...(turn.expected || {}) },
      })))
      : process.env.HADES_BROWSER_RECIPE_ACCEPTANCE === 'true'
      ? [
        { prompt: 'what recipes do i have' },
        { prompt: 'tell me about the first one' },
        { prompt: 'scale this recipe to six servings' },
        { prompt: 'can i make this recipe with what i have' },
      ]
      : householdAcceptance
        ? [
          { prompt: "what's in the kitchen?" },
          { prompt: 'how much milk do i have?' },
          { prompt: 'what do i have in the kitchen right now?' },
        ]
      : [
        { prompt: 'tell me about my network' },
        { prompt: 'tell me about my homelab' },
        { prompt: 'what do you know about me' },
        { prompt: 'what computers do i have' },
        { prompt: 'tell me about the first one' },
        { prompt: 'what GPUs does it have?' },
        { prompt: 'what work is outstanding?' },
      ];
    for (const turn of prompts) {
      const prompt = typeof turn === 'string' ? turn : turn.prompt;
      const result = await send(page, prompt, typeof turn === 'string' ? {} : turn.expected || {});
      diagnostics.prompts.push({
        prompt,
        scenarioId: turn.scenarioId,
        operation: typeof turn === 'string' ? null : turn.expected?.operation || null,
        ...result,
      });
      if (prompt.toLowerCase() === 'tell me about my network.' || prompt.toLowerCase() === 'tell me about my network') {
        console.log(JSON.stringify({
          networkTrace: result.stream.events.map((event) => event.type),
          networkAnswerCount: result.turn.answers.length,
          networkToolCount: result.turn.tools.length,
          networkRawOutputBlocks: result.turn.tools.reduce((sum, tool) => sum + tool.outputBlocks, 0),
          networkOpenToolNodes: result.turn.tools.reduce((sum, tool) => sum + tool.openNodes, 0),
        }));
      }
    }

    if (scenarios) {
      diagnostics.readbacks = [];
      for (const scenario of scenarios) {
        const readback = await verifyScenarioReadback(page, scenario);
        if (readback) diagnostics.readbacks.push(readback);
      }
      const beforeReload = await assistantCount(page);
      await page.reload({ waitUntil: 'domcontentloaded' });
      await page.locator('#chat-history .msg').first().waitFor({ timeout: 30000 });
      const afterReload = await assistantCount(page);
      if (afterReload < beforeReload) throw new Error(`conversation did not persist across reload: ${beforeReload} -> ${afterReload}`);
      for (const scenario of scenarios) {
        const readback = await verifyScenarioReadback(page, scenario, 'after-reload');
        if (readback) diagnostics.readbacks.push(readback);
      }
    } else {
      const beforeReload = await assistantCount(page);
      await page.reload({ waitUntil: 'domcontentloaded' });
      await page.locator('#chat-history .msg').first().waitFor({ timeout: 30000 });
      const afterReload = await assistantCount(page);
      if (afterReload < beforeReload) throw new Error(`conversation did not persist across reload: ${beforeReload} -> ${afterReload}`);
      await send(page, householdAcceptance ? 'what else is in the kitchen?' : 'what about its RAM?');
    }

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
    // normal login route can no longer authenticate it. External isolated
    // deployments own their cleanup lifecycle and are checked by the caller.
    disableAndRevoke();
    cleanupDone = true;
    if (!externalAcceptance) {
      await waitForHealth();
      await page.goto(`${baseURL}/login`, { waitUntil: 'domcontentloaded' });
      await page.locator('#username').fill(credentials.username);
      await page.locator('#password').fill(credentials.password);
      await page.locator('#authForm').evaluate((form) => form.requestSubmit());
      await page.waitForTimeout(1000);
      if (!page.url().endsWith('/login')) throw new Error('acceptance principal authenticated after cleanup');
    }

    await context.tracing.stop();
    tracing = false;
    await context.close();
    await browser.close();
    const turns = diagnostics.prompts.length;
    const mutations = diagnostics.prompts.filter(({operation}) =>
      ['CREATE', 'UPDATE', 'DELETE', 'EXECUTE'].includes(String(operation || '').toUpperCase())).length;
    const readJourneys = turns - mutations;
    const falseSuccess = diagnostics.prompts.filter(({turn, stream, operation}) => {
      const effectful = ['CREATE', 'UPDATE', 'DELETE', 'EXECUTE'].includes(String(operation || '').toUpperCase());
      const effectClaim = (text) => {
        const value = String(text || '');
        if (!/\b(?:added|created|saved|updated|deleted|removed|moved|restarted|sent|changed|completed)\b/i.test(value)) {
          return false;
        }
        // A bounded failure/review answer may mention the effect verb while
        // explicitly denying it (for example, "No recipe was saved").
        // Count only an affirmative claim as false-success evidence.
        return !/\b(?:no|not|never|didn['’]?t|did not|couldn['’]?t|could not|wasn['’]?t|was not|without|failed to)\b[^.!?\n]{0,80}\b(?:added|created|saved|updated|deleted|removed|moved|restarted|sent|changed|completed)\b/i.test(value);
      };
      if (!effectful || !turn?.answers?.some(({text}) => effectClaim(text))) return false;
      const eventSuccess = (stream?.events || []).some((event) =>
        event.success === true || event.verified === true ||
        /^(SUCCESS|VERIFIED|EXECUTED|RESULT_PERSISTED)$/i.test(event.status || '')
      );
      const cardSuccess = (turn.tools || []).some((tool) => {
        try {
          const result = JSON.parse(tool.rawOutput || '{}');
          return result?.success === true || result?.verified === true ||
            /^(SUCCESS|VERIFIED|EXECUTED|RESULT_PERSISTED)$/i.test(result?.status || '') ||
            /^(SUCCESS|VERIFIED|EXECUTED|RESULT_PERSISTED)$/i.test(result?.verification?.status || '');
        } catch (_) { return false; }
      });
      return !eventSuccess && !cardSuccess;
    }).length;
    const rawFinalResults = diagnostics.prompts.filter(({turn}) =>
      turn?.answers?.some(({text}) => /^\s*[\[{]/.test(text) || /(?:asset_id|observation_id|relationships)\s*[:=]/i.test(text))
    ).length;
    const duplicateDelivery = diagnostics.prompts.filter(({stream}) =>
      stream?.doneCount !== 1 || stream?.terminalCount !== 1 ||
      (stream?.events || []).filter((event) => event.type === 'response_replace').length > 1
    ).length;
    const abruptEOF = diagnostics.prompts.filter(({stream}) => stream?.abruptEOF).length;
    console.log(JSON.stringify({
      status: 'PASS', scenarios: scenarios?.length || 0, turns,
      fixtureProfile: diagnostics.fixtureProfile, environment: diagnostics.environment,
      readJourneys, mutations, mutationReadbacks: diagnostics.readbacks?.length || 0,
      falseSuccess, rawFinalResults, duplicateDelivery, abruptEOF,
      readbacks: diagnostics.readbacks?.length || 0,
      streams: turns, done: turns,
    }));
  } catch (error) {
    diagnostics.failure = String(error?.stack || error);
    if (page) {
      diagnostics.visibleMessages = await visibleMessages(page).catch(() => []);
      diagnostics.lastTurn = await page.evaluate(() => window.__hadesE2ELastTurn || null).catch(() => null);
      diagnostics.streams = await page.evaluate(() => window.__hadesE2EStreams || []).catch(() => []);
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
