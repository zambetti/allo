'use strict';

/*
 * Offline, real-browser checks. All generated HTML lives in an OS temporary
 * directory and is removed on exit. No builds or fonts change. Optional screenshot
 * output is retained only in an explicitly supplied, existing directory.
 *
 * node tests/test_variable_proof_browser.js \
 *   /opt/homebrew/lib/python3.11/site-packages/playwright/driver/package
 *
 * Optional: --font=/path/to/full-variable.woff2 --executable=/path/to/chromium
 *           --proof=/path/to/existing-proof.html --screenshots=/existing/directory
 * --proof validates an existing generated page instead of generating a new one.
 * Defaults to the current custom WOFF2 if available, otherwise the shipped one.
 * Uses the existing .venv and Playwright/browser installation; never installs.
 * These checks exercise shaping controls, not the design of the ss04 glyph.
 */

const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const {createHash} = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {pathToFileURL} = require('node:url');

const ROOT = path.resolve(__dirname, '..');
const CONFIG = /(<script id="variable-proof-data" type="application\/json">)([\s\S]*?)(<\/script>)/;
const LAUNCH_TIMEOUT = 15000;
const ACTION_TIMEOUT = 10000;
const RUN_TIMEOUT = 120000;
const CLOSE_TIMEOUT = 5000;

function argumentsFromCLI() {
  let packagePath;
  let executablePath;
  let fontPath;
  let proofPath;
  let screenshotDirectory;
  for (const arg of process.argv.slice(2)) {
    if (arg.startsWith('--font=')) {
      assert.ok(!fontPath, 'Only one --font is allowed');
      fontPath = path.resolve(arg.slice('--font='.length));
    } else if (arg.startsWith('--proof=')) {
      assert.ok(!proofPath, 'Only one --proof is allowed');
      proofPath = path.resolve(arg.slice('--proof='.length));
    } else if (arg.startsWith('--screenshots=')) {
      assert.ok(!screenshotDirectory, 'Only one --screenshots is allowed');
      screenshotDirectory = path.resolve(arg.slice('--screenshots='.length));
      assert.ok(fs.statSync(screenshotDirectory).isDirectory(), 'Screenshot directory must already exist');
    } else if (arg.startsWith('--executable=')) {
      assert.ok(!executablePath, 'Only one --executable is allowed');
      executablePath = path.resolve(arg.slice('--executable='.length));
    } else {
      assert.ok(!packagePath && !arg.startsWith('--'), 'Expected one optional Playwright package path');
      packagePath = path.resolve(arg);
    }
  }
  const custom = path.join(ROOT, 'build/custom/fonts/webfonts/AlloCustomVariable.woff2');
  fontPath ||= fs.existsSync(custom) ? custom : path.join(ROOT, 'fonts/webfonts/AlloVariable.woff2');
  return {packagePath, executablePath, fontPath, proofPath, screenshotDirectory};
}

function bounded(promise, milliseconds, label) {
  let timer;
  return Promise.race([
    promise,
    new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error(label + ' timed out after ' + milliseconds + ' ms')), milliseconds);
    }),
  ]).finally(() => clearTimeout(timer));
}

function settings(value) {
  return Object.fromEntries(value.split(',').map(entry => {
    const match = entry.trim().match(/^"([^"]{4})"(?:\s+(-?[\d.]+|on|off))?$/);
    assert.ok(match, 'Unexpected CSS setting: ' + entry);
    return [match[1], match[2] === undefined || match[2] === 'on' ? 1 : match[2] === 'off' ? 0 : Number(match[2])];
  }));
}

async function setRange(page, selector, value) {
  await page.locator(selector).evaluate((element, next) => {
    element.value = next;
    element.dispatchEvent(new Event('input', {bubbles: true}));
  }, String(value));
}

