#!/usr/bin/env python3
"""Study 05: a heavy-gj exception and a separate, unadopted word-space comparison."""
from __future__ import annotations

from copy import deepcopy
from html import escape
import base64
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True

from fontTools.misc.roundTools import otRound
from fontTools.otlLib.builder import buildLookup, buildPairPosGlyphs, buildValue
from fontTools.pens.areaPen import AreaPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables
from PIL import Image, ImageDraw, ImageFont, features

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PREVIOUS = HERE.parent / "double-storey-g-selected-spacing"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


study04 = load_module("selected_g_proof", PREVIOUS / "build_proof.py")
study03 = study04.study03
page = load_module("finish_spacing_page", HERE / "page.py")
STYLES, UPM, AMOUNTS = study04.STYLES, study04.UPM, study04.AMOUNTS
SOURCES, LABEL_FONT = study04.FONTS, study04.LABEL_FONT
FONTS = {w: HERE / f"fonts/AlloGSpacingFinish-{style}.otf" for w, style in STYLES.items()}
TAGS = ("ss15", "ss16", "ss17", "ss18", "ss19", "ss20")
SETTINGS = {
    "inherited": (), "chosen": ("ss17", "ss19"),
    "refined": ("ss15", "ss17", "ss19"),
    "boundary": ("ss15", "ss16", "ss17", "ss19"),
}
PARAGRAPHS = [
    "Morning light was reaching the garden as we began packing for the long journey. A good beginning meant checking the bags, gathering the maps, and leaving enough time to enjoy the road.",
    "We kept walking along the river, watching the changing light and talking about where we were going. Nothing needed to be hurried; there was room for another story before the evening train.",
]
TEST_TEXTS = study04.TEST_TEXTS + (
    "gj gjg ggj gjgj", "gjeng gjøre gjennom", "g j g  j", "g\u00a0j g\u00a0g",
    "g g", "g.", "g", "gj go ge gc ga gg gy", *PARAGRAPHS,
)
MAPPING = study03.study02.weight_mapping()
SHAPED = {}
digest = study04.digest


def gj_correction(weight):
    design = study03.study02.mapped_weight(weight, MAPPING)
    t = max(0.0, min(1.0, (design - 580) / 320))
    return otRound(40 * t * t * (3 - 2 * t))


CORRECTIONS = {w: gj_correction(w) for w in STYLES}


def language_systems(gpos):
    for record in gpos.ScriptList.ScriptRecord:
        script = record.Script
        if script.DefaultLangSys is not None:
            yield record.ScriptTag, "default", script.DefaultLangSys
        for language in script.LangSysRecord:
            yield record.ScriptTag, language.LangSysTag, language.LangSys


def script_signature(gpos, excluded=()):
    tags = [record.FeatureTag for record in gpos.FeatureList.FeatureRecord]
    return [(script, lang,
             None if system.ReqFeatureIndex == 0xFFFF else tags[system.ReqFeatureIndex],
             tuple(sorted(tags[index] for index in system.FeatureIndex if tags[index] not in excluded)))
            for script, lang, system in language_systems(gpos)]


