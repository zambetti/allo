"""Standalone proof contracts; fonts are read-only and outputs are temporary.

Run: .venv/bin/python -B -m unittest discover -s tests -p 'test_variable_proof.py' -v
"""

from __future__ import annotations

import base64
import hashlib
from contextlib import redirect_stdout
from io import StringIO
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

import variable_proof
from variable_proof import write_variable_proof


ROOT = Path(__file__).resolve().parents[1]
SHIPPED = ROOT / "fonts/webfonts/AlloVariable.woff2"
CUSTOM = ROOT / "build/custom/fonts/webfonts/AlloCustomVariable.woff2"
CONFIG_PATTERN = re.compile(r'<script id="variable-proof-data" type="application/json">(.*?)</script>', re.S)


def config_from(html):
    match = CONFIG_PATTERN.search(html)
    if not match:
        raise AssertionError("Missing proof configuration")
    return json.loads(match[1])


def fixture_font(axes=(("TEST", -20.5, 2.25, 105.5, "Test axis"),), family="Fixture font"):
    builder = FontBuilder(1000, isTTF=True)
    glyphs = [".notdef", "space", "n", "g", "g.alt", "a", "a.alt"]
    builder.setupGlyphOrder(glyphs)
    builder.setupCharacterMap({0x20: "space", 0x6e: "n", 0x67: "g", 0x61: "a"})
    builder.setupGlyf({glyph: TTGlyphPen(None).glyph() for glyph in glyphs})
    builder.setupHorizontalMetrics({glyph: (500, 0) for glyph in glyphs})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({"familyName": family, "styleName": "Regular"})
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    builder.setupPost()
    if axes is not None:
        builder.setupFvar(axes, [])
    addOpenTypeFeaturesFromString(builder.font, """
        feature ss01 { sub a by a.alt; } ss01;
        feature ss04 { sub g by g.alt; } ss04;
        feature kern { pos n g -30; } kern;
    """)
    builder.font.flavor = "woff2"
    return builder.font


