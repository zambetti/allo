#!/usr/bin/env python3
"""Study 06: incoming g spacing trials, retaining the approved outgoing setting."""
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
PREVIOUS = HERE.parent / "double-storey-g-spacing-finish"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


study05 = load_module("finished_g_proof", PREVIOUS / "build_proof.py")
study03 = study05.study03
page = load_module("incoming_spacing_page", HERE / "page.py")
STYLES, UPM = study05.STYLES, study05.UPM
SOURCES, LABEL_FONT = study05.FONTS, study05.LABEL_FONT
FONTS = {w: HERE / f"fonts/AlloGIncomingStudy-{style}.otf" for w, style in STYLES.items()}
SLIGHT = {w: otRound(study05.AMOUNTS[w] / 2) for w in STYLES}
TAGS = tuple(f"ss{i}" for i in range(11, 21))
BASE = ("ss15", "ss17", "ss19")
TRIALS = {"ss11": (("n",), 1), "ss12": (("n",), 2),
          "ss13": (("n", "h", "m", "u"), 1), "ss14": (("n", "h", "m", "u"), 2)}
SETTINGS = {"current": BASE, "ng-slight": (*BASE, "ss11"), "ng-tighter": (*BASE, "ss12"),
            "stems-slight": (*BASE, "ss13"), "stems-tighter": (*BASE, "ss14")}
PARAGRAPHS = ["Morning light was changing as we began walking along the river. A good beginning meant going slowly, watching the garden, and giving each passing thing a little attention."]
PAIRS = ("ng", "hg", "mg", "ug", "og", "ag", "rg", "no", "ho", "mo", "uo",
         "go", "ge", "gc", "ga", "gg", "gy", "gj", "g.", "g)")
TEST_TEXTS = tuple(dict.fromkeys((*study05.TEST_TEXTS, *PAIRS,
    "Morning", "beginning", "changing", "going", "Morning beginning changing going",
    "ng hg mg ug", "ngj ngo nge ngc", "hgj hgo mgj mgo ugj ugo",
    "ngng hghg mgmg ugug", "ng g n g ng.", "n\u00a0g h\u00a0g",
    "nag hag mag uag", "nğ hğ mğ uğ", *PARAGRAPHS)))
SHAPED = {}
digest = study05.digest


def add_trials(font, weight):
    gpos = font["GPOS"].table
    assert getattr(gpos, "FeatureVariations", None) is None
    all_tags = {record.FeatureTag for table in ("GPOS", "GSUB") for record in font[table].table.FeatureList.FeatureRecord}
    assert not set(TRIALS).intersection(all_tags)
    added = []
    for tag, (predecessors, multiple) in TRIALS.items():
        value = buildValue({"XAdvance": -SLIGHT[weight] * multiple})
        pairs = {(left, "g"): (value, None) for left in predecessors}
        subtables = buildPairPosGlyphs(pairs, font.getReverseGlyphMap())
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
    for _, _, system in study05.language_systems(gpos):
        system.FeatureIndex.extend(added)
    ordered = sorted(enumerate(gpos.FeatureList.FeatureRecord), key=lambda item: item[1].FeatureTag)
    remap = {old: new for new, (old, _) in enumerate(ordered)}
    gpos.FeatureList.FeatureRecord = [record for _, record in ordered]
    for _, _, system in study05.language_systems(gpos):
        system.FeatureIndex = sorted(remap[index] for index in system.FeatureIndex)
        system.FeatureCount = len(system.FeatureIndex)
        if system.ReqFeatureIndex != 0xFFFF:
            system.ReqFeatureIndex = remap[system.ReqFeatureIndex]
    gpos.FeatureList.FeatureCount = len(gpos.FeatureList.FeatureRecord)
    gpos.LookupList.LookupCount = len(gpos.LookupList.Lookup)


