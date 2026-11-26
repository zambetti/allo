"""In-memory Allo Custom naming and read-only validation of saved outputs.

The caller owns compilation, output paths, saving, and report serialization.
Only the explicit Allo identity namespace is supported; style/feature labels
are not family names and must not be changed by a blanket string replacement.
"""

from __future__ import annotations

from os import PathLike
from pathlib import Path
from typing import Iterable, Union

from fontTools.ttLib import TTFont


_IDENTITY_IDS = frozenset({1, 3, 4, 6, 16, 18, 21, 25})
_FAMILY_IDS = (1, 16, 21)
_FULL_IDS = (4, 18)
_STYLE_IDS = frozenset({2, 17, 22})
_REQUIRED_IDS = frozenset({1, 2, 3, 4, 6})
_PS_BASES = ("AlloVariableFriendly", "AlloVariable", "Allo")
_CUSTOM_PS_BASES = tuple(base.replace("Allo", "AlloCustom", 1) for base in _PS_BASES)
_NO_POSTSCRIPT_NAME = 65535


def _has_prefix(value: str, prefix: str, separator: str) -> bool:
    return value == prefix or value.startswith(prefix + separator)


def _check_postscript(value: str, context: str) -> None:
    if not 1 <= len(value) <= 63 or any(
        not 33 <= ord(char) <= 126 or char in "[](){}<>/%" for char in value
    ):
        raise ValueError(
            f"{context}: illegal PostScript name {value!r}; use 1–63 printable "
            "ASCII characters, without spaces or [](){}<>/%"
        )


def _renamed(value: str, postscript: bool, context: str) -> str:
    if postscript:
        if any(_has_prefix(value, base, "-") for base in _CUSTOM_PS_BASES):
            result = value
        elif any(_has_prefix(value, base, "-") for base in _PS_BASES):
            result = "AlloCustom" + value[len("Allo"):]
        else:
            raise ValueError(
                f"{context}: unexpected Allo PostScript identity {value!r}; "
                "expected Allo, AlloVariable, or AlloVariableFriendly "
                "(optionally followed by '-style'), or its AlloCustom equivalent"
            )
        _check_postscript(result, context)
        return result
    if _has_prefix(value, "Allo Custom", " "):
        return value
    if _has_prefix(value, "Allo", " "):
        return "Allo Custom" + value[len("Allo"):]
    raise ValueError(
        f"{context}: unexpected Allo identity {value!r}; expected 'Allo' "
        "or 'Allo ' followed by the existing family/style suffix"
    )


def _require_custom(value: str, postscript: bool, context: str) -> None:
    folded = value.casefold()
    prefixes = _CUSTOM_PS_BASES if postscript else ("Allo Custom",)
    separator = "-" if postscript else " "
    if not any(_has_prefix(folded, base.casefold(), separator) for base in prefixes):
        raise ValueError(
            f"{context}: stale or unexpected identity {value!r}; "
            "run rename_for_custom() before saving this custom font"
        )


def _name_context(record) -> str:
    return (
        f"name ID {record.nameID} "
        f"(platform {record.platformID}, encoding {record.platEncID}, "
        f"language {record.langID})"
    )


