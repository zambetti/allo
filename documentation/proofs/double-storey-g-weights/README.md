# Double-storey g — weight study 02

**Status: weight-range design proof, awaiting visual review.** This extends the approved Regular drawing with Thin and Black drawings and six interpolated weights. Production sources and fonts are unchanged.

## Review

Open [proof.html](proof.html) in a browser. It embeds both font families at all nine weights, so no installation, server or network access is needed. Select a weight, type your own text, and compare the current and proposed `g` alongside the **same untouched `o`**. The page also has paired 24, 16 and 12 px samples.

- [Master sheet SVG](proof.svg) / [2× PNG](proof.png): Thin, Regular and Black, each showing **current g / new g / existing o** at exactly the same size. The `a` in the word samples is another unchanged reference.
- [Interpolation ladder SVG](interpolation.svg) / [2× PNG](interpolation.png): all nine weights, explicitly labelled as drawn or interpolated.
- [validation.json](validation.json): geometry, preservation, interpolation and font-build checks.
- [`masters/`](masters/): editable, unencoded `g.ss04` drawings for Thin, Regular and Black.
- [`fonts/`](fonts/): nine standalone proof OTFs, using the distinct typographic family **Allo G Weight Study**. Nothing is installed automatically.

Use browser zoom at 100% for reading-size evaluation. The vector sheets scale to the window, so their pixel-size labels describe their original 1800 px layouts. Raster appearance varies between the PNG renderer and browsers/platforms.

## What changed

- **Thin:** a separately drawn light outline, using the existing `o`'s approximately 45–46-unit strokes as a reference.
- **Regular:** the approved study 01 GLIF is copied byte-for-byte; its compiled outline is also verified unchanged.
- **Black:** a separately drawn heavy outline, with space allocated to both counters and the connecting stroke rather than applying a uniform expansion. The lower counter's upper-left shoulder is softened without adding contour points.
- **Intermediate weights:** genuinely interpolated corresponding points, not scaled Regular glyphs or independently drawn snapshots.
- **Reference letters:** `o`, `a`, and every other glyph except plain lowercase `g` come directly from each corresponding released static font.

The Black drawing deliberately does not force every horizontal stroke to the `o`'s thickness: two stacked bowls require a different distribution of mass and white space. Whether that balance feels native is a visual review question, not something the geometry checks can settle.

## Interpolation model

The three drawings share three contours with **71 / 12 / 13 points**, identical segment types, winding and point correspondence. The proof uses piecewise-linear interpolation between Thin → Regular and Regular → Black, after applying the weight-axis mapping read from `sources/Allo.designspace`.

| User weight | Design coordinate | Drawing source |
|---:|---:|---|
| 100 | 100 | Thin master |
| 200 | 200 | 1/3 Thin → Regular |
| 300 | 300 | 2/3 Thin → Regular |
| 400 | 400 | Approved Regular master |
| 500 | 490 | 18% Regular → Black |
| 600 | 580 | 36% Regular → Black |
| 700 | 670 | 54% Regular → Black |
| 800 | 780 | 76% Regular → Black |
| 900 | 900 | Black master |

This is a **three-master design experiment**, not a replacement for Allo's full variable master graph. The existing font has an additional design-weight 580 master and other axis/sparse sources; the new outlines do not incorporate those drawings or extend to other axis values.

The release font's exact `g` advance is retained at each of the nine compiled weights. Its metric curve is slightly different from a three-master width interpolation, so the build replaces the interpolated advance with that existing integer value **without scaling or shifting the outline**. The discrepancy is recorded in `validation.json`. Kerning is retained; sidebearings change with the new outline and still need optical review.

## Validation

The build checks:

- Matching contour/segment structure across all three masters.
- All **801 integer user weights from 100 through 900**, both before and after rounding coordinates to font units.
- Three contours with the correct winding, preservation of area/topology under overlap removal, and non-collapsed counter bounds at every sampled weight.
- All nine compiled `g` outlines exactly matching their rounded interpolation results, including correct CFF width encoding and fit within existing vertical metrics.
- All **736 other glyph outlines and metrics preserved in each proof font**, including the comparison `o` and `a`.
- All release advances, character mappings and `GSUB`/`GPOS`/`GDEF` tables preserved.
- Four text samples with identical shaping sequences and positioning in each original/proof font pair.
- The approved Regular source and compiled drawing unchanged.
- SHA-256 preservation of the entire study 01 directory and all nine referenced production OTFs during the build.

Integer sampling is not a mathematical proof at every fractional weight. Open geometric counters also do not guarantee open counters at every rasterized size.

## Scope and remaining work

This is still only plain lowercase `g`, in upright Text / Friendly proportions. There is **no production `ss04` feature, no new variable font, no accent integration, no oblique design, and no optical-size or roundness extension**. The source name `g.ss04` reserves a plausible future alternate name; it does not enable a feature in these proof fonts.

The new `g` is unhinted; other glyphs retain release hinting. Inherited spacing/kerning and accent placement remain separate tasks. The current `g` in the production font is untouched.

## Rebuild

Use the same Python environment as [study 01](../double-storey-g/README.md#rebuild-and-validate): Python 3.10+, `fonttools==4.60.2`, `ufoLib2==0.18.1`, `booleanOperations==0.10.0`, `brotli==1.2.1`, `Pillow==12.0.0` with libraqm, and HarfBuzz's `hb-shape` on `PATH`.

From the repository root:

```sh
.venv-proof/bin/python documentation/proofs/double-storey-g-weights/build_proof.py
```

The script reads the three GLIFs, the existing weight map, and the nine released upright OTFs. It reuses study 01's rendering/encoding utilities without running that study's build or writing into its directory. It regenerates only the OTFs in this study's `fonts/`, the two SVG/PNG sheets, `proof.html` from `proof.template.html`, and `validation.json`.

The regular project build does not consume this directory.

## License

The font derivatives and outlines remain under the repository's [SIL Open Font License 1.1](../../../OFL.txt). Original copyright/license metadata is retained. This proof is not an upstream release or endorsement.
