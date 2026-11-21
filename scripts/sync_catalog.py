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

def normalize_for_switch(item):
    """Return the client-compatible entry, keeping source fields otherwise intact.

    The old Nintendo Switch SAX parser understands screenshots as an array,
    but treats every other nested array as the end of the games list.
    Upstream now emits "titles" as an array of release-title objects while
    our C++ client expects the compact "ID:update:version;..." string.
    """
    result = dict(item)
    if isinstance(result.get("titles"), list):
        converted = []
        for release in result["titles"]:
            if isinstance(release, str):
                # Accept complete encoded records as-is.
                if len(release.split(":", 1)[0]) == 16:
                    converted.append(release)
                continue
            if not isinstance(release, dict):
                continue
            title_id = str(release.get("id") or release.get("title_id") or "").strip().upper()
            if len(title_id) != 16 or any(ch not in "0123456789ABCDEF" for ch in title_id):
                continue
            version_value = release.get("update_version")
            update = str(version_value) if (
                isinstance(version_value, int) and version_value >= 0
            ) or (isinstance(version_value, str) and version_value.isdecimal()) else ""
            version = str(release.get("version") or "").replace(";", " ").replace(":", " ")
            converted.append(f"{title_id}:{update}:{version}")
        result["titles"] = ";".join(converted)
    # Unknown nested arrays must not silently terminate a full feed in a
    # previously released Switch client. Retain their information as JSON text.
    for key, value in result.items():
        if key != "screenshots" and isinstance(value, list):
            result[key] = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return result


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
    # Produce one normalized feed. The upstream JSON is never modified and
    # custom records remain editable independently.
    output_games = [normalize_for_switch(game) for game in result]
    visible_count = sum(bool(str(item.get("title") or "").strip()) for item in output_games)
    if visible_count < 1000:
        raise ValueError(f"Client-compatible feed has only {visible_count} titles")
    if container_key is None:
        output = output_games
    else:
        output = {key: value for key, value in source.items() if key != container_key}
        output["games"] = output_games
    changed = write_json(ROOT / "generated/catalog.json", output)
    changed_addons = write_json(ROOT / "generated/addons.json", normalized_addons)
    print(f"Games: {len(result)}; client titles: {visible_count}; addons: {len(addons)}; changed: {changed or changed_addons}")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"Sync failed; existing generated files preserved: {exc}", file=sys.stderr)
        sys.exit(1)
