from __future__ import annotations

import re
from typing import Optional

from serie_c_logos import logo_from_static_map as serie_c_logo


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


TEAM_LOGO_FALLBACK: dict[str, str] = {
    # amplia senza rimuovere
}


def espn_soccer_logo_url(team_id: str | None) -> str | None:
    """Costruisce URL stemma ESPN da id numerico (club o nazionale)."""
    if not team_id:
        return None
    raw = team_id.strip()
    if not raw:
        return None
    # espn_347, 347, espn_tennis_… (skip tennis)
    if raw.lower().startswith("espn_tennis_"):
        return None
    if raw.lower().startswith("espn_"):
        raw = raw[5:]
    if raw.isdigit():
        return f"https://a.espncdn.com/i/teamlogos/soccer/500/{raw}.png"
    return None


def resolve_team_logo(
    team_name: str | None,
    existing_logo: str | None = None,
    competition_key: str | None = None,
    team_id: str | None = None,
) -> str | None:
    """
    Priorità:
    1) logo già presente (ESPN / fonte)
    2) CDN ESPN da id numerico (club + nazionali)
    3) mappa Serie C
    4) mappa TEAM_LOGO_FALLBACK
    """
    if existing_logo and existing_logo.strip():
        url = existing_logo.strip()
        # forza https
        if url.startswith("http://"):
            url = "https://" + url[len("http://"):]
        return url

    espn = espn_soccer_logo_url(team_id)
    if espn:
        return espn

    if not team_name:
        return None

    url = serie_c_logo(team_name)
    if url:
        return url

    key = _slug(team_name)
    if not key:
        return None

    if key in TEAM_LOGO_FALLBACK:
        return TEAM_LOGO_FALLBACK[key]

    for map_key, map_url in TEAM_LOGO_FALLBACK.items():
        if key in map_key or map_key in key:
            return map_url

    return None
