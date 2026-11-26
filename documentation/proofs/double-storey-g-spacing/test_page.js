'use strict';

/*
 * Run after the parent builder creates proof.html:
 *   node documentation/proofs/double-storey-g-spacing/test_page.js
 * An optional first argument selects another generated HTML file.
 *
 * Mocked DOM interface used by page.py:
 *   document.getElementById(id), document.querySelectorAll('.class'),
 *   document.fonts.load(cssFont, sampleText) -> Promise<FontFace[]>;
 *   elements: value, textContent, dataset, style, addEventListener(type, fn).
 * Required IDs: weight, mode, size, words, sizeValue, weightSummary,
 *   fontStatus, modeExplanation, amount-a/b/c, features-a/b/c.
 * Sample classes: font-sample, custom-text, adjustable, reading-text;
 *   each font-sample carries data-variant="a", "b", or "c".
 * Controls emit change (weight/mode) or input (size/words).
 * The mock rejects HTML insertion. It does not implement layout, shaping,
 * CSS cascade, real font loading, or browser rendering.
 */

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const expectedWeights = [100, 200, 300, 400, 500, 600, 700, 800, 900];
const featureTags = ['ss17', 'ss18', 'ss19', 'ss20'];
const variants = ['a', 'b', 'c'];

function decodeEntities(text) {
  const named = {amp: '&', lt: '<', gt: '>', quot: '"', apos: "'"};
  return text.replace(/&(#x[0-9a-f]+|#\d+|amp|lt|gt|quot|apos);/gi, (_, entity) => {
    if (entity[0] !== '#') return named[entity.toLowerCase()];
    const hex = entity[1].toLowerCase() === 'x';
    return String.fromCodePoint(parseInt(entity.slice(hex ? 2 : 1), hex ? 16 : 10));
  });
}

function attributes(source) {
  const result = Object.create(null);
  const pattern = /([^\s=/>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g;
  for (const match of source.matchAll(pattern)) {
    result[match[1].toLowerCase()] = decodeEntities(match[2] ?? match[3] ?? match[4] ?? '');
  }
  return result;
}

class MockElement {
  constructor(tag, attrs, content) {
    this.tagName = tag.toUpperCase();
    this.attributes = attrs;
    this.id = attrs.id || '';
    this.classes = (attrs.class || '').split(/\s+/).filter(Boolean);
    this.dataset = Object.create(null);
    this.style = Object.create(null);
    this.listeners = new Map();
    this.textWrites = 0;
    this._text = decodeEntities(content.replace(/<[^>]*>/g, ''));
    this.value = attrs.value ?? (tag === 'textarea' ? this._text : '');
    for (const [name, value] of Object.entries(attrs)) {
      if (name.startsWith('data-')) this.dataset[this.camelCase(name.slice(5))] = value;
    }
    for (const declaration of (attrs.style || '').split(';')) {
      const colon = declaration.indexOf(':');
      if (colon !== -1) {
        this.style[this.camelCase(declaration.slice(0, colon).trim())] = declaration.slice(colon + 1).trim();
      }
    }
    if (tag === 'select') {
      this.options = Array.from(content.matchAll(/<option\b([^>]*)>([\s\S]*?)<\/option>/gi), match => {
        const option = attributes(match[1]);
        return {value: option.value, label: decodeEntities(match[2]), selected: 'selected' in option};
      });
      this.value = (this.options.find(option => option.selected) || this.options[0]).value;
    }
  }

  camelCase(name) {
    return name.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
  }

  get textContent() { return this._text; }
  set textContent(value) {
    this._text = String(value);
    this.textWrites += 1;
  }
  get innerHTML() { throw new Error('Use textContent, not innerHTML'); }
  set innerHTML(value) { throw new Error('Unsafe innerHTML assignment: ' + value); }
  set outerHTML(value) { throw new Error('Unsafe outerHTML assignment: ' + value); }
  insertAdjacentHTML() { throw new Error('Unsafe HTML insertion'); }

  addEventListener(type, listener) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(listener);
  }

  dispatch(type) {
    const listeners = this.listeners.get(type) || [];
    assert.ok(listeners.length, this.id + ' must listen for ' + type);
    for (const listener of listeners) listener({type, target: this});
  }
}

function mockDOM(html, withFontAPI = true) {
  // A bounded reader for this renderer's markup, not a general-purpose HTML parser.
  // Script/style contents are excluded so JavaScript and data URLs cannot be tags.
  const markup = html.replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1\s*>/gi, '');
  const elements = [];
  const ids = new Map();
  for (const match of markup.matchAll(/<([a-z][\w:-]*)\b([^>]*)>/gi)) {
    const tag = match[1].toLowerCase();
    const attrs = attributes(match[2]);
    const start = match.index + match[0].length;
    const end = markup.indexOf('</' + tag + '>', start);
    const content = end === -1 ? '' : markup.slice(start, end);
    const element = new MockElement(tag, attrs, content);
    elements.push(element);
    if (element.id) {
      assert.ok(!ids.has(element.id), 'Duplicate ID: ' + element.id);
      ids.set(element.id, element);
    }
  }
  const loads = [];
  const document = {
    getElementById(id) {
      assert.ok(ids.has(id), 'Missing DOM ID: ' + id);
      return ids.get(id);
    },
    querySelectorAll(selector) {
      assert.match(selector, /^\.[\w-]+$/, 'Mock supports single-class selectors only');
      return elements.filter(element => element.classes.includes(selector.slice(1)));
    },
  };
  if (withFontAPI) {
    document.fonts = {
      load(descriptor, text) {
        return new Promise((resolve, reject) => loads.push({descriptor, text, resolve, reject}));
      },
    };
  }
  return {document, elements, loads, ids};
}

