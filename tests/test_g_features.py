"""ss04 contracts using in-memory UFOs; only shaping fixtures are saved, in tempdirs."""

from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
import tempfile
import unicodedata
import unittest
from io import StringIO
from pathlib import Path
from unittest import mock

import ufoLib2
from fontTools.feaLib import ast
from fontTools.feaLib.parser import Parser
from fontTools.misc.roundTools import otRound
from fontTools.ufoLib.kerning import lookupKerningValue
from ufo2ft import compileOTF
from ufo2ft.featureCompiler import FeatureCompiler
from ufoLib2.objects import Component

from g_features import G_FAMILY, integrate_features, spacing_amount

ROOT = Path(__file__).resolve().parents[1]
ALTS = tuple(name + ".ss04" for name in G_FAMILY)
FIRST, SECOND = "public.kern1.g.ss04", "public.kern2.g.ss04"
OWNED = {*ALTS, FIRST, SECOND}
DESIGN_WEIGHTS = {100: 100, 200: 200, 300: 300, 400: 400, 500: 490,
                  600: 580, 700: 670, 800: 780, 900: 900}
STATIC_B = {100: 40, 200: 43, 300: 45, 400: 48, 500: 51,
            600: 54, 700: 57, 800: 60, 900: 64}
STATIC_N = {100: 40, 200: 44, 300: 46, 400: 48, 500: 52,
            600: 54, 700: 58, 800: 60, 900: 64}
STATIC_J = {100: 0, 200: 0, 300: 0, 400: 0, 500: 0,
            600: 0, 700: 8, 800: 27, 900: 40}


def extend(font, design_weight=400, user_weight=None):
    b = spacing_amount(design_weight)
    if user_weight is not None:
        b = otRound(b)
    for source, alternate in zip(G_FAMILY, ALTS):
        # These are test stand-ins, not proposed double-storey outlines.
        font.layers.defaultLayer.insertGlyph(font[source], name=alternate)
        font[alternate].width = font["g"].width - b


def lookup(groups, kerning):
    first = {g: k for k, gs in groups.items() if k.startswith("public.kern1.") for g in gs}
    second = {g: k for k, gs in groups.items() if k.startswith("public.kern2.") for g in gs}

    def get(a, b):
        return lookupKerningValue((a, b), kerning, groups,
                                  glyphToFirstGroup=first, glyphToSecondGroup=second)
    return get


def snapshot(font):
    return (font.features.text, copy.deepcopy(font.lib), copy.deepcopy(font.groups),
            dict(font.kerning), {g.name: copy.deepcopy(g) for g in font})


def fixture():
    font = ufoLib2.Font()
    font.info.unitsPerEm = 1000
    cmap: dict[str, int] = dict(zip(G_FAMILY, (0x67, 0x11D, 0x11F, 0x121, 0x123)))
    cmap.update({c: ord(c) for c in "aehjmnocqTu"})
    cmap.update({"nacute": 0x144, "jcircumflex": 0x135, "jdotless": 0x237,
                 "oacute": 0xF3, "oslash": 0xF8, "oe": 0x153, "acutecomb": 0x301})
    names = {*cmap, "a.1", "plus", "minus", "plus.case", "minus.case", "zero",
             "o.custom", "o.nested", "n.custom", "n.nested", "o.sups", "n.sups",
             "orange", "nonsense", "n_n", "cycle1", "cycle2"}
    for name in sorted(names):
        g = font.newGlyph(name)
        g.width = 600
        if name in cmap:
            g.unicodes = [cmap[name]]
    for name, base in (("o.custom", "o"), ("o.nested", "o.custom"),
                       ("n.custom", "n"), ("n.nested", "n.custom")):
        font[name].components = [Component(base), Component("acutecomb")]
    font["oe"].components = [Component("o"), Component("e")]
    font["n_n"].components = [Component("n"), Component("n")]
    for name, base in (("o.sups", "o"), ("n.sups", "n")):
        font[name].components = [Component(base, (0.5, 0, 0, 0.5, 0, 200))]
    font["cycle1"].components = [Component("cycle2")]
    font["cycle2"].components = [Component("cycle1")]
    members = " ".join(sorted(names))
    font.features.text = (
        "languagesystem DFLT dflt;\n"
        f"@NOT_SPACE = [{members} # a comment with ] and g.ss04\n];\n"
        f"@NOT_BRACKET = [{members}];\n"
        "feature calt {\n  lookup nearCaps {\n"
        f"    ignore sub [{' '.join(G_FAMILY)} n] [plus minus]' [zero];\n"
        "    sub [plus minus]' [zero] by [plus.case minus.case];\n"
        "  } nearCaps;\n} calt;\n"
        "# feature ss04 in a comment is not a conflict.\n"
        "feature ss05 { sub a by a.1; } ss05;\n"
    )
    font.groups.update({
        "public.kern1.g": [*G_FAMILY, "q"],
        "public.kern2.o": [*G_FAMILY, "o", "e", "c", "q", "a.1", "oe"],
        "public.kern1.a": ["a", "h", "m", "n", "nacute"],
        "public.kern2.j": ["j", "jdotless", "jcircumflex"],
        "public.kern1.T": ["T"],
        "user.selection": ["g", "a"],
    })
    font.kerning.update({
        ("public.kern1.g", "public.kern2.o"): -10,
        ("public.kern1.g", "public.kern2.j"): 20,
        ("public.kern1.T", "public.kern2.o"): -90,
        ("public.kern1.T", "gcircumflex"): -12,
        ("gcircumflex", "public.kern2.o"): -3,
        ("gcircumflex", "o"): 0,
        ("public.kern1.g", "gdotaccent"): -17,
        ("gcircumflex", "gdotaccent"): 0,
        ("g", "gbreve"): 7,
        ("gcommaaccent", "g"): 31,
        ("n", "gcommaaccent"): 17,
        ("a", "h"): -5,
    })
    font.lib["public.glyphOrder"] = sorted(names)
    font.lib["public.openTypeCategories"] = {"g": "base", "acutecomb": "mark"}
    font.lib["user.data"] = {"preserve": [1, 2, 3]}
    extend(font)
    return font


