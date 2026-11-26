"""Side-effect-free HTML renderer for selected double-storey g spacing (study 04)."""

from html import escape
import json
from math import isfinite
from string import Template


_DEFAULT_TEXT = "ago going baggage\nA good beginning grows in the garden."

_COLUMN = Template(r"""
<article class="comparison-column" data-variant="$variant" aria-labelledby="heading-$variant">
  <h3 id="heading-$variant">$heading</h3>
  <p class="setting" id="amount-$variant">$amount</p>
  <code class="feature-flags" id="features-$variant">$features</code>
  <h4>Your text</h4>
  <p class="font-sample custom-text adjustable" data-variant="$variant">$text</p>
  <h4>Round followers</h4>
  <p class="font-sample adjustable" data-variant="$variant">go ge gc</p>
  <h4>Other followers</h4>
  <p class="font-sample adjustable" data-variant="$variant">ga gn gr</p>
  <h4>Descender guards</h4>
  <p class="font-sample adjustable" data-variant="$variant">gg gy gj</p>
  <h4>Punctuation guards</h4>
  <p class="font-sample adjustable" data-variant="$variant">g. g, g: g; g) g] g!</p>
  <h4>Preceding controls</h4>
  <p class="font-sample adjustable" data-variant="$variant">og ag ng</p>
  <h4>Before a space / at text end</h4>
  <div><span class="font-sample adjustable boundary-text" data-variant="$variant" aria-describedby="boundaryNote">g g</span></div>
  <div class="reading">
    <h4>Live reading · 24 px</h4>
    <p class="font-sample reading-text" data-variant="$variant" style="font-size:24px">ago going baggage</p>
    <h4>Live reading · 16 px</h4>
    <p class="font-sample reading-text" data-variant="$variant" style="font-size:16px">A good beginning grows in the garden.</p>
    <h4>Live reading · 12 px</h4>
    <p class="font-sample reading-text" data-variant="$variant" style="font-size:12px">Going again, gathering baggage, belonging.</p>
  </div>
</article>
""")

