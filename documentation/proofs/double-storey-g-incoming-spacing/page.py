"""Pure HTML renderer for the incoming double-storey-g spacing comparison.

The parent owns fonts, generated HTML, sheets and reports. Keep the HTML source
in this Python template, not an editor-managed .html source file.
"""

import json
from html import escape
from string import Template

_TAGS = tuple(f"ss{number}" for number in range(11, 21))
_BASE = ("ss15", "ss17", "ss19")
_SLIGHT = dict(zip(range(100, 901, 100), (20, 22, 23, 24, 26, 27, 29, 30, 32)))
_VARIANTS = (("current", "Current"), ("slight", "Slightly tighter"), ("tighter", "Tighter"))
_GROUPS = (
    ("incoming", "Incoming · target and controls", ("ng", "hg", "mg", "ug")),
    ("unrelated", "Unrelated incoming · unchanged", ("og", "ag", "rg")),
    ("outgoing", "Approved outgoing · unchanged", ("go", "ge", "gc", "gj")),
    ("guards", "Guards · only the incoming step changes", ("ngj", "ngo")),
)
_WORDS = ("Morning", "beginning", "changing", "going")

_PAIR_COLUMN = Template(r"""
<article class="comparison-column pair-column" data-variant="$variant" aria-labelledby="pairHeading-$variant">
  <h3 id="pairHeading-$variant">$heading</h3>
  <p class="amount" id="pairAmount-$variant">$amount</p>
  $groups
</article>
""")

_READING_COLUMN = Template(r"""
<article class="comparison-column reading-column" data-variant="$variant" aria-labelledby="readingHeading-$variant">
  <h3 id="readingHeading-$variant">$heading</h3>
  <p class="amount" id="readingAmount-$variant">$amount</p>
  $words
  <p class="group-label">Shared passage</p>
  <div class="font-sample reading-size reading-text" data-variant="$variant" id="reading-$variant">$passage</div>
</article>
""")