class SpacingTests(unittest.TestCase):
    def test_export_and_piecewise_float_samples(self):
        self.assertEqual(G_FAMILY, ("g", "gcircumflex", "gbreve", "gdotaccent", "gcommaaccent"))
        for weight, expected in ((100, 40), (250, 44), (400, 48), (490, 50.88),
                                 (580, 53.76), (670, 56.64), (780, 60.16), (900, 64)):
            with self.subTest(weight=weight):
                self.assertIsInstance(spacing_amount(weight), float)
                self.assertAlmostEqual(spacing_amount(weight), expected)
        self.assertEqual(spacing_amount(-100), 40.0)
        self.assertEqual(spacing_amount(1000), 64.0)

    def test_nonfinite_or_nonnumeric_weights_fail_before_mutation(self):
        for value in (float("nan"), float("inf"), -float("inf"), None, "bad"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "finite"):
                    spacing_amount(value)
                f = fixture()
                before = snapshot(f)
                with self.assertRaises(ValueError):
                    integrate_features(f, value)
                self.assertEqual(snapshot(f), before)
        f = fixture()
        before = snapshot(f)
        with self.assertRaisesRegex(ValueError, "user_weight"):
            integrate_features(f, 400, user_weight=float("nan"))
        self.assertEqual(snapshot(f), before)

    def test_static_rounding_and_master_sampling_are_distinct(self):
        for user, design in DESIGN_WEIGHTS.items():
            f = fixture()
            integrate_features(f, design, user_weight=user)
            get = lookup(f.groups, f.kerning)
            self.assertEqual(get("g.ss04", "oacute"), -STATIC_B[user])
            self.assertEqual(get("nacute", "g.ss04"), -STATIC_N[user])
            self.assertEqual(get("g.ss04", "j"), 20 + STATIC_J[user])
        for weight, b, n, j in ((100, 40, 40, 0), (400, 48, 48, 0),
                                 (490, 50.88, 51, 0), (580, 53.76, 54, 0),
                                 (670, 56.64, 56.8125, 11.25), (900, 64, 64, 40)):
            with self.subTest(master=weight):
                f = fixture()
                integrate_features(f, weight)
                get = lookup(f.groups, f.kerning)
                self.assertAlmostEqual(get("g.ss04", "oacute"), -b)
                self.assertAlmostEqual(get("n", "g.ss04"), -n)
                self.assertAlmostEqual(get("g.ss04", "j"), 20 + j)


