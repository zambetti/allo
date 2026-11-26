# Double-storey g — authoring sources

The optional `ss04` family is implemented in the current UFO sources and available in new builds. It substitutes
`g`, `gcircumflex`, `gbreve`, `gdotaccent` and `gcommaaccent` with their unencoded `.ss04` counterparts. The original
single-storey family remains the default; `ss01` is independent. Untouched shipped fonts, npm packages and upstream
releases do not acquire the feature. See the [root README](../../../README.md#opentype-features) for use and custom builds.

## Baseline and provenance

These three canonical controls carry the approved upright **Text / Friendly** baseline (`opsz` 14, `ROND` 50).
They are byte-identical copies of the weight-study drawings, not inputs read from the historical proofs at build time:

| Control | Design weight | Historical source |
|---|---:|---|
| [Thin.glif](Thin.glif) | 100 | [Weight-study Thin](../../../documentation/proofs/double-storey-g-weights/masters/Thin.glif) |
| [Regular.glif](Regular.glif) | 400 | [Weight-study Regular](../../../documentation/proofs/double-storey-g-weights/masters/Regular.glif) |
| [Black.glif](Black.glif) | 900 | [Weight-study Black](../../../documentation/proofs/double-storey-g-weights/masters/Black.glif) |

Regular also preserves the [original approved drawing](../../../documentation/proofs/double-storey-g/g.ss04.glif).
The design has a compact upper bowl, short rounded ear, wider closed lower loop and left-hand link. Thin and Black
are independent drawings, not scaled Regular outlines; the two bowls deliberately use a different stroke balance
from the existing `o`. Corresponding points support interpolation between the controls.

The adopted spacing baseline is [C before rounds, B elsewhere](../../../documentation/proofs/double-storey-g-selected-spacing/README.md),
with the [heavy `gj` refinement and retained word-space policy](../../../documentation/proofs/double-storey-g-spacing-finish/README.md),
then the [Tighter, ng-only selection](../../../documentation/proofs/double-storey-g-incoming-spacing/README.md#review-outcome).
The latter preference was reviewed at Regular; it does not establish separate visual approval at every weight.
[Text-coverage study 07](../../../documentation/proofs/double-storey-g-text-coverage/README.md#confirmed-integration-direction)
records the independent, opt-in feature direction. Historical READMEs retain their study-time scope and are not
statements of the current implementation.

On 2026-11-26, the fork maintainer reviewed the generated `build/custom/variable-proof.html`, found the result
visually satisfactory, and approved the implementation for commit. This records acceptance of the interactive
proof, not a claim that every axis coordinate, accent combination or static oblique was individually reviewed.
Optical-size/roundness extensions, accent-family expansion and derived obliques extend beyond the original
plain-g controls; geometry, shaping and browser checks remain separate from aesthetic approval.

## Regeneration is an authoring operation

[`build.py`](../../../build.py) compiles the saved, editable UFOs directly. Neither a normal build nor `--custom`
needs this generator or the historical proof builders. Only when intentionally regenerating the alternate sources,
run from the repository root:

```sh
.venv/bin/python alternate_g.py --write
```

**This explicitly replaces existing alternate drawings and owned layout metadata.**
[`alternate_g.py`](../../../alternate_g.py) rewrites `g.ss04`, `gcircumflex.ss04`, `gbreve.ss04`, `gdotaccent.ss04` and
`gcommaaccent.ss04` in all **48 full masters** referenced by [`sources/Allo.designspace`](../../Allo.designspace)
and all **18 static UFOs** in [`sources/static/`](../../static/), including obliques. Manual edits to those alternates
are overwritten; retain intended changes in the controls or authoring logic before regenerating. Existing sparse
layers are not regenerated, and unrelated GLIFs are not rewritten.

The narrow writer updates the five GLIFs, `glyphs/contents.plist`, `features.fea`, `groups.plist`, `kerning.plist` and
`lib.plist`. [`g_features.py`](../../../g_features.py) rebuilds its marked `# BEGIN g_features ss04` / `# END g_features ss04`
block, `public.kern1.g.ss04` / `public.kern2.g.ss04` groups and associated pairs, glyph-order entries and base-glyph
categories. It completes `@NOT_SPACE`, `@NOT_BRACKET` and the inline lowercase `calt` guard so alternates retain the
existing contextual behavior. Unowned feature/kerning data is preserved; conflicting unowned `ss04` code or alternate
kerning memberships are rejected. Metadata files may be serialized again; original glyph drawings stay untouched.

## Geometry across the axes

- **Weight:** corresponding outline points and anchors interpolate piecewise-linearly through design weights
  100 → 400 → 900. Static user weights first use the mapping in `sources/Allo.designspace` (for example, user 600
  maps to design 580). The additional full master at design 580 is generated from the same control interpolation.
- **Optical size:** the reference is `sources/masters/Allo-opsz14-wght{weight}-ROND50.ufo` at the matching design
  weight. The native `g` supplies width and upper/lower vertical proportions; native `o` stroke changes guide counter
  compensation while retaining the control drawing's two-bowl stroke allocation. Text / Friendly is the fixed point,
  rather than Display being a uniformly scaled Regular. Anchor heights follow the native `g` anchor changes.
- **Roundness:** after that adaptation, selected short corners and terminal caps change about their tangent
  intersections, retaining point correspondence even at Sharp. Friendly preserves the control corner treatment.
  The corner operation itself leaves bowl/counter contours alone; native `g`/`o` differences can also affect the
  preceding adaptation. This is not blanket rounding of the outline.
- **Small:** `opsz` 9 keeps the same-roundness Text shape with the exact spacing-only shift from
  [`release.json`](../../../release.json): currently +17 units to outlines/anchors and +34 to advance width.
- **Static precision:** upright static outline coordinates are rounded with `otRound` to retain the historical
  Text / Friendly proof drawings. Full masters retain fractional coordinates for compatible variable compilation;
  variable outlines and metrics need not be bit-identical to separately compiled static fonts.

## Spacing and feature ownership

Spacing is computed in **mapped design-weight coordinates**, not directly from user `wght` or OS/2 weight metadata.
All amounts below are font units (2048 units/em). Let `B(d)` be endpoint-clamped, piecewise-linear interpolation
through `(100, 40)`, `(400, 48)`, `(900, 64)`, and `t = clamp((d - 580) / 320, 0, 1)`.

| Quantity | Static sources | Variable master model |
|---|---|---|
| General reduction `b` | `otRound(B(d))` | `B(d)` without static rounding |
| Incoming n-family tightening | `2 * otRound(b / 2)` | Linear samples `(100, 40)`, `(400, 48)`, `(580, 54)`, `(900, 64)` |
| Heavy j-family opening | `otRound(40 * t² * (3 - 2*t))` | `40 * t`, interpolated from master values |

Each alternate's advance is its original counterpart's advance **minus `b`**. Kerning inherits the original
family's resolved pairs and exceptions, then adds:

- Another `−b` after alternate g before actual `o`/`e`/`c` derivatives, including `ø` but excluding `œ`: total
  tightening is `2b` (the selected C), with existing kerning still active.
- The incoming tightening only from the `n` family into alternate g, not a broad `n/h/m/u` stem class.
- The positive heavy-weight opening before `j`, `jdotless` and `jcircumflex`.

The `o`/`e`/`c` and `n` families are determined from Unicode decomposition and compatible component ancestry, not
name prefixes or broad existing kerning groups. Supported accented g alternates participate in the same policy. The general width
reduction applies at spaces, punctuation and run ends; no word-space restoration is adopted. Turning `kern` off
removes pair adjustments, **not** the alternate's narrower advance. No historical `ss11`–`ss20` trial switches are
needed: `ss04` selects the glyphs, and normal `kern` supplies their pair positioning.

The variable model samples the master graph rather than reproducing every rounded static value or the static
smoothstep `gj` curve. Small intermediate differences are intentional; do not force variable results to be exact
static-proof copies. The validator distinguishes these cases.

## Accents and oblique anchors

Upright composites reuse the existing `circumflexcomb`, `brevecomb`, `dotaccentcomb` and `commaaccentrotate.cn`
components. They replace the base with `g.ss04`, shift the mark by the new-versus-old `top` anchor delta and update
attachment anchors. Each retains any fractional width difference from its original accented counterpart. `cross`
and `topr`, where present, follow the alternate's horizontal top-anchor displacement.

`gcommaaccent.ss04` uses the existing **rotated comma above**, not a new mark below. Its outgoing `top` anchor is
placed above that comma with quantization clearance, so a following combining mark stacks above it. The original
marks and default-family anchors are not changed. The existing mark system's limits are retained: for example,
repeated dot-below marks attach at the same bottom position, as in the release, rather than stacking downward.

Oblique alternates are derived from the corresponding upright statics: composites are decomposed and real contours
are sheared by the UFO's italic angle (currently 9° forward), about half the upright x-height. Advances are retained.
Because existing mark attachment anchors are unsheared, anchors use a **relative attachment model**, not the outline's
absolute shear: with `s = tan(9°)`, a `top` anchor receives `s * (y - reference_top)` in x, where `reference_top` is the
upright plain alternate's top-anchor y; a `bottom` anchor receives `s * y`. Other anchor coordinates are retained.
This accounts for stacked marks without shearing their attachment twice. These are static oblique glyphs, not a
`slnt` axis or browser-synthesized slant.

## Validation

Use the [root regression-test command](../../../README.md#checks) from the repository root. Besides the build Python
dependencies and `hb-shape` on `PATH`, its fixtures include the shipped fonts and historical weight/incoming-study
fonts. Tests use in-memory or temporary UFOs/fonts; they do not regenerate production sources.

After a complete custom build has finished, run:

```sh
.venv/bin/python -B validate_g.py --output build/g-integration/validation.json
```

[`validate_g.py`](../../../validate_g.py) requires all 39 custom binaries under `build/custom/fonts/`, corresponding
shipped references under `fonts/`, the study fonts in
`documentation/proofs/double-storey-g-incoming-spacing/fonts/`, and HarfBuzz's `hb-shape` on `PATH`. It rebuilds nothing;
missing fonts or `ss04` are failures, not skips. WOFF2 decoding uses temporary files, and the explicitly requested JSON
report is its only persistent output. Do not run it against a build still being written.

Checks cover default/release preservation, feature independence, alternate spacing, composed/decomposed accents,
absolute mark attachment, counter containment at finite axis samples and desktop/web payload consistency. Historical
proof comparisons apply to upright Text / Friendly plain-g drawings and positioning, not proof accents as an
integration oracle. Static comparisons are exact; variable positioning compares changes against each font's own
release baseline, accounting for the different spacing models and independent width/kerning rounding.

For real-browser controls and offline loading, use Node.js with an existing Playwright package and Chromium runtime:

```sh
node tests/test_variable_proof_browser.js \
  --font=build/custom/fonts/webfonts/AlloCustomVariable.woff2
```

If Node cannot resolve `playwright`, pass its installed package directory as the first positional argument; the
Python Playwright installation's `driver/package` directory also works. Optional `--executable=` selects an installed
Chromium executable. The [test header](../../../tests/test_variable_proof_browser.js) documents these arguments.
Without `--font`, the test uses the custom WOFF2 if present, otherwise the shipped font; specify the custom file as
above to avoid silently testing a font without `ss04`. It uses the existing `.venv`, installs nothing and removes its
temporary HTML on exit without changing build or proof artifacts. These are browser-control checks, not glyph-design
review. Consult the actual test output and current validation report for results.