def build_font(weight):
    family, style = "Allo G Incoming Study", STYLES[weight]
    with TTFont(SOURCES[weight], recalcTimestamp=False) as font:
        old_family = font["name"].getBestFamilyName()
        add_trials(font, weight)
        names = {3: f"AlloGIncomingStudy-06-{style}", 4: f"{family} {style}",
                 5: "Version 0.006; incoming spacing trials", 6: f"AlloGIncomingStudy-{style}",
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
        cff.topDictIndex[0].version = "0.006"
        font["head"].fontRevision = 0.006
        font.save(FONTS[weight])
    with TTFont(SOURCES[weight]) as original, TTFont(FONTS[weight]) as candidate:
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
        assert new_gpos.LookupList.LookupCount == old_gpos.LookupList.LookupCount + 4
        assert new_gpos.FeatureList.FeatureCount == old_gpos.FeatureList.FeatureCount + 4
        for before, after in zip(old_gpos.LookupList.Lookup, new_gpos.LookupList.Lookup):
            assert study03.table_xml(before, original) == study03.table_xml(after, candidate)
        records = {record.FeatureTag: record for record in new_gpos.FeatureList.FeatureRecord}
        for record in old_gpos.FeatureList.FeatureRecord:
            assert study03.table_xml(record, original) == study03.table_xml(records[record.FeatureTag], candidate)
        assert study05.script_signature(old_gpos) == study05.script_signature(new_gpos, set(TRIALS))
        count = len(original.getGlyphOrder())
    return {"weight": weight, "style": style, "slight": SLIGHT[weight], "tighter": 2 * SLIGHT[weight],
            "unchanged_outlines": count, "source": str(SOURCES[weight].relative_to(ROOT)),
            "source_sha256": digest(SOURCES[weight]), "font": str(FONTS[weight].relative_to(ROOT)),
            "font_sha256": digest(FONTS[weight])}


def shape_many(path, texts, state="current"):
    active = SETTINGS[state] if state != "default" else ()
    flags = ",".join(f"{tag}={int(tag in active)}" for tag in TAGS)
    result = subprocess.run(
        ["hb-shape", "--font-size=2048", "--font-funcs=ot", "--shapers=ot", "--direction=ltr",
         "--script=latn", "--language=en", "--output-format=json", f"--features={flags}", str(path)],
        input="\n".join(texts) + "\n", check=True, capture_output=True, text=True, timeout=30,
    )
    lines = result.stdout.splitlines()
    assert len(lines) == len(texts)
    for text, line in zip(texts, lines):
        SHAPED[path, text, state] = json.loads(line)


def shape(path, text, state="current"):
    if (path, text, state) not in SHAPED:
        shape_many(path, [text], state)
    return SHAPED[path, text, state]


def incoming_delta(base, index, weight, state):
    if state == "current" or index + 1 == len(base) or base[index + 1]["g"] != "g":
        return 0
    tag = next(tag for tag in SETTINGS[state] if tag in TRIALS)
    predecessors, multiple = TRIALS[tag]
    return -SLIGHT[weight] * multiple if base[index]["g"] in predecessors else 0


def validate_shaping():
    prior = json.loads((PREVIOUS / "validation.json").read_text())
    expected_hashes = {entry["weight"]: entry["font_sha256"] for entry in prior["fonts"]}
    for weight in STYLES:
        assert digest(SOURCES[weight]) == expected_hashes[weight]
        shape_many(SOURCES[weight], TEST_TEXTS)
        shape_many(SOURCES[weight], TEST_TEXTS, "default")
        for state in (*SETTINGS, "default"):
            shape_many(FONTS[weight], TEST_TEXTS, state)
            for text in TEST_TEXTS:
                base = shape(SOURCES[weight], text, "default" if state == "default" else "current")
                expected = deepcopy(base)
                if state != "default":
                    for index, item in enumerate(expected):
                        item["ax"] += incoming_delta(base, index, weight, state)
                actual = shape(FONTS[weight], text, state)
                assert actual == expected, (weight, state, text, actual, expected)
                # A changed preceding advance may move g; its own advance/offset must not change.
                if state != "default":
                    assert [item for item in actual if item["g"] == "g"] == [item for item in base if item["g"] == "g"]


def analyze_pairs():
    reference_path = PREVIOUS / "clearances.json"
    previous = json.loads(reference_path.read_text())
    report = {"scope": "Incoming ng-only versus n/h/m/u-before-g trials; approved outgoing spacing fixed",
              "measurement": previous["measurement"], "reference": str(reference_path.relative_to(ROOT)),
              "reference_sha256": digest(reference_path), "weights": {}, "warnings": [], "unique_measurements": 0}
    for weight in STYLES:
        pairs, cache = {}, {}
        with TTFont(FONTS[weight]) as font:
            glyphs = font.getGlyphSet()
            outlines = {name: study03.clearance._Outline(glyphs, name, 1) for name in set("".join(PAIRS)) if name not in ".)"}
            for name in ("period", "parenright"):
                outlines[name] = study03.clearance._Outline(glyphs, name, 1)
            for pair in PAIRS:
                base = shape(SOURCES[weight], pair)
                base_positions = study05.study04.origins(base)
                measurements = {}
                for state in SETTINGS:
                    shaped = shape(FONTS[weight], pair, state)
                    positions = study05.study04.origins(shaped)
                    names = [item["g"] for item in shaped]
                    assert names == [item["g"] for item in base] and len(names) == 2
                    expected = deepcopy(base_positions)
                    expected[1][0] += incoming_delta(base, 0, weight, state)
                    assert positions == expected
                    key = tuple(names), tuple(tuple(origin) for origin in positions)
                    if key not in cache:
                        first, second = [outlines[name] for name in names]
                        gap, gap_y, samples = study03.clearance._sampled_gap(first, second, positions)
                        intersection = first.positioned(*positions[0]).intersection(second.positioned(*positions[1]))
                        area = AreaPen(None)
                        intersection.draw(area)
                        cache[key] = {"origins": positions, "sampled_gap": gap, "overlap_area": abs(float(area.value)),
                                      "minimum_gap_y": gap_y, "common_y_samples": samples}
                    measurement = cache[key]
                    if state != "current":
                        expected_gap = measurements["current"]["sampled_gap"] + incoming_delta(base, 0, weight, state)
                        assert abs(measurement["sampled_gap"] - expected_gap) < 1e-6
                    if pair in previous["weights"][str(weight)]["pairs"] and state == "current":
                        old_gap = previous["weights"][str(weight)]["pairs"][pair]["refined"]["sampled_gap"]
                        assert abs(measurement["sampled_gap"] - old_gap) < 1e-6
                    measurements[state] = measurement
                    study03.clearance._warn(report["warnings"], weight, pair, state, state, measurement)
                pairs[pair] = {"glyphs": [item["g"] for item in base], **measurements}
        report["weights"][str(weight)] = {"font": str(FONTS[weight].relative_to(ROOT)), "sha256": digest(FONTS[weight]),
                                         "slight": SLIGHT[weight], "tighter": 2 * SLIGHT[weight], "pairs": pairs}
        report["unique_measurements"] += len(cache)
    assert not report["warnings"], report["warnings"]
    return report


class Sheet:
    def __init__(self, height, title):
        self.height = height
        self.fonts = {path: TTFont(path) for path in (*FONTS.values(), LABEL_FONT)}
        self.paths, self.raster_fonts = {}, {}
        self.svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="{height}" viewBox="0 0 1800 {height}">',
                    f'<title>{escape(title)}</title>', '<rect width="100%" height="100%" fill="white"/>']
        self.image = Image.new("RGB", (3600, height * 2), "white")
        self.draw = ImageDraw.Draw(self.image)

    def text(self, x, y, text, size=18, weight=None, state="current", color="#191919", max_width=None):
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
        width = cursor * size / UPM
        assert x + width <= 1740, text
        if max_width is not None:
            assert width <= max_width, (text, width, max_width)
        self.svg.append(f'<g aria-label="{escape(text, quote=True)}" fill="{color}" transform="translate({x} {y}) scale({size / UPM} {-size / UPM})">' + "".join(parts) + "</g>")
        key = path, size
        if key not in self.raster_fonts:
            self.raster_fonts[key] = ImageFont.truetype(str(path), size * 2, layout_engine=ImageFont.Layout.RAQM)
        flags = [tag if tag in SETTINGS[state] else "-" + tag for tag in TAGS]
        self.draw.text((x * 2, y * 2), text, font=self.raster_fonts[key], fill=color, anchor="ls", language="en", features=flags)

    def line(self, y, x1=80, x2=1720):
        self.svg.append(f'<path d="M{x1} {y}H{x2}" fill="none" stroke="#dedede"/>')
        self.draw.line((x1 * 2, y * 2, x2 * 2, y * 2), fill="#dedede", width=2)

    def save(self, stem):
        (HERE / f"{stem}.svg").write_text("\n".join(self.svg + ["</svg>"]) + "\n")
        self.image.save(HERE / f"{stem}.png")
        for font in self.fonts.values():
            font.close()


