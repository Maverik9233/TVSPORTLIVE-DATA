from __future__ import annotations

"""
Bandiere competizione.

CDN primario: flagsapi.com (spesso più affidabile su mobile)
Alternativa EU: flagcdn.com
"""

_COMPETITION_FLAG_CODE: dict[str, str] = {
    "serie_a": "IT",
    "serie_b": "IT",
    "serie_c": "IT",
    "coppa_italia": "IT",
    "supercoppa_italiana": "IT",
    "premier_league": "GB",
    "championship": "GB",
    "la_liga": "ES",
    "la_liga_2": "ES",
    "bundesliga": "DE",
    "bundesliga_2": "DE",
    "ligue_1": "FR",
    "primeira_liga": "PT",
    "eredivisie": "NL",
    "eerste_divisie": "NL",
    "liga_profesional": "AR",
    "brasileirao": "BR",
    "mls": "US",
    "liga_mx": "MX",
    "copa_libertadores": "BR",
    "copa_sudamericana": "AR",
    "champions_league": "EU",
    "europa_league": "EU",
    "conference_league": "EU",
    "uefa_super_cup": "EU",
    "fifa_world_cup": "UN",
    "fifa_club_world_cup": "UN",
    "formula_1": "UN",
    "motogp": "UN",
    "atp": "UN",
    "wta": "UN",
    "nba": "US",
    "wnba": "US",
    "nbl": "AU",
    "euroleague": "EU",
}


def flag_url_for_code(code: str | None) -> str | None:
    if not code:
        return None
    code = code.strip().upper()
    if not code:
        return None
    if code == "EU":
        return "https://flagcdn.com/w40/eu.png"
    if code == "UN":
        return None
    return f"https://flagsapi.com/{code}/flat/64.png"


def competition_flag_url(competition_id: str | None) -> str | None:
    if not competition_id:
        return None
    code = _COMPETITION_FLAG_CODE.get(competition_id.strip().lower())
    return flag_url_for_code(code)


def competition_logo_url(competition_id: str | None) -> str | None:
    return competition_flag_url(competition_id)
