# Double-storey g — text and pair coverage study 07

**Purpose: review one fixed spacing setting in ordinary text and across the plain Latin neighbours of g.** This is not another comparison of spacing alternatives and does not change production. It reuses the existing study 06 fonts without rebuilding or editing them. All six earlier proof directories remain intact.

## Review

Open [proof.html](proof.html), which works offline without installing fonts. Start with the **Regular paragraphs at 16 and 24 CSS px**. Both sizes show the same text. Then inspect the word/pair rows and the Thin, Regular, Bold and Black checkpoints.

- The weight selector controls the main reading, pairs and boundaries; all nine weights are available. The four checkpoint weights remain fixed.
- Pair/boundary sizes are 16, 24 or 32 CSS px; ordinary reading stays at 16 and 24.
- An optional text box replaces only the two reading passages, literally. Restore the original text with the button. Fixed examples and controls do not change.
- Use browser zoom 100%. Natural ragged-right wrapping is intentional; no tracking, justification or highlighting is inserted into font samples.

### Browser images

These are native browser captures, one image pixel per CSS pixel. View at native size; an editor preview may scale them.

- Regular reading: [16 px](browser/reading-400-16.png) / [24 px](browser/reading-400-24.png).
- [Every lowercase pair at Regular, 24 px](browser/pairs-400.png).
- [Capital, space and punctuation controls at Regular, 24 px](browser/boundaries-400.png).
- [Thin / Regular / Bold / Black checkpoints at 24 px](browser/weights.png).

## Confirmed integration direction

On 2026-11-26, the user confirmed that the **existing single-storey g remains the default**. The new double-storey design should be an independent opt-in stylistic set, selected in the same way as the existing alternate a (`ss01`). The proposed feature is **ss04 — Double-storey g**, covering plain `g` and the supported accented g family, with their spacing and mark attachment working in either state.

This is the target for subsequent integration, not functionality already implemented by these proofs. The proof-only positioning switches are not intended to become a requirement for using the production alternate. Committing these studies does not integrate or replace any production glyph.

## Fixed setting and scope

The user's [study 06 review](../double-storey-g-incoming-spacing/README.md#review-outcome) preferred the stronger **ng-only** trial at Regular: **−48 font units** of additional incoming spacing. This proof carries that trial across the weights for review, using the existing amounts below; it does not imply separate visual approval of every weight.

| Weight | 100 | 200 | 300 | 400 | 500 | 600 | 700 | 800 | 900 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Additional ng adjustment | −40 | −44 | −46 | −48 | −52 | −54 | −58 | −60 | −64 |

All samples retain the approved outgoing **C before o/e/c, B elsewhere**, the heavy `gj` refinement and the existing word-space policy. `hg`, `mg`, `ug` and all other incoming pairs stay unchanged. The drawings are unchanged. Incoming adjustment moves `g` and following text left by reducing the preceding `n` advance; it does not change `g`'s own advance or relative spacing to its follower.

The page explicitly enables **ss12, ss15, ss17, ss19**, and disables the other ss11–ss20 features. Do not combine additional trial features. The underlying study 06 OTFs still have these diagnostic features **off by default**; opening an OTF without the page's feature settings does not reproduce this proof.

Upright Text / Friendly (`opsz` 14 / `ROND` 50), plain Latin `g` and the listed neighbours only. No accent classes, obliques, other optical-size/roundness settings, variable-font integration or production `ss04` work is included. The replacement `g` remains unhinted.

## Coverage and interpretation

[coverage.json](coverage.json) is the literal corpus inventory, authored in [corpus.py](corpus.py):

- **52 lowercase rows:** 26 incoming `ag … zg`, 26 outgoing `ga … gz`; 51 unique pairs because `gg` appears twice.
- **41 word rows and 11 explicitly labeled test-string rows.** Each example contains its stated contiguous pair. Synthetic rows mean no sufficiently ordinary word was selected, not that none exists. `afghan` denotes a blanket; closed compounds intentionally preserve the adjacent letters.
- **26 capital-before-g pairs** and **22 boundary/control runs**, including spaces, punctuation, unchanged `hg/mg/ug`, approved outgoing `go/ge/gc/gj`, and combined `ngj/ngo/nge/ngc` controls.
- Three ordinary paragraphs plus the fixed focus words `Morning beginning changing going` and a shared weight-checkpoint passage.

The paragraphs test overall reading rhythm; the pair rows help locate an issue. English prose cannot naturally cover every pair. Invented strings and capital diagnostics are therefore separated from ordinary reading, not presented as words. This is not coverage of every glyph, script, language or multi-letter context.

## Validation

The builder checks corpus completeness and character coverage, shapes every authored run at all nine weights against the approved study 05 baseline, and verifies that only the intended `n`-before-`g` advance changes. It checks embedded WOFF2 identity and drawing, metric, mapping and layout tables against unchanged study 06 OTFs. It also measures lowercase, capital and punctuation pairs at their actual shaped positions, and hashes production plus all six earlier proof directories before and after the build.

- [Build report](validation.json): font/source identities, shaping and preservation checks, limits.
- [Clearance report](clearances.json): sampled horizontal gaps and independent Boolean outline intersections. These are not exact Euclidean distances or optical judgments. The inherited 32-unit review threshold is diagnostic, not a kerning rule; overlap areas up to one square font unit are numerical tolerance. Warnings require inspection, not automatic correction.
- [Browser report](browser/validation.json): exact HTML SHA-256, renderer conditions, real FontFace loads, feature/width/layout checks and capture dimensions.

Validation passed for **237 authored runs at nine weights**, giving **4,266 baseline/selected shaping comparisons**, and **918 pair geometry measurements**. No computed overlaps or sampled-clearance review flags were found among those measurements.

The browser suite passed **47 cases**, covering all nine actual embedded faces, 27 weight/size selector states, 1,404 pair-row layout states, 324 advance-width comparisons, literal text editing/reset, and five captures. The recorded renderer was **headless Chromium 149.0.7827.55 on macOS**, viewport 1440 × 1000, device scale factor 1, offline with HTTP/HTTPS blocked.

Two consecutive final builds reproduced all four generated artifacts byte-for-byte. Final artifact checks verified five PNGs, 19 local HTML/README links, source/font hashes, matching build/browser HTML hashes, and removal of the temporary browser profile. These checks do not establish optical approval. No visual issue found by this proof authorizes an unrelated drawing or spacing change.

## Rebuild

Reuse the [earlier proof Python dependencies](../double-storey-g-spacing-finish/README.md#scope-and-rebuild), including FontTools/Brotli, ufoLib2, booleanOperations and `hb-shape`. Run from the repository root:

```sh
python documentation/proofs/double-storey-g-text-coverage/build_proof.py
node documentation/proofs/double-storey-g-text-coverage/test_browser.js /opt/homebrew/lib/python3.11/site-packages/playwright/driver/package
```

The builder imports earlier helper definitions without invoking their builders. It writes only **proof.html, coverage.json, clearances.json and validation.json** here; it does not produce new OTFs. WOFF2 is embedded directly in HTML, with the source tables checked for equality.

The Node command uses this machine's installed Playwright package and Chromium runtime; the package path is optional if Node can resolve `playwright`. It runs headless/offline with HTTP/HTTPS blocked, uses and removes a temporary runtime/profile under `browser/`, and writes five captures plus its report. It installs nothing. Browser checks are specific to the recorded rendering path, not every browser, rasterizer or display.

## License

Embedded font derivatives remain under the repository's [SIL Open Font License 1.1](../../../OFL.txt), retaining the existing source metadata. This proof is not an upstream release or endorsement.
