"""Build-mode contracts without compiling fonts or writing outside temporary roots."""

from __future__ import annotations

import copy
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest import mock
import zipfile

from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables._f_v_a_r import NamedInstance
from fontTools.varLib import instancer

import build


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = ("Thin", "ExtraLight", "Light", "Regular", "Medium", "SemiBold", "Bold", "ExtraBold", "Black")
STYLES = tuple(style for weight in WEIGHTS for style in (
    weight, ("" if weight == "Regular" else weight) + "Oblique",
))
CONFIG = {"version": "9.8.7", "sourceDateEpoch": 1700000000, "smallShift": 17}


def font_paths(root, prefix):
    return {
        root / "fonts/variable" / f"{prefix}Variable.ttf",
        root / "fonts/webfonts" / f"{prefix}Variable.woff2",
        root / "fonts/webfonts" / f"{prefix}VariableFriendly.woff2",
        *(root / folder / f"{prefix}-{style}.{extension}"
          for style in STYLES
          for folder, extension in (("fonts/otf", "otf"), ("fonts/webfonts", "woff2"))),
    }


def snapshot(directory, excluding=None):
    return {
        str(path.relative_to(directory)): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in directory.rglob("*")
        if path.is_file() and (excluding is None or not path.is_relative_to(excluding))
    }