function expectedFeatures(variant, mode) {
  const selected = variant === 'a' ? null :
    (mode === 'round' ? {b: 'ss19', c: 'ss20'} : {b: 'ss17', c: 'ss18'})[variant];
  return featureTags.map(tag => '"' + tag + '" ' + (tag === selected ? 1 : 0)).join(', ');
}

function assertSettings(harness, entry, mode) {
  const {document} = harness;
  for (const sample of document.querySelectorAll('.font-sample')) {
    assert.ok(variants.includes(sample.dataset.variant));
    assert.equal(sample.style.fontWeight, String(entry.weight), 'All samples use the selected weight');
    assert.equal(sample.style.fontFeatureSettings, expectedFeatures(sample.dataset.variant, mode),
      'Every sample must explicitly set all four features; modes must not accumulate');
  }
  for (const variant of variants) {
    assert.equal(document.getElementById('features-' + variant).textContent, expectedFeatures(variant, mode));
  }
  assert.match(document.getElementById('amount-a').textContent, /^0 font units/);
  assert.ok(document.getElementById('amount-b').textContent.startsWith('−' + entry.moderate + ' font units'));
  assert.ok(document.getElementById('amount-c').textContent.startsWith('−' + entry.tighter + ' font units'));
  const summary = document.getElementById('weightSummary').textContent;
  assert.ok(summary.includes(entry.style + ' · ' + entry.weight));
  assert.ok(summary.includes('B: −' + entry.moderate + '; C: −' + entry.tighter + ' font units'));
  const explanation = document.getElementById('modeExplanation').textContent;
  if (mode === 'round') {
    assert.match(explanation, /go \/ ge \/ gc/);
    assert.match(explanation, /ss19/);
    assert.match(explanation, /ss20/);
    assert.match(explanation, /spaces and terminal g keep inherited/);
    assert.match(document.getElementById('amount-b').textContent, /ss19$/);
    assert.match(document.getElementById('amount-c').textContent, /ss20$/);
  } else {
    assert.match(explanation, /stress test, not a recommendation/);
    assert.match(explanation, /SinglePos XAdvance/);
    assert.match(explanation, /before spaces and at text end/);
    assert.match(explanation, /over-tighten descenders and punctuation/);
    assert.match(document.getElementById('amount-b').textContent, /ss17$/);
    assert.match(document.getElementById('amount-c').textContent, /ss18$/);
  }
}

const flushPromises = () => new Promise(resolve => setImmediate(resolve));

async function settle(request, result = [{status: 'loaded'}]) {
  request.resolve(result);
  await flushPromises();
}

async function reject(request) {
  request.reject(new Error('Simulated embedded font failure'));
  await flushPromises();
}

function startScript(html, script, withFontAPI = true) {
  const harness = mockDOM(html, withFontAPI);
  script.runInContext(vm.createContext({document: harness.document}), {timeout: 1000});
  return harness;
}

