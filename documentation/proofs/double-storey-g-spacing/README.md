# Double-storey g — spacing study 03

**Status: spacing-only comparison, awaiting visual review.** All nine [study 02](../double-storey-g-weights/README.md) drawings are unchanged. No spacing has been selected for production, and neither production files nor the two previous studies are modified.

## Review

Open [proof.html](proof.html) in a browser. It embeds all nine proof fonts, so no installation, server or network access is needed. The page starts at Regular / 400 in **round-followers mode** and compares:

- **A — current:** study 02's double-storey `g` with inherited spacing, not the original single-storey `g`.
- **B — moderately tighter:** a small reduction of the advance after `g`.
- **C — tighter still:** twice B's reduction.

Select a weight, enter your own text, and adjust the comparison size. The reading samples stay at 24, 16 and 12 px. Use browser zoom at 100% for live reading-size evaluation. The page reports whether the selected embedded font loaded; fallback text is not a valid font comparison.

The **Adjustment scope** control distinguishes two experiments:

- **Round followers only:** tighten only `go`, `ge` and `gc`. Other followers, spaces and terminal `g` keep their inherited advances. This is the default comparison.
- **All followers:** reduce every plain `g` advance, including before spaces and at the end of text. This models a right-sidebearing reduction and is a diagnostic stress test, **not a recommendation**. It produces actual outline overlaps in some heavier-weight C settings.

The page includes other followers (`ga gn gr`), descenders (`gg gy gj`), punctuation, preceding-letter controls (`og ag ng`), and word-boundary tests. The thin rule after `g g` marks the text-run end so that otherwise invisible terminal-advance changes can be seen.

### Files

- [Regular comparison SVG](proof.svg) / [2× PNG](proof.png): A/B/C with round-only adjustments and unchanged guard pairs.
- [All-weight comparison SVG](weights.svg) / [2× PNG](weights.png): the same three round-only settings at all nine weights.
- [Black guard-pair sheet SVG](pairs.svg) / [2× PNG](pairs.png): round-only versus blanket adjustment, including visible collision cases.
- [`fonts/`](fonts/): nine standalone OTFs in the separately named family **Allo G Spacing Study**. No font is installed automatically.
- [validation.json](validation.json): font-preservation and shaping results, trial amounts and diagnostic warnings.
- [clearances.json](clearances.json): sampled horizontal clearances, independently computed outline-intersection areas and measurement caveats.

The vector sheets use outlined text and scale to the window; their pixel-size labels refer to the original 1800 px-wide layouts. PNG and browser rasterization may differ. The interactive page is needed to judge live text at actual CSS pixel sizes.

## Trial amounts

Allo uses **2048 units per em**. The values below are positive magnitudes of tightening; the corresponding GPOS `XAdvance` adjustments are negative. A applies no additional adjustment.

| Weight | Style | B reduction | C reduction |
|---:|---|---:|---:|
| 100 | Thin | 40 | 80 |
| 200 | ExtraLight | 43 | 86 |
| 300 | Light | 45 | 90 |
| 400 | Regular | 48 | 96 |
| 500 | Medium | 51 | 102 |
| 600 | SemiBold | 54 | 108 |
| 700 | Bold | 57 | 114 |
| 800 | ExtraBold | 60 | 120 |
| 900 | Black | 64 | 128 |

B interpolates the 40 / 48 / 64-unit Thin / Regular / Black anchors using Allo's mapped weight coordinates and rounds to integer font units. C doubles each rounded B value. These are controlled comparison levels, **not final kerning values** or a mechanical conversion of measured optical whitespace into correct spacing.

## Implementation

Every glyph outline is retained from the corresponding study 02 font, including the new `g`, the reference `o` and `a`, and all other glyphs. Character mappings and the `hmtx`, `hhea`, `GSUB` and `GDEF` tables are unchanged. Existing GPOS lookups and feature records are preserved; four optional positioning features are appended:

| Feature | Scope | Trial |
|---|---|---|
| `ss17` | Every plain `g` advance, SinglePos | B |
| `ss18` | Every plain `g` advance, SinglePos | C |
| `ss19` | Only `go`, `ge`, `gc`, PairPos | B |
| `ss20` | Only `go`, `ge`, `gc`, PairPos | C |