class StubFont:
    """Persist observable pipeline state, not real font data."""

    def __init__(self, root, stem, flavor=None, hinted=False):
        self.root = root
        self.stem = stem
        self.flavor = flavor
        self.hinted = hinted
        self.saves = []

    def save(self, path):
        path = Path(path)
        if not path.resolve().is_relative_to(self.root.resolve()):
            raise AssertionError(f"Font write escaped the temporary root: {path}")
        self.saves.append((path, self.flavor, self.stem))
        path.write_text(json.dumps({
            "stem": self.stem, "flavor": self.flavor, "hinted": self.hinted,
        }, sort_keys=True))

    def getBestCmap(self):
        return {0x61: "a", 0x67: "g"}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TemporaryRootTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="allo-build-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.patch(build, "ROOT", self.root)

    def patch(self, target, name, *args, **kwargs):
        patcher = mock.patch.object(target, name, *args, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def put(self, relative, data=b"fixture"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path


class OutputHelpersTests(TemporaryRootTests):
    def test_save_keeps_default_desktop_and_web_names(self):
        font = StubFont(self.root, "AlloVariable")
        desktop = self.root / "fonts/variable/AlloVariable.ttf"
        web = self.root / "fonts/webfonts/AlloVariable.woff2"
        self.assertEqual(build.save(font, desktop), [desktop, web])
        self.assertEqual(font.saves, [(desktop, None, "AlloVariable"), (web, "woff2", "AlloVariable")])
        self.assertIsNone(json.loads(desktop.read_text())["flavor"])
        self.assertEqual(json.loads(web.read_text())["flavor"], "woff2")

    def test_save_honors_explicit_custom_web_directory(self):
        font = StubFont(self.root, "AlloCustom-Regular")
        desktop = self.root / "build/custom/fonts/otf/AlloCustom-Regular.otf"
        web_dir = self.root / "build/custom/fonts/webfonts"
        web = web_dir / "AlloCustom-Regular.woff2"
        self.assertEqual(build.save(font, desktop, web_dir), [desktop, web])
        self.assertEqual(font.saves, [
            (desktop, None, "AlloCustom-Regular"), (web, "woff2", "AlloCustom-Regular"),
        ])
        self.assertFalse((self.root / "fonts").exists())

    def check_friendly_web(self, prefix, family, explicit_directory):
        variable = TTFont(recalcTimestamp=False)
        self.addCleanup(variable.close)
        variable["name"] = newTable("name")
        variable["name"].names = []
        identities = {
            1: f"{family} Variable", 3: f"{family} Variable Regular 1.000",
            4: f"{family} Variable Regular", 6: f"{prefix}Variable-Regular",
            16: f"{family} Variable", 18: f"{family} Variable Regular",
            21: f"{family} Variable", 25: f"{prefix}Variable",
            257: f"{prefix}Variable-DisplayBold",
        }
        expected = {
            1: f"{family} Variable Friendly", 3: f"{family} Variable Friendly Regular 1.000",
            4: f"{family} Variable Friendly Regular", 6: f"{prefix}VariableFriendly-Regular",
            16: f"{family} Variable Friendly", 18: f"{family} Variable Friendly Regular",
            21: f"{family} Variable Friendly", 25: f"{prefix}VariableFriendly",
            257: f"{prefix}VariableFriendly-DisplayBold",
        }
        unchanged = {
            0: f"Copyright {family} Variable", 2: "Regular", 17: "Regular", 22: "Regular",
            256: f"{family} Variable axis label", 65535: f"{prefix}Variable-NotAnInstanceName",
        }
        for name_id, text in (identities | unchanged).items():
            for platform, encoding, language in ((1, 0, 0), (3, 1, 0x409), (3, 1, 0x40c)):
                variable["name"].setName(text, name_id, platform, encoding, language)
        variable["fvar"] = newTable("fvar")
        variable["fvar"].instances = [NamedInstance(), NamedInstance()]
        variable["fvar"].instances[0].postscriptNameID = 257
        variable["fvar"].instances[1].postscriptNameID = 65535
        original = [record.toBytes() for record in variable["name"].names]
        friendly = copy.deepcopy(variable)
        self.addCleanup(friendly.close)
        instantiate = self.patch(instancer, "instantiateVariableFont", return_value=friendly)
        saved = self.patch(friendly, "save", side_effect=lambda path: path.write_bytes(b"friendly font"))
        if explicit_directory:
            directory = self.root / "build/custom/fonts/webfonts"
            result = build.friendly_web(variable, directory, prefix, family)
            self.assertFalse((self.root / "fonts").exists())
        else:
            directory = self.root / "fonts/webfonts"
            result = build.friendly_web(variable)
        self.assertEqual(result, directory / f"{prefix}VariableFriendly.woff2")
        self.assertEqual(result.read_bytes(), b"friendly font")
        instantiate.assert_called_once_with(variable, {"ROND": 50})
        saved.assert_called_once_with(result)
        self.assertEqual(friendly.flavor, "woff2")
        self.assertIsNone(variable.flavor)
        self.assertEqual([record.toBytes() for record in variable["name"].names], original)
        for before, record in zip(original, friendly["name"].names):
            with self.subTest(name_id=record.nameID, language=record.langID):
                self.assertEqual(record.toUnicode(), (expected | unchanged)[record.nameID])
                if record.nameID in unchanged:
                    self.assertEqual(record.toBytes(), before)

    def test_friendly_web_default_family_and_filename_are_unchanged(self):
        self.check_friendly_web("Allo", "Allo", explicit_directory=False)

    def test_friendly_web_custom_names_include_explicit_instance_postscript_ids(self):
        self.check_friendly_web("AlloCustom", "Allo Custom", explicit_directory=True)

    def test_file_hashes_are_sorted_relative_and_include_nonfont_files(self):
        contents = {"z/empty.ttf": b"", "a/font.woff2": b"\x00\xfffont", "SHA256SUMS": b"old sums\n"}
        for name, data in contents.items():
            self.put(name, data)
        (self.root / "empty-directory").mkdir()
        before = snapshot(self.root)
        hashes = build.file_hashes(self.root)
        self.assertEqual(hashes, {
            name: hashlib.sha256(data).hexdigest() for name, data in contents.items()
        })
        self.assertEqual(list(hashes), sorted(contents))
        self.assertEqual(snapshot(self.root), before)
        self.put("a/font.woff2", b"changed")
        self.assertNotEqual(build.file_hashes(self.root), hashes)
        (self.root / "a/font.woff2").unlink()
        self.assertNotIn("a/font.woff2", build.file_hashes(self.root))
        self.put("added.txt", b"new")
        self.assertIn("added.txt", build.file_hashes(self.root))

    def test_custom_output_root_accepts_missing_or_ordinary_tree_without_writes(self):
        output = self.root / "build/custom"
        self.assertEqual(build.custom_output_root(), output)
        self.assertFalse(output.exists())
        self.put("build/custom/fonts/otf/old.otf")
        before = snapshot(self.root)
        self.assertEqual(build.custom_output_root(), output)
        self.assertEqual(snapshot(self.root), before)

    def test_custom_output_root_rejects_nondirectory(self):
        self.put("build/custom")
        with self.assertRaisesRegex(ValueError, "must be a directory"):
            build.custom_output_root()

    def test_custom_output_root_rejects_directory_file_and_dangling_symlinks(self):
        for index, location in enumerate((
            "build", "build/custom", "build/custom/fonts/webfonts",
            "build/custom/naming-validation.json",
        )):
            for kind in ("directory", "file", "missing"):
                with self.subTest(location=location, kind=kind):
                    case = self.root / f"case-{index}-{kind}"
                    root = case / "project"
                    target = case / "outside"
                    root.mkdir(parents=True)
                    if kind == "directory":
                        target.mkdir()
                        (target / "sentinel").write_bytes(b"untouched")
                    elif kind == "file":
                        target.write_bytes(b"untouched")
                    link = root / location
                    link.parent.mkdir(parents=True, exist_ok=True)
                    link.symlink_to(target, target_is_directory=kind == "directory")
                    with mock.patch.object(build, "ROOT", root):
                        with self.assertRaisesRegex(ValueError, "symlink"):
                            build.custom_output_root()
                    self.assertTrue(link.is_symlink())
                    if kind == "directory":
                        self.assertEqual(snapshot(target).keys(), {"sentinel"})
                        self.assertEqual((target / "sentinel").read_bytes(), b"untouched")
                    elif kind == "file":
                        self.assertEqual(target.read_bytes(), b"untouched")
                    else:
                        self.assertFalse(target.exists())


class BuildModeTests(TemporaryRootTests):
    def setUp(self):
        super().setUp()
        self.patch(build, "CONFIG", CONFIG.copy())
        environment = mock.patch.dict(os.environ, {"SOURCE_DATE_EPOCH": str(CONFIG["sourceDateEpoch"])})
        environment.start()
        self.addCleanup(environment.stop)
        self.output = self.root / "build/custom"
        self.put("sources/Allo.designspace", b"mock designspace")
        for style in STYLES:
            self.put(f"sources/static/Allo-{style}.ufo/fontinfo.plist", b"mock UFO")
        for path in font_paths(self.root, "Allo"):
            self.put(path.relative_to(self.root), b"release reference: " + path.name.encode())
        for name in ("allo.css", "allo-friendly.css", "OFL.txt"):
            self.put(name, (PROJECT_ROOT / name).read_bytes())
        self.put("fonts/SHA256SUMS", b"original release checksums\n")
        self.put(f"Allo-{CONFIG['version']}.zip", b"original release archive")
        self.put("README.md", b"original project readme")
        self.put("release.json", json.dumps(CONFIG).encode())
        self.put("proofs/sentinel.txt", b"original proof")
        self.put("build/other/sentinel.txt", b"unrelated build output")
        self.protected = snapshot(self.root, excluding=self.output)

        info = SimpleNamespace(openTypeOS2WinAscent=2300, openTypeOS2WinDescent=560)
        source = SimpleNamespace(font=SimpleNamespace(info=info))
        self.designspace = SimpleNamespace(
            sources=[source], instances=[], loadSourceFonts=mock.Mock(),
            findDefault=mock.Mock(return_value=source),
        )
        self.load_designspace = self.patch(build.DesignSpaceDocument, "fromfile", return_value=self.designspace)
        self.load_ufo = self.patch(build.ufoLib2.Font, "open", side_effect=lambda path: SimpleNamespace(stem=path.stem, info=info))
        self.check_win = self.patch(build, "check_win")
        self.variable = None
        self.compile_variable = self.patch(build, "compileVariableTTF", side_effect=self.compile_variable_font)
        self.compiled_statics = []
        self.compile_otf = self.patch(build, "compileOTF", side_effect=self.compile_static)
        self.exact_small = self.patch(build, "exact_small")
        self.drop_unreachable = self.patch(build, "drop_unreachable")
        self.smooth_unhinted = self.patch(build, "smooth_unhinted")
        self.rename = self.patch(build, "rename_for_custom", side_effect=self.rename_font)
        self.load_tt = self.patch(build, "TTFont", side_effect=self.read_font)
        self.friendly = self.patch(build, "friendly_web", side_effect=self.write_friendly)
        self.hint = self.patch(build, "hint_otfs", side_effect=self.hint_fonts)
        self.validation_inputs = None
        self.validate = self.patch(build, "validate_custom_fonts", side_effect=self.validate_fonts)

    def compile_variable_font(self, designspace, **kwargs):
        self.variable = StubFont(self.root, "AlloVariable")
        return self.variable

    def compile_static(self, ufo, **kwargs):
        font = StubFont(self.root, ufo.stem)
        self.compiled_statics.append(font)
        return font

    @staticmethod
    def rename_font(font):
        font.stem = "AlloCustom" + font.stem[len("Allo"):]

    def read_font(self, path):
        return StubFont(self.root, **json.loads(path.read_text()))

    def write_friendly(self, variable, web_dir, prefix, family):
        self.assertIsNone(variable.flavor, "Friendly must be derived from the reloaded desktop font")
        path = web_dir / f"{prefix}VariableFriendly.woff2"
        StubFont(self.root, f"{prefix}VariableFriendly", flavor="woff2").save(path)
        return path

    def hint_fonts(self, pairs):
        for paths in pairs.values():
            for path in paths:
                font = self.read_font(path)
                font.hinted = True
                font.save(path)

    def validate_fonts(self, files, references):
        # main subsequently appends packaging files to the same list.
        self.validation_inputs = (tuple(files), tuple(references))
        self.assertTrue(all(path.is_file() for path in (*files, *references)))
        return {"status": "ok", "custom_font_count": len(files), "release_font_count": len(references)}

    def run_build(self, custom=True):
        with redirect_stdout(io.StringIO()) as stdout:
            build.main(["--custom"] if custom else [])
        return stdout.getvalue()

    def assert_pipeline(self, output, prefix):
        self.load_designspace.assert_called_once_with(self.root / "sources/Allo.designspace")
        self.designspace.loadSourceFonts.assert_called_once_with(self.load_ufo)
        self.assertEqual(self.load_ufo.call_count, 18)
        self.compile_variable.assert_called_once_with(self.designspace, useProductionNames=False, flattenComponents=True)
        self.assertEqual(self.compile_otf.call_count, 18)
        for call in self.compile_otf.call_args_list:
            self.assertEqual(call.kwargs, {"removeOverlaps": False, "useProductionNames": False})
        self.exact_small.assert_called_once_with(self.variable, CONFIG["smallShift"])
        self.assertEqual(self.drop_unreachable.call_count, 19)
        self.smooth_unhinted.assert_called_once_with(self.variable)
        self.assertEqual(self.friendly.call_args.args[1:], (
            output / "fonts/webfonts", prefix, "Allo Custom" if prefix == "AlloCustom" else "Allo",
        ))
        self.hint.assert_called_once_with({
            weight: (
                output / "fonts/otf" / f"{prefix}-{weight}.otf",
                output / "fonts/otf" / f"{prefix}-{'' if weight == 'Regular' else weight}Oblique.otf",
            ) for weight in WEIGHTS
        })
        expected = font_paths(output, prefix)
        self.assertEqual(len(expected), 39)
        actual = {path for path in (output / "fonts").rglob("*") if path.suffix in (".otf", ".ttf", ".woff2")}
        self.assertEqual(actual, expected)
        for path in expected:
            with self.subTest(font=path.name):
                data = json.loads(path.read_text())
                self.assertEqual(data["stem"], path.stem)
                self.assertEqual(data["flavor"], "woff2" if path.suffix == ".woff2" else None)
                self.assertEqual(data["hinted"], "Variable" not in path.stem)
        hashes = {str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest() for path in expected}
        self.assertEqual((output / "fonts/SHA256SUMS").read_text(), "".join(
            f"{digest}  {name}\n" for name, digest in sorted(hashes.items())
        ))
        return hashes

    def test_default_routing_and_archive_remain_release_compatible(self):
        stdout = self.run_build(custom=False)
        self.assert_pipeline(self.root, "Allo")
        self.rename.assert_not_called()
        self.validate.assert_not_called()
        self.assertFalse(self.output.exists())
        self.assertFalse((self.root / "README.txt").exists())
        self.assertFalse((self.root / "naming-validation.json").exists())
        self.assertIn("39 font files built", stdout)
        archive = self.root / f"Allo-{CONFIG['version']}.zip"
        folder = f"Allo-{CONFIG['version']}/"
        expected = {str(path.relative_to(self.root)) for path in font_paths(self.root, "Allo")}
        with zipfile.ZipFile(archive) as zipped:
            self.assertEqual(zipped.namelist(), sorted(folder + name for name in expected | {"README.txt", "OFL.txt"}))
            for name in expected | {"OFL.txt"}:
                self.assertEqual(zipped.read(folder + name), (self.root / name).read_bytes())
            readme = zipped.read(folder + "README.txt").decode()
            self.assertIn(f"ALLO  {CONFIG['version']}", readme)
            self.assertIn("AlloVariable.ttf", readme)
            self.assertIn('font-family: "Allo"', readme)
            self.assertNotIn("Allo Custom", readme)
        for name, before in self.protected.items():
            if not name.startswith("fonts/") and name != archive.name:
                self.assertEqual(snapshot(self.root)[name], before)

    def test_custom_routes_all_fonts_and_preserves_release_sources_and_proofs(self):
        stdout = self.run_build()
        hashes = self.assert_pipeline(self.output, "AlloCustom")
        self.assertEqual(self.rename.call_count, 19)
        self.rename.assert_has_calls([mock.call(self.variable), *(mock.call(font) for font in self.compiled_statics)])
        self.assertEqual(self.variable.saves[0][2], "AlloCustomVariable")
        self.assertTrue(all(font.saves[0][2].startswith("AlloCustom-") for font in self.compiled_statics))
        self.validate.assert_called_once()
        files, references = self.validation_inputs
        self.assertEqual(len(files), 39)
        self.assertEqual(set(files), font_paths(self.output, "AlloCustom"))
        self.assertEqual(references, tuple(sorted(font_paths(self.root, "Allo"))))
        report = json.loads((self.output / "naming-validation.json").read_text())
        self.assertEqual(report, {
            "status": "ok", "custom_font_count": 39, "release_font_count": 39,
            "release_files_unchanged": True, "font_sha256": hashes,
        })
        self.assertEqual(snapshot(self.root, excluding=self.output), self.protected)
        self.assertIn(f"build/custom/AlloCustom-{CONFIG['version']}.zip", stdout)

    def test_custom_css_families_and_urls_match_packaged_fonts(self):
        self.run_build()
        for css_name, variable in (("allo-custom.css", "AlloCustomVariable"),
                                   ("allo-custom-friendly.css", "AlloCustomVariableFriendly")):
            with self.subTest(css=css_name):
                css = (self.output / css_name).read_text()
                self.assertTrue(css.startswith("/* Allo Custom (modified build) "))
                blocks = re.findall(r"@font-face\s*\{([^}]+)\}", css)
                self.assertEqual(len(blocks), 10)
                expected = [(variable, "100 900", "normal")] + [
                    (f"AlloCustom-{'' if weight == 'Regular' else weight}Oblique", str(index * 100), "italic")
                    for index, weight in enumerate(WEIGHTS, 1)
                ]
                for block, (stem, weight, style) in zip(blocks, expected):
                    self.assertEqual(re.findall(r'font-family:\s*"([^"]+)"', block), ["Allo Custom"])
                    urls = re.findall(r'url\("([^"]+)"\)', block)
                    self.assertEqual(urls, [f"./fonts/webfonts/{stem}.woff2"])
                    self.assertTrue((self.output / urls[0]).is_file())
                    self.assertIn(f"font-weight: {weight};", block)
                    self.assertIn(f"font-style: {style};", block)
                    self.assertIn("font-display: swap;", block)
                    self.assertIn('format("woff2")', block)
        self.assertEqual((self.output / "OFL.txt").read_bytes(), (self.root / "OFL.txt").read_bytes())
        self.assertEqual(snapshot(self.root, excluding=self.output), self.protected)

    def test_custom_readme_explains_identity_and_retains_attribution(self):
        self.run_build()
        readme = (self.output / "README.txt").read_text()
        for text in (
            f"ALLO CUSTOM  {CONFIG['version']}", "not an upstream release",
            "naming alone adds no glyphs or features", "single-storey g remains default",
            "ss04 is not added", "Static family: Allo Custom", "Variable family: Allo Custom Variable",
            "No fonts are installed automatically", "allo-custom.css", "allo-custom-friendly.css",
            "naming-validation.json", "fonts/SHA256SUMS", "AlloCustomVariable.ttf",
            "AlloCustomVariableFriendly.woff2", 'font-family: "Allo Custom"',
            "CHARACTERS  (2)", "Josh Puckett", "joshpuckett.me", "SIL Open Font License 1.1",
        ):
            with self.subTest(text=text):
                self.assertIn(text, readme)
        self.assertNotIn("AlloVariable", readme)
        self.assertNotIn('"Allo Variable"', readme)
        self.assertNotIn("{version}", readme)
        self.assertNotIn("{characters}", readme)

    def test_custom_archive_contains_exact_outputs_with_reproducible_metadata(self):
        self.put("build/custom/unrelated.txt", b"do not package")
        self.run_build()
        archive = self.output / f"AlloCustom-{CONFIG['version']}.zip"
        folder = f"AlloCustom-{CONFIG['version']}/"
        expected = {str(path.relative_to(self.output)) for path in font_paths(self.output, "AlloCustom")}
        expected |= {"README.txt", "OFL.txt", "allo-custom.css", "allo-custom-friendly.css",
                     "fonts/SHA256SUMS", "naming-validation.json"}
        with zipfile.ZipFile(archive) as zipped:
            self.assertIsNone(zipped.testzip())
            self.assertEqual(zipped.namelist(), sorted(folder + name for name in expected))
            for info in zipped.infolist():
                self.assertEqual(info.date_time, time.gmtime(CONFIG["sourceDateEpoch"])[:6])
                self.assertEqual(info.compress_type, zipfile.ZIP_DEFLATED)
                self.assertEqual((info.external_attr >> 16) & 0o777, 0o644)
                self.assertEqual(zipped.read(info), (self.output / info.filename[len(folder):]).read_bytes())
        before = {name: (self.output / name).read_bytes() for name in (
            archive.name, "naming-validation.json", "fonts/SHA256SUMS", "README.txt",
        )}
        self.run_build()
        self.assertEqual({name: (self.output / name).read_bytes() for name in before}, before)
        self.assertEqual(snapshot(self.root, excluding=self.output), self.protected)

    def test_reference_discovery_accepts_uppercase_extensions_not_other_files(self):
        reference = self.put("fonts/extra/Reference.TTF", b"extra mock reference")
        self.put("fonts/extra/notes.txt", b"not a reference font")
        self.run_build()
        self.assertEqual(self.validation_inputs[1], tuple(sorted(font_paths(self.root, "Allo") | {reference})))

    def test_custom_without_release_references_fails_before_compilation(self):
        for path in font_paths(self.root, "Allo"):
            path.unlink()
        with self.assertRaisesRegex(ValueError, "release reference fonts"):
            self.run_build()
        self.load_designspace.assert_not_called()
        self.compile_variable.assert_not_called()
        self.validate.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_missing_references_invalidates_previous_success_report(self):
        report = self.put("build/custom/naming-validation.json", b'{"status": "ok"}\n')
        for path in font_paths(self.root, "Allo"):
            path.unlink()
        with self.assertRaisesRegex(ValueError, "release reference fonts"):
            self.run_build()
        self.assertFalse(report.exists(), "A failed custom rebuild must not retain an old success report")

    def test_failures_during_load_compile_hint_or_validation_invalidate_old_report(self):
        for stage in (self.load_designspace, self.compile_variable, self.hint, self.validate):
            with self.subTest(stage=stage._mock_name):
                report = self.put("build/custom/naming-validation.json", b'{"status": "ok"}\n')
                with mock.patch.object(stage, "side_effect", RuntimeError("injected build failure")):
                    with self.assertRaisesRegex(RuntimeError, "injected build failure"):
                        self.run_build()
                self.assertFalse(report.exists())
                self.assertFalse((self.output / f"AlloCustom-{CONFIG['version']}.zip").exists())
                self.assertEqual(snapshot(self.root, excluding=self.output), self.protected)

    def test_release_hash_change_aborts_without_success_report_or_archive(self):
        report = self.put("build/custom/naming-validation.json", b'{"status": "ok"}\n')

        def change_release(files, references):
            result = self.validate_fonts(files, references)
            (self.root / "fonts/SHA256SUMS").write_bytes(b"unexpected change")
            return result

        self.validate.side_effect = change_release
        with self.assertRaisesRegex(RuntimeError, "Release reference files changed"):
            self.run_build()
        self.assertFalse(report.exists())
        self.assertFalse((self.output / f"AlloCustom-{CONFIG['version']}.zip").exists())

    def test_main_rejects_symlink_before_loading_or_writing(self):
        self.output.mkdir(parents=True)
        link = self.output / "fonts"
        link.symlink_to(self.root / "fonts", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.run_build()
        self.load_designspace.assert_not_called()
        self.compile_variable.assert_not_called()
        self.assertTrue(link.is_symlink())
        self.assertEqual(snapshot(self.root, excluding=self.output), self.protected)


if __name__ == "__main__":
    unittest.main()
