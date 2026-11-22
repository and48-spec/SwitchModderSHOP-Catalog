"""Catalog Manager core: validated local overrides and atomic GitHub publishing."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone

REPO = "and48-spec/SwitchModderSHOP-Catalog"
RAW_CATALOG = "https://raw.githubusercontent.com/" + REPO + "/main/generated/catalog.json"
DATA_PATHS = ("data/custom_games.json", "data/addons.json")
TYPES = ("dlc", "language", "update", "other")
ID_PATTERN = re.compile(r"^[0-9A-F]{16}$")
MAX_CATALOG_BYTES = 85 * 1024 * 1024


def data_dir() -> Path:
    home = os.environ.get("LOCALAPPDATA")
    root = Path(home) if home else Path.home() / ".local" / "share"
    return root / "SwitchModderSHOP" / "CatalogManager"


def json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def read_json(path: Path, default=None):
    if not path.exists():
        return [] if default is None else default
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def atomic_write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".catalog-", delete=False) as stream:
        stream.write(text)
        tmp = Path(stream.name)
    try:
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def backup_local(folder: Path, files: dict):
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    backup_dir = folder / "backups" / stamp
    backup_dir.mkdir(parents=True, exist_ok=False)
    for name, data in files.items():
        atomic_write(backup_dir / Path(name).name, json_text(data))
    return backup_dir


def normalized_id(text: str, required=False) -> str:
    value = str(text or "").strip().upper()
    if not value and not required:
        return ""
    if not ID_PATTERN.fullmatch(value):
        raise ValueError("Title ID non valido: usare esattamente 16 cifre esadecimali.")
    return value


def key_for(item: dict) -> str:
    if not isinstance(item, dict):
        raise ValueError("Ogni voce deve essere un oggetto JSON.")
    ident = item.get("title_id") or item.get("titleId") or ""
    if ident:
        return "id:" + normalized_id(ident)
    title = str(item.get("title") or item.get("name") or "").strip()
    if not title:
        raise ValueError("Ogni gioco richiede titolo oppure Title ID.")
    return "title:" + title.casefold()


def normalize_game(item: dict) -> dict:
    item = dict(item)
    if item.get("title_id"):
        item["title_id"] = normalized_id(item["title_id"])
    if "title" in item:
        item["title"] = str(item["title"]).strip()
    key_for(item)
    for field in ("title", "version", "description", "cover", "url", "magnet"):
        if field in item and not isinstance(item[field], str):
            raise ValueError("Il campo " + field + " deve essere testo.")
    return item


def normalize_addon(item: dict) -> dict:
    item = dict(item)
    item["title"] = str(item.get("title") or "").strip()
    item["parent_title_id"] = normalized_id(
        item.get("parent_title_id") or item.get("base_title_id"), required=True
    )
    item["content_type"] = str(item.get("content_type") or item.get("type") or "").strip().lower()
    if not item["title"]:
        raise ValueError("Ogni DLC/traduzione richiede un titolo.")
    if item["content_type"] not in TYPES:
        raise ValueError("Tipo non valido; scegliere DLC, lingua, aggiornamento o altro.")
    if item.get("title_id"):
        item["title_id"] = normalized_id(item["title_id"])
    item.pop("base_title_id", None)
    item.pop("type", None)
    for field in ("language", "version", "description", "cover", "url", "magnet"):
        if field in item and not isinstance(item[field], str):
            raise ValueError("Il campo " + field + " deve essere testo.")
    return item


def addon_key(item: dict) -> str:
    ident = item.get("title_id")
    if ident:
        return "id:" + normalized_id(ident)
    return "addon:" + normalized_id(item["parent_title_id"]) + "/" + item["content_type"] + "/" + item["title"].strip().casefold()


def validate(games, addons):
    if not isinstance(games, list) or not isinstance(addons, list):
        raise ValueError("I due file devono contenere array JSON.")
    out_games = [normalize_game(item) for item in games]
    out_addons = [normalize_addon(item) for item in addons]
    keys = [key_for(x) for x in out_games]
    if len(keys) != len(set(keys)):
        raise ValueError("Giochi duplicati: stesso Title ID o titolo.")
    keys = [addon_key(x) for x in out_addons]
    if len(keys) != len(set(keys)):
        raise ValueError("Componenti aggiuntivi duplicati.")
    return out_games, out_addons


def _api(path: str, token: str = "", method="GET", data=None):
    url = "https://api.github.com/repos/" + REPO + "/" + path.lstrip("/")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "SwitchModderSHOP-CatalogManager/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = "Bearer " + token.strip()
    body = None
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.loads(response.read(2 * 1024 * 1024).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = json.loads(exc.read(4096).decode("utf-8")).get("message", "")
        except Exception:
            pass
        raise RuntimeError("GitHub HTTP " + str(exc.code) + ": " + (detail or exc.reason)) from None
    except urllib.error.URLError as exc:
        raise RuntimeError("Connessione GitHub fallita: " + str(exc.reason)) from None


def get_inputs(token=""):
    contents = []
    for path in DATA_PATHS:
        response = _api("contents/" + path + "?ref=main", token)
        if response.get("encoding") != "base64":
            raise RuntimeError("Risposta GitHub non valida per " + path)
        raw = base64.b64decode(response["content"])
        contents.append(json.loads(raw.decode("utf-8-sig")))
    return validate(*contents)


def get_public_catalog():
    request = urllib.request.Request(RAW_CATALOG,
             headers={"User-Agent": "SwitchModderSHOP-CatalogManager/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=90) as stream:
            raw = stream.read(MAX_CATALOG_BYTES + 1)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError("Download catalogo non riuscito: " + str(exc)) from None
    if len(raw) > MAX_CATALOG_BYTES:
        raise ValueError("Catalogo remoto oltre il limite di 85 MiB.")
    root = json.loads(raw.decode("utf-8-sig"))
    games = root if isinstance(root, list) else root.get("games", root.get("items", root.get("data")))
    if not isinstance(games, list) or len(games) < 1000:
        raise ValueError("Catalogo pubblico inatteso o incompleto.")
    return games


def publish(games, addons, loaded_games, loaded_addons, token):
    token = token.strip()
    if not token:
        raise ValueError("Inserire un token GitHub con Contents: Read and write sul repository Catalog.")
    games, addons = validate(games, addons)
    current_games, current_addons = get_inputs(token)
    if current_games != loaded_games or current_addons != loaded_addons:
        raise RuntimeError("Il catalogo è cambiato su GitHub. Ricaricalo prima di pubblicare; modifiche locali preservate.")
    ref = _api("git/ref/heads/main", token)
    parent = ref["object"]["sha"]
    commit = _api("git/commits/" + parent, token)
    tree = _api("git/trees", token, method="POST", data={
        "base_tree": commit["tree"]["sha"],
        "tree": [
            {"path": DATA_PATHS[0], "mode": "100644", "type": "blob", "content": json_text(games)},
            {"path": DATA_PATHS[1], "mode": "100644", "type": "blob", "content": json_text(addons)},
        ],
    })
    new_commit = _api("git/commits", token, method="POST", data={
        "message": "catalog: update games and add-ons via Windows manager",
        "tree": tree["sha"],
        "parents": [parent],
    })
    _api("git/refs/heads/main", token, method="PATCH",
         data={"sha": new_commit["sha"], "force": False})
    return new_commit["sha"]


def self_test():
    assert normalized_id("010000000000000a") == "010000000000000A"
    assert validate([{"title_id": "010000000000000A", "title": "Example"}], [
        {"title": "Italian pack", "parent_title_id": "010000000000000a",
         "content_type": "language", "language": "it"}
    ])[1][0]["parent_title_id"] == "010000000000000A"
    try:
        validate([{"title": "A"}, {"title": "a"}], [])
    except ValueError:
        pass
    else:
        raise AssertionError("Duplicate games allowed")
    try:
        normalize_addon({"title": "Missing ID", "content_type": "language"})
    except ValueError:
        pass
    else:
        raise AssertionError("Orphan addon allowed")
    print("Catalog Manager core tests OK")
