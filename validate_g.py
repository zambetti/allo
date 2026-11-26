#!/usr/bin/env python3
"""Read-only verification of the built optional double-storey g.

    .venv/bin/python -B validate_g.py
    .venv/bin/python -B validate_g.py build/custom/fonts \
        --output build/g-integration/validation.json

Requires all 39 custom binaries, the shipped release and approved proof fonts,
and hb-shape on PATH. Nothing is rebuilt; missing ss04 is a failure, not a skip.
WOFF2 is decoded into temporary SFNT files for HarfBuzz (not all hb-shape builds
read WOFF2 directly). The only persistent write is an explicitly requested report.
This is finite outline/layout verification, not universal raster or design approval.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import shutil
import string
import subprocess
import tempfile
import unicodedata
from collections import Counter
from pathlib import Path
from typing import TypedDict
from booleanOperations.booleanGlyph import BooleanGlyph
from fontTools.pens.areaPen import AreaPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.qu2cuPen import Qu2CuPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib import TTFont
from fontTools.varLib.varStore import VarStoreInstancer
from ufoLib2.objects import Glyph

ROOT = Path(__file__).resolve().parent
REPORT_ROOT = ROOT / "build/g-integration"
PROOFS = ROOT / "documentation/proofs/double-storey-g-incoming-spacing/fonts"
WEIGHTS = dict(zip(range(100, 901, 100), (
    "Thin", "ExtraLight", "Light", "Regular", "Medium", "SemiBold", "Bold", "ExtraBold", "Black",
)))
STYLES = tuple(s for w in WEIGHTS.values() for s in (w, ("" if w == "Regular" else w) + "Oblique"))
FAMILY = ("g", "gcircumflex", "gbreve", "gdotaccent", "gcommaaccent")
ALTS = tuple(n + ".ss04" for n in FAMILY)
SUBSTITUTIONS = dict(zip(FAMILY, ALTS))
REVERSE = dict(zip(ALTS, FAMILY))
DESIGN = {100: 100, 200: 200, 300: 300, 400: 400, 500: 490,
          600: 580, 700: 670, 800: 780, 900: 900}
STATIC_B = {100: 40, 200: 43, 300: 45, 400: 48, 500: 51, 600: 54, 700: 57, 800: 60, 900: 64}
STATIC_N = {100: 40, 200: 44, 300: 46, 400: 48, 500: 52, 600: 54, 700: 58, 800: 60, 900: 64}
STATIC_J = {100: 0, 200: 0, 300: 0, 400: 0, 500: 0, 600: 0, 700: 8, 800: 27, 900: 40}
PROOF_FLAGS = ",".join(f"ss{i}={int(i in (12, 15, 17, 19))}" for i in range(11, 21))
NFC = ("g", "ĝ", "ğ", "ġ", "ģ")
MARK_TEXTS = ("g\u0301", "g\u0323", "g\u0301\u0307", "g\u0323\u0301", "ģ\u0301", "g\u0327\u0301", "g\u0323\u0323")
PAIRS = tuple(dict.fromkeys((
    *("g" + c for c in string.ascii_lowercase), *(c + "g" for c in string.ascii_letters),
    "gó", "gø", "gé", "gç", "gœ", "gĵ", "gȷ", "ńğ", "ñĝ", "nğ", "hğ", "mğ", "uğ",
    "ĝo", "ğj", "ġe", "ģc", "g ", "g\u00a0", "g.", "g)",
)))
PLAIN_PROOF = tuple(dict.fromkeys((
    *("g" + c for c in string.ascii_lowercase), *(c + "g" for c in string.ascii_letters),
    "g", "g ", "g\u00a0", "g.", "g)",
)))
CONTEXTS = ("ag", "áĝ", "g->a", "a->g", "g -> a", "a -> g", "g+2", "g-2", "g+g",
            "(g)", "[ĝ]", "ngj ngo nge ngc", "Morning beginning changing going",
            "giggling analogue", "ng hg mg ug", "ĝğġģ")
UNAFFECTED = ("a -> b p->next a <- b", "(HELLO) [1] -$4.50 +2% ¡HOLA! @ACME",
              "tt ff tf ft", "1/2 1 1/2 11/14/2026", "aáâä I l 1 0 469", "AVATAR office", "oec œ ø")
TEXTS = tuple(dict.fromkeys((*NFC, *(unicodedata.normalize("NFD", t) for t in NFC),
                            *MARK_TEXTS, *PAIRS, *PLAIN_PROOF, *CONTEXTS, *UNAFFECTED)))
COMPAT_FLAGS = ("ss01=1", "ss02=1,ss03=1", "cv01=1,cv02=1,cv03=1,cv04=1,cv05=1",
                "tnum=1,zero=1", "frac=1", "sups=1", "subs=1", "numr=1", "dnom=1",
                "case=1", "liga=0,clig=0,calt=0")


class ValidationError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def relative(path):
    path = Path(path).resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(prefix):
    return sorted([
        Path("variable") / f"{prefix}Variable.ttf",
        Path("webfonts") / f"{prefix}Variable.woff2",
        Path("webfonts") / f"{prefix}VariableFriendly.woff2",
        *(Path(folder) / f"{prefix}-{style}.{extension}" for style in STYLES
          for folder, extension in (("otf", "otf"), ("webfonts", "woff2"))),
    ])


def recording(glyph, glyphs):
    pen = DecomposingRecordingPen(glyphs)
    glyph.draw(pen)
    return pen.value


def translated(outline, dx=0, dy=0):
    return [(op, tuple(None if p is None else (p[0] + dx, p[1] + dy) for p in args))
            for op, args in outline]


def outlines_equal(a, b, tolerance: float = 0):
    if len(a) != len(b):
        return False
    for (op, ps), (oq, qs) in zip(a, b):
        if op != oq or len(ps) != len(qs):
            return False
        for p, q in zip(ps, qs):
            if p is None or q is None:
                if p != q:
                    return False
            elif any(not math.isfinite(x) or not math.isfinite(y) or abs(x - y) > tolerance
                     for x, y in zip(p, q)):
                return False
    return True


class ShapedGlyph(TypedDict):
    g: str
    cl: int
    dx: int
    dy: int
    ax: int
    ay: int


def normalized(run: list[ShapedGlyph]) -> list[ShapedGlyph]:
    return [{**item, "g": REVERSE.get(item["g"], item["g"])} for item in run]


def origins(run):
    """Absolute origins, not raw dx: a narrower base changes a mark's dx."""
    x = y = 0
    result = []
    for item in run:
        result.append((x + item["dx"], y + item["dy"]))
        x += item["ax"]
        y += item["ay"]
    return result


