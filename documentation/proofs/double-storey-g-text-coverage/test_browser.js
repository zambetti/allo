'use strict';

/*
 * Run only after the parent generates proof.html and browser/. No builds,
 * downloads, installs, or HTTP(S) access. Syntax checking is not a browser pass.
 *
 * node documentation/proofs/double-storey-g-text-coverage/test_browser.js \
 *   /opt/homebrew/lib/python3.11/site-packages/playwright/driver/package
 *
 * The positional package path is optional (default: require('playwright')).
 * --executable=/absolute/path may select an already-installed Chromium.
 * Headless/offline, 1440 x 1000 CSS px, DPR 1. Temporary driver/profile files
 * live under browser/ and are removed, with TMPDIR/TMP/TEMP restored afterward.
 * Launch: 15 s; actions: 12 s; run: 180 s; cleanup: 5 s, plus a 2 s exit guard.
 * Outputs: browser/validation.json and the five named panel screenshots.
 */

const assert = require('node:assert/strict');
const {createHash} = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const {fileURLToPath, pathToFileURL} = require('node:url');

const WEIGHTS = [100, 200, 300, 400, 500, 600, 700, 800, 900];
const TIGHTER = [40, 44, 46, 48, 52, 54, 58, 60, 64];
const PAIR_SIZES = [16, 24, 32];
const READING_SIZES = [16, 24];
const CHECKPOINTS = [100, 400, 700, 900];
const ALPHABET = Array.from('abcdefghijklmnopqrstuvwxyz');
const TAGS = Array.from({length: 10}, (_, index) => 'ss' + (11 + index));
const ENABLED = ['ss12', 'ss15', 'ss17', 'ss19'];
const FLAGS = TAGS.map(tag => Number(ENABLED.includes(tag)));
const BASELINE = TAGS.map(tag => '"' + tag + '" ' + Number(['ss15', 'ss17', 'ss19'].includes(tag))).join(', ');
const PROBES = ['ng', 'hg', 'mg', 'ug', 'ag', 'og', 'rg', 'go', 'ge', 'gc', 'gj', 'ngj', 'ngo', 'changing', 'Morning'];
const FOCUS_WORDS = 'Morning beginning changing going';
const SHOTS = [
  {file: 'reading-400-16.png', target: '#reading16', weights: [400], size: 16},
  {file: 'reading-400-24.png', target: '#reading24', weights: [400], size: 24},
  {file: 'pairs-400.png', target: '#pairCoverage', weights: [400], size: 24},
  {file: 'boundaries-400.png', target: '#boundaryCoverage', weights: [400], size: 24},
  {file: 'weights.png', target: '#weightCheckpoints', weights: CHECKPOINTS, size: 24},
];
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
      assert.ok(!arg.startsWith('--') && !packagePath, 'Expected one optional package path and optional --executable=...');
      packagePath = path.resolve(arg);
    }
  }
  return {packagePath, executablePath};
}

function bounded(promise, milliseconds, label) {
  let timer;
  return Promise.race([
    promise,
    new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error(label + ' exceeded ' + milliseconds + ' ms')), milliseconds);
    }),
  ]).finally(() => clearTimeout(timer));
}