class Tags(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.stack = []
        self.mismatches = []
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.mismatches.append((tag, self.stack[:]))
        else:
            self.stack.pop()


class VariableProofTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="allo-variable-proof-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.output = self.root / "nested/variable-proof.html"

    def save_fixture(self, font=None):
        if font is None:
            font = fixture_font()
        self.addCleanup(font.close)
        path = self.root / "fixture.woff2"
        font.save(path)
        return path

    def check_real_font(self, path):
        before = path.read_bytes(), path.stat().st_mtime_ns
        with mock.patch.object(TTFont, "save", side_effect=AssertionError("Source must never be saved")):
            result = write_variable_proof(str(path), str(self.output))
        self.assertEqual(result, self.output)
        html = result.read_text(encoding="utf-8")
        config = config_from(html)
        self.assertEqual(base64.b64decode(config["fontBase64"], validate=True), before[0])
        self.assertEqual(config["sha256"], hashlib.sha256(before[0]).hexdigest())
        self.assertEqual(config["fontFamily"], "AlloVariableProof_" + config["sha256"][:16])
        self.assertEqual(config["filename"], path.name)
        with TTFont(path) as font:
            self.assertEqual(config["family"], font["name"].getBestFamilyName())
            self.assertEqual(config["axes"], [
                {"tag": str(axis.axisTag), "name": font["name"].getDebugName(axis.axisNameID),
                 "min": axis.minValue, "default": axis.defaultValue, "max": axis.maxValue}
                for axis in font["fvar"].axes
            ])
            self.assertEqual(config["features"], sorted({
                record.FeatureTag for tag in ("GSUB", "GPOS") if tag in font
                for record in font[tag].table.FeatureList.FeatureRecord
            }))
            self.assertEqual(config["codepoints"], sorted(font.getBestCmap()))
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)
        self.assertNotIn(variable_proof.DATA_PLACEHOLDER, html)
        self.assertNotIn(str(ROOT), html)
        self.assertNotIn("slnt", [axis["tag"] for axis in config["axes"]])
        return config

    def test_exact_shipped_bytes_and_axis_metadata_without_mutation(self):
        config = self.check_real_font(SHIPPED)
        self.assertEqual([(axis["tag"], axis["min"], axis["default"], axis["max"])
                          for axis in config["axes"]], [
            ("opsz", 9, 14, 32), ("wght", 100, 400, 900), ("ROND", 0, 50, 100),
        ])

    @unittest.skipUnless(CUSTOM.is_file(), "No current custom full variable WOFF2")
    def test_current_custom_font_read_only(self):
        self.check_real_font(CUSTOM)

    def test_arbitrary_axes_names_fractional_coordinates_and_hidden_axis(self):
        font = fixture_font(axes=(
            ("TEST", -20.5, 2.25, 105.5, "Custom amplitude"),
            ("opsz", 6, 11.5, 72, "Different optical size"),
            ("FIXD", 3, 3, 3, "Fixed coordinate"),
        ))
        font["fvar"].axes[0].flags = 1  # Hidden axes must still be offered.
        source = self.save_fixture(font)
        write_variable_proof(source, self.output)
        config = config_from(self.output.read_text())
        self.assertEqual(config["axes"], [
            {"tag": "TEST", "name": "Custom amplitude", "min": -20.5, "default": 2.25, "max": 105.5},
            {"tag": "opsz", "name": "Different optical size", "min": 6, "default": 11.5, "max": 72},
            {"tag": "FIXD", "name": "Fixed coordinate", "min": 3, "default": 3, "max": 3},
        ])
        self.assertEqual(config["features"], ["kern", "ss01", "ss04"])
        self.assertEqual(config["codepoints"], [0x20, 0x61, 0x67, 0x6e])

    def test_missing_axis_name_falls_back_to_tag(self):
        font = fixture_font()
        axis_id = font["fvar"].axes[0].axisNameID
        font["name"].names = [record for record in font["name"].names if record.nameID != axis_id]
        write_variable_proof(self.save_fixture(font), self.output)
        self.assertEqual(config_from(self.output.read_text())["axes"][0]["name"], "TEST")

    def test_missing_name_table_has_explicit_fallback(self):
        font = fixture_font()
        del font["name"]
        write_variable_proof(self.save_fixture(font), self.output)
        config = config_from(self.output.read_text())
        self.assertEqual(config["family"], "Embedded variable font")
        self.assertEqual(config["axes"][0]["name"], "TEST")

    def test_json_script_escaping_round_trips_untrusted_names_and_filename(self):
        hostile = '</script><script>alert("&")</script>\u2028\u2029 café'
        source = self.save_fixture(fixture_font(axes=(("TEST", 0, 1, 2, hostile),), family=hostile))
        renamed = source.with_name('font<>&".woff2')
        source.rename(renamed)
        write_variable_proof(renamed, self.output)
        html = self.output.read_text()
        config = config_from(html)
        self.assertEqual(config["family"], hostile)
        self.assertEqual(config["axes"][0]["name"], hostile)
        self.assertEqual(config["filename"], renamed.name)
        payload = CONFIG_PATTERN.search(html)[1]
        for unsafe in ("<", ">", "&", "\u2028", "\u2029"):
            self.assertNotIn(unsafe, payload)
        self.assertEqual(len([tag for tag, _ in Tags(html).tags if tag == "script"]), 2)
        self.assertIn(r"\u003c/script\u003e", payload)

    def test_download_link_is_optional_and_preserves_embedded_font(self):
        source = self.save_fixture()
        write_variable_proof(source, self.output)
        default = config_from(self.output.read_text())
        self.assertNotIn("downloadFilename", default)
        write_variable_proof(source, self.output, download_filename="AlloCustom-1.1.0.zip")
        published = config_from(self.output.read_text())
        self.assertEqual(published.pop("downloadFilename"), "AlloCustom-1.1.0.zip")
        self.assertEqual(published, default)

    def test_download_rejects_paths_urls_and_unsafe_names_without_replacing_output(self):
        source = self.save_fixture()
        self.output.parent.mkdir()
        self.output.write_text("previous proof")
        for filename in ("", "../font.zip", "/font.zip", "sub/font.zip", "sub\\font.zip",
                         "https://example.com/font.zip", "//example.com/font.zip", "font.zip?x",
                         "font.zip#x", "font<bad>.zip", "font.woff2", ".hidden.zip", 42):
            with self.subTest(filename=filename), self.assertRaisesRegex(ValueError, "local ZIP filename"):
                write_variable_proof(source, self.output, download_filename=filename)
            self.assertEqual(self.output.read_text(), "previous proof")

    def test_download_archive_cannot_be_the_output(self):
        source = self.save_fixture()
        archive = self.root / "font.zip"
        archive.write_bytes(b"untouched archive")
        with self.assertRaisesRegex(ValueError, "must not overwrite its download archive"):
            write_variable_proof(source, archive, download_filename=archive.name)
        self.assertEqual(archive.read_bytes(), b"untouched archive")

    def test_command_line_generates_the_same_downloadable_proof(self):
        source = self.save_fixture()
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(variable_proof.main([str(source), str(self.output), "--download", "font.zip"]), 0)
        self.assertIn(str(self.output), output.getvalue())
        self.assertEqual(config_from(self.output.read_text())["downloadFilename"], "font.zip")
        expected = self.output.read_bytes()
        write_variable_proof(source, self.output, download_filename="font.zip")
        self.assertEqual(self.output.read_bytes(), expected)

    def test_output_is_deterministic_and_replaces_only_html(self):
        source = self.save_fixture()
        write_variable_proof(source, self.output)
        expected = self.output.read_bytes()
        another = self.root / "another.html"
        another.write_text("previous output")
        write_variable_proof(source, another)
        self.assertEqual(another.read_bytes(), expected)
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), ["another.html", "fixture.woff2", "nested"])

    def test_source_template_is_distinct_from_a_browsable_proof(self):
        self.assertEqual(variable_proof.TEMPLATE_PATH, ROOT / "templates/variable-proof.html.template")
        self.assertTrue(variable_proof.TEMPLATE_PATH.is_file())
        self.assertFalse((ROOT / "documentation/variable-proof.html").exists())

    def test_template_has_balanced_markup(self):
        parsed = Tags(variable_proof.TEMPLATE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(parsed.mismatches, [])
        self.assertEqual(parsed.stack, [])

    def test_template_is_standalone_and_previews_start_hidden(self):
        write_variable_proof(self.save_fixture(), self.output)
        html = self.output.read_text()
        tags = Tags(html).tags
        self.assertEqual(html.count("</script>"), 2)
        self.assertFalse([(tag, attrs) for tag, attrs in tags if "src" in attrs or "href" in attrs])
        self.assertNotIn("@import", html)
        self.assertNotRegex(html, r"https?://")
        ids = {attrs["id"]: attrs for _, attrs in tags if "id" in attrs}
        self.assertIn("checked", ids["ss04"])
        for name in ("main-pair", "comparison-pair"):
            self.assertIn("hidden", ids[name])
        self.assertEqual(ids["font-status"]["role"], "status")
        self.assertIn("font-synthesis: none", html)
        self.assertIn("font-optical-sizing: none", html)
        self.assertNotIn("local(", html)

    def assert_rejected(self, source, message):
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text("existing proof")
        with self.assertRaisesRegex(ValueError, message):
            write_variable_proof(source, self.output)
        self.assertEqual(self.output.read_text(), "existing proof")
        self.assertEqual(list(self.output.parent.iterdir()), [self.output])

    def test_nonvariable_woff2_rejected_without_replacing_output(self):
        self.assert_rejected(self.save_fixture(fixture_font(axes=None)), "variable WOFF2.*fvar")

    def test_desktop_variable_font_rejected(self):
        font = fixture_font()
        font.flavor = None
        self.assert_rejected(self.save_fixture(font), "compiled variable WOFF2")

    def test_empty_axis_list_rejected(self):
        font = fixture_font()
        font["fvar"].axes = []
        self.assert_rejected(self.save_fixture(font), "at least one fvar axis")

    def test_invalid_ranges_rejected(self):
        for minimum, default, maximum in ((20, 10, 30), (0, 40, 30), (30, 20, 10)):
            with self.subTest(bounds=(minimum, default, maximum)):
                font = fixture_font()
                axis = font["fvar"].axes[0]
                axis.minValue, axis.defaultValue, axis.maxValue = minimum, default, maximum
                self.assert_rejected(self.save_fixture(font), "Invalid fvar range/default")

    def test_nonfinite_coordinates_rejected(self):
        source = self.save_fixture()
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                font = fixture_font()
                font["fvar"].axes[0].defaultValue = value
                with mock.patch.object(variable_proof, "TTFont", return_value=font):
                    self.assert_rejected(source, "Invalid fvar range/default")

    def test_duplicate_or_invalid_axis_tags_rejected(self):
        for tag in ("TEST", "bad\x00"):
            with self.subTest(tag=tag):
                font = fixture_font(axes=(("TEST", 0, 1, 2, "One"), ("OTHR", 0, 1, 2, "Two")))
                font["fvar"].axes[1].axisTag = tag
                self.assert_rejected(self.save_fixture(font), "Invalid or duplicate fvar axis tag")

    def test_corrupt_fonts_rejected(self):
        valid = SHIPPED.read_bytes()
        midpoint = len(valid) // 2
        damaged = valid[:midpoint] + bytes(64) + valid[midpoint + 64:]
        for data in (b"", b"not a font", valid[:32], valid[:-32], damaged):
            with self.subTest(length=len(data)):
                source = self.root / "broken.woff2"
                source.write_bytes(data)
                self.assert_rejected(source, "Cannot generate variable proof")

    def test_missing_input_propagates_file_error_without_creating_output_directory(self):
        with self.assertRaises(FileNotFoundError):
            write_variable_proof(self.root / "missing.woff2", self.output)
        self.assertFalse(self.output.parent.exists())

    def test_missing_template_propagates_file_error(self):
        source = self.save_fixture()
        with mock.patch.object(variable_proof, "TEMPLATE_PATH", self.root / "missing.html"):
            with self.assertRaises(FileNotFoundError):
                write_variable_proof(source, self.output)
        self.assertFalse(self.output.parent.exists())

    def test_bad_template_placeholder_count_preserves_output(self):
        source = self.save_fixture()
        template = self.root / "template.html"
        for text in ("no placeholder", variable_proof.DATA_PLACEHOLDER * 2):
            with self.subTest(text=text):
                template.write_text(text)
                with mock.patch.object(variable_proof, "TEMPLATE_PATH", template):
                    self.assert_rejected(source, "exactly one data placeholder")

    def test_input_cannot_be_overwritten_via_same_path_symlink_or_hardlink(self):
        source = self.save_fixture()
        symlink = self.root / "symlink.html"
        symlink.symlink_to(source)
        hardlink = self.root / "hardlink.html"
        hardlink.hardlink_to(source)
        before = source.read_bytes()
        for output in (source, symlink, hardlink):
            with self.subTest(output=output):
                with self.assertRaisesRegex(ValueError, "must not overwrite"):
                    write_variable_proof(source, output)
                self.assertEqual(source.read_bytes(), before)

    def test_output_io_failure_preserves_previous_file_and_cleans_temporary(self):
        source = self.save_fixture()
        self.output.parent.mkdir()
        self.output.write_text("previous proof")
        with mock.patch.object(variable_proof.os, "replace", side_effect=PermissionError("read-only output")):
            with self.assertRaisesRegex(PermissionError, "read-only output"):
                write_variable_proof(source, self.output)
        self.assertEqual(self.output.read_text(), "previous proof")
        self.assertEqual(list(self.output.parent.iterdir()), [self.output])

    def test_invalid_font_does_not_create_parent_directory(self):
        source = self.save_fixture(fixture_font(axes=None))
        with self.assertRaises(ValueError):
            write_variable_proof(source, self.output)
        self.assertFalse(self.output.parent.exists())


if __name__ == "__main__":
    unittest.main()
