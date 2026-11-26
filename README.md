# Allo

Allo is your friendly neighborhood typeface. It’s variable in weight and roundness, with proportions and curves
designed to feel warm without being too cute and clear without being too cold. It’s a perfect companion out of the
box, and three variable axes and plenty of alternates let you tune its personality to exactly what you need.

Allo is optimized for screens and interfaces, with an optical size that adjusts automatically between text and
display. And it’s packed with big little details: tabular figures, fractions, punctuation that lifts beside capitals,
arrows that appear when you type them, a host of alternates and symbols, as well as a true oblique in every weight.

### [Type specimen at allo.joshpuckett.me →](https://allo.joshpuckett.me)

<br>

![Allo: the typeface, and its character set](documentation/readme-row1.png)
![Allo: OpenType features, and interface icons and symbols](documentation/readme-row2.png)

## Download

Get `Allo-1.1.0.zip` from the [latest release](https://github.com/joshpuckett/allo/releases/latest):

| Folder | Contents |
|---|---|
| `fonts/otf` | 18 static fonts, Thin to Black, each with an Oblique |
| `fonts/variable` | `AlloVariable.ttf`: all optical sizes, weights and roundnesses |
| `fonts/webfonts` | The same fonts as WOFF2, plus `AlloVariableFriendly.woff2` (roundness fixed at 50, about half the size) |

The static and variable fonts are separate families, **Allo** and **Allo Variable**, so both can be installed.

## Web

From npm:

```sh
npm install allo-font
```

```js
import "allo-font";            // the full variable font, and the obliques
// import "allo-font/friendly"; // or: roundness fixed at 50, about half the size
```

```css
body {
  font-family: "Allo", system-ui, sans-serif;
}
```

Or host the files yourself, from `fonts/webfonts`:

```css
@font-face {
  font-family: "Allo";
  src: url("AlloVariable.woff2") format("woff2");
  font-weight: 100 900;
  font-style: normal;
  font-display: swap;
}

body {
  font-family: "Allo", system-ui, sans-serif;
}
```

- **Optical size** follows the font size (`font-optical-sizing: auto`, the CSS default). Set it to `none` to keep the
  Text design at every size, or pick one with `font-variation-settings: "opsz" 32`.
- **Roundness** has no CSS property: use `font-variation-settings: "ROND" 0` (sharp) to `"ROND" 100` (round).
  Default 50.
- **Smaller file:** `AlloVariableFriendly.woff2` has roundness fixed at 50; `"ROND"` has no effect. Its family name
  is "Allo Variable Friendly".
- **Obliques:** the npm CSS includes them. Self-hosting, add an `@font-face` with `font-style: italic` and the matching `font-weight` for each oblique WOFF2
  you use (`Allo-Oblique.woff2`, `Allo-BoldOblique.woff2`, …).

## Axes

| Axis | Tag | Range | Default | Named values |
|---|---|---|---|---|
| Optical size | `opsz` | 9–32 | 14 | 9 Small, 14 Text, 32 Display |
| Weight | `wght` | 100–900 | 400 | Thin 100 to Black 900 |
| Roundness | `ROND` | 0–100 | 50 | 0 Sharp, 50 Friendly, 100 Round |

Display (32) is tighter, with stronger optical corrections. Below 14 only the spacing changes. The static fonts use
Text / Friendly proportions (opsz 14, ROND 50), but are separately edited sources, not exact variable instances.

## OpenType features

| Feature | Effect |
|---|---|
| `ss01` Single-story a | ɑ-shaped a |
| `ss02` Disambiguation | Serifed I, tailed l, footed 1, slashed zero |
| `ss03` Open figures | Open 4, 6 and 9 |
| `ss04` Double-storey g | Optional g, ĝ, ğ, ġ and ģ; current sources and new builds only |
| `cv01`–`cv04` | Footed 1, slashed zero, tailed l, serifed I, separately |
| `cv05` | Dotted zero |
| `tnum` | Tabular figures |
| `zero` | Slashed zero |
| `frac` | Fractions: 1/2 → ½ |
| `sups`, `subs`, `numr`, `dnom` | Superscript, subscript, numerator, denominator |
| `case` | Punctuation and symbols raised for capitals |
| `liga` | tt, ff, tf, ft with a shared crossbar |
| `clig` | Typed arrows: `->` → →, `=>` → ⇒, `<->` → ↔, with a space or nothing either side |
| `calt` | Brackets, signs, ¿ and ¡ raised beside capitals and figures |

`clig` and `calt` are on by default. `font-feature-settings: "clig" 0` turns off only the typed arrows (for code, say),
`"calt" 0` only the raised brackets and signs. Browsers turn ligatures off when letter-spacing is set.

`ss04` is available in the current sources and newly compiled fonts; untouched shipped `fonts/`, npm packages and
upstream releases do not gain it. The existing single-storey `g` remains the default. `ss01` controls `a` independently;
using the [custom-build CSS](#separate-name-custom-build), enable both with:

```css
.alternates {
  font-family: "Allo Custom", system-ui, sans-serif;
  font-feature-settings: "ss01" 1, "ss04" 1;
}
```

## Build

Python 3.9 or newer:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python build.py
```

Writes `fonts/` (variable TTF and WOFF2; 18 static OTFs and WOFF2s, autohinted with AFDKO), `fonts/SHA256SUMS` and
`Allo-1.1.0.zip`. Dependencies are pinned and `release.json` fixes the timestamp, so builds are reproducible.
For local alternate-g work, prefer `--custom` below to keep the shipped fonts available as comparison references.

### Separate-name custom build

To use a modified build alongside an installed Allo release, use the same environment with:

```sh
.venv/bin/python build.py --custom
```

This compiles the current sources, including optional `ss04`, into the ignored `build/custom/` directory, without
changing `sources/`, the shipped `fonts/`, or the normal release archive. No authoring regeneration is needed to
build. Running `build.py` without `--custom` retains the release-output behavior above and also compiles the
current sources; custom naming itself does not add the alternate.

| Custom output | Family / use |
|---|---|
| `build/custom/fonts/otf/AlloCustom-*.otf` | **Allo Custom**, 18 static styles including obliques |
| `build/custom/fonts/variable/AlloCustomVariable.ttf` | **Allo Custom Variable**, all three axes |
| `build/custom/fonts/webfonts/AlloCustom*.woff2` | Web versions, including **Allo Custom Variable Friendly** |
| `build/custom/variable-proof.html` | Self-contained, offline variable-font pair proof |
| `build/custom/AlloCustom-1.1.0.zip` | Fonts, CSS, license, README, checksums, naming-validation report, and `variable-proof.html` |

Install the custom OTFs and/or variable TTF manually, then select **Allo Custom** or **Allo Custom Variable** in
an app; the installed release keeps its existing name. No fonts are installed automatically. For websites, use
`build/custom/allo-custom.css` **or** `build/custom/allo-custom-friendly.css` with `font-family: "Allo Custom"`;
keep the adjacent `fonts/` directory when copying the CSS.

The custom mode changes internal family, full, unique, PostScript, CFF, and variable-instance identities—not just
filenames—while preserving style names, axis/feature labels, and original attribution/license metadata. It checks
saved font identities against the shipped release files and writes `build/custom/naming-validation.json` and
`build/custom/fonts/SHA256SUMS`. Keep the shipped `fonts/` tree available as the comparison reference.

#### Offline variable proof

Open `build/custom/variable-proof.html` directly in a browser, including offline via `file://`. It embeds the full
`build/custom/fonts/webfonts/AlloCustomVariable.woff2`, not the roundness-pinned Friendly font. No server, network
access or font installation is needed; JavaScript must be enabled. The custom ZIP includes the same proof.

- Enter any two characters or combining-mark clusters in the editable fields. They are joined without a separator
  as one shaped text run, so actual kerning and mark attachment apply, rather than separate character spans.
- Adjust the three axis sliders: `opsz`, `wght` and `ROND`. A separate preview-size slider changes CSS pixels only,
  not optical size. There is no `slnt` axis; obliques remain separate static fonts.
- Switch `ss04`, `ss01` and kerning independently, and show or hide the default-g comparison. Both previews share
  axes, size, `ss01` and kerning; the comparison forces only `ss04` off. The page starts with `ss04` on for inspection,
  without changing the font's default.

Watch the font-loading and character-coverage messages: unsupported characters may use fallback fonts. See the
[authoring notes](sources/alternates/double-storey-g/README.md#baseline-and-provenance) for the approved Text / Friendly
controls, subsequent interactive review, and its scope.

### Checks

With the build environment above and HarfBuzz's `hb-shape` on `PATH`, run the source/layout, naming/build-mode and
proof-generation regression tests (no font installation or release rebuild). Keep the shipped and historical study
fonts available as fixtures:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

See [compiled-font and real-browser checks](sources/alternates/double-storey-g/README.md#validation) for their
prerequisites and commands.

## Sources

`sources/Allo.designspace` (designspace 5, UFO) has 48 masters: opsz 9, 14, 20, 32 × wght 100, 400, 580, 900 ×
ROND 0, 50, 100, plus sparse roundness layers. The opsz 9 masters are the opsz 14 masters with wider spacing
(`release.json` "smallShift"). Corners are rounded in the outlines; the build compiles
the sources as they are. Keep points compatible across masters.

`sources/static` holds the 18 static fonts' sources: cut from the variable masters at opsz 14, ROND 50, then edited
separately. The obliques are separate drawings, not a slant axis.

The [double-storey-g authoring notes](sources/alternates/double-storey-g/README.md) document the canonical control
GLIFs, regeneration and its overwrite scope, geometry and spacing models, accents, obliques, and review limits.
Normal builds consume the saved UFOs, not the historical proof builders or the authoring generator.

## Contributing

Found a problem, or missing a character? Please [open an issue](https://github.com/joshpuckett/allo/issues); a
screenshot and the text you typed help a lot.

Pull requests that change the masters or the font files aren't accepted for now. Every change to a letter gets
reviewed by eye across all the weights and axes, and that's hard to do well for work that arrives from outside. If
you have a larger idea, such as a new script, open an issue first so we can talk about it.

You're free to modify Allo and ship your own version under the [license](OFL.txt).

## License

[SIL Open Font License 1.1](OFL.txt): free to use, modify and redistribute, including commercially. The fonts can't
be sold by themselves.

## Credit

Allo began from [Inter](https://github.com/rsms/inter) 4.2, which provided an incredible base to work from. Every
one of Allo's glyphs has been redrawn, with extensive work on spacing, kerning, features and axes, all tuned for the
friendly character that makes Allo its own. I owe a huge debt of gratitude to my friend [Rasmus Andersson](https://rsms.me) for creating
Inter and releasing it under an open license; without it, Allo would not exist.

Allo also pays homage to Honk Sans by [Seb McLauchlan](https://www.sebmclauchlan.com) and aims to bring some of that
same warmth and fun to everyone.