def feature_records(font, table, tag=None):
    records = font[table].table.FeatureList.FeatureRecord
    return [r for r in records if tag is None or r.FeatureTag == tag]


def subtables(font, table, tag=None):
    lookups = font[table].table.LookupList.Lookup
    indices = sorted({i for r in feature_records(font, table, tag) for i in r.Feature.LookupListIndex})
    for index in indices:
        lookup = lookups[index]
        for sub in lookup.SubTable:
            kind = lookup.LookupType
            if (table == "GSUB" and kind == 7) or (table == "GPOS" and kind == 9):
                kind, sub = sub.ExtensionLookupType, sub.ExtSubTable
            yield kind, sub


def scripts(font, table, exclude=()):
    tags = [r.FeatureTag for r in feature_records(font, table)]
    result = []
    for record in font[table].table.ScriptList.ScriptRecord:
        systems = [("default", record.Script.DefaultLangSys)]
        systems.extend((r.LangSysTag, r.LangSys) for r in record.Script.LangSysRecord)
        for lang, system in systems:
            if system is not None:
                required = None if system.ReqFeatureIndex == 0xFFFF else tags[system.ReqFeatureIndex]
                result.append((record.ScriptTag, lang, required,
                               tuple(sorted(tags[i] for i in system.FeatureIndex if tags[i] not in exclude))))
    return sorted(result)


def cmaps(font):
    return sorted((t.platformID, t.platEncID, t.language, t.format, sorted(t.cmap.items()))
                  for t in font["cmap"].tables if t.isUnicode())


class HarfBuzz:
    def __init__(self, directory, counts):
        executable = shutil.which("hb-shape")
        if executable is None:
            raise ValidationError("hb-shape is required on PATH")
        self.executable = executable
        self.directory = directory
        self.counts = counts
        self.decoded = {}

    def path(self, path, font):
        if path.suffix != ".woff2":
            return path
        if path not in self.decoded:
            target = self.directory / f"decoded-{len(self.decoded)}.sfnt"
            flavor = font.flavor
            try:
                font.flavor = None
                font.save(target, reorderTables=False)
            finally:
                font.flavor = flavor
            self.decoded[path] = target
        return self.decoded[path]

    def shape(self, path, font, texts, flags="", location=None):
        command = [self.executable, str(self.path(path, font)), "--output-format=json", "--no-glyph-names",
                   "--font-funcs=ot", "--shapers=ot", "--font-size=2048", "--direction=ltr",
                   "--script=latn", "--language=en"]
        if flags:
            command.append("--features=" + flags)
        if location:
            command.append("--variations=" + ",".join(f"{k}={v:g}" for k, v in sorted(location.items())))
        result = subprocess.run(command, input="\n".join(texts) + "\n", capture_output=True,
                                text=True, encoding="utf-8", check=True, timeout=30)
        lines = result.stdout.splitlines()
        require(len(lines) == len(texts), f"HarfBuzz returned {len(lines)} lines for {len(texts)} texts")
        order, output = font.getGlyphOrder(), {}
        for text, line in zip(texts, lines):
            run = json.loads(line)
            for item in run:
                item["g"] = order[int(item["g"])]
            require(all(item["g"] != ".notdef" for item in run), f"missing glyph in {text!r}")
            output[text] = run
        self.counts["hb_batches"] += 1
        self.counts["hb_text_runs"] += len(texts)
        return output


