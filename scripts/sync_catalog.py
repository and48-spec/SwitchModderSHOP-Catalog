#!/usr/bin/env python3
"""Build a standalone game catalog and separate add-on index."""
import json
import os
import pathlib
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
UPSTREAM_URL = "https://raw.githubusercontent.com/langegen/switch-games/refs/heads/main/switch_games.json"
MAX_BYTES = 85 * 1024 * 1024

def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as f:
        f.write(content)
        temporary = f.name
    os.replace(temporary, path)
    return True

def upstream():
    request = urllib.request.Request(UPSTREAM_URL, headers={"User-Agent": "SwitchModderSHOP-Catalog/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        body = response.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError("Upstream source exceeds 85 MiB")
    return json.loads(body.decode("utf-8-sig"))

def records(document):
    if isinstance(document, list):
        return document, None
    if isinstance(document, dict):
        for key in ("games", "items", "data"):
            if isinstance(document.get(key), list):
                return document[key], key
    raise ValueError("Unknown upstream JSON structure; source unchanged")

def key_for(item):
    if not isinstance(item, dict):
        raise ValueError("Catalog entries must be JSON objects")
    title_id = str(item.get("title_id") or item.get("titleId") or "").strip().upper()
    if title_id:
        return "id:" + title_id
    title = str(item.get("title") or item.get("name") or "").strip().casefold()
    if title:
        return "title:" + title
    raise ValueError("Entry without title or title_id")

def check_custom(entries, label):
    if not isinstance(entries, list):
        raise ValueError(label + " must be a JSON array")
    ids = set()
    for entry in entries:
        k = key_for(entry)
        if k in ids:
            raise ValueError("Duplicate within " + label + ": " + k)
        ids.add(k)

def main():
    custom = read_json(ROOT / "data/custom_games.json")
    addons = read_json(ROOT / "data/addons.json")
    check_custom(custom, "custom_games.json")
    check_custom(addons, "addons.json")
    normalized_addons = []
    for entry in addons:
        title = str(entry.get("title") or "").strip()
        parent = str(entry.get("parent_title_id") or entry.get("base_title_id") or "").strip().upper()
        content_type = str(entry.get("content_type") or entry.get("type") or "").strip().lower()
        if not title or not parent:
            raise ValueError("Each add-on needs title and parent_title_id")
        if content_type not in ("dlc", "language", "update", "other"):
            raise ValueError("Invalid add-on content_type: " + content_type)
        normalized = dict(entry)
        normalized["parent_title_id"] = parent
        normalized["content_type"] = content_type
        normalized.pop("base_title_id", None)
        normalized.pop("type", None)
        normalized_addons.append(normalized)
    source = upstream()
    base, container_key = records(source)
    # Refuse destructive updates from a truncated or empty upstream response.
    if len(base) < 1000:
        raise ValueError(f"Upstream has only {len(base)} records; refusing to replace the catalog")
    if any(not isinstance(entry, dict) for entry in base):
        raise ValueError("Upstream contains non-object records")
    # Preserve EVERY upstream entry (including multiple releases/versions).
    result = list(base)
    positions = {}
    for index, entry in enumerate(result):
        k = key_for(entry)
        positions.setdefault(k, []).append(index)
    for entry in custom:
        k = key_for(entry)
        if k in positions:
            # Apply local metadata to matching entries without dropping versions.
            for index in positions[k]:
                result[index] = {**result[index], **entry}
        else:
            positions[k] = [len(result)]
            result.append(entry)
    output = result if container_key is None else {**source, container_key: result}
    changed = write_json(ROOT / "generated/catalog.json", output)
    changed_addons = write_json(ROOT / "generated/addons.json", normalized_addons)
    print(f"Games: {len(result)}; addons: {len(addons)}; changed: {changed or changed_addons}")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"Sync failed; existing generated files preserved: {exc}", file=sys.stderr)
        sys.exit(1)
