#!/usr/bin/env python3
"""Study 04: prove the selected C-round/B-other combination without editing fonts."""
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

from fontTools.pens.areaPen import AreaPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont, features

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PREVIOUS = HERE.parent / "double-storey-g-spacing"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


study03 = load_module("spacing_g_proof", PREVIOUS / "build_proof.py")
page = load_module("selected_spacing_page", HERE / "page.py")
STYLES, UPM = study03.STYLES, study03.UPM
FONTS, SOURCES = study03.OUTPUTS, study03.SOURCES
AMOUNTS, LABEL_FONT = study03.AMOUNTS, study03.LABEL_FONT
TAGS = ("ss17", "ss18", "ss19", "ss20")
SETTINGS = {
    "inherited": (),
    "rounds": ("ss20",),
    # B everywhere plus another B for rounds gives C, not the excessive B + C.
    "selected": ("ss17", "ss19"),
}
TEST_TEXTS = study03.TEST_TEXTS + (
    "gogego ggo ggg", "gA gV gW gT gY g1 g0", "gá gé gö gç gœ gø",
    "g g go og g", "going gently, baggage; eggy.",
)
SHAPED = {}
digest = study03.study02.digest


def shape_many(path, texts, state="inherited"):
    texts = tuple(texts)
    assert all("\n" not in text for text in texts)
    flags = ",".join(f"{tag}={int(tag in SETTINGS[state])}" for tag in TAGS)
    result = subprocess.run(
        ["hb-shape", "--font-size=2048", "--font-funcs=ot", "--shapers=ot",
         "--direction=ltr", "--script=latn", "--language=en", "--output-format=json",
         f"--features={flags}", str(path)],
        input="\n".join(texts) + "\n", check=True, capture_output=True,
        text=True, timeout=30,
    )
    lines = result.stdout.splitlines()
    assert len(lines) == len(texts), (path, state, len(lines), len(texts))
    for text, line in zip(texts, lines):
        SHAPED[path, text, state] = json.loads(line)


def shape(path, text, state="inherited"):
    key = (path, text, state)
    if key not in SHAPED:
        shape_many(path, [text], state)
    return SHAPED[key]


def reduction(base, index, amount, state):
    if base[index]["g"] != "g" or state == "inherited":
        return 0
    is_round = index + 1 < len(base) and base[index + 1]["g"] in study03.ROUND_FOLLOWERS
    if is_round:
        return 2 * amount
    return amount if state == "selected" else 0


def validate_fonts():
    previous = json.loads((PREVIOUS / "validation.json").read_text())
    previous_fonts = {entry["weight"]: entry for entry in previous["fonts"]}
    results = []
    for weight, style in STYLES.items():
        source, proof = SOURCES[weight], FONTS[weight]
        assert digest(source) == previous_fonts[weight]["source_sha256"]
        assert digest(proof) == previous_fonts[weight]["output_sha256"]
        with TTFont(source) as original, TTFont(proof) as candidate:
            assert original.getGlyphOrder() == candidate.getGlyphOrder()
            assert original.getBestCmap() == candidate.getBestCmap()
            assert candidate["name"].getBestFamilyName() == "Allo G Spacing Study"
            assert candidate["name"].getBestSubFamilyName() == style
            assert candidate["OS/2"].usWeightClass == weight
            old, new = original.getGlyphSet(), candidate.getGlyphSet()
            for name in original.getGlyphOrder():
                assert study03.study02.recording(old[name]) == study03.study02.recording(new[name]), (weight, name)
            for tag in ("hmtx", "hhea", "GSUB", "GDEF"):
                assert original.getTableData(tag) == candidate.getTableData(tag), (weight, tag)
            glyph_count = len(original.getGlyphOrder())
        shape_many(source, TEST_TEXTS)
        for state in SETTINGS:
            shape_many(proof, TEST_TEXTS, state)
            for text in TEST_TEXTS:
                base = shape(source, text)
                actual = shape(proof, text, state)
                expected = deepcopy(base)
                for index, item in enumerate(expected):
                    item["ax"] -= reduction(base, index, AMOUNTS[weight], state)
                assert actual == expected, (weight, state, text, actual, expected)
        results.append({
            "weight": weight, "style": style, "round_reduction": 2 * AMOUNTS[weight],
            "other_reduction": AMOUNTS[weight], "unchanged_glyph_outlines": glyph_count,
            "source": str(source.relative_to(ROOT)), "source_sha256": digest(source),
            "reused_font": str(proof.relative_to(ROOT)), "reused_font_sha256": digest(proof),
        })
    return results