class Attachments:
    """Evaluate the binary mark anchors, including GDEF VariationIndex deltas."""
    def __init__(self, font):
        self.font = font
        self.base = [s for kind, s in subtables(font, "GPOS", "mark") if kind == 4]
        self.mark = [s for kind, s in subtables(font, "GPOS", "mkmk") if kind == 6]

    def anchors(self, base, mark, stacked=False):
        for sub in self.mark if stacked else self.base:
            marks = sub.Mark1Coverage.glyphs if stacked else sub.MarkCoverage.glyphs
            bases = sub.Mark2Coverage.glyphs if stacked else sub.BaseCoverage.glyphs
            if mark not in marks or base not in bases:
                continue
            mark_record = (sub.Mark1Array if stacked else sub.MarkArray).MarkRecord[marks.index(mark)]
            base_record = (sub.Mark2Array.Mark2Record if stacked else sub.BaseArray.BaseRecord)[bases.index(base)]
            anchor = (base_record.Mark2Anchor if stacked else base_record.BaseAnchor)[mark_record.Class]
            if anchor is not None and mark_record.MarkAnchor is not None:
                return anchor, mark_record.MarkAnchor
        return None

    def coverage(self, base):
        return {mark for sub in self.base if base in sub.BaseCoverage.glyphs
                for mark in sub.MarkCoverage.glyphs if self.anchors(base, mark) is not None}

    def evaluator(self, glyphs):
        store = getattr(self.font["GDEF"].table, "VarStore", None)
        instancer = VarStoreInstancer(store, self.font["fvar"].axes, glyphs.location) if store is not None else None

        def value(anchor):
            xy = [anchor.XCoordinate, anchor.YCoordinate]
            for i, field in enumerate(("XDeviceTable", "YDeviceTable")):
                device = getattr(anchor, field, None)
                if device is not None:
                    if device.DeltaFormat != 0x8000 or instancer is None:
                        raise ValidationError("unexpected pixel-device anchor; no ppem/raster test is performed")
                    xy[i] += instancer[(device.StartSize << 16) | device.EndSize]
            return xy
        return value


def check_structure(font, release, counts):
    require(font["head"].unitsPerEm == release["head"].unitsPerEm == 2048, "unexpected UPM")
    require(set(font.getGlyphOrder()) - set(release.getGlyphOrder()) == set(ALTS),
            "expected exactly the five new unencoded glyphs")
    require(set(release.getGlyphOrder()) <= set(font.getGlyphOrder()), "old glyphs were removed")
    require(cmaps(font) == cmaps(release), "Unicode cmap changed")
    require(not set(ALTS).intersection(font.getBestCmap().values()), "ss04 glyph is encoded")
    records = feature_records(font, "GSUB", "ss04")
    require(len(records) == 1, "ss04 missing or duplicated: run the complete custom build first")
    mapping = {}
    for kind, sub in subtables(font, "GSUB", "ss04"):
        require(kind == 1, "ss04 must contain only single substitutions")
        require(not set(mapping).intersection(sub.mapping), "duplicate ss04 substitution")
        mapping.update(sub.mapping)
    require(mapping == SUBSTITUTIONS, f"wrong ss04 substitutions: {mapping}")
    params = records[0].Feature.FeatureParams
    require(params is not None and font["name"].getDebugName(params.UINameID) == "Double-storey g",
            "missing/incorrect ss04 feature UI label")
    for table in ("GSUB", "GPOS"):
        old = Counter(r.FeatureTag for r in feature_records(release, table))
        expected = old + (Counter({"ss04": 1}) if table == "GSUB" else Counter())
        require(Counter(r.FeatureTag for r in feature_records(font, table)) == expected,
                f"{table} feature inventory changed beyond ss04")
        require(scripts(font, table, {"ss04"}) == scripts(release, table), f"{table} language-system compatibility changed")
    classes = font["GDEF"].table.GlyphClassDef.classDefs
    require(all(classes.get(n) == 1 for n in ALTS), "alternates are not GDEF class 1 bases")
    for name, value in release["GDEF"].table.GlyphClassDef.classDefs.items():
        require(classes.get(name) == value, f"GDEF class changed for {name}")
    attachments, old_attachments = Attachments(font), Attachments(release)
    for old, new in SUBSTITUTIONS.items():
        expected = old_attachments.coverage(old)
        require(expected and attachments.coverage(new) >= expected, f"mark coverage missing for {new}")
        counts["alternate_mark_coverage_entries"] += len(expected)
    require(attachments.mark, "mkmk lookup missing")
    counts["ss04_substitutions"] += len(mapping)
    counts["font_structures"] += 1
    return attachments


