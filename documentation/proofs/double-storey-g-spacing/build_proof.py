#!/usr/bin/env python3
"""Study 03: compare GPOS-only spacing trials without changing any drawings."""
from __future__ import annotations

from functools import lru_cache
from html import escape
from html.parser import HTMLParser
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True

from fontTools.misc.roundTools import otRound
from fontTools.misc.xmlWriter import XMLWriter
from fontTools.otlLib.builder import buildLookup, buildPairPosGlyphs, buildSinglePos, buildValue
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables
from PIL import Image, ImageDraw, ImageFont, features

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PREVIOUS = HERE.parent / "double-storey-g-weights"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


study02 = load_module("weight_g_proof", PREVIOUS / "build_proof.py")
clearance = load_module("spacing_clearance", HERE / "clearance.py")
page = load_module("spacing_page", HERE / "page.py")
STYLES, UPM = study02.STYLES, study02.UPM
SOURCES = study02.CANDIDATES
OUTPUTS = {w: HERE / f"fonts/AlloGSpacingStudy-{style}.otf" for w, style in STYLES.items()}
LABEL_FONT = study02.ORIGINALS[400]
# These are comparison levels, not values inferred mechanically from ink bounds.
ANCHORS = {100: 40, 400: 48, 900: 64}
TAGS = {"ss17": ("all", 1), "ss18": ("all", 2), "ss19": ("round", 1), "ss20": ("round", 2)}
ROUND_FOLLOWERS = {"o", "e", "c"}
TEST_TEXTS = (
    "go", "ge", "gc", "ga", "gn", "gr", "gg", "gy", "gj", "og", "ag", "ng",
    "g.", "g,", "g:", "g;", "g)", "g]", "g!", "g g", "g", "gogog", "ggg",
    "ago going baggage", "gecko garlic gently", "A good beginning grows.",
    "Good things grow gradually in the garden.", "noon area office 0123", "ğ ĝ ġ ģ",
)


def moderate_amount(weight):
    design = study02.mapped_weight(weight, study02.weight_mapping())
    lo, hi = (100, 400) if design <= 400 else (400, 900)
    return otRound(ANCHORS[lo] + (ANCHORS[hi] - ANCHORS[lo]) * (design - lo) / (hi - lo))


AMOUNTS = {weight: moderate_amount(weight) for weight in STYLES}


def feature(mode, level):
    return None if level == 0 else {("all", 1): "ss17", ("all", 2): "ss18", ("round", 1): "ss19", ("round", 2): "ss20"}[mode, level]


@lru_cache(maxsize=None)
def shape(path, text, tag=None):
    settings = ",".join(f"{name}={int(name == tag)}" for name in TAGS)
    result = subprocess.run(
        ["hb-shape", "--font-size=2048", "--font-funcs=ot", "--shapers=ot",
         "--direction=ltr", "--script=latn", "--language=en", "--output-format=json",
         f"--features={settings}", str(path), text],
        check=True, capture_output=True, text=True, timeout=15,
    )
    return json.loads(result.stdout)


def table_xml(item, font):
    stream = io.BytesIO()
    item.toXML(XMLWriter(stream), font)
    return stream.getvalue()


def add_trial_features(font, amount):
    gpos = font["GPOS"].table
    original_tags = [record.FeatureTag for record in gpos.FeatureList.FeatureRecord]
    assert not set(TAGS).intersection(original_tags)
    assert original_tags + list(TAGS) == sorted(original_tags + list(TAGS))
    glyph_map = font.getReverseGlyphMap()
    added_indices = []
    for tag, (mode, multiple) in TAGS.items():
        value = buildValue({"XAdvance": -amount * multiple})
        if mode == "all":
            subtables = buildSinglePos({"g": value}, glyph_map)
        else:
            subtables = buildPairPosGlyphs({("g", right): (value, None) for right in sorted(ROUND_FOLLOWERS)}, glyph_map)
        lookup_index = len(gpos.LookupList.Lookup)
        gpos.LookupList.Lookup.append(buildLookup(subtables))
        record = otTables.FeatureRecord()
        record.FeatureTag = tag
        record.Feature = otTables.Feature()
        record.Feature.FeatureParams = None
        record.Feature.LookupListIndex = [lookup_index]
        record.Feature.LookupCount = 1
        added_indices.append(len(gpos.FeatureList.FeatureRecord))
        gpos.FeatureList.FeatureRecord.append(record)
    gpos.LookupList.LookupCount = len(gpos.LookupList.Lookup)
    gpos.FeatureList.FeatureCount = len(gpos.FeatureList.FeatureRecord)
    for record in gpos.ScriptList.ScriptRecord:
        script = record.Script
        languages = [script.DefaultLangSys] + [lang.LangSys for lang in script.LangSysRecord]
        for language in languages:
            if language is not None:
                language.FeatureIndex.extend(added_indices)
                language.FeatureCount = len(language.FeatureIndex)