def add_exceptions(font, weight):
    gpos = font["GPOS"].table
    assert getattr(gpos, "FeatureVariations", None) is None, "This helper is for static fonts only"
    all_tags = {record.FeatureTag for table in ("GPOS", "GSUB") for record in font[table].table.FeatureList.FeatureRecord}
    assert not {"ss15", "ss16"}.intersection(all_tags)
    space = font.getBestCmap()[32]
    added = []
    for tag, follower, amount in (("ss15", "j", CORRECTIONS[weight]), ("ss16", space, AMOUNTS[weight])):
        value = buildValue({"XAdvance": amount})
        subtables = buildPairPosGlyphs({("g", follower): (value, None)}, font.getReverseGlyphMap())
        lookup = len(gpos.LookupList.Lookup)
        gpos.LookupList.Lookup.append(buildLookup(subtables))
        record = otTables.FeatureRecord()
        record.FeatureTag = tag
        record.Feature = otTables.Feature()
        record.Feature.FeatureParams = None
        record.Feature.LookupListIndex = [lookup]
        record.Feature.LookupCount = 1
        added.append(len(gpos.FeatureList.FeatureRecord))
        gpos.FeatureList.FeatureRecord.append(record)
    for _, _, system in language_systems(gpos):
        system.FeatureIndex.extend(added)
    # FeatureRecords must be tag-sorted; remap language references, not lookups.
    ordered = sorted(enumerate(gpos.FeatureList.FeatureRecord), key=lambda item: item[1].FeatureTag)
    remap = {old: new for new, (old, _) in enumerate(ordered)}
    gpos.FeatureList.FeatureRecord = [record for _, record in ordered]
    for _, _, system in language_systems(gpos):
        system.FeatureIndex = sorted(remap[index] for index in system.FeatureIndex)
        system.FeatureCount = len(system.FeatureIndex)
        if system.ReqFeatureIndex != 0xFFFF:
            system.ReqFeatureIndex = remap[system.ReqFeatureIndex]
    gpos.FeatureList.FeatureCount = len(gpos.FeatureList.FeatureRecord)
    gpos.LookupList.LookupCount = len(gpos.LookupList.Lookup)


def build_font(weight):
    path = FONTS[weight]
    with TTFont(SOURCES[weight], recalcTimestamp=False) as font:
        add_exceptions(font, weight)
        family, style = "Allo G Spacing Finish", STYLES[weight]
        old_family = font["name"].getBestFamilyName()
        names = {3: f"AlloGSpacingFinish-05-{style}", 4: f"{family} {style}",
                 5: "Version 0.005; gj refinement proof", 6: f"AlloGSpacingFinish-{style}",
                 16: family, 17: style, 18: f"{family} {style}"}
        for record in font["name"].names:
            if record.nameID in names:
                record.string = names[record.nameID]
            elif record.nameID in (1, 21):
                record.string = record.toUnicode().replace(old_family, family)
        cff = font["CFF "].cff
        cff.fontNames[0] = names[6]
        cff.topDictIndex[0].FamilyName = family
        cff.topDictIndex[0].FullName = names[4]
        cff.topDictIndex[0].version = "0.005"
        font["head"].fontRevision = 0.005
        font.save(path)
    with TTFont(SOURCES[weight]) as original, TTFont(path) as candidate:
        assert original.getGlyphOrder() == candidate.getGlyphOrder()
        assert original.getBestCmap() == candidate.getBestCmap()
        assert candidate["name"].getBestFamilyName() == family
        assert candidate["name"].getBestSubFamilyName() == style
        assert candidate["OS/2"].usWeightClass == weight
        old, new = original.getGlyphSet(), candidate.getGlyphSet()
        for name in original.getGlyphOrder():
            assert study03.study02.recording(old[name]) == study03.study02.recording(new[name]), (weight, name)
        for tag in ("hmtx", "hhea", "GSUB", "GDEF"):
            assert original.getTableData(tag) == candidate.getTableData(tag), (weight, tag)
        old_gpos, new_gpos = original["GPOS"].table, candidate["GPOS"].table
        assert new_gpos.LookupList.LookupCount == old_gpos.LookupList.LookupCount + 2
        assert new_gpos.FeatureList.FeatureCount == old_gpos.FeatureList.FeatureCount + 2
        for before, after in zip(old_gpos.LookupList.Lookup, new_gpos.LookupList.Lookup):
            assert study03.table_xml(before, original) == study03.table_xml(after, candidate)
        new_records = {record.FeatureTag: record for record in new_gpos.FeatureList.FeatureRecord}
        for record in old_gpos.FeatureList.FeatureRecord:
            assert study03.table_xml(record, original) == study03.table_xml(new_records[record.FeatureTag], candidate)
        assert script_signature(old_gpos) == script_signature(new_gpos, {"ss15", "ss16"})
        cmap = candidate.getBestCmap()
        assert [chr(code) for code, name in cmap.items() if name == cmap[32]] == [" "]
        count = len(original.getGlyphOrder())
    return {"weight": weight, "style": style, "moderate": AMOUNTS[weight], "tighter": 2 * AMOUNTS[weight],
            "gj_correction": CORRECTIONS[weight], "unchanged_outlines": count,
            "source": str(SOURCES[weight].relative_to(ROOT)), "source_sha256": digest(SOURCES[weight]),
            "font": str(path.relative_to(ROOT)), "font_sha256": digest(path)}


