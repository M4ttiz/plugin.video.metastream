#!/usr/bin/env python3
"""Build Kodi repository metadata for the add-on repository."""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ADDON_XML = ROOT / "addon.xml"
ADDONS_XML = ROOT / "addons.xml"
ADDONS_MD5 = ROOT / "addons.xml.md5"


def build_addons_xml() -> None:
    if not ADDON_XML.exists():
        raise FileNotFoundError(f"Missing add-on manifest: {ADDON_XML}")

    addon_content = ADDON_XML.read_text(encoding="utf-8").strip()
    if addon_content.startswith("<?xml"):
        addon_content = addon_content.split("?>", 1)[1].strip()

    repository_xml = '<?xml version="1.0" encoding="UTF-8"?>\n<addons>\n' + addon_content + '\n</addons>\n'
    ADDONS_XML.write_text(repository_xml, encoding="utf-8")

    md5_hash = hashlib.md5(ADDONS_XML.read_bytes()).hexdigest()
    ADDONS_MD5.write_text(md5_hash, encoding="utf-8")


if __name__ == "__main__":
    build_addons_xml()
    print(f"Created {ADDONS_XML.name} and {ADDONS_MD5.name}")