def expected_reduction(base, index, mode, amount):
    if base[index]["g"] != "g":
        return 0
    if mode == "all" or (index + 1 < len(base) and base[index + 1]["g"] in ROUND_FOLLOWERS):
        return amount
    return 0


def build_font(weight):
    source, output = SOURCES[weight], OUTPUTS[weight]
    font = TTFont(source, recalcTimestamp=False)
    family, style = "Allo G Spacing Study", STYLES[weight]
    previous_family = font["name"].getBestFamilyName()
    add_trial_features(font, AMOUNTS[weight])
    names = {3: f"AlloGSpacingStudy-03-{style}", 4: f"{family} {style}",
             5: "Version 0.003; spacing diagnostic only", 6: f"AlloGSpacingStudy-{style}",
             16: family, 17: style, 18: f"{family} {style}"}
    for record in font["name"].names:
        if record.nameID in names:
            record.string = names[record.nameID]
        elif record.nameID in (1, 21):
            record.string = record.toUnicode().replace(previous_family, family)
    cff = font["CFF "].cff
    cff.fontNames[0] = names[6]
    cff.topDictIndex[0].FamilyName = family
    cff.topDictIndex[0].FullName = names[4]
    cff.topDictIndex[0].version = "0.003"
    font["head"].fontRevision = 0.003
    font.save(output)
    font.close()

    original, candidate = TTFont(source), TTFont(output)
    assert original.getGlyphOrder() == candidate.getGlyphOrder()
    assert original.getBestCmap() == candidate.getBestCmap()
    assert candidate["name"].getBestFamilyName() == family
    assert candidate["name"].getBestSubFamilyName() == style
    assert candidate["OS/2"].usWeightClass == weight
    old, new = original.getGlyphSet(), candidate.getGlyphSet()
    for name in original.getGlyphOrder():
        assert study02.recording(old[name]) == study02.recording(new[name]), (weight, name)
    for tag in ("hmtx", "hhea", "GSUB", "GDEF"):
        assert original.getTableData(tag) == candidate.getTableData(tag), (weight, tag)
    old_gpos, new_gpos = original["GPOS"].table, candidate["GPOS"].table
    for a, b in zip(old_gpos.LookupList.Lookup, new_gpos.LookupList.Lookup):
        assert table_xml(a, original) == table_xml(b, candidate)
    for a, b in zip(old_gpos.FeatureList.FeatureRecord, new_gpos.FeatureList.FeatureRecord):
        assert table_xml(a, original) == table_xml(b, candidate)
    for a, b in zip(old_gpos.ScriptList.ScriptRecord, new_gpos.ScriptList.ScriptRecord):
        assert a.ScriptTag == b.ScriptTag
        assert b.Script.DefaultLangSys.FeatureIndex[:len(a.Script.DefaultLangSys.FeatureIndex)] == a.Script.DefaultLangSys.FeatureIndex
    assert new_gpos.LookupList.LookupCount == old_gpos.LookupList.LookupCount + 4
    assert [r.FeatureTag for r in new_gpos.FeatureList.FeatureRecord[-4:]] == list(TAGS)
    for text in TEST_TEXTS:
        base = shape(source, text)
        assert shape(output, text) == base, (weight, text, "default shaping changed")
        for tag, (mode, multiple) in TAGS.items():
            trial = shape(output, text, tag)
            assert len(trial) == len(base)
            for index, (a, b) in enumerate(zip(base, trial)):
                expected = dict(a)
                expected["ax"] -= expected_reduction(base, index, mode, AMOUNTS[weight] * multiple)
                assert b == expected, (weight, tag, text, index, b, expected)
    report = {
        "weight": weight, "style": style, "moderate": AMOUNTS[weight], "tighter": 2 * AMOUNTS[weight],
        "unchanged_glyph_outlines_including_g": len(original.getGlyphOrder()),
        "test_strings": len(TEST_TEXTS), "feature_states_tested": 5,
        "source": str(source.relative_to(ROOT)), "source_sha256": study02.digest(source),
        "output_sha256": study02.digest(output),
    }
    original.close()
    candidate.close()
    return report