def header(sheet, title, subtitle):
    sheet.text(80, 58, "ALLO / GLYPH STUDY 06", 15, color="#626262")
    sheet.text(80, 116, title, 40)
    sheet.text(80, 155, subtitle, 18, color="#626262")
    sheet.line(187)


COLUMNS = (("current", "CURRENT"), ("ng-slight", "SLIGHTLY TIGHTER"), ("ng-tighter", "TIGHTER"))


def build_sheets():
    sheet = Sheet(1330, "Allo incoming ng spacing: current, slightly tighter and tighter")
    header(sheet, "Bringing n and g into the same rhythm", "Regular / 400 · Only incoming spacing changes · Approved C/B and gj refinement held fixed")
    for index, ((state, label), x) in enumerate(zip(COLUMNS, (80, 640, 1200))):
        sheet.text(x, 239, label, 20)
        sheet.text(x, 275, f"{index * SLIGHT[400]} units tighter before g", 16, color="#626262")
        for baseline, size, text in ((430, 140, "ng"), (540, 58, "Morning"), (615, 58, "beginning"), (690, 48, "changing going")):
            sheet.text(x, baseline, text, size, 400, state, max_width=520)
        sheet.line(740, x, x + 520)
        sheet.text(x, 778, "UNCHANGED CONTROLS IN ng-ONLY MODE", 13, color="#626262")
        sheet.text(x, 842, "hg mg ug", 58, 400, state, max_width=520)
        sheet.text(x, 908, "og ag rg", 48, 400, state, max_width=520)
        sheet.text(x, 972, "go ge gc gj", 48, 400, state, max_width=520)
        sheet.line(1010, x, x + 520)
        sheet.text(x, 1048, "SHARED-STEM TRIAL / COMPARISON ONLY", 13, color="#626262")
        shared = "current" if index == 0 else ("stems-slight", "stems-tighter")[index - 1]
        sheet.text(x, 1120, "hg mg ug", 58, 400, shared, max_width=520)
    sheet.line(1200)
    sheet.text(80, 1240, "Top rows tighten ng only. The lower shared-stem trial tests the same amounts on hg / mg / ug; no class has been adopted.", 17, color="#626262")
    sheet.text(80, 1278, "No drawing changes. Incoming adjustment changes the preceding letter advance, not the approved advance after g.", 17, color="#626262")
    sheet.save("proof")

    sheet = Sheet(2110, "Allo incoming ng spacing trials across nine weights")
    header(sheet, "Incoming spacing across the weights", "ng-only trials · hg / mg / ug remain controls · Current C/B and gj settings in every column")
    sheet.text(80, 224, "WEIGHT", 16, color="#626262")
    for (_, label), x in zip(COLUMNS, (310, 800, 1290)):
        sheet.text(x, 224, label, 16, color="#626262")
    for row, (weight, style) in enumerate(STYLES.items()):
        y = 273 + row * 190
        sheet.line(y - 22)
        sheet.text(80, y + 40, str(weight), 22)
        sheet.text(80, y + 72, style, 16, color="#626262")
        for index, ((state, _), x) in enumerate(zip(COLUMNS, (310, 800, 1290))):
            sheet.text(x, y + 9, f"{index * SLIGHT[weight]} units tighter", 13, color="#626262")
            sheet.text(x, y + 77, "ng going", 56, weight, state, max_width=430)
            sheet.text(x, y + 122, "Morning beginning", 32, weight, state, max_width=430)
            sheet.text(x, y + 156, "hg mg ug", 24, weight, state, max_width=430)
    sheet.line(2010)
    sheet.text(80, 2050, "Slightly tighter: 20 / 24 / 32 units at Thin / Regular / Black. The stronger trial doubles that reduction.", 17, color="#626262")
    sheet.save("weights")


