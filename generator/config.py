from __future__ import annotations

APP_NAME = "TVSPORTLIVE"

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