class IntegrationTests(unittest.TestCase):
    def test_metadata_and_three_context_classes_preserve_other_data(self):
        f = fixture()
        old_groups, old_kerning = copy.deepcopy(f.groups), dict(f.kerning)
        old_order = f.lib["public.glyphOrder"][:]
        old_glyphs = {g.name: copy.deepcopy(g) for g in f}
        for name in ALTS:
            old_glyphs[name].unicodes = []
        with mock.patch.object(ufoLib2.Font, "save", side_effect=AssertionError("must not save")):
            self.assertIsNone(integrate_features(f, 400, user_weight=400))
        self.assertEqual(f.lib["public.glyphOrder"], old_order + list(ALTS))
        self.assertEqual(f.lib["user.data"], {"preserve": [1, 2, 3]})
        for name in ALTS:
            self.assertEqual(f.lib["public.openTypeCategories"][name], "base")
        for name, glyph in old_glyphs.items():
            self.assertEqual(f[name], glyph, name)
        for name, members in old_groups.items():
            self.assertEqual(f.groups[name], members)
        for pair, value in old_kerning.items():
            self.assertEqual(f.kerning[pair], value)
        self.assertEqual(f.groups[FIRST], list(ALTS))
        self.assertEqual(f.groups[SECOND], list(ALTS))
        self.assertIn("# a comment with ] and g.ss04", f.features.text)
        self.assertIn("feature ss05 { sub a by a.1; } ss05;\n", f.features.text)
        parsed = Parser(StringIO(f.features.text), glyphNames=f.keys()).parse()
        classes = [s.glyphs for s in parsed.statements
                   if isinstance(s, ast.GlyphClassDefinition) and s.name in {"NOT_SPACE", "NOT_BRACKET"}]
        calt = next(s for s in parsed.statements if isinstance(s, ast.FeatureBlock) and s.name == "calt")
        classes.append(calt.statements[0].statements[0].chainContexts[0][0][0])
        for glyph_class in classes:
            for name in ALTS:
                self.assertEqual(glyph_class.glyphSet().count(name), 1)
        blocks = [s.name for s in parsed.statements if isinstance(s, ast.FeatureBlock)]
        self.assertEqual(blocks.count("ss04"), 1)
        self.assertNotIn("kern", blocks)
        self.assertIn('name "Double-storey g";', f.features.text)

    def test_effective_inheritance_matrix_including_zero_exceptions_and_both_alternates(self):
        f = fixture()
        old = lookup(copy.deepcopy(f.groups), dict(f.kerning))
        originals = set(f.keys()) - set(ALTS)
        rounds = {"o", "e", "c", "oacute", "oslash", "o.custom", "o.nested"}
        ns = {"n", "nacute", "n.custom", "n.nested"}
        js = {"j", "jdotless", "jcircumflex"}
        integrate_features(f, 900, user_weight=900)
        get = lookup(f.groups, f.kerning)
        for other in sorted(originals):
            for source, alt in zip(G_FAMILY, ALTS):
                self.assertEqual(get(alt, other), old(source, other) + (-64 if other in rounds else 40 if other in js else 0), (alt, other))
                self.assertEqual(get(other, alt), old(other, source) - (64 if other in ns else 0), (other, alt))
        for a in sorted(originals):
            for b in sorted(originals):
                self.assertEqual(get(a, b), old(a, b), (a, b))
        for a, aa in zip(G_FAMILY, ALTS):
            for b, bb in zip(G_FAMILY, ALTS):
                self.assertEqual(get(aa, bb), old(a, b), (aa, bb))
        self.assertIn(("gcircumflex.ss04", "gdotaccent.ss04"), f.kerning)
        self.assertEqual(f.kerning["gcircumflex.ss04", "gdotaccent.ss04"], 0)

    def test_idempotence_stale_owned_keys_and_rebuild_after_weight_or_original_change(self):
        f = fixture()
        integrate_features(f, 400, user_weight=400)
        before = snapshot(f)
        integrate_features(f, 400, user_weight=400)
        self.assertEqual(snapshot(f), before)
        f.kerning["g.ss04", "stale.follower"] = 999
        f.kerning["stale.predecessor", "gcircumflex.ss04"] = 999
        f.kerning[FIRST, "stale.group"] = 999
        f.kerning["n", "g"] = 12
        f.groups[FIRST] = ["g.ss04"]
        f.lib["public.glyphOrder"].extend(["g.ss04", "g.ss04"])
        f.groups["user.selection"].append("g.ss04")
        f.newGlyph("unrelated.ss04")
        f.kerning["unrelated.ss04", "a"] = 23
        integrate_features(f, 900, user_weight=900)
        self.assertFalse(any("stale" in key for pair in f.kerning for key in pair))
        self.assertEqual(lookup(f.groups, f.kerning)("n", "g.ss04"), 12 - 64)
        self.assertEqual(f.kerning["unrelated.ss04", "a"], 23)
        self.assertIn("g.ss04", f.groups["user.selection"])
        self.assertEqual(f.lib["public.glyphOrder"].count("g.ss04"), 1)
        before = snapshot(f)
        integrate_features(f, 900, user_weight=900)
        self.assertEqual(snapshot(f), before)

    def test_missing_glyphs_and_unowned_conflicts_leave_font_unchanged(self):
        def missing(f):
            del f["gdotaccent.ss04"]

        def feature(f):
            f.features.text += "feature ss04 { sub g by g.ss04; } ss04;\n"

        def membership(f):
            f.groups["public.kern1.g"].append("g.ss04")

        def markers(f):
            f.features.text += "\n# BEGIN g_features ss04\n"

        def context(f):
            f.features.text = f.features.text.replace("@NOT_SPACE", "@NOT_SPACES")

        for change in (missing, feature, membership, markers, context):
            with self.subTest(change=change.__name__):
                f = fixture()
                change(f)
                before = snapshot(f)
                with self.assertRaises(ValueError):
                    integrate_features(f, 400)
                self.assertEqual(snapshot(f), before)


