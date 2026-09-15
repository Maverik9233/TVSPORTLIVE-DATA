from __future__ import annotations

import os


# ============================================================
# TVSPORTLIVE - GENERATOR CONFIGURATION
# ============================================================

APP_NAME = "TVSPORTLIVE"

# ------------------------------------------------------------
# Dropbox
#
# Questi sono gli stessi tre file che l'app Android utilizza.
# Il generatore leggerà channels.txt e aggiornerà:
#
#   events.txt
#   live.txt
#
# Le credenziali Dropbox NON vengono salvate qui.
# Verranno fornite tramite GitHub Secrets.
# ------------------------------------------------------------

CHANNELS_URL = (
    "https://www.dropbox.com/scl/fi/"
    "9ecu6jkvziuzanftvc9zn/channels.txt"
    "?rlkey=e1itmamnnvjpuga57ihuoa8ac"
    "&st=mi0gwguz"
    "&dl=1"
)

EVENTS_URL = (
    "https://www.dropbox.com/scl/fi/"
    "8a42xmyn1qmorx0y7nz31/events.txt"
    "?rlkey=cjmsa47wiioait2oxbgjti7ee"
    "&st=iiffkqth"
    "&dl=1"
)

LIVE_URL = (
    "https://www.dropbox.com/scl/fi/"
    "0xjtwvlt85farvcnv4elr/live.txt"
    "?rlkey=oa1j9f2fjnt2orubd17o6qbvn"
    "&st=6zppwb5v"
    "&dl=1"
)


# ------------------------------------------------------------
# GitHub Secrets
#
# NON inserire mai direttamente questi valori nel file.
# ------------------------------------------------------------

DROPBOX_ACCESS_TOKEN = os.getenv(
    "TVSPORTLIVE_DROPBOX_ACCESS_TOKEN",
    ""
)


# ------------------------------------------------------------
# Generatore
# ------------------------------------------------------------

TIMEZONE = "Europe/Rome"

EVENTS_DAYS_AHEAD = 1

REQUEST_TIMEOUT_SECONDS = 30

USER_AGENT = (
    "TVSPORTLIVE-DataGenerator/1.0 "
    "(automated sports data updater)"
)


# ------------------------------------------------------------
# Sport supportati
# ------------------------------------------------------------

SUPPORTED_SPORTS = (
    "FOOTBALL",
    "FORMULA_1",
    "MOTOGP",
    "TENNIS",
    "BASKETBALL",
)


# ------------------------------------------------------------
# Competizioni supportate
#
# L'elenco serve come filtro del generatore.
# Non significa che vengano inventati eventi:
# verranno inseriti soltanto eventi realmente trovati
# dalle fonti configurate.
# ------------------------------------------------------------

SUPPORTED_COMPETITIONS = (
    "serie_a",
    "serie_b",
    "serie_c",
    "coppa_italia",
    "supercoppa_italiana",
    "champions_league",
    "europa_league",
    "conference_league",
    "uefa_super_cup",
    "fifa_world_cup",
    "fifa_club_world_cup",
    "premier_league",
    "la_liga",
    "bundesliga",
    "ligue_1",
    "primeira_liga",
    "eredivisie",
    "formula_1",
    "motogp",
    "atp",
    "wta",
    "euroleague",
    "nba",
)


# ------------------------------------------------------------
# Regole eventi
# ------------------------------------------------------------

# L'app deve mostrare principalmente:
#   - oggi
#   - domani
#
# Il generatore quindi non pubblicherà un calendario enorme.
SHOW_TODAY = True
SHOW_TOMORROW = True


# ------------------------------------------------------------
# Regole canali
# ------------------------------------------------------------

# I canali vengono letti dal channels.txt dell'utente.
#
# Il generatore:
#   1. legge name
#   2. legge aliases
#   3. confronta i broadcaster trovati
#   4. restituisce gli ID dei canali corrispondenti
#
# Gli URL degli stream NON vengono modificati dal generatore.
MATCH_CHANNEL_ALIASES = True

# Preferenza per i canali italiani quando esistono
PREFER_ITALIAN_CHANNELS = True


# ------------------------------------------------------------
# Output JSON
# ------------------------------------------------------------

JSON_VERSION = 1

JSON_INDENT = 2


# ------------------------------------------------------------
# Controllo sicurezza
# ------------------------------------------------------------

def validate_configuration() -> None:
    """
    Verifica la configurazione minima necessaria.
    """

    if not CHANNELS_URL:
        raise RuntimeError(
            "CHANNELS_URL non configurato."
        )

    if not EVENTS_URL:
        raise RuntimeError(
            "EVENTS_URL non configurato."
        )

    if not LIVE_URL:
        raise RuntimeError(
            "LIVE_URL non configurato."
        )

    if not DROPBOX_ACCESS_TOKEN:
        raise RuntimeError(
            "Secret TVSPORTLIVE_DROPBOX_ACCESS_TOKEN "
            "non configurato."
        )