All four features are **off by default** in the fonts. The proof page explicitly disables all four for A and enables exactly one for each B/C column. Do not enable multiple trial features together: their reductions can add. These are experimental GPOS features, not a production `ss04` implementation.

The broad SinglePos experiment models a smaller right sidebearing without editing actual `hmtx` advances, moving outlines within their glyphs, or changing the drawings. Existing kerning remains active. Font identity/version metadata is changed to keep this diagnostic family distinct.

## Findings and limits

Across the tested pairs at all nine weights, the analysis reports **11 close/overlap warnings**, including **four actual overlap cases**, all in all-followers C:

- `gj` at weights **700, 800 and 900**.
- `gy` at weight **900**.

At Black, all-followers B leaves `gj` about **8.4 units** of sampled horizontal clearance with no computed intersection. All-followers C leaves `gg` about **8.6 units** and `g]` about **12.4 units**. No intersection does not imply comfortable spacing.

There are **no warnings among the tested baseline or round-only cases**. That supports exploring selective round-follower adjustments rather than applying the same reduction indiscriminately, but does not establish a final spacing choice or a universal legibility guarantee.

Clearance is sampled from cubic outlines every four vertical font units, supplemented with curve-derived event levels. It is the horizontal envelope gap at common sampled heights, **not exact Euclidean distance**. Actual outline intersections are checked separately using BooleanGlyph, with a one-square-font-unit numerical tolerance. The below-32-unit clearance warning is a design-review threshold, not a typographic rule. See `clearances.json` for full definitions and per-pair results.

This remains an upright **Text / Friendly** study (`opsz` 14 / `ROND` 50), covering plain lowercase `g` only. Round mode covers only unaccented `o`, `e` and `c`; it is not a complete kerning class or an accent-spacing proposal. There is no production integration, production `ss04`, oblique design, accent integration, optical-size or roundness extension, or variable-font integration. Study 02 hinting is inherited: the new `g` remains unhinted, while other glyphs retain their existing hinting.

## Validation

The builder checks:

- **6,633 unchanged outlines:** all 737 glyphs in each of nine fonts.
- Unchanged metrics/layout tables listed above, and preservation of existing GPOS behavior while appending exactly four trial lookups/features.
- **1,305 shaping comparisons:** 29 strings × five feature states × nine weights. Default shaping matches study 02; trial states change only the expected `g` advances by the exact requested amounts, without changing glyph sequences or offsets.
- Unchanged descender, punctuation, preceding-letter and word-boundary controls in round mode.
- HTML tag balance and a single valid script boundary.
- SHA-256 preservation of both previous proof directories during the build.

`test_page.js` checks all weights, both scopes, explicit feature flags, literal text updates, independent comparison/reading sizes, and font-load failure/stale-load handling. These are **mocked-DOM tests**, not real-browser rendering validation. Font shaping is tested independently with HarfBuzz. Clearance warnings are intentional diagnostic findings, not failed preservation tests.

## Rebuild

Use the same environment as the preceding studies: Python 3.10+, `fonttools==4.60.2`, `ufoLib2==0.18.1`, `booleanOperations==0.10.0`, `brotli==1.2.1`, and `Pillow==12.0.0` with libraqm. HarfBuzz's `hb-shape` and Node.js must be on `PATH` for shaping and the UI test respectively.

With that Python environment active, run from the repository root:

```sh
python documentation/proofs/double-storey-g-spacing/build_proof.py
node documentation/proofs/double-storey-g-spacing/test_page.js
```

The builder reads study 02's nine proof OTFs, the existing weight map and rendering utilities from the previous studies. Importing those utilities does not run either previous build. It writes only this study's nine OTFs, three SVG/PNG sheet pairs, `proof.html` and two JSON reports: **18 generated artifacts**. `page.py` is the side-effect-free HTML source; `clearance.py` performs the geometry analysis. The regular project build does not consume this directory.

## License

The font derivatives remain under the repository's [SIL Open Font License 1.1](../../../OFL.txt). Original copyright/license metadata is retained. This diagnostic proof is not an upstream release or endorsement.
