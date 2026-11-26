#!/usr/bin/env python3
"""Build a standalone Regular-weight design proof; never write production fonts."""
from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
from xml.sax.saxutils import escape

from booleanOperations.booleanGlyph import BooleanGlyph
from fontTools.pens.areaPen import AreaPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.ttLib import TTFont
from fontTools.ufoLib.glifLib import readGlyphFromString
from PIL import Image, ImageDraw, ImageFont, features
from ufoLib2.objects import Glyph

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ORIGINAL = ROOT / "fonts/otf/Allo-Regular.otf"
CANDIDATE = HERE / "AlloGStudy-Regular.otf"
GLIF = HERE / "g.ss04.glif"
UPM = 2048


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bounds(glyph):
    pen = BoundsPen(None)
    glyph.draw(pen)
    return pen.bounds


def area(outline):
    pen = AreaPen(None)
    outline.draw(pen)
    return pen.value


def recording(glyph):
    pen = RecordingPen()
    glyph.draw(pen)
    return pen.value


def shape(path, text):
    result = subprocess.run(
        ["hb-shape", "--output-format=json", f"--font-size={UPM}",
         "--direction=ltr", "--language=en", str(path), text],
        check=True, capture_output=True, text=True, timeout=15,
    )
    return json.loads(result.stdout)