def check_old_outlines(font, release, names, counts, location=None):
    new_glyphs = font.getGlyphSet(location=location)
    old_glyphs = release.getGlyphSet(location=location)
    for name in names:
        require(outlines_equal(recording(new_glyphs[name], new_glyphs), recording(old_glyphs[name], old_glyphs),
                               1e-6 if location else 0), f"old outline changed: {name} at {location}")
        require(abs(new_glyphs[name].width - old_glyphs[name].width) < 1e-6,
                f"old advance changed: {name} at {location}")
        if location is None:
            require(font["hmtx"][name] == release["hmtx"][name], f"old hmtx changed: {name}")
        counts["old_outline_metric_comparisons"] += 1
    return new_glyphs


def check_counters(glyph, counts):
    """Finite compiled-outline check, including intermediate variable locations."""
    outline = Glyph()
    glyph.draw(Qu2CuPen(outline.getPen(), max_err=0.01, all_cubic=True))
    require(len(outline.contours) == 3, "alternate must have an outer contour and two counters")
    require(all(math.isfinite(v) for c in outline.contours for p in c.points for v in (p.x, p.y)),
            "nonfinite alternate coordinates")

    def area(shape):
        pen = AreaPen(None)
        shape.draw(pen)
        return pen.value

    signed = [area(c) for c in outline.contours]
    require(all(signed[0] * value < 0 for value in signed[1:]), "incorrect alternate counter winding")
    cleaned = BooleanGlyph(outline).removeOverlap()
    # Compatible quadratic conversion can leave sub-unit slivers at collapsed
    # Sharp corners. Do not count those as genuine additional counters/islands.
    significant = [c for c in cleaned.contours if abs(area(c)) > 1]
    require(len(significant) == 3, "alternate has additional or collapsed filled regions/counters")
    outer = Glyph()
    outer.contours = [outline.contours[0]]
    counters = []
    for contour in outline.contours[1:]:
        pen = BoundsPen(None)
        contour.draw(pen)
        x0, y0, x1, y1 = pen.bounds
        require(x1 - x0 > 100 and y1 - y0 > 100, "alternate counter collapsed")
        counter = Glyph()
        counter.contours = [contour]
        counters.append(BooleanGlyph(counter))
        require(abs(area(counters[-1].difference(BooleanGlyph(outer)))) < 1,
                "alternate counter escapes the outer contour")
    require(abs(area(counters[0].intersection(counters[1]))) < 1, "alternate counters overlap")
    counts["compiled_counter_checks"] += 1


def amounts(weight, variable):
    if not variable:
        return STATIC_B[weight], STATIC_N[weight], STATIC_J[weight]
    design = DESIGN[weight]
    b = 40 + (design - 100) * 8 / 300 if design <= 400 else 48 + (design - 400) * 16 / 500
    samples = ((100, 40), (400, 48), (580, 54), (900, 64))
    incoming = float(samples[-1][1])
    for (left, low), (right, high) in zip(samples, samples[1:]):
        if design <= right:
            incoming = low + (high - low) * (design - left) / (right - left)
            break
    return b, incoming, max(0, (design - 580) / 320) * 40


def check_switch(off, on, counts):
    for text in off:
        expected = [SUBSTITUTIONS.get(item["g"], item["g"]) for item in off[text]]
        require([item["g"] for item in on[text]] == expected, f"ss04 changed a non-g glyph in {text!r}")
        if not any(item["g"] in FAMILY for item in off[text]):
            require(on[text] == off[text], f"ss04 changed unaffected positioning in {text!r}")
        counts["ss04_scope_comparisons"] += 1
    for text, name in zip(NFC, ALTS):
        require([i["g"] for i in on[text]] == [name], f"NFC did not select {name}")
        decomposed = unicodedata.normalize("NFD", text)
        require(on[decomposed] == on[text], f"NFC/NFD mismatch for {text!r}")
        counts["nfc_nfd_comparisons"] += 1


