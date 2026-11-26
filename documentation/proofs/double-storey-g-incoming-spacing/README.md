# Double-storey g — incoming spacing study 06

**Status: user prefers the “Tighter” ng trial; comparison retained, no production integration.** This investigates the awkward `ng` observed in study 05's running text. The drawings, approved outgoing C/B spacing, heavy `gj` refinement, and current word-space policy are held fixed. Production and all five earlier proof directories remain untouched.

## Review outcome

On 2026-11-26, the user preferred **Tighter** after the Regular / 24 CSS px / ng-only comparison: “I agree tighter is better.” At Regular this is **−48 font units** of additional incoming adjustment.

- Carry forward the **ng-only** direction. `hg`, `mg`, and `ug` stay unchanged; the shared-stem hypothesis is not adopted.
- The weight-dependent amounts in the Tighter column below are the tested candidates for the other weights. This review does not establish separate visual approval of every weight.
- No additional proof is needed merely to record this preference. The existing page, fonts, captures, and generated reports remain the original comparison evidence; any “unselected” wording in those artifacts describes their build-time status, before this review.

This records a visual preference, not a production change. Standalone font defaults are unchanged, and production integration still requires explicit authorization.

## Review

Open [proof.html](proof.html). It embeds all nine fonts, requires no installation or network access, and starts at **Regular / 400, ng-only, 24 CSS px**, matching the size of the reported example.

The three columns compare **Current / Slightly tighter / Tighter**. At Regular these mean **0 / −24 / −48 font units** of additional incoming adjustment. These labels are separate from the already approved outgoing B/C amounts.

- **ng-only:** change only `n` immediately before plain `g`. `hg`, `mg`, and `ug` are unchanged controls.
- **Shared-stem hypothesis:** apply the same trial to `n/h/m/u` immediately before plain `g`. This is an optional comparison, not an adopted kerning class.

The page includes the four focus words—`Morning`, `beginning`, `changing`, `going`—and a shared editable passage. The weight and scope controls affect the whole page; reading size offers 12, 16 and 24 CSS px while pairs stay at 64 px. Text edits are literal and do not change fixed controls. Unrelated incoming `og/ag/rg`, outgoing `go/ge/gc/gj`, and `ngj/ngo` guards help isolate the change.

Use browser zoom 100%. The three equal-width columns remain side by side with horizontal scrolling on narrow screens. Natural wrapping may change when a passage becomes shorter; no justification or tracking is added.

### Files

- [Regular comparison SVG](proof.svg) / [2× PNG](proof.png): ng-only trials above unchanged controls, with a separate shared-stem comparison at the bottom.
- [All-weight SVG](weights.svg) / [2× PNG](weights.png): ng-only trials across nine weights.
- [Proof fonts](fonts/): **Allo G Incoming Study**, nine separately named OTFs.
- [Build validation](validation.json) and [clearance/intersection measurements](clearances.json).
- [Previous outgoing-spacing finish](../double-storey-g-spacing-finish/proof.html).

### Actual browser captures

- Regular, ng-only: [16 px](browser/reading-400-ng-only-16.png) / [24 px](browser/reading-400-ng-only-24.png).
- Regular, shared-stem scope: [24 px](browser/reading-400-stems-24.png).
- Black: [ng-only, 24 px](browser/reading-900-ng-only-24.png) / [shared-stem scope, 24 px](browser/reading-900-stems-24.png).
- [Browser report](browser/validation.json), including the exact HTML SHA-256, renderer and capture dimensions.

These screenshots have one image pixel per CSS pixel; view them at native size or use the live page. The English passage is ng-focused, so its text can look identical between scopes: inspect `hg/mg/ug` in the pair section or enter a passage with other target pairs to judge shared scope. Static sheet previews scale to the window and do not establish actual reading size.

## Trial amounts

Allo has 2048 units/em. The table shows positive tightening magnitudes; the actual PairPos advance changes are negative.

| Weight | Slightly tighter | Tighter |
|---:|---:|---:|
| 100 | 20 | 40 |
| 200 | 22 | 44 |
| 300 | 23 | 46 |
| 400 | 24 | 48 |
| 500 | 26 | 52 |
| 600 | 27 | 54 |
| 700 | 29 | 58 |
| 800 | 30 | 60 |
| 900 | 32 | 64 |

The slight level is half the existing B magnitude, rounded to an integer; the stronger level doubles that rounded value. These are modest controlled comparison steps, not a conversion of measured whitespace into correct kerning. They do not alter B or C themselves.

At Regular, sampled minimum horizontal gaps for `ng/hg/mg/ug` are approximately 287–288 units before adjustment. In shared mode the stronger trial reduces them to approximately 239–240 units. Their similar profiles motivate testing shared scope, but numerical similarity does not by itself establish an optical class or a preferred amount. Full-height whitespace distribution still differs between glyphs.

## What changes—and what does not

