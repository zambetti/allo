'use strict';

/*
 * Real-browser validation, separate from deterministic builder artifacts.
 * Run from the repository root after the parent builds proof.html and creates
 * documentation/proofs/double-storey-g-spacing-finish/browser/:
 *
 *   node documentation/proofs/double-storey-g-spacing-finish/test_browser.js \
 *     /opt/homebrew/lib/python3.11/site-packages/playwright/driver/package
 *
 * The package argument is optional (defaults to require('playwright')). An
 * optional --executable=/absolute/path selects a Chromium executable; otherwise
 * Playwright selects its own cached revision. No download or installation runs.
 *
 * This script must actually be executed before its browser checks can be claimed
 * to pass. Launch timeout: 15 s. Test budget: 180 s, plus bounded cleanup. The
 * parent should also apply a terminal timeout. No source or builder output is
 * modified; runtime outputs are browser/reading-{weight}-{size}.png and
 * browser/validation.json. The output directory must already exist.
 */

const assert = require('node:assert/strict');
const {createHash} = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');

const WEIGHTS = [100, 200, 300, 400, 500, 600, 700, 800, 900];
const B = [40, 43, 45, 48, 51, 54, 57, 60, 64];
const CORRECTIONS = [0, 0, 0, 0, 0, 0, 8, 27, 40];
const SIZES = [12, 16, 24];
const TAGS = ['ss15', 'ss16', 'ss17', 'ss18', 'ss19', 'ss20'];
const FLAGS = {chosen: [0, 0, 1, 0, 1, 0], refined: [1, 0, 1, 0, 1, 0], boundary: [1, 1, 1, 0, 1, 0]};
const VIEWPORT = {width: 1200, height: 900};
const UPM = 2048;
const TOLERANCE = 0.05;
const LAUNCH_TIMEOUT = 15000;
const ACTION_TIMEOUT = 10000;
const RUN_TIMEOUT = 180000;
const CLOSE_TIMEOUT = 5000;
const PAIR_RUNS = ['gj', 'gjg', 'go', 'ge', 'gc', 'gg', 'gy', 'g'];

function argumentsFromCLI() {
  let packagePath = null;
  let executablePath;
  for (const arg of process.argv.slice(2)) {
    if (arg.startsWith('--executable=')) {
      assert.ok(!executablePath, 'Only one --executable argument is allowed');
      executablePath = arg.slice('--executable='.length);
      assert.ok(path.isAbsolute(executablePath), '--executable must be an absolute path');
    } else {
      assert.ok(!arg.startsWith('--') && !packagePath, 'Expected one optional Playwright package path and optional --executable=...');
      packagePath = path.resolve(arg);
    }
  }
  return {packagePath, executablePath};
}

function bounded(promise, milliseconds, label) {
  let timer;
  return Promise.race([
    promise,
    new Promise((_, reject) => { timer = setTimeout(() => reject(new Error(label + ' timed out after ' + milliseconds + ' ms')), milliseconds); }),
  ]).finally(() => clearTimeout(timer));
}

