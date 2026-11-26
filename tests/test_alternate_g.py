"""Exercise the real authoring integration without saving any production UFO.

Run with .venv/bin/python -B -m unittest discover -s tests -p test_alternate_g.py.
Binary/release comparisons live in validate_g.py and require a completed custom build.
"""
from __future__ import annotations

import math
import shutil
import tempfile
import unittest
from collections import Counter
from copy import deepcopy
from pathlib import Path

from booleanOperations.booleanGlyph import BooleanGlyph
from fontTools.designspaceLib import DesignSpaceDocument
from fontTools.misc.roundTools import otRound
from fontTools.pens.areaPen import AreaPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
import ufoLib2
from ufoLib2.objects import Glyph

import alternate_g as author
import validate_g as validator

ROOT = Path(__file__).resolve().parents[1]
FAMILY = ("g", "gcircumflex", "gbreve", "gdotaccent", "gcommaaccent")
ALTS = tuple(name + ".ss04" for name in FAMILY)
WEIGHTS = dict(zip(range(100, 901, 100), (
    "Thin", "ExtraLight", "Light", "Regular", "Medium", "SemiBold", "Bold", "ExtraBold", "Black",
)))
DESIGN = {100: 100, 200: 200, 300: 300, 400: 400, 500: 490,
          600: 580, 700: 670, 800: 780, 900: 900}
B = {100: 40, 200: 43, 300: 45, 400: 48, 500: 51, 600: 54, 700: 57, 800: 60, 900: 64}
MARKS = dict(zip(FAMILY[1:], ("circumflexcomb", "brevecomb", "dotaccentcomb", "commaaccentrotate.cn")))
PROOF = ROOT / "documentation/proofs/double-storey-g-weights"


def recording(glyph, glyphs=None):
    pen = DecomposingRecordingPen(glyphs)
    glyph.draw(pen)
    return pen.value


def area(outline):
    pen = AreaPen(None)
    outline.draw(pen)
    return pen.value


def box(outline, glyphs=None):
    pen = BoundsPen(glyphs)
    outline.draw(pen)
    return pen.bounds


def anchor_map(glyph):
    return {a.name: (a.x, a.y) for a in glyph.anchors}


def topology(glyph):
    # Smooth flags are editor hints, not interpolation topology.
    return tuple(tuple(p.type for p in c.points) for c in glyph.contours)


def points(glyph):
    return [(p.x, p.y) for c in glyph.contours for p in c.points]


def state(font):
    return (deepcopy([font[n] for n in ALTS]), font.features.text,
            deepcopy(font.lib), deepcopy(font.groups), dict(font.kerning))


