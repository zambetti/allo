"""In-memory ss04 layout integration; the caller owns geometry, widths and saving.

The five alternate names, the two public.kern*.g.ss04 groups, and the marked
feature block are owned by this module. Other feature text and kerning data
are preserved, apart from completing the three existing contextual classes.
"""

from __future__ import annotations

import math
import re
import unicodedata
from io import StringIO


import ufoLib2
from fontTools.feaLib import ast
from fontTools.feaLib.lexer import Lexer
from fontTools.feaLib.parser import Parser
from fontTools.misc.roundTools import otRound
from fontTools.ufoLib.kerning import lookupKerningValue

G_FAMILY = ("g", "gcircumflex", "gbreve", "gdotaccent", "gcommaaccent")
_ALTERNATES = tuple(name + ".ss04" for name in G_FAMILY)
_FIRST = "public.kern1.g.ss04"
_SECOND = "public.kern2.g.ss04"
_OWNED_KEYS = frozenset((*_ALTERNATES, _FIRST, _SECOND))
_BEGIN = "# BEGIN g_features ss04"
_END = "# END g_features ss04"
_BLOCK = "\n".join((
    _BEGIN,
    "feature ss04 {",
    '  featureNames { name "Double-storey g"; };',
    *(f"  sub {name} by {alternate};" for name, alternate in zip(G_FAMILY, _ALTERNATES)),
    "} ss04;",
    _END,
))
_OWNED_BLOCK = re.compile(
    r"(?:\n|\A)" + re.escape(_BEGIN) + r"\r?\n.*?^" + re.escape(_END) + r"(?:\r?\n|$)",
    re.MULTILINE | re.DOTALL,
)


def _finite_weight(value, name):
    try:
        weight = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(weight):
        raise ValueError(f"{name} must be a finite number")
    return weight


def _interpolate(weight, samples):
    if weight <= samples[0][0]:
        return float(samples[0][1])
    for (left, low), (right, high) in zip(samples, samples[1:]):
        if weight <= right:
            return float(low + (high - low) * (weight - left) / (right - left))
    return float(samples[-1][1])


def spacing_amount(design_weight) -> float:
    """Return B at a design coordinate, linearly interpolated and endpoint-clamped.

    Samples are 100:40, 400:48, 900:64. Static callers use otRound on this
    result when setting widths; this function itself never rounds.
    """
    weight = _finite_weight(design_weight, "design_weight")
    return _interpolate(weight, ((100, 40), (400, 48), (900, 64)))


def _amounts(design_weight, user_weight):
    weight = _finite_weight(design_weight, "design_weight")
    b = spacing_amount(weight)
    t = max(0.0, min(1.0, (weight - 580) / 320))
    if user_weight is not None:
        _finite_weight(user_weight, "user_weight")
        b = otRound(b)
        incoming = 2 * otRound(b / 2)
        heavy_j = otRound(40 * t * t * (3 - 2 * t))
    else:
        incoming = _interpolate(weight, ((100, 40), (400, 48), (580, 54), (900, 64)))
        heavy_j = 40 * t
    return b, incoming, heavy_j


def _parse(text, font):
    return Parser(StringIO(text), glyphNames=font.keys(), followIncludes=False).parse()


def _walk(statements):
    for statement in statements:
        yield statement
        yield from _walk(getattr(statement, "statements", ()))


def _complete_class(text, location):
    """Edit only owned glyph-name tokens, retaining comments and other members."""
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))

    def offset(loc):
        return offsets[loc.line - 1] + loc.column - 1

    tokens = list(Lexer(text, None))
    start = next(i for i, (_, value, loc) in enumerate(tokens)
                 if loc == location and value == "[")
    end = next(i for i in range(start + 1, len(tokens)) if tokens[i][1] == "]"
               and tokens[i][0] == Lexer.SYMBOL)
    opening, closing = offset(tokens[start][2]) + 1, offset(tokens[end][2])
    contents = text[opening:closing]
    removals = []
    for kind, value, loc in tokens[start + 1:end]:
        if kind == Lexer.NAME and value in _ALTERNATES:
            begin = offset(loc) - opening
            finish = begin + len(value)
            if begin and contents[begin - 1] == " ":
                begin -= 1
            removals.append((begin, finish))
    for begin, finish in reversed(removals):
        contents = contents[:begin] + contents[finish:]
    return text[:opening] + contents + " " + " ".join(_ALTERNATES) + text[closing:]