class SourceTests(unittest.TestCase):
    def test_all_full_masters_and_statics_preserve_originals_and_inherit_effective_pairs(self):
        paths = sorted((ROOT / "sources/masters").glob("*.ufo")) + sorted((ROOT / "sources/static").glob("*.ufo"))
        self.assertEqual(len(paths), 66)
        for path in paths:
            with self.subTest(source=path.name), ufoLib2.Font.open(path) as f:
                user = None if path.parent.name == "masters" else f.info.openTypeOS2WeightClass
                if user is None:
                    match = re.search(r"wght(\d+)", path.stem)
                    if match is None:
                        self.fail(f"master filename has no design weight: {path.name}")
                    design = int(match[1])
                else:
                    design = DESIGN_WEIGHTS[user]
                extend(f, design, user)
                old_groups = {k: copy.deepcopy(v) for k, v in f.groups.items() if k not in {FIRST, SECOND}}
                old_kern = {p: v for p, v in f.kerning.items() if not OWNED.intersection(p)}
                old = lookup(old_groups, old_kern)
                original_names = sorted(set(f.keys()) - set(ALTS))
                rounds, ns = {"oslash"}, set()
                for name in original_names:
                    for u in f[name].unicodes:
                        root = unicodedata.normalize("NFD", chr(u))[0]
                        if root in "oec":
                            rounds.add(name)
                        if root == "n":
                            ns.add(name)
                b = spacing_amount(design) if user is None else STATIC_B[user]
                n = {100: 40, 400: 48, 580: 54, 900: 64}[design] if user is None else STATIC_N[user]
                j = (40 if design == 900 else 0) if user is None else STATIC_J[user]
                integrate_features(f, design, user_weight=user)
                self.assertEqual({k: v for k, v in f.groups.items() if k not in {FIRST, SECOND}}, old_groups)
                self.assertEqual({p: v for p, v in f.kerning.items() if not OWNED.intersection(p)}, old_kern)
                get = lookup(f.groups, f.kerning)
                for other in original_names:
                    for source, alternate in zip(G_FAMILY, ALTS):
                        self.assertAlmostEqual(get(alternate, other), old(source, other) + (-b if other in rounds else j if other in {"j", "jdotless", "jcircumflex"} else 0), msg=f"{alternate}/{other}")
                        self.assertAlmostEqual(get(other, alternate), old(other, source) - (n if other in ns else 0), msg=f"{other}/{alternate}")
                for a, aa in zip(G_FAMILY, ALTS):
                    for b_name, bb in zip(G_FAMILY, ALTS):
                        self.assertEqual(get(aa, bb), old(a, b_name))
                generated = (f.features.text, dict(f.kerning), copy.deepcopy(f.groups), copy.deepcopy(f.lib))
                integrate_features(f, design, user_weight=user)
                self.assertEqual((f.features.text, dict(f.kerning), f.groups, f.lib), generated)

    def test_generated_layout_covers_unencoded_alternates_and_keeps_mark_writers(self):
        for stem, weight in (("Regular", 400), ("Black", 900), ("Oblique", 400)):
            with self.subTest(style=stem), ufoLib2.Font.open(ROOT / f"sources/static/Allo-{stem}.ufo") as f:
                extend(f, weight, weight)
                integrate_features(f, weight, user_weight=weight)
                compiler = FeatureCompiler(f)
                tt = compiler.compile()
                self.assertEqual({r.FeatureTag for r in tt["GPOS"].table.FeatureList.FeatureRecord}, {"kern", "mark", "mkmk"})
                record = next(r for r in tt["GSUB"].table.FeatureList.FeatureRecord if r.FeatureTag == "ss04")
                mapping = {}
                for index in record.Feature.LookupListIndex:
                    for subtable in tt["GSUB"].table.LookupList.Lookup[index].SubTable:
                        mapping.update(subtable.mapping)
                self.assertEqual(mapping, dict(zip(G_FAMILY, ALTS)))
                self.assertEqual(tt["name"].getDebugName(record.Feature.FeatureParams.UINameID), "Double-storey g")
                for name in ALTS:
                    self.assertEqual(tt["GDEF"].table.GlyphClassDef.classDefs[name], 1)
                    self.assertIn(f"pos base {name}\n", compiler.features)
                self.assertNotIn("feature kern", f.features.text)

    @unittest.skipUnless(shutil.which("hb-shape"), "optional local hb-shape is unavailable")
    def test_harfbuzz_default_preservation_ss01_independence_marks_and_kern_off(self):
        executable = shutil.which("hb-shape")
        assert executable is not None
        with tempfile.TemporaryDirectory(prefix="allo-g-features-test-") as temporary:
            for stem, weight in (("Regular", 400), ("Black", 900)):
                with self.subTest(style=stem), ufoLib2.Font.open(ROOT / f"sources/static/Allo-{stem}.ufo") as f:
                    # Use the original side of any already integrated source as the baseline.
                    extend(f, weight, weight)
                    integrate_features(f, weight, user_weight=weight)
                    tt = compileOTF(f, removeOverlaps=False, useProductionNames=False)
                    path = Path(temporary) / f"{stem}.otf"
                    tt.save(path)
                    order = tt.getGlyphOrder()
                    get = lookup(f.groups, f.kerning)

                    def shape(text, ss04=0, kern=1, ss01=0, path=path, order=order):
                        run = subprocess.run([
                            executable, str(path), "--text=" + text,
                            f"--features=ss04={ss04},kern={kern},ss01={ss01}",
                            "--output-format=json", "--no-glyph-names",
                        ], capture_output=True, text=True, check=True, timeout=10)
                        result = json.loads(run.stdout)
                        for item in result:
                            item["g"] = order[item["g"]]
                        return result

                    for text, names in (("ngj", ["n", "g", "j"]), ("ńğ", ["nacute", "gbreve"]),
                                        ("Tĝ", ["T", "gcircumflex"]), ("gœ", ["g", "oe"]),
                                        ("gø", ["g", "oslash"]), ("gog", ["g", "o", "g"]),
                                        ("gĝ", ["g", "gcircumflex"]), ("hg", ["h", "g"])):
                        for enabled in (0, 1):
                            selected = [n + ".ss04" if enabled and n in G_FAMILY else n for n in names]
                            for kern in (0, 1):
                                shaped = shape(text, enabled, kern)
                                self.assertEqual([i["g"] for i in shaped], selected)
                                advances = [otRound(f[n].width) + (otRound(get(n, selected[i + 1])) if kern and i + 1 < len(selected) else 0)
                                            for i, n in enumerate(selected)]
                                self.assertEqual([i["ax"] for i in shaped], advances, (text, enabled, kern))
                    for ss01 in (0, 1):
                        self.assertEqual([i["g"] for i in shape("ag", 1, ss01=ss01)], ["a.1" if ss01 else "a", "g.ss04"])
                    for text, name in (("ĝ", "gcircumflex"), ("ğ", "gbreve"), ("ġ", "gdotaccent"), ("ģ", "gcommaaccent")):
                        for enabled in (0, 1):
                            composed = shape(text, enabled)
                            decomposed = shape(unicodedata.normalize("NFD", text), enabled)
                            self.assertEqual([i["g"] for i in composed], [name + ".ss04" if enabled else name])
                            self.assertEqual(composed, decomposed)
                    for text in ("g\u0301", "g\u0323", "g\u0301\u0307"):
                        original, alternate = shape(text), shape(text, 1)
                        self.assertEqual(alternate[0]["g"], "g.ss04")
                        self.assertEqual(alternate[0]["ax"], original[0]["ax"] - STATIC_B[weight])
                        for old, new in zip(original[1:], alternate[1:]):
                            self.assertEqual(new["g"], old["g"])
                            self.assertEqual(new["dy"], old["dy"])
                            # Relative glyph offsets compensate for the reduced base advance.
                            self.assertEqual(new["dx"] + alternate[0]["ax"], old["dx"] + original[0]["ax"])


if __name__ == "__main__":
    unittest.main()
