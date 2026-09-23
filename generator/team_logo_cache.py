"""
Cache persistente loghi squadre (club + nazionali).

- Si riempie ad ogni run del generatore dagli eventi ESPN
- File: data/team_logos_cache.json (id + slug nome → URL)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

CACHE_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "team_logos_cache.json"
)


def _slug(value: str) -> str:
    value = value.upper()
    for src, dst in (
        ("À", "A"), ("È", "E"), ("É", "E"),
        ("Ì", "I"), ("Ò", "O"), ("Ù", "U"),
        ("Ä", "A"), ("Ö", "O"), ("Ü", "U"),
        ("Ñ", "N"), ("Ç", "C"),
    ):
        value = value.replace(src, dst)
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def _https(url: str) -> str:
    url = url.strip()
    if url.startswith("http://"):
        return "https://" + url[len("http://") :]
    return url


def espn_cdn(numeric_id: str) -> str:
    return f"https://a.espncdn.com/i/teamlogos/soccer/500/{numeric_id}.png"


def load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {"by_id": {}, "by_name": {}}
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"by_id": {}, "by_name": {}}
        data.setdefault("by_id", {})
        data.setdefault("by_name", {})
        return data
    except Exception:
        return {"by_id": {}, "by_name": {}}


def save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def remember_logo(
    cache: dict,
    team_id: str | None,
    team_name: str | None,
    logo_url: str | None,
) -> None:
    if not logo_url or not str(logo_url).strip():
        if team_id:
            raw = team_id.strip()
            if raw.lower().startswith("espn_"):
                raw = raw[5:]
            if raw.isdigit():
                logo_url = espn_cdn(raw)
            else:
                return
        else:
            return

    url = _https(str(logo_url))
    if team_id:
        tid = team_id.strip()
        cache["by_id"][tid] = url
        if tid.lower().startswith("espn_"):
            cache["by_id"][tid[5:]] = url
        elif tid.isdigit():
            cache["by_id"][f"espn_{tid}"] = url
    if team_name:
        cache["by_name"][_slug(team_name)] = url


def lookup_logo(
    cache: dict,
    team_id: str | None = None,
    team_name: str | None = None,
) -> str | None:
    if team_id:
        tid = team_id.strip()
        for key in (tid, tid.lower(), tid.replace("espn_", ""), f"espn_{tid}"):
            if key in cache.get("by_id", {}):
                return cache["by_id"][key]
        raw = tid[5:] if tid.lower().startswith("espn_") else tid
        if raw.isdigit():
            return espn_cdn(raw)
    if team_name:
        key = _slug(team_name)
        if key in cache.get("by_name", {}):
            return cache["by_name"][key]
        for map_key, url in cache.get("by_name", {}).items():
            if key and (key in map_key or map_key in key):
                return url
    return None


def ingest_raw_events(events, cache: dict | None = None) -> dict:
    cache = cache if cache is not None else load_cache()
    before = len(cache.get("by_id", {})) + len(cache.get("by_name", {}))
    for ev in events:
        remember_logo(
            cache,
            getattr(ev, "home_team_id", None),
            getattr(ev, "home_team_name", None),
            getattr(ev, "home_team_logo", None),
        )
        remember_logo(
            cache,
            getattr(ev, "away_team_id", None),
            getattr(ev, "away_team_name", None),
            getattr(ev, "away_team_logo", None),
        )
    after = len(cache.get("by_id", {})) + len(cache.get("by_name", {}))
    save_cache(cache)
    print(f"[LOGOS] Cache aggiornata: {after} voci (+{after - before})")
    return cache