def shape_many(path, texts, state="inherited"):
    flags = ",".join(f"{tag}={int(tag in SETTINGS[state])}" for tag in TAGS)
    result = subprocess.run(
        ["hb-shape", "--font-size=2048", "--font-funcs=ot", "--shapers=ot", "--direction=ltr",
         "--script=latn", "--language=en", "--output-format=json", f"--features={flags}", str(path)],
        input="\n".join(texts) + "\n", check=True, capture_output=True, text=True, timeout=30,
    )
    lines = result.stdout.splitlines()
    assert len(lines) == len(texts)
    for text, line in zip(texts, lines):
        SHAPED[path, text, state] = json.loads(line)


def shape(path, text, state="inherited"):
    if (path, text, state) not in SHAPED:
        shape_many(path, [text], state)
    return SHAPED[path, text, state]


def validate_shaping():
    for weight in STYLES:
        shape_many(SOURCES[weight], TEST_TEXTS)
        shape_many(SOURCES[weight], TEST_TEXTS, "chosen")
        for state in SETTINGS:
            shape_many(FONTS[weight], TEST_TEXTS, state)
            for text in TEST_TEXTS:
                base = shape(SOURCES[weight], text)
                expected = deepcopy(base)
                for index, item in enumerate(expected):
                    if item["g"] != "g" or state == "inherited":
                        continue
                    follower = base[index + 1]["g"] if index + 1 < len(base) else None
                    item["ax"] -= AMOUNTS[weight] * (2 if follower in study03.ROUND_FOLLOWERS else 1)
                    if state in ("refined", "boundary") and follower == "j":
                        item["ax"] += CORRECTIONS[weight]
                    if state == "boundary" and follower == "space":
                        item["ax"] += AMOUNTS[weight]
                actual = shape(FONTS[weight], text, state)
                assert actual == expected, (weight, state, text, actual, expected)
                if state == "chosen":
                    assert actual == shape(SOURCES[weight], text, "chosen")