class Sheet:
    def __init__(self, height, title):
        self.width, self.height, self.scale = 1800, height, 2
        self.fonts = {path: TTFont(path) for path in (*OUTPUTS.values(), LABEL_FONT)}
        self.paths, self.raster_fonts = {}, {}
        self.svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="{height}" viewBox="0 0 1800 {height}">',
                    f'<title>{escape(title)}</title>', '<rect width="100%" height="100%" fill="white"/>']
        self.image = Image.new("RGB", (self.width * 2, height * 2), "white")
        self.draw = ImageDraw.Draw(self.image)

    def text(self, x, y, text, size=18, color="#191919", weight=None, tag=None):
        path = LABEL_FONT if weight is None else OUTPUTS[weight]
        glyphs = self.fonts[path].getGlyphSet()
        cursor, parts = 0, []
        for item in shape(path, text, tag):
            name = item["g"]
            assert name != ".notdef", text
            key = (path, name)
            if key not in self.paths:
                pen = SVGPathPen(glyphs)
                glyphs[name].draw(pen)
                self.paths[key] = pen.getCommands()
            parts.append(f'<path transform="translate({cursor + item["dx"]} {item["dy"]})" d="{self.paths[key]}"/>')
            cursor += item["ax"]
        assert x + cursor * size / UPM <= self.width - 60, text
        self.svg.append(f'<g aria-label="{escape(text, {chr(34): "&quot;"})}" fill="{color}" transform="translate({x} {y}) scale({size / UPM} {-size / UPM})">' + "".join(parts) + "</g>")
        key = (path, size)
        if key not in self.raster_fonts:
            self.raster_fonts[key] = ImageFont.truetype(str(path), size * 2, layout_engine=ImageFont.Layout.RAQM)
        self.draw.text((x * 2, y * 2), text, font=self.raster_fonts[key], fill=color, anchor="ls", language="en", features=[tag] if tag else [])

    def line(self, x1, y, x2, color="#dedede"):
        self.svg.append(f'<path d="M{x1} {y}H{x2}" fill="none" stroke="{color}"/>')
        self.draw.line((x1 * 2, y * 2, x2 * 2, y * 2), fill=color, width=2)

    def save(self, stem):
        (HERE / f"{stem}.svg").write_text("\n".join(self.svg + ["</svg>"]) + "\n")
        self.image.save(HERE / f"{stem}.png")
        for font in self.fonts.values():
            font.close()


def header(sheet, title, subtitle):
    sheet.text(80, 58, "ALLO / GLYPH STUDY 03", 15, "#626262")
    sheet.text(80, 116, title, 40)
    sheet.text(80, 155, subtitle, 18, "#626262")
    sheet.line(80, 187, 1720)


