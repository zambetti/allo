"""Read-only spacing diagnostics for the unchanged study02 outlines.

``analyze`` accepts all nine weights or a subset for testing. It does not create
fonts, reports, or temporary files. HarfBuzz shapes the source fonts with default
features (including kerning); the simulated reduction only translates glyph two.

Return schema (weight keys are decimal strings, pairs retain the order below)::

    {
        "schema_version": 1,
        "measurement": {...}, "shaping": {...}, "modes": {...},
        "weights": {
            "400": {
                "font": str, "sha256": str, "source_upm": int,
                "amounts": {"moderate": int, "tighter": int},
                "pairs": {
                    "go": {
                        "glyphs": [str, str],
                        "baseline_origins": [[x, y], [x, y]],
                        "common_y_samples": int,
                        "minimum_gap_y": float | None,
                        "baseline": measurement,
                        "round-followers": {
                            "moderate": measurement, "tighter": measurement},
                        "all-followers": {
                            "moderate": measurement, "tighter": measurement}
                    }, ...
                }
            }, ...
        },
        "warnings": [{"weight": int, "pair": str, "mode": str,
                      "level": str, "reasons": [str, ...]}, ...]
    }

Each measurement is {"second_dx": int, "sampled_gap": float | None,
"overlap_area": float}. Baseline warnings use mode=level="baseline". Reasons
are "ink_overlap" and/or "sampled_gap_below_design_review_threshold".
"minimum_gap_y" is shared by all translations, which do not change y positions.
A null gap/y means no common sampled ink; zero overlap is still tested separately.
"sampled_gap" is not an exact Euclidean distance or a legibility verdict.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess

from booleanOperations.booleanGlyph import BooleanGlyph
from fontTools.misc.bezierTools import solveCubic, solveQuadratic
from fontTools.pens.areaPen import AreaPen
from fontTools.pens.basePen import BasePen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from ufoLib2.objects import Glyph

__all__ = ["analyze"]

_UPM = 2048
_SAMPLE_STEP = 4
_OVERLAP_TOLERANCE = 1.0
_REVIEW_THRESHOLD = 32.0
_EPSILON = 1e-7
_PAIRS = (
    "go", "ge", "gc", "ga", "gn", "gr", "gg", "gy", "gj",
    "g.", "g,", "g:", "g;", "g)", "g]", "g!", "og", "ag", "ng",
)
_ROUND_PAIRS = ("go", "ge", "gc")
_MODES = ("round-followers", "all-followers")


def _polynomial(values):
    """Return cubic power-basis coefficients, also for lines/quadratics."""
    if len(values) == 2:
        p0, p1 = values
        return (0.0, 0.0, p1 - p0, p0)
    if len(values) == 3:
        p0, p1, p2 = values
        return (0.0, p0 - 2 * p1 + p2, 2 * (p1 - p0), p0)
    p0, p1, p2, p3 = values
    return (-p0 + 3 * p1 - 3 * p2 + p3,
            3 * p0 - 6 * p1 + 3 * p2, 3 * (p1 - p0), p0)


def _evaluate(coefficients, t):
    a, b, c, d = coefficients
    return ((a * t + b) * t + c) * t + d


def _extreme_parameters(coefficients):
    a, b, c, _ = coefficients
    return [t for t in solveQuadratic(3 * a, 2 * b, c) if 0 < t < 1]


class _Segment:
    def __init__(self, points):
        self.x = _polynomial([p[0] for p in points])
        self.y = _polynomial([p[1] for p in points])
        self.y_bounds = (min(p[1] for p in points), max(p[1] for p in points))
        self.sample_ys = tuple(
            _evaluate(self.y, t)
            for t in (0.0, 0.5, 1.0, *_extreme_parameters(self.y))
        )
        # Horizontal curves can turn back in x: their endpoints alone need not
        # delimit their boundary ink. Include their internal x extrema as well.
        self.horizontal_xs = None
        if self.y_bounds[0] == self.y_bounds[1]:
            self.horizontal_xs = tuple(
                _evaluate(self.x, t)
                for t in (0.0, 1.0, *_extreme_parameters(self.x))
            )

    def crossings(self, y):
        if y < self.y_bounds[0] - _EPSILON or y > self.y_bounds[1] + _EPSILON:
            return ()
        if self.horizontal_xs is not None:
            return self.horizontal_xs if abs(y - self.y[3]) <= _EPSILON else ()
        a, b, c, d = self.y
        roots = solveCubic(a, b, c, d - y)
        return tuple(
            _evaluate(self.x, min(1.0, max(0.0, t)))
            for t in roots if -_EPSILON <= t <= 1.0 + _EPSILON
        )


class _SegmentPen(BasePen):
    """BasePen decomposes multi-control-point curves into simple segments."""

    def __init__(self):
        super().__init__(None)
        self.segments = []
        self.start = None

    def _moveTo(self, point):
        self.start = point

    def _lineTo(self, point):
        self.segments.append(_Segment((self._getCurrentPoint(), point)))

    def _qCurveToOne(self, control, point):
        self.segments.append(_Segment((self._getCurrentPoint(), control, point)))

    def _curveToOne(self, control1, control2, point):
        self.segments.append(
            _Segment((self._getCurrentPoint(), control1, control2, point))
        )

    def _closePath(self):
        if self._getCurrentPoint() != self.start:
            self._lineTo(self.start)

    def _endPath(self):
        raise ValueError("Ink diagnostics require closed outline contours")


class _Outline:
    def __init__(self, glyph_set, name, scale):
        recording = DecomposingRecordingPen(
            glyph_set, skipMissingComponents=False, reverseFlipped=True
        )
        glyph_set[name].draw(recording)
        self.glyph = Glyph(name=name)
        recording.replay(TransformPen(
            self.glyph.getPen(), (scale, 0, 0, scale, 0, 0)
        ))
        segments = _SegmentPen()
        self.glyph.draw(segments)
        self.segments = segments.segments
        self.sample_ys = sorted({y for s in self.segments for y in s.sample_ys})
        bounds = BoundsPen(None)
        self.glyph.draw(bounds)
        self.bounds = bounds.bounds
        self._crossing_cache = {}

    def ink_extents(self, y):
        if y not in self._crossing_cache:
            xs = [x for segment in self.segments for x in segment.crossings(y)]
            # Counters lie inside outer contours. Only the outermost boundary
            # crossings matter for this envelope measurement, not counter widths.
            self._crossing_cache[y] = (min(xs), max(xs)) if xs else None
        return self._crossing_cache[y]

    def positioned(self, x, y):
        glyph = Glyph(name=self.glyph.name)
        self.glyph.draw(TransformPen(glyph.getPen(), (1, 0, 0, 1, x, y)))
        return BooleanGlyph(glyph)


def _sampled_gap(first, second, origins):
    if first.bounds is None or second.bounds is None:
        return None, None, 0
    (x1, y1), (x2, y2) = origins
    low = max(first.bounds[1] + y1, second.bounds[1] + y2)
    high = min(first.bounds[3] + y1, second.bounds[3] + y2)
    if low > high:
        return None, None, 0

    events = {low, high}
    events.update(y + y1 for y in first.sample_ys if low <= y + y1 <= high)
    events.update(y + y2 for y in second.sample_ys if low <= y + y2 <= high)
    ordered_events = sorted(events)
    # Event-interval midpoints sample narrow features even between grid rows.
    ys = events | {
        (a + b) / 2 for a, b in zip(ordered_events, ordered_events[1:])
    }
    ys.update(
        i * _SAMPLE_STEP
        for i in range(math.ceil(low / _SAMPLE_STEP),
                       math.floor(high / _SAMPLE_STEP) + 1)
    )
    minimum = minimum_y = None
    common_samples = 0
    for y in sorted(ys):
        ink1 = first.ink_extents(y - y1)
        ink2 = second.ink_extents(y - y2)
        if ink1 is None or ink2 is None:
            continue
        common_samples += 1
        gap = (ink2[0] + x2) - (ink1[1] + x1)
        if minimum is None or gap < minimum:
            minimum, minimum_y = gap, y
    return minimum, minimum_y, common_samples


def _shape_pairs(executable, path, glyph_order):
    command = [
        executable, f"--font-file={path}", f"--font-size={_UPM}",
        "--font-funcs=ot", "--shapers=ot", "--direction=ltr", "--script=latn",
        "--language=en", "--output-format=json", "--no-glyph-names",
    ]
    try:
        result = subprocess.run(
            command, input="\n".join(_PAIRS) + "\n", text=True,
            capture_output=True, check=True, timeout=30,
        )
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"hb-shape failed for {path}: {error.stderr.strip()}") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"hb-shape exceeded 30 seconds for {path}") from error

    lines = result.stdout.splitlines()
    if len(lines) != len(_PAIRS):
        raise ValueError(f"Expected {len(_PAIRS)} shaped pairs from hb-shape for {path}")
    shaped = {}
    for pair, line in zip(_PAIRS, lines):
        records = json.loads(line)
        if len(records) != 2 or [g["cl"] for g in records] != [0, 1]:
            raise ValueError(f"{path}: {pair!r} did not shape to two ordered glyphs")
        names, origins = [], []
        pen_x = pen_y = 0
        for record in records:
            gid = record["g"]
            if not isinstance(gid, int) or not 0 < gid < len(glyph_order):
                raise ValueError(f"{path}: missing or invalid glyph in {pair!r}: {gid!r}")
            if not all(math.isfinite(record[k]) for k in ("ax", "ay", "dx", "dy")):
                raise ValueError(f"{path}: non-finite glyph position in {pair!r}")
            names.append(glyph_order[gid])
            origins.append([pen_x + record["dx"], pen_y + record["dy"]])
            pen_x += record["ax"]
            pen_y += record["ay"]
        shaped[pair] = (names, origins)
    return shaped


def _warn(warnings, weight, pair, mode, level, measurement):
    reasons = []
    if measurement["overlap_area"] > _OVERLAP_TOLERANCE:
        reasons.append("ink_overlap")
    gap = measurement["sampled_gap"]
    if gap is not None and gap < _REVIEW_THRESHOLD:
        reasons.append("sampled_gap_below_design_review_threshold")
    if reasons:
        warnings.append({
            "weight": weight, "pair": pair, "mode": mode,
            "level": level, "reasons": reasons,
        })


def _analyze_weight(path, amount, executable):
    with TTFont(path) as font:
        source_upm = font["head"].unitsPerEm
        shaped = _shape_pairs(executable, path, font.getGlyphOrder())
        glyph_set = font.getGlyphSet()
        outlines = {
            name: _Outline(glyph_set, name, _UPM / source_upm)
            for name in sorted({name for names, _ in shaped.values() for name in names})
        }
        positioned_cache = {}
        area_cache = {}

        def positioned(name, origin):
            key = (name, *origin)
            if key not in positioned_cache:
                positioned_cache[key] = outlines[name].positioned(*origin)
            return positioned_cache[key]

        def overlap_area(names, origins, dx):
            origin1, (x2, y2) = origins
            origin2 = (x2 + dx, y2)
            key = (names[0], *origin1, names[1], *origin2)
            if key not in area_cache:
                intersection = positioned(names[0], origin1).intersection(
                    positioned(names[1], origin2)
                )
                area = AreaPen(None)
                intersection.draw(area)
                # Sum signed contours BEFORE taking absolute value: counters
                # subtract ink rather than contributing spurious overlap area.
                area_cache[key] = abs(float(area.value))
            return area_cache[key]

        pairs = {}
        for pair, (names, origins) in shaped.items():
            gap, gap_y, sample_count = _sampled_gap(
                outlines[names[0]], outlines[names[1]], origins
            )

            def measurement(dx):
                return {
                    "second_dx": dx,
                    "sampled_gap": None if gap is None else gap + dx,
                    "overlap_area": overlap_area(names, origins, dx),
                }

            entry = {
                "glyphs": names,
                "baseline_origins": origins,
                "common_y_samples": sample_count,
                "minimum_gap_y": gap_y,
                "baseline": measurement(0),
            }
            for mode in _MODES:
                applies = pair in _ROUND_PAIRS if mode == "round-followers" else pair[0] == "g"
                entry[mode] = {
                    "moderate": measurement(-amount if applies else 0),
                    "tighter": measurement(-2 * amount if applies else 0),
                }
            pairs[pair] = entry

    return {
        "font": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_upm": source_upm,
        "amounts": {"moderate": amount, "tighter": 2 * amount},
        "pairs": pairs,
    }


def analyze(font_paths: dict[int, Path], amounts: dict[int, int]) -> dict:
    """Return deterministic, JSON-serializable diagnostics without any writes.

    Input mappings must have the same nonempty set of integer weight keys and
    nonnegative integer reductions. Fonts are shaped once per weight. Decomposed
    outlines, local-y crossings, positioned BooleanGlyphs, and intersection areas
    are cached within that weight only; there is no persistent/global cache.
    """
    if not font_paths or font_paths.keys() != amounts.keys():
        raise ValueError("font_paths and amounts must have the same nonempty weight keys")
    if any(type(weight) is not int for weight in font_paths):
        raise ValueError("Weight keys must be integers")
    if any(type(amount) is not int or amount < 0 for amount in amounts.values()):
        raise ValueError("Reductions must be nonnegative integers")
    executable = shutil.which("hb-shape")
    if executable is None:
        raise RuntimeError("hb-shape must be available on PATH")

    report = {
        "schema_version": 1,
        "measurement": {
            "name": "sampled horizontal clearance",
            "upm": _UPM,
            "gap_units": "font units",
            "area_units": "square font units",
            "sample_step": _SAMPLE_STEP,
            "extra_samples": (
                "Common vertical-range endpoints; segment endpoints, t=0.5 and "
                "y extrema; midpoints between these event levels."
            ),
            "gap_definition": (
                "Minimum of second-ink leftmost x minus first-ink rightmost x "
                "at common sampled y, including boundary tangencies. Null if "
                "there is no common sampled ink."
            ),
            "overlap_method": (
                "Independent BooleanGlyph intersection of decomposed, positioned "
                "outlines (nonzero fill); absolute signed AreaPen contour sum. "
                "Boolean curve reconstruction is numerical."
            ),
            "overlap_tolerance": _OVERLAP_TOLERANCE,
            "design_review_gap_threshold": _REVIEW_THRESHOLD,
            "warning_policy": (
                "Warn for overlap_area > 1 square font unit and/or sampled_gap "
                "< 32 font units. Area <= 1 is numerical tolerance; 32 is a "
                "design-review threshold, not a universal rule."
            ),
            "caveat": (
                "Sampled horizontal clearance, not exact Euclidean distance "
                "or a legibility verdict. A negative envelope gap alone does "
                "not establish actual ink overlap."
            ),
        },
        "shaping": {
            "engine": "hb-shape", "font_size": _UPM,
            "font_funcs": "ot", "shaper": "ot", "direction": "ltr",
            "script": "latn", "language": "en", "features": "source defaults",
            "positioning": "Cumulative x/y advances plus each glyph's x/y offsets",
        },
        "modes": {
            "round-followers": "Translate only glyph two in go, ge, gc",
            "all-followers": "Translate glyph two in every tested pair starting with g",
            "translation": "second_dx = -reduction; tighter = 2 * moderate",
            "controls": "og, ag, ng never shift: their g is terminal",
        },
        "weights": {},
        "warnings": [],
    }
    for weight in sorted(font_paths):
        data = _analyze_weight(Path(font_paths[weight]), amounts[weight], executable)
        report["weights"][str(weight)] = data
        for pair, entry in data["pairs"].items():
            _warn(report["warnings"], weight, pair, "baseline", "baseline", entry["baseline"])
            for mode in _MODES:
                for level in ("moderate", "tighter"):
                    _warn(report["warnings"], weight, pair, mode, level, entry[mode][level])
    return report
