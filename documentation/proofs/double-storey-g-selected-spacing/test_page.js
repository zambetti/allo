'use strict';

/*
 * Run after the parent builder creates proof.html:
 *   node documentation/proofs/double-storey-g-selected-spacing/test_page.js
 * An optional first argument selects another render-generated HTML file, such
 * as a temporary fixture. This test never builds fonts or writes proof files.
 *
 * Mocked DOM interface used by page.py:
 *   document.getElementById(id), document.querySelectorAll('.class'),
 *   document.fonts.load(cssFont, sampleText) -> Promise<FontFace[]>;
 *   elements: value, textContent, dataset, style, addEventListener(type, fn).
 * Required IDs: weight, size, words, sizeValue, weightSummary, fontStatus,
 *   selectionExplanation, boundaryNote, clearanceNote, preservationNote,
 *   heading-a/b/c, amount-a/b/c, features-a/b/c.
 * Sample classes: font-sample, custom-text, adjustable, reading-text;
 *   each font-sample carries data-variant="a", "b", or "c".
 * Controls emit change (weight) or input (size/words); there is no scope mode.
 * Columns a/b/c mean inherited / C rounds only / selected C rounds + B others,
 * NOT the old A/B/C amount levels. Selected enables ss17 + ss19, NOT ss20.
 * This is a mocked-DOM test, not a browser test. The mock rejects HTML
 * insertion. It does not implement layout, shaping,
 * CSS cascade, real font loading, or browser rendering.
 */

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const expectedWeights = [100, 200, 300, 400, 500, 600, 700, 800, 900];
const expectedModerate = [40, 43, 45, 48, 51, 54, 57, 60, 64];
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

function expectedFeatures(variant) {
  const flags = {a: [0, 0, 0, 0], b: [0, 0, 0, 1], c: [1, 0, 1, 0]}[variant];
  return featureTags.map((tag, index) => '"' + tag + '" ' + flags[index]).join(', ');
}

function assertAmounts(harness, entry) {
  const element = id => harness.document.getElementById(id);
  assert.equal(element('heading-a').textContent, 'Inherited');
  assert.equal(element('heading-b').textContent, 'C for rounds only');
  assert.equal(element('heading-c').textContent, 'Selected: C rounds + B others');
  for (const variant of variants) {
    assert.equal(element('features-' + variant).textContent, expectedFeatures(variant));
  }
  assert.equal(element('amount-a').textContent, '0 font units · inherited spacing; all four features off');
  assert.equal(element('amount-b').textContent, 'C: −' + entry.tighter +
    ' font units · go / ge / gc only; other advances inherited · ss20');
  assert.equal(element('amount-c').textContent, 'C: −' + entry.tighter +
    ' font units · go / ge / gc; B: −' + entry.moderate +
    ' font units · all other plain g advances, including before spaces and terminal g · ss17 + ss19');
  assert.equal(element('weightSummary').textContent, entry.style + ' · ' + entry.weight +
    ' — study 03 amounts: B: −' + entry.moderate + '; C: −' + entry.tighter + ' font units (2048 units/em).');
}

