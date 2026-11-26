"""Side-effect-free HTML renderer for the double-storey g spacing finish proof.

Only the parent builder owns fonts, reports, sheets, and generated proof.html.
Keep the HTML in Python templates to avoid editor HTML auto-closing changes.
"""

import json
from html import escape
from math import isfinite
from string import Template
from unicodedata import name as unicode_name

_TAGS = ("ss15", "ss16", "ss17", "ss18", "ss19", "ss20")
_ACTIVE = {
    "chosen": ("ss17", "ss19"),
    "refined": ("ss15", "ss17", "ss19"),
    "boundary": ("ss15", "ss16", "ss17", "ss19"),
}
_CORRECTIONS = {weight: amount for weight, amount in zip(
    range(100, 901, 100), (0, 0, 0, 0, 0, 0, 8, 27, 40))}
_GAPS = {
    700: ("49.7625", "57.7625"),
    800: ("28.6425", "55.6425"),
    900: ("8.3873", "48.3873"),
}

_PAIR_COLUMN = Template(r"""
<article class="comparison-column pair-column" data-variant="$variant" aria-labelledby="pairHeading-$variant">
  <h3 id="pairHeading-$variant">$heading</h3>
  <p class="amount" id="pairAmount-$variant">$amount</p>
  <code class="feature-flags" id="pairFeatures-$variant">$features</code>
  <div class="pair-lines" id="pairSamples-$variant">
    <p class="font-sample pair-sample" data-variant="$variant" id="pair-$variant-gj">gj</p>
    <p class="font-sample pair-sample" data-variant="$variant" id="pair-$variant-gjg">gjg</p>
    <p class="font-sample pair-sample" data-variant="$variant" id="pair-$variant-guards">gg gy</p>
    <p class="font-sample pair-sample" data-variant="$variant" id="pair-$variant-rounds">go ge gc</p>
  </div>
</article>
""")

_READING_COLUMN = Template(r"""
<article class="comparison-column reading-column" data-variant="$variant" aria-labelledby="textHeading-$variant">
  <h3 id="textHeading-$variant">$heading</h3>
  <p class="amount" id="textAmount-$variant">$amount</p>
  <code class="feature-flags" id="textFeatures-$variant">$features</code>
  <div class="font-sample text-sample reading-size reading-text" data-variant="$variant" id="reading-$variant" aria-labelledby="textHeading-$variant">$text</div>
  <div class="diagnostic">
    <h4>Norwegian diagnostics · separate from the English passage</h4>
    <p class="font-sample text-sample reading-size" data-variant="$variant" id="norwegian-$variant" lang="nb">gjeng gjøre gjennom</p>
  </div>
  <div class="diagnostic">
    <h4>Space / terminal g · fixed 16 CSS px</h4>
    <span class="font-sample text-sample boundary-sample" data-variant="$variant" id="boundary-$variant" aria-describedby="boundaryNote boundaryScope">$boundary_sample</span>
  </div>
</article>
""")

