"""Side-effect-free HTML renderer for the double-storey g spacing diagnostic."""

from html import escape
import json
from string import Template


_DEFAULT_TEXT = "ago going baggage\nA good beginning grows in the garden."

_COLUMN = Template(r"""
<article class="comparison-column" aria-labelledby="heading-$variant">
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
  <div><span class="font-sample adjustable boundary-text" data-variant="$variant">g g</span></div>
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
<title>Allo — double-storey g spacing comparison</title>
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
.controls {display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:20px; margin:20px 0}
.control {min-width:0}
label {display:block; font-weight:500; margin-bottom:6px}
select, textarea {width:100%; padding:10px; border:1px solid #888; border-radius:3px; background:#fff; color:#191919; font:inherit}
textarea {min-height:112px; resize:vertical}
input[type=range] {width:100%; min-height:32px; accent-color:#333; margin:0}
:focus-visible {outline:2px solid #191919; outline-offset:3px}
output {font-weight:400}
#fontStatus {min-height:1.6em}
#fontStatus[data-state=failed], #fontStatus[data-state=unavailable] {font-weight:600; color:#191919}
.scope-note {border-inline-start:2px solid #aaa; padding-inline-start:16px}
.comparison {display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:28px; margin:28px 0}
.comparison-column {min-width:0; border-top:1px solid #aaa; padding-top:16px}
.setting {margin:0 0 6px; min-height:3.2em}
.feature-flags {display:block; color:#595959; font-size:12px; overflow-wrap:anywhere}
.font-sample {font-family:SpacingProof,sans-serif; font-synthesis:none; font-weight:400; font-style:normal; font-kerning:normal; line-height:1.5; margin:6px 0 16px; overflow-x:auto}
.font-sample[data-variant=a] {font-feature-settings:"ss17" 0, "ss18" 0, "ss19" 0, "ss20" 0}
.font-sample[data-variant=b] {font-feature-settings:"ss17" 0, "ss18" 0, "ss19" 1, "ss20" 0}
.font-sample[data-variant=c] {font-feature-settings:"ss17" 0, "ss18" 0, "ss19" 0, "ss20" 1}
.adjustable {font-size:36px}
.custom-text {white-space:pre-wrap; overflow-wrap:anywhere; min-height:3em}
.boundary-text {display:inline-block; white-space:pre; border-inline-end:1px solid #999}
.reading {border-top:1px solid #ddd; margin-top:20px; padding-top:4px}
figure {margin:24px 0 32px}
.sheet {display:block; width:100%; height:auto; border-top:1px solid #ddd}
figcaption {margin-top:10px}
summary {cursor:pointer; padding:12px 0; font-weight:500}
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
  <p class="eyebrow">Spacing-only diagnostic · nine static weights</p>
  <h1>A double-storey g: three spacing choices</h1>
  <p><strong>A is study 02’s new double-storey g with its current, inherited spacing</strong> — not the original single-storey g. B reduces its advance moderately; C reduces it further. All three columns use the same embedded font and selected weight, with identical outlines.</p>
  <p class="note">No outlines or font <code>hmtx</code> metrics are changed by this spacing study. Previous studies and production fonts are unchanged. These optional GPOS features are diagnostic, not production <code>ss04</code>. The font defaults leave all four features off; this page enables one per comparison column. No font installation or network access is needed.</p>
</header>
<section aria-labelledby="live-title">
  <h2 id="live-title">Live comparison</h2>
  <div class="controls">
    <div class="control">
      <label for="weight">Weight</label>
      <select id="weight">$weight_options</select>
    </div>
    <div class="control">
      <label for="mode">Adjustment scope</label>
      <select id="mode" aria-describedby="modeExplanation">
        <option value="round" selected>Round followers only · go / ge / gc</option>
        <option value="all">All followers · stress test</option>
      </select>
    </div>
    <div class="control">
      <label for="size">Comparison size · <output id="sizeValue" for="size">36 px</output></label>
      <input id="size" type="range" min="12" max="72" step="1" value="36" aria-describedby="sizeHint">
    </div>
  </div>
  <p class="note" id="sizeHint">The slider changes your text and pair tests only. Reading samples stay at 24, 16 and 12 px. Evaluate live sizes at browser zoom 100%.</p>
  <p class="note" id="weightSummary">$weight_summary</p>
  <p class="note" id="fontStatus" role="status" aria-live="polite" aria-atomic="true" data-state="loading">Loading selected embedded weight…</p>
  <p class="scope-note" id="modeExplanation">Round mode changes the advance of g only before o, e or c (go / ge / gc): B uses ss19; C uses ss20. Other followers, spaces and terminal g keep inherited advances.</p>
  <p class="note"><strong>All-followers mode is a stress test, not a recommendation.</strong> Its SinglePos XAdvance reduction applies to every plain g, modelling a right-sidebearing reduction, including before spaces and at the end of text. In the measured all-followers C trial, gj overlaps at weights 700–900, and gy also overlaps at 900. Round mode leaves those pairs unchanged. Round mode is deliberately limited to go / ge / gc; neither mode is a complete spacing or kerning proposal.</p>
  <label for="words">Try your own text</label>
  <textarea id="words" rows="3" spellcheck="false" aria-describedby="textHint">$default_text</textarea>
  <p class="note" id="textHint">The same text appears in A, B and C. The preceding controls og / ag / ng inspect the left side of g; all mode still changes the final g advance. The thin rule after “g g” marks the text-run end, exposing the advance before a space and after the final g.</p>
  <noscript><p>JavaScript is needed for the live controls and font-loading status. Use the rendered sheets below for the static comparison.</p></noscript>
  <div class="comparison" id="comparison">$columns</div>
  <p class="note">The new g remains unhinted, as in study 02. Raster appearance depends on browser and platform; the live view and rendered sheets may differ. This page does not establish browser-rendering validation.</p>
</section>
<section aria-labelledby="sheets-title">
  <h2 id="sheets-title">Rendered reference sheets</h2>
  <p class="note">Size labels on the rendered sheets refer to their intrinsic layout sizes. These images scale to fit the window, so their displayed text is not necessarily at the labelled size. Live controls do not change the sheets. Use the live 24 / 16 / 12 px samples at browser zoom 100% for reading-size comparisons.</p>
  <figure>
    <a href="proof.svg"><img class="sheet" src="proof.svg" loading="lazy" alt="Rendered spacing comparison of A, B and C for the new double-storey g"></a>
    <figcaption>Spacing overview · <a href="proof.svg">SVG</a> / <a href="proof.png">PNG</a> · labels describe intrinsic sheet sizes.</figcaption>
  </figure>
  <details>
    <summary>All nine weights</summary>
    <figure>
      <a href="weights.svg"><img class="sheet" src="weights.svg" loading="lazy" alt="Rendered A, B and C spacing comparison across all nine weights, Thin through Black"></a>
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
  <p class="note"><a href="README.md">Build and scope notes</a> · <a href="validation.json">Build validation data</a> · <a href="../../../OFL.txt">SIL Open Font License 1.1</a></p>
</footer>
</main>
<script>
'use strict';
const config = $config_json;
const weight = document.getElementById('weight');
const mode = document.getElementById('mode');
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
  const active = variant === 'a' ? null :
    (mode.value === 'round' ? {b: 'ss19', c: 'ss20'} : {b: 'ss17', c: 'ss18'})[variant];
  return tags.map(tag => '"' + tag + '" ' + (tag === active ? 1 : 0)).join(', ');
}

function updateSettings() {
  const entry = selectedWeight();
  const round = mode.value === 'round';
  samples.forEach(sample => {
    sample.style.fontWeight = String(entry.weight);
    sample.style.fontFeatureSettings = featureSettings(sample.dataset.variant);
  });
  document.getElementById('weightSummary').textContent = entry.style + ' · ' + entry.weight +
    ' — B: −' + entry.moderate + '; C: −' + entry.tighter + ' font units.';
  document.getElementById('amount-a').textContent = '0 font units · inherited spacing; all four features off';
  document.getElementById('amount-b').textContent = '−' + entry.moderate + ' font units · ' +
    (round ? 'go / ge / gc only · ss19' : 'every plain g · ss17');
  document.getElementById('amount-c').textContent = '−' + entry.tighter + ' font units · ' +
    (round ? 'go / ge / gc only · ss20' : 'every plain g · ss18');
  ['a', 'b', 'c'].forEach(variant => {
    document.getElementById('features-' + variant).textContent = featureSettings(variant);
  });
  document.getElementById('modeExplanation').textContent = round
    ? 'Round mode changes the advance of g only before o, e or c (go / ge / gc): B uses ss19; C uses ss20. Other followers, spaces and terminal g keep inherited advances.'
    : 'All-followers mode is a stress test, not a recommendation: B uses ss17; C uses ss18. SinglePos XAdvance reduces every plain g advance, including before spaces and at text end. It can over-tighten descenders and punctuation; outlines and hmtx stay unchanged.';
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
    if (faces.length === 0) throw new Error('No matching embedded face');
    if (request !== fontLoadRequest) return;
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
mode.addEventListener('change', updateSettings);
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

    The caller supplies the actual compiled font-unit amounts. No interpolation,
    font generation, file access, or mutation of the caller's config happens here.
    """
    weights = sorted(config["weights"], key=lambda entry: entry["weight"])
    if [entry["weight"] for entry in weights] != list(range(100, 901, 100)):
        raise ValueError("Expected exactly nine weights, 100 through 900")
    for entry in weights:
        if not isinstance(entry["style"], str):
            raise ValueError("Each weight needs a style label")
        for field in ("moderate", "tighter"):
            amount = entry[field]
            if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount <= 0:
                raise ValueError("Spacing reductions must be positive font-unit amounts")
        if entry["tighter"] != 2 * entry["moderate"]:
            raise ValueError("The tighter amount must be twice the moderate amount")
    # JSON is embedded in a script, not an HTML attribute. Escape HTML delimiters
    # so even a style label containing a closing script tag remains inert data.
    config_json = (json.dumps(config, ensure_ascii=True, allow_nan=False)
                   .replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e"))
    options = []
    for entry in weights:
        selected = " selected" if entry["weight"] == 400 else ""
        options.append('<option value="{}"{}>{} · {}</option>'.format(
            entry["weight"], selected, escape(entry["style"]), entry["weight"]))
    regular = next(entry for entry in weights if entry["weight"] == 400)
    columns = []
    for variant, heading, amount, active in (
        ("a", "A · current / inherited", "0 font units · inherited spacing; all four features off", None),
        ("b", "B · moderately tighter", f'−{regular["moderate"]} font units · go / ge / gc only · ss19', "ss19"),
        ("c", "C · tighter still", f'−{regular["tighter"]} font units · go / ge / gc only · ss20', "ss20"),
    ):
        features = ", ".join(f'"{tag}" {int(tag == active)}' for tag in ("ss17", "ss18", "ss19", "ss20"))
        columns.append(_COLUMN.substitute(
            variant=variant, heading=heading, amount=amount,
            features=escape(features), text=escape(_DEFAULT_TEXT)))
    summary = (f'{regular["style"]} · 400 — B: −{regular["moderate"]}; '
               f'C: −{regular["tighter"]} font units.')
    return _PAGE.substitute(
        font_rules=font_rules, config_json=config_json,
        weight_options="\n".join(options), columns="\n".join(columns),
        weight_summary=escape(summary), default_text=escape(_DEFAULT_TEXT))