def _read_names(font: TTFont):
    if "name" not in font:
        raise ValueError("missing required name table")
    ps_ids = {6, 25}
    required = set(_REQUIRED_IDS)
    if "fvar" in font:
        fvar = font["fvar"]
        label_ids = {axis.axisNameID for axis in fvar.axes}
        label_ids.update(instance.subfamilyNameID for instance in fvar.instances)
        required.update(label_ids)
        for index, instance in enumerate(fvar.instances):
            name_id = instance.postscriptNameID
            if name_id == _NO_POSTSCRIPT_NAME:
                continue
            if (name_id != 6 and not 256 <= name_id <= 32767) or name_id in label_ids:
                raise ValueError(
                    f"fvar instance {index}: invalid postscriptNameID {name_id}; "
                    "use 6, a dedicated ID in 256–32767, or 65535 for no PS name"
                )
            ps_ids.add(name_id)
            required.add(name_id)
    relevant = _IDENTITY_IDS | _STYLE_IDS | ps_ids | required
    records = []
    for record in font["name"].names:
        if record.nameID not in relevant:
            continue
        try:
            value = record.toUnicode(errors="strict")
        except (UnicodeError, LookupError) as exc:
            raise ValueError(f"{_name_context(record)}: cannot decode name: {exc}") from exc
        if not value.strip():
            raise ValueError(f"{_name_context(record)}: empty identity or style label")
        records.append((record, value))
    present = {record.nameID for record, _ in records}
    missing = sorted(required - present)
    if missing:
        raise ValueError(f"missing required name IDs {missing} (including fvar references)")
    return records, ps_ids


def _values(records, name_ids) -> list[str]:
    return sorted({value for record, value in records if record.nameID in name_ids})


def _cff_identity(font: TTFont, records, custom: bool):
    if "CFF " not in font:
        return None
    cff = font["CFF "].cff
    if len(cff.fontNames) != 1 or len(cff.topDictIndex) != 1:
        raise ValueError("CFF: expected exactly one fontNames entry and one TopDict")
    top = cff.topDictIndex[0]
    family = getattr(top, "FamilyName", None)
    full = getattr(top, "FullName", None)
    families = _values(records, (16,)) or _values(records, (1,))
    if cff.fontNames != _values(records, (6,)):
        raise ValueError("CFF fontNames must agree with name ID 6")
    if family not in families:
        raise ValueError("CFF FamilyName must agree with name ID 16 (or ID 1 if absent)")
    if full not in _values(records, (4,)):
        raise ValueError("CFF FullName must agree with name ID 4")
    if custom:
        for key in ("UniqueID", "XUID"):
            if key in top.rawDict or key in vars(top):
                raise ValueError(f"CFF: stale numeric {key}; run rename_for_custom()")
    return {"font_names": list(cff.fontNames), "family_name": family, "full_name": full}


def rename_for_custom(font: TTFont) -> None:
    """Rename an Allo TTFont in memory, without saving it or changing styles.

    Rename all encodings/languages of IDs 1, 3, 4, 6, 16, 18, 21, 25 and
    explicit fvar instance PS IDs. Existing Custom identities are left alone.
    Name ID 25 is not synthesized; fvar's 65535 sentinel is not a name ID.
    Unexpected identities, missing required names, and encoding failures raise
    ValueError before any name strings or CFF identities are changed.
    """
    records, ps_ids = _read_names(font)
    replacements = []
    for record, value in records:
        if record.nameID not in _IDENTITY_IDS | ps_ids:
            continue
        context = _name_context(record)
        renamed = _renamed(value, record.nameID in ps_ids, context)
        try:
            encoded = renamed.encode(record.getEncoding(), errors="strict")
        except (UnicodeError, LookupError) as exc:
            raise ValueError(f"{context}: cannot encode custom name: {exc}") from exc
        replacements.append((record, encoded))
    cff_names = _cff_identity(font, records, custom=False)
    if cff_names is not None:
        cff_ps = _renamed(cff_names["font_names"][0], True, "CFF fontNames")
        cff_family = _renamed(cff_names["family_name"], False, "CFF FamilyName")
        cff_full = _renamed(cff_names["full_name"], False, "CFF FullName")

    for record, encoded in replacements:
        record.string = encoded
    if cff_names is not None:
        cff = font["CFF "].cff
        cff.fontNames[:] = [cff_ps]
        top = cff.topDictIndex[0]
        top.FamilyName = cff_family
        top.FullName = cff_full
        # CFF values may be either lazy rawDict entries or materialized attributes.
        for key in ("UniqueID", "XUID"):
            top.rawDict.pop(key, None)
            vars(top).pop(key, None)


