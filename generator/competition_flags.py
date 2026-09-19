from __future__ import annotations

"""
Bandiere (e opzionale logo lega) per competizione.

Fonte bandiere: flagcdn.com (HTTPS, stabile, w40 = 40px).
Aggiungi solo voci nuove; non rimuovere le esistenti.
"""

# country code ISO 3166-1 alpha-2 → usato in URL flagcdn
_COMPETITION_FLAG_CODE: dict[str, str] = {
    # Italia
    "serie_a": "it",
    "serie_b": "it",
    "serie_c": "it",
    "coppa_italia": "it",
    "supercoppa_italiana": "it",
    # Inghilterra
    "premier_league": "gb",
    "championship": "gb",
    # Spagna
    "la_liga": "es",
    "la_liga_2": "es",
    # Germania
    "bundesliga": "de",
    "bundesliga_2": "de",
    # Francia
    "ligue_1": "fr",
    # Portogallo
    "primeira_liga": "pt",
    # Olanda
    "eredivisie": "nl",
    "eerste_divisie": "nl",
    # Sud America / Nord America
    "liga_profesional": "ar",
    "brasileirao": "br",
    "mls": "us",
    "liga_mx": "mx",
    "copa_libertadores": "br",  # CONMEBOL: usiamo BR come default
    "copa_sudamericana": "ar",
    # UEFA / FIFA → bandiera generica europea / mondo non sempre disponibile
    "champions_league": "eu",
    "europa_league": "eu",
    "conference_league": "eu",
    "uefa_super_cup": "eu",
    "fifa_world_cup": "un",
    "fifa_club_world_cup": "un",
    # Motorsport / altri
    "formula_1": "un",
    "motogp": "un",
    "atp": "un",
    "wta": "un",
    "nba": "us",
    "wnba": "us",
    "nbl": "au",
    "euroleague": "eu",
}


def flag_url_for_code(code: str | None) -> str | None:
    if not code:
        return None
    code = code.strip().lower()
    if not code:
        return None
    # flagcdn: eu e un a volte non esistono; fallback su un png generico
    if code in {"eu", "un"}:
        # Europa / mondo: usiamo una bandiera neutra via flagcdn se disponibile,
        # altrimenti None (l'app userà l'emoji sport)
        if code == "eu":
            return "https://flagcdn.com/w40/eu.png"
        return None
    return f"https://flagcdn.com/w40/{code}.png"


def competition_flag_url(competition_id: str | None) -> str | None:
    if not competition_id:
        return None
    code = _COMPETITION_FLAG_CODE.get(competition_id.strip().lower())
    return flag_url_for_code(code)


def competition_logo_url(competition_id: str | None) -> str | None:
    """
    Per l'app attuale (che legge competition.logoUrl):
    usiamo la bandiera come logo competizione.
    """
    return competition_flag_url(competition_id)