function assertNotes(harness) {
  const element = id => harness.document.getElementById(id);
  const explanation = element('selectionExplanation').textContent;
  assert.match(explanation, /columns are fixed/);
  assert.match(explanation, /Inherited disables all four/);
  assert.match(explanation, /C for rounds only enables ss20 alone/);
  assert.match(explanation, /ss17=1, ss18=0, ss19=1, ss20=0/);
  assert.match(explanation, /B on every plain g advance plus another B only before o \/ e \/ c/);
  assert.match(explanation, /B \+ B = C for go \/ ge \/ gc/);
  assert.match(explanation, /does not use ss17 \+ ss20.*B \+ C = 3B/);
  assert.match(explanation, /Existing kerning stays active/);
  const boundary = element('boundaryNote').textContent;
  assert.match(boundary, /blanket-B effects before spaces and on terminal g/);
  assert.match(boundary, /isolated preceding control og \/ ag \/ ng, glyph origins are unchanged/);
  assert.match(boundary, /combined text run, that advance change shifts later text/);
  assert.match(boundary, /terminal g advance changes by −B/);
  assert.match(boundary, /thin rule after “g g” marks the text-run end/);
  assert.match(boundary, /before the space and the final g advance are reduced/);
  assert.match(boundary, /Inherited and C for rounds only leave these boundary advances unchanged/);
  const clearance = element('clearanceNote').textContent;
  assert.match(clearance, /gj.*sampled horizontal gap is 28\.6425 font units at 800 and 8\.3873 at 900/);
  assert.match(clearance, /no computed overlap/);
  assert.match(clearance, /does not guarantee comfortable spacing/);
  assert.match(clearance, /not an exact Euclidean distance/);
  assert.match(clearance, /No exceptions have been added for gj, spaces, terminal g or other followers/);
  const preservation = element('preservationNote').textContent;
  assert.match(preservation, /study 03 fonts unchanged/);
  assert.match(preservation, /identical outlines/);
  assert.match(preservation, /No outlines or font hmtx metrics are edited/);
  assert.match(preservation, /Previous proof directories and production fonts remain unchanged/);
  assert.match(preservation, /proof-only, not production integration or production ss04/);
  assert.match(preservation, /no font installation, server or network access is needed/);
  for (const id of ['selectionExplanation', 'boundaryNote', 'clearanceNote', 'preservationNote']) {
    assert.ok(!('hidden' in element(id).attributes), id + ' must not be hidden');
    assert.notEqual(element(id).attributes['aria-hidden'], 'true');
  }
}