_PAGE = Template(r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Allo — double-storey g spacing finish</title>
<style>
$font_rules
:root {color-scheme:light}
* {box-sizing:border-box}
body {margin:0; background:#fff; color:#191919; font:16px/1.6 system-ui,sans-serif}
main {max-width:1240px; margin:auto; padding:32px clamp(16px,4vw,56px) 48px}
h1 {font-size:clamp(26px,4vw,38px); line-height:1.2; font-weight:500; margin:8px 0 20px}
h2 {font-size:22px; line-height:1.3; font-weight:500; margin:32px 0 12px}
h3 {font-size:17px; line-height:1.4; font-weight:600; margin:0}
h4 {font-size:13px; font-weight:500; color:#595959; margin:0 0 8px}
p {margin:12px 0}
a {color:inherit; text-underline-offset:3px}
a:hover {text-decoration-thickness:2px}
.note, .amount, figcaption {font-size:14px; color:#595959}
.eyebrow {font-size:13px; color:#595959}
.controls {display:flex; flex-wrap:wrap; gap:16px; margin:20px 0 8px}
.control {flex:1 1 180px; max-width:360px; min-width:0}
label {display:block; font-weight:500; margin-bottom:6px}
select, textarea {width:100%; max-width:100%; padding:10px; border:1px solid #888; border-radius:3px; background:#fff; color:#191919; font:inherit}
textarea {min-height:160px; resize:vertical}
:focus-visible {outline:2px solid #191919; outline-offset:3px}
.font-status {min-height:1.6em}
.font-status[data-state=failed], .font-status[data-state=unavailable] {font-weight:600; color:#191919}
.comparison {display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px 28px; margin:24px 0}
.comparison-column {display:grid; grid-template-rows:subgrid; grid-row:span 4; min-width:0; border-top:1px solid #aaa; padding-top:16px}
.reading-column {grid-row:span 6}
.amount {margin:0}
.feature-flags {display:block; font-size:12px; color:#595959; overflow-wrap:anywhere}
.font-sample {font-family:SpacingProof,sans-serif; font-synthesis:none; font-style:normal; font-stretch:normal; font-variant:normal; font-kerning:normal; letter-spacing:normal; word-spacing:normal; text-align:start; text-transform:none; line-height:1.5; hyphens:manual; min-width:0; max-width:100%; margin:0; overflow-wrap:anywhere}
.font-sample[data-variant=chosen] {font-feature-settings:$chosen_features}
.font-sample[data-variant=refined] {font-feature-settings:$refined_features}
.font-sample[data-variant=boundary] {font-feature-settings:$boundary_features}
.pair-sample {font-size:72px; font-weight:900}
.text-sample {font-weight:400}
.reading-size {font-size:16px}
.reading-text {white-space:pre-wrap}
.diagnostic {margin-top:16px; min-width:0}
.boundary-sample {display:inline-block; font-size:16px; white-space:pre; border-inline-end:1px solid #777}
.scope-note {border-inline-start:2px solid #aaa; padding-inline-start:16px}
figure {margin:24px 0}
.sheet {display:block; width:100%; height:auto; border-top:1px solid #ddd}
figcaption {margin-top:10px}
footer {border-top:1px solid #ddd; margin-top:32px; padding-top:12px}
@media (max-width:720px) {
  .comparison {grid-template-columns:minmax(0,1fr); row-gap:28px}
  .comparison-column {grid-row:auto; grid-template-rows:none; row-gap:10px}
}
</style>
</head>
<body>
<main>
<header>
  <p class="eyebrow">Spacing finish · study 05 · nine static weights · proof only</p>
  <h1>A little more room for heavy gj</h1>
  <p>The selected spacing stays: C for go / ge / gc, B for other plain g advances. First compare the positive gj correction; then review running text and word spaces independently.</p>
  <p class="note" id="preservationNote">Nine embedded WOFF2 faces use the separate Allo G Spacing Finish family, exposed here as SpacingProof. All six optional features are off by default in the fonts; this page explicitly sets each one. This is a proof-only comparison, not a production change. No font installation or network request is needed for the live text.</p>
</header>
<section id="pairSection" aria-labelledby="pairTitle">
  <h2 id="pairTitle">1 · gj before / after · 72 CSS px</h2>
  <div class="controls">
    <div class="control"><label for="pairWeight">Pair weight</label><select id="pairWeight">$pair_options</select></div>
  </div>
  <p class="note" id="pairSummary">$pair_summary</p>
  <p class="note font-status" id="pairFontStatus" role="status" aria-live="polite" aria-atomic="true" data-state="loading" data-weight="900">Loading the embedded pair weight…</p>
  <div class="comparison" id="pairComparison">$pair_columns</div>
  <p class="note" id="pairGap">$pair_gap</p>
  <p class="scope-note note" id="correctionNote">ss15 adds positive advance only for gj; every other pair is unchanged by ss15. The supplied corrections are +0 at weights 100–600, +8 at 700, +27 at 800 and +40 at 900. They use 40 × smoothstep over design-coordinate 580–900, rounded; design coordinates are not CSS weight labels. +40 is a conservative optical trial, not an automatically derived minimum gap. These sampled horizontal gaps are not exact Euclidean distances or a guarantee of comfortable spacing.</p>
  <p class="note" id="featureNote">Fixed states: chosen = ss17 + ss19; refined = ss15 + ss17 + ss19; boundary = ss15 + ss16 + ss17 + ss19. ss17 applies B to every plain g advance; ss19 adds B before o / e / c, so B + B = C. ss18 (C on all g) and ss20 (C before o / e / c) stay off. Never ss17 + ss20: that would make 3B on round followers. Existing kerning stays active.</p>
</section>
<section id="textSection" aria-labelledby="textTitle">
  <h2 id="textTitle">2 · Running text and word spaces</h2>
  <p>The left column keeps the current word-space policy. The right column is an <strong>unadopted comparison only</strong>: it restores the inherited g advance only before the font’s space glyph. Both include the gj refinement.</p>
  <div class="controls">
    <div class="control"><label for="textWeight">Reading weight · both columns</label><select id="textWeight">$text_options</select></div>
    <div class="control"><label for="textSize">Reading size · both columns</label><select id="textSize"><option value="12">12 CSS px</option><option value="16" selected>16 CSS px</option><option value="24">24 CSS px</option></select></div>
  </div>
  <p class="note" id="sizeNote">Reading text and Norwegian diagnostics: <output id="textSizeValue" for="textSize">16 CSS px</output>. Use browser zoom 100% to judge these CSS reading sizes. Both columns use the same weight, size, width and typography, with natural ragged-right wrapping, no justification and no added tracking. The small boundary sample stays at 16 CSS px; the pair section stays at 72 CSS px.</p>
  <p class="note" id="textSummary">$text_summary</p>
  <p class="note font-status" id="textFontStatus" role="status" aria-live="polite" aria-atomic="true" data-state="loading" data-weight="400">Loading the embedded reading weight…</p>
  <label for="words">Shared passage · edit once, read in both columns</label>
  <textarea id="words" rows="6" spellcheck="false" aria-describedby="textHint">
$default_text</textarea>
  <p class="note" id="textHint">Text is copied literally, including blank lines between paragraphs. The fixed pairs, Norwegian diagnostics and boundary samples do not change when you edit it.</p>
  <div class="comparison" id="textComparison">$reading_columns</div>
  <p class="scope-note note" id="boundaryNote">Current policy reduces g by B before a space and at text end. The boundary trial adds +B only when g is followed by the font’s space glyph, cancelling that reduction there; it does not widen the space glyph itself. Terminal g retains B in both columns (an advance change of −B). In the fixed sample, the first g precedes a space; the thin rule after the final g marks the text-run end, including its advance. This is a word-space comparison, not an adopted exception or a general word-boundary rule.</p>
  <p class="note" id="boundaryScope">$boundary_scope</p>
</section>
<noscript><p>JavaScript is needed for the live controls and font-loading status. The static reference below is independent of the controls.</p></noscript>
<section aria-labelledby="sheetTitle">
  <h2 id="sheetTitle">Static heavy-gj reference</h2>
  <figure>
    <a href="proof.svg"><img class="sheet" src="proof.svg" loading="lazy" alt="Heavy gj spacing ladder: selected spacing before and after the positive gj correction"></a>
    <figcaption>Heavy-gj ladder · <a href="proof.svg">SVG</a> / <a href="proof.png">PNG</a>. This image scales to fit; its labelled sizes are intrinsic, not necessarily displayed CSS reading sizes. Live controls do not change it.</figcaption>
  </figure>
  <p class="note" id="validationNote">The UI unit checks are mocked-DOM tests, not browser tests. Separate headless Chromium checks verify the loaded fonts, controls, spacing deltas and reading layout; the browser report and screenshots are linked in the build notes. These checks do not establish appearance on every browser or display. A loaded status reports font availability, not optical approval.</p>
</section>
<footer>
  <p class="note"><a href="README.md">Build and scope notes</a> · <a href="validation.json">Build validation data</a> · <a href="clearances.json">Clearances and caveats</a> · <a href="../double-storey-g-selected-spacing/proof.html">Previous selected-spacing proof</a> · <a href="../../../OFL.txt">SIL Open Font License 1.1</a></p>
</footer>
</main>
<script>
'use strict';
const config = $config_json;
const gaps = $gaps_json;
const tags = ['ss15', 'ss16', 'ss17', 'ss18', 'ss19', 'ss20'];
const active = {chosen: ['ss17', 'ss19'], refined: ['ss15', 'ss17', 'ss19'], boundary: ['ss15', 'ss16', 'ss17', 'ss19']};
const byId = id => document.getElementById(id);
const pairWeight = byId('pairWeight');
const textWeight = byId('textWeight');
const textSize = byId('textSize');
const words = byId('words');
const pairSamples = Array.from(document.querySelectorAll('.pair-sample'));
const textSamples = Array.from(document.querySelectorAll('.text-sample'));

function features(variant) {
  return tags.map(tag => '"' + tag + '" ' + (active[variant].includes(tag) ? 1 : 0)).join(', ');
}

function selectedWeight(control) {
  return config.weights.find(entry => entry.weight === Number(control.value));
}

function summary(entry) {
  return entry.style + ' · ' + entry.weight + ' — C: −' + entry.tighter +
    ' for go / ge / gc; B: −' + entry.moderate +
    ' for other g advances, before the gj correction (font units; 2048/em).';
}

function applyWeight(samples, entry) {
  samples.forEach(sample => {
    sample.style.fontWeight = String(entry.weight);
    sample.style.fontFeatureSettings = features(sample.dataset.variant);
  });
}

function updatePairs() {
  const entry = selectedWeight(pairWeight);
  applyWeight(pairSamples, entry);
  byId('pairSummary').textContent = summary(entry);
  byId('pairAmount-chosen').textContent = 'gj correction: +0 font units · selected baseline.';
  byId('pairAmount-refined').textContent = 'gj correction: +' + entry.gj_correction + ' font units · ss15 only.';
  ['chosen', 'refined'].forEach(variant => { byId('pairFeatures-' + variant).textContent = features(variant); });
  byId('pairGap').textContent = gaps[entry.weight] ?
    'Sampled horizontal gj gap: ' + gaps[entry.weight][0] + ' → ' + gaps[entry.weight][1] + ' font units (chosen → refined).' :
    'No gj correction at this weight (+0); the two columns use the same spacing.';
}

function updateReading() {
  const entry = selectedWeight(textWeight);
  applyWeight(textSamples, entry);
  byId('textSummary').textContent = summary(entry);
  byId('textAmount-refined').textContent = 'Before space: −' + entry.moderate + ' (B); terminal g: −' + entry.moderate +
    ' (B). gj correction: +' + entry.gj_correction + ' font units.';
  byId('textAmount-boundary').textContent = 'Before space: −' + entry.moderate + ' +' + entry.moderate +
    ' = 0 (inherited); terminal g: −' + entry.moderate + ' (B). gj correction: +' + entry.gj_correction + ' font units.';
  ['refined', 'boundary'].forEach(variant => { byId('textFeatures-' + variant).textContent = features(variant); });
}

function updateText() {
  document.querySelectorAll('.reading-text').forEach(sample => { sample.textContent = words.value; });
}

function updateSize() {
  document.querySelectorAll('.reading-size').forEach(sample => { sample.style.fontSize = textSize.value + 'px'; });
  byId('textSizeValue').textContent = textSize.value + ' CSS px';
}

function fontLoader(status) {
  // Each section owns its token, including A → B → A requests for one weight.
  let latest = 0;
  return async (entry, size) => {
    const request = ++latest;
    const label = entry.style + ' (' + entry.weight + ')';
    status.dataset.state = 'loading';
    status.dataset.weight = String(entry.weight);
    status.textContent = 'Loading embedded ' + label + '…';
    try {
      if (!document.fonts || typeof document.fonts.load !== 'function') {
        status.dataset.state = 'unavailable';
        status.textContent = 'Font loading cannot be verified for ' + label + '. Live text may be fallback; use the static reference.';
        return;
      }
      const faces = await document.fonts.load(entry.weight + ' ' + size + 'px "SpacingProof"', 'gj ogec ø' + config.space_characters.join(''));
      if (request !== latest) return;
      if (!faces.length || faces.some(face => face.status !== 'loaded')) throw new Error('No loaded embedded face');
      status.dataset.state = 'ready';
      status.textContent = 'Embedded ' + label + ' loaded.';
    } catch (error) {
      if (request !== latest) return;
      status.dataset.state = 'failed';
      status.textContent = 'Font loading failed for ' + label + '. Live text may be fallback; use the static reference.';
    }
  };
}

const loadPairs = fontLoader(byId('pairFontStatus'));
const loadReading = fontLoader(byId('textFontStatus'));
pairWeight.addEventListener('change', () => {
  updatePairs();
  loadPairs(selectedWeight(pairWeight), 72);
});
textWeight.addEventListener('change', () => {
  updateReading();
  loadReading(selectedWeight(textWeight), Number(textSize.value));
});
textSize.addEventListener('change', updateSize);
words.addEventListener('input', updateText);
updatePairs();
updateReading();
updateText();
updateSize();
loadPairs(selectedWeight(pairWeight), 72);
loadReading(selectedWeight(textWeight), Number(textSize.value));
</script>
</body>
</html>
""")


def _features(variant):
    return ", ".join(f'"{tag}" {int(tag in _ACTIVE[variant])}' for tag in _TAGS)


def _summary(entry):
    return (f'{entry["style"]} · {entry["weight"]} — C: −{entry["tighter"]} for go / ge / gc; '
            f'B: −{entry["moderate"]} for other g advances, before the gj correction (font units; 2048/em).')


def _codepoint(char):
    return f'U+{ord(char):04X} {unicode_name(char, "UNNAMED")}'


def render(font_rules: str, config: dict) -> str:
    """Return HTML without file access or mutation of the supplied config.

    ``font_rules`` is trusted parent-supplied CSS: nine embedded SpacingProof
    WOFF2 faces (actual family Allo G Spacing Finish). Config contains ``weights``
    (weight, style, moderate, tighter, gj_correction), ``paragraphs`` (strings),
    and ``space_characters`` (actual encoded characters mapping to glyph space).
    Amounts come from compiled fonts; this renderer does not interpolate them.
    """
    if not isinstance(font_rules, str) or not font_rules.strip():
        raise ValueError("Expected trusted embedded font CSS")
    if not isinstance(config, dict) or not isinstance(config.get("weights"), list):
        raise TypeError("Expected a config with a weights list")
    fields = ("weight", "style", "moderate", "tighter", "gj_correction")
    weights = []
    for entry in config["weights"]:
        if not isinstance(entry, dict) or not set(fields) <= entry.keys():
            raise ValueError("Each weight needs weight, style, moderate, tighter and gj_correction")
        weight = entry["weight"]
        if isinstance(weight, bool) or not isinstance(weight, int) or weight not in _CORRECTIONS:
            raise ValueError("Weights must be integers 100 through 900 in steps of 100")
        if not isinstance(entry["style"], str) or not entry["style"].strip():
            raise ValueError("Each weight needs a nonempty style label")
        for field in ("moderate", "tighter"):
            amount = entry[field]
            if (isinstance(amount, bool) or not isinstance(amount, (int, float))
                    or not 0 < amount <= 2**53 - 1 or not isfinite(amount)):
                raise ValueError("Spacing reductions must be finite positive, JS-safe font-unit amounts")
        if entry["tighter"] != 2 * entry["moderate"]:
            raise ValueError("The tighter amount C must equal twice the moderate amount B")
        correction = entry["gj_correction"]
        if isinstance(correction, bool) or not isinstance(correction, int) or correction != _CORRECTIONS[weight]:
            raise ValueError("Expected gj corrections 0, 0, 0, 0, 0, 0, 8, 27, 40")
        normalized = {field: entry[field] for field in fields}
        # Keep static labels and JS number strings identical for amounts like 48.0.
        for field in ("moderate", "tighter"):
            if normalized[field] == int(normalized[field]):
                normalized[field] = int(normalized[field])
        weights.append(normalized)
    weights.sort(key=lambda entry: entry["weight"])
    if [entry["weight"] for entry in weights] != list(_CORRECTIONS):
        raise ValueError("Expected exactly nine distinct weights, 100 through 900")
    paragraphs = config.get("paragraphs")
    if not isinstance(paragraphs, list) or not paragraphs or not all(isinstance(text, str) for text in paragraphs):
        raise ValueError("Expected a nonempty paragraphs list of literal strings")
    spaces = config.get("space_characters")
    if (not isinstance(spaces, list) or not spaces
            or not all(isinstance(char, str) and len(char) == 1 and not 0xD800 <= ord(char) <= 0xDFFF for char in spaces)
            or len(set(spaces)) != len(spaces)):
        raise ValueError("Expected distinct single Unicode scalar space_characters")
    data = {"weights": weights, "paragraphs": list(paragraphs), "space_characters": list(spaces)}
    # Script data is not HTML: even closing script tags must remain inert text.
    config_json = (json.dumps(data, ensure_ascii=True, allow_nan=False)
                   .replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e"))
    text = escape("\n\n".join(paragraphs))
    sample_space = " " if " " in spaces else spaces[0]
    pair_columns = []
    for variant, heading, amount in (
        ("chosen", "Chosen · before", "gj correction: +0 font units · selected baseline."),
        ("refined", "Refined · after", "gj correction: +40 font units · ss15 only."),
    ):
        pair_columns.append(_PAIR_COLUMN.substitute(
            variant=variant, heading=heading, amount=amount, features=escape(_features(variant))))
    regular = weights[3]
    b = regular["moderate"]
    reading_columns = []
    for variant, heading, amount in (
        ("refined", "Refined · current word-space policy",
         f"Before space: −{b} (B); terminal g: −{b} (B). gj correction: +0 font units."),
        ("boundary", "Boundary trial · comparison only",
         f"Before space: −{b} +{b} = 0 (inherited); terminal g: −{b} (B). gj correction: +0 font units."),
    ):
        reading_columns.append(_READING_COLUMN.substitute(
            variant=variant, heading=heading, amount=amount, features=escape(_features(variant)),
            text=text, boundary_sample=escape("g" + sample_space + "g")))

    def options(selected):
        return "\n".join('<option value="{}"{}>{} · {}</option>'.format(
            entry["weight"], " selected" if entry["weight"] == selected else "",
            escape(entry["style"]), entry["weight"]) for entry in weights)

    return _PAGE.substitute(
        font_rules=font_rules, config_json=config_json, gaps_json=json.dumps(_GAPS),
        chosen_features=_features("chosen"), refined_features=_features("refined"),
        boundary_features=_features("boundary"), pair_options=options(900), text_options=options(400),
        pair_columns="\n".join(pair_columns), reading_columns="\n".join(reading_columns),
        pair_summary=escape(_summary(weights[8])), text_summary=escape(_summary(regular)),
        pair_gap=f"Sampled horizontal gj gap: {_GAPS[900][0]} → {_GAPS[900][1]} font units (chosen → refined).",
        default_text=text, boundary_scope=escape(
            "ss16 follows the glyph space, not a generic whitespace class. Encoded characters in scope: "
            + "; ".join(_codepoint(char) for char in spaces)
            + ". The fixed sample uses " + _codepoint(sample_space) + "."))