def build_font():
    original_hash = digest(ORIGINAL)
    glyph = Glyph(name="g.ss04")
    readGlyphFromString(GLIF.read_text(), glyph, glyph.getPointPen())
    assert glyph.name == "g.ss04" and glyph.width == 1243
    assert not glyph.unicodes and not glyph.components
    assert len(glyph.contours) == 3
    signed_areas = [area(contour) for contour in glyph.contours]
    assert signed_areas[0] > 0 and all(a < 0 for a in signed_areas[1:])
    cleaned = BooleanGlyph(glyph).removeOverlap()
    assert len(cleaned.contours) == 3, "Unexpected overlap or contour topology"
    assert abs(abs(area(cleaned)) - abs(area(glyph))) < 1

    font = TTFont(ORIGINAL, recalcTimestamp=False)
    assert font["head"].unitsPerEm == UPM
    assert font["OS/2"].usWeightClass == 400
    top = font["CFF "].cff.topDictIndex[0]
    # The existing CFF has a nonzero nominalWidthX: Type 2 encodes a delta.
    pen = T2CharStringPen(glyph.width - top.Private.nominalWidthX, None)
    glyph.draw(pen)
    top.CharStrings["g"] = pen.getCharString(
        private=top.Private, globalSubrs=font["CFF "].cff.GlobalSubrs,
    )
    font["hmtx"]["g"] = (int(glyph.width), round(bounds(glyph)[0]))
    names = {
        1: "Allo G Study", 2: "Regular", 3: "AlloGStudy-01-Regular",
        4: "Allo G Study Regular", 5: "Version 0.001; design proof only",
        6: "AlloGStudy-Regular", 16: "Allo G Study", 17: "Regular",
        18: "Allo G Study Regular", 21: "Allo G Study", 22: "Regular",
    }
    for record in font["name"].names:
        if record.nameID in names:
            record.string = names[record.nameID]
    font["CFF "].cff.fontNames[0] = "AlloGStudy-Regular"
    top.FamilyName = "Allo G Study"
    top.FullName = "Allo G Study Regular"
    top.version = "0.001"
    font["head"].fontRevision = 0.001
    font.save(CANDIDATE)
    font.close()

    original = TTFont(ORIGINAL)
    candidate = TTFont(CANDIDATE)
    assert original.getGlyphOrder() == candidate.getGlyphOrder()
    assert original.getBestCmap() == candidate.getBestCmap()
    old, new = original.getGlyphSet(), candidate.getGlyphSet()
    unchanged = 0
    for name in original.getGlyphOrder():
        assert original["hmtx"][name][0] == candidate["hmtx"][name][0]
        if name != "g":
            assert recording(old[name]) == recording(new[name]), name
            assert original["hmtx"][name] == candidate["hmtx"][name]
            unchanged += 1
    assert recording(old["g"]) != recording(new["g"])
    assert bounds(new["g"]) == bounds(glyph)
    assert candidate["CFF "].cff.topDictIndex[0].CharStrings["g"].width == 1243
    for tag in ("GSUB", "GPOS", "GDEF"):
        assert original.getTableData(tag) == candidate.getTableData(tag), tag
    for sample in ("going baggage", "giggling analogue", "ag og ng gg gy gr", "Good beginnings"):
        assert shape(ORIGINAL, sample) == shape(CANDIDATE, sample), sample
    assert digest(ORIGINAL) == original_hash
    assert bounds(new["g"])[1] >= -candidate["OS/2"].usWinDescent
    assert bounds(new["g"])[3] <= candidate["OS/2"].usWinAscent
    assert candidate["name"].getDebugName(1) == "Allo G Study"
    report = {
        "scope": "Regular upright; plain lowercase g only; separate proof font",
        "reference": str(ORIGINAL.relative_to(ROOT)),
        "reference_sha256": original_hash,
        "glif_sha256": digest(GLIF),
        "proof_sha256": digest(CANDIDATE),
        "units_per_em": UPM,
        "advance_width": glyph.width,
        "reference_bounds": bounds(old["g"]),
        "candidate_bounds": bounds(new["g"]),
        "contours": len(glyph.contours),
        "unchanged_other_glyph_outlines": unchanged,
        "checks_passed": [
            "Three contours with opposite outer/counter winding",
            "Overlap removal preserves three contours and area within 1 square unit",
            "Compiled outline bounds and CFF width match the GLIF",
            "All other glyph outlines, mappings and metrics preserved",
            "All advance widths and GSUB/GPOS/GDEF tables preserved",
            "Four shaping samples retain identical glyph sequences and positioning",
            "Outline fits existing Windows vertical metrics",
            "Proof font has a distinct family name",
            "Original font SHA-256 unchanged",
        ],
        "limitations": [
            "Design proposal, not a released feature",
            "Existing g spacing and kerning are provisional for this new shape",
            "No accent, other weight, optical-size, roundness or oblique implementation",
            "Replacement g is unhinted; the other glyphs keep their original hints",
        ],
    }
    (HERE / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    original.close()
    candidate.close()
    return report


class Sheet:
    """Outline-based SVG plus a 2x FreeType/HarfBuzz raster of the same layout."""
    width, height, scale = 1440, 1290, 2

    def __init__(self):
        self.fonts = {path: TTFont(path) for path in (ORIGINAL, CANDIDATE)}
        self.paths = {}
        self.raster_fonts = {}
        self.svg = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" viewBox="0 0 {self.width} {self.height}">',
            '<title>Allo: double-storey g, Regular-weight design proof 01</title>',
            '<desc>Current single-storey g at left, proposed double-storey g at right. Both use the same advance width.</desc>',
            '<rect width="100%" height="100%" fill="white"/>',
        ]
        self.image = Image.new("RGB", (self.width * self.scale, self.height * self.scale), "white")
        self.draw = ImageDraw.Draw(self.image)

    def text(self, x, baseline, text, size=18, color="#191919", font=ORIGINAL):
        glyphs = self.fonts[font].getGlyphSet()
        parts, cursor = [], 0
        for item in shape(font, text):
            name = item["g"]
            assert name != ".notdef", f"Missing character in {text!r}"
            key = (font, name)
            if key not in self.paths:
                pen = SVGPathPen(glyphs)
                glyphs[name].draw(pen)
                self.paths[key] = pen.getCommands()
            parts.append(f'<path transform="translate({cursor + item["dx"]} {item["dy"]})" d="{self.paths[key]}"/>')
            cursor += item["ax"]
        assert x + cursor * size / UPM <= self.width - 60, text
        self.svg.append(
            f'<g aria-label="{escape(text, {chr(34): "&quot;"})}" fill="{color}" '
            f'transform="translate({x} {baseline}) scale({size / UPM} {-size / UPM})">'
            + "".join(parts) + "</g>"
        )
        key = (font, size)
        if key not in self.raster_fonts:
            self.raster_fonts[key] = ImageFont.truetype(
                str(font), size * self.scale, layout_engine=ImageFont.Layout.RAQM,
            )
        self.draw.text(
            (x * self.scale, baseline * self.scale), text,
            font=self.raster_fonts[key], fill=color, anchor="ls", language="en",
        )

    def line(self, x1, y1, x2, y2, color="#dedede"):
        self.svg.append(f'<path d="M{x1} {y1}H{x2}" fill="none" stroke="{color}"/>')
        self.draw.line(tuple(v * self.scale for v in (x1, y1, x2, y2)), fill=color, width=self.scale)

    def save(self):
        self.svg.append("</svg>")
        (HERE / "proof.svg").write_text("\n".join(self.svg) + "\n")
        self.image.save(HERE / "proof.png")
        for font in self.fonts.values():
            font.close()