def origins(shaped):
    x = y = 0
    result = []
    for item in shaped:
        result.append([x + item["dx"], y + item["dy"]])
        x += item["ax"]
        y += item["ay"]
    return result


def analyze_selected():
    reference_path = PREVIOUS / "clearances.json"
    reference = json.loads(reference_path.read_text())
    report = {
        "scope": "Actual selected ss17 + ss19 positioning; C rounds, B other g advances",
        "measurement": deepcopy(reference["measurement"]),
        "shaping": {**reference["shaping"], "features": "ss17=1,ss18=0,ss19=1,ss20=0"},
        "reference": str(reference_path.relative_to(ROOT)), "reference_sha256": digest(reference_path),
        "verification": "Fresh sampled gaps and BooleanGlyph intersections at actual combined-feature glyph origins; cross-checked against the corresponding study 03 states",
        "weights": {}, "warnings": [],
    }
    for weight in STYLES:
        old = reference["weights"][str(weight)]
        assert old["sha256"] == digest(SOURCES[weight])
        assert old["amounts"] == {"moderate": AMOUNTS[weight], "tighter": 2 * AMOUNTS[weight]}
        pairs = {}
        with TTFont(FONTS[weight]) as font:
            assert font["head"].unitsPerEm == UPM
            glyph_set = font.getGlyphSet()
            names = {name for entry in old["pairs"].values() for name in entry["glyphs"]}
            outlines = {name: study03.clearance._Outline(glyph_set, name, 1) for name in names}
            for pair, entry in old["pairs"].items():
                base = shape(FONTS[weight], pair)
                selected = shape(FONTS[weight], pair, "selected")
                names = [item["g"] for item in selected]
                assert names == entry["glyphs"] and len(names) == 2
                assert origins(base) == entry["baseline_origins"]
                round_pair = pair[0] == "g" and pair[1] in study03.ROUND_FOLLOWERS
                mode, level = ("round-followers", "tighter") if round_pair else ("all-followers", "moderate")
                previous_measurement = entry[mode][level]
                positioned = origins(selected)
                expected_origins = deepcopy(entry["baseline_origins"])
                expected_origins[1][0] += previous_measurement["second_dx"]
                assert positioned == expected_origins, (weight, pair, positioned, expected_origins)
                first, second = [outlines[name] for name in names]
                gap, gap_y, samples = study03.clearance._sampled_gap(first, second, positioned)
                intersection = first.positioned(*positioned[0]).intersection(second.positioned(*positioned[1]))
                area = AreaPen(None)
                intersection.draw(area)
                overlap = abs(float(area.value))
                assert abs(overlap - previous_measurement["overlap_area"]) <= 1, (weight, pair)
                if gap is None:
                    assert previous_measurement["sampled_gap"] is None
                else:
                    assert abs(gap - previous_measurement["sampled_gap"]) < 1e-6, (weight, pair)
                measurement = {
                    "second_dx": positioned[1][0] - entry["baseline_origins"][1][0],
                    "sampled_gap": gap, "overlap_area": overlap,
                }
                pairs[pair] = {
                    "glyphs": names, "selected_origins": positioned,
                    "common_y_samples": samples, "minimum_gap_y": gap_y,
                    "baseline": entry["baseline"], "selected": measurement,
                    "equivalent_study03_state": {"mode": mode, "level": level},
                }
                study03.clearance._warn(report["warnings"], weight, pair, "combined", "selected", measurement)
        report["weights"][str(weight)] = {
            "font": str(FONTS[weight].relative_to(ROOT)), "sha256": digest(FONTS[weight]),
            "round_reduction": 2 * AMOUNTS[weight], "other_reduction": AMOUNTS[weight], "pairs": pairs,
        }
    assert {(item["weight"], item["pair"]) for item in report["warnings"]} == {(800, "gj"), (900, "gj")}
    assert all("ink_overlap" not in item["reasons"] for item in report["warnings"])
    return report


