'use strict';

/*
 * Run against the parent's generated proof, or pass a temporary render fixture:
 *   node documentation/proofs/double-storey-g-spacing-finish/test_page.js [file]
 * Default file: proof.html beside this test. Nothing is generated or written.
 *
 * Browser-check hooks (IDs, not positional selectors):
 *   pairWeight (change), textWeight (change), textSize (change), words (input);
 *   pairFontStatus / textFontStatus: data-state=loading|ready|failed|unavailable,
 *     data-weight is the requested weight; pairSummary / textSummary;
 *   pairComparison, pairHeading-chosen/refined, pairAmount-chosen/refined,
 *     pairFeatures-chosen/refined, pairGap;
 *   pair-chosen/refined-gj/gjg/guards/rounds (e.g. pair-refined-gj);
 *   textComparison, textHeading-refined/boundary, textAmount-refined/boundary,
 *     textFeatures-refined/boundary, textSizeValue;
 *   reading-refined/boundary, norwegian-refined/boundary,
 *     boundary-refined/boundary (the end border is the terminal-g marker);
 *   correctionNote, featureNote, boundaryNote, boundaryScope, sizeNote,
 *     preservationNote, validationNote.
 * Every .font-sample has data-variant=chosen|refined|boundary. .pair-sample
 * and .text-sample select independent weights; .reading-size changes size,
 * .reading-text receives literal edited text. Boundary samples stay 16px.
 *
 * This is a mocked-DOM test, not browser validation. It rejects HTML insertion,
 * but does not implement layout, CSS cascade, shaping or real font loading.
 */

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const expectedWeights = [100, 200, 300, 400, 500, 600, 700, 800, 900];
const expectedModerate = [40, 43, 45, 48, 51, 54, 57, 60, 64];
const expectedCorrections = [0, 0, 0, 0, 0, 0, 8, 27, 40];
const tags = ['ss15', 'ss16', 'ss17', 'ss18', 'ss19', 'ss20'];
const stateFlags = {chosen: [0, 0, 1, 0, 1, 0], refined: [1, 0, 1, 0, 1, 0], boundary: [1, 1, 1, 0, 1, 0]};
const gaps = {700: ['49.7625', '57.7625'], 800: ['28.6425', '55.6425'], 900: ['8.3873', '48.3873']};

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
  for (const match of source.matchAll(/([^\s=/>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g)) {
    result[match[1].toLowerCase()] = decodeEntities(match[2] ?? match[3] ?? match[4] ?? '');
  }
  return result;
}

const camelCase = name => name.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());

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
    // HTML ignores a single leading newline immediately inside a textarea.
    if (tag === 'textarea') content = content.replace(/^\n/, '');
    this._text = decodeEntities(content.replace(/<[^>]*>/g, ''));
    this.value = attrs.value ?? (tag === 'textarea' ? this._text : '');
    for (const [name, value] of Object.entries(attrs)) {
      if (name.startsWith('data-')) this.dataset[camelCase(name.slice(5))] = value;
    }
    for (const declaration of (attrs.style || '').split(';')) {
      const colon = declaration.indexOf(':');
      if (colon !== -1) this.style[camelCase(declaration.slice(0, colon).trim())] = declaration.slice(colon + 1).trim();
    }
    if (tag === 'select') {
      this.options = Array.from(content.matchAll(/<option\b([^>]*)>([\s\S]*?)<\/option>/gi), match => {
        const option = attributes(match[1]);
        return {value: option.value, label: decodeEntities(match[2]), selected: 'selected' in option};
      });
      this.value = (this.options.find(option => option.selected) || this.options[0]).value;
    }
  }

  get textContent() { return this._text; }
  set textContent(value) { this._text = String(value); this.textWrites += 1; }
  get innerHTML() { throw new Error('Use textContent, not innerHTML'); }
  set innerHTML(value) { throw new Error('Unsafe innerHTML assignment: ' + value); }
  set outerHTML(value) { throw new Error('Unsafe outerHTML assignment: ' + value); }
  insertAdjacentHTML() { throw new Error('Unsafe HTML insertion'); }
  addEventListener(type, fn) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(fn);
  }
  dispatch(type) {
    const listeners = this.listeners.get(type) || [];
    assert.ok(listeners.length, this.id + ' must listen for ' + type);
    for (const fn of listeners) fn({type, target: this});
  }
}