def build_html():
    rules = [f"@font-face {{font-family:SpacingProof;font-weight:{w};font-style:normal;src:url(data:font/woff2;base64,{study03.study02.study01.webfont(path)}) format('woff2')}}"
             for w, path in FONTS.items()]
    config = {"weights": [{"weight": w, "style": style, "slight": SLIGHT[w], "tighter": 2 * SLIGHT[w]} for w, style in STYLES.items()],
              "paragraphs": PARAGRAPHS}
    html = page.render("\n".join(rules), config)
    study03.validate_html(html)
    faces = re.findall(r"@font-face\s*\{font-family:SpacingProof;font-weight:(\d+);font-style:normal;src:url\(data:font/woff2;base64,([A-Za-z0-9+/=]+)\)", html)
    assert len(faces) == 9 and {int(w) for w, _ in faces} == set(STYLES)
    for weight_text, encoded in faces:
        weight = int(weight_text)
        with TTFont(io.BytesIO(base64.b64decode(encoded, validate=True))) as web, TTFont(FONTS[weight]) as otf:
            assert web["name"].getBestFamilyName() == "Allo G Incoming Study"
            assert web["name"].getBestSubFamilyName() == STYLES[weight]
            assert web["OS/2"].usWeightClass == weight
            for tag in ("CFF ", "GPOS", "GSUB", "GDEF", "hmtx", "hhea"):
                assert web.getTableData(tag) == otf.getTableData(tag), (weight, tag)
    (HERE / "proof.html").write_text(html)


