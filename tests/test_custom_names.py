"""Focused naming tests; all saved fixtures live in TemporaryDirectory."""

from __future__ import annotations

import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables._f_v_a_r import Axis, NamedInstance

from custom_names import rename_for_custom, validate_custom_fonts


ROOT = Path(__file__).resolve().parents[1]
SHIPPED = tuple(sorted(
    path for folder in ("otf", "variable", "webfonts")
    for path in (ROOT / "fonts" / folder).iterdir()
    if path.suffix in (".otf", ".ttf", ".woff2")
))
STATIC = ROOT / "fonts/otf/Allo-Regular.otf"
VARIABLE = ROOT / "fonts/variable/AlloVariable.ttf"
IDENTITY_IDS = {1, 3, 4, 6, 16, 18, 21, 25}


def values(font, name_id):
    return sorted({record.toUnicode() for record in font["name"].names if record.nameID == name_id})


def set_name(font, name_id, value):
    records = [record for record in font["name"].names if record.nameID == name_id]
    if not records:
        font["name"].setName(value, name_id, 3, 1, 0x409)
    for record in records:
        record.string = value.encode(record.getEncoding())


def name_snapshot(font):
    return [
        (record.nameID, record.platformID, record.platEncID, record.langID, record.toBytes())
        for record in font["name"].names
    ]


def cff_snapshot(font, strip_identity=True):
    output = io.BytesIO()
    font.saveXML(output, tables=["CFF "])
    root = ET.fromstring(output.getvalue())
    if strip_identity:
        for node in root.iter("CFFFont"):
            node.set("name", "IDENTITY")
            for child in list(node):
                if child.tag in {"FamilyName", "FullName", "UniqueID", "XUID"}:
                    node.remove(child)
    return ET.tostring(root)


def simple_font(family="Allo", style="Regular", ps="Allo-Regular"):
    # A name-only SFNT keeps negative identity tests independent of font builds.
    font = TTFont(recalcTimestamp=False)
    font["name"] = newTable("name")
    font["name"].names = []
    for name_id, value in {
        1: family, 2: style, 3: f"{family} {style}",
        4: f"{family} {style}", 6: ps,
    }.items():
        set_name(font, name_id, value)
    return font


def add_variable(font, ps="Allo-Regular", ps_id=257, coordinate=400):
    font["fvar"] = newTable("fvar")
    axis = Axis()
    axis.axisTag = "wght"
    axis.minValue, axis.defaultValue, axis.maxValue = 100, 400, 900
    axis.flags, axis.axisNameID = 0, 256
    instance = NamedInstance()
    instance.subfamilyNameID, instance.flags = 2, 0
    instance.coordinates = {"wght": coordinate}
    instance.postscriptNameID = ps_id
    font["fvar"].axes = [axis]
    font["fvar"].instances = [instance]
    set_name(font, 256, "Allo axis label")
    if ps_id not in (6, 65535):
        set_name(font, ps_id, ps)
    return font