Four optional positioning features are added to derivatives of the study 05 fonts:

| Feature | Eligible pair(s) | Level |
|---|---|---|
| `ss11` | `ng` | Slight |
| `ss12` | `ng` | Tighter |
| `ss13` | `ng`, `hg`, `mg`, `ug` | Slight |
| `ss14` | `ng`, `hg`, `mg`, `ug` | Tighter |

Each adjusts the **preceding letter's XAdvance**, not `g`'s advance or outline. This moves `g` and subsequent text left while preserving the approved distance from `g` to its follower. For example, `ngj` gets the incoming correction but retains the `gj` exception; `ngo` retains C on `go`.

Every displayed state enables `ss15`, `ss17`, and `ss19` (the study 05 refined setting). `ss16`, `ss18`, and `ss20` stay off. Current enables none of the four new features; each trial enables exactly one. Never combine incoming trial features cumulatively.

All ten diagnostic features remain **off by default in the standalone fonts**. The page and renderers enable the required settings explicitly. Merely opening an OTF without feature settings shows inherited spacing, not this proof's Current state. Actual `hmtx` metrics, glyph drawings and hinting are unchanged; the new `g` remains unhinted.

## Validation

The builder checks:

- **6,633 unchanged outlines:** 737 glyphs × nine fonts.
- Unchanged `hmtx`, `hhea`, `GSUB`, and `GDEF`; original GPOS lookups, feature records and language-system selections preserved while adding four optional PairPos lookups/features.
- **3,402 shaping comparisons:** 63 strings × nine weights × six states (five displayed combinations plus the all-off font default). Current exactly matches study 05's refined state. Only eligible preceding advances change; every `g` advance and glyph offset remains intact.
- **900 pair/state checks:** 20 pairs × nine weights × five states. Identical positioned outlines are cached, giving **252 unique geometry measurements**. These include the incoming targets, unrelated controls and approved outgoing pairs.
- No sampled-clearance warnings or computed overlaps among the tested combinations. This does not select a preferred setting or guarantee universal legibility.
- All nine embedded WOFF2 identities, weights, outlines, metrics and layout tables match their OTFs; HTML structure is valid.
- SHA-256 preservation of all five earlier studies, production sources/fonts, and root build/configuration files during the build.

Clearance uses the preceding studies' cubic-aware horizontal sampling and independent BooleanGlyph intersections. It is not exact Euclidean distance. The 32-unit review threshold is not a typographic rule; intersections up to one square font unit are treated as numerical tolerance. See `clearances.json` for definitions.

The real-browser suite passed **74 cases**, covering **54 weight/scope/size combinations**, all nine actual embedded faces, nine approved-baseline checks, computed flags, equal column geometry, exact incoming width reductions, preserved outgoing widths, literal hostile text, and stale font-load success/failure handling. It also produced five reading screenshots. Browser-measured advance deltas use a 0.05 CSS px tolerance; screenshot dimensions account for outward rounding of fractional crop edges.

The recorded run used **headless Chromium 149.0.7827.55 on macOS**, viewport 1440 × 1000, device scale factor 1. The context is offline and blocks HTTP/HTTPS requests. These results are specific to that browser/rendering path, not every browser, display or rasterizer.

Two consecutive rebuilds reproduced all 16 generated artifacts byte-for-byte, also matching the browser-tested originals. Final checks parsed both SVGs, verified all seven PNGs, resolved 27 local HTML/README links, checked all nine font hashes, and confirmed that the passing browser report's HTML SHA-256 still matches the final proof.

## Scope and rebuild

This remains a proof-only upright Text / Friendly study (`opsz` 14 / `ROND` 50). Targets are plain unaccented `n/h/m/u` followed by plain `g`. No accent-class expansion, obliques, other optical-size/roundness settings, variable fonts, production `ss04` or production integration are included.

Use the [previous proof dependencies](../double-storey-g-spacing-finish/README.md#scope-and-rebuild). With the proof Python environment active, run from the repository root:

```sh
python documentation/proofs/double-storey-g-incoming-spacing/build_proof.py
node documentation/proofs/double-storey-g-incoming-spacing/test_browser.js /opt/homebrew/lib/python3.11/site-packages/playwright/driver/package
```

The second command uses this machine's installed Playwright package; its path is an optional argument, otherwise Node must resolve `playwright` normally. A compatible local Chromium runtime is required. The browser check is bounded, uses a temporary profile under this study's `browser/`, removes that profile on close, and writes captures plus a checksum-linked report there.

The font builder writes only this study's **16 generated artifacts**: nine OTFs, two SVG/PNG pairs, `proof.html`, `validation.json` and `clearances.json`. It imports previous helpers without invoking previous builders. The browser report and five screenshots are separate. The regular project build does not consume this directory.

## License

The font derivatives remain under the repository's [SIL Open Font License 1.1](../../../OFL.txt), retaining original copyright/license metadata. This proof is not an upstream release or endorsement.