_PAGE = Template(r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Allo — incoming space before double-storey g</title>
<style>
$font_rules
:root {color-scheme:light}
* {box-sizing:border-box}
body {margin:0; background:#fff; color:#191919; font:16px/1.5 system-ui,sans-serif}
main {max-width:1440px; margin:auto; padding:28px 32px 40px}
h1 {font-size:32px; line-height:1.2; font-weight:500; margin:8px 0 16px}
h2 {font-size:20px; line-height:1.3; font-weight:500; margin:0 0 10px}
h3 {font-size:16px; line-height:1.4; margin:0; font-weight:600}
p {margin:10px 0}
a {color:inherit; text-underline-offset:3px}
.note, .amount, .group-label {font-size:13px; color:#555}
.eyebrow {font-size:13px; color:#555; margin:0}
.controls {display:flex; flex-wrap:wrap; gap:16px; margin:20px 0 12px}
.control {flex:1 1 180px; max-width:400px}
label {display:block; font-size:14px; font-weight:500; margin-bottom:5px}
select, textarea {width:100%; padding:8px; color:inherit; background:#fff; border:1px solid #888; border-radius:3px; font:inherit}
textarea {display:block; resize:vertical; min-height:100px}
:focus-visible {outline:2px solid #191919; outline-offset:3px}
#scopeNote {border-inline-start:2px solid #aaa; padding-inline-start:12px}
#fontStatus {min-height:1.5em}
#fontStatus[data-state=failed], #fontStatus[data-state=unavailable] {border:2px solid #555; padding:10px; font-weight:600}
details {margin:12px 0}
summary {cursor:pointer; font-size:14px}
#passageEditor label {margin-top:10px}
.comparison-scroll {overflow-x:auto; margin-top:24px; padding-bottom:4px}
.comparison-grid {display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px 24px; min-width:840px}
.comparison-column {display:grid; grid-template-rows:subgrid; min-width:0; border-top:1px solid #aaa; padding-top:12px}
.pair-column {grid-row:span 6}
.reading-column {grid-row:span 8}
.amount, .group-label {margin:0}
.pair-group {min-width:0; margin-top:8px}
.pair-line {display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:0 12px}
.font-sample {font-family:SpacingProof,sans-serif; font-weight:400; font-style:normal; font-stretch:normal; font-synthesis:none; font-variant:normal; font-kerning:normal; letter-spacing:normal; word-spacing:normal; text-align:left; text-transform:none; hyphens:none; word-break:normal; overflow-wrap:normal; min-width:0; margin:0}
.font-sample[data-variant=current] {font-feature-settings:$current_features}
.font-sample[data-variant=slight] {font-feature-settings:$slight_features}
.font-sample[data-variant=tighter] {font-feature-settings:$tighter_features}
.pair-sample {display:block; font-size:64px; line-height:1.2; white-space:pre}
.reading-size {font-size:24px; line-height:1.5}
.focus-word {white-space:nowrap}
.reading-text {white-space:pre-wrap}
#readingComparison {padding-top:12px; background:#fff}
#readingSummary {margin:0 0 14px}
.feature-flags {display:block; font-size:12px; overflow-wrap:anywhere; margin:6px 0}
footer {border-top:1px solid #ddd; margin-top:28px; padding-top:12px}
@media (max-width:900px) {main {padding:24px 16px} .comparison-scroll {overflow-x:auto}}
</style>
</head>
<body>
<main>
<header>
  <p class="eyebrow">Incoming spacing study · nine static weights · proof only</p>
  <h1>Incoming space before g</h1>
  <p>Current spacing beside two modestly tighter trials. Start with <strong>ng only</strong>; h / m / u are controls. No final setting is selected by this proof.</p>
</header>
<section id="comparison" aria-label="Incoming spacing comparison">
  <div class="controls">
    <div class="control"><label for="weight">Weight · whole page</label><select id="weight">$weight_options</select></div>
    <div class="control"><label for="scope">Incoming scope · comparison only</label><select id="scope"><option value="ng-only" selected>ng only · h / m / u unchanged</option><option value="stems">n / h / m / u · shared-stem hypothesis</option></select></div>
    <div class="control"><label for="readingSize">Reading size · all three columns</label><select id="readingSize"><option value="12">12 CSS px</option><option value="16">16 CSS px</option><option value="24" selected>24 CSS px</option></select></div>
  </div>
  <p class="note" id="trialSummary">$trial_summary</p>
  <p class="note" id="scopeNote">ng-only trial: only n immediately before g changes. hg / mg / ug remain untouched controls in all three columns.</p>
  <p class="note" id="preservationNote">Each trial is negative incoming PairPos on the preceding letter’s advance, never a change to g’s advance or drawing. All columns preserve the APPROVED outgoing C spacing for go / ge / gc, B for other g advances, the heavy gj refinement, and the current word-space policy. No production, accent or oblique integration.</p>
  <p class="note" id="fontStatus" role="status" aria-live="polite" aria-atomic="true" data-state="loading" data-weight="400">Loading embedded Regular (400)… Live text may be fallback until the face is verified.</p>
  <details id="passageEditor">
    <summary>Edit the shared passage</summary>
    <label for="words">Literal text · copied to all three columns</label>
    <textarea id="words" rows="4" spellcheck="false" aria-describedby="textHint">
$passage</textarea>
    <p class="note" id="textHint">Blank lines, punctuation and markup-like text are copied literally. Fixed words and pair controls do not change.</p>
  </details>
  <div class="comparison-scroll">
    <section id="pairComparison" aria-labelledby="pairTitle">
      <h2 id="pairTitle">Pairs · fixed 64 CSS px</h2>
      <div class="comparison-grid" id="pairGrid">$pair_columns</div>
    </section>
  </div>
  <div class="comparison-scroll">
    <section id="readingComparison" aria-labelledby="readingTitle">
      <h2 id="readingTitle">Words and shared passage</h2>
      <p class="note" id="readingSummary">Regular · 400 · ng only · 24 CSS px</p>
      <div class="comparison-grid" id="readingGrid">$reading_columns</div>
    </section>
  </div>
  <p class="note">Use browser zoom 100% to judge reading sizes. Columns stay equal and aligned, with natural left-aligned, ragged-right wrapping, no justification and no added tracking. On a narrow screen, scroll horizontally rather than stacking the columns.</p>
</section>
<noscript><p><strong>Live controls and font verification require JavaScript.</strong> The default comparison is 400 / ng only / 24 CSS px, but the embedded font cannot be verified here. Use the static sheets if text is fallback.</p></noscript>
<details id="featureDetails">
  <summary>Explicit font features and proof scope</summary>
  <p class="note">Nine embedded faces belong to the separate Allo G Incoming Study family, exposed as SpacingProof. All ten optional features are off by default in the standalone fonts. This page explicitly sets ss11 through ss20 for every sample. No font installation or network is needed.</p>
  <p class="note">Always on: ss15 (heavy gj refinement), ss17 (B on all g), ss19 (extra B before o / e / c, making C). Always off: ss16 (the unadopted boundary trial), ss18 and ss20. ng-only trials use ss11 / ss12; the comparison-only shared-stem hypothesis uses ss13 / ss14 instead. The two trial levels are alternatives, never cumulative.</p>
  <code class="feature-flags" id="features-current">Current: $current_features</code>
  <code class="feature-flags" id="features-slight">Slightly tighter: $slight_features</code>
  <code class="feature-flags" id="features-tighter">Tighter: $tighter_features</code>
</details>
<footer>
  <p class="note">Static comparison: <a href="proof.svg">SVG</a> / <a href="proof.png">PNG</a> · All weights: <a href="weights.svg">SVG</a> / <a href="weights.png">PNG</a>. Sheets are independent of the live controls.</p>
  <p class="note"><a href="README.md">Build and scope notes</a> · <a href="validation.json">Build validation</a> · <a href="clearances.json">Clearances and caveats</a> · <a href="browser/validation.json">Real-browser report</a> · <a href="../double-storey-g-spacing-finish/proof.html">Previous outgoing-spacing finish</a> · <a href="../../../OFL.txt">SIL Open Font License 1.1</a></p>
  <p class="note" id="validationNote">This page does not assert that browser checks have passed. Consult the real-browser report’s status and proof SHA-256 for this exact generated HTML. A loaded font status reports availability, not optical approval; width checks do not select a final setting.</p>
</footer>
</main>
<script>
'use strict';
const config = $config_json;
const tags = ['ss11', 'ss12', 'ss13', 'ss14', 'ss15', 'ss16', 'ss17', 'ss18', 'ss19', 'ss20'];
const variants = ['current', 'slight', 'tighter'];
const headings = {current: 'Current', slight: 'Slightly tighter', tighter: 'Tighter'};
const byId = id => document.getElementById(id);
const weight = byId('weight');
const scope = byId('scope');
const readingSize = byId('readingSize');
const words = byId('words');
const status = byId('fontStatus');
const samples = Array.from(document.querySelectorAll('.font-sample'));
let latestFontRequest = 0;

function features(variant) {
  const on = ['ss15', 'ss17', 'ss19'];
  if (variant !== 'current') {
    on.push(scope.value === 'ng-only' ? (variant === 'slight' ? 'ss11' : 'ss12') : (variant === 'slight' ? 'ss13' : 'ss14'));
  }
  return tags.map(tag => '"' + tag + '" ' + (on.includes(tag) ? 1 : 0)).join(', ');
}

function selectedWeight() {
  return config.weights.find(entry => entry.weight === Number(weight.value));
}

function updateComparison() {
  const entry = selectedWeight();
  const ngOnly = scope.value === 'ng-only';
  samples.forEach(sample => {
    sample.style.fontWeight = String(entry.weight);
    sample.style.fontFeatureSettings = features(sample.dataset.variant);
    if (sample.classList.contains('reading-size')) sample.style.fontSize = readingSize.value + 'px';
  });
  variants.forEach(variant => {
    const amount = variant === 'current' ? 'Incoming: unchanged' : 'Incoming: −' + entry[variant] + ' font units';
    byId('pairAmount-' + variant).textContent = amount;
    byId('readingAmount-' + variant).textContent = amount;
    byId('features-' + variant).textContent = headings[variant] + ': ' + features(variant);
  });
  byId('trialSummary').textContent = entry.style + ' · ' + entry.weight + ' — incoming reductions: 0 / −' + entry.slight + ' / −' + entry.tighter + ' font units (2048/em). The stronger trial is exactly twice the slight trial.';
  byId('scopeNote').textContent = ngOnly ?
    'ng-only trial: only n immediately before g changes. hg / mg / ug remain untouched controls in all three columns.' :
    'COMPARISON ONLY — shared-stem hypothesis: n / h / m / u immediately before g all receive the same trial amount. This does not establish or adopt a spacing class.';
  byId('readingSummary').textContent = entry.style + ' · ' + entry.weight + ' · ' + (ngOnly ? 'ng only' : 'shared stems · comparison-only hypothesis') + ' · ' + readingSize.value + ' CSS px';
}

function updateText() {
  document.querySelectorAll('.reading-text').forEach(sample => { sample.textContent = words.value; });
}

async function loadSelectedFont() {
  // A generation token, not just a weight check, protects A → B → A requests.
  const request = ++latestFontRequest;
  const entry = selectedWeight();
  const label = entry.style + ' (' + entry.weight + ')';
  status.dataset.state = 'loading';
  status.dataset.weight = String(entry.weight);
  status.dataset.request = String(request);
  status.textContent = 'Loading embedded ' + label + '… Live text may be fallback until the face is verified.';
  let timer;
  try {
    if (!document.fonts || typeof document.fonts.load !== 'function') {
      status.dataset.state = 'unavailable';
      status.textContent = 'Font verification unavailable for ' + label + '. Live text may be fallback; use the linked static sheets instead.';
      return;
    }
    const faces = await Promise.race([
      document.fonts.load(entry.weight + ' 64px "SpacingProof"', 'ng hg mg ug og ag rg go ge gc gj Morning beginning changing going'),
      new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('Font load timed out')), 10000); }),
    ]);
    if (request !== latestFontRequest) return;
    if (faces.length !== 1 || faces[0].status !== 'loaded' || faces[0].weight !== String(entry.weight) ||
        faces[0].style !== 'normal' || faces[0].family.replace(/^["']|["']$$/g, '') !== 'SpacingProof') {
      throw new Error('The exact embedded static face was not loaded');
    }
    status.dataset.state = 'ready';
    status.textContent = 'Embedded ' + label + ' loaded. Font availability only, not spacing approval.';
  } catch (error) {
    if (request !== latestFontRequest) return;
    status.dataset.state = 'failed';
    status.textContent = 'Font loading failed for ' + label + '. Live text may be fallback; use the linked static sheets instead.';
  } finally {
    clearTimeout(timer);
  }
}

weight.addEventListener('change', () => { updateComparison(); loadSelectedFont(); });
scope.addEventListener('change', updateComparison);
readingSize.addEventListener('change', updateComparison);
words.addEventListener('input', updateText);
words.value = config.paragraphs.join('\n\n');
updateComparison();
updateText();
loadSelectedFont();
</script>
</body>
</html>
""")


def _features(variant):
    active = set(_BASE)
    if variant != "current":
        active.add("ss11" if variant == "slight" else "ss12")
    return ", ".join(f'"{tag}" {int(tag in active)}' for tag in _TAGS)


def render(font_rules: str, config: dict) -> str:
    """Return HTML without filesystem access or mutation of caller-owned data.

    ``font_rules`` is trusted parent-supplied CSS for nine embedded SpacingProof
    faces (internal family Allo G Incoming Study). ``config`` has ``weights``
    containing weight/style/slight/tighter and a ``paragraphs`` list of strings.
    Trial amounts are positive magnitudes; fonts apply negative PairPos to the
    preceding letter. This renderer never builds or changes a font.
    """
    if not isinstance(font_rules, str) or not font_rules.strip():
        raise ValueError("Expected trusted embedded font CSS")
    if not isinstance(config, dict) or not isinstance(config.get("weights"), list):
        raise TypeError("Expected a config with a weights list")
    fields = ("weight", "style", "slight", "tighter")
    weights = []
    for entry in config["weights"]:
        if not isinstance(entry, dict) or not set(fields) <= entry.keys():
            raise ValueError("Each weight needs weight, style, slight and tighter")
        weight = entry["weight"]
        if isinstance(weight, bool) or not isinstance(weight, int) or weight not in _SLIGHT:
            raise ValueError("Expected integer weights 100 through 900 in steps of 100")
        if not isinstance(entry["style"], str) or not entry["style"].strip():
            raise ValueError("Each weight needs a nonempty style label")
        for field, expected in (("slight", _SLIGHT[weight]), ("tighter", 2 * _SLIGHT[weight])):
            amount = entry[field]
            if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount != expected:
                raise ValueError(f"Weight {weight}: {field} must be {expected} font units")
        weights.append({"weight": weight, "style": entry["style"],
                        "slight": _SLIGHT[weight], "tighter": 2 * _SLIGHT[weight]})
    weights.sort(key=lambda entry: entry["weight"])
    if [entry["weight"] for entry in weights] != list(_SLIGHT):
        raise ValueError("Expected exactly nine distinct weights, 100 through 900")
    paragraphs = config.get("paragraphs")
    if not isinstance(paragraphs, list) or not paragraphs or not all(isinstance(text, str) for text in paragraphs):
        raise ValueError("Expected a nonempty paragraphs list of literal strings")
    data = {"weights": weights, "paragraphs": list(paragraphs)}
    # JSON lives inside a script, not in an HTML text node. Escape its delimiters.
    config_json = (json.dumps(data, ensure_ascii=True, allow_nan=False)
                   .replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e"))
    passage = escape("\n\n".join(paragraphs))
    regular = weights[3]
    pair_columns, reading_columns = [], []
    for variant, heading in _VARIANTS:
        amount = "Incoming: unchanged" if variant == "current" else f'Incoming: −{regular[variant]} font units'
        groups = []
        for key, label, runs in _GROUPS:
            spans = "".join(
                f'<span class="font-sample pair-sample" data-variant="{variant}" data-run="{run}" '
                f'id="pair-{variant}-{run}">{run}</span>' for run in runs)
            groups.append(f'<div class="pair-group" id="group-{variant}-{key}">'
                          f'<p class="group-label">{label}</p><div class="pair-line">{spans}</div></div>')
        word_lines = "".join(
            f'<p class="font-sample reading-size focus-word" data-variant="{variant}" '
            f'id="word-{variant}-{word}">{word}</p>' for word in _WORDS)
        pair_columns.append(_PAIR_COLUMN.substitute(
            variant=variant, heading=heading, amount=amount, groups="\n".join(groups)))
        reading_columns.append(_READING_COLUMN.substitute(
            variant=variant, heading=heading, amount=amount, words=word_lines, passage=passage))
    options = "\n".join(
        '<option value="{}"{}>{} · {}</option>'.format(
            entry["weight"], " selected" if entry["weight"] == 400 else "",
            escape(entry["style"]), entry["weight"]) for entry in weights)
    return _PAGE.substitute(
        font_rules=font_rules, config_json=config_json, passage=passage,
        current_features=_features("current"), slight_features=_features("slight"),
        tighter_features=_features("tighter"), weight_options=options,
        pair_columns="\n".join(pair_columns), reading_columns="\n".join(reading_columns),
        trial_summary=escape(
            f'{regular["style"]} · 400 — incoming reductions: 0 / −{regular["slight"]} / '
            f'−{regular["tighter"]} font units (2048/em). The stronger trial is exactly twice the slight trial.'))
