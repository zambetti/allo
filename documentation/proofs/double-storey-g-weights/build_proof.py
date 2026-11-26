#!/usr/bin/env python3
"""Study 02: isolated three-master g drawings and nine static comparison fonts."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True

from booleanOperations.booleanGlyph import BooleanGlyph
from fontTools.misc.roundTools import otRound
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.ttLib import TTFont
from fontTools.ufoLib.glifLib import readGlyphFromString
from PIL import Image, ImageDraw, features
from ufoLib2.objects import Glyph

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PREVIOUS = HERE.parent / "double-storey-g"
STYLES = dict(zip(range(100, 901, 100), (
    "Thin", "ExtraLight", "Light", "Regular", "Medium", "SemiBold", "Bold", "ExtraBold", "Black",
)))
ORIGINALS = {weight: ROOT / f"fonts/otf/Allo-{style}.otf" for weight, style in STYLES.items()}
CANDIDATES = {weight: HERE / f"fonts/AlloGWeightStudy-{style}.otf" for weight, style in STYLES.items()}
MASTER_FILES = {weight: HERE / f"masters/{STYLES[weight]}.glif" for weight in (100, 400, 900)}

# Reuse the first study's drawing/encoding utilities without running its build
# or writing bytecode into its directory. Its sources and outputs stay untouched.
spec = importlib.util.spec_from_file_location("regular_g_proof", PREVIOUS / "build_proof.py")
study01 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study01)
area, bounds, digest, recording, shape = (getattr(study01, name) for name in (
    "area", "bounds", "digest", "recording", "shape",
))
UPM = study01.UPM


def read_master(path):
    assert ET.parse(path).getroot().get("name") == "g.ss04"
    glyph = Glyph(name="g.ss04")
    readGlyphFromString(path.read_text(), glyph, glyph.getPointPen())
    assert not glyph.unicodes and not glyph.components
    return glyph


def topology(glyph):
    return [[point.type for point in contour.points] for contour in glyph.contours]


def weight_mapping():
    axis = next(axis for axis in ET.parse(ROOT / "sources/Allo.designspace").getroot().find("axes")
                if axis.get("tag") == "wght")
    return [(float(p.get("input")), float(p.get("output"))) for p in axis.findall("map")]


def mapped_weight(weight, mapping):
    for (user0, design0), (user1, design1) in zip(mapping, mapping[1:]):
        if user0 <= weight <= user1:
            return design0 + (design1 - design0) * (weight - user0) / (user1 - user0)
    raise ValueError(f"Weight outside the proof range: {weight}")


def interpolate(weight, masters, mapping, rounded=False):
    design = mapped_weight(weight, mapping)
    low, high = (100, 400) if design <= 400 else (400, 900)
    t = (design - low) / (high - low)
    glyph = copy.deepcopy(masters[low])
    for contour, left, right in zip(glyph.contours, masters[low].contours, masters[high].contours):
        for point, a, b in zip(contour.points, left.points, right.points):
            point.x, point.y = a.x + t * (b.x - a.x), a.y + t * (b.y - a.y)
            if rounded:
                point.x, point.y = otRound(point.x), otRound(point.y)
    glyph.width = masters[low].width + t * (masters[high].width - masters[low].width)
    for anchor, a, b in zip(glyph.anchors, masters[low].anchors, masters[high].anchors):
        anchor.x, anchor.y = a.x + t * (b.x - a.x), a.y + t * (b.y - a.y)
    return glyph


def check_geometry(glyph):
    assert len(glyph.contours) == 3
    signed = [area(contour) for contour in glyph.contours]
    assert signed[0] > 0 and all(a < 0 for a in signed[1:])
    clean = BooleanGlyph(glyph).removeOverlap()
    assert len(clean.contours) == 3, "Overlap removal changed the three-contour structure"
    assert abs(abs(area(clean)) - abs(area(glyph))) < 1, "Overlap removal changed area"
    for contour in glyph.contours[1:]:
        x0, y0, x1, y1 = bounds(contour)
        assert x1 - x0 > 200 and y1 - y0 > 180, "Counter collapsed"
    return [bounds(contour) for contour in glyph.contours[1:]]


def build_font(weight, glyph):
    original_path, output = ORIGINALS[weight], CANDIDATES[weight]
    font = TTFont(original_path, recalcTimestamp=False)
    assert font["head"].unitsPerEm == UPM and font["OS/2"].usWeightClass == weight
    interpolated_width = glyph.width
    # Keep release spacing exactly. Its four-master metric curve differs from
    # the three-master drawing model by at most about one unit at these samples.
    # This changes the advance only; outlines are never horizontally fitted.
    glyph.width = font["hmtx"]["g"][0]
    top = font["CFF "].cff.topDictIndex[0]
    pen = T2CharStringPen(glyph.width - top.Private.nominalWidthX, None)
    glyph.draw(pen)
    top.CharStrings["g"] = pen.getCharString(
        private=top.Private, globalSubrs=font["CFF "].cff.GlobalSubrs,
    )
    font["hmtx"]["g"] = (int(glyph.width), otRound(bounds(glyph)[0]))
    style, family = STYLES[weight], "Allo G Weight Study"
    names = {
        3: f"AlloGWeightStudy-02-{style}", 4: f"{family} {style}",
        5: "Version 0.002; weight design proof only", 6: f"AlloGWeightStudy-{style}",
        16: family, 17: style, 18: f"{family} {style}",
    }
    for record in font["name"].names:
        if record.nameID in names:
            record.string = names[record.nameID]
        elif record.nameID in (1, 21):
            record.string = record.toUnicode().replace("Allo", family)
    font["CFF "].cff.fontNames[0] = names[6]
    top.FamilyName, top.FullName, top.version = family, names[4], "0.002"
    font["head"].fontRevision = 0.002
    font.save(output)
    font.close()

    original, candidate = TTFont(original_path), TTFont(output)
    assert candidate["name"].getBestFamilyName() == family
    assert candidate["name"].getBestSubFamilyName() == style
    assert candidate["name"].getDebugName(6) == names[6]
    assert original.getGlyphOrder() == candidate.getGlyphOrder()
    assert original.getBestCmap() == candidate.getBestCmap()
    old, new = original.getGlyphSet(), candidate.getGlyphSet()
    for name in original.getGlyphOrder():
        assert original["hmtx"][name][0] == candidate["hmtx"][name][0]
        if name != "g":
            assert recording(old[name]) == recording(new[name]), (weight, name)
            assert original["hmtx"][name] == candidate["hmtx"][name]
    assert recording(old["g"]) != recording(new["g"])
    assert recording(glyph) == recording(new["g"])
    assert candidate["CFF "].cff.topDictIndex[0].CharStrings["g"].width == glyph.width
    assert bounds(new["g"])[1] >= -candidate["OS/2"].usWinDescent
    assert bounds(new["g"])[3] <= candidate["OS/2"].usWinAscent
    for tag in ("GSUB", "GPOS", "GDEF"):
        assert original.getTableData(tag) == candidate.getTableData(tag), (weight, tag)
    for sample in ("ago ogo going baggage", "giggling analogue", "ag og ng gg gy gr", "Good beginnings"):
        assert shape(original_path, sample) == shape(output, sample), (weight, sample)
    if weight == 400:
        approved = TTFont(PREVIOUS / "AlloGStudy-Regular.otf")
        assert recording(approved.getGlyphSet()["g"]) == recording(new["g"])
        approved.close()
    report = {
        "weight": weight, "style": style,
        "outline_source": "drawn master" if weight in MASTER_FILES else "interpolated",
        "advance": glyph.width, "three_master_interpolated_advance": interpolated_width,
        "advance_adjustment_without_outline_scaling": glyph.width - interpolated_width,
        "bounds": bounds(new["g"]), "counter_bounds": check_geometry(glyph),
        "unchanged_other_glyph_outlines": len(original.getGlyphOrder()) - 1,
        "reference_sha256": digest(original_path), "proof_sha256": digest(output),
    }
    original.close()
    candidate.close()
    return report


class Sheet(study01.Sheet):
    """Reuse study 01's text and rule renderer, with study 02's fonts and output paths."""
    def __init__(self, height, title):
        self.width, self.height, self.scale = 1800, height, 2
        self.fonts = {path: TTFont(path) for path in (*ORIGINALS.values(), *CANDIDATES.values())}
        self.paths, self.raster_fonts = {}, {}
        self.svg = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" viewBox="0 0 {self.width} {self.height}">',
            f'<title>{title}</title>', '<rect width="100%" height="100%" fill="white"/>',
        ]
        self.image = Image.new("RGB", (self.width * self.scale, self.height * self.scale), "white")
        self.draw = ImageDraw.Draw(self.image)

    def save(self, stem):
        (HERE / f"{stem}.svg").write_text("\n".join(self.svg + ["</svg>"]) + "\n")
        self.image.save(HERE / f"{stem}.png")
        for font in self.fonts.values():
            font.close()


def build_sheets():
    sheet = Sheet(1280, "Allo study 02: Thin, Regular and Black with existing o references")
    sheet.text(80, 58, "ALLO / GLYPH STUDY 02", 15, "#626262")
    sheet.text(80, 116, "A g across the weight range", 40)
    sheet.text(80, 155, "Thin and Black drawings · Approved Regular unchanged · Text / Friendly · Upright only", 18, "#626262")
    sheet.line(80, 187, 1720, 187)
    for x, weight in ((80, 100), (640, 400), (1200, 900)):
        old, new = ORIGINALS[weight], CANDIDATES[weight]
        sheet.text(x, 235, f"{STYLES[weight]} / {weight}", 22)
        for offset, label in ((10, "CURRENT g"), (180, "NEW g"), (350, "EXISTING o")):
            sheet.text(x + offset, 279, label, 13, "#626262")
        for y in (445 - 1118 * 260 / UPM, 445, 445 + 412 * 260 / UPM):
            sheet.line(x, y, x + 520, y, "#e9e9e9")
        sheet.text(x + 10, 445, "g", 260, font=old)
        sheet.text(x + 180, 445, "g", 260, font=new)
        sheet.text(x + 350, 445, "o", 260, font=old)
        sheet.text(x, 555, "NEW g IN CONTEXT / OTHER LETTERS UNCHANGED", 13, "#626262")
        sheet.text(x, 623, "ago  ogo", 64, font=new)
        sheet.text(x, 697, "going baggage", 52, font=new)
        sheet.text(x, 769, "giggling analogue", 48, font=new)
        sheet.line(x, 806, x + 520, 806)
        for label_y, baseline, size, text in (
            (844, 881, 24, "A good beginning grows."),
            (933, 966, 16, "Good things grow gradually in the garden."),
            (1015, 1044, 12, "Going, gathering, belonging. A good beginning grows."),
        ):
            sheet.text(x, label_y, f"{size} PX", 12, "#626262")
            sheet.text(x, baseline, text, size, font=new)
    sheet.line(80, 1112, 1720, 1112)
    sheet.text(80, 1152, "The o is an untouched reference at the same size and weight. The a in the samples is also unchanged.", 18, "#626262")
    sheet.text(80, 1191, "Separate proof fonts · Original advances and kerning retained · No accents, obliques or other axis settings", 16, "#626262")
    sheet.text(80, 1224, "New glyphs are unhinted. Use the browser proof at 100% zoom for actual reading-size comparison.", 16, "#626262")
    sheet.save("proof")

    sheet = Sheet(1720, "Allo study 02: nine weights, three drawn masters and six interpolated samples")
    sheet.text(80, 58, "ALLO / GLYPH STUDY 02", 15, "#626262")
    sheet.text(80, 116, "Between the drawings", 40)
    sheet.text(80, 155, "Six intermediate weights use corresponding-point interpolation and Allo's weight-axis mapping.", 18, "#626262")
    for x, text in ((80, "WEIGHT"), (300, "CURRENT g"), (480, "NEW g"), (660, "EXISTING o"), (870, "NEW g IN CONTEXT")):
        sheet.text(x, 205, text, 13, "#626262")
    for index, (weight, style) in enumerate(STYLES.items()):
        y = 260 + index * 150
        sheet.line(80, y - 29, 1720, y - 29, "#e9e9e9")
        sheet.text(80, y + 24, f"{weight} / {style}", 18)
        sheet.text(80, y + 54, "Drawn master" if weight in MASTER_FILES else "Interpolated", 13, "#626262")
        sheet.text(300, y + 62, "g", 120, font=ORIGINALS[weight])
        sheet.text(480, y + 62, "g", 120, font=CANDIDATES[weight])
        sheet.text(660, y + 62, "o", 120, font=ORIGINALS[weight])
        sheet.text(870, y + 47, "ago  going  baggage", 48, font=CANDIDATES[weight])
        sheet.text(870, y + 87, "Good things grow gradually in the garden.", 20, font=CANDIDATES[weight])
    sheet.line(80, 1620, 1720, 1620)
    sheet.text(80, 1661, "Only g is new. Reference letters, advance widths and kerning come from each matching released static font.", 17, "#626262")
    sheet.save("interpolation")


def build_html():
    rules = []
    for family, paths in (("Current", ORIGINALS), ("Candidate", CANDIDATES)):
        for weight, path in paths.items():
            rules.append(f"@font-face {{font-family:{family};font-weight:{weight};font-style:normal;src:url(data:font/woff2;base64,{study01.webfont(path)}) format('woff2')}}")
    html = (HERE / "proof.template.html").read_text()
    options = "\n".join(f'<option value="{weight}"{" selected" if weight == 400 else ""}>{weight} — {style}</option>' for weight, style in STYLES.items())
    html = html.replace("__FONT_RULES__", "\n".join(rules)).replace("__WEIGHT_OPTIONS__", options)
    (HERE / "proof.html").write_text(html)


def main():
    if not shutil.which("hb-shape") or not features.check_feature("raqm"):
        raise SystemExit("Requires hb-shape and Pillow with libraqm, as in study 01.")
    protected = list(ORIGINALS.values()) + [p for p in PREVIOUS.rglob("*") if p.is_file()]
    before = {path: digest(path) for path in protected}
    assert digest(MASTER_FILES[400]) == digest(PREVIOUS / "g.ss04.glif"), "Regular must remain approved study 01"
    masters = {weight: read_master(path) for weight, path in MASTER_FILES.items()}
    assert all(topology(glyph) == topology(masters[400]) for glyph in masters.values())
    mapping = weight_mapping()
    print("Checking compatible outlines at all 801 integer weights, before and after rounding…", flush=True)
    for weight in range(100, 901):
        for rounded in (False, True):
            check_geometry(interpolate(weight, masters, mapping, rounded))
    print("Geometry checks passed. Building nine separate proof fonts…", flush=True)
    reports = [build_font(weight, interpolate(weight, masters, mapping, rounded=True)) for weight in STYLES]
    build_sheets()
    build_html()
    assert all(digest(path) == checksum for path, checksum in before.items())
    report = {
        "scope": "Upright weight proof at Text/Friendly; plain lowercase g only",
        "master_weights": list(MASTER_FILES), "sample_weights": list(STYLES),
        "user_to_design_weight_map": mapping,
        "corresponding_points_per_contour": [len(c.points) for c in masters[400].contours],
        "integer_weights_geometry_checked": 801,
        "geometry_checked_before_and_after_coordinate_rounding": True,
        "approved_regular_source_and_compiled_outline_preserved": True,
        "all_previous_study_files_and_referenced_release_fonts_sha256_unchanged": True,
        "fonts": reports,
        "checks_passed": [
            "All three masters have identical contour and segment structure",
            "All integer weights 100–900 retain three contours and two open counters",
            "Overlap-removal area and topology checks pass before and after rounding",
            "All 736 other outlines, including o and a, are preserved in every proof font",
            "All release advances, mappings and GSUB/GPOS/GDEF tables are preserved",
            "Four shaping samples have identical glyph sequences and positioning at each weight",
            "Compiled g outlines exactly match their rounded interpolation results",
            "Proof outlines fit existing vertical metrics; proof families are separately named",
        ],
        "limitations": [
            "Nine static proof fonts, not a new variable font or a production ss04 feature",
            "Three-master g model; source weight mapping is retained, not the original g drawings",
            "Release advance widths override the three-master width interpolation without scaling outlines",
            "No accent, oblique, optical-size or roundness integration",
            "New g outlines are unhinted; existing glyphs keep release hinting",
            "Advance widths and kerning are inherited; new sidebearings require optical review",
            "Integer sampling does not constitute proof at every fractional weight",
        ],
    }
    (HERE / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Passed: 801 integer weights × 2 coordinate modes; 9 fonts; {sum(r['unchanged_other_glyph_outlines'] for r in reports)} preserved reference outlines.")
    print(f"Wrote master comparison, interpolation ladder, browser proof and validation report to {HERE}")


if __name__ == "__main__":
    main()