_PAGE = Template(r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Allo — selected double-storey g spacing · study 04</title>
<style>
$font_rules
:root {color-scheme:light}
* {box-sizing:border-box}
body {margin:0; background:#fff; color:#191919; font:16px/1.6 system-ui,sans-serif}
main {max-width:1600px; margin:auto; padding:32px clamp(16px,4vw,64px) 56px}
h1 {font-size:clamp(26px,4vw,38px); line-height:1.2; font-weight:500; margin:8px 0 20px}
h2 {font-size:20px; font-weight:500; margin:28px 0 12px}
h3 {font-size:18px; font-weight:600; margin:0 0 8px}
h4 {font-size:13px; color:#595959; font-weight:500; margin:20px 0 6px}
p {max-width:95ch}
a {color:inherit; text-underline-offset:3px}
a:hover {text-decoration-thickness:2px}
.note, figcaption, .setting {font-size:14px; color:#595959}
.eyebrow {font-size:13px; color:#595959; letter-spacing:.05em; text-transform:uppercase}
.controls {display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:20px; margin:20px 0}
.control {min-width:0}
label {display:block; font-weight:500; margin-bottom:6px}
select, textarea {width:100%; padding:10px; border:1px solid #888; border-radius:3px; background:#fff; color:#191919; font:inherit}
textarea {min-height:112px; resize:vertical}
input[type=range] {width:100%; min-height:32px; accent-color:#333; margin:0}
:focus-visible {outline:2px solid #191919; outline-offset:3px}
output {font-weight:400}
#fontStatus {min-height:1.6em}
#fontStatus[data-state=failed], #fontStatus[data-state=unavailable] {font-weight:600; color:#191919}
.selection-note {border-inline-start:2px solid #aaa; padding-inline-start:16px}
.comparison {display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:28px; margin:28px 0}
.comparison-column {min-width:0; border-top:1px solid #aaa; padding-top:16px}
.setting {margin:0 0 6px; min-height:3.2em}
.feature-flags {display:block; color:#595959; font-size:12px; overflow-wrap:anywhere}
.font-sample {font-family:SpacingProof,sans-serif; font-synthesis:none; font-weight:400; font-style:normal; font-kerning:normal; line-height:1.5; margin:6px 0 16px; overflow-x:auto}
.font-sample[data-variant=a] {font-feature-settings:"ss17" 0, "ss18" 0, "ss19" 0, "ss20" 0}
.font-sample[data-variant=b] {font-feature-settings:"ss17" 0, "ss18" 0, "ss19" 0, "ss20" 1}
.font-sample[data-variant=c] {font-feature-settings:"ss17" 1, "ss18" 0, "ss19" 1, "ss20" 0}
.adjustable {font-size:36px}
.custom-text {white-space:pre-wrap; overflow-wrap:anywhere; min-height:3em}
.boundary-text {display:inline-block; white-space:pre; border-inline-end:1px solid #999}
.reading {border-top:1px solid #ddd; margin-top:20px; padding-top:4px}
figure {margin:24px 0 32px}
.sheet {display:block; width:100%; height:auto; border-top:1px solid #ddd}
figcaption {margin-top:10px}
summary {cursor:pointer; padding:12px 0; font-weight:500}
table {border-collapse:collapse; font-size:14px; font-variant-numeric:tabular-nums}
caption {text-align:start; margin-bottom:8px}
th, td {text-align:start; padding:6px 12px; border-bottom:1px solid #ddd}
footer {border-top:1px solid #ddd; margin-top:32px; padding-top:12px}
@media (max-width:850px) {
  .controls, .comparison {grid-template-columns:1fr}
  .comparison {gap:36px}
  .setting {min-height:0}
}
</style>
</head>
<body>
<main>
<header>
  <p class="eyebrow">Selected spacing · study 04 · nine static weights · proof only</p>
  <h1>A double-storey g: the selected spacing</h1>
  <p><strong>The user selected study 03’s C amount for round followers go / ge / gc and B for all other plain g advances.</strong> Compare inherited spacing, the prior C-for-rounds-only setting, and the selected combination. These are comparison columns, not the old A/B/C amount labels: B and C here name the study 03 reductions.</p>
  <p class="note" id="preservationNote">All three columns reuse the study 03 fonts unchanged, at the same selected weight and with identical outlines. Inherited means study 02’s double-storey g spacing, not the original single-storey g. No outlines or font <code>hmtx</code> metrics are edited. Previous proof directories and production fonts remain unchanged. The combined optional GPOS settings are proof-only, not production integration or production <code>ss04</code>. All four trial features remain off by default in the fonts. Nine embedded WOFF2 faces mean no font installation, server or network access is needed.</p>
</header>
<section aria-labelledby="live-title">
  <h2 id="live-title">Live comparison</h2>
  <div class="controls">
    <div class="control">
      <label for="weight">Weight</label>
      <select id="weight">$weight_options</select>
    </div>

    <div class="control">
      <label for="size">Comparison size · <output id="sizeValue" for="size">36 px</output></label>
      <input id="size" type="range" min="12" max="72" step="1" value="36" aria-describedby="sizeHint">
    </div>
  </div>
  <p class="note" id="sizeHint">The slider changes your text and pair tests only. Reading samples stay at 24, 16 and 12 px. Evaluate live sizes at browser zoom 100%.</p>
  <p class="note" id="weightSummary">$weight_summary</p>
  <p class="note" id="fontStatus" role="status" aria-live="polite" aria-atomic="true" data-state="loading">Loading selected embedded weight…</p>
  <p class="selection-note" id="selectionExplanation">The columns are fixed. Inherited disables all four trial features. C for rounds only enables ss20 alone. Selected uses ss17=1, ss18=0, ss19=1, ss20=0: B on every plain g advance plus another B only before o / e / c, so B + B = C for go / ge / gc. It does not use ss17 + ss20, which would give B + C = 3B and over-tighten the rounds. Existing kerning stays active.</p>
  <p class="note" id="boundaryNote"><strong>The selected setting inherits blanket-B effects before spaces and on terminal g.</strong> For each isolated preceding control og / ag / ng, glyph origins are unchanged, but its terminal g advance changes by −B. In a combined text run, that advance change shifts later text. The thin rule after “g g” marks the text-run end: both the advance before the space and the final g advance are reduced. Inherited and C for rounds only leave these boundary advances unchanged.</p>
  <p class="selection-note" id="clearanceNote"><strong>Keep gj under review:</strong> in the selected setting its sampled horizontal gap is 28.6425 font units at 800 and 8.3873 at 900, with no computed overlap. No computed overlap does not guarantee comfortable spacing; this sampled gap is not an exact Euclidean distance. No exceptions have been added for gj, spaces, terminal g or other followers. See <a href="clearances.json">clearance data and measurement caveats</a>.</p>
  <p class="note">This proof covers plain lowercase g and the unaccented round followers o / e / c only. It is not a complete kerning class, accent-spacing proposal or variable-font integration.</p>
  <label for="words">Try your own text</label>
  <textarea id="words" rows="3" spellcheck="false" aria-describedby="textHint">$default_text</textarea>
  <p class="note" id="textHint">Your text appears literally in all three comparison columns. The pair tests, boundary marker and reading samples remain independent of this editable text.</p>
  <noscript><p>JavaScript is needed for the live controls and font-loading status. Use the rendered sheets below for the static comparison.</p></noscript>
  <div class="comparison" id="comparison">$columns</div>
  <p class="note">The new g remains unhinted, as in study 02. Raster appearance depends on browser and platform; the live view and rendered sheets may differ. The UI checks are mocked-DOM tests, not browser tests; this page does not establish browser-rendering validation.</p>
  <details>
    <summary>Study 03 reduction amounts · all nine weights</summary>
    <table>
      <caption>Positive tightening magnitudes in font units (2048 units/em); GPOS advance changes are negative. C = 2B. B/C name amounts, not comparison columns.</caption>
      <thead><tr><th scope="col">Weight</th><th scope="col">Style</th><th scope="col">B reduction</th><th scope="col">C reduction</th></tr></thead>
      <tbody>$amount_rows</tbody>
    </table>
  </details>
</section>
<section aria-labelledby="sheets-title">
  <h2 id="sheets-title">Rendered reference sheets</h2>
  <p class="note">Size labels on the rendered sheets refer to their intrinsic layout sizes. These images scale to fit the window, so their displayed text is not necessarily at the labelled size. Live controls do not change the sheets. Use the live 24 / 16 / 12 px samples at browser zoom 100% for reading-size comparisons.</p>
  <figure>
    <a href="proof.svg"><img class="sheet" src="proof.svg" loading="lazy" alt="Rendered double-storey g comparison: inherited, C for rounds only, and selected C rounds plus B others"></a>
    <figcaption>Spacing overview · <a href="proof.svg">SVG</a> / <a href="proof.png">PNG</a> · labels describe intrinsic sheet sizes.</figcaption>
  </figure>
  <details>
    <summary>All nine weights</summary>
    <figure>
      <a href="weights.svg"><img class="sheet" src="weights.svg" loading="lazy" alt="Inherited, C for rounds only, and selected spacing across all nine weights, Thin through Black"></a>
      <figcaption>Weight ladder · <a href="weights.svg">SVG</a> / <a href="weights.png">PNG</a> · labels describe intrinsic sheet sizes.</figcaption>
    </figure>
  </details>
  <details>
    <summary>Pairs and guards</summary>
    <figure>
      <a href="pairs.svg"><img class="sheet" src="pairs.svg" loading="lazy" alt="Rendered spacing pairs, other followers, descender and punctuation guards, and preceding controls"></a>
      <figcaption>Pair sheet · <a href="pairs.svg">SVG</a> / <a href="pairs.png">PNG</a> · labels describe intrinsic sheet sizes.</figcaption>
    </figure>
  </details>
</section>
<footer>
  <p class="note"><a href="README.md">Build and scope notes</a> · <a href="validation.json">Build validation data</a> · <a href="clearances.json">Clearances and caveats</a> · <a href="../double-storey-g-spacing/proof.html">Previous spacing proof · study 03</a> · <a href="../../../OFL.txt">SIL Open Font License 1.1</a></p>
</footer>
</main>
<script>
'use strict';
const config = $config_json;
const weight = document.getElementById('weight');

const size = document.getElementById('size');
const words = document.getElementById('words');
const status = document.getElementById('fontStatus');
const samples = Array.from(document.querySelectorAll('.font-sample'));
const tags = ['ss17', 'ss18', 'ss19', 'ss20'];
let fontLoadRequest = 0;

function selectedWeight() {
  return config.weights.find(entry => entry.weight === Number(weight.value));
}

function featureSettings(variant) {
  const active = {a: [], b: ['ss20'], c: ['ss17', 'ss19']}[variant];
  return tags.map(tag => '"' + tag + '" ' + (active.includes(tag) ? 1 : 0)).join(', ');
}

function updateSettings() {
  const entry = selectedWeight();

  samples.forEach(sample => {
    sample.style.fontWeight = String(entry.weight);
    sample.style.fontFeatureSettings = featureSettings(sample.dataset.variant);
  });
  document.getElementById('weightSummary').textContent = entry.style + ' · ' + entry.weight +
    ' — study 03 amounts: B: −' + entry.moderate + '; C: −' + entry.tighter + ' font units (2048 units/em).';
  document.getElementById('amount-a').textContent = '0 font units · inherited spacing; all four features off';
  document.getElementById('amount-b').textContent = 'C: −' + entry.tighter +
    ' font units · go / ge / gc only; other advances inherited · ss20';
  document.getElementById('amount-c').textContent = 'C: −' + entry.tighter +
    ' font units · go / ge / gc; B: −' + entry.moderate +
    ' font units · all other plain g advances, including before spaces and terminal g · ss17 + ss19';
  ['a', 'b', 'c'].forEach(variant => {
    document.getElementById('features-' + variant).textContent = featureSettings(variant);
  });

}

function updateText() {
  document.querySelectorAll('.custom-text').forEach(sample => {
    sample.textContent = words.value;
  });
}

function updateSize() {
  document.querySelectorAll('.adjustable').forEach(sample => {
    sample.style.fontSize = size.value + 'px';
  });
  document.getElementById('sizeValue').textContent = size.value + ' px';
}

async function loadSelectedWeight() {
  const request = ++fontLoadRequest;
  const entry = selectedWeight();
  const label = entry.style + ' (' + entry.weight + ')';
  status.dataset.state = 'loading';
  status.textContent = 'Loading embedded ' + label + '…';
  if (!document.fonts || typeof document.fonts.load !== 'function') {
    status.dataset.state = 'unavailable';
    status.textContent = 'Font loading cannot be verified in this browser. Live text may be fallback; use the rendered sheets below.';
    return;
  }
  try {
    const faces = await document.fonts.load(entry.weight + ' 36px "SpacingProof"', 'g ogeca');
    if (request !== fontLoadRequest) return;
    if (faces.length === 0) throw new Error('No matching embedded face');
    status.dataset.state = 'ready';
    status.textContent = 'Embedded ' + label + ' loaded.';
  } catch (error) {
    if (request !== fontLoadRequest) return;
    status.dataset.state = 'failed';
    status.textContent = 'Font loading failed for ' + label + '. Live text may be fallback; use the rendered sheets below.';
  }
}

weight.addEventListener('change', () => {
  updateSettings();
  loadSelectedWeight();
});

words.addEventListener('input', updateText);
size.addEventListener('input', updateSize);
updateText();
updateSize();
updateSettings();
loadSelectedWeight();
</script>
</body>
</html>
""")


def render(font_rules: str, config: dict) -> str:
    """Return standalone HTML; ``font_rules`` is trusted, embedded @font-face CSS.

    ``config["weights"]`` contains nine dictionaries with ``weight``, ``style``,
    ``moderate`` and ``tighter`` fields: weights 100..900, with C = 2B as in study 03.
    The caller supplies nine embedded SpacingProof WOFF2 @font-face rules and
    the actual compiled font-unit amounts. No interpolation, font generation,
    file access, or mutation of the caller's config happens here. The template
    stays in Python to avoid editor HTML auto-closing changes to the script.
    """
    if not isinstance(config, dict) or not isinstance(config.get("weights"), list):
        raise ValueError("Expected a config with a weights list")
    for entry in config["weights"]:
        if not isinstance(entry, dict) or not {"weight", "style", "moderate", "tighter"} <= entry.keys():
            raise ValueError("Each weight needs weight, style, moderate and tighter fields")
        if isinstance(entry["weight"], bool) or not isinstance(entry["weight"], int):
            raise ValueError("Weights must be integers")
        if not isinstance(entry["style"], str):
            raise ValueError("Each weight needs a style label")
        for field in ("moderate", "tighter"):
            amount = entry[field]
            if (isinstance(amount, bool) or not isinstance(amount, (int, float))
                    or amount <= 0 or (isinstance(amount, float) and not isfinite(amount))):
                raise ValueError("Spacing reductions must be finite positive font-unit amounts")
        if entry["tighter"] != 2 * entry["moderate"]:
            raise ValueError("The tighter amount must be twice the moderate amount")
    weights = sorted(config["weights"], key=lambda entry: entry["weight"])
    if [entry["weight"] for entry in weights] != list(range(100, 901, 100)):
        raise ValueError("Expected exactly nine weights, 100 through 900")
    # JSON is embedded in a script, not an HTML attribute. Escape HTML delimiters
    # so even a style label containing a closing script tag remains inert data.
    config_json = (json.dumps(config, ensure_ascii=True, allow_nan=False)
                   .replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e"))
    options = []
    amount_rows = []
    for entry in weights:
        selected = " selected" if entry["weight"] == 400 else ""
        options.append('<option value="{}"{}>{} · {}</option>'.format(
            entry["weight"], selected, escape(entry["style"]), entry["weight"]))
        amount_rows.append('<tr data-weight="{}"><th scope="row">{}</th><td>{}</td><td>{}</td><td>{}</td></tr>'.format(
            entry["weight"], entry["weight"], escape(entry["style"]), entry["moderate"], entry["tighter"]))
    regular = next(entry for entry in weights if entry["weight"] == 400)
    columns = []
    for variant, heading, amount, active in (
        ("a", "Inherited", "0 font units · inherited spacing; all four features off", ()),
        ("b", "C for rounds only",
         f'C: −{regular["tighter"]} font units · go / ge / gc only; other advances inherited · ss20', ("ss20",)),
        ("c", "Selected: C rounds + B others",
         f'C: −{regular["tighter"]} font units · go / ge / gc; B: −{regular["moderate"]} '
         'font units · all other plain g advances, including before spaces and terminal g · ss17 + ss19',
         ("ss17", "ss19")),
    ):
        features = ", ".join(f'"{tag}" {int(tag in active)}' for tag in ("ss17", "ss18", "ss19", "ss20"))
        columns.append(_COLUMN.substitute(
            variant=variant, heading=heading, amount=amount,
            features=escape(features), text=escape(_DEFAULT_TEXT)))
    summary = (f'{regular["style"]} · 400 — study 03 amounts: B: −{regular["moderate"]}; '
               f'C: −{regular["tighter"]} font units (2048 units/em).')
    return _PAGE.substitute(
        font_rules=font_rules, config_json=config_json,
        weight_options="\n".join(options), columns="\n".join(columns),
        weight_summary=escape(summary), amount_rows="\n".join(amount_rows), default_text=escape(_DEFAULT_TEXT))