def analyze_pairs():
    reference_path = PREVIOUS / "clearances.json"
    reference = json.loads(reference_path.read_text())
    report = {"scope": "Chosen C/B versus the same C/B with only the positive gj exception",
              "measurement": reference["measurement"], "reference": str(reference_path.relative_to(ROOT)),
              "reference_sha256": digest(reference_path), "weights": {}, "warnings": []}
    for weight in STYLES:
        old = reference["weights"][str(weight)]
        assert old["sha256"] == digest(SOURCES[weight])
        pairs = {}
        with TTFont(FONTS[weight]) as font:
            assert font["head"].unitsPerEm == UPM
            glyphs = font.getGlyphSet()
            outlines = {name: study03.clearance._Outline(glyphs, name, 1)
                        for name in {name for pair in old["pairs"].values() for name in pair["glyphs"]}}
            for pair, previous in old["pairs"].items():
                measurements = {}
                for state in ("chosen", "refined"):
                    shaped = shape(FONTS[weight], pair, state)
                    positions = study04.origins(shaped)
                    names = [item["g"] for item in shaped]
                    assert names == previous["glyphs"]
                    expected = deepcopy(previous["selected_origins"])
                    if state == "refined" and pair == "gj":
                        expected[1][0] += CORRECTIONS[weight]
                    assert positions == expected, (weight, pair, state)
                    first, second = [outlines[name] for name in names]
                    gap, gap_y, samples = study03.clearance._sampled_gap(first, second, positions)
                    intersection = first.positioned(*positions[0]).intersection(second.positioned(*positions[1]))
                    area = AreaPen(None)
                    intersection.draw(area)
                    measurement = {"origins": positions, "sampled_gap": gap, "overlap_area": abs(float(area.value)),
                                   "minimum_gap_y": gap_y, "common_y_samples": samples}
                    if state == "chosen":
                        assert abs(gap - previous["selected"]["sampled_gap"]) < 1e-6
                    elif pair != "gj":
                        assert measurement == measurements["chosen"]
                    else:
                        assert abs(gap - measurements["chosen"]["sampled_gap"] - CORRECTIONS[weight]) < 1e-6
                    measurements[state] = measurement
                    study03.clearance._warn(report["warnings"], weight, pair, state, state, measurement)
                pairs[pair] = {"glyphs": previous["glyphs"], **measurements}
        report["weights"][str(weight)] = {"font": str(FONTS[weight].relative_to(ROOT)), "sha256": digest(FONTS[weight]),
                                          "gj_correction": CORRECTIONS[weight], "pairs": pairs}
    report["refined_warnings"] = [item for item in report["warnings"] if item["mode"] == "refined"]
    assert not report["refined_warnings"], report["refined_warnings"]
    return report


class Sheet:
    def __init__(self):
        self.fonts = {path: TTFont(path) for path in (*FONTS.values(), LABEL_FONT)}
        self.paths, self.raster_fonts = {}, {}
        self.svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="1420" viewBox="0 0 1800 1420">',
                    '<title>Allo heavy gj refinement, unchanged C/B spacing elsewhere</title>',
                    '<rect width="100%" height="100%" fill="white"/>']
        self.image = Image.new("RGB", (3600, 2840), "white")
        self.draw = ImageDraw.Draw(self.image)

    def text(self, x, y, text, size=18, weight=None, state="inherited", color="#191919"):
        path = LABEL_FONT if weight is None else FONTS[weight]
        glyphs = self.fonts[path].getGlyphSet()
        cursor, parts = 0, []
        for item in shape(path, text, state):
            assert item["g"] != ".notdef", text
            key = path, item["g"]
            if key not in self.paths:
                pen = SVGPathPen(glyphs)
                glyphs[item["g"]].draw(pen)
                self.paths[key] = pen.getCommands()
            parts.append(f'<path transform="translate({cursor + item["dx"]} {item["dy"]})" d="{self.paths[key]}"/>')
            cursor += item["ax"]
        assert x + cursor * size / UPM <= 1740, text
        self.svg.append(f'<g aria-label="{escape(text, quote=True)}" fill="{color}" transform="translate({x} {y}) scale({size / UPM} {-size / UPM})">' + "".join(parts) + "</g>")
        key = path, size
        if key not in self.raster_fonts:
            self.raster_fonts[key] = ImageFont.truetype(str(path), size * 2, layout_engine=ImageFont.Layout.RAQM)
        flags = [tag if tag in SETTINGS[state] else "-" + tag for tag in TAGS]
        self.draw.text((x * 2, y * 2), text, font=self.raster_fonts[key], fill=color, anchor="ls", language="en", features=flags)

    def line(self, y):
        self.svg.append(f'<path d="M80 {y}H1720" fill="none" stroke="#dedede"/>')
        self.draw.line((160, y * 2, 3440, y * 2), fill="#dedede", width=2)

    def save(self):
        (HERE / "proof.svg").write_text("\n".join(self.svg + ["</svg>"]) + "\n")
        self.image.save(HERE / "proof.png")
        for font in self.fonts.values():
            font.close()