def protected_snapshot():
    result = study05.protected_snapshot()
    result.update({str(path.relative_to(ROOT)): digest(path) for path in PREVIOUS.rglob("*") if path.is_file()})
    return result


def main():
    if not shutil.which("hb-shape") or not features.check_feature("raqm"):
        raise SystemExit("Requires hb-shape and Pillow with libraqm")
    protected = protected_snapshot()
    print("Building nine incoming-spacing trial fonts; retaining all prior drawings and layout…", flush=True)
    fonts = [build_font(w) for w in STYLES]
    validate_shaping()
    print("Checking incoming pair geometry, untouched controls and fixed outgoing g advances…", flush=True)
    clearances = analyze_pairs()
    build_sheets()
    build_html()
    assert protected_snapshot() == protected, "A protected file changed, appeared or disappeared"
    (HERE / "clearances.json").write_text(json.dumps(clearances, indent=2) + "\n")
    report = {
        "scope": "Comparison only: current incoming ng, two tighter levels, optional shared n/h/m/u-before-g hypothesis; no final spacing selected",
        "fonts": fonts, "features": {state: {tag: int(tag in active) for tag in TAGS} for state, active in SETTINGS.items()},
        "trial_formula": "slight=round(study05 B/2); tighter=2*slight; magnitudes are comparison choices, not mechanically inferred kerning",
        "new_features": {tag: {"predecessors": list(predecessors), "follower": "g", "multiple": multiple}
                         for tag, (predecessors, multiple) in TRIALS.items()},
        "test_strings": len(TEST_TEXTS), "shaping_checks": len(STYLES) * len(TEST_TEXTS) * 6,
        "shaping_states": [*SETTINGS, "default"], "unchanged_outlines": sum(entry["unchanged_outlines"] for entry in fonts),
        "pair_state_geometry_checks": len(PAIRS) * len(STYLES) * len(SETTINGS),
        "unique_geometry_measurements": clearances["unique_measurements"], "warnings": clearances["warnings"],
        "protected_files_sha256_unchanged": True, "protected_file_count": len(protected),
        "checks_passed": [
            "All 737 drawings per font, hmtx, hhea, GSUB and GDEF unchanged",
            "Existing GPOS lookups, feature records and language-system selections preserved; four optional PairPos features added",
            "Current state matches study 05 refined C/B plus gj exactly; all-off defaults also preserved",
            "Only eligible preceding n/h/m/u advances change; every g advance, glyph sequence and offset is preserved",
            "ngj/ngo/nge/ngc and shared-stem equivalents retain approved outgoing relative spacing",
            "Current and all four incoming trials measured at actual shaped positions; no tested clearance warnings or overlaps",
            "Nine embedded WOFF2 identities, weights, outlines, metrics and layout tables verified against OTFs",
            "HTML structure checked; all five earlier studies and production files preserved byte-for-byte",
        ],
        "limitations": [
            "Neither a trial amount nor shared-stem scope has been adopted",
            "Proof-only optional positioning features; all ten are off by default in standalone fonts",
            "Plain unaccented n/h/m/u and g only; no broader kerning-class or accent integration",
            "Upright Text/Friendly only; no oblique, optical-size, roundness or variable-font integration",
            "g remains unhinted; inherited hinting otherwise retained",
            "Sampled horizontal clearance is not exact Euclidean distance or a legibility verdict",
            "Browser tests and capture conditions, if run, are recorded separately in browser/validation.json",
        ],
    }
    (HERE / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Passed: {report['unchanged_outlines']} preserved outlines; {report['shaping_checks']} shaping checks; {report['pair_state_geometry_checks']} pair/state checks.")
    print(f"No tested clearance warnings. {clearances['unique_measurements']} unique positioned-outline measurements; approved g advances unchanged.")
    print(f"Wrote {HERE}; all incoming trials remain unselected.")


if __name__ == "__main__":
    main()