class Sheet:
    def __init__(self, height, title):
        self.width, self.height = 1800, height
        self.fonts = {path: TTFont(path) for path in (*FONTS.values(), LABEL_FONT)}
        self.paths, self.raster_fonts = {}, {}
        self.svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="{height}" viewBox="0 0 1800 {height}">',
                    f'<title>{escape(title)}</title>', '<rect width="100%" height="100%" fill="white"/>']
        self.image = Image.new("RGB", (self.width * 2, height * 2), "white")
        self.draw = ImageDraw.Draw(self.image)

    def text(self, x, y, text, size=18, color="#191919", weight=None, state="inherited", max_width=None):
        path = LABEL_FONT if weight is None else FONTS[weight]
        glyphs = self.fonts[path].getGlyphSet()
        cursor, parts = 0, []
        for item in shape(path, text, state):
            name = item["g"]
            assert name != ".notdef", text
            key = (path, name)
            if key not in self.paths:
                pen = SVGPathPen(glyphs)
                glyphs[name].draw(pen)
                self.paths[key] = pen.getCommands()
            parts.append(f'<path transform="translate({cursor + item["dx"]} {item["dy"]})" d="{self.paths[key]}"/>')
            cursor += item["ax"]
        width = cursor * size / UPM
        assert x + width <= self.width - 60, text
        if max_width is not None:
            assert width <= max_width, (text, width, max_width)
        self.svg.append(f'<g aria-label="{escape(text, quote=True)}" fill="{color}" transform="translate({x} {y}) scale({size / UPM} {-size / UPM})">' + "".join(parts) + "</g>")
        key = (path, size)
        if key not in self.raster_fonts:
            self.raster_fonts[key] = ImageFont.truetype(str(path), size * 2, layout_engine=ImageFont.Layout.RAQM)
        flags = [tag if tag in SETTINGS[state] else "-" + tag for tag in TAGS]
        self.draw.text((x * 2, y * 2), text, font=self.raster_fonts[key], fill=color, anchor="ls", language="en", features=flags)
        return width

    def line(self, x1, y, x2, color="#dedede"):
        self.svg.append(f'<path d="M{x1} {y}H{x2}" fill="none" stroke="{color}"/>')
        self.draw.line((x1 * 2, y * 2, x2 * 2, y * 2), fill=color, width=2)

    def boundary(self, x, y, text, size, weight, state):
        end = x + self.text(x, y, text, size, weight=weight, state=state)
        self.svg.append(f'<path d="M{end} {y - size}V{y + 12}" fill="none" stroke="#999"/>')
        self.draw.line((end * 2, (y - size) * 2, end * 2, (y + 12) * 2), fill="#999", width=2)

    def save(self, stem):
        (HERE / f"{stem}.svg").write_text("\n".join(self.svg + ["</svg>"]) + "\n")
        self.image.save(HERE / f"{stem}.png")
        for font in self.fonts.values():
            font.close()


def header(sheet, title, subtitle):
    sheet.text(80, 58, "ALLO / GLYPH STUDY 04", 15, "#626262")
    sheet.text(80, 116, title, 40)
    sheet.text(80, 155, subtitle, 18, "#626262")
    sheet.line(80, 187, 1720)


COLUMNS = (("inherited", "INHERITED"), ("rounds", "C / ROUND FOLLOWERS ONLY"), ("selected", "SELECTED / C ROUNDS + B OTHERS"))