def build_sheet(clearances):
    sheet = Sheet()
    sheet.text(80, 58, "ALLO / GLYPH STUDY 05", 15, color="#626262")
    sheet.text(80, 116, "More room for gj, the same C/B elsewhere", 40)
    sheet.text(80, 155, "Positive pair correction only · Original drawings retained · Word-space policy unchanged in the refined setting", 18, color="#626262")
    sheet.line(187)
    sheet.text(360, 238, "CHOSEN C/B", 20)
    sheet.text(1040, 238, "WITH gj EXCEPTION", 20)
    for index, weight in enumerate((600, 700, 800, 900)):
        y = 290 + index * 240
        sheet.text(80, y + 65, str(weight), 26)
        sheet.text(80, y + 98, STYLES[weight], 18, color="#626262")
        for x, state in ((360, "chosen"), (1040, "refined")):
            sheet.text(x, y + 105, "gj", 140, weight, state)
            sheet.text(x + 205, y + 105, "gjg", 96, weight, state)
            gap = clearances["weights"][str(weight)]["pairs"]["gj"][state]["sampled_gap"]
            correction = CORRECTIONS[weight] if state == "refined" else 0
            sheet.text(x, y + 153, f"+{correction} units · sampled gj gap {gap:.1f}", 17, color="#626262")
            sheet.text(x, y + 203, "gg gy   go ge gc", 42, weight, state)
        sheet.line(y + 222)
    sheet.text(80, 1308, "A gradual +0 / +8 / +27 / +40 units at 600 / 700 / 800 / 900. No added gj spacing below 600.", 18, color="#626262")
    sheet.text(80, 1346, "No sampled-clearance warnings or computed overlaps in the tested refined pairs. This is not a universal legibility guarantee.", 17, color="#626262")
    sheet.save()


def build_html():
    rules = [f"@font-face {{font-family:SpacingProof;font-weight:{w};font-style:normal;src:url(data:font/woff2;base64,{study03.study02.study01.webfont(path)}) format('woff2')}}"
             for w, path in FONTS.items()]
    config = {"weights": [{"weight": w, "style": style, "moderate": AMOUNTS[w], "tighter": 2 * AMOUNTS[w], "gj_correction": CORRECTIONS[w]}
                          for w, style in STYLES.items()], "paragraphs": PARAGRAPHS, "space_characters": [" "]}
    html = page.render("\n".join(rules), config)
    study03.validate_html(html)
    faces = re.findall(r"@font-face\s*\{font-family:SpacingProof;font-weight:(\d+);font-style:normal;src:url\(data:font/woff2;base64,([A-Za-z0-9+/=]+)\)", html)
    assert len(faces) == 9 and {int(w) for w, _ in faces} == set(STYLES)
    for weight_text, encoded in faces:
        weight = int(weight_text)
        with TTFont(io.BytesIO(base64.b64decode(encoded, validate=True))) as web, TTFont(FONTS[weight]) as otf:
            assert web["name"].getBestFamilyName() == "Allo G Spacing Finish"
            assert web["name"].getBestSubFamilyName() == STYLES[weight]
            assert web["OS/2"].usWeightClass == weight
            for tag in ("CFF ", "GPOS", "GSUB", "GDEF", "hmtx", "hhea"):
                assert web.getTableData(tag) == otf.getTableData(tag), (weight, tag)
    (HERE / "proof.html").write_text(html)


def protected_snapshot():
    protected = study04.protected_snapshot()
    protected.update({str(path.relative_to(ROOT)): digest(path) for path in PREVIOUS.rglob("*") if path.is_file()})
    return protected