def check_spacing(off, on, no_kern_off, no_kern_on, weight, variable, counts):
    b, incoming, heavy_j = amounts(weight, variable)
    tolerance = 1 if variable else 0
    rounds = {"o", "e", "c", "oacute", "oslash", "eacute", "ccedilla"}
    ns, js = {"n", "nacute", "ntilde"}, {"j", "jcircumflex", "jdotless"}
    for text in PAIRS:
        a, z, na, nz = (r[text] for r in (off, on, no_kern_off, no_kern_on))
        require(len(a) == len(z) == len(na) == len(nz) == 2, f"pair is not two glyphs: {text!r}")
        for old, new in zip(na, nz):
            expected = -b if old["g"] in FAMILY else 0
            require(abs(new["ax"] - old["ax"] - expected) <= tolerance,
                    f"wrong B width/kern-off advance: {text!r}: {new['ax'] - old['ax']} vs {expected:g}")
        first, second = a[0]["g"], a[1]["g"]
        expected = (-incoming if first in ns and second in FAMILY else
                    -b if first in FAMILY and second in rounds else
                    heavy_j if first in FAMILY and second in js else 0)
        actual = (z[0]["ax"] - nz[0]["ax"]) - (a[0]["ax"] - na[0]["ax"])
        require(abs(actual - expected) <= tolerance,
                f"pair correction outside scope/value: {text!r}: {actual} vs {expected:g}")
        counts["pair_scope_width_comparisons"] += 1


def check_marks(on, font, glyphs, attachments, counts, variable):
    evaluate = attachments.evaluator(glyphs)
    tolerance = 1 if variable else 0
    for text in MARK_TEXTS:
        run = on[text]
        require(len(run) >= 2 and run[0]["g"] in ALTS, f"mark case did not select alternate: {text!r}")
        positions = origins(run)
        for index, item in enumerate(run[1:], 1):
            require(font["GDEF"].table.GlyphClassDef.classDefs.get(item["g"]) == 3 and item["ax"] == 0,
                    f"not a zero-advance GDEF mark: {text!r}")
            selected = None
            for previous in range(index - 1, 0, -1):
                anchors = attachments.anchors(run[previous]["g"], item["g"], stacked=True)
                if anchors is not None:
                    selected = previous, anchors
                    break
            if selected is None:
                selected = 0, attachments.anchors(run[0]["g"], item["g"])
            base_index, anchors = selected
            require(anchors is not None, f"missing attachment for {text!r}/{item['g']}")
            base, mark = map(evaluate, anchors)
            expected = tuple(p + b - m for p, b, m in zip(positions[base_index], base, mark))
            require(all(abs(p - q) <= tolerance for p, q in zip(positions[index], expected)),
                    f"incorrect absolute mark attachment: {text!r}: {positions[index]} vs {expected}")
            counts["absolute_mark_attachments"] += 1
        if text == "ģ\u0301":
            pen = BoundsPen(glyphs)
            glyphs["gcommaaccent.ss04"].draw(pen)
            base_anchor, _ = attachments.anchors("gcommaaccent.ss04", run[1]["g"])
            require(evaluate(base_anchor)[1] >= pen.bounds[3] - tolerance,
                    "rotated-comma top anchor does not stack above the comma")


def proof_adjustment(run, index, weight, variable):
    """Expected advance change and number of independently rounded terms.

    The historical comparison covers plain-g runs only. Accent and mark
    integration is checked separately because the old proofs did not implement it.
    """
    b, incoming, heavy_j = amounts(weight, variable)
    name = run[index]["g"]
    following = run[index + 1]["g"] if index + 1 < len(run) else None
    change, terms = (-b, 1) if name == "g" else (0, 0)
    if name == "g" and following in ("o", "e", "c"):
        change, terms = change - b, terms + 1
    elif name == "g" and following == "j":
        change, terms = change + heavy_j, terms + 1
    elif name == "n" and following == "g":
        change, terms = change - incoming, terms + 1
    return change, terms


