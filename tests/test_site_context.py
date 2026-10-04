import json
import shutil

import pytest

from app.site_context import DEFAULT_SITE_CONTEXT_ROOT, SiteContextError, load_site_context, public_site_context


def copy_context(tmp_path):
    root = tmp_path / "site-context"
    root.mkdir(parents=True)
    shutil.copy2(DEFAULT_SITE_CONTEXT_ROOT / "manifest.json", root / "manifest.json")
    shutil.copy2(DEFAULT_SITE_CONTEXT_ROOT / "parkhaven-aerial-2025.jpg", root / "parkhaven-aerial-2025.jpg")
    return root


def test_pinned_site_context_has_bounded_public_contract():
    context = load_site_context()
    public = public_site_context()
    assert context["image_width"] == context["image_height"] == 2500
    assert public["manifest_sha256"] == context["manifest_sha256"]
    assert public["image_url"] == "/api/site-context/aerial.jpg"
    assert "image_path" not in public and "manifest_path" not in public and "image_filename" not in public


def test_site_context_rejects_changed_image_and_path_escape(tmp_path):
    root = copy_context(tmp_path)
    image = root / "parkhaven-aerial-2025.jpg"
    image.write_bytes(image.read_bytes() + b"changed")
    with pytest.raises(SiteContextError, match="wijkt af"):
        load_site_context(root)

    root = copy_context(tmp_path / "other")
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["image_filename"] = "../outside.jpg"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(SiteContextError, match="ongeldig manifest"):
        load_site_context(root)
