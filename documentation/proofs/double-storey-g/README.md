# Double-storey g — study 01

**Status: first Regular-weight design proof, awaiting visual review.** This is not a change to Allo's masters or released fonts, and is not a completed `ss04` implementation.

## Review

Open [proof.html](proof.html) in a browser. Both comparison fonts are embedded, so no font installation, local server or network access is needed. Type your own words and adjust the size. The default `g` is on the left; the candidate is on the right.

- [proof.svg](proof.svg): scalable comparison sheet with all text converted to outlines.
- [proof.png](proof.png): the same layout rendered at 2× resolution.
- [AlloGStudy-Regular.otf](AlloGStudy-Regular.otf): optional standalone proof font, with the distinct family name **Allo G Study**. It is not installed automatically.
- [g.ss04.glif](g.ss04.glif): editable, unencoded source outline for the proposed alternate. The name anticipates a possible future feature; it does not enable one.
- [validation.json](validation.json): build checks, metrics and input/output hashes.

Use the live HTML samples at 100% browser zoom for reading-size comparisons. The sheet scales to fit the window; its size labels refer to its original 1440-pixel layout. Rasterization will vary between the PNG renderer and browsers/platforms.

## Design intent

A compact upper bowl, a short rounded ear, and a wider closed lower loop, connected on the left. The roundness and restrained contrast aim to sit beside Allo's existing `a`, `o` and `n` without introducing a distinctly calligraphic construction.

The drawing uses the released Regular upright as its context, based on Text / Friendly proportions. Its vertical side strokes are approximately 176–178 units and its top/bottom bowl strokes approximately 154 units, close to the existing `o`'s 180–181-unit sides and 161-unit top/bottom strokes.

| Measurement | Current g | Candidate |
|---|---:|---:|
| Units per em | 2048 | 2048 |
| Advance width | 1243 | 1243 |
| Outline top | 1132 | 1132 |
| Outline bottom | −412 | −412 |
| Left sidebearing | 95 | 104 |
| Right sidebearing | 149 | 112 |

Keeping the advance width and descender depth fixed makes the first comparison easier to judge. It does **not** establish that the inherited spacing and kerning are final: the ear and loop change the white space next to neighbouring letters.

Useful review questions:

- Does the smaller upper bowl and wider loop feel native beside the existing letters?
- Does the left-hand link look too prominent, or appropriately soft?
- Do the counters remain comfortably distinct at 12–24 px?

## Scope and limitations

Only the plain lowercase `g` is replaced, and only in the separately named proof font. The regular project build does not use this directory.

The proof is built from a copy **in memory** of `fonts/otf/Allo-Regular.otf`. The production font is never overwritten. Other glyph outlines, character mappings, advance widths and existing OpenType layout tables are preserved. The candidate's left sidebearing metric is updated to match its new outline.

- Accented `g` forms still have their original drawings; accent placement has not been integrated or validated for this candidate.
- No other weights, optical sizes, roundness masters or obliques have been drawn.
- The new `g` is unhinted; the other glyphs retain the release font's hints.
- No new OpenType feature is added yet. A future `ss04` would select the alternate without replacing the default `g` in production.
- A successful geometry/build check is not aesthetic approval or a complete small-size rendering test.

After review, the next design checks would be Thin and Black before constructing compatible outlines across the family.

## Rebuild and validate

Requirements: Python 3.10 or newer, HarfBuzz's `hb-shape` on `PATH`, and the Python packages below. The build was checked with Python 3.13 and a Pillow wheel including libraqm. `hb-shape` is supplied by the HarfBuzz CLI tools (on macOS, `brew install harfbuzz`).

From the repository root, using a separate environment:

```sh
python3 -m venv .venv-proof
.venv-proof/bin/python -m pip install fonttools==4.60.2 ufoLib2==0.18.1 booleanOperations==0.10.0 brotli==1.2.1 Pillow==12.0.0
.venv-proof/bin/python documentation/proofs/double-storey-g/build_proof.py
```

The script reads the GLIF and released Regular OTF, then regenerates the proof OTF, HTML, SVG, PNG and validation report **only in this directory**. The HTML embeds WOFF2 versions of both fonts. The SVG uses HarfBuzz positioning and font outlines; the PNG uses Pillow/FreeType with libraqm at 2× resolution.

Checks include:

- Three contours with opposing outer/counter winding; overlap removal preserves the contour count and area within one square font unit.
- Matching source/compiled outline bounds, correct Type 2 width encoding, and fit within existing vertical metrics.
- Identical drawing commands and metrics for all 736 other glyphs.
- Unchanged character mappings, advance widths and `GSUB`/`GPOS`/`GDEF` tables.
- Identical glyph sequences and positioning for four shaping samples.
- A distinct family name and an unchanged SHA-256 for the original OTF.

## License

The font and derived outline remain under the repository's [SIL Open Font License 1.1](../../../OFL.txt). The proof font retains the original copyright and license metadata. This study is not an upstream release or endorsement.
