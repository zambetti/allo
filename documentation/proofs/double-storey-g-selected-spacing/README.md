# Double-storey g — selected spacing study 04

**Selected direction: C for round followers, B for the others.** This records and applies the user's choice from [study 03](../double-storey-g-spacing/README.md) in a separate proof. The glyph drawings, all three previous studies, production sources and production fonts remain untouched. This is not production integration or a request to choose the same spacing again.

## Review the combined result

Open [proof.html](proof.html) in a browser. It embeds all nine weights and needs no font installation, server or network access. The fixed comparison columns show:

1. **Inherited:** study 02's double-storey `g`, with inherited spacing.
2. **C for rounds only:** the previous round-only C setting, leaving other advances unchanged.
3. **Selected — C rounds + B others:** C before unaccented `o/e/c`, B on all other plain `g` advances.

The column letters used internally are not the earlier A/B/C amount labels. B and C still mean the exact study 03 reduction amounts.

Use the weight selector, comparison-size slider and editable text. Reading samples remain at 24, 16 and 12 px; evaluate those at browser zoom 100%. Font-load status distinguishes the embedded font from possible fallback rendering. The sheets are static and scale to the window; their size labels refer to the original 1800 px-wide layouts, not necessarily their displayed size.

- [Regular comparison SVG](proof.svg) / [2× PNG](proof.png).
- [All nine weights SVG](weights.svg) / [2× PNG](weights.png).
- [Black guard-pair sheet SVG](pairs.svg) / [2× PNG](pairs.png), including the text-run boundary marker.
- [validation.json](validation.json): exact shaping, preservation and embedded-font checks.
- [clearances.json](clearances.json): fresh measurements at the actual combined-feature glyph positions.
- [Reused study 03 OTFs](../double-storey-g-spacing/fonts/): unchanged files in the **Allo G Spacing Study** family, not newly built selected-default fonts.

## The selected combination

The existing study 03 fonts already contain the necessary component adjustments. The selected proof uses:

```text
ss17=1, ss18=0, ss19=1, ss20=0
```

`ss17` applies B to every plain `g` advance. `ss19` applies one additional B only before `o`, `e` or `c`. Therefore round pairs receive **B + B = C**, while other advances receive B. Enabling `ss17` with `ss20` instead would incorrectly give rounds **B + C = 3B**; this proof does not do that.

Existing kerning remains active. All trial features remain off by default in the standalone OTFs; the selected settings are enabled explicitly by the proof page and sheet renderer. Merely opening an OTF without those settings will show inherited spacing. No new font files are written and no actual `hmtx` metrics are edited.

### Amounts

Positive magnitudes below describe tightening in font units; the actual advance adjustments are negative. Allo uses 2048 units/em. These retain study 03's mapped-weight amounts exactly.

| Weight | B — other advances | C — before o/e/c |
|---:|---:|---:|
| 100 | 40 | 80 |
| 200 | 43 | 86 |
| 300 | 45 | 90 |
| 400 | 48 | 96 |
| 500 | 51 | 102 |
| 600 | 54 | 108 |
| 700 | 57 | 114 |
| 800 | 60 | 120 |
| 900 | 64 | 128 |

### Boundaries and exceptions

“B for the others” follows the preceding study's all-followers B behavior: it includes the advance **before a space and after a terminal `g`**. For an isolated `og`, `ag` or `ng`, neither glyph origin moves, but the final advance shrinks. In a longer run, that advance reduction shifts subsequent text. The rule after `g g` exposes both effects.

No exceptions were silently added for `gj`, punctuation, spaces, terminal `g`, or other followers. Before any production integration, these boundary effects and the close heavy-weight `gj` should remain explicit review items rather than being mistaken for a completed kerning system.

## Clearance findings

The selected setting produces **no computed intersections above the one-square-font-unit tolerance in the 171 tested pair/weight combinations** (19 pairs × nine weights). Two sampled-clearance warnings remain:

| Pair | Weight | Sampled horizontal gap | Computed intersection area |
|---|---:|---:|---:|
| `gj` | 800 / ExtraBold | 28.6425 units | 0 |
| `gj` | 900 / Black | 8.3873 units | 0 |

These are the existing B-level warnings, not the overlaps from the rejected blanket-C experiment. The selected round pairs retain their C values exactly. No overlap does not establish comfortable spacing or guarantee collision-free rasterization.

The builder shapes the actual combined features, then freshly measures cubic-outline horizontal gaps and independently intersects the positioned outlines with BooleanGlyph. It also checks that the positions and measurements agree with the corresponding study 03 round-C or all-followers-B diagnostics. Sampling is every four vertical font units plus curve-derived event levels. This is **not exact Euclidean distance**. The below-32-unit warning is a design-review threshold, not a typographic rule; numerical intersection tolerance and full definitions are included in `clearances.json`.

## Validation and scope

The builder verifies:

- **6,633 unchanged outlines:** all 737 glyphs in each of nine reused fonts match study 02.
- Unchanged `hmtx`, `hhea`, `GSUB` and `GDEF` relative to study 02; the reused study 03 OTFs also match their recorded SHA-256 hashes in full.
- **918 shaping checks:** 34 strings × three settings × nine weights. Only the intended advances change; glyph sequences and offsets are preserved. Tests include repeated `g`, punctuation, boundaries, uppercase/digit followers and selected accented-follower controls.
- **171 geometric pair checks** at the actual selected positions, including fresh intersection tests and comparison with the corresponding previous measurements.
- All nine embedded WOFF2 identities, weights, outlines, metrics and layout tables match their source OTFs.
- Balanced HTML and a single script boundary.
- SHA-256 preservation of all three previous proof directories, production `sources/` and `fonts/`, and root `build.py`, `requirements.txt` and `README.md` during the build.

The Node test checks fixed feature flags, all nine weights and amounts, literal editable text, independent comparison/reading sizes, boundary explanations, and font-loading failures/stale-load races. It is a **mocked-DOM test, not browser-rendering validation**; HarfBuzz shaping and outline geometry are checked separately.

Scope remains plain lowercase `g` in nine upright Text / Friendly weights (`opsz` 14 / `ROND` 50). The additional round adjustment covers only unaccented `o/e/c`, not a complete kerning class. This does not integrate accented `g`, obliques, other optical-size or roundness values, a variable font, or production `ss04`. The new `g` remains unhinted; other glyphs retain inherited hinting. Browser and PNG raster appearance may differ.

## Rebuild

Use the [study 03 dependencies](../double-storey-g-spacing/README.md#rebuild): Python 3.10+, FontTools, ufoLib2, booleanOperations, Brotli, Pillow with libraqm, `hb-shape`, and Node.js. With the proof Python environment active, run from the repository root:

```sh
python documentation/proofs/double-storey-g-selected-spacing/build_proof.py
node documentation/proofs/double-storey-g-selected-spacing/test_page.js
```

The builder imports previous rendering/measurement utilities without invoking any previous builder. It writes only this directory's **nine generated artifacts**: three SVG/PNG pairs, `proof.html`, `validation.json` and `clearances.json`. `page.py` is the HTML source. Existing fonts are read, never rewritten. The regular project build does not consume this directory.

## License

The embedded font derivatives remain under the repository's [SIL Open Font License 1.1](../../../OFL.txt), with original copyright/license metadata retained. This proof is not an upstream release or endorsement.
