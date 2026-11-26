'use strict';

/*
 * REAL Chromium validation. Run only after the parent generates proof.html,
 * its embedded fonts, and browser/. No builders, installs or downloads run.
 *
 * node documentation/proofs/double-storey-g-incoming-spacing/test_browser.js \
 *   /opt/homebrew/lib/python3.11/site-packages/playwright/driver/package
 *
 * The package argument is optional: default require('playwright'). An optional
 * --executable=/absolute/path selects an already-installed Chromium executable.
 * Headless, offline, HTTP/HTTPS blocked, 1440 × 1000 CSS px, DPR 1. Playwright's
 * temporary profile/artifacts live under browser/ and are removed after closing.
 * Launch: 15 s; complete run: 180 s; close/cleanup: 5 s. The caller should also
 * bound the process. Outputs: browser/validation.json and five reading PNGs.
 * A syntax check is NOT a browser pass; only the generated report records one.
 */

const assert = require('node:assert/strict');
const {createHash} = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');

const WEIGHTS = [100, 200, 300, 400, 500, 600, 700, 800, 900];
const SLIGHT = [20, 22, 23, 24, 26, 27, 29, 30, 32];
const APPROVED_B = [40, 43, 45, 48, 51, 54, 57, 60, 64];
const GJ_CORRECTION = [0, 0, 0, 0, 0, 0, 8, 27, 40];
const SCOPES = ['ng-only', 'stems'];
const SIZES = [12, 16, 24];
const VARIANTS = ['current', 'slight', 'tighter'];
const HEADINGS = ['Current', 'Slightly tighter', 'Tighter'];
const TAGS = Array.from({length: 10}, (_, index) => 'ss' + (11 + index));
const PAIRS = ['ng', 'hg', 'mg', 'ug', 'og', 'ag', 'rg', 'go', 'ge', 'gc', 'gj', 'ngj', 'ngo'];
const WORDS = ['Morning', 'beginning', 'changing', 'going'];
const BASELINE_RUNS = [...PAIRS, 'g', 'n', 'h', 'm', 'u', 'g ', 'g\u00a0g', 'g g', 'ng ng hg mg ug'];
const SHOTS = [[400, 'ng-only', 16], [400, 'ng-only', 24], [400, 'stems', 24], [900, 'ng-only', 24], [900, 'stems', 24]];
const VIEWPORT = {width: 1440, height: 1000};
const UPM = 2048;
const TOLERANCE = 0.05;
const LAUNCH_TIMEOUT = 15000;
const ACTION_TIMEOUT = 12000;
const RUN_TIMEOUT = 180000;
const CLOSE_TIMEOUT = 5000;

function argumentsFromCLI() {
  let packagePath;
  let executablePath;
  for (const arg of process.argv.slice(2)) {
    if (arg.startsWith('--executable=')) {
      assert.ok(!executablePath, 'Only one --executable is allowed');
      executablePath = arg.slice('--executable='.length);
      assert.ok(path.isAbsolute(executablePath), '--executable must be an absolute path');
    } else {
      assert.ok(!arg.startsWith('--') && !packagePath, 'Expected an optional package path and optional --executable=...');
      packagePath = path.resolve(arg);
    }
  }
  return {packagePath, executablePath};
}

function bounded(promise, milliseconds, label) {
  let timer;
  return Promise.race([
    promise,
    new Promise((_, reject) => { timer = setTimeout(() => reject(new Error(label + ' exceeded ' + milliseconds + ' ms')), milliseconds); }),
  ]).finally(() => clearTimeout(timer));
}

function expectedFlags(scope, variant) {
  const enabled = ['ss15', 'ss17', 'ss19'];
  if (variant !== 'current') enabled.push(scope === 'ng-only' ? (variant === 'slight' ? 'ss11' : 'ss12') : (variant === 'slight' ? 'ss13' : 'ss14'));
  return TAGS.map(tag => Number(enabled.includes(tag)));
}

