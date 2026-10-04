"""Validated, immutable visual site-context package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
from typing import Any


DEFAULT_SITE_CONTEXT_ROOT = Path(__file__).resolve().parents[1] / "site-context"


class SiteContextError(ValueError):
    pass


def _jpeg_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        raise SiteContextError("Luchtfoto is geen geldig JPEG-bestand.")
    offset = 2
    while offset + 4 <= len(data):
        if data[offset] != 0xFF:
            raise SiteContextError("Luchtfoto bevat ongeldige JPEG-segmenten.")
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1
        marker = data[offset]
        offset += 1
        if marker in {0xD8, 0xD9}:
            continue
        if marker == 0xDA or offset + 2 > len(data):
            break
        length = struct.unpack(">H", data[offset:offset + 2])[0]
        if length < 2 or offset + length > len(data):
            break
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            if length < 7:
                break
            height, width = struct.unpack(">HH", data[offset + 3:offset + 7])
            return width, height
        offset += length
    raise SiteContextError("Afmetingen van de JPEG-luchtfoto zijn ongeldig.")


def load_site_context(root: Path = DEFAULT_SITE_CONTEXT_ROOT) -> dict[str, Any]:
    root = root.resolve()
    manifest_path = root / "manifest.json"
    try:
        raw = manifest_path.read_bytes()
        manifest = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SiteContextError("Luchtfotocontext kan niet worden gelezen.") from exc
    image_name = manifest.get("image_filename") if isinstance(manifest, dict) else None
    image_path = (root / image_name).resolve() if isinstance(image_name, str) else None
    corners = manifest.get("local_corners_m") if isinstance(manifest, dict) else None
    required_corners = {"south_west", "south_east", "north_west", "north_east"}
    if (manifest.get("schema_version") != 1 or manifest.get("kind") != "visual_aerial"
            or not image_path or not image_path.is_relative_to(root) or not image_path.is_file()
            or not isinstance(corners, dict) or set(corners) != required_corners
            or any(not isinstance(corners[key], list) or len(corners[key]) != 3
                   or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in corners[key])
                   for key in required_corners)):
        raise SiteContextError("Luchtfotocontext heeft een ongeldig manifest.")
    try:
        image = image_path.read_bytes()
    except OSError as exc:
        raise SiteContextError("Luchtfoto kan niet worden gelezen.") from exc
    if len(image) > 10 * 1024 * 1024 or hashlib.sha256(image).hexdigest() != manifest.get("image_sha256"):
        raise SiteContextError("Luchtfoto wijkt af van het vastgelegde contextpakket.")
    if _jpeg_dimensions(image) != (manifest.get("image_width"), manifest.get("image_height")):
        raise SiteContextError("Luchtfoto heeft onverwachte afmetingen.")
    source = manifest.get("source")
    alignment = manifest.get("alignment")
    if (not isinstance(source, dict) or not isinstance(source.get("attribution"), str)
            or not isinstance(alignment, dict) or alignment.get("status") != "provisional"):
        raise SiteContextError("Luchtfotocontext mist bron- of uitlijnprovenance.")
    return {**manifest, "manifest_sha256": hashlib.sha256(raw).hexdigest(),
            "manifest_path": manifest_path, "image_path": image_path}


def public_site_context(root: Path = DEFAULT_SITE_CONTEXT_ROOT) -> dict[str, Any]:
    context = load_site_context(root)
    return {key: value for key, value in context.items() if key not in {"manifest_path", "image_path", "image_filename"}} | {
        "image_url": "/api/site-context/aerial.jpg",
    }
