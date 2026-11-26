#!/usr/bin/env python3
"""Author the ss04 UFO family from the approved Text/Friendly control drawings.

Run with --write to regenerate only the five alternates and their layout metadata.
Normal builds consume the resulting editable UFOs, not this generator or proofs.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import math
from pathlib import Path

from fontTools.designspaceLib import DesignSpaceDocument
from fontTools.misc.roundTools import otRound
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ufoLib import UFOWriter
from fontTools.ufoLib.glifLib import readGlyphFromString
import ufoLib2
from ufoLib2.objects import Glyph

from g_features import G_FAMILY, integrate_features, spacing_amount

ROOT = Path(__file__).resolve().parent
CONTROLS = ROOT / 'sources/alternates/double-storey-g'
STYLES = ('Thin', 'ExtraLight', 'Light', 'Regular', 'Medium', 'SemiBold', 'Bold', 'ExtraBold', 'Black')
ACCENTS = dict(zip(G_FAMILY[1:], ('circumflexcomb', 'brevecomb', 'dotaccentcomb', 'commaaccentrotate.cn')))


def bounds(glyph, glyphs=None):
    pen = BoundsPen(glyphs)
    glyph.draw(pen)
    return pen.bounds


def anchors(glyph):
    return {anchor.name: anchor for anchor in glyph.anchors}


def control_drawings():
    result = {}
    for weight, style in ((100, 'Thin'), (400, 'Regular'), (900, 'Black')):
        glyph = Glyph('g.ss04')
        readGlyphFromString((CONTROLS / (style + '.glif')).read_text(), glyph, glyph.getPointPen())
        if glyph.unicodes or glyph.components or [len(c.points) for c in glyph.contours] != [71, 12, 13]:
            raise ValueError(f'Unexpected control drawing: {style}')
        result[weight] = glyph
    return result


def interpolate_drawing(design_weight, controls):
    low, high = (100, 400) if design_weight <= 400 else (400, 900)
    t = (design_weight - low) / (high - low)
    result = deepcopy(controls[low])
    for contour, left, right in zip(result.contours, controls[low].contours, controls[high].contours):
        for point, a, b in zip(contour.points, left.points, right.points):
            point.x = a.x + t * (b.x - a.x)
            point.y = a.y + t * (b.y - a.y)
    for anchor, a, b in zip(result.anchors, controls[low].anchors, controls[high].anchors):
        anchor.x = a.x + t * (b.x - a.x)
        anchor.y = a.y + t * (b.y - a.y)
    result.width = controls[low].width + t * (controls[high].width - controls[low].width)
    return result


def _corner(points, start, factor):
    """Change a short corner's radius about the intersection of its tangents.

    The same four points remain even at Sharp, keeping all masters compatible.
    Unlike rounding the whole outline, this leaves the bowls and counters alone.
    """
    p, a, b, q = points[start:start + 4]
    u = (a.x - p.x, a.y - p.y)
    v = (q.x - b.x, q.y - b.y)
    cross = u[0] * v[1] - u[1] * v[0]
    if abs(cross) < 1e-9:
        raise ValueError(f'Parallel corner tangents at point {start}')
    d = (q.x - p.x, q.y - p.y)
    t = (d[0] * v[1] - d[1] * v[0]) / cross
    cx, cy = p.x + t * u[0], p.y + t * u[1]
    for point in (p, a, b, q):
        point.x = cx + factor * (point.x - cx)
        point.y = cy + factor * (point.y - cy)


def roundness(glyph, value):
    if value == 50:
        return
    points = glyph.contours[0].points
    factor = value / 50 if value < 50 else 1 + (value - 50) / 100
    for start in (6, 15, 37, 49, 65):
        _corner(points, start, factor)
    # The terminal becomes nearly a semicircle at Round without crossing its
    # two on-curve endpoints; Thin/Regular/Black have different cap proportions.
    height = points[62].y - points[55].y
    radii = points[58].y - points[55].y + points[62].y - points[59].y
    maximum = 0.98 * height / radii
    cap_factor = value / 50 if value < 50 else 1 + (value - 50) / 50 * (maximum - 1)
    _corner(points, 55, cap_factor)
    _corner(points, 59, cap_factor)


def optical_size(glyph, target, text):
    """Extend Text using the existing g's proportions and o's stroke contrasts.

    The reviewed Text drawing is an exact fixed point. Display is not a scaled
    Regular: weight drawings stay independent, while counters compensate for
    the native o's optical stroke changes. Small is handled separately as the
    project's exact +17 sidebearing change.
    """
    sx = target['g'].width / text['g'].width
    old_g, new_g = bounds(text['g']), bounds(target['g'])
    sy_top, sy_bottom = new_g[3] / old_g[3], new_g[1] / old_g[1]
    before = [bounds(c) for c in glyph.contours[1:]]
    for contour in glyph.contours:
        for point in contour.points:
            point.x *= sx
            point.y *= sy_top if point.y >= 0 else sy_bottom
    # Retain the proof's two-bowl stroke allocation while following the native
    # optical-size change in horizontal and vertical strokes.
    old_o, new_o = text['o'], target['o']
    outer0, inner0 = (bounds(c) for c in old_o.contours)
    outer1, inner1 = (bounds(c) for c in new_o.contours)
    stem_x = (inner1[0] - outer1[0]) / (inner0[0] - outer0[0])
    stem_y = (outer1[3] - inner1[3]) / (outer0[3] - inner0[3])
    for contour, old_box in zip(glyph.contours[1:], before):
        x0, y0, x1, y1 = bounds(contour)
        # Control drawings intentionally have lighter horizontal strokes than o.
        ratio_y = (y1 - y0) / (old_box[3] - old_box[1])
        dx = (inner0[0] - outer0[0]) * (stem_x - sx)
        dy = (outer0[3] - inner0[3]) * (stem_y - ratio_y)
        fx, fy = 1 - 2 * dx / (x1 - x0), 1 - 2 * dy / (y1 - y0)
        if min(fx, fy) <= 0:
            raise ValueError('Optical counter compensation collapsed a counter')
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        for point in contour.points:
            point.x = cx + (point.x - cx) * fx
            point.y = cy + (point.y - cy) * fy
    for anchor in glyph.anchors:
        anchor.x *= sx
    current, reference = anchors(target['g']), anchors(text['g'])
    for anchor in glyph.anchors:
        anchor.y += current[anchor.name].y - reference[anchor.name].y


def make_g(font, reference, design_weight, rond, controls, *, small_shift=0, static=False):
    glyph = interpolate_drawing(design_weight, controls)
    # Undo Small's spacing-only translation before adapting the optical design.
    # Keep its ROND-specific shape: Black/Round has a deeper default descender
    # than Friendly, and Small must match Text at that same roundness exactly.
    target = font
    if small_shift:
        target = {name: font[name].copy() for name in ('g', 'o')}
        for original in target.values():
            original.move((-small_shift, 0))
            original.width -= 2 * small_shift
    optical_size(glyph, target, reference)
    roundness(glyph, rond)
    b = spacing_amount(design_weight)
    glyph.width = font['g'].width - (otRound(b) if static else b)
    if small_shift:
        glyph.move((small_shift, 0))
    original = anchors(font['g'])
    new = anchors(glyph)
    dx = new['top'].x - original['top'].x
    for name in ('cross', 'topr'):
        if name in original:
            anchor = deepcopy(original[name])
            anchor.x += dx
            glyph.anchors.append(anchor)
    # Quantization matches the reviewed static proof without rounding the full
    # source master graph; variable compilation performs compatible conversion.
    if static:
        for contour in glyph.contours:
            for point in contour.points:
                point.x, point.y = otRound(point.x), otRound(point.y)
    glyph.unicodes = []
    return glyph


def add_accents(font):
    base = anchors(font['g.ss04'])
    old_base = anchors(font['g'])
    dx, dy = base['top'].x - old_base['top'].x, base['top'].y - old_base['top'].y
    for original, accent in ACCENTS.items():
        source = font[original]
        if len(source.components) != 2 or source.components[0].baseGlyph != 'g' or source.components[1].baseGlyph != accent:
            raise ValueError(f'Unexpected upright composite: {original}')
        glyph = source.copy(name=original + '.ss04')
        glyph.unicodes = []
        # Accent sources sometimes differ from plain g by a fractional unit.
        # Preserve that metric distinction rather than forcing every advance
        # onto the plain-g width (which changes compiled rounding at some weights).
        glyph.width = source.width - (font['g'].width - font['g.ss04'].width)
        glyph.components[0].baseGlyph = 'g.ss04'
        mark = glyph.components[1]
        xx, xy, yx, yy, x, y = mark.transformation
        mark.transformation = (xx, xy, yx, yy, x + dx, y + dy)
        for anchor in glyph.anchors:
            if anchor.name == 'top':
                anchor.x += dx
                anchor.y += dy
            elif anchor.name in base:
                anchor.x, anchor.y = base[anchor.name].x, base[anchor.name].y
        if original == 'gcommaaccent':
            # The helper is a rotated comma ABOVE, with no outgoing top anchor.
            # Give this new composite a real stacking top instead of attaching
            # a following mark through its existing comma; defaults stay intact.
            top = anchors(glyph)['top']
            # Leave two units for outline/anchor quantization during compilation.
            top.y = math.ceil(bounds(font[accent], font)[3] + y + dy) + 2
        font.layers.defaultLayer.insertGlyph(glyph, overwrite=True, copy=False)


def add_upright(font, reference, design_weight, rond, controls, *, small_shift=0, static=False):
    glyph = make_g(font, reference, design_weight, rond, controls, small_shift=small_shift, static=static)
    font.layers.defaultLayer.insertGlyph(glyph, overwrite=True, copy=False)
    add_accents(font)
    integrate_features(font, design_weight, user_weight=font.info.openTypeOS2WeightClass if static else None)


def add_oblique(font, upright, design_weight):
    shear = math.tan(math.radians(-font.info.italicAngle))
    pivot = upright.info.xHeight / 2
    reference_top = anchors(upright['g.ss04'])['top'].y
    for original in G_FAMILY:
        name = original + '.ss04'
        source = upright[name]
        glyph = Glyph(name)
        pen = DecomposingRecordingPen(upright)
        source.draw(pen)
        pen.replay(glyph.getPen())
        glyph.width = source.width
        glyph.anchors = deepcopy(source.anchors)
        for contour in glyph.contours:
            for point in contour.points:
                point.x += shear * (point.y - pivot)
        for anchor in glyph.anchors:
            # Existing mark anchors are unsheared. Correct relative attachment,
            # not absolute coordinates: top marks originate at reference_top,
            # bottom marks at zero. This also supports stacked marks correctly.
            if anchor.name == 'top':
                anchor.x += shear * (anchor.y - reference_top)
            elif anchor.name == 'bottom':
                anchor.x += shear * anchor.y
        font.layers.defaultLayer.insertGlyph(glyph, overwrite=True, copy=False)
    integrate_features(font, design_weight, user_weight=font.info.openTypeOS2WeightClass)


def write_family(path, font):
    # UFO.save() can rewrite unrelated GLIFs. Write only the five new glyphs and
    # metadata that explicitly registers them; old drawings remain byte-identical.
    with UFOWriter(path, formatVersion=3) as writer:
        glyphs = writer.getGlyphSet()
        for original in G_FAMILY:
            glyph = font[original + '.ss04']
            glyphs.writeGlyph(glyph.name, glyph, glyph.drawPoints)
        glyphs.writeContents()
        writer.writeFeatures(font.features.text)
        writer.writeGroups(font.groups)
        writer.writeKerning(font.kerning)
        writer.writeLib(font.lib)


def generate(root=ROOT):
    ds = DesignSpaceDocument.fromfile(root / 'sources/Allo.designspace')
    mapping = next(axis for axis in ds.axes if axis.tag == 'wght')
    controls = control_drawings()
    small_shift = json.loads((root / 'release.json').read_text())['smallShift']
    masters = [source for source in ds.sources if source.layerName is None]
    for source in masters:
        loc = source.location
        size, weight, rond = (loc[key] for key in ('Optical size', 'Weight', 'Roundness'))
        reference_path = root / f'sources/masters/Allo-opsz14-wght{weight:g}-ROND50.ufo'
        with ufoLib2.Font.open(source.path) as font, ufoLib2.Font.open(reference_path) as reference:
            shift = small_shift if size == 9 else 0
            add_upright(font, reference, weight, rond, controls, small_shift=shift)
            write_family(source.path, font)
    for user_weight, style in zip(range(100, 901, 100), STYLES):
        weight = mapping.map_forward(user_weight)
        upright_path = root / f'sources/static/Allo-{style}.ufo'
        oblique_path = root / f"sources/static/Allo-{'' if style == 'Regular' else style}Oblique.ufo"
        with ufoLib2.Font.open(upright_path) as upright, ufoLib2.Font.open(oblique_path) as oblique:
            add_upright(upright, upright, weight, 50, controls, static=True)
            add_oblique(oblique, upright, weight)
            write_family(upright_path, upright)
            write_family(oblique_path, oblique)
    return len(masters) + 2 * len(STYLES)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='regenerate the five ss04 glyphs and their UFO layout metadata')
    args = parser.parse_args()
    if not args.write:
        parser.error('--write is required; this authoring step replaces existing ss04 source drawings')
    count = generate()
    print(f'Integrated the five-glyph ss04 family in {count} UFOs; existing GLIFs were not rewritten.')


if __name__ == '__main__':
    main()