function featureFlags(value) {
  const entries = value.split(',').map(part => {
    const match = part.trim().match(/^["'](ss\d{2})["'](?:\s+(\d+|on|off))?$/);
    assert.ok(match, 'Unexpected computed feature settings: ' + value);
    return [match[1], match[2] === undefined || match[2] === 'on' ? 1 : match[2] === 'off' ? 0 : Number(match[2])];
  });
  assert.equal(entries.length, 10, 'All ten ss11..ss20 flags must be explicit');
  assert.deepEqual(entries.map(([tag]) => tag).sort(), TAGS, 'Exactly the ten distinct feature tags');
  const flags = Object.fromEntries(entries);
  return TAGS.map(tag => flags[tag]);
}

async function installHelpers(page) {
  await page.evaluate(() => {
    const properties = ['fontFamily', 'fontWeight', 'fontSize', 'fontStyle', 'fontStretch', 'fontSynthesis',
      'fontKerning', 'fontFeatureSettings', 'fontVariationSettings', 'fontVariant', 'fontOpticalSizing',
      'letterSpacing', 'wordSpacing', 'textTransform', 'textRendering', 'lineHeight', 'whiteSpace', 'direction'];
    const typography = node => {
      const style = getComputedStyle(node);
      return Object.fromEntries(properties.map(property => [property, style[property]]));
    };
    const textSample = node => ({text: node.textContent, children: node.children.length,
      fontSample: node.classList.contains('font-sample')});
    const visible = node => {
      const style = getComputedStyle(node);
      const rect = node.getBoundingClientRect();
      return style.display !== 'none' && style.visibility === 'visible' && Number(style.opacity) > 0 && rect.width > 0 && rect.height > 0;
    };
    const pairLayout = () => {
      const errors = [];
      const rows = Array.from(document.querySelectorAll('#pairCoverage .pair-row'));
      let runs = 0;
      for (const row of rows) {
        const label = row.dataset.direction + '/' + row.dataset.pair;
        const bounds = row.getBoundingClientRect();
        if (!visible(row)) errors.push(label + ': missing/hidden row box');
        if (row.scrollWidth > row.clientWidth + 1 || row.scrollHeight > row.clientHeight + 1) errors.push(label + ': row scroll overflow');
        for (const node of row.querySelectorAll('.pair-token, .word-example, .kind-label')) {
          runs++;
          const name = label + '/' + node.className;
          const own = node.getBoundingClientRect();
          if (!visible(node)) errors.push(name + ': missing/hidden text box');
          const range = document.createRange();
          range.selectNodeContents(node);
          const rects = Array.from(range.getClientRects()).filter(rect => rect.width > 0 && rect.height > 0);
          if (!rects.length) errors.push(name + ': no text rectangles');
          // Scroll extents are integer-rounded; Range rectangles also catch
          // visible text spilling out of a grid cell without a scrollbar.
          if (node.clientWidth && node.scrollWidth > node.clientWidth + 1) errors.push(name + ': horizontal cell overflow');
          for (const rect of rects) {
            if (rect.left < bounds.left - 1 || rect.right > bounds.right + 1 || rect.top < bounds.top - 1 || rect.bottom > bounds.bottom + 1) {
              errors.push(name + ': text outside row');
            }
            if (rect.left < own.left - 1 || rect.right > own.right + 1) errors.push(name + ': text outside cell');
          }
        }
      }
      return {rows: rows.length, runs, toleranceCssPx: 1, errors,
        documentOverflowCssPx: Math.max(0, document.documentElement.scrollWidth - innerWidth)};
    };
    const snapshot = () => ({
      controls: {weight: document.getElementById('weight').value, pairSize: document.getElementById('pairSize').value},
      fontState: document.getElementById('fontStatus').dataset.state,
      passage: document.getElementById('words').value,
      labels: Array.from(document.querySelectorAll('.selected-label'), node => node.textContent.trim()),
      samples: Array.from(document.querySelectorAll('.font-sample'), (node, index) => ({...textSample(node),
        id: node.id || 'sample-' + index, classes: node.className, selected: node.classList.contains('selected-sample'),
        pairSize: node.classList.contains('pair-size'), checkpoint: node.classList.contains('checkpoint-sample'),
        dataWeight: node.dataset.weight, style: typography(node)})),
      reading: [16, 24].map(size => {
        const panel = document.getElementById('reading' + size);
        return {size, texts: Array.from(panel.querySelectorAll('.reading-text'), node => ({...textSample(node), style: typography(node)})),
          focus: Array.from(panel.querySelectorAll('.focus-words'), textSample)};
      }),
      rows: Array.from(document.querySelectorAll('#pairCoverage .pair-row'), row => ({
        direction: row.dataset.direction, pair: row.dataset.pair, kind: row.dataset.kind,
        tokens: Array.from(row.querySelectorAll('.pair-token'), textSample),
        examples: Array.from(row.querySelectorAll('.word-example'), textSample),
        labels: Array.from(row.querySelectorAll('.kind-label'), node => node.textContent.trim()),
      })),
      capitals: Array.from(document.querySelectorAll('#boundaryCoverage .capital-pair'), textSample),
      boundaries: Array.from(document.querySelectorAll('#boundaryCoverage .boundary-sample'), textSample),
      layout: pairLayout(),
    });
    const measure = (source, text, features) => {
      const probe = source.cloneNode(false);
      probe.removeAttribute('id');
      Object.assign(probe.style, typography(source), {position: 'fixed', left: '-100000px', top: '0',
        display: 'inline-block', width: 'max-content', minWidth: '0', maxWidth: 'none', height: 'auto',
        margin: '0', padding: '0', border: '0', whiteSpace: 'pre', textIndent: '0', textAlign: 'left',
        wordBreak: 'normal', overflowWrap: 'normal', transform: 'none', visibility: 'hidden', pointerEvents: 'none',
        fontFeatureSettings: features});
      document.body.append(probe);
      try {
        // Sum explicit lines, not a full-width paragraph box or the longest
        // line of a multiline box. No wrapping or shaping-breaking spans.
        let width = 0;
        for (const line of text.split(/\r\n?|\n/)) {
          probe.textContent = line;
          width += probe.getBoundingClientRect().width;
        }
        return width;
      } finally {
        probe.remove();
      }
    };
    const compare = ({probes, baseline}) => [16, 24].map(size => {
      const source = document.querySelector('#reading' + size + ' .reading-text.font-sample');
      const style = typography(source);
      return {size, style, runs: probes.map(probe => ({...probe,
        chosenCssPx: measure(source, probe.text, style.fontFeatureSettings),
        baselineCssPx: measure(source, probe.text, baseline)}))};
    });
    const protectedContent = () => ({
      panels: ['pairCoverage', 'boundaryCoverage', 'weightCheckpoints'].map(id => document.getElementById(id).innerHTML),
      focus: Array.from(document.querySelectorAll('.focus-words'), node => node.outerHTML),
    });
    window.__coverageTest = {snapshot, compare, protectedContent, visible};
  });
}

async function main() {
  const options = argumentsFromCLI();
  const proofPath = path.join(__dirname, 'proof.html');
  const outputDirectory = path.join(__dirname, 'browser');
  assert.ok(fs.existsSync(outputDirectory) && fs.lstatSync(outputDirectory).isDirectory(), 'The parent must create a real browser/ directory first');
  const report = {
    status: 'running', startedAt: new Date().toISOString(), proof: 'proof.html', proofSha256: null, browserVersion: null,
    renderer: {engine: 'Chromium / Blink', mode: 'headless', platform: process.platform,
      package: options.packagePath || 'playwright', executable: null, offline: true, httpHttpsBlocked: true,
      serviceWorkers: 'block', locale: 'en-US', colorScheme: 'light', temporaryProfile: true,
      measurement: 'Cloned DOM text runs; max-content, preformatted, explicit line widths summed'},
    viewport: {...VIEWPORT, deviceScaleFactor: 1}, unitsPerEm: UPM, toleranceCssPx: TOLERANCE,
    features: {chosen: TAGS.map((tag, index) => [tag, FLAGS[index]]), baseline: BASELINE},
    timeoutsMs: {launch: LAUNCH_TIMEOUT, action: ACTION_TIMEOUT, run: RUN_TIMEOUT, cleanup: CLOSE_TIMEOUT},
    expectedCoverage: {weights: WEIGHTS, pairSizesCssPx: PAIR_SIZES, readingSizesCssPx: READING_SIZES,
      states: 27, pairRows: 52, capitalPairs: 26, checkpointWeights: CHECKPOINTS, probeComparisons: 324, screenshots: 5},
    counts: {casesStarted: 0, casesPassed: 0, casesFailed: 0, assertions: 0, states: 0, loadedFontFaces: 0,
      resolvedFontLoads: 0, pairRows: 0, wordRows: 0, syntheticRows: 0, pairRowStates: 0,
      capitalPairs: 0, boundarySamples: 0, checkpoints: 0, probeComparisons: 0, screenshots: 0, localLinks: 0},
    cases: [], fonts: [], states: [], probes: [], screenshots: [], links: [],
    consoleErrors: [], pageErrors: [], failedRequests: [], blockedRequests: [], httpErrors: [], fontLoadingErrors: [],
    cleanup: {environmentRestored: false, runtimeRemoved: false, browserClosed: false, errors: []},
    limits: 'Geometry and width tests are not optical approval or glyph-outline/.notdef validation. Font coverage is checked by the parent Python validation. No mobile layout claim.',
  };
  const check = {
    equal(actual, expected, label) { report.counts.assertions++; assert.equal(actual, expected, label); },
    deepEqual(actual, expected, label) { report.counts.assertions++; assert.deepEqual(actual, expected, label); },
    ok(value, label) { report.counts.assertions++; assert.ok(value, label); },
    near(actual, expected, label) {
      report.counts.assertions++;
      assert.ok(Number.isFinite(actual) && Number.isFinite(expected) && Math.abs(actual - expected) <= TOLERANCE,
        label + ': expected ' + expected + ' CSS px, got ' + actual + ' (tolerance ' + TOLERANCE + ')');
    },
  };
  const writeReport = () => fs.writeFileSync(path.join(outputDirectory, 'validation.json'), JSON.stringify(report, null, 2) + '\n', 'utf8');
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
      record.error = error.stack || error.message;
      report.counts.casesFailed++;
      throw error;
    }
  }
  let browser;
  let page;
  let failure;
  let closing = false;
  let runtimeDirectory;
  const temporaryEnvironment = Object.fromEntries(['TMPDIR', 'TMP', 'TEMP'].map(key => [key, process.env[key]]));
  const restoreEnvironment = () => {
    for (const [key, value] of Object.entries(temporaryEnvironment)) {
      if (value === undefined) delete process.env[key]; else process.env[key] = value;
    }
    report.cleanup.environmentRestored = true;
  };
  const hardStop = setTimeout(() => {
    report.status = 'failed';
    report.error ||= 'Browser validation exceeded its total run/cleanup budget';
    restoreEnvironment();
    try { writeReport(); } catch (error) { console.error(error); }
    console.error(report.error);
    process.exit(1);
  }, RUN_TIMEOUT + CLOSE_TIMEOUT + 2000);
  hardStop.unref();

  async function run() {
    check.ok(fs.existsSync(proofPath), 'The parent must generate proof.html before this test runs');
    const bytes = fs.readFileSync(proofPath);
    report.proofSha256 = createHash('sha256').update(bytes).digest('hex');
    const match = bytes.toString('utf8').match(/^[ \t]*const config = ([^\r\n]+);[ \t]*\r?$/m);
    check.ok(match, 'Expected a one-line, safely JSON-serialized const config');
    const config = JSON.parse(match[1]);
    await test('parent configuration contract', async () => {
      check.ok(Array.isArray(config.weights), 'Configured weights array');
      check.deepEqual(config.weights.map(entry => entry.weight), WEIGHTS, 'Exactly nine configured weights');
      check.deepEqual(config.weights.map(entry => entry.tighter), TIGHTER, 'Exact ng-only adjustment amounts');
      check.ok(config.weights.every(entry => typeof entry.style === 'string' && entry.style.trim()), 'Nonempty style labels');
      check.ok(Array.isArray(config.paragraphs) && config.paragraphs.length === 3 && config.paragraphs.every(text => typeof text === 'string' && text.trim()), 'Three literal paragraphs');
    });
    const passage = config.paragraphs.join('\n\n');

    runtimeDirectory = fs.mkdtempSync(path.join(outputDirectory, '.playwright-'));
    for (const key of Object.keys(temporaryEnvironment)) process.env[key] = runtimeDirectory;
    const {chromium} = require(options.packagePath || 'playwright');
    check.ok(chromium && typeof chromium.launch === 'function', 'Expected Playwright chromium');
    report.renderer.executable = options.executablePath || chromium.executablePath();
    browser = await chromium.launch({headless: true, timeout: LAUNCH_TIMEOUT, downloadsPath: runtimeDirectory,
      env: {...process.env}, ...(options.executablePath ? {executablePath: options.executablePath} : {})});
    report.browserVersion = browser.version();
    const context = await browser.newContext({viewport: VIEWPORT, deviceScaleFactor: 1, isMobile: false,
      hasTouch: false, locale: 'en-US', colorScheme: 'light', offline: true, serviceWorkers: 'block'});
    context.setDefaultTimeout(ACTION_TIMEOUT);
    context.setDefaultNavigationTimeout(LAUNCH_TIMEOUT);
    await context.route(/^https?:\/\//i, async route => {
      report.blockedRequests.push({url: route.request().url().slice(0, 500), method: route.request().method()});
      await route.abort('blockedbyclient');
    });
    context.on('requestfailed', request => {
      if (!closing) report.failedRequests.push({url: request.url().slice(0, 500), error: request.failure()?.errorText});
    });
    context.on('response', response => {
      if (!closing && response.status() >= 400) report.httpErrors.push({url: response.url().slice(0, 500), status: response.status()});
    });
    page = await context.newPage();
    page.on('console', message => {
      if (!closing && message.type() === 'error') report.consoleErrors.push({text: message.text(), location: message.location()});
    });
    page.on('pageerror', error => { if (!closing) report.pageErrors.push(error.stack || error.message); });
    await page.addInitScript(() => {
      window.__coverageFontErrors = [];
      document.fonts.addEventListener('loadingerror', event => {
        window.__coverageFontErrors.push(Array.from(event.fontfaces, face => ({family: face.family, weight: face.weight, status: face.status})));
      });
    });
    await page.goto(pathToFileURL(proofPath).href, {waitUntil: 'load', timeout: LAUNCH_TIMEOUT});
    await page.waitForFunction(() => {
      const status = document.getElementById('fontStatus');
      if (!status) throw new Error('Missing #fontStatus');
      if (status.dataset.state === 'failed') throw new Error(status.textContent);
      return status.dataset.state === 'ready';
    }, null, {timeout: ACTION_TIMEOUT});
    await installHelpers(page);
    const settled = () => bounded(page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))), ACTION_TIMEOUT, 'Layout settlement');
    const snapshot = () => page.evaluate(() => window.__coverageTest.snapshot());
    async function setState(weight, size) {
      await page.selectOption('#weight', String(weight));
      await page.selectOption('#pairSize', String(size));
      await settled();
    }

    await test('fixed renderer, initial controls, and nine eagerly loaded actual FontFaces', async () => {
      const environment = await page.evaluate(() => {
        const faces = Array.from(document.fonts, face => ({family: face.family, weight: face.weight, style: face.style, status: face.status}));
        const rules = [];
        const collect = list => {
          for (const rule of list) {
            if (rule.type === CSSRule.FONT_FACE_RULE) rules.push({family: rule.style.fontFamily, weight: rule.style.fontWeight,
              style: rule.style.fontStyle || 'normal', sourcePresent: Boolean(rule.style.getPropertyValue('src'))});
            if (rule.cssRules) collect(rule.cssRules);
          }
        };
        for (const sheet of document.styleSheets) collect(sheet.cssRules);
        return {width: innerWidth, height: innerHeight, dpr: devicePixelRatio, scale: visualViewport.scale,
          zoom: getComputedStyle(document.body).zoom, userAgent: navigator.userAgent, fontSetStatus: document.fonts.status,
          faces, rules, controls: Object.fromEntries(['weight', 'pairSize'].map(id => {
            const node = document.getElementById(id);
            return [id, {tag: node.tagName, value: node.value, options: Array.from(node.options, option => option.value)}];
          })), editor: {tag: document.getElementById('passageEditor').tagName,
            textareaInside: document.querySelector('#passageEditor textarea#words') !== null,
            resetTag: document.getElementById('resetText').tagName}};
      });
      report.environment = environment;
      check.equal(environment.width, VIEWPORT.width, 'Viewport width');
      check.equal(environment.height, VIEWPORT.height, 'Viewport height');
      check.equal(environment.dpr, 1, 'DPR');
      check.equal(environment.scale, 1, 'No viewport scaling');
      check.ok(['1', 'normal'].includes(environment.zoom), 'No body CSS zoom');
      check.deepEqual(environment.controls, {weight: {tag: 'SELECT', value: '400', options: WEIGHTS.map(String)},
        pairSize: {tag: 'SELECT', value: '24', options: PAIR_SIZES.map(String)}}, 'Control options/defaults');
      check.deepEqual(environment.editor, {tag: 'DETAILS', textareaInside: true, resetTag: 'BUTTON'}, 'Literal passage editor controls');
      check.equal(environment.rules.length, 9, 'Exactly nine @font-face rules');
      check.equal(environment.faces.length, 9, 'Exactly nine actual FontFaces');
      check.deepEqual(environment.rules.map(face => Number(face.weight)).sort((a, b) => a - b), WEIGHTS, 'Exact CSS face weights');
      check.deepEqual(environment.faces.map(face => Number(face.weight)).sort((a, b) => a - b), WEIGHTS, 'Exact actual face weights');
      check.equal(environment.fontSetStatus, 'loaded', 'All eager loading finished before controls are tested');
      for (const face of [...environment.rules, ...environment.faces]) {
        check.equal(face.family.replace(/["']/g, '').trim(), 'CoverageProof', 'Exact font family');
        check.equal(face.style, 'normal', 'Upright face');
        if ('status' in face) check.equal(face.status, 'loaded', 'Face already loaded, not loaded by the test');
        if ('sourcePresent' in face) check.ok(face.sourcePresent, 'Font source present');
      }
      report.fonts = environment.faces;
      report.counts.loadedFontFaces = environment.faces.length;
      for (const weight of WEIGHTS) {
        const faces = await bounded(page.evaluate(async value => {
          const loaded = await document.fonts.load(value + ' 24px "CoverageProof"', 'ng hg mg ug go ge gc gj');
          return loaded.map(face => ({family: face.family.replace(/["']/g, '').trim(), weight: face.weight, style: face.style, status: face.status}));
        }, weight), ACTION_TIMEOUT, 'Actual font match for ' + weight);
        check.deepEqual(faces, [{family: 'CoverageProof', weight: String(weight), style: 'normal', status: 'loaded'}], 'Exact loaded face, not fallback/nearest-weight fonts.check');
        report.counts.resolvedFontLoads++;
      }
    });

    await settled();
    const initial = await snapshot();
    const plainSample = (sample, label) => {
      check.ok(sample.fontSample, label + ' uses .font-sample');
      check.equal(sample.children, 0, label + ' is literal text without shaping-breaking elements');
    };
    function validateState(actual, weight, size) {
      const entry = config.weights.find(item => item.weight === weight);
      check.deepEqual(actual.controls, {weight: String(weight), pairSize: String(size)}, 'Selected controls');
      check.equal(actual.fontState, 'ready', 'Font status remains ready');
      check.equal(actual.passage, passage, 'Original editor text');
      check.ok(actual.labels.length > 0, 'Visible-style labels exist');
      for (const label of actual.labels) {
        check.ok(label.includes(entry.style) && new RegExp('\\b' + weight + '\\b').test(label), 'Selected label contains style and weight: ' + label);
      }
      check.equal(actual.samples.length, initial.samples.length, 'Stable sample count');
      for (const [index, sample] of actual.samples.entries()) {
        const original = initial.samples[index];
        const style = sample.style;
        check.equal(sample.classes, original.classes, sample.id + ' retains control roles');
        check.equal(sample.text, original.text, sample.id + ' unchanged by selectors');
        check.equal(sample.children, original.children, sample.id + ' unchanged text structure');
        check.deepEqual(featureFlags(style.fontFeatureSettings), FLAGS, sample.id + ' explicit chosen flags');
        check.equal(style.fontFamily.split(',')[0].replace(/["']/g, '').trim(), 'CoverageProof', sample.id + ' family');
        check.equal(style.fontWeight, sample.selected ? String(weight) : original.style.fontWeight, sample.id + ' only selected samples change weight');
        check.equal(style.fontSize, sample.pairSize ? size + 'px' : original.style.fontSize, sample.id + ' only pair-size samples change size');
        check.equal(style.fontStyle, 'normal', sample.id + ' upright');
        check.equal(style.fontSynthesis, 'none', sample.id + ' no synthesis');
        check.equal(style.fontKerning, 'normal', sample.id + ' kerning');
        check.equal(style.letterSpacing, 'normal', sample.id + ' no tracking');
        check.ok(['normal', '0px'].includes(style.wordSpacing), sample.id + ' normal word spacing');
        check.equal(style.textTransform, 'none', sample.id + ' literal case');
      }
      for (const panel of actual.reading) {
        check.equal(panel.texts.length, 1, 'One reading text at ' + panel.size);
        plainSample(panel.texts[0], 'Reading ' + panel.size);
        check.equal(panel.texts[0].text, passage, 'Literal paragraphs joined by blank lines');
        check.equal(panel.texts[0].style.fontSize, panel.size + 'px', 'Fixed reading size');
        check.equal(panel.texts[0].style.fontWeight, String(weight), 'Selected reading weight');
        check.equal(panel.focus.length, 1, 'One focus-word sample per reading panel');
        plainSample(panel.focus[0], 'Focus words');
        check.equal(panel.focus[0].text, FOCUS_WORDS, 'Fixed focus words');
      }
      const checkpoints = actual.samples.filter(sample => sample.checkpoint);
      check.deepEqual(checkpoints.map(sample => Number(sample.dataWeight)), CHECKPOINTS, 'Four fixed checkpoint weights');
      check.ok(checkpoints[0].text.trim(), 'Nonempty checkpoint text');
      for (const sample of checkpoints) {
        check.ok(!sample.selected && !sample.pairSize, 'Checkpoint independent of selectors');
        check.equal(sample.style.fontWeight, sample.dataWeight, 'Fixed checkpoint face');
        check.equal(sample.style.fontSize, '24px', 'Fixed checkpoint size');
        check.equal(sample.text, checkpoints[0].text, 'Same checkpoint text at all weights');
      }
      check.equal(actual.layout.rows, 52, 'All pair rows remain present');
      check.equal(actual.layout.runs, 156, 'Token, example and kind label have boxes in every row');
      check.deepEqual(actual.layout.errors, [], 'No hidden, missing, clipped or overflowing pair text at ' + weight + '/' + size);
      check.ok(actual.layout.documentOverflowCssPx <= 1, 'No horizontal document overflow at the fixed desktop viewport');
    }
    await test('exact alphabet coverage, synthetic labels, boundary samples, and initial typography', async () => {
      check.ok(initial.samples.some(sample => sample.selected), 'Selected font samples exist');
      check.ok(initial.samples.some(sample => sample.pairSize), 'Pair-size font samples exist');
      validateState(initial, 400, 24);
      check.equal(initial.rows.length, 52, 'Exactly 52 pair rows');
      for (const direction of ['incoming', 'outgoing']) {
        const expected = ALPHABET.map(letter => direction === 'incoming' ? letter + 'g' : 'g' + letter).sort();
        check.deepEqual(initial.rows.filter(row => row.direction === direction).map(row => row.pair).sort(), expected, 'Exact ' + direction + ' alphabet, including gg');
      }
      for (const row of initial.rows) {
        check.equal(row.tokens.length, 1, row.pair + ' has one token');
        check.equal(row.examples.length, 1, row.pair + ' has one example');
        plainSample(row.tokens[0], row.pair + ' token');
        plainSample(row.examples[0], row.pair + ' example');
        check.equal(row.tokens[0].text, row.pair, 'Exact pair token');
        check.ok(row.examples[0].text.includes(row.pair), row.pair + ' occurs literally in its example');
        check.ok(['word', 'synthetic'].includes(row.kind), 'Explicit word/synthetic classification');
        check.deepEqual(row.labels, [row.kind === 'synthetic' ? 'test string' : 'word'], 'Honest visible example-kind label');
        report.counts[row.kind === 'synthetic' ? 'syntheticRows' : 'wordRows']++;
      }
      check.deepEqual(initial.capitals.map(sample => sample.text).sort(), ALPHABET.map(letter => letter.toUpperCase() + 'g').sort(), 'Exactly Ag through Zg');
      for (const sample of [...initial.capitals, ...initial.boundaries]) plainSample(sample, 'Boundary sample');
      check.ok(initial.boundaries.length > 0 && initial.boundaries.every(sample => sample.text.length > 0), 'Nonempty literal boundary snippets');
      check.ok(initial.boundaries.some(sample => /\s/u.test(sample.text)), 'Space boundary coverage');
      check.ok(initial.boundaries.some(sample => /\p{P}/u.test(sample.text)), 'Punctuation boundary coverage');
      report.counts.pairRows = initial.rows.length;
      report.counts.capitalPairs = initial.capitals.length;
      report.counts.boundarySamples = initial.boundaries.length;
      report.counts.checkpoints = 4;
      report.coverage = {rows: initial.rows, capitals: initial.capitals, boundaries: initial.boundaries};
    });

    const probes = [...PROBES.map(text => ({name: text, text})), ...config.paragraphs.map((text, index) => ({name: 'paragraph-' + (index + 1), text}))];
    for (const [index, weight] of WEIGHTS.entries()) {
      for (const size of PAIR_SIZES) {
        await test('selectors and pair-row layout / ' + weight + ' / ' + size, async () => {
          await setState(weight, size);
          const actual = await snapshot();
          validateState(actual, weight, size);
          check.deepEqual(actual.rows, initial.rows, 'Selectors preserve all pair coverage and labels');
          check.deepEqual(actual.capitals, initial.capitals, 'Selectors preserve capital coverage');
          check.deepEqual(actual.boundaries, initial.boundaries, 'Selectors preserve literal boundary strings');
          report.states.push({weight, pairSizeCssPx: size, samples: actual.samples.length, layout: actual.layout});
          report.counts.states++;
          report.counts.pairRowStates += actual.layout.rows;
        });
      }
      await test('ng-only width deltas at both reading sizes / ' + weight, async () => {
        const comparisons = await page.evaluate(args => window.__coverageTest.compare(args), {probes, baseline: BASELINE});
        check.deepEqual(comparisons.map(item => item.size), READING_SIZES, 'Both reading sizes measured');
        for (const comparison of comparisons) {
          check.equal(comparison.style.fontWeight, String(weight), 'Probe source uses actual selected weight');
          check.equal(comparison.style.fontSize, comparison.size + 'px', 'Probe source uses actual reading size');
          check.deepEqual(featureFlags(comparison.style.fontFeatureSettings), FLAGS, 'Probe chosen features');
          check.equal(comparison.runs.length, probes.length, 'All pair, word and paragraph probes');
          for (const run of comparison.runs) {
            const occurrences = (run.text.match(/ng/g) || []).length;
            const expectedCssPx = occurrences * TIGHTER[index] * comparison.size / UPM;
            const shorteningCssPx = run.baselineCssPx - run.chosenCssPx;
            report.probes.push({weight, sizeCssPx: comparison.size, ...run, occurrences, expectedShorteningCssPx: expectedCssPx, shorteningCssPx});
            check.ok(run.baselineCssPx > 0 && run.chosenCssPx > 0, 'Nonzero text-run widths: ' + run.name);
            check.near(shorteningCssPx, expectedCssPx, weight + '/' + comparison.size + '/' + run.name + ' only ng shortens');
            if (occurrences) check.ok(shorteningCssPx > 0, run.name + ' actually shortens');
            report.counts.probeComparisons++;
          }
        }
      });
    }

    await setState(400, 24);
    await test('literal hostile passage, unaffected coverage/focus/checkpoints, and reset', async () => {
      const editor = page.locator('#passageEditor');
      const wasOpen = await editor.evaluate(node => node.open);
      const protectedBefore = await page.evaluate(() => window.__coverageTest.protectedContent());
      const hostile = '<img src="missing-coverage-test.png" onerror="window.__coverageInjected=1"><script>window.__coverageInjected=2</script>\n\nMorning & beginning <b>changing</b> going < >';
      try {
        if (!wasOpen) await page.locator('#passageEditor > summary').click();
        await page.locator('#words').fill(hostile);
        await settled();
        const edited = await snapshot();
        check.equal(edited.passage, hostile, 'Textarea retains literal hostile text');
        for (const panel of edited.reading) {
          check.equal(panel.texts[0].text, hostile, 'Both reading panels receive textContent');
          check.equal(panel.texts[0].children, 0, 'No injected elements');
        }
        check.equal(await page.evaluate(() => typeof window.__coverageInjected), 'undefined', 'No injected script or event handler ran');
        check.deepEqual(await page.evaluate(() => window.__coverageTest.protectedContent()), protectedBefore, 'Editing leaves coverage, focus words and checkpoints untouched');
        await page.locator('#resetText').click();
        await settled();
        validateState(await snapshot(), 400, 24);
        check.deepEqual(await page.evaluate(() => window.__coverageTest.protectedContent()), protectedBefore, 'Reset changes only reading passage');
      } finally {
        await page.locator('#words').fill(passage);
        await editor.evaluate((node, open) => { node.open = open; }, wasOpen);
      }
    });

    await setState(400, 24);
    validateState(await snapshot(), 400, 24);
    for (const shot of SHOTS) {
      await test('panel screenshot / ' + shot.file, async () => {
        const target = page.locator(shot.target);
        await target.scrollIntoViewIfNeeded();
        await settled();
        const label = await target.evaluate(node => {
          const copy = node.cloneNode(true);
          copy.querySelectorAll('.font-sample, script, style').forEach(sample => sample.remove());
          return {text: copy.textContent, visibleHeadings: Array.from(node.querySelectorAll('h1, h2, h3, h4, h5, h6')).filter(window.__coverageTest.visible).length};
        });
        check.ok(label.visibleHeadings > 0, shot.target + ' includes a visible panel heading');
        for (const value of [...shot.weights, shot.size]) check.ok(new RegExp('(?:^|\\D)' + value + '(?:\\D|$)').test(label.text), shot.target + ' screenshot label includes ' + value);
        const geometry = await target.evaluate(node => {
          const rect = node.getBoundingClientRect();
          return {cssBounds: {x: rect.x, y: rect.y, width: rect.width, height: rect.height}, scroll: {x: scrollX, y: scrollY},
            pageBounds: {left: rect.left + scrollX, top: rect.top + scrollY, right: rect.right + scrollX, bottom: rect.bottom + scrollY}};
        });
        const bounds = geometry.pageBounds;
        const crop = {x: Math.floor(bounds.left), y: Math.floor(bounds.top),
          width: Math.ceil(bounds.right) - Math.floor(bounds.left), height: Math.ceil(bounds.bottom) - Math.floor(bounds.top)};
        check.ok(crop.width > 0 && crop.height > 0, 'Nonempty screenshot target');
        // Locator screenshots round outward in PAGE coordinates. Rounding a
        // viewport-relative height (or merely adding one pixel) is incorrect.
        const image = await target.screenshot({path: path.join(outputDirectory, shot.file), type: 'png',
          scale: 'css', animations: 'disabled', caret: 'hide', timeout: ACTION_TIMEOUT});
        check.ok(image.length >= 24, 'PNG has an IHDR header');
        check.equal(image.subarray(0, 8).toString('hex'), '89504e470d0a1a0a', 'PNG signature');
        check.equal(image.subarray(12, 16).toString('ascii'), 'IHDR', 'PNG dimensions header');
        const pixels = {width: image.readUInt32BE(16), height: image.readUInt32BE(20)};
        const expectedPixels = {width: crop.width, height: crop.height};
        report.screenshots.push({file: 'browser/' + shot.file, target: shot.target, weights: shot.weights,
          sizeCssPx: shot.size, deviceScaleFactor: 1, scale: 'css', ...geometry, crop, expectedPixels, pixels,
          sha256: createHash('sha256').update(image).digest('hex')});
        check.deepEqual(pixels, expectedPixels, 'Exact outward-rounded screenshot dimensions');
        report.counts.screenshots++;
      });
    }

    await test('local href targets resolve without navigation or networking', async () => {
      // Make the self-link resolvable on a first run; finally overwrites this
      // explicitly running report with the final pass/fail and cleanup result.
      writeReport();
      const links = await page.evaluate(() => Array.from(document.querySelectorAll('[href]'), node => {
        const href = node.getAttribute('href');
        const url = new URL(href, document.baseURI);
        const sameDocument = url.protocol === location.protocol && url.host === location.host && url.pathname === location.pathname && url.search === location.search;
        return {href, url: url.href, sameDocument, fragmentExists: !url.hash || !sameDocument || Boolean(document.getElementById(decodeURIComponent(url.hash.slice(1))))};
      }));
      for (const link of links) {
        const url = new URL(link.url);
        const record = {...link, local: url.protocol === 'file:'};
        report.links.push(record);
        if (!record.local) continue;
        const localPath = fileURLToPath(url);
        record.exists = fs.existsSync(localPath);
        check.ok(record.exists, 'Local href resolves: ' + link.href);
        check.ok(link.fragmentExists, 'Same-document fragment resolves: ' + link.href);
        report.counts.localLinks++;
      }
    });
    await test('complete coverage and no console, page, font or network errors', async () => {
      report.fontLoadingErrors = await page.evaluate(() => window.__coverageFontErrors);
      check.equal(report.counts.states, 27, 'All nine weights by three pair sizes');
      check.equal(new Set(report.states.map(state => state.weight + '/' + state.pairSizeCssPx)).size, 27, 'Distinct selector states');
      check.equal(report.counts.pairRowStates, 52 * 27, 'Every row checked in every state');
      check.equal(report.counts.probeComparisons, 324, 'All requested width comparisons');
      check.equal(report.counts.loadedFontFaces, 9, 'Nine initially loaded FontFaces');
      check.equal(report.counts.resolvedFontLoads, 9, 'Nine exact FontFace matches');
      check.equal(report.counts.screenshots, 5, 'All five screenshots');
      for (const key of ['consoleErrors', 'pageErrors', 'fontLoadingErrors', 'failedRequests', 'blockedRequests', 'httpErrors']) check.deepEqual(report[key], [], 'No ' + key);
      check.equal(createHash('sha256').update(fs.readFileSync(proofPath)).digest('hex'), report.proofSha256, 'proof.html did not change during the run');
    });
  }

  try {
    await bounded(run(), RUN_TIMEOUT, 'Browser validation');
  } catch (error) {
    failure = error;
  } finally {
    closing = true;
    if (page && !page.isClosed()) {
      try {
        report.fontLoadingErrors = await bounded(page.evaluate(() => window.__coverageFontErrors || []), 500, 'Collect font errors');
      } catch (error) {
        report.fontErrorCollectionError = error.message;
        failure ||= error;
      }
    }
    try {
      if (browser) await bounded(browser.close(), 3000, 'Browser close');
      report.cleanup.browserClosed = true;
    } catch (error) {
      report.cleanup.errors.push(error.message);
      failure ||= error;
    }
    try {
      if (runtimeDirectory) await bounded(fs.promises.rm(runtimeDirectory, {recursive: true, force: true, maxRetries: 2, retryDelay: 100}), 1500, 'Local runtime removal');
      report.cleanup.runtimeRemoved = true;
    } catch (error) {
      report.cleanup.errors.push(error.message);
      failure ||= error;
    }
    restoreEnvironment();
    for (const record of report.cases.filter(item => item.status === 'running')) {
      record.status = 'interrupted';
      record.error = 'Run budget expired before completion';
      report.counts.casesFailed++;
    }
    report.status = failure ? 'failed' : 'passed';
    if (failure) report.error = failure.stack || failure.message;
    report.finishedAt = new Date().toISOString();
    try {
      writeReport();
    } finally {
      if (report.cleanup.browserClosed && report.cleanup.runtimeRemoved) clearTimeout(hardStop);
    }
  }
  if (failure) throw failure;
  console.log('PASS: 27 selector states, 1,404 pair-row states, 9 eager FontFaces, 324 width comparisons, literal editor/reset, 5 screenshots.');
  console.log(report.counts.assertions + ' assertions; browser report: ' + path.join(outputDirectory, 'validation.json'));
}

main().catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
