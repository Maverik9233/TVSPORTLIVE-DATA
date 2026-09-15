from __future__ import annotations

APP_NAME = "TVSPORTLIVE"

CHANNELS_URL = (
    "https://github.com/Maverik9233/TVSPORTLIVE-DATA/"
    "raw/refs/heads/main/data/channels.txt"
)

EVENTS_URL = (
    "https://github.com/Maverik9233/TVSPORTLIVE-DATA/"
    "raw/refs/heads/main/data/events.txt"
)

LIVE_URL = (
    "https://github.com/Maverik9233/TVSPORTLIVE-DATA/"
    "raw/refs/heads/main/data/live.txt"
)

TIMEZONE = "Europe/Rome"

EVENTS_DAYS_AHEAD = 1

REQUEST_TIMEOUT_SECONDS = 30

USER_AGENT = (
    "TVSPORTLIVE-DataGenerator/1.0 "
    "(automated sports data updater)"
)

SUPPORTED_SPORTS = (
    "FOOTBALL",
    "FORMULA_1",
    "MOTOGP",
    "TENNIS",
    "BASKETBALL",
)

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

SHOW_TODAY = True

SHOW_TOMORROW = True

MATCH_CHANNEL_ALIASES = True

PREFER_ITALIAN_CHANNELS = True

JSON_VERSION = 1

JSON_INDENT = 2


def validate_configuration() -> None:
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