def _paired_names(records, family_ids, style_ids) -> set[tuple[str, str]]:
    family_id = next(name_id for name_id in family_ids if _values(records, (name_id,)))
    pairs = set()
    for record, family in records:
        if record.nameID != family_id:
            continue
        locale = (record.platformID, record.platEncID, record.langID)
        localized = [
            (other, value) for other, value in records
            if (other.platformID, other.platEncID, other.langID) == locale
        ]
        styles = []
        for candidates in (localized, records):
            for style_id in style_ids:
                styles = _values(candidates, (style_id,))
                if styles:
                    break
            if styles:
                break
        pairs.update((family, style) for style in styles)
    return pairs


def _identity(font: TTFont, custom: bool) -> dict:
    records, ps_ids = _read_names(font)
    for record, value in records:
        context = _name_context(record)
        if record.nameID in ps_ids:
            _check_postscript(value, context)
        if custom and record.nameID in _IDENTITY_IDS | ps_ids:
            _require_custom(value, record.nameID in ps_ids, context)
    for name_id in sorted(ps_ids):
        if len(_values(records, (name_id,))) > 1:
            raise ValueError(f"name ID {name_id}: inconsistent PostScript names across records")
    pairs = set()
    for families, styles in (
        ((1,), (2,)), ((16, 1), (17, 2)), ((21, 16, 1), (22, 17, 2)),
    ):
        pairs.update(_paired_names(records, families, styles))
    instances = []
    if "fvar" in font:
        defaults = {axis.axisTag: axis.defaultValue for axis in font["fvar"].axes}
        base_ps = _values(records, (6,))[0].casefold()
        seen = {}
        for index, instance in enumerate(font["fvar"].instances):
            name_id = instance.postscriptNameID
            ps_names = [] if name_id == _NO_POSTSCRIPT_NAME else _values(records, (name_id,))
            for value in ps_names:
                folded = value.casefold()
                if folded == base_ps and instance.coordinates != defaults:
                    raise ValueError(
                        f"fvar instance {index}: non-default instance shares base "
                        f"PostScript name {value!r}"
                    )
                if folded in seen:
                    raise ValueError(
                        f"fvar instances {seen[folded]} and {index}: "
                        f"duplicate PostScript name {value!r}"
                    )
                seen[folded] = index
            pairs.update(_paired_names(records, (16, 1), (instance.subfamilyNameID,)))
            instances.append({
                "subfamily_name_id": instance.subfamilyNameID,
                "postscript_name_id": name_id,
                "styles": _values(records, (instance.subfamilyNameID,)),
                "postscript_names": ps_names,
                "coordinates": dict(sorted(instance.coordinates.items())),
            })
    identity_ids = _IDENTITY_IDS | _STYLE_IDS | ps_ids | {
        instance["subfamily_name_id"] for instance in instances
    }
    localized_names = sorted(
        (record.nameID, record.platformID, record.platEncID, record.langID, value)
        for record, value in records if record.nameID in identity_ids
    )
    names = {
        str(name_id): _values(records, (name_id,))
        for name_id in sorted({record.nameID for record, _ in records} & identity_ids)
    }
    return {
        "names": names,
        "name_records": [
            {"name_id": name_id, "platform_id": platform, "encoding_id": encoding,
             "language_id": language, "value": value}
            for name_id, platform, encoding, language, value in localized_names
        ],
        "families": _values(records, _FAMILY_IDS),
        "family_styles": [
            {"family": family, "style": style} for family, style in sorted(pairs)
        ],
        "full_names": _values(records, _FULL_IDS),
        "unique_ids": _values(records, (3,)),
        "postscript_names": _values(records, ps_ids - {25}),
        "postscript_prefixes": _values(records, (25,)),
        "instances": instances,
        "cff": _cff_identity(font, records, custom),
    }