function mockDOM(html, withFontAPI = true) {
  // Bounded markup reader for this template, not a general-purpose HTML parser.
  const markup = html.replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1\s*>/gi, '');
  const elements = [];
  const ids = new Map();
  for (const match of markup.matchAll(/<([a-z][\w:-]*)\b([^>]*)>/gi)) {
    const tag = match[1].toLowerCase();
    const attrs = attributes(match[2]);
    const start = match.index + match[0].length;
    const end = markup.indexOf('</' + tag + '>', start);
    const element = new MockElement(tag, attrs, end === -1 ? '' : markup.slice(start, end));
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
  if (withFontAPI) document.fonts = {
    load(descriptor, text) {
      return new Promise((resolve, reject) => loads.push({descriptor, text, resolve, reject}));
    },
  };
  return {document, elements, ids, loads};
}

const get = (harness, id) => harness.document.getElementById(id);
const select = (harness, name) => Array.from(harness.document.querySelectorAll('.' + name));
const features = variant => tags.map((tag, i) => '"' + tag + '" ' + stateFlags[variant][i]).join(', ');
const summary = entry => entry.style + ' · ' + entry.weight + ' — C: −' + entry.tighter +
  ' for go / ge / gc; B: −' + entry.moderate + ' for other g advances, before the gj correction (font units; 2048/em).';

function assertPairAmounts(harness, entry) {
  assert.equal(get(harness, 'pairHeading-chosen').textContent, 'Chosen · before');
  assert.equal(get(harness, 'pairHeading-refined').textContent, 'Refined · after');
  assert.equal(get(harness, 'pairSummary').textContent, summary(entry));
  assert.equal(get(harness, 'pairAmount-chosen').textContent, 'gj correction: +0 font units · selected baseline.');
  assert.equal(get(harness, 'pairAmount-refined').textContent, 'gj correction: +' + entry.gj_correction + ' font units · ss15 only.');
  for (const variant of ['chosen', 'refined']) assert.equal(get(harness, 'pairFeatures-' + variant).textContent, features(variant));
  assert.equal(get(harness, 'pairGap').textContent, gaps[entry.weight] ?
    'Sampled horizontal gj gap: ' + gaps[entry.weight][0] + ' → ' + gaps[entry.weight][1] + ' font units (chosen → refined).' :
    'No gj correction at this weight (+0); the two columns use the same spacing.');
}

function assertReadingAmounts(harness, entry) {
  assert.equal(get(harness, 'textHeading-refined').textContent, 'Refined · current word-space policy');
  assert.equal(get(harness, 'textHeading-boundary').textContent, 'Boundary trial · comparison only');
  assert.equal(get(harness, 'textSummary').textContent, summary(entry));
  assert.equal(get(harness, 'textAmount-refined').textContent, 'Before space: −' + entry.moderate + ' (B); terminal g: −' + entry.moderate +
    ' (B). gj correction: +' + entry.gj_correction + ' font units.');
  assert.equal(get(harness, 'textAmount-boundary').textContent, 'Before space: −' + entry.moderate + ' +' + entry.moderate +
    ' = 0 (inherited); terminal g: −' + entry.moderate + ' (B). gj correction: +' + entry.gj_correction + ' font units.');
  for (const variant of ['refined', 'boundary']) assert.equal(get(harness, 'textFeatures-' + variant).textContent, features(variant));
}

function assertSettings(harness, section, entry) {
  const sampleClass = section === 'pair' ? 'pair-sample' : 'text-sample';
  for (const sample of select(harness, sampleClass)) {
    assert.equal(sample.style.fontWeight, String(entry.weight));
    assert.equal(sample.style.fontFeatureSettings, features(sample.dataset.variant), 'All SIX feature flags are explicit');
    assert.ok(sample.style.fontFeatureSettings.endsWith('"ss20" 0'), 'Never ss17 + ss20');
  }
  if (section === 'pair') assertPairAmounts(harness, entry);
  else assertReadingAmounts(harness, entry);
}

