"""Keep the committed Pages snapshot and downloadable font bundle consistent."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
import zipfile

from variable_proof import write_variable_proof

ROOT = Path(__file__).resolve().parents[1]
VERSION = json.loads((ROOT / "release.json").read_text())["version"]
ARCHIVE = ROOT / f"AlloCustom-{VERSION}.zip"
PREFIX = f"AlloCustom-{VERSION}/"
CONFIG = re.compile(r'<script id="variable-proof-data" type="application/json">(.*?)</script>', re.S)


class PublishedProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.config = json.loads(CONFIG.search(cls.html)[1])

    def test_page_is_current_and_embeds_the_exact_downloadable_font(self):
        self.assertEqual(self.config["downloadFilename"], ARCHIVE.name)
        self.assertEqual(self.config["filename"], "AlloCustomVariable.woff2")
        with zipfile.ZipFile(ARCHIVE) as archive:
            font = archive.read(PREFIX + "fonts/webfonts/AlloCustomVariable.woff2")
        self.assertEqual(base64.b64decode(self.config["fontBase64"], validate=True), font)
        self.assertEqual(self.config["sha256"], hashlib.sha256(font).hexdigest())
        self.assertEqual({axis["tag"] for axis in self.config["axes"]}, {"opsz", "wght", "ROND"})
        self.assertTrue({"ss01", "ss04"} <= set(self.config["features"]))
        with tempfile.TemporaryDirectory(prefix="allo-published-proof-") as directory:
            source = Path(directory) / self.config["filename"]
            source.write_bytes(font)
            generated = write_variable_proof(source, Path(directory) / "index.html", download_filename=ARCHIVE.name)
            self.assertEqual(generated.read_text(encoding="utf-8"), self.html,
                             "Refresh index.html after changing the proof template/generator")

    def test_archive_checksums_license_and_offline_proof(self):
        with zipfile.ZipFile(ARCHIVE) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(len(archive.namelist()), len(set(archive.namelist())))
            self.assertEqual(archive.read(PREFIX + "OFL.txt"), (ROOT / "OFL.txt").read_bytes())
            sums = dict((name, digest) for digest, name in
                        (line.split("  ", 1) for line in archive.read(PREFIX + "fonts/SHA256SUMS").decode().splitlines()))
            self.assertEqual(len(sums), 39)
            for name, digest in sums.items():
                with self.subTest(font=name):
                    self.assertEqual(hashlib.sha256(archive.read(PREFIX + name)).hexdigest(), digest)
            report = json.loads(archive.read(PREFIX + "naming-validation.json"))
            self.assertEqual(report["font_sha256"], sums)
            self.assertTrue(report["release_files_unchanged"])
            offline = json.loads(CONFIG.search(archive.read(PREFIX + "variable-proof.html").decode())[1])
            self.assertNotIn("downloadFilename", offline, "The extracted proof must not link to a missing ZIP")
            self.assertEqual(offline["fontBase64"], self.config["fontBase64"])

    def test_pages_root_is_static_not_a_redirect_or_build_cache(self):
        self.assertTrue((ROOT / ".nojekyll").is_file())
        self.assertNotRegex(self.html, r'http-equiv=["\']refresh')
        self.assertNotIn("__VARIABLE_PROOF_DATA__", self.html)
        self.assertNotIn("build/custom/", self.html)
        self.assertNotIn(str(ROOT), self.html)


if __name__ == "__main__":
    unittest.main()