def _paths(paths: Iterable[Union[str, PathLike]], label: str) -> list[Path]:
    result = sorted((Path(path) for path in paths), key=lambda path: (path.name.casefold(), path.name))
    if not result:
        raise ValueError(f"no {label} font files supplied; cannot validate custom/release isolation")
    names = set()
    for path in result:
        if path.name in names:
            raise ValueError(f"duplicate {label} basename {path.name!r}; supply each file once")
        names.add(path.name)
    return result


def _read_file(path: Path, custom: bool) -> dict:
    try:
        # Own the stream even if TTFont construction fails before __enter__.
        with path.open("rb") as stream:
            with TTFont(stream, lazy=True, recalcTimestamp=False) as font:
                identity = _identity(font, custom)
    except Exception as exc:
        raise ValueError(f"{path.name}: cannot validate font identity: {exc}") from exc
    return {"file": path.name, "stem": path.stem, **identity}


def _collision_fields(identity: dict) -> dict:
    return {
        "family": identity["families"],
        "full name": identity["full_names"],
        "unique ID": identity["unique_ids"],
        "PostScript name": identity["postscript_names"] + identity["postscript_prefixes"],
    }


def validate_custom_fonts(
    custom_paths: Iterable[Union[str, PathLike]],
    release_paths: Iterable[Union[str, PathLike]],
) -> dict:
    """Read saved fonts and return a deterministic JSON-serializable report.

    The supplied release references must be nonempty. Identity comparisons are
    case-insensitive, across all languages and corresponding identity namespaces.
    Custom files with exactly the same path.stem are format twins: their names,
    styles, and instance identities must agree. Different stems may share a
    family, but not a family/style pair, full name, unique ID, or PS identity.
    A default fvar instance may reuse its own base PS name.

    No files are written. The report contains basenames, not paths/timestamps;
    counts describe the supplied files, not a claim of complete release coverage.
    Invalid identities or collisions raise ValueError with the offending file.
    """
    references = _paths(release_paths, "release reference")
    outputs = _paths(custom_paths, "custom")
    release = [_read_file(path, custom=False) for path in references]
    custom = [_read_file(path, custom=True) for path in outputs]

    release_names = {}
    for identity in release:
        for category, values in _collision_fields(identity).items():
            for value in values:
                release_names.setdefault((category, value.casefold()), identity["file"])

    twins = {}
    seen = {}
    for identity in custom:
        stem = identity["stem"]
        signature = {
            key: identity[key] for key in ("name_records", "family_styles", "instances")
        }
        if stem in twins and twins[stem][0] != signature:
            raise ValueError(
                f"{identity['file']}: same-stem identity mismatch with {twins[stem][1]}"
            )
        twins.setdefault(stem, (signature, identity["file"]))
        fields = _collision_fields(identity)
        for category, values in fields.items():
            for value in values:
                reference = release_names.get((category, value.casefold()))
                if reference is not None:
                    raise ValueError(
                        f"{identity['file']}: {category} {value!r} collides with "
                        f"release reference {reference} (case-insensitive comparison)"
                    )
        del fields["family"]
        fields["family/style"] = [
            (pair["family"], pair["style"]) for pair in identity["family_styles"]
        ]
        for category, values in fields.items():
            for value in values:
                folded = (
                    tuple(part.casefold() for part in value)
                    if isinstance(value, tuple) else value.casefold()
                )
                key = (category, folded)
                previous = seen.get(key)
                if previous is not None and previous[0] != stem:
                    raise ValueError(
                        f"{identity['file']}: duplicate {category} {value!r} across "
                        f"distinct output stems ({previous[1]})"
                    )
                seen.setdefault(key, (stem, identity["file"]))

    return {
        "status": "ok",
        "custom_font_count": len(custom),
        "release_font_count": len(release),
        "families": sorted({family for identity in custom for family in identity["families"]}),
        "fonts": custom,
    }
