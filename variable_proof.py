"""Generate a standalone, offline variable-font pair proof from compiled WOFF2.

Build integration (after the full custom variable WOFF2 has been saved)::

    write_variable_proof(
        output_root / "fonts/webfonts/AlloCustomVariable.woff2",
        output_root / "variable-proof.html",
    )

Include the returned HTML path in the custom ZIP. Do not pass the Friendly font,
which pins an axis: controls reflect only the axes present in the supplied font.
The source font is read once, never rewritten, subsetted, or installed.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
from io import BytesIO
import json
import math
import os
from pathlib import Path
import re
import struct
import tempfile

from brotli import error as BrotliError
from fontTools.ttLib import TTFont, TTLibError


TEMPLATE_PATH = Path(__file__).resolve().parent / "templates/variable-proof.html.template"
DATA_PLACEHOLDER = "__VARIABLE_PROOF_DATA__"


def _font_metadata(data: bytes) -> dict:
    with TTFont(BytesIO(data), recalcTimestamp=False) as font:
        if font.flavor != "woff2":
            raise ValueError("Expected a compiled variable WOFF2, not a desktop font or WOFF.")
        if "fvar" not in font or not font["fvar"].axes:
            raise ValueError("Expected a variable WOFF2 with at least one fvar axis.")
        names = font["name"] if "name" in font else None
        axes = []
        seen = set()
        for axis in font["fvar"].axes:
            tag = str(axis.axisTag)
            if not re.fullmatch(r"[\x20-\x7e]{4}", tag) or tag in seen:
                raise ValueError(f"Invalid or duplicate fvar axis tag: {tag!r}.")
            seen.add(tag)
            minimum, default, maximum = map(float, (
                axis.minValue, axis.defaultValue, axis.maxValue,
            ))
            if not all(map(math.isfinite, (minimum, default, maximum))) or not minimum <= default <= maximum:
                raise ValueError(f"Invalid fvar range/default for axis {tag!r}.")
            axes.append({
                "tag": tag,
                "name": (names.getDebugName(axis.axisNameID) if names else None) or tag,
                "min": minimum, "default": default, "max": maximum,
            })
        features = set()
        for tag in ("GSUB", "GPOS"):
            if tag in font:
                feature_list = getattr(font[tag].table, "FeatureList", None)
                if feature_list:
                    features.update(record.FeatureTag for record in feature_list.FeatureRecord)
        return {
            "family": (names.getBestFamilyName() if names else None) or "Embedded variable font",
            "axes": axes,
            "features": sorted(features),
            "codepoints": sorted((font.getBestCmap() or {}).keys()),
        }


def _script_json(value: dict) -> str:
    # A script raw-text element is ended by </script> even with application/json.
    # ASCII encoding also escapes U+2028/U+2029; no data is interpolated into JS/CSS.
    return (json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def write_variable_proof(font_path: str | Path, output_path: str | Path, *,
                         download_filename: str | None = None) -> Path:
    """Embed the exact WOFF2 bytes and its fvar metadata; return the HTML Path.

    Accepts strings or Paths and creates missing output directories. Invalid,
    non-variable, and non-WOFF2 fonts raise ValueError. Missing/unreadable input,
    template, and output filesystem errors propagate as OSError subclasses.
    Validation precedes writing; an existing output is replaced atomically only
    after successful generation. The output must not alias the input font.
    download_filename optionally links to a ZIP beside the HTML; no archive is
    copied or fetched. Offline/bundled proofs omit that link by default.
    """
    if download_filename is not None and (not isinstance(download_filename, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.zip", download_filename)):
        raise ValueError("Download must be a local ZIP filename, not a path or URL.")
    font_path, output_path = Path(font_path), Path(output_path)
    if download_filename == output_path.name:
        raise ValueError("The proof output must not overwrite its download archive.")
    if (font_path.resolve() == output_path.resolve()
            or (output_path.exists() and font_path.exists() and output_path.samefile(font_path))):
        raise ValueError("The proof output must not overwrite its input font.")
    data = font_path.read_bytes()
    try:
        metadata = _font_metadata(data)
    except (TTLibError, BrotliError, KeyError, struct.error, EOFError, ValueError) as error:
        raise ValueError(f"Cannot generate variable proof from {font_path.name}: {error}") from error
    digest = hashlib.sha256(data).hexdigest()
    config = {
        **metadata,
        "filename": font_path.name,
        "sha256": digest,
        "fontFamily": "AlloVariableProof_" + digest[:16],
        "fontBase64": base64.b64encode(data).decode("ascii"),
    }
    if download_filename is not None:
        config["downloadFilename"] = download_filename
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    if template.count(DATA_PLACEHOLDER) != 1:
        raise ValueError("Variable proof template must contain exactly one data placeholder.")
    html = template.replace(DATA_PLACEHOLDER, _script_json(config))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=output_path.parent,
            prefix=".variable-proof-", suffix=".html", delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(html)
        os.replace(temporary_path, output_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return output_path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate a self-contained variable-font proof; no font is installed.")
    parser.add_argument("font", type=Path, help="compiled full-variable WOFF2")
    parser.add_argument("output", type=Path, help="HTML output path")
    parser.add_argument("--download", metavar="ZIP_FILENAME", help="optional link to a ZIP already beside the output")
    args = parser.parse_args(argv)
    result = write_variable_proof(args.font, args.output, download_filename=args.download)
    print(f"Wrote {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