def build_sheet():
    sheet = Sheet()
    sheet.text(80, 58, "ALLO / GLYPH STUDY 01", 15, "#626262")
    sheet.text(80, 116, "A double-storey g", 40)
    sheet.text(80, 155, "Regular upright · Text proportions · Friendly roundness · First design proof", 18, "#626262")
    sheet.line(80, 185, 1360, 185)
    for x, font, title in (
        (80, ORIGINAL, "CURRENT / SINGLE-STOREY"),
        (760, CANDIDATE, "CANDIDATE / DOUBLE-STOREY"),
    ):
        sheet.text(x, 224, title, 15, "#626262")
        for y in (510 - 1118 * 440 / UPM, 510, 510 + 412 * 440 / UPM):
            sheet.line(x, y, x + 600, y, "#e9e9e9")
        sheet.text(x + 150, 510, "g", 440, font=font)
        sheet.text(x, 635, "Same 1,243-unit advance · same descender depth", 15, "#626262")
        sheet.text(x, 708, "going   baggage", 56, font=font)
        sheet.text(x, 781, "giggling   analogue", 56, font=font)
        sheet.line(x, 819, x + 600, 819)
        sheet.text(x, 854, "24 PX", 12, "#626262")
        sheet.text(x, 891, "A good beginning grows into something great.", 24, font=font)
        sheet.text(x, 946, "16 PX", 12, "#626262")
        sheet.text(x, 979, "Good things grow gradually. A winding garden path", 16, font=font)
        sheet.text(x, 1005, "brings neighbours together, again and again.", 16, font=font)
        sheet.text(x, 1055, "12 PX", 12, "#626262")
        sheet.text(x, 1084, "Good things grow gradually. A winding garden path brings", 12, font=font)
        sheet.text(x, 1105, "neighbours together, again and again. Going, gathering, belonging.", 12, font=font)
    sheet.line(80, 1162, 1360, 1162)
    sheet.text(80, 1201, "PROOF ONLY", 13, "#626262")
    sheet.text(80, 1232, "Only plain g is changed. Spacing is inherited; accents, other weights and obliques are not implemented.", 16, "#626262")
    sheet.save()