async function main() {
  const filename = process.argv[2] ? path.resolve(process.argv[2]) : path.join(__dirname, 'proof.html');
  const html = fs.readFileSync(filename, 'utf8');
  const scripts = Array.from(html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi));
  assert.equal(scripts.length, 1, 'Exactly one inline script, including the JSON config');
  assert.ok(!('src' in attributes(scripts[0][1])), 'No external script');
  const source = scripts[0][2];
  const script = new vm.Script(source, {filename: filename + '#inline-script'});
  const configMatch = source.match(/^const config = (.+);$/m);
  assert.ok(configMatch, 'Expected a single-line, safely serialized JSON config');
  const config = JSON.parse(configMatch[1]);
  const entries = [...config.weights].sort((a, b) => a.weight - b.weight);
  assert.deepEqual(entries.map(entry => entry.weight), expectedWeights);
  for (const entry of entries) {
    assert.equal(typeof entry.style, 'string');
    assert.ok(Number.isFinite(entry.moderate) && entry.moderate > 0);
    assert.equal(entry.tighter, 2 * entry.moderate);
  }
  for (const [weight, moderate] of [[100, 40], [400, 48], [900, 64]]) {
    assert.equal(entries.find(entry => entry.weight === weight).moderate, moderate);
  }

  assert.match(html, /font-synthesis\s*:\s*none/);
  assert.match(html, /\.font-sample\s*\{[^}]*font-family\s*:\s*SpacingProof\s*,/);
  const faces = Array.from(html.matchAll(/@font-face\s*\{([^}]+)\}/gi), match => match[1]);
  assert.equal(faces.length, 9, 'Nine embedded static font faces');
  assert.deepEqual(faces.map(face => {
    assert.match(face, /font-family\s*:\s*['"]?SpacingProof['"]?\s*;/);
    assert.match(face, /url\(\s*['"]?data:[^,]*;base64,/);
    return Number(face.match(/font-weight\s*:\s*(\d+)/)[1]);
  }).sort((a, b) => a - b), expectedWeights);
  for (const variant of variants) {
    const rule = html.match(new RegExp('\\.font-sample\\[data-variant=' + variant + '\\]\\s*\\{([^}]+)\\}'));
    assert.ok(rule, 'Explicit default feature rule for ' + variant);
    assert.equal(rule[1].replace(/^\s*font-feature-settings\s*:\s*/, '').trim(), expectedFeatures(variant, 'round'));
  }

  const harness = startScript(html, script);
  const {document, loads, elements} = harness;
  const element = id => document.getElementById(id);
  const samples = document.querySelectorAll('.font-sample');
  const custom = document.querySelectorAll('.custom-text');
  const adjustable = document.querySelectorAll('.adjustable');
  const reading = document.querySelectorAll('.reading-text');
  assert.equal(samples.length, 30);
  assert.equal(custom.length, 3);
  assert.equal(adjustable.length, 21);
  assert.equal(reading.length, 9);
  const readingSizes = reading.map(sample => sample.style.fontSize);
  assert.deepEqual(readingSizes, ['24px', '16px', '12px', '24px', '16px', '12px', '24px', '16px', '12px']);
  for (const variant of variants) {
    const texts = samples.filter(sample => sample.dataset.variant === variant).map(sample => sample.textContent);
    for (const text of ['go ge gc', 'ga gn gr', 'gg gy gj', 'g. g, g: g; g) g] g!', 'og ag ng', 'g g', 'ago going baggage']) {
      assert.ok(texts.includes(text), 'Missing ' + variant + ' test: ' + text);
    }
  }
  for (const id of ['weight', 'mode', 'size', 'words']) {
    assert.ok(elements.some(node => node.tagName === 'LABEL' && node.attributes.for === id), 'Accessible label for ' + id);
  }
  for (const target of ['proof.svg', 'weights.svg', 'pairs.svg', 'README.md', 'validation.json', '../../../OFL.txt']) {
    assert.ok(elements.some(node => node.tagName === 'A' && node.attributes.href === target), 'Missing link: ' + target);
  }
  for (const target of ['proof.svg', 'weights.svg', 'pairs.svg']) {
    assert.ok(elements.some(node => node.tagName === 'IMG' && node.attributes.src === target && node.attributes.alt), 'Missing labelled sheet: ' + target);
  }
  assert.equal(element('fontStatus').attributes.role, 'status');
  assert.equal(element('fontStatus').attributes['aria-live'], 'polite');
  assert.deepEqual(element('weight').options.map(option => Number(option.value)), expectedWeights);
  assert.deepEqual(element('mode').options.map(option => option.value), ['round', 'all']);
  assert.equal(element('weight').value, '400');
  assert.equal(element('mode').value, 'round');
  assert.equal(element('size').attributes.min, '12');
  assert.equal(element('size').attributes.max, '72');
  assert.equal(element('size').value, '36');
  assertSettings(harness, entries[3], 'round');
  assert.equal(element('fontStatus').dataset.state, 'loading');
  assert.equal(loads.length, 1);
  assert.equal(loads[0].descriptor, '400 36px "SpacingProof"');
  assert.ok(loads[0].text.includes('g'));
  for (const sample of custom) assert.equal(sample.textContent, element('words').value);
  for (const sample of adjustable) assert.equal(sample.style.fontSize, '36px');
  await settle(loads[0]);
  assert.equal(element('fontStatus').dataset.state, 'ready');

  function changeWeight(value) {
    const count = loads.length;
    element('weight').value = String(value);
    element('weight').dispatch('change');
    assert.equal(loads.length, count + 1);
    assert.equal(element('fontStatus').dataset.state, 'loading');
    assert.ok(element('fontStatus').textContent.includes('(' + value + ')'));
    assert.equal(loads[count].descriptor, value + ' 36px "SpacingProof"');
    return loads[count];
  }

  // Repeated round -> all -> round transitions at every weight catch leaked flags.
  for (const entry of entries) {
    const request = changeWeight(entry.weight);
    const count = loads.length;
    for (const mode of ['round', 'all', 'round']) {
      element('mode').value = mode;
      element('mode').dispatch('change');
      assertSettings(harness, entry, mode);
      assert.equal(loads.length, count, 'Scope changes must not reload fonts');
    }
    await settle(request);
    assert.equal(element('fontStatus').dataset.state, 'ready');
    assert.ok(element('fontStatus').textContent.includes(entry.style + ' (' + entry.weight + ')'));
  }

  const staticSamples = samples.filter(sample => !sample.classes.includes('custom-text'));
  const staticText = staticSamples.map(sample => sample.textContent);
  const loadCount = loads.length;
  const nodeCount = elements.length;
  for (const text of [
    'ago going baggage',
    '</textarea><script>throw new Error("injected")</script><img src=x onerror=alert(1)> & <g>\n"quoted"',
    '',
    'g g\nGoing again — café 🧳',
  ]) {
    const previousWrites = custom.map(sample => sample.textWrites);
    element('words').value = text;
    element('words').dispatch('input');
    custom.forEach((sample, index) => {
      assert.equal(sample.textContent, text, 'Custom text is copied literally, never interpreted as markup');
      assert.equal(sample.textWrites, previousWrites[index] + 1);
    });
    assert.deepEqual(staticSamples.map(sample => sample.textContent), staticText);
    assert.equal(elements.length, nodeCount);
  }
  for (const size of ['12', '72', '25', '36']) {
    element('size').value = size;
    element('size').dispatch('input');
    for (const sample of adjustable) assert.equal(sample.style.fontSize, size + 'px');
    assert.deepEqual(reading.map(sample => sample.style.fontSize), readingSizes, 'Reading sizes stay fixed');
    assert.equal(element('sizeValue').textContent, size + ' px');
    assertSettings(harness, entries[8], 'round');
  }
  assert.equal(loads.length, loadCount, 'Text and size changes must not reload fonts');

  await reject(changeWeight(400));
  assert.equal(element('fontStatus').dataset.state, 'failed');
  assert.match(element('fontStatus').textContent, /failed.*\(400\).*fallback.*sheets/);
  assertSettings(harness, entries[3], 'round');
  await settle(changeWeight(500), []);
  assert.equal(element('fontStatus').dataset.state, 'failed', 'No matching faces is not success');
  await settle(changeWeight(600));
  assert.equal(element('fontStatus').dataset.state, 'ready', 'A later successful load recovers');

  let old = changeWeight(100);
  let current = changeWeight(900);
  await settle(old);
  assert.equal(element('fontStatus').dataset.state, 'loading', 'Stale success cannot finish the current load');
  assert.match(element('fontStatus').textContent, /\(900\)/);
  await settle(current);
  assert.equal(element('fontStatus').dataset.state, 'ready');

  old = changeWeight(200);
  current = changeWeight(700);
  await settle(current);
  const readyText = element('fontStatus').textContent;
  await reject(old);
  assert.equal(element('fontStatus').dataset.state, 'ready', 'Stale failure cannot overwrite current success');
  assert.equal(element('fontStatus').textContent, readyText);
  assert.match(readyText, /\(700\)/);

  old = changeWeight(300);
  current = changeWeight(800);
  await reject(current);
  const failedText = element('fontStatus').textContent;
  await settle(old);
  assert.equal(element('fontStatus').dataset.state, 'failed', 'Stale success cannot overwrite current failure');
  assert.equal(element('fontStatus').textContent, failedText);
  assert.match(failedText, /\(800\)/);
  assertSettings(harness, entries[7], 'round');

  const unsupported = startScript(html, script, false);
  assert.equal(unsupported.document.getElementById('fontStatus').dataset.state, 'unavailable');
  assert.match(unsupported.document.getElementById('fontStatus').textContent, /cannot be verified.*fallback/);
  assertSettings(unsupported, entries[3], 'round');

  console.log('PASS: nine weights; both modes; four explicit feature flags; literal text; independent sizes; font failures and stale-load races.');
  console.log('Generated markup and mocked DOM logic only; browser rendering and font shaping were not tested.');
}

main().catch(error => {
  if (error.code === 'ENOENT') {
    console.error('Build proof.html with the parent builder before running this test. ' + error.message);
  } else {
    console.error(error.stack || error);
  }
  process.exitCode = 1;
});