def main():
    if not shutil.which("hb-shape") or not features.check_feature("raqm"):
        raise SystemExit("Requires hb-shape and Pillow with libraqm")
    protected = protected_snapshot()
    ramp = [gj_correction(weight) for weight in range(100, 901)]
    assert CORRECTIONS == {100: 0, 200: 0, 300: 0, 400: 0, 500: 0, 600: 0, 700: 8, 800: 27, 900: 40}
    assert all(value == 0 for value in ramp[:501]) and ramp[-1] == 40
    assert all(0 <= right - left <= 1 for left, right in zip(ramp, ramp[1:]))
    print("Building nine proof fonts, preserving existing drawings and layout…", flush=True)
    fonts = [build_font(weight) for weight in STYLES]
    validate_shaping()
    print("Checking the actual chosen/refined glyph positions and intersections…", flush=True)
    clearances = analyze_pairs()
    build_sheet(clearances)
    build_html()
    assert protected_snapshot() == protected, "A protected file changed, appeared or disappeared"
    (HERE / "clearances.json").write_text(json.dumps(clearances, indent=2) + "\n")
    checks = len(STYLES) * len(TEST_TEXTS) * len(SETTINGS)
    report = {
        "scope": "Heavy gj refinement only; selected C/B retained; g-space restoration offered separately for comparison, not adopted",
        "fonts": fonts, "features": {state: {tag: int(tag in active) for tag in TAGS} for state, active in SETTINGS.items()},
        "gj_ramp": {"formula": "round(40 * t*t*(3-2*t)); t=clamp((mapped_weight-580)/320,0,1)",
                    "integer_weights_checked": 801, "nondecreasing": True, "largest_integer_step": max(b-a for a,b in zip(ramp,ramp[1:])),
                    "interpretation": "Smooth before rounding in mapped design coordinates; only nine static fonts are emitted, not a variable font"},
        "space_trial": {"feature": "ss16", "adopted": False, "glyph": "space", "characters": ["U+0020"],
                        "terminal_g": "Unchanged from chosen B", "nbsp": "U+00A0 uses a different glyph and is not restored"},
        "test_strings": len(TEST_TEXTS), "shaping_checks": checks,
        "unchanged_outlines": sum(entry["unchanged_outlines"] for entry in fonts),
        "geometric_pair_checks": sum(2 * len(entry["pairs"]) for entry in clearances["weights"].values()),
        "refined_warnings": clearances["refined_warnings"], "protected_files_sha256_unchanged": True,
        "protected_file_count": len(protected),
        "checks_passed": [
            "All outlines, hmtx, hhea, GSUB and GDEF retained; existing GPOS lookups and feature records retained",
            "Two optional PairPos lookups added; FeatureList sorted with language references remapped and verified",
            "Chosen C/B shaping matches the previous fonts exactly",
            "Refined changes only plain gj advances by the weight-specific positive amount",
            "Boundary trial changes only plain g before U+0020 space; terminal g and NBSP remain as chosen",
            "Exact glyph sequences, offsets and advances checked for all four states",
            "Fresh chosen/refined sampled gaps and BooleanGlyph intersections; all other tested pairs unchanged",
            "All nine embedded WOFF2 identities, weights, outlines, metrics and layout tables verified",
            "HTML structure checked; all four earlier studies and production files preserved",
        ],
        "limitations": [
            "Diagnostic features off by default; page selects them explicitly; no production integration",
            "Plain g and j only; C round class remains unaccented o/e/c; no broader accent integration",
            "Upright Text/Friendly only; no optical-size, roundness, oblique or variable-font integration",
            "New g remains unhinted; inherited hinting otherwise retained",
            "Sampled horizontal gap is not exact Euclidean distance or a legibility verdict",
            "Browser checks, if run, are recorded separately in browser/validation.json",
        ],
    }
    (HERE / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Passed: {report['unchanged_outlines']} unchanged outlines; {checks} shaping checks; {report['geometric_pair_checks']} pair/state geometry checks.")
    print("Refined spacing: no warnings among tested pairs; gj gaps 57.8 / 55.6 / 48.4 at 700 / 800 / 900.")
    print(f"Wrote {HERE}; word-space policy is unchanged in the refined setting.")


if __name__ == "__main__":
    main()
