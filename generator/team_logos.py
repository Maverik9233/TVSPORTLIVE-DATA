from __future__ import annotations

from serie_c_logos import logo_from_static_map as serie_c_logo
from team_logo_cache import (
    espn_cdn,
    load_cache,
    lookup_logo,
    remember_logo,
    save_cache,
)

_CACHE = None


def _cache():
    global _CACHE
    if _CACHE is None:
        _CACHE = load_cache()
    return _CACHE


def resolve_team_logo(
    team_name: str | None,
    existing_logo: str | None = None,
    competition_key: str | None = None,
    team_id: str | None = None,
) -> str | None:
    cache = _cache()

    if existing_logo and existing_logo.strip():
        url = existing_logo.strip()
        if url.startswith("http://"):
            url = "https://" + url[len("http://") :]
        remember_logo(cache, team_id, team_name, url)
        return url

    found = lookup_logo(cache, team_id=team_id, team_name=team_name)
    if found:
        return found

    if team_id:
        raw = team_id.strip()
        if raw.lower().startswith("sofascore_") or (
            not raw.lower().startswith("espn_") and False
        ):
            url = sofascore_team_image_url(raw)
            if url:
                remember_logo(cache, team_id, team_name, url)
                return url
        if not raw.lower().startswith("espn_tennis_"):
            if raw.lower().startswith("espn_"):
                raw = raw[5:]
            if raw.isdigit():
                # ESPN solo come ultimo fallback numerico
                url = espn_cdn(raw)
                remember_logo(cache, team_id, team_name, url)
                return url

    if team_name:
        url = serie_c_logo(team_name)
        if url:
            remember_logo(cache, team_id, team_name, url)
            return url

    return None


def flush_logo_cache() -> None:
    global _CACHE
    if _CACHE is not None:
        save_cache(_CACHE)


def sofascore_team_image_url(team_id: str | int | None) -> str | None:
    """URL immagine SofaScore (funziona senza API key)."""
    if team_id is None:
        return None
    tid = str(team_id).strip()
    if tid.lower().startswith("sofascore_"):
        tid = tid.split("_", 1)[-1]
    if not tid.isdigit():
        return None
    return f"https://img.sofascore.com/api/v1/team/{tid}/image"