def compare_runs(actual, expected, context, counts, *, baselines=None, weight=None):
    """Exact static proof comparison, or baseline-relative variable comparison.

    Static sources were edited separately, so their pre-existing advances must
    not be imposed on the variable font. Compare each alternate's change against
    its own release baseline, accounting for the explicit static/variable spacing
    models; allow one unit per independently rounded width or pair adjustment.
    """
    variable = baselines is not None
    for text in expected:
        a, b = normalized(actual[text]), normalized(expected[text])
        require(len(a) == len(b), f"{context}: glyph count mismatch for {text!r}")
        if variable:
            base_a, base_b = (normalized(runs[text]) for runs in baselines)
            require(len(a) == len(base_a) == len(base_b), f"{context}: baseline count mismatch for {text!r}")
        for index, (x, y) in enumerate(zip(a, b)):
            require({k: v for k, v in x.items() if k != "ax"} == {k: v for k, v in y.items() if k != "ax"},
                    f"{context}: glyph/cluster/offset mismatch for {text!r}: {x} vs {y}")
            actual_advance, expected_advance, tolerance = x["ax"], y["ax"], 0
            if variable:
                require(x["g"] == base_a[index]["g"] == base_b[index]["g"],
                        f"{context}: baseline glyph mismatch for {text!r}")
                variable_change, tolerance = proof_adjustment(a, index, weight, True)
                static_change, _ = proof_adjustment(b, index, weight, False)
                actual_advance -= base_a[index]["ax"]
                expected_advance -= base_b[index]["ax"]
                expected_advance += variable_change - static_change
            require(abs(actual_advance - expected_advance) <= tolerance,
                    f"{context}: advance {'delta ' if variable else ''}mismatch for {text!r}: "
                    f"{actual_advance:g} vs {expected_advance:g} (tolerance {tolerance})")
        counts["variable_proof_delta_comparisons" if variable else "static_proof_runs"] += 1


def sample_grid(friendly=False):
    rounds = (50,) if friendly else (0, 25, 50, 75, 100)
    grid: set[tuple[float, int, int]] = set(itertools.product((9, 11.5, 14, 23, 32), (100, 400, 500, 600, 700, 900), rounds))
    grid.update((14, w, 50) for w in WEIGHTS)
    return [{"opsz": s, "wght": w, **({} if friendly else {"ROND": r})} for s, w, r in sorted(grid)]


