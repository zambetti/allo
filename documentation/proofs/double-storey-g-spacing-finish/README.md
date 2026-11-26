# Double-storey g — spacing finish study 05

**Status: the approved C/B spacing is retained, with the requested heavy-weight `gj` refinement.** The running-text proof separately compares word-space behavior; that comparison has **not** been adopted. No glyph drawings, production files or earlier proof directories are changed.

## Review

Open [proof.html](proof.html) in a browser. All nine fonts are embedded; installation, a server and network access are unnecessary.

1. **Pair comparison:** chosen C/B versus the same setting with the `gj` exception, at 72 CSS px. The independent weight selector starts at Black / 900.
2. **Running text:** the refined setting in both columns, at the same weight and 12, 16 or 24 CSS px. The left column retains current word spacing; the right is an explicitly unadopted comparison restoring the inherited `g` advance before an ordinary space. Edit the shared passage once to update both columns literally. Reading starts at Regular / 400, 16 px.

Use browser zoom 100% for actual CSS-size comparisons. Both reading columns have equal widths, natural ragged-right wrapping, and no added tracking or justification. The Norwegian words `gjeng gjøre gjennom` provide separate `gj` diagnostics; the English passage exercises word-final `g` and ordinary reading rhythm. The small `g g` sample has a text-run end marker and remains at 16 CSS px.

- [Heavy-gj ladder SVG](proof.svg) / [2× PNG](proof.png).
- [Nine proof OTFs](fonts/) in the distinct **Allo G Spacing Finish** family.
- [Font/build validation](validation.json) and [pair clearance/intersection data](clearances.json).
- [Previous C/B selection](../double-storey-g-selected-spacing/proof.html), preserved unchanged.

### Browser reading captures

These are actual headless Chromium captures, not the Pillow-rendered vector-sheet preview. Each capture includes the current and comparison-only boundary policies side by side.

| Weight | 12 CSS px | 16 CSS px | 24 CSS px |
|---|---|---|---|
| Regular / 400 | [PNG](browser/reading-400-12.png) | [PNG](browser/reading-400-16.png) | [PNG](browser/reading-400-24.png) |
| Black / 900 | [PNG](browser/reading-900-12.png) | [PNG](browser/reading-900-16.png) | [PNG](browser/reading-900-24.png) |

The captures use one image pixel per CSS pixel. A preview that scales an image changes its apparent text size; use native-size viewing or the live page. Capture conditions and the exact proof HTML checksum are recorded in [browser/validation.json](browser/validation.json).

## The gj refinement

The exception adds positive advance to plain `g` **only when followed by plain `j`**. C for `go/ge/gc`, B for other followers, all glyph drawings and all other tested pair positions are retained.

| Weight | Added gj advance | Previous sampled gap | Refined sampled gap |
|---:|---:|---:|---:|
| 100–500 | 0 | unchanged | unchanged |
| 600 / SemiBold | 0 | 67.5958 | 67.5958 |
| 700 / Bold | +8 | 49.7625 | 57.7625 |
| 800 / ExtraBold | +27 | 28.6425 | 55.6425 |
| 900 / Black | +40 | 8.3873 | 48.3873 |

All values are font units; Allo uses 2048 units/em. The +40-unit Black endpoint is a conservative optical adjustment, **not a clearance threshold automatically converted into correct spacing**. It opens the troublesome lower-form gap without undoing the general B reduction entirely.

The transition uses Allo's mapped design weight:

```text
t = clamp((mapped_weight - 580) / 320, 0, 1)
gj_correction = round(40 × t² × (3 − 2t))
```

The start is user weight 600 / design coordinate 580; the end is 900. This smoothstep has zero endpoint slopes before integer rounding in design coordinates. The builder checks the rounded correction at all 801 integer user weights for monotonicity and steps no greater than one unit. That is a **correction-curve check**, not a geometry check at 801 weights or a delivered variable font. Nine static proof fonts are emitted.

## Word-space comparison—not a second adopted exception

The refined setting retains B before spaces and on terminal `g`, exactly as in study 04.

The alternative adds +B back to `g` only before the font's `space` glyph, cancelling B there. In these fonts that glyph encodes **U+0020 SPACE only**. U+00A0 NO-BREAK SPACE uses a different glyph and is not restored. Neither a terminal `g` nor punctuation, line breaks or other whitespace receives a new exception. The space glyph's own width never changes.

In the inspected Regular and Black passages at 12, 16 and 24 CSS px, the boundary difference is subtle and does not provide a compelling visual reason to adopt another exception. The current policy is therefore retained. This is an optical assessment of these samples, not a claim that the two states are identical or that word spacing has been exhaustively settled.

## Font implementation

The nine new derivatives read the study 03 fonts reused by study 04. Existing GPOS lookups and feature records remain intact. Two optional PairPos features are added:

| Feature | Effect |
|---|---|
| `ss15` | Positive, weight-dependent `gj` correction |
| `ss16` | +B before the `space` glyph, comparison only |

The earlier four diagnostic features remain available and unchanged. All six are **off by default in the OTFs**; the page and sheet renderer explicitly select:

| State | Enabled features |
|---|---|
| Chosen C/B | `ss17`, `ss19` |
| Refined C/B | `ss15`, `ss17`, `ss19` |
| Boundary comparison | `ss15`, `ss16`, `ss17`, `ss19` |

`ss17` supplies B overall and `ss19` adds another B for rounds: B + B = C. `ss18` and `ss20` stay off in these states. Simply opening a proof OTF without feature settings shows inherited spacing, not the refined setting. No fonts are installed automatically.

The sorted GPOS feature list requires remapping language-system feature indices; the build verifies that the original feature selections and required-feature references are preserved. Actual `hmtx` metrics are unchanged. This is still diagnostic positioning, not production `ss04`.

## Validation

The font builder checks:

- **6,633 unchanged outlines:** 737 glyphs × nine fonts, including every new `g`.
- Unchanged `hmtx`, `hhea`, `GSUB` and `GDEF`; preservation of all existing GPOS lookups, feature records and language-system behavior.
- **1,584 shaping comparisons:** 44 strings × four states × nine weights. Glyph sequences and offsets stay unchanged; advances change by exactly the expected amounts. Chosen C/B reproduces the prior proof exactly. Controls include repeated `gj`, round followers, other descenders, punctuation, spaces, terminal `g`, NBSP and the running passages.
- **342 pair/state geometry checks:** 19 pairs × nine weights × chosen/refined. Fresh cubic-outline sampling and BooleanGlyph intersections use the actual shaped positions. Only `gj` changes in the refined state.
- **No refined-state warnings among the tested pairs:** no sampled gaps below the 32-unit review threshold and no intersections above the one-square-unit numerical tolerance. The previous two chosen-state `gj` warnings remain recorded for comparison.
- All nine embedded WOFF2 identities, weights, outlines, metrics and layout tables match their generated OTFs.
- HTML structure and script boundaries, and SHA-256 preservation of all four earlier proofs, production `sources/` and `fonts/`, and root `build.py`, `requirements.txt` and `README.md`.

Horizontal clearance is sampled every four vertical font units plus curve-derived levels. It is not exact Euclidean distance, and absence of intersections is not a universal legibility or rasterization guarantee. Full methods remain in `clearances.json`.

`test_page.js` independently tests the two weight controls, six explicit flags, sizes, literal shared text, scope notes, and font-loading failures/recovery/races in a mocked DOM.

### Browser checks

`test_browser.js` separately passed **45 cases / 7,613 assertions** in headless **Chromium 149.0.7827.55** on macOS, with a 1200 × 900 viewport and device scale factor 1. It verifies:

- All nine pair weights and all 27 reading weight/size combinations.
- Nine actual embedded FontFace objects loaded, not merely CSS declarations or fallback text.
- Computed feature flags, independent controls, equal reading-column widths and aligned text starts.
- Browser-measured advance changes for `gj`, unchanged round/guard pairs, the space comparison and terminal `g`, within 0.05 CSS px.
- Six reading screenshots, no page/console/font-loading errors, and no attempted HTTP/HTTPS page requests. The context is offline and HTTP/HTTPS requests are blocked.

The initial sandboxed browser launch timed out; a diagnostic launch also aborted. The successful browser check ran with approved unsandboxed execution, using a temporary profile and no installed-font changes. Browser evidence is specific to this renderer and capture path, not every browser, OS, display or rasterizer.

## Scope and rebuild

Upright Text / Friendly only (`opsz` 14 / `ROND` 50), plain lowercase `g` and `j`, with C's existing unaccented `o/e/c` scope. No broader accent, oblique, optical-size, roundness, variable-font or production integration. The new `g` remains unhinted; other inherited hinting is retained.

Use the [study 03 Python dependencies](../double-storey-g-spacing/README.md#rebuild), HarfBuzz's `hb-shape` and Node.js. With the proof Python environment active, run from the repository root:

```sh
python documentation/proofs/double-storey-g-spacing-finish/build_proof.py
node documentation/proofs/double-storey-g-spacing-finish/test_page.js
```

The builder regenerates only this study's **14 artifacts**: nine OTFs, one SVG/PNG pair, `proof.html`, `validation.json` and `clearances.json`. It imports earlier helpers without running earlier builders. Consecutive builds are checked for byte-for-byte reproducibility.

The optional browser check requires Playwright and its browser runtime. It accepts a Playwright package path as its first argument; this machine's installed copy was used as follows:

```sh
node documentation/proofs/double-storey-g-spacing-finish/test_browser.js /opt/homebrew/lib/python3.11/site-packages/playwright/driver/package
```

It writes six captures and `browser/validation.json`, separately from deterministic font-build artifacts. `browser/` must exist first. A successful rerun replaces the captures; consult the report's status and proof checksum rather than assuming old captures describe a newly rebuilt page. The regular project build does not consume this directory.

## License

Font derivatives remain under the repository's [SIL Open Font License 1.1](../../../OFL.txt), retaining original copyright/license metadata. This proof is not an upstream release or endorsement.