def build_sheets(clearances):
    sheet = Sheet(1340, "Allo selected spacing: C for round followers, B for other g advances")
    header(sheet, "C for rounds, B for the others", "Regular / 400 · Same drawings · Selected combination in the right-hand column")
    for (state, title), x in zip(COLUMNS, (80, 640, 1200)):
        sheet.text(x, 239, title, 18, max_width=520)
        description = {"inherited": "No additional reduction", "rounds": "96 units before o / e / c; otherwise unchanged", "selected": "96 units before o / e / c; 48 units otherwise"}[state]
        sheet.text(x, 275, description, 16, "#626262", max_width=520)
        for baseline, size, text in ((428, 160, "ago"), (541, 78, "go ge gc"),
                                     (638, 54, "going baggage"), (712, 54, "gecko gently")):
            sheet.text(x, baseline, text, size, weight=400, state=state, max_width=520)
        sheet.line(x, 752, x + 520)
        sheet.text(x, 788, "OTHER FOLLOWERS AND GUARDS", 13, "#626262")
        sheet.text(x, 839, "ga gn gr   gg gy gj", 38, weight=400, state=state, max_width=520)
        sheet.text(x, 893, "og ag ng   g. g, g)", 38, weight=400, state=state, max_width=520)
        for label_y, baseline, size, text in ((945, 982, 24, "A good beginning grows."),
                                            (1027, 1059, 16, "Good things grow gradually in the garden."),
                                            (1100, 1130, 12, "Going again, gathering baggage, belonging.")):
            sheet.text(x, label_y, f"{size} PX", 12, "#626262")
            sheet.text(x, baseline, text, size, weight=400, state=state, max_width=520)
    sheet.line(80, 1200, 1720)
    sheet.text(80, 1240, "The selected setting includes B before spaces and on terminal g. No outlines, hmtx metrics or production files changed.", 17, "#626262")
    sheet.text(80, 1274, "No overlaps in the tested selected pairs; gj remains close at ExtraBold and Black. No exception has been silently added.", 17, "#626262")
    sheet.save("proof")

    sheet = Sheet(2190, "Allo selected C-round/B-other spacing at all nine weights")
    header(sheet, "Selected spacing across the weights", "Same drawings · Round pairs retain C · Other g advances receive B in the selected column")
    sheet.text(80, 224, "WEIGHT", 16, "#626262")
    for (_, title), x in zip(COLUMNS, (310, 800, 1290)):
        sheet.text(x, 224, title, 14, "#626262", max_width=430)
    for index, (weight, style) in enumerate(STYLES.items()):
        y = 273 + index * 200
        sheet.line(80, y - 22, 1720, "#e9e9e9")
        sheet.text(80, y + 40, str(weight), 22)
        sheet.text(80, y + 72, style, 16, "#626262")
        for (state, _), x in zip(COLUMNS, (310, 800, 1290)):
            b = AMOUNTS[weight]
            caption = {"inherited": "0 units", "rounds": f"Rounds: {2 * b}; others: 0", "selected": f"Rounds: {2 * b}; others: {b}"}[state]
            sheet.text(x, y + 9, caption, 13, "#626262")
            for offset, size, text in ((74, 56, "ago going"), (118, 32, "garden eggy"), (153, 24, "gg gy gj   g. g)")):
                sheet.text(x, y + offset, text, size, weight=weight, state=state, max_width=430)
    sheet.line(80, 2100, 1720)
    sheet.text(80, 2140, "B = 40 / 48 / 64 units at Thin / Regular / Black; C = twice B. gj needs close review at weights 800 and 900.", 17, "#626262")
    sheet.save("weights")

    sheet = Sheet(1300, "Allo selected spacing: Black round, other, descender, punctuation and boundary checks")
    header(sheet, "The combined setting, under stress", "Black / 900 · C = 128 units; B = 64 units · No outlines changed; no exceptions added")
    for (state, title), x in zip(COLUMNS, (80, 640, 1200)):
        sheet.text(x, 239, title, 18, max_width=520)
        for baseline, size, text in ((365, 84, "go ge gc"), (470, 76, "ga gn gr"),
                                     (605, 88, "gg gy gj"), (725, 64, "g. g, g: g;"),
                                     (825, 64, "g) g] g!"), (945, 64, "og ag ng")):
            sheet.text(x, baseline, text, size, weight=900, state=state, max_width=520)
        sheet.boundary(x, 1050, "g g", 64, 900, state)
        sheet.text(x, 1095, "The rule marks the text-run end.", 15, "#626262")
    sheet.line(80, 1140, 1720)
    black_gap = clearances["weights"]["900"]["pairs"]["gj"]["selected"]["sampled_gap"]
    extra_gap = clearances["weights"]["800"]["pairs"]["gj"]["selected"]["sampled_gap"]
    sheet.text(80, 1180, f"Selected gj clearance: {black_gap:.1f} units at Black, {extra_gap:.1f} at ExtraBold. No computed overlap, but little breathing room.", 18, "#626262")
    sheet.text(80, 1220, "The selected column is B overall plus one extra B before o / e / c: exactly C for rounds, not B plus C.", 17, "#626262")
    sheet.save("pairs")


def build_html():
    rules = [f"@font-face {{font-family:SpacingProof;font-weight:{weight};font-style:normal;src:url(data:font/woff2;base64,{study03.study02.study01.webfont(path)}) format('woff2')}}"
             for weight, path in FONTS.items()]
    config = {"weights": [{"weight": weight, "style": style, "moderate": AMOUNTS[weight], "tighter": 2 * AMOUNTS[weight]}
                          for weight, style in STYLES.items()]}
    html = page.render("\n".join(rules), config)
    study03.validate_html(html)
    faces = re.findall(r"@font-face\s*\{font-family:SpacingProof;font-weight:(\d+);font-style:normal;src:url\(data:font/woff2;base64,([A-Za-z0-9+/=]+)\)", html)
    assert len(faces) == 9 and {int(weight) for weight, _ in faces} == set(STYLES)
    for weight_text, encoded in faces:
        weight = int(weight_text)
        with TTFont(io.BytesIO(base64.b64decode(encoded, validate=True))) as web, TTFont(FONTS[weight]) as otf:
            assert web["name"].getBestFamilyName() == "Allo G Spacing Study"
            assert web["name"].getBestSubFamilyName() == STYLES[weight]
            assert web["OS/2"].usWeightClass == weight
            for tag in ("CFF ", "GPOS", "GSUB", "GDEF", "hmtx", "hhea"):
                assert web.getTableData(tag) == otf.getTableData(tag), (weight, tag)
    (HERE / "proof.html").write_text(html)