class Validator:
    def __init__(self, root, hb, report):
        self.root, self.hb, self.report = root, hb, report
        self.counts = report["counts"]
        self.proof_runs = {}
        self.proof_baselines = {}

    def proof(self, weight):
        if weight not in self.proof_runs:
            path = PROOFS / f"AlloGIncomingStudy-{WEIGHTS[weight]}.otf"
            baseline = ROOT / f"fonts/otf/Allo-{WEIGHTS[weight]}.otf"
            with TTFont(path) as font, TTFont(baseline) as release:
                self.proof_runs[weight] = self.hb.shape(path, font, PLAIN_PROOF, PROOF_FLAGS)
                self.proof_baselines[weight] = self.hb.shape(baseline, release, PLAIN_PROOF)
        return self.proof_runs[weight]

    def shaping(self, path, font, release_path, release, glyphs, attachments, location=None):
        variable = location is not None
        weight = location["wght"] if variable else font["OS/2"].usWeightClass
        states = {}
        for key, flags in (("off", ""), ("on", "ss04=1"), ("off_a", "ss01=1"),
                           ("on_a", "ss01=1,ss04=1"), ("off_k", "kern=0"), ("on_k", "kern=0,ss04=1")):
            texts = PAIRS if key.endswith("_k") else TEXTS
            states[key] = self.hb.shape(path, font, texts, flags, location)
            if key in ("off", "off_a", "off_k"):
                baseline = self.hb.shape(release_path, release, texts, flags, location)
                for text in texts:
                    require(states[key][text] == baseline[text], f"default/release shaping changed: {text!r} ({flags})")
                    self.counts["release_shaping_comparisons"] += 1
        check_switch(states["off"], states["on"], self.counts)
        check_switch(states["off_a"], states["on_a"], self.counts)
        require(states["on_a"]["ag"][0]["g"] == "a.1", "ss01 did not operate alongside ss04")
        check_spacing(states["off"], states["on"], states["off_k"], states["on_k"], weight, variable, self.counts)
        check_marks(states["on"], font, glyphs, attachments, self.counts, variable)
        text_friendly = not variable or location["opsz"] == 14 and location.get("ROND", 50) == 50
        if text_friendly and (variable or "Oblique" not in path.stem):
            proof = self.proof(weight)
            compare_runs(states["on"], proof, "study 06", self.counts,
                         baselines=(states["off"], self.proof_baselines[weight]) if variable else None,
                         weight=weight)
        self.counts["shaping_locations"] += 1

    def compatibility(self, path, font, release_path, release):
        for flags in COMPAT_FLAGS:
            # Other features are independently exercised on text with no g;
            # ss01 and g-containing contextual behavior get the larger grid.
            baseline = self.hb.shape(release_path, release, UNAFFECTED, flags)
            for suffix in ("", ",ss04=1"):
                actual = self.hb.shape(path, font, UNAFFECTED, flags + suffix)
                require(actual == baseline, f"feature compatibility regression: {flags + suffix}")
                self.counts["feature_compatibility_runs"] += len(UNAFFECTED)

    def variable(self, path, font, release_path, release, attachments):
        friendly = "Friendly" in path.stem
        expected_axes = {"opsz", "wght"} if friendly else {"opsz", "wght", "ROND"}
        axes = {a.axisTag: (a.minValue, a.defaultValue, a.maxValue) for a in font["fvar"].axes}
        require(set(axes) == expected_axes, "wrong variable axes")
        require(axes == {a.axisTag: (a.minValue, a.defaultValue, a.maxValue) for a in release["fvar"].axes},
                "variable axis ranges changed")
        signatures = {}
        for location in sample_grid(friendly):
            try:
                glyphs = check_old_outlines(font, release, FAMILY, self.counts, location)
                outlines = {name: recording(glyphs[name], glyphs) for name in ALTS}
                check_counters(glyphs["g.ss04"], self.counts)
                for old, new in SUBSTITUTIONS.items():
                    require(not outlines_equal(outlines[new], recording(glyphs[old], glyphs)),
                            f"alternate has the old outline: {new}")
                    require(abs(glyphs[old].width - glyphs[new].width - amounts(location["wght"], True)[0]) <= 1,
                            f"wrong interpolated B advance: {new}")
                key = location["opsz"], location["wght"], location.get("ROND", 50)
                signatures[key] = (outlines, {n: glyphs[n].width for n in ALTS})
                self.shaping(path, font, release_path, release, glyphs, attachments, location)
                self.counts["variable_grid_locations"] += 1
            except ValidationError as exc:
                raise ValidationError(f"at {location}: {exc}") from exc
        for axis, index in (("opsz", 0), ("wght", 1), ("ROND", 2)):
            if axis not in axes:
                continue
            low, high = [14, 400, 50], [14, 400, 50]
            low[index], high[index] = axes[axis][0], axes[axis][2]
            require(not outlines_equal(signatures[tuple(low)][0]["g.ss04"], signatures[tuple(high)][0]["g.ss04"]),
                    f"{axis} has no effect on the alternate g geometry")
            self.counts["active_geometry_axes"] += 1
        for (size, weight, rond), (small, widths) in signatures.items():
            if size != 9:
                continue
            text, text_widths = signatures[14, weight, rond]
            for name in ALTS:
                require(outlines_equal(small[name], translated(text[name], 17), 1e-5),
                        f"Small is not the exact +17 outline move: {name}/{weight}/{rond}")
                require(abs(widths[name] - text_widths[name] - 34) < 1e-5,
                        f"Small is not +34 advance: {name}/{weight}/{rond}")
                self.counts["binary_small_relationships"] += 1

    def font(self, relative_path):
        path = self.root / relative_path
        release_path = ROOT / "fonts" / str(relative_path).replace("AlloCustom", "Allo")
        with TTFont(path, recalcTimestamp=False) as font, TTFont(release_path, recalcTimestamp=False) as release:
            require(feature_records(font, "GSUB", "ss04"), "ss04 missing: run alternate_g.py --write and the full custom build first")
            attachments = check_structure(font, release, self.counts)
            names = release.getGlyphOrder() if path.suffix == ".otf" else FAMILY
            glyphs = check_old_outlines(font, release, names, self.counts)
            if path.suffix == ".otf":
                self.counts["complete_static_outline_inventories"] += 1
            if "fvar" in font:
                self.variable(path, font, release_path, release, attachments)
            else:
                check_counters(glyphs["g.ss04"], self.counts)
                for old, new in SUBSTITUTIONS.items():
                    require(font["hmtx"][new][0] == release["hmtx"][old][0] - STATIC_B[font["OS/2"].usWeightClass],
                            f"wrong static B advance: {new}")
                if "Oblique" not in path.stem:
                    proof_path = PROOFS / f"AlloGIncomingStudy-{WEIGHTS[font['OS/2'].usWeightClass]}.otf"
                    with TTFont(proof_path) as proof:
                        proof_glyphs = proof.getGlyphSet()
                        require(outlines_equal(recording(glyphs["g.ss04"], glyphs), recording(proof_glyphs["g"], proof_glyphs)),
                                "Text/Friendly alternate outline differs from the approved study 06 drawing")
                        self.counts["exact_static_proof_outlines"] += 1
                self.shaping(path, font, release_path, release, glyphs, attachments)
            self.compatibility(path, font, release_path, release)
            self.counts["validated_fonts"] += 1

    def web_payloads(self):
        for item in inventory("AlloCustom"):
            if item.suffix != ".woff2" or "Friendly" in item.stem:
                continue
            desktop = (Path("variable") / (item.stem + ".ttf") if "Variable" in item.stem
                       else Path("otf") / (item.stem + ".otf"))
            with TTFont(self.root / item, recalcTimestamp=False) as web, TTFont(self.root / desktop, recalcTimestamp=False) as original:
                for table in ("CFF ", "glyf", "gvar", "hmtx", "GSUB", "GPOS", "GDEF", "fvar", "HVAR", "avar"):
                    require((table in web) == (table in original), f"web table mismatch: {item}/{table}")
                    if table in web:
                        require(web.getTableData(table) == original.getTableData(table), f"web payload differs: {item}/{table}")
                        self.counts["web_payload_table_comparisons"] += 1