def _feature_text(font):
    text = _OWNED_BLOCK.sub("", font.features.text or "")
    if any(line.strip() in {_BEGIN, _END} for line in text.splitlines()):
        raise ValueError("incomplete owned ss04 block; restore its g_features markers")
    parsed = _parse(text, font)
    if any(isinstance(s, ast.FeatureBlock) and s.name == "ss04" for s in _walk(parsed.statements)):
        raise ValueError("unowned feature ss04 already exists; refusing to replace user feature code")

    locations = []
    for name in ("NOT_SPACE", "NOT_BRACKET"):
        matches = [s for s in parsed.statements
                   if isinstance(s, ast.GlyphClassDefinition) and s.name == name]
        if len(matches) != 1:
            raise ValueError(f"expected one existing @{name} class")
        locations.append(matches[0].glyphs.location)

    guards = []
    for feature in parsed.statements:
        if not isinstance(feature, ast.FeatureBlock) or feature.name != "calt":
            continue
        for statement in _walk(feature.statements):
            if not isinstance(statement, ast.IgnoreSubstStatement):
                continue
            for prefix, glyphs, suffix in statement.chainContexts:
                if (len(prefix) == len(glyphs) == 1 and suffix
                        and isinstance(prefix[0], ast.GlyphClass)
                        and set(glyphs[0].glyphSet()) == {"plus", "minus"}
                        and set(G_FAMILY).issubset(prefix[0].glyphSet())):
                    guards.append(prefix[0].location)
    if len(guards) != 1:
        raise ValueError("expected one inline lowercase calt guard before plus/minus")
    locations.extend(guards)
    # Later edits cannot invalidate the source locations of earlier classes.
    for location in sorted(locations, key=lambda loc: (loc.line, loc.column), reverse=True):
        text = _complete_class(text, location)
    result = text + "\n" + _BLOCK + "\n"
    _parse(result, font)
    return result


def _derivatives(font, root, names):
    """Find the actual family, not a name prefix or a broad kerning group."""
    result = {root} & names
    for name in sorted(names):
        glyph = font[name]
        if name == "oe" or 0x0153 in glyph.unicodes:
            continue
        for codepoint in glyph.unicodes:
            decomposition = unicodedata.normalize("NFD", chr(codepoint))
            first = decomposition[0]
            # U+00F8 has no canonical o+stroke decomposition, and the oblique
            # oslash has contours rather than the upright's o component.
            if root == "o" and first == "ø":
                first = "o"
            if first == root and all(unicodedata.combining(c) for c in decomposition[1:]):
                result.add(name)
                break
    changed = True
    while changed:
        changed = False
        for name in sorted(names - result):
            glyph = font[name]
            if name == "oe" or 0x0153 in glyph.unicodes or not glyph.components:
                continue
            base = glyph.components[0]
            if base.baseGlyph not in result or tuple(base.transformation)[:4] != (1, 0, 0, 1):
                continue
            # Multiple letters are ligatures, not accented derivatives. Permit
            # unencoded construction parts (e.g. the slash) and combining marks.
            decorations = glyph.components[1:]
            if any(c.baseGlyph not in font or any(unicodedata.category(chr(u)).startswith("L")
                                                 for u in font[c.baseGlyph].unicodes)
                   for c in decorations):
                continue
            result.add(name)
            changed = True
    return result