function sectionSnapshot(harness, section) {
  const sampleClass = section === 'pair' ? 'pair-sample' : 'text-sample';
  const ids = section === 'pair' ? ['pairWeight', 'pairSummary', 'pairGap', 'pairFontStatus',
    'pairAmount-chosen', 'pairAmount-refined', 'pairFeatures-chosen', 'pairFeatures-refined'] :
    ['textWeight', 'textSize', 'textSizeValue', 'words', 'textSummary', 'textFontStatus',
      'textAmount-refined', 'textAmount-boundary', 'textFeatures-refined', 'textFeatures-boundary'];
  return JSON.stringify([...ids.map(id => get(harness, id)), ...select(harness, sampleClass)].map(node =>
    [node.id, node.value, node.textContent, node.textWrites, node.style, node.dataset]));
}

function changeWeight(harness, section, weight) {
  const other = section === 'pair' ? 'text' : 'pair';
  const snapshot = sectionSnapshot(harness, other);
  const count = harness.loads.length;
  get(harness, section + 'Weight').value = String(weight);
  get(harness, section + 'Weight').dispatch('change');
  assert.equal(sectionSnapshot(harness, other), snapshot, 'Changing ' + section + ' must not affect ' + other);
  assert.equal(harness.loads.length, count + 1, 'Only this section requests a font');
  const status = get(harness, section + 'FontStatus');
  assert.equal(status.dataset.state, 'loading');
  assert.equal(status.dataset.weight, String(weight));
  assert.ok(status.textContent.includes('(' + weight + ')'));
  const size = section === 'pair' ? '72' : get(harness, 'textSize').value;
  assert.equal(harness.loads[count].descriptor, weight + ' ' + size + 'px "SpacingProof"');
  return harness.loads[count];
}

const flushPromises = () => new Promise(resolve => setImmediate(resolve));
async function settle(request, result = [{status: 'loaded'}]) { request.resolve(result); await flushPromises(); }
async function reject(request) { request.reject(new Error('Simulated font failure')); await flushPromises(); }

function startScript(html, script, withFontAPI = true, prepare = () => {}) {
  const harness = mockDOM(html, withFontAPI);
  prepare(harness.document);
  script.runInContext(vm.createContext({document: harness.document}), {timeout: 1000});
  return harness;
}

async function assertFontRaces(harness, section) {
  const status = get(harness, section + 'FontStatus');
  await reject(changeWeight(harness, section, 400));
  assert.equal(status.dataset.state, 'failed');
  assert.match(status.textContent, /failed.*\(400\).*fallback.*static reference/s);
  for (const result of [[], [{status: 'error'}], [{status: 'loading'}], null]) {
    await settle(changeWeight(harness, section, 500), result);
    assert.equal(status.dataset.state, 'failed', 'A missing or unloaded face is not success');
  }
  await settle(changeWeight(harness, section, 600));
  assert.equal(status.dataset.state, 'ready', 'Successful retry recovers');

  for (const staleResult of ['success', 'failure', 'empty']) {
    const old = changeWeight(harness, section, 100);
    const current = changeWeight(harness, section, 900);
    const pending = status.textContent;
    if (staleResult === 'failure') await reject(old);
    else await settle(old, staleResult === 'empty' ? [] : [{status: 'loaded'}]);
    assert.equal(status.dataset.state, 'loading', 'Stale ' + staleResult + ' cannot finish a newer load');
    assert.equal(status.textContent, pending);
    await settle(current);
    assert.equal(status.dataset.state, 'ready');
  }
  let old = changeWeight(harness, section, 200);
  let current = changeWeight(harness, section, 700);
  await settle(current);
  const ready = status.textContent;
  await reject(old);
  assert.equal(status.dataset.state, 'ready', 'Stale failure cannot overwrite current success');
  assert.equal(status.textContent, ready);
  old = changeWeight(harness, section, 300);
  current = changeWeight(harness, section, 800);
  await reject(current);
  const failed = status.textContent;
  await settle(old);
  assert.equal(status.dataset.state, 'failed', 'Stale success cannot overwrite current failure');
  assert.equal(status.textContent, failed);

  old = changeWeight(harness, section, 400);
  const middle = changeWeight(harness, section, 600);
  current = changeWeight(harness, section, 400);
  await settle(old);
  assert.equal(status.dataset.state, 'loading', 'A → B → A requires request tokens, not just weight equality');
  await settle(middle, []);
  assert.equal(status.dataset.state, 'loading');
  await settle(current);
  assert.equal(status.dataset.state, 'ready');
}