async function snapshot(page) {
  return page.evaluate(() => {
    const byId = id => document.getElementById(id);
    const sample = id => {
      const element = byId(id);
      const style = getComputedStyle(element);
      return {
        text: element.textContent,
        nodes: [...element.childNodes].map(node => node.nodeType),
        hidden: element.hidden,
        family: style.fontFamily.replace(/^['"]|['"]$/g, ''),
        axes: style.fontVariationSettings,
        features: style.fontFeatureSettings,
        kerning: style.fontKerning,
        size: style.fontSize,
        opticalSizing: style.fontOpticalSizing,
        synthesis: style.fontSynthesis,
        fontStyle: style.fontStyle,
        letterSpacing: style.letterSpacing,
      };
    };
    return {
      main: sample('main-pair'), comparison: sample('comparison-pair'),
      axes: [...document.querySelectorAll('[data-axis]')].map(slider => ({
        tag: slider.dataset.axis, min: Number(slider.min), max: Number(slider.max),
        value: Number(slider.value), label: slider.labels[0]?.textContent,
        output: document.querySelector('output[for="' + slider.id + '"]')?.value,
      })),
      css: byId('css-readout').textContent,
      summary: byId('axis-summary').value,
      fontState: byId('font-status').dataset.state,
      fontStatus: byId('font-status').textContent,
      features: byId('feature-status').textContent,
      coverage: {hidden: byId('coverage-status').hidden, text: byId('coverage-status').textContent},
      comparisonHidden: byId('comparison-card').hidden,
      faces: [...document.fonts].map(face => ({family: face.family, status: face.status, weight: face.weight})),
    };
  });
}

async function layoutSnapshot(page) {
  return page.evaluate(() => {
    const box = element => {
      const rect = element.getBoundingClientRect();
      return {top: rect.top, bottom: rect.bottom, left: rect.left, right: rect.right, height: rect.height};
    };
    const controls = selector => [...document.querySelectorAll(selector)].map(element => ({
      id: element.id || element.getAttribute('aria-label'), ...box(element),
    }));
    return {
      viewport: {width: innerWidth, height: innerHeight}, scrollY,
      documentWidth: document.documentElement.scrollWidth,
      controls: controls('.workbench input, .workbench button'),
      axes: controls('[data-axis]'), size: box(document.getElementById('preview-size')),
      main: box(document.getElementById('main-pair')),
      comparison: box(document.getElementById('comparison-pair')),
      coordinates: [...document.querySelectorAll('[data-axis]')].map(slider => [slider.dataset.axis, Number(slider.value)]),
    };
  });
}

function assertInViewport(box, viewport, label) {
  assert.ok(box.height > 0 && box.top >= 0 && box.bottom <= viewport.height
    && box.left >= 0 && box.right <= viewport.width,
  label + ' must remain fully in the viewport: ' + JSON.stringify({box, viewport}));
}

async function waitForState(page, state) {
  await page.waitForFunction(expected => {
    const status = document.getElementById('font-status');
    if (expected === 'ready' && status?.dataset.state === 'failed') throw new Error(status.textContent);
    return status && status.dataset.state === expected;
  }, state);
}

async function main() {
  const options = argumentsFromCLI();
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'allo-variable-proof-browser-'));
  const proof = options.proofPath || path.join(directory, 'variable-proof.html');
  const original = fs.readFileSync(options.fontPath);
  const originalTime = fs.statSync(options.fontPath).mtimeMs;
  let browser;
  let passed = 0;
  const errors = [];
  const requests = [];
  const blocked = [];
  const screenshots = [];
  const hardStop = setTimeout(() => {
    console.error('Browser validation exceeded its total run/cleanup budget.');
    process.exit(1);
  }, RUN_TIMEOUT + CLOSE_TIMEOUT + 2000);
  hardStop.unref();

  async function test(name, run) {
    await run();
    passed += 1;
    console.log('PASS ' + name);
  }

  try {
    if (!options.proofPath) {
      execFileSync(path.join(ROOT, '.venv/bin/python'), [
        '-B', '-c', 'import sys; from variable_proof import write_variable_proof; write_variable_proof(sys.argv[1], sys.argv[2])',
        options.fontPath, proof,
      ], {cwd: ROOT, timeout: 30000, stdio: 'pipe'});
    }
    const html = fs.readFileSync(proof, 'utf8');
    const config = JSON.parse(html.match(CONFIG)[2]);
    assert.deepEqual(Buffer.from(config.fontBase64, 'base64'), original);
    assert.equal(config.sha256, createHash('sha256').update(original).digest('hex'));
    const variant = (filename, changes) => {
      const data = JSON.stringify({...config, ...changes}).replace(/[<>&]/g, char => ({'<': '\\u003c', '>': '\\u003e', '&': '\\u0026'}[char]));
      const target = path.join(directory, filename);
      fs.writeFileSync(target, html.replace(CONFIG, (_, start, _old, end) => start + data + end));
      return target;
    };

    async function capture(page, name, fullPage = false) {
      if (!options.screenshotDirectory) return;
      const filename = path.join(options.screenshotDirectory, 'variable-proof-' + name + '.png');
      await page.screenshot({path: filename, fullPage, animations: 'disabled', caret: 'hide', timeout: ACTION_TIMEOUT});
      screenshots.push({file: path.relative(ROOT, filename), fullPage, ...await layoutSnapshot(page)});
    }

    async function run() {
      const {chromium} = require(options.packagePath || 'playwright');
      browser = await chromium.launch({headless: true, timeout: LAUNCH_TIMEOUT,
        ...(options.executablePath ? {executablePath: options.executablePath} : {})});
      console.log('Chromium ' + browser.version() + ' · ' + path.relative(ROOT, options.fontPath));
      const context = await browser.newContext({
        viewport: {width: 1365, height: 900}, deviceScaleFactor: 1, offline: true,
        serviceWorkers: 'block', locale: 'en-US', colorScheme: 'light',
      });
      context.setDefaultTimeout(ACTION_TIMEOUT);
      context.setDefaultNavigationTimeout(LAUNCH_TIMEOUT);
      await context.route(/^https?:\/\//i, async route => {
        blocked.push(route.request().url());
        await route.abort('blockedbyclient');
      });
      const page = await context.newPage();
      page.on('pageerror', error => {
        errors.push(error.message);
        console.error('Browser page error: ' + error.message);
      });
      page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
      page.on('requestfailed', request => errors.push(request.url().slice(0, 120) + ': ' + request.failure()?.errorText));
      context.on('request', request => requests.push(request.url().split(':', 1)[0]));
      await page.goto(pathToFileURL(proof).href, {waitUntil: 'load'});
      await waitForState(page, 'ready');
      const defaults = Object.fromEntries(config.axes.map(axis => [axis.tag, axis.default]));
      const selectors = config.axes.map((_, index) => '#axis-' + index);

      await test('file:// loads the exact embedded font offline with all fvar defaults', async () => {
        assert.ok(page.url().startsWith('file:'));
        const state = await snapshot(page);
        assert.equal(state.fontState, 'ready');
        assert.match(state.fontStatus, /Embedded font loaded/);
        assert.deepEqual(state.faces.map(face => [face.family, face.status]), [[config.fontFamily, 'loaded']]);
        assert.equal(state.main.family, config.fontFamily);
        assert.equal(state.main.text, 'ng');
        assert.deepEqual(state.main.nodes, [3]);
        assert.deepEqual(state.comparison.nodes, [3]);
        assert.deepEqual(settings(state.main.axes), defaults);
        assert.equal(state.main.axes, state.comparison.axes);
        assert.equal(state.main.hidden, false);
        assert.equal(state.comparisonHidden, false);
        assert.equal(state.main.size, '176px');
        assert.equal(state.main.opticalSizing, 'none');
        assert.equal(state.main.synthesis, 'none');
        assert.equal(state.main.fontStyle, 'normal');
        assert.ok(['0px', 'normal'].includes(state.main.letterSpacing));
        assert.deepEqual(settings(state.main.features), {ss04: 1, ss01: 0, kern: 1});
        assert.deepEqual(settings(state.comparison.features), {ss04: 0, ss01: 0, kern: 1});
        assert.equal(state.axes.length, config.axes.length);
        for (const [index, axis] of config.axes.entries()) {
          assert.equal(state.axes[index].tag, axis.tag);
          assert.equal(state.axes[index].min, axis.min);
          assert.equal(state.axes[index].max, axis.max);
          assert.equal(state.axes[index].value, axis.default);
          assert.equal(state.axes[index].output, String(axis.default));
          assert.ok(state.axes[index].label.includes(axis.name));
        }
        if (!config.features.includes('ss04')) assert.match(state.features, /Not advertised.*ss04/);
      });

      await test('laptop controls and both previews stay in view throughout real slider dragging', async () => {
        for (const width of [1365, 1200]) {
          await page.setViewportSize({width, height: 900});
          await page.locator('#reset').click();
          await page.evaluate(() => scrollTo(0, 0));
          const checkLayout = async () => {
            const layout = await layoutSnapshot(page);
            assert.equal(layout.scrollY, 0, 'Dragging must not require page scrolling');
            for (const control of layout.controls) assertInViewport(control, layout.viewport, control.id);
            assertInViewport(layout.main, layout.viewport, 'Main pair');
            assertInViewport(layout.comparison, layout.viewport, 'Comparison pair');
          };
          await checkLayout();
          if (width === 1365) await capture(page, 'desktop');
          for (const [index, axis] of config.axes.entries()) {
            if (axis.min === axis.max) continue;
            const slider = await page.locator(selectors[index]).boundingBox();
            const y = slider.y + slider.height / 2;
            await page.mouse.move(slider.x + slider.width * .2, y);
            await page.mouse.down();
            try {
              for (const fraction of [.35, .65, .85]) {
                await page.mouse.move(slider.x + slider.width * fraction, y, {steps: 3});
                await checkLayout();
                const state = await snapshot(page);
                const value = state.axes[index].value;
                // Computed CSS rounds dragged fractional coordinates to six significant digits.
                assert.ok(Math.abs(settings(state.main.axes)[axis.tag] - value) <= Math.max(1e-5, Math.abs(value) * 5e-6));
                assert.equal(state.main.axes, state.comparison.axes);
              }
            } finally {
              await page.mouse.up();
            }
            assert.ok((await snapshot(page)).axes[index].value > axis.min + (axis.max - axis.min) * .7,
              'Pointer dragging must actually change ' + axis.tag);
          }
          if (width === 1365) await capture(page, 'desktop-sliding');
        }
        await page.setViewportSize({width: 1365, height: 900});
        await page.locator('#reset').click();
      });

      await test('layout containers contain no stray markup text', async () => {
        const stray = await page.locator('main, .workbench, .workspace').evaluateAll(elements =>
          elements.flatMap(element => [...element.childNodes]
            .filter(node => node.nodeType === Node.TEXT_NODE && node.textContent.trim())
            .map(node => node.textContent.trim())));
        assert.deepEqual(stray, []);
      });

      await test('each axis reaches its bounds and synchronizes both runs, output and CSS', async () => {
        for (const [index, axis] of config.axes.entries()) {
          for (const value of [axis.min, axis.max, axis.default]) {
            await setRange(page, selectors[index], value);
            const state = await snapshot(page);
            assert.equal(settings(state.main.axes)[axis.tag], value);
            assert.equal(state.main.axes, state.comparison.axes);
            assert.equal(state.axes[index].output, String(value));
            assert.ok(state.summary.includes(axis.tag + ' ' + value));
            assert.ok(state.css.includes(JSON.stringify(axis.tag) + ' ' + value));
            assert.equal(state.main.size, '176px');
          }
        }
      });

      await test('editable combining clusters and every preset remain a single unmodified text run', async () => {
        await page.locator('#left-character').fill('g\u0301');
        await page.locator('#right-character').fill('o\u0308');
        let state = await snapshot(page);
        assert.equal(state.main.text, 'g\u0301o\u0308');
        assert.equal(state.main.text, state.comparison.text);
        assert.deepEqual(state.main.nodes, [3]);
        assert.deepEqual(state.comparison.nodes, [3]);
        for (const button of await page.locator('[data-left]').all()) {
          const expected = (await button.getAttribute('data-left')) + (await button.getAttribute('data-right'));
          await button.click();
          state = await snapshot(page);
          assert.equal(state.main.text, expected);
          assert.equal(state.comparison.text, expected);
          assert.deepEqual(state.main.nodes, [3]);
        }
        await page.locator('#left-character').fill('<g>');
        await page.locator('#right-character').fill('&');
        state = await snapshot(page);
        assert.equal(state.main.text, '<g>&');
        assert.deepEqual(state.main.nodes, [3]);
        await page.locator('#left-character').fill('');
        await page.locator('#right-character').fill('');
        assert.equal((await snapshot(page)).main.text, '');
      });

      await test('font size is independent of opsz and the comparison matches', async () => {
        const before = (await snapshot(page)).main.axes;
        for (const value of [24, 320, 147]) {
          await setRange(page, '#preview-size', value);
          const state = await snapshot(page);
          assert.equal(state.main.size, value + 'px');
          assert.equal(state.comparison.size, state.main.size);
          assert.equal(state.main.axes, before);
          assert.ok(state.css.includes('font-size: ' + value + 'px;'));
        }
      });

      await test('ss04, ss01, kerning and comparison switches are independent and explicit', async () => {
        await page.locator('#ss01').check();
        await page.locator('#kerning').uncheck();
        let state = await snapshot(page);
        assert.deepEqual(settings(state.main.features), {ss04: 1, ss01: 1, kern: 0});
        assert.deepEqual(settings(state.comparison.features), {ss04: 0, ss01: 1, kern: 0});
        assert.equal(state.main.kerning, 'none');
        assert.equal(state.comparison.kerning, 'none');
        await page.locator('#ss04').uncheck();
        state = await snapshot(page);
        assert.deepEqual(state.main, state.comparison);
        assert.ok(state.css.includes('"ss04" 0'));
        await page.locator('#show-comparison').uncheck();
        assert.equal((await snapshot(page)).comparisonHidden, true);
        await page.locator('#show-comparison').check();
        assert.equal((await snapshot(page)).comparisonHidden, false);
      });

      await test('reset restores text, axes, size and every feature/comparison default', async () => {
        for (const [index, axis] of config.axes.entries()) await setRange(page, selectors[index], axis.max);
        await page.locator('#show-comparison').uncheck();
        await page.locator('#reset').click();
        const state = await snapshot(page);
        assert.equal(state.main.text, 'ng');
        assert.equal(state.comparison.text, 'ng');
        assert.equal(state.main.size, '176px');
        assert.deepEqual(settings(state.main.axes), defaults);
        assert.equal(state.main.axes, state.comparison.axes);
        assert.deepEqual(settings(state.main.features), {ss04: 1, ss01: 0, kern: 1});
        assert.deepEqual(settings(state.comparison.features), {ss04: 0, ss01: 0, kern: 1});
        assert.equal(state.comparisonHidden, false);
        assert.equal(state.main.kerning, 'normal');
      });

      await test('native keyboard sliders and feature toggles work; every input has a label', async () => {
        const unlabeled = await page.locator('input').evaluateAll(inputs => inputs.filter(input => !input.labels.length).map(input => input.id));
        assert.deepEqual(unlabeled, []);
        for (const [index, axis] of config.axes.entries()) {
          if (axis.min === axis.max) continue;
          await setRange(page, selectors[index], axis.min);
          await page.locator(selectors[index]).focus();
          await page.keyboard.press('ArrowRight');
          assert.ok((await snapshot(page)).axes[index].value > axis.min);
        }
        await page.locator('#ss01').focus();
        await page.keyboard.press('Space');
        assert.equal(settings((await snapshot(page)).main.features).ss01, 1);
        await page.locator('#reset').focus();
        await page.keyboard.press('Enter');
        assert.equal(settings((await snapshot(page)).main.features).ss01, 0);
      });

      await test('unsupported characters produce an explicit fallback warning', async () => {
        await page.locator('#right-character').fill('\u{10ffff}');
        let state = await snapshot(page);
        assert.equal(state.coverage.hidden, false);
        assert.match(state.coverage.text, /U\+10FFFF.*fallback/);
        await page.locator('#reset').click();
        state = await snapshot(page);
        assert.equal(state.coverage.hidden, true);
      });

      await test('mobile axes and main pair share the scrolled workspace without sticky overlays', async () => {
        await page.setViewportSize({width: 390, height: 844});
        await page.locator('#reset').click();
        await page.evaluate(() => scrollTo(0, 0));
        await capture(page, 'mobile', true);
        await page.evaluate(() => scrollTo(0, document.querySelector('.axes').getBoundingClientRect().top + scrollY - 12));
        const before = await layoutSnapshot(page);
        for (const axis of before.axes) assertInViewport(axis, before.viewport, axis.id);
        assertInViewport(before.size, before.viewport, 'Preview size');
        assertInViewport(before.main, before.viewport, 'Main pair');
        assert.ok(before.documentWidth <= before.viewport.width);
        await capture(page, 'mobile-workspace');
        const slider = page.locator('[data-axis]').last();
        await slider.focus();
        await page.keyboard.press('ArrowRight');
        const after = await layoutSnapshot(page);
        assert.equal(after.scrollY, before.scrollY, 'An in-view slider must not scroll the pair away');
        assertInViewport(after.main, after.viewport, 'Main pair after keyboard sliding');
        await page.locator('#reset').click();
      });

      await test('desktop and narrow mobile layouts contain oversized previews without page overflow', async () => {
        for (const width of [1200, 390, 320]) {
          await page.setViewportSize({width, height: 844});
          await setRange(page, '#preview-size', 320);
          await page.locator('#left-character').fill('gggg');
          await page.locator('#right-character').fill('gggg');
          const layout = await page.evaluate(() => ({
            viewport: innerWidth, page: document.documentElement.scrollWidth,
            cards: [...document.querySelectorAll('.preview')].map(element => ({
              x: element.getBoundingClientRect().x, width: element.getBoundingClientRect().width,
            })),
            scrollers: [...document.querySelectorAll('.sample-viewport')].map(element => ({
              width: element.clientWidth, scrollWidth: element.scrollWidth,
            })),
          }));
          assert.ok(layout.page <= layout.viewport + 1, JSON.stringify(layout));
          assert.ok(layout.cards.every(card => card.x >= 0 && card.x + card.width <= width + 1));
          assert.ok(layout.scrollers.every(scroller => scroller.scrollWidth > scroller.width));
        }
        await page.locator('#reset').click();
      });

      await test('normal operation has no console, page, request, or network errors', async () => {
        assert.deepEqual(errors, []);
        assert.deepEqual(blocked, []);
        assert.ok(requests.every(protocol => ['file', 'data'].includes(protocol)), requests.join(', '));
      });

      await test('untrusted font/axis labels are rendered only as text', async () => {
        const hostile = '</script><img src="https://invalid.example/p" onerror="window.injected=true">';
        const target = variant('labels.html', {
          family: hostile, axes: config.axes.map(axis => ({...axis, name: hostile})),
        });
        const probe = await context.newPage();
        await probe.goto(pathToFileURL(target).href);
        await waitForState(probe, 'ready');
        assert.equal(await probe.locator('#font-name').textContent(), hostile);
        assert.equal(await probe.locator('img').count(), 0);
        assert.equal(await probe.evaluate(() => window.injected), undefined);
        await probe.close();
      });

      await test('corrupt embedded font explicitly fails and never exposes a fallback preview', async () => {
        const target = variant('broken.html', {fontBase64: Buffer.from('not a WOFF2 font').toString('base64')});
        const probe = await context.newPage();
        await probe.goto(pathToFileURL(target).href);
        await waitForState(probe, 'failed');
        let state = await snapshot(probe);
        assert.match(state.fontStatus, /Font load failed.*no fallback proof/);
        assert.equal(state.main.hidden, true);
        assert.equal(state.comparison.hidden, true);
        await probe.locator('#left-character').fill('a');
        await probe.locator('#reset').click();
        state = await snapshot(probe);
        assert.equal(state.main.hidden, true);
        assert.equal(state.comparison.hidden, true);
        await probe.close();
      });

      await test('missing Font Loading API has an explicit visible failure', async () => {
        const probe = await context.newPage();
        await probe.addInitScript(() => { window.FontFace = undefined; });
        await probe.goto(pathToFileURL(proof).href);
        await waitForState(probe, 'failed');
        const state = await snapshot(probe);
        assert.match(state.fontStatus, /does not support the Font Loading API/);
        assert.equal(state.main.hidden, true);
        await probe.close();
      });

      await test('a stalled font load is bounded and reported rather than hanging invisibly', async () => {
        const probe = await context.newPage();
        await probe.addInitScript(() => {
          window.FontFace = class { load() { return new Promise(() => {}); } };
          const original = window.setTimeout.bind(window);
          window.setTimeout = (callback, ms, ...args) => original(callback, ms === 15000 ? 20 : ms, ...args);
        });
        await probe.goto(pathToFileURL(proof).href);
        await waitForState(probe, 'failed');
        const state = await snapshot(probe);
        assert.match(state.fontStatus, /did not load within 15 seconds/);
        assert.equal(state.main.hidden, true);
        await probe.close();
      });

      await test('JavaScript-disabled browsers explain the requirement and hide both previews', async () => {
        const noJS = await browser.newContext({javaScriptEnabled: false, offline: true, serviceWorkers: 'block'});
        const probe = await noJS.newPage();
        probe.setDefaultTimeout(ACTION_TIMEOUT);
        probe.setDefaultNavigationTimeout(LAUNCH_TIMEOUT);
        await probe.goto(pathToFileURL(proof).href);
        assert.match(await probe.locator('noscript').textContent(), /JavaScript is required/);
        assert.equal(await probe.locator('#main-pair').isVisible(), false);
        assert.equal(await probe.locator('#comparison-pair').isVisible(), false);
        await noJS.close();
      });

      await test('source font stays byte-identical and every page remains network-free', async () => {
        assert.deepEqual(fs.readFileSync(options.fontPath), original);
        assert.equal(fs.statSync(options.fontPath).mtimeMs, originalTime);
        assert.deepEqual(blocked, []);
        assert.ok(requests.every(protocol => ['file', 'data'].includes(protocol)));
      });
      await context.close();
    }

    await bounded(run(), RUN_TIMEOUT, 'Browser validation');
    console.log(passed + ' browser checks passed. Run validate_g.py separately for compiled-font geometry and shaping checks.');
    if (options.screenshotDirectory) {
      const report = path.join(options.screenshotDirectory, 'variable-proof-layout.json');
      fs.writeFileSync(report, JSON.stringify({
        browser: browser.version(), proof: path.relative(ROOT, proof),
        fontSha256: config.sha256, ss04: config.features.includes('ss04'),
        passed, networkRequests: blocked, screenshots,
      }, null, 2) + '\n');
      console.log('Screenshots and layout measurements: ' + path.relative(ROOT, report));
    }
  } finally {
    try {
      if (browser) await bounded(browser.close(), CLOSE_TIMEOUT, 'Browser close');
    } finally {
      fs.rmSync(directory, {recursive: true, force: true});
      clearTimeout(hardStop);
    }
  }
}

main().catch(error => {
  console.error(error.stack || String(error));
  process.exitCode = 1;
});