function assertSettings(harness, entry) {
  const {document} = harness;
  for (const sample of document.querySelectorAll('.font-sample')) {
    assert.ok(variants.includes(sample.dataset.variant));
    assert.equal(sample.style.fontWeight, String(entry.weight), 'All samples use the selected weight');
    assert.equal(sample.style.fontFeatureSettings, expectedFeatures(sample.dataset.variant),
      'Every sample must explicitly set all four fixed flags; selected rounds must not become 3B');
  }
  assertAmounts(harness, entry);
  assertNotes(harness);
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

function startScript(html, script, withFontAPI = true, prepare = () => {}) {
  const harness = mockDOM(html, withFontAPI);
  prepare(harness.document);
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
  assert.doesNotMatch(configMatch[1], /[<>&\u2028\u2029]/, 'Script data must escape HTML delimiters and line separators');
  const config = JSON.parse(configMatch[1]);
  const entries = [...config.weights].sort((a, b) => a.weight - b.weight);
  assert.deepEqual(entries.map(entry => entry.weight), expectedWeights);
  for (const entry of entries) {
    assert.equal(typeof entry.style, 'string');
    assert.ok(Number.isFinite(entry.moderate) && entry.moderate > 0);
    assert.equal(entry.tighter, 2 * entry.moderate);
  }
  assert.deepEqual(entries.map(entry => entry.moderate), expectedModerate, 'Reuse all nine study 03 B amounts');
  assert.deepEqual(entries.map(entry => entry.tighter), expectedModerate.map(amount => amount * 2));

  assert.match(html, /font-synthesis\s*:\s*none/);
  assert.match(html, /font-kerning\s*:\s*normal/);
  assert.match(html, /\.font-sample\s*\{[^}]*font-weight\s*:\s*400\s*;/);
  assert.match(html, /\.adjustable\s*\{\s*font-size\s*:\s*36px\s*\}/);
  assert.match(html, /\.boundary-text\s*\{[^}]*display\s*:\s*inline-block/);
  assert.match(html, /\.boundary-text\s*\{[^}]*border-inline-end\s*:\s*1px solid/);
  assert.match(html, /mocked-DOM tests, not browser tests/);
  assert.match(html, /\.font-sample\s*\{[^}]*font-family\s*:\s*SpacingProof\s*,/);
  const faces = Array.from(html.matchAll(/@font-face\s*\{([^}]+)\}/gi), match => match[1]);
  assert.equal(faces.length, 9, 'Nine embedded static font faces');
  assert.deepEqual(faces.map(face => {
    assert.match(face, /font-family\s*:\s*['"]?SpacingProof['"]?\s*;/);
    assert.match(face, /url\(\s*['"]?data:font\/woff2;base64,/);
    assert.match(face, /format\(\s*['"]woff2['"]\s*\)/);
    assert.doesNotMatch(face, /\blocal\s*\(/i, 'Always use the embedded proof font, not an installed font');
    return Number(face.match(/font-weight\s*:\s*(\d+)/)[1]);
  }).sort((a, b) => a - b), expectedWeights);
  for (const variant of variants) {
    const rule = html.match(new RegExp('\\.font-sample\\[data-variant=' + variant + '\\]\\s*\\{([^}]+)\\}'));
    assert.ok(rule, 'Explicit default feature rule for ' + variant);
    assert.equal(rule[1].replace(/^\s*font-feature-settings\s*:\s*/, '').trim(), expectedFeatures(variant));
  }

  // Static labels and flags must agree with initialization, even before JS runs.
  const initial = mockDOM(html);
  assertAmounts(initial, entries[3]);
  assertNotes(initial);
  assert.equal(initial.document.getElementById('weight').value, '400');
  for (const entry of entries) {
    const option = initial.document.getElementById('weight').options.find(item => Number(item.value) === entry.weight);
    assert.equal(option.label, entry.style + ' · ' + entry.weight, 'Style labels must remain literal text');
  }
  const amountRows = initial.elements.filter(node => node.tagName === 'TR' && node.dataset.weight);
  assert.deepEqual(amountRows.map(row => Number(row.dataset.weight)), expectedWeights);
  amountRows.forEach((row, index) => {
    const entry = entries[index];
    assert.equal(row.textContent, String(entry.weight) + entry.style + entry.moderate + entry.tighter);
  });

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
  const columns = document.querySelectorAll('.comparison-column');
  assert.deepEqual(columns.map(column => column.dataset.variant), variants, 'Three fixed comparison columns');
  assert.equal(elements.filter(node => node.tagName === 'SELECT').length, 1, 'No mode or scope selector');
  assert.ok(!harness.ids.has('mode') && !harness.ids.has('scope') && !harness.ids.has('modeExplanation'));
  assert.deepEqual(elements.filter(node => node.listeners.size).map(node => node.id), ['weight', 'size', 'words']);
  assert.deepEqual([...element('weight').listeners.keys()], ['change']);
  assert.deepEqual([...element('size').listeners.keys()], ['input']);
  assert.deepEqual([...element('words').listeners.keys()], ['input']);
  for (const sample of document.querySelectorAll('.boundary-text')) {
    assert.equal(sample.textContent, 'g g');
    assert.equal(sample.attributes['aria-describedby'], 'boundaryNote');
  }
  assert.equal(document.querySelectorAll('.boundary-text').length, 3);
  for (const id of ['weight', 'size', 'words']) {
    assert.ok(elements.some(node => node.tagName === 'LABEL' && node.attributes.for === id), 'Accessible label for ' + id);
  }
  for (const target of [
    'proof.svg', 'proof.png', 'weights.svg', 'weights.png', 'pairs.svg', 'pairs.png',
    'README.md', 'validation.json', 'clearances.json', '../double-storey-g-spacing/proof.html', '../../../OFL.txt',
  ]) {
    assert.ok(elements.some(node => node.tagName === 'A' && node.attributes.href === target), 'Missing link: ' + target);
  }
  for (const target of ['proof.svg', 'weights.svg', 'pairs.svg']) {
    assert.ok(elements.some(node => node.tagName === 'IMG' && node.attributes.src === target && node.attributes.alt), 'Missing labelled sheet: ' + target);
  }
  assert.equal(element('fontStatus').attributes.role, 'status');
  assert.equal(element('fontStatus').attributes['aria-live'], 'polite');
  assert.equal(element('fontStatus').attributes['aria-atomic'], 'true');
  assert.deepEqual(element('weight').options.map(option => Number(option.value)), expectedWeights);
  assert.equal(element('weight').value, '400');
  assert.equal(element('size').attributes.min, '12');
  assert.equal(element('size').attributes.max, '72');
  assert.equal(element('size').value, '36');
  assertSettings(harness, entries[3]);
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

  // Both directions exercise every weight without ever changing the fixed flags.
  for (const entry of [...entries, ...entries.slice().reverse()]) {
    const request = changeWeight(entry.weight);
    assertSettings(harness, entry);
    await settle(request);
    assert.equal(element('fontStatus').dataset.state, 'ready');
    assert.equal(element('fontStatus').textContent, 'Embedded ' + entry.style + ' (' + entry.weight + ') loaded.');
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
    assertSettings(harness, entries[0]);
  }
  for (const size of ['12', '72', '36', '25']) {
    element('size').value = size;
    element('size').dispatch('input');
    for (const sample of adjustable) assert.equal(sample.style.fontSize, size + 'px');
    assert.deepEqual(reading.map(sample => sample.style.fontSize), readingSizes, 'Reading sizes stay fixed');
    assert.equal(element('sizeValue').textContent, size + ' px');
    assertSettings(harness, entries[0]);
  }
  assert.equal(loads.length, loadCount, 'Text and size changes must not reload fonts');
  const editedText = element('words').value;
  await settle(changeWeight(900));
  assertSettings(harness, entries[8]);
  for (const sample of custom) assert.equal(sample.textContent, editedText, 'Weight changes preserve editable text');
  for (const sample of adjustable) assert.equal(sample.style.fontSize, '25px', 'Weight changes preserve the non-default comparison size');
  assert.equal(element('size').value, '25');
  assert.equal(element('sizeValue').textContent, '25 px');
  assert.deepEqual(reading.map(sample => sample.style.fontSize), readingSizes);
  assert.deepEqual(staticSamples.map(sample => sample.textContent), staticText);

  await reject(changeWeight(400));
  assert.equal(element('fontStatus').dataset.state, 'failed');
  assert.match(element('fontStatus').textContent, /failed.*\(400\).*fallback.*sheets/s);
  assertSettings(harness, entries[3]);
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
  assertSettings(harness, entries[7]);

  old = changeWeight(400);
  current = changeWeight(500);
  await reject(old);
  assert.equal(element('fontStatus').dataset.state, 'loading', 'Stale failure cannot finish the current load');
  assert.match(element('fontStatus').textContent, /\(500\)/);
  await settle(current);

  // A -> B -> A must use a request token, not just compare the selected weight.
  old = changeWeight(400);
  const middle = changeWeight(600);
  current = changeWeight(400);
  await settle(old);
  assert.equal(element('fontStatus').dataset.state, 'loading', 'An older same-weight success is still stale');
  await settle(middle, []);
  assert.equal(element('fontStatus').dataset.state, 'loading', 'Stale empty results cannot report failure');
  await settle(current);
  assert.equal(element('fontStatus').dataset.state, 'ready');
  assertSettings(harness, entries[3]);

  for (const unsupported of [
    startScript(html, script, false),
    startScript(html, script, true, doc => { doc.fonts = {}; }),
  ]) {
    const unsupportedStatus = unsupported.document.getElementById('fontStatus');
    assert.equal(unsupportedStatus.dataset.state, 'unavailable');
    assert.match(unsupportedStatus.textContent, /cannot be verified.*fallback.*sheets/);
    assert.equal(unsupported.loads.length, 0);
    assertSettings(unsupported, entries[3]);
    const unsupportedWeight = unsupported.document.getElementById('weight');
    unsupportedWeight.value = '900';
    unsupportedWeight.dispatch('change');
    assert.equal(unsupportedStatus.dataset.state, 'unavailable');
    assertSettings(unsupported, entries[8]);
  }
  const throwing = startScript(html, script, true, doc => {
    doc.fonts.load = () => { throw new Error('Synchronous font API failure'); };
  });
  assert.equal(throwing.document.getElementById('fontStatus').dataset.state, 'failed');
  assert.match(throwing.document.getElementById('fontStatus').textContent, /failed.*fallback.*sheets/s);
  assertSettings(throwing, entries[3]);

  console.log('PASS: nine weights and amounts; three fixed feature combinations; boundary and clearance caveats; literal text; independent sizes; font failures and stale-load races.');
  console.log('Mocked-DOM test, not a browser test: layout, real font loading, rendering, shaping and geometry were not tested.');
}

main().catch(error => {
  if (error.code === 'ENOENT') {
    console.error('Pass a render-generated HTML path, or let the parent builder create proof.html first. ' + error.message);
  } else {
    console.error(error.stack || error);
  }
  process.exitCode = 1;
});