def webfont(path):
    font = TTFont(path, recalcTimestamp=False)
    font.flavor = "woff2"
    buffer = io.BytesIO()
    font.save(buffer)
    font.close()
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def build_html():
    html = '''<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Allo — double-storey g study 01</title>
<style>
@font-face {font-family:Current;src:url(data:font/woff2;base64,__CURRENT__) format('woff2');font-weight:400}
@font-face {font-family:Candidate;src:url(data:font/woff2;base64,__CANDIDATE__) format('woff2');font-weight:400}
* {box-sizing:border-box}
body {margin:0;background:white;color:#191919;font:16px/1.6 system-ui,sans-serif}
main {max-width:1440px;margin:auto;padding:36px clamp(20px,5.5vw,80px) 60px}
h1 {font-size:30px;font-weight:500;letter-spacing:-.025em;margin:0 0 12px}
h2 {font-size:14px;font-weight:500;text-transform:uppercase;letter-spacing:.04em;color:#626262}
p {max-width:80ch}
.note,output {color:#626262;font-size:14px}
textarea {width:100%;min-height:105px;padding:14px;border:1px solid #aaa;border-radius:4px;font:inherit;resize:vertical}
.controls {display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin:20px 0}
input {width:240px}
.comparison {display:grid;grid-template-columns:1fr 1fr;gap:50px;margin:30px 0}
.sample {white-space:pre-wrap;overflow-wrap:anywhere;font-size:36px;line-height:1.5;font-synthesis:none;margin:12px 0}
.current {font-family:Current,sans-serif}
.candidate {font-family:Candidate,sans-serif}
.sheet {display:block;width:100%;height:auto;margin-top:25px;border-top:1px solid #ddd}
a {color:inherit}
@media (max-width:700px) {.comparison {grid-template-columns:1fr;gap:10px}}
</style>
<main>
<h1>A double-storey g for Allo</h1>
<p>Study 01: Regular upright, based on the Text / Friendly design. The left sample is the released font; the right has only its plain lowercase <strong>g</strong> replaced. These fonts are embedded here—no installation or network access is needed.</p>
<p class="note">This is a separate design proof, not an installed stylistic set. Accented forms, other weights, variable axes and obliques are unchanged. Existing g spacing is provisional, and the new glyph has not been hinted.</p>
<label for="words">Try your own text</label>
<textarea id="words" spellcheck="false">going, baggage, giggling, analogue
A good beginning grows into something great.</textarea>
<div class="controls"><label for="size">Size</label><input id="size" type="range" min="12" max="72" value="36"><output id="sizeValue" for="size">36 px</output><span id="fontStatus" class="note" role="status">Loading proof fonts…</span></div>
<div class="comparison">
<section><h2>Current / single-storey</h2><p class="sample current" id="current"></p></section>
<section><h2>Candidate / double-storey</h2><p class="sample candidate" id="candidate"></p></section>
</div>
<p class="note">For true reading-size comparison, use the slider at 12–24 px with browser zoom at 100%. The large sheet below is scaled to fit your window; its size labels describe the original 1440 px layout.</p>
<img class="sheet" src="proof.svg" alt="Current and proposed g, enlarged and in words at several sizes">
<p class="note"><a href="proof.svg">Vector sheet</a> · <a href="proof.png">2× PNG</a> · <a href="AlloGStudy-Regular.otf">Proof-only OTF</a> · <a href="../../../OFL.txt">SIL Open Font License</a></p>
</main>
<script>
const words = document.getElementById('words');
const size = document.getElementById('size');
function update() {
  document.querySelectorAll('.sample').forEach(sample => {
    sample.textContent = words.value;
    sample.style.fontSize = size.value + 'px';
  });
  document.getElementById('sizeValue').value = size.value + ' px';
}
words.addEventListener('input', update);
size.addEventListener('input', update);
update();
Promise.all([document.fonts.load('16px Current'), document.fonts.load('16px Candidate')]).then(fonts => {
  if (fonts.some(faces => faces.length === 0)) throw new Error('Font not available');
  document.getElementById('fontStatus').textContent = 'Both proof fonts loaded';
}).catch(() => {
  document.getElementById('fontStatus').textContent = 'Font loading failed—use the vector sheet below instead.';
});
</script>
</html>
'''
    html = html.replace("__CURRENT__", webfont(ORIGINAL)).replace("__CANDIDATE__", webfont(CANDIDATE))
    (HERE / "proof.html").write_text(html)


def main():
    if not shutil.which("hb-shape"):
        raise SystemExit("hb-shape is required (HarfBuzz CLI tools).")
    if not features.check_feature("raqm"):
        raise SystemExit("Pillow must include libraqm for HarfBuzz-shaped PNG text.")
    report = build_font()
    build_sheet()
    build_html()
    print(json.dumps(report, indent=2))
    print(f"Wrote proof font, SVG, PNG, HTML and validation report to {HERE}")


if __name__ == "__main__":
    main()
