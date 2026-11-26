#!/usr/bin/env python3
"""Build study 07 text coverage using unchanged study 06 fonts; never rebuild prior proofs."""
from __future__ import annotations

import base64
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True

from fontTools.pens.areaPen import AreaPen
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PREVIOUS = HERE.parent / "double-storey-g-incoming-spacing"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


study06 = load_module("coverage_incoming_source", PREVIOUS / "build_proof.py")
corpus = load_module("g_coverage_corpus", HERE / "corpus.py")
page = load_module("g_coverage_page", HERE / "page.py")
digest = study06.digest
STYLES = study06.STYLES
FONTS = study06.FONTS
FEATURES = {f"ss{i}": int(f"ss{i}" in page.ACTIVE) for i in range(11, 21)}
STRINGS = corpus.test_strings()
GEOMETRY_PAIRS = list(dict.fromkeys([
    *(row["pair"] for row in corpus.ROWS), *corpus.CAPITAL_PAIRS, *corpus.PUNCTUATION_PAIRS,
]))


def protected_snapshot():
    result = study06.protected_snapshot()
    result.update({str(path.relative_to(ROOT)): digest(path)
                   for path in PREVIOUS.rglob("*") if path.is_file()})
    return result


def validate_corpus():
    data = corpus.inventory()
    assert data["counts"]["unique_lowercase_pairs"] == 51
    assert len(corpus.ROWS) == 52 and len(corpus.CAPITAL_PAIRS) == 26
    assert len(corpus.PARAGRAPHS) == 3
    assert corpus.FOCUS_WORDS == "Morning beginning changing going"
    for row in corpus.ROWS:
        assert all(row["pair"] in example for example in row["examples"])
        assert row["kind"] in ("word", "synthetic")
    assert FEATURES == {f"ss{i}": int(i in (12, 15, 17, 19)) for i in range(11, 21)}
    assert study06.SETTINGS["ng-tighter"] == (*study06.BASE, "ss12")
    return data


def validate_shaping():
    """Independently predict ng-only changes against study 05 for every authored run."""
    source_report = json.loads((PREVIOUS / "validation.json").read_text())
    source_hashes = {entry["weight"]: entry["font_sha256"] for entry in source_report["fonts"]}
    fonts = []
    for weight, path in FONTS.items():
        assert digest(path) == source_hashes[weight], (weight, "source hash")
        baseline_path = study06.SOURCES[weight]
        study06.shape_many(baseline_path, STRINGS, "current")
        study06.shape_many(path, STRINGS, "current")
        study06.shape_many(path, STRINGS, "ng-tighter")
        with TTFont(path, recalcTimestamp=False) as font:
            cmap = font.getBestCmap()
            missing = sorted({character for text in STRINGS for character in text if ord(character) not in cmap})
            assert not missing, (weight, "missing characters", missing)
            assert font["name"].getBestFamilyName() == "Allo G Incoming Study"
            assert font["OS/2"].usWeightClass == weight
            assert font["head"].unitsPerEm == 2048
        for text in STRINGS:
            original = study06.shape(baseline_path, text, "current")
            current = study06.shape(path, text, "current")
            actual = study06.shape(path, text, "ng-tighter")
            assert current == original, (weight, text, "approved baseline changed")
            expected = deepcopy(original)
            for index in range(len(expected) - 1):
                if original[index]["g"] == "n" and original[index + 1]["g"] == "g":
                    expected[index]["ax"] -= 2 * study06.SLIGHT[weight]
            assert actual == expected, (weight, text, "unexpected positioning")
            assert not any(record["g"] == ".notdef" for record in actual)
            assert [record for record in actual if record["g"] == "g"] == [
                record for record in original if record["g"] == "g"], (weight, text, "g advance/offset changed")
        fonts.append({"weight": weight, "style": STYLES[weight], "ng_tightening": 2 * study06.SLIGHT[weight],
                      "source": str(path.relative_to(ROOT)), "source_sha256": digest(path),
                      "baseline_source": str(baseline_path.relative_to(ROOT)), "baseline_sha256": digest(baseline_path),
                      "authored_runs_checked": len(STRINGS)})
    return fonts


def measure_geometry():
    clearance = study06.study03.clearance
    reference = json.loads((PREVIOUS / "clearances.json").read_text())
    report = {
        "scope": "Fixed stronger ng-only setting; all lowercase neighbours, capitals before g, and listed punctuation pairs",
        "measurement": reference["measurement"],
        "notes": [
            "Sampled horizontal envelope gaps are not exact Euclidean distances or optical judgments.",
            "Warnings request visual review; they never authorize a spacing edit or fail an otherwise valid coverage build.",
            "Word/space contexts are shaping-checked, not represented by this two-outline clearance metric.",
            "Capital and punctuation diagnostics are not an expansion of approved kerning scope.",
        ],
        "pairs_per_weight": len(GEOMETRY_PAIRS), "measurements": 0, "warnings": [], "weights": {},
    }
    for weight, path in FONTS.items():
        print(f"Measuring pair coverage at {weight}…", flush=True)
        measurements = {}
        with TTFont(path, recalcTimestamp=False) as font:
            glyphs, outlines = font.getGlyphSet(), {}
            for pair in GEOMETRY_PAIRS:
                shaped = study06.shape(path, pair, "ng-tighter")
                assert len(shaped) == 2, (weight, pair, shaped)
                names = [item["g"] for item in shaped]
                origins = study06.study05.study04.origins(shaped)
                for name in names:
                    if name not in outlines:
                        outlines[name] = clearance._Outline(glyphs, name, 1)
                first, second = [outlines[name] for name in names]
                gap, minimum_y, samples = clearance._sampled_gap(first, second, origins)
                intersection = first.positioned(*origins[0]).intersection(second.positioned(*origins[1]))
                area = AreaPen(None)
                intersection.draw(area)
                measurement = {"glyphs": names, "origins": origins, "sampled_gap": gap,
                               "overlap_area": abs(float(area.value)), "minimum_gap_y": minimum_y,
                               "common_y_samples": samples}
                measurements[pair] = measurement
                clearance._warn(report["warnings"], weight, pair, "ng-only", "tighter", measurement)
                report["measurements"] += 1
        report["weights"][str(weight)] = {"source_sha256": digest(path), "pairs": measurements}
    return report