class RenameTests(unittest.TestCase):
    def test_shipped_inventory(self):
        self.assertEqual(len(SHIPPED), 39)
        self.assertEqual(sum(path.suffix == ".otf" for path in SHIPPED), 18)
        self.assertEqual(sum(path.suffix == ".ttf" for path in SHIPPED), 1)
        self.assertEqual(sum(path.suffix == ".woff2" for path in SHIPPED), 20)
        self.assertIn("AlloVariableFriendly.woff2", {path.name for path in SHIPPED})

    def test_all_shipped_fonts_preserve_every_non_identity_table_and_label(self):
        for path in SHIPPED:
            with self.subTest(font=path.name), TTFont(path, recalcTimestamp=False) as font:
                font.ensureDecompiled()
                ps_ids = {6, 25}
                if "fvar" in font:
                    ps_ids.update(
                        instance.postscriptNameID for instance in font["fvar"].instances
                        if instance.postscriptNameID != 65535
                    )
                original_names = name_snapshot(font)
                original_text = [record.toUnicode() for record in font["name"].names]
                tags = [tag for tag in font.keys() if tag not in {"GlyphOrder", "name", "CFF "}]
                # Prime lazy compile caches before taking the comparison snapshot.
                for tag in tags:
                    font.getTableData(tag)
                before = {tag: font.getTableData(tag) for tag in tags}
                glyphs = font.getGlyphOrder()[:]
                cff_before = cff_snapshot(font) if "CFF " in font else None

                with mock.patch.object(TTFont, "save", side_effect=AssertionError("must not save")):
                    self.assertIsNone(rename_for_custom(font))
                self.assertEqual(font.getGlyphOrder(), glyphs)
                self.assertEqual(len(font["name"].names), len(original_names))
                for old, text, record in zip(original_names, original_text, font["name"].names):
                    self.assertEqual(old[:4], (record.nameID, record.platformID, record.platEncID, record.langID))
                    if record.nameID in IDENTITY_IDS | ps_ids:
                        prefix = "AlloCustom" if record.nameID in ps_ids else "Allo Custom"
                        self.assertEqual(record.toUnicode(), prefix + text[len("Allo"):])
                    else:
                        self.assertEqual(record.toBytes(), old[4])
                for tag, data in before.items():
                    with self.subTest(table=tag):
                        self.assertEqual(font.getTableData(tag), data)
                if cff_before is not None:
                    self.assertIn(b"CharStrings", cff_before)
                    self.assertIn(b"Private", cff_before)
                    self.assertEqual(cff_snapshot(font), cff_before)
                    cff = font["CFF "].cff
                    self.assertEqual(cff.fontNames, values(font, 6))
                    self.assertEqual(cff.topDictIndex[0].FamilyName, "Allo Custom")
                    self.assertEqual(cff.topDictIndex[0].FullName, values(font, 4)[0])

    def test_optional_ids_all_platforms_and_languages_only(self):
        font = simple_font(family="Allo Thin", style="Regular", ps="Allo-Thin")
        for name_id, value in {
            16: "Allo", 17: "Allo style label", 18: "Allo Thin Compatible",
            21: "Allo", 22: "Allo WWS style", 25: "AlloVariableFriendly",
        }.items():
            set_name(font, name_id, value)
        untouched_ids = (0, 7, 8, 9, 10, 11, 12, 13, 14, 19, 20, 23, 24, 256, 300, 400, 65535)
        for name_id in untouched_ids:
            set_name(font, name_id, "Allo untouched label or attribution")
        for record in list(font["name"].names):
            for platform, encoding, language in ((0, 4, 0), (1, 0, 0), (3, 1, 0x40C), (3, 10, 0x411)):
                font["name"].setName(record.toUnicode(), record.nameID, platform, encoding, language)
        before = name_snapshot(font)
        rename_for_custom(font)
        for old, record in zip(before, font["name"].names):
            if record.nameID not in IDENTITY_IDS:
                self.assertEqual(record.toBytes(), old[4])
            else:
                self.assertTrue(record.toUnicode().startswith(
                    "AlloCustom" if record.nameID in (6, 25) else "Allo Custom"
                ))
        self.assertEqual(values(font, 1), ["Allo Custom Thin"])
        self.assertEqual(values(font, 16), ["Allo Custom"])
        self.assertEqual(values(font, 25), ["AlloCustomVariableFriendly"])

    def test_exact_prefixes_and_only_initial_occurrence(self):
        for ps in ("Allo", "AlloVariable", "AlloVariableFriendly"):
            with self.subTest(ps=ps):
                font = simple_font(ps=ps)
                for name_id in (1, 3, 4, 16, 18, 21):
                    set_name(font, name_id, "Allo")
                set_name(font, 25, ps)
                rename_for_custom(font)
                self.assertEqual(values(font, 4), ["Allo Custom"])
                self.assertEqual(values(font, 6), ["AlloCustom" + ps[4:]])
                self.assertEqual(values(font, 25), values(font, 6))
        font = simple_font(style="Allo Regular")
        rename_for_custom(font)
        self.assertEqual(values(font, 4), ["Allo Custom Allo Regular"])
        self.assertEqual(values(font, 2), ["Allo Regular"])

    def test_idempotent_including_cff(self):
        with TTFont(STATIC, recalcTimestamp=False) as font:
            rename_for_custom(font)
            before = name_snapshot(font), cff_snapshot(font, strip_identity=False)
            rename_for_custom(font)
            self.assertEqual((name_snapshot(font), cff_snapshot(font, strip_identity=False)), before)
        font = simple_font()
        set_name(font, 1, "Allo Custom")
        rename_for_custom(font)
        self.assertEqual(values(font, 1), ["Allo Custom"])

    def test_unexpected_identities_are_actionable_and_do_not_partially_rename(self):
        for name_id, value in ((1, "Another Family"), (4, "Allophone Regular"),
                               (6, "AlloVariableUnexpected-Regular"), (25, "AlloCustomary")):
            with self.subTest(name_id=name_id):
                font = simple_font()
                set_name(font, name_id, value)
                before = name_snapshot(font)
                with self.assertRaisesRegex(ValueError, f"name ID {name_id}.*unexpected"):
                    rename_for_custom(font)
                self.assertEqual(name_snapshot(font), before)

    def test_postscript_legality_and_length_after_expansion(self):
        for suffix in ("Has Space", "Régular", "Bad\x7f", "X" * 53, *"[](){}<>/%"):
            with self.subTest(suffix=suffix):
                font = simple_font(ps="Allo-" + suffix)
                with self.assertRaisesRegex(ValueError, "illegal PostScript name"):
                    rename_for_custom(font)
        font = simple_font(ps="Allo-" + "X" * 52)
        rename_for_custom(font)
        self.assertEqual(len(values(font, 6)[0]), 63)

    def test_fvar_explicit_ps_ids_and_sentinel_leave_other_high_ids_alone(self):
        with TTFont(VARIABLE, recalcTimestamp=False) as font:
            first = font["fvar"].instances[0]
            orphan_id = first.postscriptNameID
            orphan = values(font, orphan_id)
            first.postscriptNameID = 65535
            set_name(font, 65535, "AlloVariable-NotAReference")
            set_name(font, 25, "AlloVariable")
            second_id = font["fvar"].instances[1].postscriptNameID
            font["name"].setName(values(font, second_id)[0], second_id, 1, 0, 0)
            before = font.getTableData("fvar")
            rename_for_custom(font)
            self.assertEqual(font.getTableData("fvar"), before)
            self.assertEqual(values(font, orphan_id), orphan)
            self.assertEqual(values(font, 65535), ["AlloVariable-NotAReference"])
            self.assertEqual(values(font, second_id), ["AlloCustomVariable-ExtraLight"])
            self.assertEqual(values(font, 25), ["AlloCustomVariable"])
            self.assertEqual(values(font, 256), ["Optical size"])
            self.assertEqual(values(font, 300), ["Single-story a"])

    def test_missing_names_and_invalid_fvar_references(self):
        for name_id in (1, 2, 3, 4, 6, 256, 257):
            with self.subTest(missing=name_id):
                font = add_variable(simple_font())
                font["name"].removeNames(nameID=name_id)
                with self.assertRaisesRegex(ValueError, "missing required name IDs"):
                    rename_for_custom(font)
        for name_id in (2, 256, 65534):
            with self.subTest(invalid=name_id):
                font = add_variable(simple_font())
                font["fvar"].instances[0].postscriptNameID = name_id
                with self.assertRaisesRegex(ValueError, "invalid postscriptNameID"):
                    rename_for_custom(font)
        with self.assertRaisesRegex(ValueError, "missing required name table"):
            rename_for_custom(TTFont())

    def test_cff_removes_lazy_and_materialized_numeric_uids_only(self):
        for materialized in (False, True):
            with self.subTest(materialized=materialized), TTFont(STATIC, recalcTimestamp=False) as font:
                before = cff_snapshot(font)
                top = font["CFF "].cff.topDictIndex[0]
                for key, value in (("UniqueID", 1234567), ("XUID", [1, 2, 3])):
                    if materialized:
                        setattr(top, key, value)
                    else:
                        top.rawDict[key] = value
                rename_for_custom(font)
                for key in ("UniqueID", "XUID"):
                    self.assertNotIn(key, top.rawDict)
                    self.assertNotIn(key, vars(top))
                    self.assertFalse(hasattr(top, key))
                self.assertEqual(cff_snapshot(font), before)
                output = io.BytesIO()
                font.save(output)
                output.seek(0)
                with TTFont(output) as reopened:
                    self.assertEqual(cff_snapshot(reopened), before)

    def test_cff_mismatch_is_detected_before_mutating_names(self):
        with TTFont(STATIC) as font:
            font["CFF "].cff.topDictIndex[0].FamilyName = "Another Family"
            before = name_snapshot(font)
            with self.assertRaisesRegex(ValueError, "CFF FamilyName"):
                rename_for_custom(font)
            self.assertEqual(name_snapshot(font), before)


class ShippedValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory(prefix="allo-custom-names-")
        cls.addClassCleanup(temporary.cleanup)
        cls.directory = Path(temporary.name)
        cls.custom = []
        cls.source_hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in SHIPPED}
        for source in SHIPPED:
            destination = cls.directory / source.name
            with TTFont(source, recalcTimestamp=False) as font:
                rename_for_custom(font)
                font.save(destination)
            cls.custom.append(destination)

    def test_all_39_saved_fonts_validate_and_report_is_reproducible(self):
        report = validate_custom_fonts(self.custom, SHIPPED)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["custom_font_count"], 39)
        self.assertEqual(report["release_font_count"], 39)
        for family in ("Allo Custom", "Allo Custom Thin", "Allo Custom Variable", "Allo Custom Variable Friendly"):
            self.assertIn(family, report["families"])
        self.assertEqual(report["families"], sorted(set(report["families"])))
        encoded = json.dumps(report, sort_keys=True, allow_nan=False)
        again = validate_custom_fonts(reversed(self.custom), (path for path in reversed(SHIPPED)))
        self.assertEqual(json.dumps(again, sort_keys=True, allow_nan=False), encoded)
        self.assertNotIn(str(self.directory), encoded)
        self.assertNotIn(str(ROOT), encoded)
        self.assertNotIn("timestamp", encoded)
        files = {identity["file"]: identity for identity in report["fonts"]}
        self.assertEqual(set(files), {path.name for path in SHIPPED})
        for name, prefix in (("AlloVariable.ttf", "AlloCustomVariable"),
                             ("AlloVariableFriendly.woff2", "AlloCustomVariableFriendly")):
            self.assertEqual(files[name]["names"]["6"], [prefix + "-Regular"])
            self.assertEqual(len(files[name]["instances"]), 18)
            self.assertNotIn("25", files[name]["names"])
            self.assertIn(prefix + "-DisplayBlack", files[name]["postscript_names"])
        for source in SHIPPED:
            if source.suffix in (".otf", ".ttf"):
                twin = files[source.with_suffix(".woff2").name]
                self.assertEqual(files[source.name]["names"], twin["names"])
                self.assertEqual(files[source.name]["instances"], twin["instances"])

    def test_validation_writes_nothing_and_shipped_sources_are_untouched(self):
        paths = (*SHIPPED, *self.custom)
        before = {path: (path.stat().st_mtime_ns, path.read_bytes()) for path in paths}
        with mock.patch.object(TTFont, "save", side_effect=AssertionError("must not save")):
            validate_custom_fonts(self.custom, SHIPPED)
        after = {path: (path.stat().st_mtime_ns, path.read_bytes()) for path in paths}
        self.assertEqual(after, before)
        self.assertEqual(
            {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in SHIPPED},
            self.source_hashes,
        )


class ValidationEdgeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="allo-naming-edge-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.reference = self.save(simple_font(), "reference.ttf")

    def save(self, font, basename):
        path = self.directory / basename
        font.save(path)
        return path

    def custom(self, **kwargs):
        font = simple_font(**kwargs)
        rename_for_custom(font)
        return font

    def validate(self, font):
        return validate_custom_fonts([self.save(font, "custom.ttf")], [self.reference])

    def test_empty_inputs_and_unreadable_references_are_errors(self):
        with self.assertRaisesRegex(ValueError, "no release reference font files"):
            validate_custom_fonts([], [])
        with self.assertRaisesRegex(ValueError, "no custom font files"):
            validate_custom_fonts([], [self.reference])
        custom = self.save(self.custom(), "custom.ttf")
        with self.assertRaisesRegex(ValueError, "missing.ttf.*cannot validate"):
            validate_custom_fonts([custom], [self.directory / "missing.ttf"])
        invalid = self.directory / "invalid.ttf"
        invalid.write_bytes(b"not an SFNT")
        with self.assertRaisesRegex(ValueError, "invalid.ttf.*cannot validate"):
            validate_custom_fonts([custom], [invalid])
        with self.assertRaisesRegex(ValueError, "duplicate custom basename"):
            validate_custom_fonts([custom, custom], [self.reference])

    def test_file_handle_closed_even_if_font_constructor_fails(self):
        custom = self.save(self.custom(), "custom.ttf")
        streams = []

        def fail(stream, **kwargs):
            streams.append(stream)
            raise ValueError("invalid font constructor")

        with mock.patch("custom_names.TTFont", side_effect=fail):
            with self.assertRaisesRegex(ValueError, "reference.ttf.*invalid font constructor"):
                validate_custom_fonts([custom], [self.reference])
        self.assertEqual(len(streams), 1)
        self.assertTrue(streams[0].closed)

    def test_required_names_and_nonempty_identity_records(self):
        for name_id in (1, 2, 3, 4, 6):
            with self.subTest(missing=name_id):
                font = self.custom()
                font["name"].removeNames(nameID=name_id)
                with self.assertRaisesRegex(ValueError, "missing required name IDs"):
                    self.validate(font)
        for name_id in IDENTITY_IDS | {2, 17, 22}:
            with self.subTest(empty=name_id):
                font = self.custom()
                set_name(font, name_id, "")
                with self.assertRaisesRegex(ValueError, f"name ID {name_id}.*empty"):
                    self.validate(font)
        with self.assertRaisesRegex(ValueError, "missing required name table"):
            self.validate(TTFont())

    def test_every_identity_id_checked_in_every_language_for_stale_names(self):
        for name_id in sorted(IDENTITY_IDS):
            with self.subTest(name_id=name_id):
                font = self.custom()
                font["name"].setName("Allo", name_id, 3, 1, 0x40C)
                with self.assertRaisesRegex(ValueError, f"name ID {name_id}.*stale or unexpected"):
                    self.validate(font)
        font = add_variable(self.custom(), ps="Allo-Instance", coordinate=700)
        with self.assertRaisesRegex(ValueError, "name ID 257.*stale or unexpected"):
            self.validate(font)

    def test_unrelated_high_names_and_attributions_are_not_identities(self):
        font = self.custom()
        for name_id in (0, 8, 9, 13, 14, 256, 300, 400, 65535):
            set_name(font, name_id, "Allo release text must remain")
        self.assertEqual(self.validate(font)["status"], "ok")

    def test_postscript_legality_for_base_prefix_and_instance_names(self):
        for name_id in (6, 25, 257):
            for suffix in ("Has Space", "Régular", "Bad\x7f", "X" * 53, *"[](){}<>/%"):
                with self.subTest(name_id=name_id, suffix=suffix):
                    font = add_variable(self.custom(), ps="AlloCustom-Instance", coordinate=700)
                    set_name(font, name_id, "AlloCustom-" + suffix)
                    with self.assertRaisesRegex(ValueError, "illegal PostScript name"):
                        self.validate(font)
        font = self.custom(ps="Allo-" + "X" * 52)
        self.assertEqual(self.validate(font)["status"], "ok")

    def test_postscript_records_must_agree_across_languages(self):
        font = self.custom()
        font["name"].setName("AlloCustom-Other", 6, 1, 0, 0)
        with self.assertRaisesRegex(ValueError, "inconsistent PostScript names"):
            self.validate(font)

    def test_release_collisions_cover_all_namespaces_case_insensitively(self):
        for name_id, value, category in (
            (1, "Allo Custom", "family"), (16, "Allo Custom", "family"),
            (21, "Allo Custom", "family"), (4, "Allo Custom Regular", "full name"),
            (18, "Allo Custom Regular", "full name"), (3, "Allo Custom Regular", "unique ID"),
            (6, "AlloCustom-Regular", "PostScript name"),
            (25, "AlloCustomVariable", "PostScript name"),
        ):
            with self.subTest(name_id=name_id):
                reference = simple_font()
                set_name(reference, name_id, value.lower())
                self.save(reference, "reference.ttf")
                font = self.custom()
                set_name(font, 25, "AlloCustomVariable")
                with self.assertRaisesRegex(ValueError, category + ".*collides with release"):
                    self.validate(font)

    def test_base_and_instance_ps_names_share_collision_namespace(self):
        reference = add_variable(simple_font(), ps="allocustom-regular", coordinate=700)
        self.save(reference, "reference.ttf")
        with self.assertRaisesRegex(ValueError, "PostScript name.*collides with release"):
            self.validate(self.custom())
        reference = simple_font(ps="allocustom-instance")
        self.save(reference, "reference.ttf")
        font = add_variable(self.custom(), ps="AlloCustom-Instance", coordinate=700)
        with self.assertRaisesRegex(ValueError, "PostScript name.*collides with release"):
            self.validate(font)

    def test_different_styles_can_share_family_but_not_style_identities(self):
        first = self.custom()
        second = self.custom(style="Bold", ps="Allo-Bold")
        paths = [self.save(first, "Regular.ttf"), self.save(second, "Bold.ttf")]
        self.assertEqual(validate_custom_fonts(paths, [self.reference])["status"], "ok")
        for name_id, value, category in (
            (4, "allo custom regular", "full name"),
            (18, "allo custom regular", "full name"),
            (3, "allo custom regular", "unique ID"),
            (6, "allocustom-regular", "PostScript name"),
            (2, "regular", "family/style"),
        ):
            with self.subTest(name_id=name_id):
                second = self.custom(style="Bold", ps="Allo-Bold")
                set_name(second, name_id, value)
                self.save(second, "Bold.ttf")
                with self.assertRaisesRegex(ValueError, "duplicate " + category + ".*distinct output stems"):
                    validate_custom_fonts(paths, [self.reference])

    def test_typographic_and_wws_family_style_duplicates(self):
        for family_id, style_id in ((16, 17), (21, 22)):
            with self.subTest(family_id=family_id):
                first = self.custom()
                second = self.custom(family="Allo Second", style="Bold", ps="Allo-SecondBold")
                for font, style in ((first, "Book"), (second, "book")):
                    set_name(font, family_id, "Allo Custom Shared")
                    set_name(font, style_id, style)
                paths = [self.save(first, "First.ttf"), self.save(second, "Second.ttf")]
                with self.assertRaisesRegex(ValueError, "duplicate family/style"):
                    validate_custom_fonts(paths, [self.reference])

    def test_instance_ps_collision_across_distinct_custom_stems(self):
        first = add_variable(self.custom(), ps="AlloCustom-Instance", coordinate=700)
        second = self.custom(family="Allo Second", style="Bold", ps="Allo-Instance")
        paths = [self.save(first, "First.ttf"), self.save(second, "Second.ttf")]
        with self.assertRaisesRegex(ValueError, "duplicate PostScript name"):
            validate_custom_fonts(paths, [self.reference])

    def test_same_stem_twins_require_matching_names_and_instance_identities(self):
        first = add_variable(self.custom(), ps="AlloCustom-Instance", coordinate=700)
        paths = [self.save(first, "Twin.ttf"), self.save(first, "Twin.otf")]
        self.assertEqual(validate_custom_fonts(paths, [self.reference])["custom_font_count"], 2)
        for name_id, value in ((4, "Allo Custom Different"), (18, "Allo Custom Compatible"),
                               (2, "Different Style"), (257, "AlloCustom-DifferentInstance")):
            with self.subTest(name_id=name_id):
                second = copy.deepcopy(first)
                set_name(second, name_id, value)
                self.save(second, "Twin.otf")
                with self.assertRaisesRegex(ValueError, "same-stem identity mismatch"):
                    validate_custom_fonts(paths, [self.reference])
        second = copy.deepcopy(first)
        second["fvar"].instances[0].coordinates["wght"] = 800
        self.save(second, "Twin.otf")
        with self.assertRaisesRegex(ValueError, "same-stem identity mismatch"):
            validate_custom_fonts(paths, [self.reference])

    def test_twins_cannot_swap_localized_names_even_with_identical_string_sets(self):
        for name_id in (4, 258):
            with self.subTest(name_id=name_id):
                first = add_variable(self.custom(), ps="AlloCustom-Instance")
                first["fvar"].instances[0].subfamilyNameID = 258
                set_name(first, 258, "Named Style")
                first["name"].setName("Allo Custom English", name_id, 3, 1, 0x409)
                first["name"].setName("Allo Custom French", name_id, 3, 1, 0x40C)
                second = copy.deepcopy(first)
                second["name"].setName("Allo Custom French", name_id, 3, 1, 0x409)
                second["name"].setName("Allo Custom English", name_id, 3, 1, 0x40C)
                self.assertEqual(values(first, name_id), values(second, name_id))
                paths = [self.save(first, "Twin.ttf"), self.save(second, "Twin.otf")]
                with self.assertRaisesRegex(ValueError, "same-stem identity mismatch"):
                    validate_custom_fonts(paths, [self.reference])

    def test_default_instance_can_share_base_ps_and_sentinel_is_not_a_reference(self):
        for name_id in (6, 257, 65535):
            with self.subTest(name_id=name_id):
                font = add_variable(self.custom(), ps="AlloCustom-Regular", ps_id=name_id)
                set_name(font, 65535, "Allo-NotAnInstanceName")
                report = self.validate(font)
                self.assertEqual(report["status"], "ok")
                instance = report["fonts"][0]["instances"][0]
                self.assertEqual(instance["postscript_name_id"], name_id)
                self.assertEqual(instance["postscript_names"], [] if name_id == 65535 else ["AlloCustom-Regular"])

    def test_nondefault_instance_cannot_share_base_ps_or_another_instance_ps(self):
        font = add_variable(self.custom(), ps="AlloCustom-Regular", coordinate=700)
        with self.assertRaisesRegex(ValueError, "non-default instance shares base"):
            self.validate(font)
        font = add_variable(self.custom(), ps="AlloCustom-Instance")
        second = copy.deepcopy(font["fvar"].instances[0])
        second.coordinates["wght"] = 700
        font["fvar"].instances.append(second)
        with self.assertRaisesRegex(ValueError, "duplicate PostScript name"):
            self.validate(font)

    def test_missing_fvar_ps_and_label_references_are_rejected(self):
        for name_id in (256, 257, 258):
            with self.subTest(name_id=name_id):
                font = add_variable(self.custom(), ps="AlloCustom-Instance")
                font["fvar"].instances[0].subfamilyNameID = 258
                set_name(font, 258, "Named Style")
                font["name"].removeNames(nameID=name_id)
                with self.assertRaisesRegex(ValueError, "missing required name IDs"):
                    self.validate(font)

    def test_cff_name_consistency_and_numeric_uid_validation(self):
        for field, value in (("fontNames", ["AlloCustom-Other"]),
                             ("FamilyName", "Allo Custom Other"),
                             ("FullName", "Allo Custom Other"),
                             ("UniqueID", 1234567), ("XUID", [1, 2, 3])):
            with self.subTest(field=field), TTFont(STATIC, recalcTimestamp=False) as font:
                rename_for_custom(font)
                cff = font["CFF "].cff
                if field == "fontNames":
                    cff.fontNames[:] = value
                else:
                    setattr(cff.topDictIndex[0], field, value)
                path = self.save(font, "bad.otf")
                with self.assertRaisesRegex(ValueError, "CFF.*" + field):
                    validate_custom_fonts([path], [self.reference])

    def test_localized_style_pairs_preserve_distinct_styles(self):
        first = self.custom()
        second = self.custom(style="Bold", ps="Allo-Bold")
        for font, french_style in ((first, "Normal"), (second, "Gras")):
            font["name"].setName("Allo Custom", 1, 3, 1, 0x40C)
            font["name"].setName(french_style, 2, 3, 1, 0x40C)
        paths = [self.save(first, "First.ttf"), self.save(second, "Second.ttf")]
        report = validate_custom_fonts(paths, [self.reference])
        pairs = report["fonts"][0]["family_styles"]
        self.assertIn({"family": "Allo Custom", "style": "Normal"}, pairs)
        self.assertIn({"family": "Allo Custom", "style": "Regular"}, pairs)


if __name__ == "__main__":
    unittest.main()