def build_sheets(clearance_report):
    sheet = Sheet(1340, "Allo g spacing: same Regular drawing, three round-follower spacings")
    header(sheet, "Same drawing, three spacings", "Regular / 400 · Only go, ge and gc tightened · The drawings are identical in A, B and C")
    for level, x in enumerate((80, 640, 1200)):
        label = ("A / CURRENT", "B / MODERATELY TIGHTER", "C / TIGHTER STILL")[level]
        tag = feature("round", level)
        sheet.text(x, 239, label, 20)
        sheet.text(x, 275, f"{AMOUNTS[400] * level if level else 0} units tighter after g before o / e / c", 16, "#626262")
        sheet.text(x, 428, "ago", 160, weight=400, tag=tag)
        sheet.text(x, 541, "go ge gc", 78, weight=400, tag=tag)
        sheet.text(x, 638, "going baggage", 54, weight=400, tag=tag)
        sheet.text(x, 712, "gecko gently", 54, weight=400, tag=tag)
        sheet.line(x, 752, x + 520)
        sheet.text(x, 788, "UNCHANGED GUARDS IN ROUND MODE", 13, "#626262")
        sheet.text(x, 839, "ga gn gr   gg gy gj", 38, weight=400, tag=tag)
        sheet.text(x, 893, "og ag ng   g. g, g)", 38, weight=400, tag=tag)
        for label_y, baseline, size, text in (
            (945, 982, 24, "A good beginning grows."),
            (1027, 1059, 16, "Good things grow gradually in the garden."),
            (1100, 1130, 12, "Going again, gathering baggage, belonging."),
        ):
            sheet.text(x, label_y, f"{size} PX", 12, "#626262")
            sheet.text(x, baseline, text, size, weight=400, tag=tag)
    sheet.line(80, 1200, 1720)
    sheet.text(80, 1240, "A is the study 02 double-storey g with inherited spacing. B and C are comparison values, not final kerning.", 18, "#626262")
    sheet.text(80, 1274, "No outline changes. The live page also tests all followers; that stronger blanket change can create overlaps.", 17, "#626262")
    sheet.save("proof")

    sheet = Sheet(2010, "Allo g spacing: three round-follower settings at all nine weights")
    header(sheet, "Spacing across the weights", "Only go, ge and gc tightened · All other followers unchanged · Same glyph drawings throughout")
    for x, text in ((80, "WEIGHT"), (310, "A / CURRENT"), (800, "B / MODERATE"), (1290, "C / TIGHTER")):
        sheet.text(x, 224, text, 16, "#626262")
    for index, (weight, style) in enumerate(STYLES.items()):
        y = 273 + index * 180
        sheet.line(80, y - 22, 1720, "#e9e9e9")
        sheet.text(80, y + 40, str(weight), 22)
        sheet.text(80, y + 72, style, 16, "#626262")
        for level, x in enumerate((310, 800, 1290)):
            tag = feature("round", level)
            sheet.text(x, y + 9, f"{AMOUNTS[weight] * level} units tighter", 13, "#626262")
            sheet.text(x, y + 74, "ago going", 56, weight=weight, tag=tag)
            sheet.text(x, y + 123, "gecko baggage", 32, weight=weight, tag=tag)
    sheet.line(80, 1920, 1720)
    sheet.text(80, 1960, "The trial reductions increase with weight: B is 40 / 48 / 64 units at Thin / Regular / Black; C doubles B.", 17, "#626262")
    sheet.save("weights")

    sheet = Sheet(1610, "Allo g spacing: Black guard pairs distinguish targeted spacing from blanket tightening")
    header(sheet, "Why the adjustment scope matters", "Black / 900 · Same amounts, different scope · A: 0 units; B: 64 units; C: 128 units tighter")
    for panel_y, mode, title in ((230, "round", "ROUND FOLLOWERS ONLY / go, ge, gc"),
                                 (870, "all", "ALL FOLLOWERS / DIAGNOSTIC STRESS TEST")):
        sheet.text(80, panel_y, title, 21)
        for level, x in enumerate((80, 640, 1200)):
            tag = feature(mode, level)
            sheet.text(x, panel_y + 42, ("A / CURRENT", "B / MODERATE", "C / TIGHTER")[level], 15, "#626262")
            for offset, size, text in ((119, 64, "go ge gc"), (190, 58, "ga gn gr"),
                                       (286, 72, "gg gy gj"), (365, 48, "g. g, g: g;"),
                                       (427, 48, "g) g] g!"), (489, 48, "og ag ng")):
                sheet.text(x, panel_y + offset, text, size, weight=900, tag=tag)
        sheet.line(80, panel_y + 540, 1720)
    black = clearance_report["weights"]["900"]["pairs"]
    overlap_pairs = [pair for pair, data in black.items() if data["all-followers"]["tighter"]["overlap_area"] > 1]
    sheet.text(80, 1490, "All-followers C produces actual outline overlaps in: " + ", ".join(overlap_pairs) + ". Round mode leaves these pairs unchanged.", 18, "#626262")
    sheet.text(80, 1527, f"All-followers B leaves gj about {black['gj']['all-followers']['moderate']['sampled_gap']:.1f} units of sampled horizontal clearance. No overlap does not guarantee good spacing.", 17, "#626262")
    sheet.save("pairs")


