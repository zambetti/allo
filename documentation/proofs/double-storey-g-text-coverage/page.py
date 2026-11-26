"""Self-contained reading proof; existing fonts and corpus are supplied by the builder."""
from html import escape
import json
from string import Template

ACTIVE = {"ss12", "ss15", "ss17", "ss19"}
FEATURES = ", ".join(f'"ss{i}" {int(f"ss{i}" in ACTIVE)}' for i in range(11, 21))

_PAGE = Template(r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Allo — g in everyday text and every lowercase pair</title>
<style>
$font_rules
:root {color-scheme:light; --selected-weight:400; --pair-size:24px}
* {box-sizing:border-box}
body {margin:0; background:#fff; color:#191919; font:16px/1.5 system-ui,sans-serif}
main {max-width:1440px; margin:auto; padding:32px}
h1 {font-size:36px; line-height:1.15; font-weight:500; margin:8px 0 16px}
h2 {font-size:21px; line-height:1.3; font-weight:600; margin:0 0 8px}
h3 {font-size:15px; font-weight:600; margin:0 0 12px}
p {margin:8px 0 12px}
a {color:inherit; text-underline-offset:3px}
.note, .eyebrow, .kind-label {font-size:13px; color:#555}
.eyebrow {margin:0; text-transform:uppercase; letter-spacing:.05em}
.controls {display:flex; flex-wrap:wrap; gap:20px; margin:20px 0 12px}
.control {width:270px; max-width:100%}
label {display:block; font-size:14px; font-weight:500; margin-bottom:6px}
select, textarea, button {padding:8px 10px; border:1px solid #999; border-radius:3px; background:#fff; color:inherit; font:inherit}
select, textarea {width:100%}
textarea {resize:vertical; display:block; margin-bottom:12px}
button {cursor:pointer}
:focus-visible {outline:2px solid #191919; outline-offset:3px}
details {margin:18px 0 24px}
summary {cursor:pointer; font-size:14px; margin-bottom:10px}
#fontStatus[data-state=failed], #fontStatus[data-state=unavailable] {border:2px solid #555; padding:10px; font-weight:600}
.reading-grid, .pair-grid, .checkpoint-grid {display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:24px}
.reading-grid {align-items:start}
.reading-panel, .proof-panel {border:1px solid #ddd; padding:20px; background:#fff; min-width:0}
.proof-panel {margin-top:28px}
.font-sample {font-family:CoverageProof,sans-serif; font-style:normal; font-weight:400; font-stretch:normal; font-synthesis:none; font-variant:normal; font-kerning:normal; font-optical-sizing:none; font-variation-settings:normal; font-feature-settings:$features; letter-spacing:normal; word-spacing:normal; text-align:left; text-transform:none; text-rendering:auto; direction:ltr; hyphens:none; word-break:normal; overflow-wrap:normal; margin:0; min-width:0}
.selected-sample {font-weight:var(--selected-weight)}
.reading-text {white-space:pre-wrap; line-height:1.5; margin-top:18px}
#reading16 .font-sample {font-size:16px}
#reading24 .font-sample {font-size:24px}
.focus-words {line-height:1.5; margin-top:22px; padding-top:16px; border-top:1px solid #ddd}
.pair-grid {gap:32px; margin-top:20px}
.pair-column {min-width:0}
.pair-row {display:grid; grid-template-columns:60px minmax(0,1fr) 72px; align-items:center; gap:12px; padding:10px 0; border-top:1px solid #eee; min-width:0}
.pair-size {font-size:var(--pair-size); line-height:1.45}
.pair-token {white-space:nowrap}
.kind-label {text-align:right; line-height:1.3}
.capital-grid {display:grid; grid-template-columns:repeat(13,minmax(0,1fr)); gap:12px 16px; margin:18px 0 24px}
.boundary-line {display:flex; flex-wrap:wrap; gap:10px 30px; margin:12px 0 20px}
.boundary-sample, .capital-pair {white-space:pre}
.checkpoint-grid {gap:24px 36px; margin-top:20px}
.checkpoint {border-top:1px solid #ddd; padding-top:16px; min-width:0}
.checkpoint-sample {font-size:24px; line-height:1.5}
footer {margin-top:28px; border-top:1px solid #ddd; padding-top:16px}
@media (max-width:900px) {
  main {padding:24px 16px}
  .reading-grid, .pair-grid, .checkpoint-grid {grid-template-columns:1fr}
  .capital-grid {grid-template-columns:repeat(7,minmax(0,1fr))}
  .pair-row {grid-template-columns:48px minmax(0,1fr) 60px; gap:8px}
}
</style>
</head>
<body>
<main>
<header>
  <p class="eyebrow">Allo / double-storey g / coverage study 07</p>
  <h1>g in everyday text</h1>
  <p>One fixed spacing setting, not another set of alternatives. Read the paragraphs first; use the pair rows to find any particular join that feels uneven.</p>
  <p class="note">Tighter ng only · approved outgoing C/B spacing · heavy gj refinement. The other incoming pairs are unchanged. Regular is the reviewed preference; the other weights remain review candidates. Upright Text / Friendly only.</p>
</header>
<div class="controls">
  <div class="control"><label for="weight">Weight · reading, pairs and boundaries</label><select id="weight">$weight_options</select></div>
  <div class="control"><label for="pairSize">Pair and boundary size</label><select id="pairSize"><option value="16">16 CSS px</option><option value="24" selected>24 CSS px</option><option value="32">32 CSS px</option></select></div>
</div>
<p class="note" id="settingSummary">Regular · 400 · ng tightened by 48 font units (2048/em).</p>
<p class="note" id="fontStatus" role="status" aria-live="polite" aria-atomic="true" data-state="loading">Loading and verifying all nine embedded fonts… Live text may be fallback until this completes.</p>
<details id="passageEditor">
  <summary>Try your own reading text</summary>
  <label for="words">Replaces both reading passages; fixed words and coverage rows stay unchanged</label>
  <textarea id="words" rows="6" spellcheck="false">$passage</textarea>
  <button id="resetText" type="button">Restore the proof text</button>
  <p class="note">Text is copied literally, including blank lines. Use browser zoom 100%; sizes below are CSS pixels.</p>
</details>
<div class="reading-grid">
  <section class="reading-panel" id="reading16" aria-labelledby="reading16Title">
    <p class="eyebrow">Allo / ordinary reading</p>
    <h2 id="reading16Title">16 CSS px · <span class="selected-label">Regular · 400</span></h2>
    <p class="note">Tighter ng · approved outgoing spacing · same text at both sizes</p>
    <div class="font-sample selected-sample reading-text">$passage</div>
    <p class="font-sample selected-sample focus-words">$focus_words</p>
  </section>
  <section class="reading-panel" id="reading24" aria-labelledby="reading24Title">
    <p class="eyebrow">Allo / ordinary reading</p>
    <h2 id="reading24Title">24 CSS px · <span class="selected-label">Regular · 400</span></h2>
    <p class="note">Tighter ng · approved outgoing spacing · same text at both sizes</p>
    <div class="font-sample selected-sample reading-text">$passage</div>
    <p class="font-sample selected-sample focus-words">$focus_words</p>
  </section>
</div>
<section class="proof-panel" id="pairCoverage" aria-labelledby="pairTitle">
  <p class="eyebrow">Allo / systematic lowercase coverage</p>
  <h2 id="pairTitle">Every lowercase neighbour · <span class="selected-label">Regular · 400</span></h2>
  <p class="note"><span class="pair-size-label">24 CSS px</span> · 26 incoming + 26 outgoing rows. gg appears in both columns.</p>
  <p class="note">Real words where practical; rows labeled “test string” are invented. No highlighting or letter spacing is inserted inside a word. Pair tokens are diagnostic; judge the word alongside them.</p>
  <div class="pair-grid">$pair_columns</div>
</section>
<section class="proof-panel" id="boundaryCoverage" aria-labelledby="boundaryTitle">
  <p class="eyebrow">Allo / boundaries and controls</p>
  <h2 id="boundaryTitle">Capitals, spaces and punctuation · <span class="selected-label">Regular · 400</span></h2>
  <p class="note"><span class="pair-size-label">24 CSS px</span> · Diagnostic strings, not a claim that these are ordinary words.</p>
  <h3>Every capital immediately before lowercase g</h3>
  <div class="capital-grid">$capital_pairs</div>
  $boundary_groups
</section>
<section class="proof-panel" id="weightCheckpoints" aria-labelledby="checkpointTitle">
  <p class="eyebrow">Allo / weight checkpoints</p>
  <h2 id="checkpointTitle">One passage, four weights · 24 CSS px</h2>
  <p class="note">These four weights stay fixed when the selector changes. The stronger ng trial scales from −40 at Thin to −64 at Black; approval at Regular does not establish optical approval of every weight.</p>
  <div class="checkpoint-grid">$checkpoints</div>
</section>
<footer class="note">
  <p>Reading and coverage only. No new drawings, kerning edits, font installation or production integration. The page embeds unchanged study 06 font tables in WOFF2 form; it works offline.</p>
  <p><a href="README.md">Study notes</a> · <a href="coverage.json">Text and pair inventory</a> · <a href="validation.json">Build checks</a> · <a href="clearances.json">Sampled clearances</a> · <a href="../double-storey-g-incoming-spacing/proof.html">Earlier ng comparison</a></p>
  <details><summary>Exact diagnostic feature settings</summary><code>$features_text</code></details>
</footer>
</main>
<script>
'use strict';
const config = $config_json;
const byId = id => document.getElementById(id);
const weight = byId('weight');
const pairSize = byId('pairSize');
const words = byId('words');
const status = byId('fontStatus');
function updateSelection() {
  const entry = config.weights.find(item => item.weight === Number(weight.value));
  document.documentElement.style.setProperty('--selected-weight', String(entry.weight));
  document.documentElement.style.setProperty('--pair-size', pairSize.value + 'px');
  document.querySelectorAll('.selected-label').forEach(node => { node.textContent = entry.style + ' · ' + entry.weight; });
  document.querySelectorAll('.pair-size-label').forEach(node => { node.textContent = pairSize.value + ' CSS px'; });
  byId('settingSummary').textContent = entry.style + ' · ' + entry.weight + ' · ng tightened by ' + entry.tighter + ' font units (2048/em). Other incoming pairs unchanged.';
}
function updateText() {
  document.querySelectorAll('.reading-text').forEach(node => { node.textContent = words.value; });
}
function resetText() {
  words.value = config.paragraphs.join('\n\n');
  updateText();
}
async function loadFonts() {
  if (!document.fonts || typeof document.fonts.load !== 'function') {
    status.dataset.state = 'unavailable';
    status.textContent = 'Font verification is unavailable. Live text may be fallback; use the saved browser captures instead.';
    return;
  }
  let timer;
  try {
    // Load once: every selector state and fixed checkpoint then uses a verified face.
    const requests = config.weights.map(async entry => {
      const faces = await document.fonts.load(entry.weight + ' 24px "CoverageProof"', 'Morning ng hg mg ug go ge gc gj Ag “g”');
      if (faces.length !== 1 || faces[0].status !== 'loaded' || faces[0].weight !== String(entry.weight) ||
          faces[0].style !== 'normal' || faces[0].family.replace(/["']/g, '') !== 'CoverageProof') {
        throw new Error('Exact embedded face unavailable: ' + entry.weight);
      }
    });
    await Promise.race([Promise.all(requests), new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error('Font load timed out')), 10000);
    })]);
    status.dataset.state = 'ready';
    status.textContent = 'All nine embedded fonts loaded. This verifies font availability, not optical approval.';
  } catch (error) {
    status.dataset.state = 'failed';
    status.textContent = 'Font verification failed: ' + error.message + '. Live text may be fallback; use the saved browser captures instead.';
  } finally { clearTimeout(timer); }
}
weight.addEventListener('change', updateSelection);
pairSize.addEventListener('change', updateSelection);
words.addEventListener('input', updateText);
byId('resetText').addEventListener('click', resetText);
resetText();
updateSelection();
loadFonts();
</script>
</body>
</html>
''')


def render(font_rules, config, inventory):
    options = ''.join(
        f'<option value="{entry["weight"]}"' + (' selected' if entry['weight'] == 400 else '') +
        f'>{escape(entry["style"])} · {entry["weight"]}</option>' for entry in config['weights'])
    columns = []
    for direction, label in (("incoming", "Before g"), ("outgoing", "After g")):
        rows = []
        for row in inventory['rows']:
            if row['direction'] != direction:
                continue
            rows.append(f'<div class="pair-row" data-direction="{direction}" data-pair="{row["pair"]}" data-kind="{row["kind"]}">'
                        f'<span class="font-sample selected-sample pair-size pair-token">{row["pair"]}</span>'
                        f'<span class="font-sample selected-sample pair-size word-example">{escape(row["text"])}</span>'
                        f'<span class="kind-label">{"word" if row["kind"] == "word" else "test string"}</span></div>')
        columns.append(f'<div class="pair-column"><h3>{label}</h3>{"".join(rows)}</div>')
    capitals = ''.join(f'<span class="font-sample selected-sample pair-size capital-pair">{pair}</span>' for pair in inventory['capital_pairs'])
    boundaries = ''.join(
        f'<h3>{escape(group["label"])}</h3><div class="boundary-line">' +
        ''.join(f'<span class="font-sample selected-sample pair-size boundary-sample">{escape(run)}</span>' for run in group['runs']) + '</div>'
        for group in inventory['boundaries'])
    checkpoints = ''.join(
        f'<article class="checkpoint"><h3>{escape(entry["style"])} · {entry["weight"]} / ng −{entry["tighter"]}</h3>'
        f'<p class="font-sample checkpoint-sample" data-weight="{entry["weight"]}" style="font-weight:{entry["weight"]}">{escape(inventory["checkpoint_text"])}</p></article>'
        for entry in config['weights'] if entry['weight'] in inventory['checkpoint_weights'])
    serialized = json.dumps(config, ensure_ascii=True, allow_nan=False).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
    return _PAGE.substitute(font_rules=font_rules, features=FEATURES, features_text=escape(FEATURES),
                            config_json=serialized, weight_options=options,
                            passage=escape('\n\n'.join(config['paragraphs'])), focus_words=escape(inventory['focus_words']),
                            pair_columns=''.join(columns), capital_pairs=capitals,
                            boundary_groups=boundaries, checkpoints=checkpoints)