def validate(root):
    counts = Counter()
    report = {
        "schema_version": 1, "status": "failed", "fonts_root": relative(root), "counts": counts,
        "failures": [], "font_sha256": {}, "reference_sha256": {},
        "scope": "39 actual binary payloads; all old outlines/metrics in 18 static OTFs; finite HarfBuzz, counter-containment and three-axis geometry samples. Not universal rasterization or aesthetic approval.",
        "proof": {"features": PROOF_FLAGS, "outline_scope": "nine upright Text/Friendly statics, OTF and WOFF2",
                  "position_scope": "plain-g pairs; proof accents retain old drawings/anchors and are not an integration oracle",
                  "static_advance_tolerance": 0,
                  "variable_position_scope": "advance changes against each font's release baseline, with the documented static/variable spacing-model difference removed",
                  "variable_delta_rounding_tolerance_per_term": 1, "variable_mark_rounding_tolerance": 1},
        "sample_grids": {"full": sample_grid(), "friendly": sample_grid(True)},
    }
    try:
        expected = inventory("AlloCustom")
        actual = sorted(p.relative_to(root) for p in root.rglob("*") if p.suffix.lower() in (".otf", ".ttf", ".woff2"))
        require(actual == expected, f"expected all 39 custom fonts; missing={list(map(str, sorted(set(expected) - set(actual))))}; unexpected={list(map(str, sorted(set(actual) - set(expected))))}")
        references = [ROOT / "fonts" / str(p).replace("AlloCustom", "Allo") for p in expected]
        references += [PROOFS / f"AlloGIncomingStudy-{style}.otf" for style in WEIGHTS.values()]
        require(all(p.is_file() for p in references), "shipped release or approved study 06 fonts missing")
        report["font_sha256"] = {str(p): digest(root / p) for p in expected}
        report["reference_sha256"] = {relative(p): digest(p) for p in sorted(references)}
        with tempfile.TemporaryDirectory(prefix="allo-validate-g-") as temporary:
            hb = HarfBuzz(Path(temporary), counts)
            report["harfbuzz"] = subprocess.run([hb.executable, "--version"], check=True, text=True,
                                                capture_output=True, timeout=10).stdout.splitlines()[0]
            validator = Validator(root, hb, report)
            for path in expected:
                try:
                    validator.font(path)
                except (ValidationError, OSError, ValueError, KeyError, AttributeError, subprocess.SubprocessError) as exc:
                    report["failures"].append({"font": str(path), "error": str(exc)})
            if not report["failures"]:
                validator.web_payloads()
        require(report["font_sha256"] == {str(p): digest(root / p) for p in expected}, "binary inputs changed during validation (build still running?)")
        require(report["reference_sha256"] == {relative(p): digest(p) for p in sorted(references)}, "release/proof inputs changed during validation")
        if not report["failures"]:
            require(counts["validated_fonts"] == 39 and counts["complete_static_outline_inventories"] == 18,
                    "incomplete verification inventory")
            report["status"] = "passed"
    except (ValidationError, OSError, ValueError, KeyError, AttributeError, subprocess.SubprocessError) as exc:
        report["failures"].append({"stage": "preflight/finalization", "error": str(exc)})
    report["counts"] = dict(sorted(counts.items()))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("fonts", nargs="?", type=Path, default=ROOT / "build/custom/fonts")
    parser.add_argument("--output", type=Path, help="optional JSON report path, restricted to build/g-integration/")
    args = parser.parse_args(argv)
    output = args.output.resolve() if args.output is not None else None
    if output is not None:
        if not output.is_relative_to(REPORT_ROOT.resolve()) or output.suffix != ".json":
            parser.error("--output must be a .json path under build/g-integration/")
    report = validate(args.fonts.resolve())
    serialized = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
        print(f"{report['status']}: {report['counts'].get('validated_fonts', 0)}/39 fonts; report: {relative(output)}")
        for failure in report["failures"]:
            print(f"  {failure.get('font', failure.get('stage'))}: {failure['error']}")
    else:
        print(serialized, end="")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