def protected_snapshot():
    directories = [HERE.parent / name for name in ("double-storey-g", "double-storey-g-weights", "double-storey-g-spacing")]
    directories += [ROOT / "sources", ROOT / "fonts"]
    files = [path for directory in directories for path in directory.rglob("*") if path.is_file()]
    files += [ROOT / name for name in ("build.py", "requirements.txt", "README.md")]
    return {str(path.relative_to(ROOT)): digest(path) for path in files}


def main():
    if not shutil.which("hb-shape") or not features.check_feature("raqm"):
        raise SystemExit("Requires hb-shape and Pillow with libraqm, as in the preceding studies.")
    protected = protected_snapshot()
    print("Checking unchanged fonts and the exact C-round/B-other combination at all nine weights…", flush=True)
    fonts = validate_fonts()
    print("Measuring actual combined-feature pair origins, clearances and intersections…", flush=True)
    clearances = analyze_selected()
    build_sheets(clearances)
    build_html()
    assert protected_snapshot() == protected, "A protected file changed, appeared or disappeared"
    (HERE / "clearances.json").write_text(json.dumps(clearances, indent=2) + "\n")
    checks = len(STYLES) * len(TEST_TEXTS) * len(SETTINGS)
    outlines = sum(entry["unchanged_glyph_outlines"] for entry in fonts)
    report = {
        "decision": "User selected C for round followers and B for others; applied in a separate proof, not production",
        "features": {state: {tag: int(tag in active) for tag in TAGS} for state, active in SETTINGS.items()},
        "round_followers": sorted(study03.ROUND_FOLLOWERS),
        "boundary_policy": "B applies before spaces and on terminal plain g, matching study 03 all-followers B",
        "fonts": fonts, "fonts_written": 0, "unchanged_outlines": outlines,
        "test_strings": len(TEST_TEXTS), "shaping_comparisons": checks,
        "geometric_pair_checks": sum(len(entry["pairs"]) for entry in clearances["weights"].values()),
        "warnings": clearances["warnings"],
        "protected_files_sha256_unchanged": True, "protected_file_count": len(protected),
        "checks_passed": [
            "All study 02 outlines preserved in the reused study 03 fonts; hmtx, hhea, GSUB and GDEF unchanged",
            "All three states produce exactly the expected advances with unchanged glyph sequences and offsets",
            "Selected round reductions are exactly C, not B plus C; every other plain g advance is reduced by B",
            "Combined-feature pair origins match the corresponding study 03 positions",
            "Fresh sampled clearances and numerical BooleanGlyph intersections agree with study 03 diagnostics",
            "All nine embedded WOFF2 identities, weights, outlines, metrics and layout tables verified against reused OTFs",
            "HTML tag balance and single script boundary checked",
            "All three previous studies, production sources/fonts and root build/config files preserved byte-for-byte",
        ],
        "limitations": [
            "No production integration or production ss04; reused OTF defaults still have all trial features off",
            "Only plain g, with additional C tightening limited to unaccented o/e/c; no accent or oblique integration",
            "Only nine upright Text/Friendly weights; no variable, optical-size or roundness extension",
            "Study 02 hinting inherited; new g remains unhinted",
            "gj at 800 and 900 remains below the sampled-clearance review threshold; no exceptions added",
            "No intersection in tested pairs is not a universal collision or legibility guarantee",
            "UI logic tests are separate mocked-DOM checks, not real-browser rendering validation",
        ],
    }
    (HERE / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Passed: {outlines} unchanged outlines, {checks} shaping checks, {report['geometric_pair_checks']} geometric pair checks.")
    print(f"Selected result: no tested overlaps; {len(clearances['warnings'])} close-clearance warnings (gj at 800 and 900).")
    print(f"Reused nine fonts without modification. Wrote selected-spacing proof to {HERE}")


if __name__ == "__main__":
    main()