function featureFlags(value) {
  // Computed CSS may serialize an explicit 1 as an omitted value (on).
  const entries = value.split(',').map(part => {
    const match = part.trim().match(/^["'](ss\d{2})["'](?:\s+(\d+|on|off))?$/);
    assert.ok(match, 'Unexpected computed feature settings: ' + value);
    return [match[1], match[2] === undefined || match[2] === 'on' ? 1 : match[2] === 'off' ? 0 : Number(match[2])];
  });
  assert.equal(entries.length, 10, 'All ten feature flags must be explicit');
  assert.equal(new Set(entries.map(([tag]) => tag)).size, 10, 'No duplicate feature tags');
  assert.deepEqual(entries.map(([tag]) => tag).sort(), TAGS);
  const values = Object.fromEntries(entries);
  return TAGS.map(tag => values[tag]);
}

function incomingCount(text, scope) {
  const preceding = scope === 'ng-only' ? 'n' : 'nhmu';
  let count = 0;
  for (let index = 0; index + 1 < text.length; index++) {
    if (preceding.includes(text[index]) && text[index + 1] === 'g') count++;
  }
  return count;
}

async function waitForFontStatus(page, weight) {
  await page.waitForFunction(expected => {
    const status = document.getElementById('fontStatus');
    if (!status) throw new Error('Missing #fontStatus');
    if (['failed', 'unavailable'].includes(status.dataset.state)) throw new Error(status.textContent);
    return status.dataset.state === 'ready' && status.dataset.weight === String(expected);
  }, weight, {timeout: ACTION_TIMEOUT});
}

async function installMeasurementHelpers(page) {
  await page.evaluate(() => {
    const byId = id => {
      const node = document.getElementById(id);
      if (!node) throw new Error('Missing #' + id);
      return node;
    };
    const properties = ['fontFamily', 'fontWeight', 'fontSize', 'fontStyle', 'fontStretch', 'fontSynthesis',
      'fontVariant', 'fontKerning', 'fontFeatureSettings', 'fontVariationSettings', 'letterSpacing',
      'wordSpacing', 'textAlign', 'textTransform', 'lineHeight', 'whiteSpace', 'hyphens', 'wordBreak', 'overflowWrap'];
    const typography = node => {
      const style = getComputedStyle(node);
      return Object.fromEntries(properties.map(property => [property, style[property]]));
    };
    const box = node => {
      const rect = node.getBoundingClientRect();
      return {x: rect.x, y: rect.y, width: rect.width, height: rect.height};
    };
    const firstTextY = node => {
      if (!node.firstChild || !node.firstChild.textContent.length) return null;
      const range = document.createRange();
      range.setStart(node.firstChild, 0);
      range.setEnd(node.firstChild, 1);
      return range.getBoundingClientRect().y;
    };
    const measure = (source, text, features) => {
      // Isolated DOM text runs, not canvas, ink bounds, or a full-width paragraph
      // box. Preserve shaping within each line; sum explicit lines without wraps.
      const style = typography(source);
      let total = 0;
      for (const line of text.split(/\r\n?|\n/)) {
        const probe = document.createElement('span');
        Object.assign(probe.style, style, {position: 'fixed', left: '-100000px', top: '0',
          display: 'inline-block', width: 'max-content', maxWidth: 'none', margin: '0',
          padding: '0', border: '0', whiteSpace: 'pre', visibility: 'hidden', pointerEvents: 'none'});
        if (features !== undefined) probe.style.fontFeatureSettings = features;
        probe.textContent = line;
        document.body.append(probe);
        try { total += probe.getBoundingClientRect().width; } finally { probe.remove(); }
      }
      return total;
    };
    const snapshot = () => ({
      controls: Object.fromEntries(['weight', 'scope', 'readingSize'].map(id => [id, byId(id).value])),
      status: {...byId('fontStatus').dataset, text: byId('fontStatus').textContent},
      passage: byId('words').value,
      summary: byId('readingSummary').textContent,
      scopeNote: byId('scopeNote').textContent,
      grids: ['pairGrid', 'readingGrid'].map(id => ({id, box: box(byId(id)), columns: Array.from(byId(id).children, column => ({
        variant: column.dataset.variant, box: box(column),
        rows: Array.from(column.children, child => ({id: child.id, text: child.textContent, box: box(child)})),
      }))})),
      features: ['current', 'slight', 'tighter'].map(variant => byId('features-' + variant).textContent),
      samples: Array.from(document.querySelectorAll('.font-sample'), sample => ({
        id: sample.id, variant: sample.dataset.variant, run: sample.dataset.run || null,
        text: sample.textContent, childElements: sample.children.length, style: typography(sample),
        box: box(sample), firstTextY: firstTextY(sample), width: measure(sample, sample.textContent),
      })),
    });
    const baseline = runs => {
      const source = byId('pair-current-ng');
      const off = Array.from({length: 10}, (_, index) => '"ss' + (11 + index) + '" 0').join(', ');
      return runs.map(text => ({text, current: measure(source, text),
        explicitOff: measure(source, text, off), normal: measure(source, text, 'normal')}));
    };
    window.__incomingTest = {snapshot, baseline};
  });
}

async function main() {
  const options = argumentsFromCLI();
  const proofPath = path.join(__dirname, 'proof.html');
  const outputDirectory = path.join(__dirname, 'browser');
  assert.ok(fs.existsSync(outputDirectory) && fs.lstatSync(outputDirectory).isDirectory(), 'The parent must create a real browser/ directory first');
  const report = {
    status: 'running', proof: 'proof.html', proofSha256: null, browserVersion: null,
    renderer: {engine: 'Chromium / Blink', mode: 'headless', platform: process.platform,
      package: options.packagePath || 'playwright', executable: null, offline: true, httpHttpsBlocked: true, temporaryProfile: true},
    viewport: {...VIEWPORT, deviceScaleFactor: 1}, unitsPerEm: UPM, toleranceCssPx: TOLERANCE,
    timeoutsMs: {launch: LAUNCH_TIMEOUT, action: ACTION_TIMEOUT, run: RUN_TIMEOUT, close: CLOSE_TIMEOUT},
    expectedCoverage: {weights: WEIGHTS, scopes: SCOPES, sizesCssPx: SIZES, states: 54, screenshots: 5},
    counts: {casesStarted: 0, casesPassed: 0, casesFailed: 0, assertions: 0, states: 0,
      resolvedFontLoads: 0, loadedFontFaces: 0, baselineWeights: 0, screenshots: 0},
    cases: [], fonts: [], states: [], baselines: [], screenshots: [],
    consoleErrors: [], pageErrors: [], failedRequests: [], blockedRequests: [], fontLoadingErrors: [],
    limits: 'Width/layout checks do not verify drawings, establish optical approval, or select a final setting. Font-table validation belongs to the parent build report.',
  };
  const check = {
    equal(actual, expected, label) { report.counts.assertions++; assert.equal(actual, expected, label); },
    deepEqual(actual, expected, label) { report.counts.assertions++; assert.deepEqual(actual, expected, label); },
    ok(value, label) { report.counts.assertions++; assert.ok(value, label); },
    near(actual, expected, label, tolerance = TOLERANCE) {
      report.counts.assertions++;
      assert.ok(Number.isFinite(actual) && Number.isFinite(expected) && Math.abs(actual - expected) <= tolerance,
        label + ': expected ' + expected + ' CSS px, got ' + actual + ' (tolerance ' + tolerance + ')');
    },
  };
  async function test(name, fn) {
    const record = {name, status: 'running'};
    report.cases.push(record);
    report.counts.casesStarted++;
    try {
      await fn();
      record.status = 'passed';
      report.counts.casesPassed++;
    } catch (error) {
      record.status = 'failed';
      record.error = error.message;
      report.counts.casesFailed++;
      throw error;
    }
  }
  let browser;
  let failure;
  let closing = false;
  let cleanupFinished = true;
  let runtimeDirectory;
  const temporaryEnvironment = Object.fromEntries(['TMPDIR', 'TMP', 'TEMP'].map(key => [key, process.env[key]]));
  const hardStop = setTimeout(() => {
    console.error('Browser validation exceeded its total run/cleanup budget.');
    process.exit(1);
  }, RUN_TIMEOUT + CLOSE_TIMEOUT + 2000);
  hardStop.unref();

  async function run() {
    check.ok(fs.existsSync(proofPath), 'The parent must generate proof.html first');
    const html = fs.readFileSync(proofPath, 'utf8');
    report.proofSha256 = createHash('sha256').update(html).digest('hex');
    const match = html.match(/^const config = (.+);$/m);
    check.ok(match, 'Expected the renderer’s safely serialized config');
    const config = JSON.parse(match[1]);
    await test('font and renderer configuration contract', async () => {
      check.deepEqual(config.weights.map(entry => entry.weight), WEIGHTS, 'Exactly nine weights');
      check.deepEqual(config.weights.map(entry => entry.slight), SLIGHT, 'Exact slight amounts');
      check.deepEqual(config.weights.map(entry => entry.tighter), SLIGHT.map(amount => 2 * amount), 'Exact stronger amounts');
      check.ok(config.weights.every(entry => typeof entry.style === 'string' && entry.style.trim()), 'Style labels');
      check.ok(Array.isArray(config.paragraphs) && config.paragraphs.length && config.paragraphs.every(text => typeof text === 'string'), 'Literal paragraphs');
      check.deepEqual(WORDS.map(word => incomingCount(word, 'ng-only')), [1, 1, 2, 1], 'Independent focus-word occurrence counts');
    });

    // Both Node/driver mkdtemp calls and Chromium inherit this local temp root.
    runtimeDirectory = fs.mkdtempSync(path.join(outputDirectory, '.playwright-'));
    for (const key of Object.keys(temporaryEnvironment)) process.env[key] = runtimeDirectory;
    const {chromium} = require(options.packagePath || 'playwright');
    check.ok(chromium && typeof chromium.launch === 'function', 'Expected Playwright chromium');
    report.renderer.executable = options.executablePath || chromium.executablePath();
    browser = await chromium.launch({headless: true, timeout: LAUNCH_TIMEOUT,
      downloadsPath: runtimeDirectory, env: {...process.env},
      ...(options.executablePath ? {executablePath: options.executablePath} : {})});
    report.browserVersion = browser.version();
    const context = await browser.newContext({viewport: VIEWPORT, deviceScaleFactor: 1,
      isMobile: false, hasTouch: false, locale: 'en-US', colorScheme: 'light', offline: true, serviceWorkers: 'block'});
    context.setDefaultTimeout(ACTION_TIMEOUT);
    context.setDefaultNavigationTimeout(LAUNCH_TIMEOUT);
    await context.route(/^https?:\/\//i, async route => {
      report.blockedRequests.push({url: route.request().url(), method: route.request().method()});
      await route.abort('blockedbyclient');
    });
    const page = await context.newPage();
    page.on('console', message => {
      if (!closing && message.type() === 'error') report.consoleErrors.push({text: message.text(), location: message.location()});
    });
    page.on('pageerror', error => { if (!closing) report.pageErrors.push(error.stack || error.message); });
    page.on('requestfailed', request => {
      if (!closing) report.failedRequests.push({url: request.url().slice(0, 500), error: request.failure()?.errorText});
    });
    await page.addInitScript(() => {
      window.__incomingFontErrors = [];
      document.fonts.addEventListener('loadingerror', event => {
        window.__incomingFontErrors.push(Array.from(event.fontfaces, face => ({family: face.family, weight: face.weight, status: face.status})));
      });
    });
    await page.goto(pathToFileURL(proofPath).href, {waitUntil: 'load', timeout: LAUNCH_TIMEOUT});
    await installMeasurementHelpers(page);
    const settled = () => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    const snapshot = () => page.evaluate(() => window.__incomingTest.snapshot());
    async function setState(weight, scope, size) {
      await page.selectOption('#weight', String(weight));
      await page.selectOption('#scope', scope);
      await page.selectOption('#readingSize', String(size));
      await waitForFontStatus(page, weight);
      await settled();
    }
    async function loadFace(weight) {
      const faces = await page.evaluate(async value => {
        const loaded = await document.fonts.load(value + ' 64px "SpacingProof"', 'ng hg mg ug go ge gc gj');
        return loaded.map(face => ({family: face.family, weight: face.weight, style: face.style, status: face.status}));
      }, weight);
      check.equal(faces.length, 1, 'Exactly one actual embedded face, not a fallback-only fonts.check result');
      check.equal(faces[0].family.replace(/^["']|["']$/g, ''), 'SpacingProof', 'CSS font family');
      check.equal(faces[0].weight, String(weight), 'Exact weight, not nearest matching weight');
      check.equal(faces[0].style, 'normal', 'Upright face');
      check.equal(faces[0].status, 'loaded', 'Actual FontFace loaded');
      report.counts.resolvedFontLoads++;
    }

    function validateState(actual, weight, scope, size) {
      const entry = config.weights.find(item => item.weight === weight);
      check.deepEqual(actual.controls, {weight: String(weight), scope, readingSize: String(size)}, 'Shared controls');
      check.equal(actual.status.state, 'ready', 'Verified font status');
      check.equal(actual.status.weight, String(weight), 'Status is for current weight');
      check.equal(actual.passage, config.paragraphs.join('\n\n'), 'Original shared passage');
      check.ok(actual.summary.includes(size + ' CSS px') && actual.summary.includes(String(weight)), 'Screenshot identifies shared size and weight');
      check.ok(scope === 'ng-only' ? actual.scopeNote.includes('untouched controls') : /COMPARISON ONLY/.test(actual.scopeNote), 'Honest scope note');
      check.equal(actual.samples.length, 3 * (PAIRS.length + WORDS.length + 1), 'All displayed font samples covered');
      const flags = {};
      for (const [index, variant] of VARIANTS.entries()) {
        flags[variant] = expectedFlags(scope, variant);
        check.deepEqual(featureFlags(actual.features[index].slice(actual.features[index].indexOf(':') + 1)), flags[variant], variant + ' visible feature declaration');
      }
      for (const sample of actual.samples) {
        const style = sample.style;
        check.deepEqual(featureFlags(style.fontFeatureSettings), flags[sample.variant], sample.id + ' computed ten flags');
        check.equal(style.fontWeight, String(weight), sample.id + ' shared weight');
        check.equal(style.fontSize, (sample.run ? 64 : size) + 'px', sample.id + ' actual CSS size');
        check.equal(style.fontFamily.split(',')[0].replace(/["']/g, '').trim(), 'SpacingProof', sample.id + ' font family');
        check.equal(style.fontStyle, 'normal', 'No oblique');
        check.equal(style.fontSynthesis, 'none', 'No synthetic weight/style');
        check.equal(style.fontKerning, 'normal', 'Keep existing kerning');
        check.equal(style.fontVariant, 'normal', 'No additional variants');
        check.equal(style.letterSpacing, 'normal', 'No tracking');
        check.ok(['normal', '0px'].includes(style.wordSpacing), 'No extra word spacing');
        check.equal(style.textAlign, 'left', 'Natural ragged-right layout');
        check.equal(style.textTransform, 'none', 'Literal letter case');
        check.equal(style.hyphens, 'none', 'No automatic hyphenation');
        check.equal(style.overflowWrap, 'normal', 'Natural wrapping');
        check.equal(style.wordBreak, 'normal', 'No artificial word breaks');
        check.equal(sample.childElements, 0, 'No injected markup or shape-breaking nested spans');
        if (sample.id.startsWith('reading-')) check.equal(style.whiteSpace, 'pre-wrap', 'Literal paragraph breaks');
      }
      for (const grid of actual.grids) {
        check.deepEqual(grid.columns.map(column => column.variant), VARIANTS, 'Three fixed column order');
        check.deepEqual(grid.columns.map(column => column.rows[0].text), HEADINGS, 'Aligned headings');
        check.ok(grid.box.width <= VIEWPORT.width, 'No horizontal overflow at test viewport');
        const first = grid.columns[0];
        for (const column of grid.columns) {
          check.near(column.box.width, first.box.width, grid.id + ' equal column width');
          check.near(column.box.y, first.box.y, grid.id + ' equal column start');
          check.equal(column.rows.length, grid.id === 'pairGrid' ? 6 : 8, 'Aligned subgrid row count');
          column.rows.forEach((row, index) => {
            check.near(row.box.y, first.rows[index].box.y, grid.id + ' row ' + index + ' equal starts');
            check.near(row.box.x, column.box.x, grid.id + ' natural left edge');
          });
        }
        check.ok(grid.columns[1].box.x > first.box.x + first.box.width, 'Columns do not stack or overlap');
        check.ok(grid.columns[2].box.x > grid.columns[1].box.x + grid.columns[1].box.width, 'Third column stays beside the others');
      }
      const pairColumns = actual.grids[0].columns;
      actual.grids[1].columns.forEach((column, index) => {
        check.near(column.box.x, pairColumns[index].box.x, 'Pair/reading columns share left edges');
        check.near(column.box.width, pairColumns[index].box.width, 'Pair/reading columns share widths');
      });
      const runs = [];
      const groups = [...PAIRS.map(text => ({kind: 'pair', text, prefix: 'pair-', suffix: '-' + text, size: 64})),
        ...WORDS.map(text => ({kind: 'word', text, prefix: 'word-', suffix: '-' + text, size})),
        {kind: 'passage', text: actual.passage, prefix: 'reading-', suffix: '', size}];
      for (const group of groups) {
        const samples = VARIANTS.map(variant => actual.samples.find(sample => sample.id === group.prefix + variant + group.suffix));
        check.ok(samples.every(Boolean), 'Every variant supplies ' + group.kind);
        samples.forEach(sample => {
          check.equal(sample.text, group.text, 'Identical literal content across columns');
          check.near(sample.box.y, samples[0].box.y, 'Equal text block starts');
          if (sample.firstTextY !== null) check.near(sample.firstTextY, samples[0].firstTextY, 'Equal first text starts');
        });
        const occurrences = incomingCount(group.text, scope);
        const widths = Object.fromEntries(VARIANTS.map((variant, index) => [variant, samples[index].width]));
        const deltas = {slight: widths.slight - widths.current, tighter: widths.tighter - widths.current};
        const expected = -occurrences * entry.slight * group.size / UPM;
        check.near(deltas.slight, expected, group.kind + ' ' + (group.kind === 'passage' ? '' : group.text) + ' slight incoming delta');
        check.near(deltas.tighter, 2 * expected, 'Stronger delta is exactly twice the incoming amount');
        check.near(deltas.tighter, 2 * deltas.slight, 'Measured stronger/slight relationship', 2 * TOLERANCE);
        runs.push({kind: group.kind, ...(group.kind === 'passage' ? {characters: group.text.length} : {text: group.text}),
          occurrences, sizeCssPx: group.size, widthsCssPx: widths, deltasCssPx: deltas, expectedSlightDeltaCssPx: expected});
      }
      const pair = text => runs.find(run => run.kind === 'pair' && run.text === text);
      for (const variant of ['slight', 'tighter']) {
        for (const guard of ['ngj', 'ngo']) check.near(pair(guard).deltasCssPx[variant], pair('ng').deltasCssPx[variant], guard + ' delta is incoming only, not outgoing');
        for (const unchanged of ['og', 'ag', 'rg', 'go', 'ge', 'gc', 'gj', ...(scope === 'ng-only' ? ['hg', 'mg', 'ug'] : [])]) {
          check.near(pair(unchanged).deltasCssPx[variant], 0, unchanged + ' unchanged by trial');
        }
      }
      return {weight, scope, sizeCssPx: size, featureFlags: flags,
        columns: actual.grids.map(grid => ({id: grid.id, columns: grid.columns.map(column => ({variant: column.variant, ...column.box}))})), runs};
    }

    await test('initial controls, viewport, links and explicit feature states', async () => {
      await waitForFontStatus(page, 400);
      await settled();
      validateState(await snapshot(), 400, 'ng-only', 24);
      const environment = await page.evaluate(() => ({width: innerWidth, height: innerHeight, dpr: devicePixelRatio,
        scale: visualViewport.scale, zoom: getComputedStyle(document.body).zoom, userAgent: navigator.userAgent,
        options: Object.fromEntries(['weight', 'scope', 'readingSize'].map(id => [id, Array.from(document.getElementById(id).options, option => option.value)])),
        links: Array.from(document.querySelectorAll('a'), anchor => anchor.getAttribute('href'))}));
      report.environment = environment;
      check.equal(environment.width, VIEWPORT.width);
      check.equal(environment.height, VIEWPORT.height);
      check.equal(environment.dpr, 1);
      check.equal(environment.scale, 1);
      check.ok(['1', 'normal'].includes(environment.zoom), 'No CSS zoom');
      check.deepEqual(environment.options, {weight: WEIGHTS.map(String), scope: SCOPES, readingSize: SIZES.map(String)});
      for (const href of ['proof.svg', 'proof.png', 'weights.svg', 'weights.png', 'README.md', 'validation.json', 'clearances.json',
        'browser/validation.json', '../double-storey-g-spacing-finish/proof.html', '../../../OFL.txt']) {
        check.ok(environment.links.includes(href), 'Required link ' + href);
      }
    });

    for (const [index, weight] of WEIGHTS.entries()) {
      await test('loaded face and approved baseline / ' + weight, async () => {
        await setState(weight, 'ng-only', 24);
        await loadFace(weight);
        const runs = await page.evaluate(texts => window.__incomingTest.baseline(texts), BASELINE_RUNS);
        for (const run of runs) {
          check.near(run.normal, run.explicitOff, 'Standalone optional features default off: ' + run.text);
          const gCount = Array.from(run.text).filter(character => character === 'g').length;
          const rounds = (run.text.match(/g[oec]/g) || []).length;
          const gj = (run.text.match(/gj/g) || []).length;
          const expected = (-APPROVED_B[index] * (gCount + rounds) + GJ_CORRECTION[index] * gj) * 64 / UPM;
          check.near(run.current - run.explicitOff, expected, 'Approved C/B, heavy gj, and unchanged word-space policy: ' + run.text);
        }
        report.baselines.push({weight, sizeCssPx: 64, approvedB: APPROVED_B[index], gjCorrection: GJ_CORRECTION[index], runs});
        report.counts.baselineWeights++;
      });
      for (const scope of SCOPES) {
        for (const size of SIZES) {
          await test('state / ' + weight + ' / ' + scope + ' / ' + size, async () => {
            await setState(weight, scope, size);
            report.states.push(validateState(await snapshot(), weight, scope, size));
            report.counts.states++;
          });
        }
      }
    }

    await test('all nine actual FontFaces loaded', async () => {
      report.fonts = await page.evaluate(async () => {
        await document.fonts.ready;
        return Array.from(document.fonts).filter(face => face.family.replace(/^["']|["']$/g, '') === 'SpacingProof')
          .map(face => ({family: face.family, weight: face.weight, style: face.style, status: face.status}))
          .sort((a, b) => Number(a.weight) - Number(b.weight));
      });
      check.equal(report.fonts.length, 9);
      check.deepEqual(report.fonts.map(face => Number(face.weight)), WEIGHTS);
      check.ok(report.fonts.every(face => face.status === 'loaded' && face.style === 'normal'), 'No unloaded or synthesized faces');
      report.counts.loadedFontFaces = report.fonts.length;
    });

    await test('literal hostile passage, fixed controls, and passage restoration', async () => {
      const original = config.paragraphs.join('\n\n');
      const hostile = 'Morning <script>window.__incomingInjected = true;</script> & <img src="https://invalid.example/pixel" onerror="window.__incomingInjected=true"> "ng"\n\nbeginning  changing\tgoing\nng\u00a0hg mg ug </textarea> \u2028 last line';
      await page.locator('#passageEditor > summary').click();
      try {
        await page.locator('#words').fill(hostile);
        const actual = await snapshot();
        check.equal(actual.passage, hostile, 'Textarea literal value');
        for (const sample of actual.samples) {
          if (sample.id.startsWith('reading-')) {
            check.equal(sample.text, hostile, 'Literal passage in every variant');
            check.equal(sample.childElements, 0, 'No markup was interpreted');
          } else {
            check.equal(sample.text, sample.run || WORDS.find(word => sample.id.endsWith('-' + word)), 'Fixed samples unaffected');
          }
        }
        check.equal(await page.evaluate(() => typeof window.__incomingInjected), 'undefined', 'No script or event handler executed');
      } finally {
        await page.locator('#words').fill(original);
        await page.locator('#passageEditor > summary').click();
      }
      const restored = await snapshot();
      for (const sample of restored.samples.filter(sample => sample.id.startsWith('reading-'))) check.equal(sample.text, original, 'Passage restored before screenshots');
    });

    await test('real DOM font-status race: stale success/failure cannot replace newest request', async () => {
      await page.evaluate(() => {
        const descriptor = Object.getOwnPropertyDescriptor(document.fonts, 'load');
        const nativeLoad = document.fonts.load.bind(document.fonts);
        const requests = [];
        Object.defineProperty(document.fonts, 'load', {configurable: true, writable: true, value: (...args) =>
          new Promise((resolve, reject) => { requests.push({args, resolve, reject}); })});
        window.__incomingLoadRace = {
          requests,
          async release(index, fail) {
            const request = requests[index];
            if (!request) throw new Error('Missing controlled font request ' + index);
            if (fail) request.reject(new Error('Intentional controlled font-load failure'));
            else request.resolve(await nativeLoad(...request.args));
          },
          restore() {
            if (descriptor) Object.defineProperty(document.fonts, 'load', descriptor);
            else delete document.fonts.load;
          },
        };
      });
      const change = value => page.evaluate(weight => {
        const select = document.getElementById('weight');
        select.value = String(weight);
        select.dispatchEvent(new Event('change', {bubbles: true}));
      }, value);
      const release = (index, fail) => page.evaluate(({index, fail}) => window.__incomingLoadRace.release(index, fail), {index, fail});
      const state = () => page.locator('#fontStatus').getAttribute('data-state');
      try {
        await change(400); await change(900); await change(400);
        check.equal(await state(), 'loading');
        await release(2, true);
        check.equal(await state(), 'failed', 'Newest failure is visible');
        check.ok(await page.locator('#fontStatus').isVisible(), 'Visible fallback warning');
        check.ok(/fallback.*static sheets/.test(await page.locator('#fontStatus').textContent()), 'Actionable failure fallback');
        await release(0, false);
        check.equal(await state(), 'failed', 'Old success for the same weight cannot clear latest failure');
        await release(1, true);
        check.equal(await state(), 'failed', 'Old failure cannot change latest status');
        check.equal(await page.locator('#fontStatus').getAttribute('data-weight'), '400');
        await change(400); await release(3, false);
        await waitForFontStatus(page, 400);
        await change(900); await change(400); await release(5, false);
        await waitForFontStatus(page, 400);
        await release(4, true);
        check.equal(await state(), 'ready', 'Late failure cannot replace a newer success');
      } finally {
        await page.evaluate(() => { window.__incomingLoadRace.restore(); delete window.__incomingLoadRace; });
      }
      await setState(400, 'ng-only', 24);
    });

    for (const [weight, scope, size] of SHOTS) {
      await test('reading screenshot / ' + weight + ' / ' + scope + ' / ' + size, async () => {
        await setState(weight, scope, size);
        validateState(await snapshot(), weight, scope, size);
        const filename = 'reading-' + weight + '-' + scope + '-' + size + '.png';
        const target = page.locator('#readingComparison');
        await target.scrollIntoViewIfNeeded();
        const bounds = await target.boundingBox();
        const scroll = await page.evaluate(() => ({x: scrollX, y: scrollY}));
        // The screenshot encloses both fractional edges on the device-pixel grid.
        // At DPR 1 this can add nearly two pixels, not just one, to a CSS extent.
        const expectedPixels = {
          width: Math.ceil(bounds.x + scroll.x + bounds.width) - Math.floor(bounds.x + scroll.x),
          height: Math.ceil(bounds.y + scroll.y + bounds.height) - Math.floor(bounds.y + scroll.y),
        };
        const image = await target.screenshot({path: path.join(outputDirectory, filename), type: 'png',
          scale: 'css', animations: 'disabled', caret: 'hide', timeout: ACTION_TIMEOUT});
        check.equal(image.subarray(0, 8).toString('hex'), '89504e470d0a1a0a', 'PNG screenshot');
        const pixels = {width: image.readUInt32BE(16), height: image.readUInt32BE(20)};
        check.equal(pixels.width, expectedPixels.width, 'DPR-1 outward-rounded screenshot width');
        check.equal(pixels.height, expectedPixels.height, 'DPR-1 outward-rounded screenshot height');
        report.screenshots.push({file: 'browser/' + filename, weight, scope, sizeCssPx: size,
          target: '#readingComparison', deviceScaleFactor: 1, pixels, cssBounds: bounds, expectedPixels});
        report.counts.screenshots++;
      });
    }
    await setState(400, 'ng-only', 24);
    await test('complete coverage and no font, console, page or network errors', async () => {
      report.fontLoadingErrors = await page.evaluate(() => window.__incomingFontErrors);
      check.equal(report.counts.states, 54);
      check.equal(new Set(report.states.map(state => [state.weight, state.scope, state.sizeCssPx].join('/'))).size, 54);
      check.equal(report.counts.baselineWeights, 9);
      check.equal(report.counts.resolvedFontLoads, 9);
      check.equal(report.counts.loadedFontFaces, 9);
      check.equal(report.counts.screenshots, 5);
      check.deepEqual(report.fontLoadingErrors, [], 'No actual font loading failures');
      check.deepEqual(report.consoleErrors, [], 'No browser console errors');
      check.deepEqual(report.pageErrors, [], 'No uncaught page errors');
      check.deepEqual(report.failedRequests, [], 'No failed local assets/fonts');
      check.deepEqual(report.blockedRequests, [], 'No HTTP/HTTPS attempted; all would be blocked');
    });
  }

  try {
    await bounded(run(), RUN_TIMEOUT, 'Browser validation');
  } catch (error) {
    failure = error;
  } finally {
    closing = true;
    try {
      await bounded((async () => {
        if (browser) await browser.close();
        if (runtimeDirectory) await fs.promises.rm(runtimeDirectory, {recursive: true, force: true});
      })(), CLOSE_TIMEOUT, 'Browser close and local temporary-profile cleanup');
    } catch (error) {
      cleanupFinished = false;
      report.closeError = error.message;
      failure ||= error;
    }
    for (const [key, value] of Object.entries(temporaryEnvironment)) {
      if (value === undefined) delete process.env[key]; else process.env[key] = value;
    }
    for (const record of report.cases.filter(item => item.status === 'running')) {
      record.status = 'interrupted';
      record.error = 'Run budget expired before this case completed';
    }
    report.status = failure ? 'failed' : 'passed';
    if (failure) report.error = failure.stack || failure.message;
    try {
      fs.writeFileSync(path.join(outputDirectory, 'validation.json'), JSON.stringify(report, null, 2) + '\n', 'utf8');
    } finally {
      if (cleanupFinished) clearTimeout(hardStop);
    }
  }
  if (failure) throw failure;
  console.log('PASS: 54 states, 9 actual loaded faces, 9 approved-baseline checks, literal-text and stale-font checks, 5 screenshots.');
  console.log(report.counts.assertions + ' assertions; browser-only report: ' + path.join(outputDirectory, 'validation.json'));
}

main().catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