function featureFlags(value) {
  // Chromium may serialize an explicit 1 as an omitted optional value (on).
  const entries = value.split(',').map(part => {
    const match = part.trim().match(/^["'](ss\d{2})["'](?:\s+(\d+|on|off))?$/);
    assert.ok(match, 'Unexpected computed feature setting: ' + value);
    return [match[1], match[2] === undefined || match[2] === 'on' ? 1 : match[2] === 'off' ? 0 : Number(match[2])];
  });
  assert.equal(entries.length, 6, 'All six feature flags must be explicit');
  assert.equal(new Set(entries.map(([tag]) => tag)).size, 6, 'Feature tags must not repeat');
  assert.deepEqual(entries.map(([tag]) => tag).sort(), TAGS);
  const values = Object.fromEntries(entries);
  return TAGS.map(tag => values[tag]);
}

async function waitForFontStatus(page, section, weight) {
  await page.waitForFunction(({section, weight}) => {
    const status = document.getElementById(section + 'FontStatus');
    if (!status) throw new Error('Missing ' + section + 'FontStatus');
    if (['failed', 'unavailable'].includes(status.dataset.state)) throw new Error(status.textContent);
    return status.dataset.state === 'ready' && status.dataset.weight === String(weight);
  }, {section, weight}, {timeout: ACTION_TIMEOUT});
}

async function installMeasurementHelpers(page) {
  await page.evaluate(() => {
    const properties = ['fontFamily', 'fontSize', 'fontWeight', 'fontStyle', 'fontStretch',
      'fontKerning', 'fontSynthesis', 'fontFeatureSettings', 'fontVariationSettings',
      'fontOpticalSizing', 'fontVariantLigatures', 'fontVariantCaps', 'fontVariantNumeric',
      'fontVariantEastAsian', 'fontVariantPosition', 'fontVariantAlternates', 'textRendering',
      'letterSpacing', 'wordSpacing', 'textAlign', 'textAlignLast', 'textTransform',
      'lineHeight', 'whiteSpace', 'direction', 'unicodeBidi', 'writingMode', 'color'];
    const byId = id => {
      const node = document.getElementById(id);
      if (!node) throw new Error('Missing DOM ID: ' + id);
      return node;
    };
    const typography = node => {
      const style = getComputedStyle(node);
      return Object.fromEntries(properties.map(property => [property, style[property]]));
    };
    const sample = node => ({id: node.id, variant: node.dataset.variant, text: node.textContent,
      lang: node.closest('[lang]')?.getAttribute('lang') || '', style: typography(node)});
    const box = node => {
      const rect = node.getBoundingClientRect();
      return {x: rect.x + scrollX, y: rect.y + scrollY, width: rect.width, height: rect.height};
    };
    const firstTextY = node => {
      const range = document.createRange();
      range.selectNodeContents(node);
      const rect = Array.from(range.getClientRects()).find(item => item.width > 0 && item.height > 0);
      return rect ? rect.top + scrollY : null;
    };
    const section = prefix => {
      const root = byId(prefix + 'Section');
      const status = byId(prefix + 'FontStatus');
      return {
        controls: Array.from(root.querySelectorAll('select, textarea'), node => ({id: node.id, value: node.value})),
        status: {state: status.dataset.state, weight: status.dataset.weight, text: status.textContent},
        labels: Array.from(root.querySelectorAll('.amount, .feature-flags'), node => ({id: node.id, text: node.textContent})),
        summary: byId(prefix + 'Summary').textContent,
        samples: Array.from(root.querySelectorAll('.font-sample'), sample),
      };
    };
    const measure = (id, texts) => {
      const source = byId(id);
      const probe = document.createElement('span');
      const style = typography(source);
      for (const property of properties) if (style[property] !== undefined) probe.style[property] = style[property];
      probe.lang = source.closest('[lang]')?.getAttribute('lang') || document.documentElement.lang;
      // Intrinsic DOM advance widths, not ink bounds, ratios, or a reversed run.
      // Keep the source's direction/language/kerning/features. pre preserves the
      // trailing ASCII space in "g " and prevents line wrapping in these probes.
      Object.assign(probe.style, {position: 'fixed', left: '0', top: '0', display: 'inline-block',
        width: 'max-content', maxWidth: 'none', margin: '0', padding: '0', border: '0',
        whiteSpace: 'pre', visibility: 'hidden', pointerEvents: 'none'});
      document.body.appendChild(probe);
      try {
        return Object.fromEntries(texts.map(text => {
          probe.textContent = text;
          return [text, probe.getBoundingClientRect().width];
        }));
      } finally {
        probe.remove();
      }
    };
    const reading = () => {
      const left = byId('reading-refined');
      const right = byId('reading-boundary');
      return {
        left: box(left), right: box(right), firstTextY: [firstTextY(left), firstTextY(right)],
        headingY: [box(byId('textHeading-refined')).y, box(byId('textHeading-boundary')).y],
        columnRows: Array.from(document.querySelectorAll('.reading-column'), node => getComputedStyle(node).gridTemplateRows),
        columns: getComputedStyle(byId('textComparison')).gridTemplateColumns,
        boundary: ['refined', 'boundary'].map(variant => {
          const node = byId('boundary-' + variant);
          const style = getComputedStyle(node);
          return {text: node.textContent, box: box(node), border: style.borderInlineEndWidth,
            borderStyle: style.borderInlineEndStyle, display: style.display, whiteSpace: style.whiteSpace};
        }),
        refinedRuns: measure('boundary-refined', ['g', 'g ', 'g g']),
        boundaryRuns: measure('boundary-boundary', ['g', 'g ', 'g g']),
      };
    };
    window.__spacingFinishBrowserTest = {section, measure, reading};
  });
}

async function main() {
  const options = argumentsFromCLI();
  const proofPath = path.join(__dirname, 'proof.html');
  const outputDirectory = path.join(__dirname, 'browser');
  assert.ok(fs.existsSync(proofPath), 'The parent must generate the local proof.html first');
  assert.ok(fs.existsSync(outputDirectory) && fs.statSync(outputDirectory).isDirectory(), 'The parent must create the browser/ output directory first');
  const html = fs.readFileSync(proofPath, 'utf8');
  const match = html.match(/^const config = (.+);$/m);
  assert.ok(match, 'Expected the renderer’s safely serialized config');
  const config = JSON.parse(match[1]);
  const report = {
    status: 'running', proof: 'proof.html', proofSha256: createHash('sha256').update(html).digest('hex'), browserVersion: null,
    renderer: {engine: 'Chromium / Blink', mode: 'headless', platform: process.platform,
      package: options.packagePath || 'playwright', executable: null},
    viewport: {...VIEWPORT, deviceScaleFactor: 1},
    timeoutsMs: {launch: LAUNCH_TIMEOUT, action: ACTION_TIMEOUT, run: RUN_TIMEOUT, close: CLOSE_TIMEOUT},
    toleranceCssPx: TOLERANCE, unitsPerEm: UPM,
    counts: {casesStarted: 0, casesPassed: 0, casesFailed: 0, assertions: 0,
      pairWeights: 0, readingWeightSizes: 0, resolvedFontLoads: 0, loadedFontFaces: 0, screenshots: 0},
    cases: [], fonts: [], measurements: {pairs: [], reading: []}, screenshots: [],
    consoleErrors: [], pageErrors: [], failedRequests: [], blockedRequests: [], fontLoadingErrors: [],
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
  async function test(name, fn) {
    report.counts.casesStarted++;
    try {
      await fn();
      report.counts.casesPassed++;
      report.cases.push({name, status: 'passed'});
    } catch (error) {
      report.counts.casesFailed++;
      report.cases.push({name, status: 'failed', error: error.message});
      throw error;
    }
  }
  let browser;
  let failure;
  let closing = false;
  let closeFinished = true;
  // Last-resort bound if a driver/close operation leaves the Node process alive.
  // Normal timeout handling below still attempts browser.close() in finally.
  const hardStop = setTimeout(() => {
    console.error('Browser validation exceeded its total run/cleanup budget.');
    process.exit(1);
  }, RUN_TIMEOUT + CLOSE_TIMEOUT + 2000);
  hardStop.unref();

  async function run() {
    const {chromium} = require(options.packagePath || 'playwright');
    assert.ok(chromium && typeof chromium.launch === 'function', 'The package must export Playwright chromium');
    report.renderer.executable = options.executablePath || chromium.executablePath();
    browser = await chromium.launch({headless: true, timeout: LAUNCH_TIMEOUT,
      ...(options.executablePath ? {executablePath: options.executablePath} : {})});
    report.browserVersion = browser.version();
    const context = await browser.newContext({viewport: VIEWPORT, deviceScaleFactor: 1,
      isMobile: false, hasTouch: false, locale: 'en-US', colorScheme: 'light',
      offline: true, serviceWorkers: 'block'});
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
      if (!closing) report.failedRequests.push({url: request.url().slice(0, 500), error: request.failure()?.errorText || 'Unknown request failure'});
    });
    await page.addInitScript(() => {
      window.__spacingFinishFontErrors = [];
      document.fonts.addEventListener('loadingerror', event => {
        window.__spacingFinishFontErrors.push(Array.from(event.fontfaces, face => ({family: face.family, weight: face.weight, status: face.status})));
      });
    });
    await page.goto(pathToFileURL(proofPath).href, {waitUntil: 'load', timeout: LAUNCH_TIMEOUT});
    await installMeasurementHelpers(page);
    const snapshot = section => page.evaluate(prefix => window.__spacingFinishBrowserTest.section(prefix), section);
    const settledLayout = () => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));

    async function loadFace(weight, size) {
      const faces = await page.evaluate(async ({weight, size}) => {
        try {
          const loaded = await document.fonts.load(weight + ' ' + size + 'px "SpacingProof"', 'gj ogec ø \u00a0');
          return loaded.map(face => ({family: face.family, weight: face.weight, style: face.style, status: face.status}));
        } catch (error) {
          throw new Error('document.fonts.load failed for weight ' + weight + ': ' + error.message);
        }
      }, {weight, size});
      // check() alone can succeed when no face matches. Require a resolved face.
      check.equal(faces.length, 1, 'Exactly one embedded static face resolves for weight ' + weight);
      check.equal(faces[0].family.replace(/^["']|["']$/g, ''), 'SpacingProof', 'Resolved font family');
      check.equal(faces[0].weight, String(weight), 'Resolved face weight, not a nearest fallback');
      check.equal(faces[0].style, 'normal', 'Resolved upright face');
      check.equal(faces[0].status, 'loaded', 'Resolved face really loaded');
      report.counts.resolvedFontLoads++;
    }

    function expectSection(actual, section, weight, readingSize = 16) {
      check.equal(actual.status.state, 'ready', section + ' loaded independently');
      check.equal(actual.status.weight, String(weight), section + ' requested weight');
      check.equal(actual.controls.find(control => control.id === section + 'Weight').value, String(weight));
      check.equal(actual.samples.length, section === 'pair' ? 8 : 6);
      for (const sample of actual.samples) {
        const style = sample.style;
        const size = section === 'pair' ? 72 : sample.id.startsWith('boundary-') ? 16 : readingSize;
        check.equal(style.fontWeight, String(weight), sample.id + ' computed weight');
        check.equal(style.fontSize, size + 'px', sample.id + ' computed CSS size');
        check.equal(style.fontFamily.split(',')[0].trim().replace(/^["']|["']$/g, ''), 'SpacingProof', sample.id + ' first family');
        check.deepEqual(featureFlags(style.fontFeatureSettings), FLAGS[sample.variant], sample.id + ' all six fixed flags');
        check.equal(style.fontKerning, 'normal', sample.id + ' kerning');
        check.equal(style.fontStyle, 'normal', sample.id + ' upright');
        check.equal(style.fontSynthesis, 'none', sample.id + ' no synthesized faces');
        check.equal(style.direction, 'ltr', sample.id + ' normal text direction');
        check.ok(['normal', '0px', '0'].includes(style.letterSpacing), sample.id + ' no tracking');
        check.ok(['normal', '0px', '0'].includes(style.wordSpacing), sample.id + ' no added word spacing');
        check.ok(['start', 'left'].includes(style.textAlign), sample.id + ' ragged right');
        check.ok(['auto', 'start', 'left'].includes(style.textAlignLast), sample.id + ' no last-line justification');
      }
    }

    async function expectReading(weight, size) {
      const current = await snapshot('text');
      expectSection(current, 'text', weight, size);
      check.equal(current.controls.find(control => control.id === 'textSize').value, String(size));
      const left = current.samples.find(sample => sample.id === 'reading-refined');
      const right = current.samples.find(sample => sample.id === 'reading-boundary');
      const input = current.controls.find(control => control.id === 'words').value;
      check.ok(input.trim().length > 0, 'A nonempty passage is needed for reading geometry checks');
      check.equal(left.text, input, 'Current column contains the literal shared passage');
      check.equal(right.text, input, 'Boundary column contains the same literal passage');
      check.equal(left.style.whiteSpace, 'pre-wrap', 'Paragraph breaks and natural wrapping');
      check.equal(left.lang, right.lang, 'Same passage language');
      const withoutFeatures = style => Object.fromEntries(Object.entries(style).filter(([key]) => key !== 'fontFeatureSettings'));
      check.deepEqual(withoutFeatures(left.style), withoutFeatures(right.style), 'No typography differences except the intended feature flags');
      const geometry = await page.evaluate(() => window.__spacingFinishBrowserTest.reading());
      check.ok(geometry.left.width > 0, 'Visible paragraph width');
      check.near(geometry.left.width, geometry.right.width, 'Equal paragraph widths');
      check.near(geometry.left.y, geometry.right.y, 'Equal paragraph starting y');
      check.near(geometry.firstTextY[0], geometry.firstTextY[1], 'Equal first text-line starting y');
      check.near(geometry.headingY[0], geometry.headingY[1], 'Aligned column headings');
      check.ok(geometry.right.x >= geometry.left.x + geometry.left.width, 'Columns are side by side, not stacked');
      check.ok(geometry.columnRows.length === 2 && geometry.columnRows.every(rows => rows.startsWith('subgrid')), 'Both reading columns use subgrid');
      for (const boundary of geometry.boundary) {
        check.equal(boundary.text, 'g g', 'One ASCII space followed by a terminal g');
        check.equal(boundary.border, '1px', 'Visible terminal advance marker');
        check.equal(boundary.borderStyle, 'solid');
        check.equal(boundary.display, 'inline-block');
        check.equal(boundary.whiteSpace, 'pre', 'One-line boundary sample');
      }
      const expectedDelta = B[WEIGHTS.indexOf(weight)] * 16 / UPM;
      const markerDelta = geometry.boundary[1].box.width - geometry.boundary[0].box.width;
      check.near(markerDelta, expectedDelta, 'Live terminal markers differ by +B before the single space');
      for (const text of ['g ', 'g g']) {
        check.near(geometry.boundaryRuns[text] - geometry.refinedRuns[text], expectedDelta, JSON.stringify(text) + ' has exactly one +B restoration');
      }
      check.near(geometry.boundaryRuns.g - geometry.refinedRuns.g, 0, 'Terminal g has the same advance in both states');
      return {weight, sizeCssPx: size, paragraphBoxes: {refined: geometry.left, boundary: geometry.right},
        firstTextY: geometry.firstTextY, expectedBoundaryDeltaCssPx: expectedDelta, markerDeltaCssPx: markerDelta,
        refinedBoundaryRuns: geometry.refinedRuns, boundaryTrialRuns: geometry.boundaryRuns};
    }

    await test('configuration, viewport and initial independent fonts', async () => {
      const entries = [...config.weights].sort((a, b) => a.weight - b.weight);
      check.deepEqual(entries.map(entry => entry.weight), WEIGHTS);
      check.deepEqual(entries.map(entry => entry.moderate), B);
      check.deepEqual(entries.map(entry => entry.tighter), B.map(amount => amount * 2));
      check.deepEqual(entries.map(entry => entry.gj_correction), CORRECTIONS);
      check.ok(config.space_characters.includes(' '), 'ASCII space must map to the font space glyph for the boundary test');
      for (const id of ['pairWeight', 'textWeight']) {
        check.deepEqual(await page.locator('#' + id + ' option').evaluateAll(nodes => nodes.map(node => Number(node.value))), WEIGHTS);
      }
      check.deepEqual(await page.locator('#textSize option').evaluateAll(nodes => nodes.map(node => Number(node.value))), SIZES);
      const environment = await page.evaluate(() => ({userAgent: navigator.userAgent, platform: navigator.platform,
        devicePixelRatio, width: innerWidth, height: innerHeight, visualViewportScale: visualViewport?.scale,
        bodyZoom: getComputedStyle(document.body).zoom, location: location.protocol}));
      report.renderer.environment = environment;
      check.equal(environment.location, 'file:', 'Local proof only');
      check.equal(environment.width, VIEWPORT.width);
      check.equal(environment.height, VIEWPORT.height);
      check.equal(environment.devicePixelRatio, 1);
      check.equal(environment.visualViewportScale, 1, '100% visual viewport scale');
      check.equal(environment.bodyZoom, '1', 'No CSS page zoom');
      await Promise.all([waitForFontStatus(page, 'pair', 900), waitForFontStatus(page, 'text', 400)]);
      await loadFace(900, 72);
      await loadFace(400, 16);
      expectSection(await snapshot('pair'), 'pair', 900);
      expectSection(await snapshot('text'), 'text', 400, 16);
    });

    for (const [index, weight] of WEIGHTS.entries()) {
      await test('pair weight ' + weight + ': ss15 advance and unchanged guards', async () => {
        const readingBefore = await snapshot('text');
        await page.selectOption('#pairWeight', String(weight));
        await waitForFontStatus(page, 'pair', weight);
        await loadFace(weight, 72);
        expectSection(await snapshot('pair'), 'pair', weight);
        check.deepEqual(await snapshot('text'), readingBefore, 'Pair control leaves reading weight, size, text, flags and load state unchanged');
        const widths = await page.evaluate(texts => ({
          chosen: window.__spacingFinishBrowserTest.measure('pair-chosen-gj', texts),
          refined: window.__spacingFinishBrowserTest.measure('pair-refined-gj', texts),
        }), PAIR_RUNS);
        const expected = CORRECTIONS[index] * 72 / UPM;
        const deltas = {};
        for (const text of PAIR_RUNS) {
          check.ok(widths.chosen[text] > 0 && widths.refined[text] > 0, 'Nonzero DOM advance for ' + text);
          deltas[text] = widths.refined[text] - widths.chosen[text];
          check.near(deltas[text], text === 'gj' || text === 'gjg' ? expected : 0, text + ' ss15 advance delta at ' + weight);
        }
        if (CORRECTIONS[index] > 0) check.ok(deltas.gj > 0, 'Heavy gj correction increases the advance');
        report.measurements.pairs.push({weight, sizeCssPx: 72, expectedGjDeltaCssPx: expected, widths, deltasCssPx: deltas});
        report.counts.pairWeights++;
      });
    }

    for (const weight of WEIGHTS) {
      for (const size of SIZES) {
        await test('reading weight ' + weight + ' at ' + size + ' CSS px', async () => {
          const pairsBefore = await snapshot('pair');
          await page.selectOption('#textWeight', String(weight));
          await page.selectOption('#textSize', String(size));
          await waitForFontStatus(page, 'text', weight);
          await loadFace(weight, size);
          await settledLayout();
          report.measurements.reading.push(await expectReading(weight, size));
          expectSection(await snapshot('pair'), 'pair', 900);
          check.deepEqual(await snapshot('pair'), pairsBefore, 'Reading controls leave pair weight, size, text, flags and load state unchanged');
          report.counts.readingWeightSizes++;
        });
      }
    }

    await test('all nine embedded FontFace objects are actually loaded', async () => {
      report.fonts = await page.evaluate(async () => {
        await document.fonts.ready;
        return Array.from(document.fonts).filter(face => face.family.replace(/^["']|["']$/g, '') === 'SpacingProof')
          .map(face => ({family: face.family, weight: face.weight, style: face.style, status: face.status}))
          .sort((a, b) => Number(a.weight) - Number(b.weight));
      });
      check.equal(report.fonts.length, 9);
      check.deepEqual(report.fonts.map(face => Number(face.weight)), WEIGHTS);
      check.ok(report.fonts.every(face => face.status === 'loaded' && face.style === 'normal'), 'No unloaded or fallback-only weight passes');
      report.counts.loadedFontFaces = report.fonts.length;
    });

    for (const weight of [400, 900]) {
      for (const size of SIZES) {
        await test('reading screenshot ' + weight + ' / ' + size, async () => {
          await page.selectOption('#textWeight', String(weight));
          await page.selectOption('#textSize', String(size));
          await waitForFontStatus(page, 'text', weight);
          await settledLayout();
          await expectReading(weight, size);
          const filename = 'reading-' + weight + '-' + size + '.png';
          const image = await page.locator('#textComparison').screenshot({path: path.join(outputDirectory, filename),
            type: 'png', scale: 'css', animations: 'disabled', caret: 'hide', timeout: ACTION_TIMEOUT});
          check.equal(image.subarray(0, 8).toString('hex'), '89504e470d0a1a0a', 'PNG screenshot');
          report.screenshots.push({file: 'browser/' + filename, weight, sizeCssPx: size,
            target: '#textComparison', deviceScaleFactor: 1,
            pixels: {width: image.readUInt32BE(16), height: image.readUInt32BE(20)}});
          report.counts.screenshots++;
        });
      }
    }

    await test('coverage complete; no font, console, page or network errors', async () => {
      report.fontLoadingErrors = await page.evaluate(() => window.__spacingFinishFontErrors);
      check.equal(report.counts.pairWeights, 9);
      check.equal(report.counts.readingWeightSizes, 27);
      check.equal(report.counts.loadedFontFaces, 9);
      check.equal(report.counts.screenshots, 6);
      check.deepEqual(report.fontLoadingErrors, [], 'No FontFaceSet loadingerror events');
      check.deepEqual(report.consoleErrors, [], 'No browser console errors');
      check.deepEqual(report.pageErrors, [], 'No uncaught page errors');
      check.deepEqual(report.failedRequests, [], 'No failed local assets or fonts');
      check.deepEqual(report.blockedRequests, [], 'No HTTP/HTTPS requests attempted (all would be aborted)');
    });
  }

  try {
    await bounded(run(), RUN_TIMEOUT, 'Browser validation');
  } catch (error) {
    failure = error;
  } finally {
    closing = true;
    if (browser) {
      try {
        await bounded(browser.close(), CLOSE_TIMEOUT, 'browser.close');
      } catch (error) {
        closeFinished = false;
        report.closeError = error.message;
        failure ||= error;
      }
    }
    report.status = failure ? 'failed' : 'passed';
    if (failure) report.error = failure.stack || failure.message;
    try {
      fs.writeFileSync(path.join(outputDirectory, 'validation.json'), JSON.stringify(report, null, 2) + '\n', 'utf8');
    } finally {
      if (closeFinished) clearTimeout(hardStop);
    }
  }
  if (failure) throw failure;
  console.log('PASS: ' + report.counts.casesPassed + ' browser cases, ' + report.counts.assertions +
    ' assertions; 9 pair weights, 27 reading weight/size combinations, 9 loaded faces and 6 screenshots.');
  console.log('Browser-only artifacts: ' + outputDirectory);
}

main().catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
