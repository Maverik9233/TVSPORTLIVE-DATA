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


# Fallback extra (oltre ESPN e Serie C).
# Aggiungi man mano: slug → URL HTTPS pubblico.
TEAM_LOGO_FALLBACK: dict[str, str] = {
    # esempi / placeholder utili; amplia senza rimuovere
}


def resolve_team_logo(
    team_name: str | None,
    existing_logo: str | None = None,
    competition_key: str | None = None,
) -> str | None:
    """
    Priorità:
    1) logo già presente (ESPN / fonte)
    2) mappa Serie C
    3) mappa TEAM_LOGO_FALLBACK
    """
    if existing_logo and existing_logo.strip():
        return existing_logo.strip()

    if not team_name:
        return None

    # Serie C (e nomi italiani generici in mappa)
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