def validate_html(html):
    class Structure(HTMLParser):
        void = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

        def __init__(self):
            super().__init__()
            self.stack = []

        def handle_starttag(self, tag, attrs):
            if tag not in self.void:
                self.stack.append(tag)

        def handle_endtag(self, tag):
            assert self.stack and self.stack.pop() == tag, f"Unbalanced HTML at </{tag}>"

    parser = Structure()
    parser.feed(html)
    parser.close()
    assert not parser.stack, parser.stack
    assert html.count("<script>") == html.count("</script>") == 1


def build_html():
    rules = [f"@font-face {{font-family:SpacingProof;font-weight:{weight};font-style:normal;src:url(data:font/woff2;base64,{study02.study01.webfont(path)}) format('woff2')}}"
             for weight, path in OUTPUTS.items()]
    config = {"weights": [{"weight": w, "style": style, "moderate": AMOUNTS[w], "tighter": 2 * AMOUNTS[w]} for w, style in STYLES.items()]}
    html = page.render("\n".join(rules), config)
    validate_html(html)
    (HERE / "proof.html").write_text(html)


def main():
    if not shutil.which("hb-shape") or not features.check_feature("raqm"):
        raise SystemExit("Requires hb-shape and Pillow with libraqm, as in the preceding studies.")
    protected = [p for directory in (PREVIOUS, HERE.parent / "double-storey-g") for p in directory.rglob("*") if p.is_file()]
    before = {path: study02.digest(path) for path in protected}
    print("Building nine GPOS-only diagnostic fonts and checking every unchanged outline…", flush=True)
    fonts = [build_font(weight) for weight in STYLES]
    print("Measuring pair clearances and checking actual outline intersections…", flush=True)
    clearances = clearance.analyze(SOURCES, AMOUNTS)
    for weight, data in clearances["weights"].items():
        data["font"] = str(SOURCES[int(weight)].relative_to(ROOT))
    (HERE / "clearances.json").write_text(json.dumps(clearances, indent=2) + "\n")
    build_sheets(clearances)
    build_html()
    assert all(study02.digest(path) == checksum for path, checksum in before.items())
    report = {
        "scope": "Spacing-only comparison on all nine study 02 upright drawings; no outline changes",
        "trial_anchors": ANCHORS,
        "features": {tag: {"scope": mode, "multiple_of_moderate": multiple} for tag, (mode, multiple) in TAGS.items()},
        "round_followers": sorted(ROUND_FOLLOWERS), "fonts": fonts,
        "shaping_comparisons": len(STYLES) * len(TEST_TEXTS) * 5,
        "all_previous_study_files_sha256_unchanged": True,
        "clearance_warnings": clearances["warnings"],
        "checks_passed": [
            "All 737 glyph drawings, including every g, unchanged in all nine fonts",
            "hmtx, hhea, GSUB and GDEF tables unchanged",
            "All existing GPOS lookups, feature records and script feature-index prefixes preserved",
            "Exactly four optional GPOS lookups/features appended; all off by default",
            "Source and proof default shaping identical for every test string",
            "All four feature states change only the expected g advances by the exact trial amounts",
            "Round mode leaves descender, punctuation, preceding-letter and word-boundary controls unchanged",
            "HTML tag balance and single script boundary checked before writing",
            "Both previous proof directories preserved byte-for-byte during the build",
        ],
        "limitations": [
            "Experimental ss17–ss20 positioning features, not production ss04 or final kerning",
            "Round mode covers only plain g followed by unaccented o, e or c",
            "All-followers SinglePos models a right-sidebearing reduction; hmtx remains unchanged",
            "All-followers tight settings intentionally expose crowding and some actual overlaps",
            "Clearance is a sampled horizontal envelope distance, not Euclidean distance or legibility",
            "No accent, oblique, optical-size, roundness or variable-font integration",
            "Study 02 hinting is preserved; its new g remains unhinted",
        ],
    }
    (HERE / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    overlaps = [w for w in clearances["warnings"] if "ink_overlap" in w["reasons"]]
    print(f"Passed: {sum(f['unchanged_glyph_outlines_including_g'] for f in fonts)} preserved outlines; {report['shaping_comparisons']} shaping checks.")
    print(f"Diagnostic results: {len(clearances['warnings'])} close/overlap warnings, including {len(overlaps)} actual overlap cases. These are recorded, not hidden.")
    print(f"Wrote spacing sheets, interactive proof and validation reports to {HERE}")


if __name__ == "__main__":
    main()