async function main() {
  const filename = process.argv[2] ? path.resolve(process.argv[2]) : path.join(__dirname, 'proof.html');
  const html = fs.readFileSync(filename, 'utf8');
  const scripts = Array.from(html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi));
  assert.equal(scripts.length, 1, 'Exactly one inline script, with safely serialized config');
  assert.ok(!('src' in attributes(scripts[0][1])));
  const source = scripts[0][2];
  assert.doesNotMatch(source, /\b(?:innerHTML|outerHTML|insertAdjacentHTML|eval)\b|document\.write\s*\(/);
  const script = new vm.Script(source, {filename: filename + '#inline-script'});
  const configMatch = source.match(/^const config = (.+);$/m);
  assert.ok(configMatch);
  assert.doesNotMatch(configMatch[1], /[<>&\u2028\u2029]/, 'Escape script delimiters and line separators');
  const config = JSON.parse(configMatch[1]);
  const entries = [...config.weights].sort((a, b) => a.weight - b.weight);
  assert.deepEqual(entries.map(entry => entry.weight), expectedWeights);
  assert.deepEqual(entries.map(entry => entry.moderate), expectedModerate);
  assert.deepEqual(entries.map(entry => entry.tighter), expectedModerate.map(amount => amount * 2));
  assert.deepEqual(entries.map(entry => entry.gj_correction), expectedCorrections);
  assert.ok(entries.every(entry => typeof entry.style === 'string' && entry.style.trim()));
  assert.ok(config.paragraphs.length && config.paragraphs.every(text => typeof text === 'string'));
  assert.ok(config.space_characters.length && config.space_characters.every(char => Array.from(char).length === 1));
  assert.equal(new Set(config.space_characters).size, config.space_characters.length);

  const css = html.match(/<style>([\s\S]*?)<\/style>/)[1];
  const faces = Array.from(css.matchAll(/@font-face\s*\{([^}]+)\}/gi), match => match[1]);
  assert.equal(faces.length, 9);
  assert.deepEqual(faces.map(face => {
    assert.match(face, /font-family\s*:\s*['"]?SpacingProof['"]?\s*;/);
    assert.match(face, /url\(\s*['"]?data:font\/woff2;base64,/);
    assert.match(face, /format\(\s*['"]woff2['"]\s*\)/);
    assert.doesNotMatch(face, /\blocal\s*\(/i);
    return Number(face.match(/font-weight\s*:\s*(\d+)/)[1]);
  }).sort((a, b) => a - b), expectedWeights);
  const rule = selector => {
    const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const match = css.match(new RegExp(escaped + '\\s*\\{([^}]+)\\}'));
    assert.ok(match, 'Missing CSS rule ' + selector);
    return match[1];
  };
  for (const variant of Object.keys(stateFlags)) {
    assert.equal(rule('.font-sample[data-variant=' + variant + ']').replace(/^\s*font-feature-settings\s*:\s*/, '').trim(), features(variant));
  }
  for (const declaration of ['font-family:SpacingProof,sans-serif', 'font-synthesis:none', 'font-kerning:normal',
    'letter-spacing:normal', 'word-spacing:normal', 'text-align:start', 'overflow-wrap:anywhere']) {
    assert.ok(rule('.font-sample').includes(declaration));
  }
  assert.match(rule('.comparison'), /grid-template-columns:repeat\(2,minmax\(0,1fr\)\)/, 'Equal-width columns');
  assert.match(rule('.comparison-column'), /grid-template-rows:subgrid/, 'Shared rows align headings and text starts');
  assert.match(css, /@media\s*\(max-width:720px\)/);
  assert.match(rule('.pair-sample'), /font-size:72px; font-weight:900/);
  assert.match(rule('.text-sample'), /font-weight:400/);
  assert.match(rule('.reading-size'), /font-size:16px/);
  assert.match(rule('.reading-text'), /white-space:pre-wrap/);
  assert.match(rule('.boundary-sample'), /display:inline-block; font-size:16px; white-space:pre; border-inline-end:1px solid/);
  assert.doesNotMatch(css, /overflow(?:-[xy])?\s*:\s*(?:hidden|clip|scroll)|text-align\s*:\s*justify|text-overflow|transform\s*:\s*scale/);

  const initial = mockDOM(html);
  assertPairAmounts(initial, entries[8]);
  assertReadingAmounts(initial, entries[3]);
  for (const section of ['pair', 'text']) {
    const control = get(initial, section + 'Weight');
    assert.deepEqual(control.options.map(option => Number(option.value)), expectedWeights);
    assert.equal(control.value, section === 'pair' ? '900' : '400');
    for (const entry of entries) assert.equal(control.options.find(option => Number(option.value) === entry.weight).label, entry.style + ' · ' + entry.weight);
    const status = get(initial, section + 'FontStatus');
    assert.equal(status.attributes.role, 'status');
    assert.equal(status.attributes['aria-live'], 'polite');
    assert.equal(status.attributes['aria-atomic'], 'true');
  }
  assert.deepEqual(get(initial, 'textSize').options.map(option => option.value), ['12', '16', '24']);
  assert.equal(get(initial, 'textSize').value, '16');
  assert.equal(get(initial, 'words').value, config.paragraphs.join('\n\n'));
  for (const sample of select(initial, 'reading-text')) assert.equal(sample.textContent, get(initial, 'words').value);
  assert.equal(select(initial, 'font-sample').length, 14);
  assert.equal(select(initial, 'pair-sample').length, 8);
  assert.equal(select(initial, 'text-sample').length, 6);
  assert.equal(select(initial, 'reading-size').length, 4);
  assert.equal(select(initial, 'reading-text').length, 2);
  assert.deepEqual(select(initial, 'pair-column').map(node => node.dataset.variant), ['chosen', 'refined']);
  assert.deepEqual(select(initial, 'reading-column').map(node => node.dataset.variant), ['refined', 'boundary']);
  for (const variant of ['chosen', 'refined']) {
    for (const [id, text] of Object.entries({gj: 'gj', gjg: 'gjg', guards: 'gg gy', rounds: 'go ge gc'})) {
      assert.equal(get(initial, 'pair-' + variant + '-' + id).textContent, text);
    }
  }
  for (const variant of ['refined', 'boundary']) {
    assert.equal(get(initial, 'norwegian-' + variant).textContent, 'gjeng gjøre gjennom');
    assert.equal(get(initial, 'norwegian-' + variant).attributes.lang, 'nb');
    assert.equal(get(initial, 'boundary-' + variant).textContent, 'g' + (config.space_characters.includes(' ') ? ' ' : config.space_characters[0]) + 'g');
    assert.equal(get(initial, 'boundary-' + variant).attributes['aria-describedby'], 'boundaryNote boundaryScope');
  }
  for (const char of config.space_characters) assert.ok(get(initial, 'boundaryScope').textContent.includes('U+' + char.codePointAt(0).toString(16).toUpperCase().padStart(4, '0')));
  assert.match(get(initial, 'correctionNote').textContent, /only for gj; every other pair is unchanged by ss15/);
  assert.match(get(initial, 'correctionNote').textContent, /design-coordinate 580–900, rounded/);
  assert.match(get(initial, 'correctionNote').textContent, /conservative optical trial, not an automatically derived minimum gap/);
  assert.match(get(initial, 'boundaryNote').textContent, /adds \+B only when g is followed by the font’s space glyph/);
  assert.match(get(initial, 'boundaryNote').textContent, /Terminal g retains B in both columns/);
  assert.match(get(initial, 'boundaryNote').textContent, /not an adopted exception/);
  assert.match(get(initial, 'featureNote').textContent, /Never ss17 \+ ss20/);
  assert.match(get(initial, 'preservationNote').textContent, /All six optional features are off by default/);
  assert.match(get(initial, 'sizeNote').textContent, /browser zoom 100%/);
  assert.match(get(initial, 'validationNote').textContent, /mocked-DOM tests, not browser tests/);
  for (const id of ['correctionNote', 'featureNote', 'boundaryNote', 'boundaryScope', 'sizeNote', 'validationNote']) {
    assert.ok(!('hidden' in get(initial, id).attributes));
    assert.notEqual(get(initial, id).attributes['aria-hidden'], 'true');
  }
  for (const id of ['pairWeight', 'textWeight', 'textSize', 'words']) {
    assert.ok(initial.elements.some(node => node.tagName === 'LABEL' && node.attributes.for === id));
  }
  assert.equal(initial.elements.filter(node => node.tagName === 'SELECT').length, 3, 'No feature or state toggles');
  const targets = ['proof.svg', 'proof.png', 'README.md', 'validation.json', 'clearances.json', '../double-storey-g-selected-spacing/proof.html', '../../../OFL.txt'];
  assert.deepEqual([...new Set(initial.elements.filter(node => node.tagName === 'A').map(node => node.attributes.href))].sort(), targets.sort(), 'Only parent-owned assets and requested links');
  assert.deepEqual(initial.elements.filter(node => node.tagName === 'IMG').map(node => node.attributes.src), ['proof.svg']);
  assert.ok(initial.elements.find(node => node.tagName === 'IMG').attributes.alt);
  assert.ok(initial.elements.every(node => Object.keys(node.attributes).every(name => !name.startsWith('on'))), 'No inline event attributes');

  const harness = startScript(html, script);
  const {loads} = harness;
  assert.deepEqual(harness.elements.filter(node => node.listeners.size).map(node => node.id), ['pairWeight', 'textWeight', 'textSize', 'words']);
  assert.equal(loads.length, 2);
  assert.equal(loads[0].descriptor, '900 72px "SpacingProof"');
  assert.equal(loads[1].descriptor, '400 16px "SpacingProof"');
  for (const request of loads) {
    assert.ok(request.text.includes('gj'));
    for (const char of config.space_characters) assert.ok(request.text.includes(char));
  }
  assertSettings(harness, 'pair', entries[8]);
  assertSettings(harness, 'text', entries[3]);
  await settle(loads[1]);
  assert.equal(get(harness, 'textFontStatus').dataset.state, 'ready');
  assert.equal(get(harness, 'pairFontStatus').dataset.state, 'loading');
  await settle(loads[0]);
  assert.equal(get(harness, 'pairFontStatus').dataset.state, 'ready', 'Reading load cannot invalidate the pair token');

  for (const section of ['pair', 'text']) {
    const other = section === 'pair' ? 'text' : 'pair';
    for (const entry of [...entries, ...entries.slice().reverse()]) {
      const snapshot = sectionSnapshot(harness, other);
      await settle(changeWeight(harness, section, entry.weight));
      assertSettings(harness, section, entry);
      assert.equal(get(harness, section + 'FontStatus').textContent, 'Embedded ' + entry.style + ' (' + entry.weight + ') loaded.');
      assert.equal(sectionSnapshot(harness, other), snapshot, 'Other section is unchanged after completion');
    }
  }
  const fixed = select(harness, 'font-sample').filter(node => !node.classes.includes('reading-text'));
  const fixedTexts = fixed.map(node => node.textContent);
  const loadCount = loads.length;
  const nodeCount = harness.elements.length;
  const pairSnapshot = sectionSnapshot(harness, 'pair');
  for (const text of ['', 'Going again, belonging.\n\nA good beginning grows in the garden.',
    '</textarea><script>throw new Error("injected")</script><img src=x onerror=alert(1)> & <g>\n"quoted"',
    '\n g  g\n\ngjeng gjøre gjennom — café 🧳\u00a0g\u2028g\u2029g', 'g'.repeat(1500)]) {
    const previousWrites = select(harness, 'reading-text').map(node => node.textWrites);
    get(harness, 'words').value = text;
    get(harness, 'words').dispatch('input');
    select(harness, 'reading-text').forEach((node, i) => {
      assert.equal(node.textContent, text, 'Edited text remains literal in BOTH columns');
      assert.equal(node.textWrites, previousWrites[i] + 1);
    });
    assert.deepEqual(fixed.map(node => node.textContent), fixedTexts);
    assert.equal(harness.elements.length, nodeCount);
  }
  for (const size of ['12', '24', '16', '24']) {
    get(harness, 'textSize').value = size;
    get(harness, 'textSize').dispatch('change');
    for (const sample of select(harness, 'reading-size')) assert.equal(sample.style.fontSize, size + 'px');
    for (const sample of [...select(harness, 'pair-sample'), ...select(harness, 'boundary-sample')]) assert.equal(sample.style.fontSize, undefined, 'Fixed CSS sizes are not overridden');
    assert.equal(get(harness, 'textSizeValue').textContent, size + ' CSS px');
  }
  assert.equal(loads.length, loadCount, 'Editing text or size does not reload static font faces');
  assert.equal(sectionSnapshot(harness, 'pair'), pairSnapshot);
  await settle(changeWeight(harness, 'text', 800));
  for (const sample of select(harness, 'reading-size')) assert.equal(sample.style.fontSize, '24px');
  for (const sample of select(harness, 'reading-text')) assert.equal(sample.textContent, get(harness, 'words').value);
  assert.deepEqual(fixed.map(node => node.textContent), fixedTexts);

  for (const section of ['pair', 'text']) {
    const other = section === 'pair' ? 'text' : 'pair';
    const snapshot = sectionSnapshot(harness, other);
    await assertFontRaces(harness, section);
    assertSettings(harness, section, entries[3]);
    assert.equal(sectionSnapshot(harness, other), snapshot, 'Errors and races remain section-local');
  }
  const pairPending = changeWeight(harness, 'pair', 900);
  const readingPending = changeWeight(harness, 'text', 900);
  await reject(readingPending);
  await settle(pairPending);
  assert.equal(get(harness, 'pairFontStatus').dataset.state, 'ready');
  assert.equal(get(harness, 'textFontStatus').dataset.state, 'failed', 'Same-weight sections still have independent outcomes');

  for (const unsupported of [startScript(html, script, false), startScript(html, script, true, doc => { doc.fonts = {}; })]) {
    assert.equal(unsupported.loads.length, 0);
    for (const section of ['pair', 'text']) {
      const status = get(unsupported, section + 'FontStatus');
      assert.equal(status.dataset.state, 'unavailable');
      assert.match(status.textContent, /cannot be verified.*fallback.*static reference/s);
      get(unsupported, section + 'Weight').value = '700';
      get(unsupported, section + 'Weight').dispatch('change');
      assert.equal(status.dataset.state, 'unavailable');
      assertSettings(unsupported, section, entries[6]);
    }
  }
  const throwing = startScript(html, script, true, doc => {
    doc.fonts.load = () => { throw new Error('Synchronous font API failure'); };
  });
  for (const section of ['pair', 'text']) assert.equal(get(throwing, section + 'FontStatus').dataset.state, 'failed');

  const lostAPI = startScript(html, script);
  const api = lostAPI.document.fonts;
  lostAPI.document.fonts = undefined;
  for (const section of ['pair', 'text']) {
    get(lostAPI, section + 'Weight').value = '700';
    get(lostAPI, section + 'Weight').dispatch('change');
  }
  await settle(lostAPI.loads[0]);
  await reject(lostAPI.loads[1]);
  for (const section of ['pair', 'text']) assert.equal(get(lostAPI, section + 'FontStatus').dataset.state, 'unavailable', 'Stale completion cannot overwrite unavailable status');
  lostAPI.document.fonts = api;
  for (const section of ['pair', 'text']) {
    await settle(changeWeight(lostAPI, section, 600));
    assert.equal(get(lostAPI, section + 'FontStatus').dataset.state, 'ready');
  }

  console.log('PASS: both independent nine-weight controls; all six fixed flags and amounts; literal shared text; reading sizes; space scope; font errors, recovery and stale-load races.');
  console.log('Mocked DOM only: real font loading, layout, rendering, shaping and geometry were not tested.');
}

main().catch(error => {
  if (error.code === 'ENOENT') console.error('Pass a render-generated HTML path, or let the parent builder create proof.html first. ' + error.message);
  else console.error(error.stack || error);
  process.exitCode = 1;
});