def files(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


class GeometryAssertions(unittest.TestCase):
    def assertSafe(self, glyph):
        self.assertEqual(len(glyph.contours), 3)
        signed = [area(c) for c in glyph.contours]
        self.assertGreater(signed[0], 0)
        for value in signed[1:]:
            self.assertLess(value, 0)
        cleaned = BooleanGlyph(glyph).removeOverlap()
        self.assertEqual(len(cleaned.contours), 3, "union changed the outer/two-counter topology")
        self.assertAlmostEqual(area(cleaned), area(glyph), delta=1,
                               msg="union changed filled area (crossing/overlap)")
        outer = Glyph()
        outer.contours = [deepcopy(glyph.contours[0])]
        counters = []
        for contour in glyph.contours[1:]:
            x0, y0, x1, y1 = box(contour)
            self.assertGreater(x1 - x0, 100, "collapsed counter width")
            self.assertGreater(y1 - y0, 100, "collapsed counter height")
            counter = Glyph()
            counter.contours = [deepcopy(contour)]
            counters.append(BooleanGlyph(counter))
            outside = counters[-1].difference(BooleanGlyph(outer))
            self.assertLess(abs(area(outside)), 1, "counter escapes the outer contour")
        self.assertLess(abs(area(counters[0].intersection(counters[1]))), 1,
                        "counters overlap one another")

    def assertAccents(self, font):
        base, old = anchor_map(font["g.ss04"]), anchor_map(font["g"])
        self.assertEqual(set(base), {"top", "bottom", "cross", "topr"})
        dx, dy = (a - b for a, b in zip(base["top"], old["top"]))
        for original, accent in MARKS.items():
            with self.subTest(accent=original):
                glyph, source = font[original + ".ss04"], font[original]
                self.assertFalse(glyph.unicodes)
                self.assertFalse(glyph.contours)
                self.assertAlmostEqual(source.width - glyph.width,
                                       font["g"].width - font["g.ss04"].width)
                self.assertEqual([c.baseGlyph for c in glyph.components], ["g.ss04", accent])
                self.assertEqual(tuple(glyph.components[0].transformation),
                                 tuple(source.components[0].transformation))
                expected = list(source.components[1].transformation)
                expected[4] += dx
                expected[5] += dy
                self.assertEqual(tuple(glyph.components[1].transformation), tuple(expected))
                new_anchors, old_anchors = anchor_map(glyph), anchor_map(source)
                self.assertEqual(set(new_anchors), set(old_anchors))
                for name in set(new_anchors) - {"top"}:
                    self.assertEqual(new_anchors[name], base[name])
                self.assertEqual(new_anchors["top"][0], old_anchors["top"][0] + dx)
                if original == "gcommaaccent":
                    self.assertNotIn("top", anchor_map(font[accent]))
                    accent_top = box(font[accent], font)[3] + expected[5]
                    self.assertEqual(new_anchors["top"][1], math.ceil(accent_top) + 2)
                    self.assertGreater(new_anchors["top"][1], base["top"][1],
                                       "a following mark must stack above the rotated comma")
                else:
                    self.assertEqual(new_anchors["top"][1], old_anchors["top"][1] + dy)


class MasterTests(GeometryAssertions):
    def test_controls_are_byte_identical_to_approved_drawings(self):
        for style in ("Thin", "Regular", "Black"):
            with self.subTest(style=style):
                self.assertEqual((author.CONTROLS / f"{style}.glif").read_bytes(),
                                 (PROOF / f"masters/{style}.glif").read_bytes())
        controls = author.control_drawings()
        self.assertEqual(set(controls), {100, 400, 900})
        for glyph in controls.values():
            self.assertFalse(glyph.unicodes)
            self.assertFalse(glyph.components)
            self.assertEqual([len(c.points) for c in glyph.contours], [71, 12, 13])
        self.assertEqual(topology(controls[100]), topology(controls[400]))
        self.assertEqual(topology(controls[900]), topology(controls[400]))

    def test_all_48_master_locations_topology_safety_roundness_small_and_accents(self):
        ds = DesignSpaceDocument.fromfile(ROOT / "sources/Allo.designspace")
        sources = [s for s in ds.sources if s.layerName is None]
        expected_locations = {(s, w, r) for s in (9, 14, 20, 32)
                              for w in (100, 400, 580, 900) for r in (0, 50, 100)}
        self.assertEqual(len(sources), 48)
        self.assertEqual({tuple(s.location[k] for k in ("Optical size", "Weight", "Roundness"))
                          for s in sources}, expected_locations)
        controls = author.control_drawings()
        before_controls = deepcopy(controls)
        drawings = {}
        for source in sources:
            size, weight, rond = (source.location[k] for k in ("Optical size", "Weight", "Roundness"))
            with self.subTest(location=(size, weight, rond)), ufoLib2.Font.open(source.path) as font, \
                    ufoLib2.Font.open(ROOT / f"sources/masters/Allo-opsz14-wght{weight:g}-ROND50.ufo") as reference:
                old = {n: deepcopy(font[n]) for n in (*FAMILY, "o", *MARKS.values())}
                author.add_upright(font, reference, weight, rond, controls, small_shift=17 if size == 9 else 0)
                glyph = font["g.ss04"]
                self.assertEqual(topology(glyph), topology(controls[400]))
                self.assertTrue(all(math.isfinite(v) for point in points(glyph) for v in point))
                expected_b = 40 + (weight - 100) * 8 / 300 if weight <= 400 else 48 + (weight - 400) * 16 / 500
                self.assertAlmostEqual(font["g"].width - glyph.width, expected_b)
                self.assertSafe(glyph)
                self.assertAccents(font)
                self.assertEqual({n: font[n] for n in old}, old, "authoring changed an existing glyph")
                for name in ALTS:
                    self.assertFalse(font[name].unicodes)
                    self.assertEqual(font.lib["public.openTypeCategories"][name], "base")
                drawings[size, weight, rond] = deepcopy(glyph)
        self.assertEqual(controls, before_controls, "shared controls were mutated")
        for weight in (100, 400, 580, 900):
            for rond in (0, 50, 100):
                with self.subTest(relationship="Small/Text", weight=weight, roundness=rond):
                    text, small = drawings[14, weight, rond], drawings[9, weight, rond]
                    self.assertEqual(small.width, text.width + 34)
                    for a, b in zip(points(text), points(small)):
                        self.assertAlmostEqual(b[0] - a[0], 17)
                        self.assertEqual(b[1], a[1])
                    for name, (x, y) in anchor_map(text).items():
                        self.assertAlmostEqual(anchor_map(small)[name][0] - x, 17)
                        self.assertEqual(anchor_map(small)[name][1], y)
            for size in (9, 14, 20, 32):
                sharp, friendly, rounded = (drawings[size, weight, r] for r in (0, 50, 100))
                self.assertNotEqual(points(sharp), points(friendly))
                self.assertNotEqual(points(rounded), points(friendly))
                self.assertEqual(sharp.width, friendly.width)
                self.assertEqual(rounded.width, friendly.width)
                # Isolate the corner operation: native o proportions can also
                # change with ROND during the preceding optical-size adaptation.
                for rond in (0, 100):
                    corners_only = deepcopy(friendly)
                    author.roundness(corners_only, rond)
                    for index in (1, 2):
                        self.assertEqual(corners_only.contours[index], friendly.contours[index])
            self.assertNotEqual(points(drawings[14, weight, 50]), points(drawings[32, weight, 50]))


class StaticTests(GeometryAssertions):
    @classmethod
    def setUpClass(cls):
        cls.controls = author.control_drawings()
        cls.fonts = {}
        for weight, style in WEIGHTS.items():
            font = ufoLib2.Font.open(ROOT / f"sources/static/Allo-{style}.ufo")
            cls.addClassCleanup(font.close)
            author.add_upright(font, font, DESIGN[weight], 50, cls.controls, static=True)
            cls.fonts[weight] = font

    def test_nine_text_friendly_outlines_are_exact_approved_proof_with_b_width(self):
        for weight, font in self.fonts.items():
            with self.subTest(weight=weight), TTFont(PROOF / f"fonts/AlloGWeightStudy-{WEIGHTS[weight]}.otf") as proof:
                self.assertEqual(recording(font["g.ss04"]), recording(proof.getGlyphSet()["g"]))
                self.assertEqual(otRound(font["g.ss04"].width), proof["hmtx"]["g"][0] - B[weight])
                self.assertEqual(font["g"].width - font["g.ss04"].width, B[weight])
                self.assertSafe(font["g.ss04"])
                self.assertAccents(font)
                self.assertTrue(all(v == otRound(v) for point in points(font["g.ss04"]) for v in point))
                original = state(font)
                author.add_upright(font, font, DESIGN[weight], 50, self.controls, static=True)
                self.assertEqual(state(font), original, "upright integration is not idempotent")

    def test_nine_obliques_shear_actual_contours_and_relative_attachment_anchors(self):
        for weight, upright in self.fonts.items():
            style = ("" if weight == 400 else WEIGHTS[weight]) + "Oblique"
            with self.subTest(style=style), ufoLib2.Font.open(ROOT / f"sources/static/Allo-{style}.ufo") as oblique:
                self.assertEqual(oblique.info.italicAngle, -9)
                original = {n: deepcopy(oblique[n]) for n in FAMILY}
                author.add_oblique(oblique, upright, DESIGN[weight])
                shear = math.tan(math.radians(9))
                pivot = upright.info.xHeight / 2
                reference_top = anchor_map(upright["g.ss04"])["top"][1]
                for name in ALTS:
                    a, b = upright[name], oblique[name]
                    self.assertFalse(b.components)
                    self.assertFalse(b.unicodes)
                    self.assertEqual(b.width, a.width)
                    decomposed = Glyph()
                    pen = DecomposingRecordingPen(upright)
                    a.draw(pen)
                    pen.replay(decomposed.getPen())
                    expected = DecomposingRecordingPen(None)
                    decomposed.draw(TransformPen(expected, (1, 0, shear, 1, -shear * pivot, 0)))
                    actual = recording(b)
                    self.assertEqual([op for op, _ in actual], [op for op, _ in expected.value])
                    for (_, aa), (_, bb) in zip(actual, expected.value):
                        for p, q in zip(aa, bb):
                            self.assertAlmostEqual(p[0], q[0], places=9)
                            self.assertAlmostEqual(p[1], q[1], places=9)
                    for anchor, (x, y) in anchor_map(a).items():
                        bx, by = anchor_map(b)[anchor]
                        self.assertEqual(by, y)
                        shift = shear * (y - reference_top) if anchor == "top" else shear * y if anchor == "bottom" else 0
                        self.assertAlmostEqual(bx - x, shift)
                    # A following top mark uses the difference from the base's top,
                    # not a second absolute shear about the outline pivot.
                    self.assertAlmostEqual(anchor_map(b)["top"][0] - anchor_map(oblique["g.ss04"])["top"][0],
                                           anchor_map(a)["top"][0] - anchor_map(upright["g.ss04"])["top"][0]
                                           + shear * (anchor_map(a)["top"][1] - reference_top))
                self.assertEqual({n: oblique[n] for n in FAMILY}, original)
                snapshot = state(oblique)
                author.add_oblique(oblique, upright, DESIGN[weight])
                self.assertEqual(state(oblique), snapshot)


class WriterTests(unittest.TestCase):
    def test_writer_is_narrow_and_byte_idempotent_in_temporary_ufo(self):
        controls = author.control_drawings()
        for relative in ("masters/Allo-opsz14-wght400-ROND50.ufo", "static/Allo-Regular.ufo"):
            with self.subTest(source=relative), tempfile.TemporaryDirectory(prefix="allo-alternate-g-") as temporary:
                path = Path(temporary) / "test.ufo"
                shutil.copytree(ROOT / "sources" / relative, path)
                (path / "data").mkdir(exist_ok=True)
                (path / "data/unrelated.bin").write_bytes(b"\x00unrelated application data\xff")
                before = files(path)
                with ufoLib2.Font.open(path) as font:
                    original = {n: deepcopy(font[n]) for n in font.keys() if n not in ALTS}
                    author.add_upright(font, font, 400, 50, controls, static=relative.startswith("static/"))
                    snapshot = state(font)
                    author.add_upright(font, font, 400, 50, controls, static=relative.startswith("static/"))
                    self.assertEqual(state(font), snapshot)
                    self.assertEqual({n: font[n] for n in original}, original)
                    author.write_family(path, font)
                import plistlib
                contents = plistlib.loads((path / "glyphs/contents.plist").read_bytes())
                allowed = {"features.fea", "groups.plist", "kerning.plist", "lib.plist", "glyphs/contents.plist",
                           *("glyphs/" + contents[n] for n in ALTS)}
                after = files(path)
                self.assertFalse(set(before) - set(after), "writer removed files")
                self.assertLessEqual(set(after) - set(before), allowed)
                for name in set(before) - allowed:
                    self.assertEqual(after[name], before[name], f"unowned file rewritten: {name}")
                with ufoLib2.Font.open(path) as reopened:
                    for name in ALTS:
                        self.assertFalse(reopened[name].unicodes)
                        self.assertEqual(reopened.lib["public.openTypeCategories"][name], "base")
                    author.add_upright(reopened, reopened, 400, 50, controls, static=relative.startswith("static/"))
                    author.write_family(path, reopened)
                self.assertEqual(files(path), after, "second narrow write changed bytes")


class ValidatorTests(unittest.TestCase):
    def test_missing_build_fails_deterministically_without_writing(self):
        with tempfile.TemporaryDirectory(prefix="allo-g-missing-build-") as temporary:
            root = Path(temporary)
            first = validator.validate(root)
            self.assertEqual(first, validator.validate(root))
            self.assertEqual(first["status"], "failed")
            self.assertIn("expected all 39", first["failures"][0]["error"])
            self.assertEqual(files(root), {})

    def test_unintegrated_font_is_not_silently_skipped(self):
        with tempfile.TemporaryDirectory(prefix="allo-g-unintegrated-") as temporary:
            root = Path(temporary)
            (root / "otf").mkdir()
            relative = Path("otf/AlloCustom-Regular.otf")
            shutil.copyfile(ROOT / "fonts/otf/Allo-Regular.otf", root / relative)
            report = {"counts": Counter()}
            check = validator.Validator(root, validator.HarfBuzz(root, report["counts"]), report)
            before = files(root)
            with self.assertRaisesRegex(validator.ValidationError, "ss04 missing"):
                check.font(relative)
            self.assertEqual(files(root), before)
            self.assertEqual(report["counts"]["validated_fonts"], 0)

    def test_counter_check_rejects_winding_collapse_escape_and_overlap(self):
        control = author.control_drawings()[400]
        counts = Counter()
        validator.check_counters(control, counts)
        self.assertEqual(counts["compiled_counter_checks"], 1)
        for defect in ("winding", "collapse", "escape", "overlap"):
            glyph = deepcopy(control)
            if defect == "winding":
                glyph.contours[1] = deepcopy(glyph.contours[0])
            elif defect == "collapse":
                for point in glyph.contours[1].points:
                    point.x *= 0.01
            elif defect == "escape":
                for point in glyph.contours[1].points:
                    point.x += 2000
            else:
                glyph.contours[2] = deepcopy(glyph.contours[1])
            with self.subTest(defect=defect), self.assertRaises(validator.ValidationError):
                validator.check_counters(glyph, counts)
        self.assertEqual(counts["compiled_counter_checks"], 1)

    def test_grid_covers_corners_intermediates_and_mapped_user_weights(self):
        grid = {tuple(p[k] for k in ("opsz", "wght", "ROND")) for p in validator.sample_grid()}
        self.assertEqual(len(grid), 153)
        self.assertTrue({(s, w, r) for s in (9, 32) for w in (100, 900) for r in (0, 100)} <= grid)
        self.assertTrue({(s, w, r) for s in (11.5, 23) for w in (500, 600, 700) for r in (25, 75)} <= grid)
        self.assertTrue({(14, w, 50) for w in WEIGHTS} <= grid)
        self.assertEqual(len(validator.sample_grid(True)), 33)
        self.assertTrue(all("ROND" not in p for p in validator.sample_grid(True)))

    def test_absolute_attachment_name_normalization_and_proof_tolerance_scope(self):
        def glyph(name, advance, dx=0):
            return {"g": name, "cl": 0, "ax": advance, "ay": 0, "dx": dx, "dy": 0}

        old = [glyph("g", 1200), glyph("acutecomb", 0, -838)]
        new = [glyph("g.ss04", 1152), glyph("acutecomb", 0, -790)]
        self.assertNotEqual(old[1]["dx"], new[1]["dx"])
        self.assertEqual(validator.origins(old), validator.origins(new))
        self.assertEqual(validator.normalized(new)[0]["g"], "g")
        proof = {"ng": [glyph("n", 1100), glyph("g", 1152)]}
        same = {"ng": [glyph("n", 1100), glyph("g.ss04", 1152)]}
        validator.compare_runs(same, proof, "test", Counter())
        same["ng"][0]["ax"] += 1
        with self.assertRaisesRegex(validator.ValidationError, "advance mismatch"):
            validator.compare_runs(same, proof, "test", Counter())

    def test_variable_proof_compares_deltas_not_static_baseline_metrics(self):
        def run(n, g, alternate=False):
            return {"ng": [{"g": name, "cl": i, "ax": advance, "ay": 0, "dx": 0, "dy": 0}
                           for i, (name, advance) in enumerate((("n", n), ("g.ss04" if alternate else "g", g)))]}

        # Actual Medium baseline metrics: variable n is 1210, static n is 1209.
        # Static incoming correction is -52, variable interpolation gives -51.
        proof = run(1157, 1204)
        actual = run(1159, 1204, True)
        baselines = (run(1210, 1255), run(1209, 1255))
        counts = Counter()
        validator.compare_runs(actual, proof, "test", counts, baselines=baselines, weight=500)
        self.assertEqual(counts["variable_proof_delta_comparisons"], 1)
        # A large unrelated baseline difference must also cancel, not enlarge
        # the tolerance allowed for an incorrect ss04 spacing change.
        actual["ng"][0]["ax"] += 200
        baselines[0]["ng"][0]["ax"] += 200
        validator.compare_runs(actual, proof, "test", counts, baselines=baselines, weight=500)
        actual["ng"][0]["ax"] += 2
        with self.assertRaisesRegex(validator.ValidationError, "advance delta mismatch"):
            validator.compare_runs(actual, proof, "test", counts, baselines=baselines, weight=500)

    def test_variable_proof_models_heavy_gj_and_keeps_other_glyphs_exact(self):
        def run(g, j, alternate=False):
            return {"gj": [{"g": name, "cl": i, "ax": advance, "ay": 0, "dx": 0, "dy": 0}
                           for i, (name, advance) in enumerate((("g.ss04" if alternate else "g", g), ("j", j)))]}

        # Bold: static -57 width/+8 pair, variable -56.64 width/+11.25 pair.
        actual = run(1205, 501, True)
        proof = run(1201, 500)
        baselines = (run(1250, 501), run(1250, 500))
        validator.compare_runs(actual, proof, "test", Counter(), baselines=baselines, weight=700)
        actual["gj"][0]["ax"] += 3
        with self.assertRaisesRegex(validator.ValidationError, "advance delta mismatch"):
            validator.compare_runs(actual, proof, "test", Counter(), baselines=baselines, weight=700)
        actual = run(1205, 502, True)
        with self.assertRaisesRegex(validator.ValidationError, "advance delta mismatch"):
            validator.compare_runs(actual, proof, "test", Counter(), baselines=baselines, weight=700)

    def test_actual_integrated_static_binaries_and_woff_decoder_in_temp(self):
        # The production build is deliberately not a unit-test prerequisite.
        # Compile the real integration, not substituted placeholder drawings.
        from ufo2ft import compileOTF
        from build import drop_unreachable

        controls = author.control_drawings()
        with tempfile.TemporaryDirectory(prefix="allo-g-binary-tests-") as temporary:
            root = Path(temporary)
            (root / "otf").mkdir()
            (root / "webfonts").mkdir()
            report = {"counts": Counter()}
            check = validator.Validator(root, validator.HarfBuzz(root, report["counts"]), report)
            for style, weight in (("Regular", 400), ("Black", 900), ("Oblique", 400)):
                with self.subTest(style=style), ufoLib2.Font.open(ROOT / f"sources/static/Allo-{style}.ufo") as font:
                    if style == "Oblique":
                        with ufoLib2.Font.open(ROOT / "sources/static/Allo-Regular.ufo") as upright:
                            author.add_upright(upright, upright, 400, 50, controls, static=True)
                            author.add_oblique(font, upright, 400)
                    else:
                        author.add_upright(font, font, weight, 50, controls, static=True)
                    binary = compileOTF(font, removeOverlaps=False, useProductionNames=False)
                    try:
                        drop_unreachable(binary)
                        relative = Path("otf") / f"AlloCustom-{style}.otf"
                        binary.save(root / relative)
                        check.font(relative)
                        if style == "Regular":
                            binary.flavor = "woff2"
                            relative = Path("webfonts/AlloCustom-Regular.woff2")
                            binary.save(root / relative)
                            check.font(relative)
                    finally:
                        binary.close()
            self.assertEqual(report["counts"]["validated_fonts"], 4)
            self.assertEqual(report["counts"]["complete_static_outline_inventories"], 3)
            self.assertGreater(report["counts"]["absolute_mark_attachments"], 0)
            self.assertGreater(report["counts"]["static_proof_runs"], 0)


if __name__ == "__main__":
    unittest.main()
