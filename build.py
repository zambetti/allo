#!/usr/bin/env python3
"""Compile Allo from its editable, finished UFO masters. No drawing tools required."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import zipfile

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / 'release.json').read_text())
os.environ.setdefault('SOURCE_DATE_EPOCH', str(CONFIG['sourceDateEpoch']))
from fontTools.designspaceLib import DesignSpaceDocument
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib import TTFont
from ufo2ft import compileOTF, compileVariableTTF
import ufoLib2
from custom_names import rename_for_custom, validate_custom_fonts
from variable_proof import write_variable_proof


def save(font, path, web_dir=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    font.save(path)
    font.flavor = 'woff2'
    web = (web_dir if web_dir is not None else ROOT / 'fonts/webfonts') / (path.stem + '.woff2')
    web.parent.mkdir(parents=True, exist_ok=True)
    font.save(web)
    return [path, web]


def friendly_web(variable, web_dir=None, prefix='Allo', family='Allo'):
    """The lighter web font (Josh, 2026-11-14): the variable font with roundness fixed at Friendly (50), keeping
    optical size and weight; about half the size. Its own family, "Allo Variable Friendly", so it never stands in
    for the full font. Web only (fonts/webfonts/AlloVariableFriendly.woff2)."""
    from fontTools.varLib.instancer import instantiateVariableFont
    font = instantiateVariableFont(variable, {'ROND': 50})
    identity_ids = {1, 3, 4, 6, 16, 18, 21, 25}
    identity_ids.update(instance.postscriptNameID for instance in font['fvar'].instances
                        if instance.postscriptNameID != 65535)
    for record in font['name'].names:
        if record.nameID not in identity_ids:
            continue
        text = record.toUnicode()
        new = text.replace(prefix + 'Variable', prefix + 'VariableFriendly').replace(
            family + ' Variable', family + ' Variable Friendly')
        if new != text:
            record.string = new
    font.flavor = 'woff2'
    web = (web_dir if web_dir is not None else ROOT / 'fonts/webfonts') / (prefix + 'VariableFriendly.woff2')
    web.parent.mkdir(parents=True, exist_ok=True)
    font.save(web)
    return web


def drop_unreachable(tt):
    """Take out of a compiled font the glyphs nothing can reach: no character, no GSUB rule makes them,
    and no glyph that is reached uses them as a component (a CFF font has none: they're decomposed).
    They stay in the sources (the parts glyphs are built from, a duplicate ○). The font's subsetter
    does it, keeping every character, feature, name and table, and every master's deltas with their
    glyphs. The authoring build has the same function. Returns the names taken out."""
    from fontTools import subset
    options = subset.Options(
        layout_features=["*"], layout_scripts=["*"], name_IDs=["*"], name_languages=["*"], name_legacy=True,
        glyph_names=True, legacy_cmap=True, symbol_cmap=True, notdef_glyph=True, notdef_outline=True,
        hinting=True, drop_tables=[], passthrough_tables=True, prune_unicode_ranges=False,
        prune_codepage_ranges=False, recalc_bounds=False, recalc_timestamp=False, recalc_average_width=False,
        recalc_max_context=False)
    before = tt.getGlyphOrder()
    if "gvar" in tt:
        for name in before:
            tt["gvar"].variations.setdefault(name, [])
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=tt.getBestCmap())
    subsetter.subset(tt)
    kept = set(tt.getGlyphOrder())
    return [name for name in before if name not in kept]


WIN_PAST = ("circumflexacutecomb.cn", "circumflexgravecomb.cn", "circumflexhookcomb.cn", "circumflextildecomb.cn",
            "breveacutecomb.cn", "brevegravecomb.cn", "brevetildecomb.cn", "brevecomb_hookabovecomb", "dotbelow", "dotbelowcomb",
            "cedillacomb")
WIN_PAST_LIMIT = (2300, 560)


def check_win(fonts, win):
    """Every glyph in these fonts (UFOs, every layer) inside the Windows ascent and descent `win`, which all
    seven fonts share (so old Windows apps space them alike); raises if one would be cut off. Raise
    openTypeOS2WinAscent/Descent in every source then."""
    import math
    past_names = set(WIN_PAST)
    for f in fonts:
        for layer in f.layers:
            for g in layer:
                if any(c.baseGlyph in WIN_PAST for c in g.components): past_names.add(g.name)
    reach = {False: [0, 0], True: [0, 0]}
    for f in fonts:
        for layer in f.layers:
            for g in layer:
                past = g.name in past_names
                pen = BoundsPen(layer)
                g.draw(pen)
                if pen.bounds:
                    r = reach[past]
                    r[0], r[1] = max(r[0], math.ceil(pen.bounds[3])), max(r[1], math.ceil(-pen.bounds[1]))
    (hi, lo), (phi, plo) = reach[False], reach[True]
    if hi > win[0] or lo > win[1]:
        raise ValueError(f'glyphs reach {hi}/{lo} (ascent/descent), past the Windows metrics {win}')
    if phi > WIN_PAST_LIMIT[0] or plo > WIN_PAST_LIMIT[1]:
        raise ValueError(f'stacked accents or the dot below reach {phi}/{plo}, past WIN_PAST_LIMIT {WIN_PAST_LIMIT}')


def _crossings(glyphs, name, at, vertical=False):
    """Where the line y = at (vertical: x = at) crosses the glyph's outline, in order along it."""
    from fontTools.misc.bezierTools import calcCubicParameters, solveCubic
    pen = DecomposingRecordingPen(glyphs)
    glyphs[name].draw(pen)
    k = 0 if vertical else 1
    hits, start, last = [], None, None
    for op, pts in pen.value:
        if op == "moveTo":
            start = last = pts[0]
            continue
        if op in ("closePath", "endPath"):
            pts = (start,)
        if op != "curveTo":
            (x0, y0), (x1, y1) = last, pts[-1]
            pts = ((x0 + (x1 - x0) / 3, y0 + (y1 - y0) / 3), (x0 + 2 * (x1 - x0) / 3, y0 + 2 * (y1 - y0) / 3), pts[-1])
        a, b, c, d = calcCubicParameters(last, *pts)
        for t in solveCubic(a[k], b[k], c[k], d[k] - at):
            if 0 <= t < 1:
                hits.append(((a[1 - k] * t + b[1 - k]) * t + c[1 - k]) * t + d[1 - k])
        last = pts[-1]
    return sorted(hits)


def hint_values(fonts):
    """PostScript hinting values for the static CFF fonts, measured from the uprights (TTFonts, keyed by
    weight name): one set of alignment zones for the whole family, so the weights align together, and
    each weight's stems. Returns {weight name: Private dict values}."""
    zones = None
    stems = {}
    for name, tt in fonts.items():
        glyphs = tt.getGlyphSet()

        def box(g):
            pen = BoundsPen(glyphs)
            glyphs[g].draw(pen)
            return pen.bounds

        low = lambda names: min(box(g)[1] for g in names)
        high = lambda names: max(box(g)[3] for g in names)
        over = -low("o O zero e s c".split())
        xh, cap = box("x")[3], min(box(g)[3] for g in ("H", "one"))
        asc = min(box(g)[3] for g in "b d h k l".split())
        here = [(-over, 0), (xh, high("o e s c".split())), (cap, high(["O", "zero"])),
                (asc, asc + over),
                (low(["g", "j"]), max(box(g)[1] for g in "p q y".split()))]
        zones = here if zones is None else [(min(a, c), max(b, d)) for (a, b), (c, d) in zip(zones, here)]
        n = _crossings(glyphs, "n", xh / 2)
        h = _crossings(glyphs, "H", cap / 4)
        o = _crossings(glyphs, "o", sum(box("o")[::2]) / 2, vertical=True)
        bar = _crossings(glyphs, "H", sum(box("H")[::2]) / 2, vertical=True)
        lower_v, upper_v, lower_h, upper_h = (round(s[1] - s[0]) for s in (n, h, o, bar))
        stems[name] = {"StdVW": lower_v, "StdHW": lower_h,
                       "StemSnapV": sorted({lower_v, upper_v}), "StemSnapH": sorted({lower_h, upper_h})}
    zones = [(round(a), round(b)) for a, b in zones]
    blues, other = sorted(zones[:4]), zones[4:]
    edges = [v for zone in blues for v in zone]
    assert edges == sorted(edges) and len(set(edges)) == len(edges), ("overlapping zones", blues)
    blues, other = [v for zone in blues for v in zone], [v for zone in other for v in zone]
    scale = round(0.75 / max(b - a for a, b in zones), 6)
    return {name: {"BlueValues": blues, "OtherBlues": other, "BlueScale": scale} | s for name, s in stems.items()}


def hint_otfs(pairs):
    """Autohint the static CFF fonts in place (AFDKO's otfautohint), so stems snap to whole pixels
    where a rasteriser uses hints (Windows, FreeType); macOS ignores them. `pairs`: {weight name:
    (upright path, oblique path)}. First each Private dict gets hint_values' zones and stems; an
    oblique takes its upright's (slanting keeps heights and the horizontal widths of stems). Then
    otfautohint writes stems and hint masks, and the font is subroutinized again (otfautohint
    leaves every charstring flat, about twice the size). Outlines are untouched."""
    import cffsubr
    from afdko.otfautohint.__main__ import main as otfautohint
    values = hint_values({name: TTFont(upright) for name, (upright, _) in pairs.items()})
    for name, paths in pairs.items():
        for path in paths:
            tt = TTFont(path)
            private = tt["CFF "].cff.topDictIndex[0].Private
            for key, value in values[name].items():
                setattr(private, key, value)
            tt.save(path)
            if otfautohint([str(path), "--ignore-fontinfo", "--traceback", "-p", "1"]):
                raise RuntimeError(f"otfautohint failed on {path}")
            tt = TTFont(path)
            cffsubr.subroutinize(tt)
            tt.save(path)


def exact_small(tt, d):
    """The optical axis's small end is the text size with every glyph moved d units each side (release.json
    "smallShift"). Compiling leaves rounding noise in the tuples below the text size; this replaces them with
    the exact move: each point of a glyph with an advance d across, its advance 2d wider, composites' offsets
    so each part lands with its glyph (zero-width marks stay). Edited in place."""
    from fontTools.misc.roundTools import otRound
    from fontTools.ttLib.tables.TupleVariation import TupleVariation
    glyf, gvar, metrics = tt['glyf'], tt['gvar'], tt['hmtx'].metrics
    moves = {name: (d if metrics[name][0] else 0) for name in tt.getGlyphOrder()}
    for name in tt.getGlyphOrder():
        kept = [v for v in gvar.variations.get(name, []) if v.axes.get('opsz', (0, 0, 0))[1] >= 0]
        g = glyf[name]
        coords, control = glyf._getCoordinatesAndControls(name, metrics)
        if moves[name] or (g.isComposite() and any(moves[c.glyphName] for c in g.components)):
            dg = moves[name]
            if g.isComposite():
                deltas = []
                for c in g.components:
                    xx, xy = (c.transform[0][0], c.transform[0][1]) if hasattr(c, 'transform') else (1, 0)
                    deltas.append((otRound(dg - xx * moves[c.glyphName]), otRound(-xy * moves[c.glyphName])))
            else:
                deltas = [(dg, 0)] * (len(coords) - 4)
            deltas += [(0, 0), (2 * dg, 0), (0, 0), (0, 0)]
            tv = TupleVariation({'opsz': (-1.0, -1.0, 0.0)}, deltas)
            tv.optimize(coords, control.endPts, isComposite=g.isComposite())
            kept.append(tv)
        if kept:
            gvar.variations[name] = kept
        else:
            gvar.variations.pop(name, None)


SMART_DROPOUT = False


def smooth_unhinted(tt):
    '''The font has no TrueType hints: ask for smoothing at every size (gasp), so Windows doesn't pick a
    mode by size, and turn on smart dropout control (prep), so thin parts don't vanish at small sizes.
    The same tables as gftools fix-nonhinting; maxp's stack depth counts the one value prep pushes at a
    time (the spec counts prep there; fontTools doesn't).'''
    from fontTools.ttLib import newTable
    from fontTools.ttLib.tables import ttProgram
    tt['gasp'] = newTable('gasp')
    tt['gasp'].gaspRange = {0xFFFF: 15}
    if SMART_DROPOUT:
        tt['prep'] = newTable('prep')
        tt['prep'].program = ttProgram.Program()
        tt['prep'].program.fromBytecode(b'\xb8\x01\xff\x85\xb0\x04\x8d')
        tt['maxp'].maxStackElements = max(tt['maxp'].maxStackElements, 1)


WEIGHT_NAMES = ('Thin', 'ExtraLight', 'Light', 'Regular', 'Medium', 'SemiBold', 'Bold', 'ExtraBold', 'Black')

ZIP_README = '''
  ALLO  {version} ............................................ type specimen

  A friendly sans-serif typeface by Josh Puckett.
  Nine weights with obliques, and a variable font with three axes.


  AXES  (variable font)
    wght   100 ●━━━━━━━━━○━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━● 900
                         400
    opsz     9 ●━━━━━━━━━○━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━● 32
               small     14 text                     display
    ROND     0 ●━━━━━━━━━━━━━━━━━━━━━━━○━━━━━━━━━━━━━━━━━━━━● 100
               sharp               friendly               round

    Display (32) is drawn and spaced for headlines; below 14 only the
    spacing opens up. The static fonts are Text size, Friendly.


  STYLES
    100 Thin        400 Regular     700 Bold
    200 ExtraLight  500 Medium      800 ExtraBold
    300 Light       600 SemiBold    900 Black
                                    + an Oblique of each


  FEATURES
    ss01   Single-story a       a, and its accented forms
    ss02   Disambiguation       I l 1 0  →  serifed I, tailed l,
                                footed 1, slashed zero
    ss03   Open figures         4 6 9 with open forms
    ss04   Double-storey g      g, ĝ, ğ, ġ, ģ (single-storey stays default)
    cv01   Footed 1             cv02   Slashed zero
    cv03   Tailed l             cv04   Serifed I
    cv05   Dotted zero

    tnum   Tabular figures      every figure the same width
    zero   Slashed zero
    frac   Fractions            1/2 → ½   (1 1/2 and 11/14/2026 stay)
    sups   Superscript          2 → ²
    subs   Subscript            2 → ₂
    numr   Numerators           dnom   Denominators
    case   Capital forms        punctuation and signs sit with
                                capitals: (HELLO) [A–Z] ¿QUÉ?
    liga   Ligatures            tt ff tf ft share one crossbar
    clig   Typed arrows         on by default:
                                a -> b   a <- b   a --> b   a => b
    calt   Contextual           on by default, lifting:
                                (A) [1] −$4.50 +2% ¡HOLA! @ACME
    kern   Kerning

    Arrows need a space or nothing either side, so p->next stays code.
    "clig" 0 turns off only the arrows, "calt" 0 only the lifting.
    Letter-spacing turns ligatures off in most browsers.


  CHARACTERS  ({characters})
    Latin        A–Z a–z, accented forms, Vietnamese, ẞ ß Æ æ Œ œ
    Figures      0–9  ⁰¹²³⁴⁵⁶⁷⁸⁹  ₀₁₂₃₄₅₆₇₈₉  ½ ⅓ ¼ ⅔ ¾ ⅛ ⅜ ⅝ ⅞
    Punctuation  ! ? ¡ ¿ … · • † ‡ § ¶ ‘ ’ “ ” « » ‹ › ‐ – — ‒
    Currency     $ ¢ £ ¥ € ₹ ₩ ₽ ₺ ₪ ฿ ₫ ₴ ₦ ₱ ₿ ƒ
    Math         + − × ÷ = ≠ ≈ < > ≤ ≥ ± ∞ ¬ ° ′ ″ ‰ № ℃ ℉
    Arrows       ← → ↑ ↓ ↔ ↕ ↖ ↗ ↘ ↙ ⇐ ⇒ ⇔ ↩ ↵ ↻ ↺
    Keys         ⌘ ⌥ ⇧ ⌃ ⎋ ⇥ ⌫ ⌦ ⏎ ␣ ⌕
    Shapes       ● ○ ■ □ ▲ ▼ ▶ ◀ ◆ ★ ♥ ⚠ ✓ ✕ ✗ ❮ ❯


  FILES
    fonts/otf/        18 static fonts. Install these on your computer.
    fonts/variable/   AlloVariable.ttf, for apps with variable fonts.
                      Its family is "Allo Variable", so it installs
                      beside the static fonts.
    fonts/webfonts/   The same fonts as WOFF2, for websites, plus
                      AlloVariableFriendly.woff2: the variable font
                      with roundness fixed at Friendly (50). About half
                      the size; it has no ROND axis.
    OFL.txt           The license.

    Mac       double-click a font, then Install
    Windows   select the files, right-click, Install


  WEB
    @font-face {
      font-family: "Allo";
      src: url("AlloVariable.woff2") format("woff2");
      font-weight: 100 900;
    }
    body { font-family: "Allo", sans-serif; }
    /* Optical size follows the font size on its own.
       To keep Text everywhere: font-optical-sizing: none; */
    .round { font-variation-settings: "ROND" 100; }

    Not changing roundness? Use AlloVariableFriendly.woff2 instead:
    about half the size, optical size and weight still work, and
    roundness stays at 50 ("ROND" does nothing).


  ....................................................................
  Josh Puckett  ·  joshpuckett.me  ·  github.com/joshpuckett/allo
  SIL Open Font License 1.1
'''


def custom_output_root():
    """Keep generated custom files in one ignored tree, never through a symlink."""
    output = ROOT / 'build/custom'
    for path in (ROOT / 'build', output):
        if path.is_symlink():
            raise ValueError(f'Custom output must not be a symlink: {path}')
    if output.exists():
        if not output.is_dir():
            raise ValueError(f'Custom output must be a directory: {output}')
        for path in output.rglob('*'):
            if path.is_symlink():
                raise ValueError(f'Custom output contains a symlink: {path}')
    return output


def file_hashes(directory):
    return {str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(directory.rglob('*')) if path.is_file()}


def custom_readme(readme):
    text = (readme.replace('ALLO  ', 'ALLO CUSTOM  ', 1)
            .replace('AlloVariable', 'AlloCustomVariable')
            .replace('Allo Variable', 'Allo Custom Variable')
            .replace('"Allo"', '"Allo Custom"'))
    return ("ALLO CUSTOM — separate-name development build, not an upstream release.\n"
            "Built from the current project sources; naming alone adds no glyphs or features.\n"
            "The existing single-storey g remains default. Enable ss04 for the double-storey alternate.\n"
            "Open variable-proof.html for offline axis sliders and an editable two-character proof.\n"
            "Static family: Allo Custom. Variable family: Allo Custom Variable.\n"
            "These identities are distinct from the Allo release. No fonts are installed automatically.\n"
            "Web: use allo-custom.css OR allo-custom-friendly.css with font-family: Allo Custom.\n"
            "See naming-validation.json for identity checks and fonts/SHA256SUMS for font checksums.\n"
            "Original attribution and SIL Open Font License are retained below and in OFL.txt.\n"
            + text)


def custom_support_files(output):
    files = []
    for source, destination in (('allo.css', 'allo-custom.css'),
                                ('allo-friendly.css', 'allo-custom-friendly.css')):
        text = ((ROOT / source).read_text()
                .replace('/* Allo ', '/* Allo Custom (modified build) ', 1)
                .replace('"Allo"', '"Allo Custom"')
                .replace('./fonts/webfonts/Allo', './fonts/webfonts/AlloCustom'))
        path = output / destination
        path.write_text(text)
        files.append(path)
    license_path = output / 'OFL.txt'
    shutil.copyfile(ROOT / 'OFL.txt', license_path)
    files.append(license_path)
    return files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--custom', action='store_true',
                        help='build separately named Allo Custom fonts under build/custom/; leave release outputs untouched')
    args = parser.parse_args(argv)
    output = custom_output_root() if args.custom else ROOT
    prefix = 'AlloCustom' if args.custom else 'Allo'
    family = 'Allo Custom' if args.custom else 'Allo'
    web_dir = output / 'fonts/webfonts'
    if args.custom:
        # A failed rebuild must not leave a previous success report beside partial outputs.
        (output / 'naming-validation.json').unlink(missing_ok=True)
        references = sorted(path for path in (ROOT / 'fonts').rglob('*')
                            if path.suffix.lower() in ('.otf', '.ttf', '.woff2'))
        if not references:
            raise ValueError('Custom naming checks require the release reference fonts in fonts/')
        release_hashes = file_hashes(ROOT / 'fonts')
        print('Building Allo Custom from sources; release fonts and source names remain untouched.', flush=True)
    ds = DesignSpaceDocument.fromfile(ROOT / 'sources/Allo.designspace')
    ds.loadSourceFonts(ufoLib2.Font.open)
    for instance in ds.instances:
        instance.localisedStyleName = {'en': instance.styleName, **instance.localisedStyleName}
    statics = {path.stem: ufoLib2.Font.open(path) for path in sorted((ROOT / 'sources/static').glob('*.ufo'))}
    default = ds.findDefault().font.info
    win = (default.openTypeOS2WinAscent, default.openTypeOS2WinDescent)
    assert all((f.info.openTypeOS2WinAscent, f.info.openTypeOS2WinDescent) == win for f in [s.font for s in ds.sources] + list(statics.values())), 'Windows metrics differ between sources'
    check_win([s.font for s in ds.sources] + list(statics.values()), win)
    if args.custom:
        print('Compiling variable font…', flush=True)
    variable = compileVariableTTF(ds, useProductionNames=False, flattenComponents=True)
    if CONFIG.get('smallShift'):
        exact_small(variable, CONFIG['smallShift'])
    drop_unreachable(variable)
    smooth_unhinted(variable)
    if args.custom:
        rename_for_custom(variable)
    variable_path = output / 'fonts/variable' / (prefix + 'Variable.ttf')
    files = save(variable, variable_path, web_dir)
    with TTFont(variable_path) as saved_variable:
        files.append(friendly_web(saved_variable, web_dir, prefix, family))
    otfs = {}
    for stem, ufo in statics.items():
        target_stem = prefix + stem[len('Allo'):] if args.custom else stem
        otfs[stem] = output / 'fonts/otf' / (target_stem + '.otf')
        otfs[stem].parent.mkdir(parents=True, exist_ok=True)
        if args.custom:
            print(f'Compiling {target_stem}…', flush=True)
        otf = compileOTF(ufo, removeOverlaps=False, useProductionNames=False)
        drop_unreachable(otf)
        if args.custom:
            rename_for_custom(otf)
        otf.save(otfs[stem])
    if args.custom:
        print('Autohinting static OTFs…', flush=True)
    hint_otfs({w: (otfs[f'Allo-{w}'], otfs['Allo-' + ('' if w == 'Regular' else w) + 'Oblique']) for w in WEIGHT_NAMES})
    for path in otfs.values():
        with TTFont(path) as font:
            files += save(font, path, web_dir)
    hashes = {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    sums_path = output / 'fonts/SHA256SUMS'
    sums_path.write_text(''.join(f'{digest}  {name}\n' for name, digest in sorted(hashes.items())))
    readme = ZIP_README.replace('{version}', CONFIG['version']).replace('{characters}', str(len(variable.getBestCmap())))
    if args.custom:
        report = validate_custom_fonts(files, references)
        if file_hashes(ROOT / 'fonts') != release_hashes:
            raise RuntimeError('Release reference files changed during the custom build')
        report['release_files_unchanged'] = True
        report['font_sha256'] = hashes
        report_path = output / 'naming-validation.json'
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
        proof_path = write_variable_proof(web_dir / (prefix + 'Variable.woff2'), output / 'variable-proof.html')
        files += [report_path, sums_path, proof_path, *custom_support_files(output)]
        readme = custom_readme(readme)
        (output / 'README.txt').write_text(readme)
    else:
        files += [sums_path, ROOT / 'OFL.txt']
    archive = output / f"{prefix}-{CONFIG['version']}.zip"
    date = time.gmtime(int(os.environ['SOURCE_DATE_EPOCH']))[:6]
    entries = {str(p.relative_to(output)): p.read_bytes() for p in files
               if args.custom or p.name != 'SHA256SUMS'}
    entries['README.txt'] = readme.encode()
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(prefix + '-' + CONFIG['version'] + '/' + name, date)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, data)
    print(f'{len(hashes)} font files built; {archive.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