def embedded_fonts():
    rules, records = [], []
    for weight, path in FONTS.items():
        buffer = io.BytesIO()
        with TTFont(path, recalcTimestamp=False) as font:
            font.flavor = "woff2"
            font.save(buffer)
        payload = buffer.getvalue()
        with TTFont(io.BytesIO(payload), recalcTimestamp=False) as web, TTFont(path, recalcTimestamp=False) as original:
            assert web["name"].getBestFamilyName() == "Allo G Incoming Study"
            assert web["name"].getBestSubFamilyName() == STYLES[weight]
            assert web["OS/2"].usWeightClass == weight
            for tag in ("CFF ", "GPOS", "GSUB", "GDEF", "hmtx", "hhea", "cmap", "name", "OS/2"):
                assert web.getTableData(tag) == original.getTableData(tag), (weight, tag, "webfont changed")
        encoded = base64.b64encode(payload).decode("ascii")
        rules.append(f"@font-face {{font-family:CoverageProof;font-weight:{weight};font-style:normal;src:url(data:font/woff2;base64,{encoded}) format('woff2')}}")
        records.append({"weight": weight, "woff2_bytes": len(payload),
                        "matching_tables": ["CFF ", "GPOS", "GSUB", "GDEF", "hmtx", "hhea", "cmap", "name", "OS/2"]})
    return "\n".join(rules), records


def main():
    if not shutil.which("hb-shape"):
        raise SystemExit("Requires hb-shape on PATH and the previous proof Python dependencies")
    protected = protected_snapshot()
    inventory = validate_corpus()
    print("Checking the complete authored corpus against unchanged study 06 fonts…", flush=True)
    fonts = validate_shaping()
    geometry = measure_geometry()
    font_rules, webfonts = embedded_fonts()
    config = {"weights": [{"weight": weight, "style": style, "tighter": 2 * study06.SLIGHT[weight]}
                          for weight, style in STYLES.items()], "paragraphs": corpus.PARAGRAPHS}
    html = page.render(font_rules, config, inventory)
    study06.study03.validate_html(html)
    (HERE / "proof.html").write_text(html)
    (HERE / "coverage.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n")
    (HERE / "clearances.json").write_text(json.dumps(geometry, indent=2) + "\n")
    assert protected_snapshot() == protected, "Production or a prior proof changed, appeared or disappeared"
    report = {
        "status": "passed", "scope": "Coverage review, not new spacing or production integration",
        "proof_sha256": digest(HERE / "proof.html"), "coverage_sha256": digest(HERE / "coverage.json"),
        "source_code_sha256": {name: digest(HERE / name) for name in ("build_proof.py", "corpus.py", "page.py")},
        "fonts": fonts, "embedded_fonts": webfonts, "features": FEATURES,
        "counts": {**inventory["counts"], "authored_runs": len(STRINGS),
                   "baseline_and_selected_shaping_comparisons": 2 * len(STRINGS) * len(STYLES),
                   "geometry_pairs_per_weight": len(GEOMETRY_PAIRS), "geometry_measurements": geometry["measurements"]},
        "geometry_warnings": geometry["warnings"],
        "protected_file_count": len(protected), "protected_files_sha256_unchanged": True,
        "checks_passed": [
            "All 52 lowercase coverage rows and 26 capital-before-g pairs are present, ordered and literal",
            "Every example contains its stated contiguous pair; invented contexts are explicitly labeled test strings",
            "Every authored character is mapped in every source font; no shaped .notdef glyphs",
            "Approved study 05 baseline preserved for every authored run; only n-before-g advance changes in selected state",
            "Every g advance and glyph offset retained, including ngj/ngo/nge/ngc controls",
            "All embedded font identities and drawing, metric, mapping and layout tables match unchanged study 06 OTFs",
            "HTML structure checked; all six earlier proofs and production files SHA-256 preserved",
        ],
        "limitations": [
            "Regular tighter ng is the reviewed preference; the other weights remain visual review candidates",
            "Plain Latin g and listed neighbours only; no accent, oblique, other opsz/ROND or variable-family coverage",
            "No shared-stem kerning adoption, automatic spacing optimization, font installation or production edit",
            "Sampled clearances and Boolean intersections are diagnostic, not optical approval",
            "Browser rendering and actual-size captures are checked separately in browser/validation.json",
        ],
    }
    (HERE / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Passed: {len(STRINGS)} authored runs × nine weights; {geometry['measurements']} pair measurements.")
    print(f"Coverage: 52 lowercase rows, 26 capital pairs; {len(geometry['warnings'])} geometric review flags.")
    print("Wrote proof.html and three reports only; no source fonts or prior proofs modified.")


if __name__ == "__main__":
    main()