def _kerning(font, groups, kerning, b, incoming, heavy_j):
    names = set(font.keys()) - set(_ALTERNATES)
    maps = [{}, {}]
    for group, members in groups.items():
        for side in (0, 1):
            if group.startswith(f"public.kern{side + 1}."):
                for name in members:
                    if name in maps[side] and maps[side][name] != group:
                        raise ValueError(f"{name} belongs to multiple kern{side + 1} groups")
                    maps[side][name] = group

    def original(first, second):
        return lookupKerningValue((first, second), kerning, groups,
                                  glyphToFirstGroup=maps[0], glyphToSecondGroup=maps[1])

    rounds = set().union(*(_derivatives(font, root, names) for root in ("o", "e", "c")))
    incoming_n = _derivatives(font, "n", names)
    js = {"j", "jdotless", "jcircumflex"} & names
    result = {}
    for name in sorted(names):
        correction = -b if name in rounds else heavy_j if name in js else 0
        baseline = original("g", name) + correction
        if baseline:
            result[_FIRST, name] = baseline
        for source, alternate in zip(G_FAMILY, _ALTERNATES):
            value = original(source, name) + correction
            if value != baseline:
                result[alternate, name] = value

        correction = -incoming if name in incoming_n else 0
        baseline = original(name, "g") + correction
        if baseline:
            result[name, _SECOND] = baseline
        for source, alternate in zip(G_FAMILY, _ALTERNATES):
            value = original(name, source) + correction
            if value != baseline:
                result[name, alternate] = value

    # Neither preceding loop covers alternate-to-alternate pairs. Their old
    # counterparts can themselves have glyph exceptions, including zeroes.
    baseline = original("g", "g")
    if baseline:
        result[_FIRST, _SECOND] = baseline
    for first, first_alt in zip(G_FAMILY, _ALTERNATES):
        for second, second_alt in zip(G_FAMILY, _ALTERNATES):
            value = original(first, second)
            if value != baseline:
                result[first_alt, second_alt] = value
    return result


def integrate_features(font: ufoLib2.Font, design_weight, *, user_weight=None) -> None:
    """Integrate ss04 into an already extended UFO without saving it.

    All G_FAMILY glyphs and their .ss04 alternates must exist. Alternates are
    made unencoded and classified as bases; their geometry, anchors, widths
    and glyph libs are not changed. user_weight=None selects master sampling;
    any finite user_weight selects static rounding. Numeric evaluation always
    uses design_weight, not user_weight or the font's weight-class metadata.

    Repeated calls rebuild owned data from the untouched original family,
    including when weights or original kerning have changed. Conflicting
    unowned ss04 code or kerning memberships raise before mutation. The helper
    adds no manual kern feature: disabling kern removes its pair adjustments,
    not the B reduction already applied to alternate widths by the caller.
    """
    missing = sorted({*G_FAMILY, *_ALTERNATES} - set(font.keys()))
    if missing:
        raise ValueError("add the complete g family before integration: " + ", ".join(missing))
    amounts = _amounts(design_weight, user_weight)
    groups = {name: members for name, members in font.groups.items() if name not in {_FIRST, _SECOND}}
    for name, members in groups.items():
        if name.startswith(("public.kern1.", "public.kern2.")) and set(members) & set(_ALTERNATES):
            raise ValueError(f"alternate already belongs to unowned kerning group {name}")
    kerning = {pair: value for pair, value in font.kerning.items() if not _OWNED_KEYS.intersection(pair)}
    features = _feature_text(font)
    generated = _kerning(font, groups, kerning, *amounts)
    order = [name for name in font.lib.get("public.glyphOrder", sorted(font.keys())) if name not in _ALTERNATES]
    categories = dict(font.lib.get("public.openTypeCategories", {}))
    categories.update(dict.fromkeys(_ALTERNATES, "base"))

    for name in _ALTERNATES:
        font[name].unicodes = []
    font.lib["public.glyphOrder"] = order + list(_ALTERNATES)
    font.lib["public.openTypeCategories"] = categories
    font.features.text = features
    for name in (_FIRST, _SECOND):
        font.groups[name] = list(_ALTERNATES)
    for pair in list(font.kerning):
        if _OWNED_KEYS.intersection(pair):
            del font.kerning[pair]
    font.kerning.update(generated)
