from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from config import (
    REQUEST_TIMEOUT_SECONDS,
    SHOW_TODAY,
    SHOW_TOMORROW,
    TIMEZONE,
    USER_AGENT,
)


# ============================================================
# TVSPORTLIVE - SPORTS SOURCES
#
# Recupera eventi sportivi REALI dalle fonti pubbliche.
#
# Questo modulo:
#
#   - NON crea eventi fittizi
#   - NON gestisce Dropbox
#   - NON gestisce LiveOnSat
#   - NON gestisce i canali
#
# Il suo unico compito è recuperare gli eventi sportivi
# disponibili per oggi e domani.
# ============================================================


@dataclass(frozen=True)
class SourceCompetition:
    key: str
    sport: str
    league: str


@dataclass
class RawEvent:
    source: str
    source_event_id: str

    competition_key: str
    competition_name: str

    sport: str

    title: str
    start_time: str

    status: str

    home_team_id: str | None = None
    home_team_name: str | None = None
    home_team_short_name: str | None = None
    home_team_logo: str | None = None

    away_team_id: str | None = None
    away_team_name: str | None = None
    away_team_short_name: str | None = None
    away_team_logo: str | None = None

    home_score: int | None = None
    away_score: int | None = None

    period: str | None = None
    minute: int | None = None

    country: str | None = None


# ============================================================
# COMPETITIONS
# ============================================================

SOCCER_COMPETITIONS = (
    SourceCompetition(
        key="serie_a",
        sport="FOOTBALL",
        league="ita.1",
    ),
    SourceCompetition(
        key="serie_b",
        sport="FOOTBALL",
        league="ita.2",
    ),
    SourceCompetition(
        key="serie_c",
        sport="FOOTBALL",
        league="ita.3",
    ),
    SourceCompetition(
        key="premier_league",
        sport="FOOTBALL",
        league="eng.1",
    ),
    SourceCompetition(
        key="la_liga",
        sport="FOOTBALL",
        league="esp.1",
    ),
    SourceCompetition(
        key="bundesliga",
        sport="FOOTBALL",
        league="ger.1",
    ),
    SourceCompetition(
        key="ligue_1",
        sport="FOOTBALL",
        league="fra.1",
    ),
    SourceCompetition(
        key="primeira_liga",
        sport="FOOTBALL",
        league="por.1",
    ),
    SourceCompetition(
        key="eredivisie",
        sport="FOOTBALL",
        league="ned.1",
    ),
    SourceCompetition(
        key="champions_league",
        sport="FOOTBALL",
        league="uefa.champions",
    ),
    SourceCompetition(
        key="europa_league",
        sport="FOOTBALL",
        league="uefa.europa",
    ),
    SourceCompetition(
        key="conference_league",
        sport="FOOTBALL",
        league="uefa.europa.conf",
    ),
    SourceCompetition(
        key="fifa_world_cup",
        sport="FOOTBALL",
        league="fifa.world",
    ),
    SourceCompetition(
        key="fifa_club_world_cup",
        sport="FOOTBALL",
        league="fifa.cwc",
    ),
)


OTHER_COMPETITIONS = (
    SourceCompetition(
        key="formula_1",
        sport="FORMULA_1",
        league="f1",
    ),
    SourceCompetition(
        key="motogp",
        sport="MOTOGP",
        league="motogp",
    ),
    SourceCompetition(
        key="atp",
        sport="TENNIS",
        league="atp",
    ),
    SourceCompetition(
        key="wta",
        sport="TENNIS",
        league="wta",
    ),
    SourceCompetition(
        key="nba",
        sport="BASKETBALL",
        league="nba",
    ),
    SourceCompetition(
        key="euroleague",
        sport="BASKETBALL",
        league="euroleague",
    ),
)


ALL_COMPETITIONS = (
    *SOCCER_COMPETITIONS,
    *OTHER_COMPETITIONS,
)


# ============================================================
# ESPN URL
# ============================================================

ESPN_BASE_URL = (
    "https://site.api.espn.com/apis/site/v2/sports"
)


def build_scoreboard_url(
    competition: SourceCompetition,
    date_value: str,
) -> str:
    """
    Costruisce l'URL ESPN scoreboard.

    date_value:
        YYYYMMDD
    """

    encoded_date = urllib.parse.quote(
        date_value,
        safe="",
    )

    return (
        f"{ESPN_BASE_URL}/"
        f"{get_espn_sport_path(competition.sport)}/"
        f"{competition.league}/"
        f"scoreboard"
        f"?dates={encoded_date}"
    )


def get_espn_sport_path(
    sport: str,
) -> str:
    """
    Converte il nostro SportType nel percorso ESPN.
    """

    mapping = {
        "FOOTBALL": "soccer",
        "FORMULA_1": "racing",
        "MOTOGP": "racing",
        "TENNIS": "tennis",
        "BASKETBALL": "basketball",
    }

    try:
        return mapping[sport]
    except KeyError:
        raise ValueError(
            f"Sport non supportato: {sport}"
        )


# ============================================================
# DATE
# ============================================================

def get_requested_dates() -> list[str]:
    """
    Restituisce le date che devono essere recuperate.

    Le date sono nel fuso orario Europe/Rome.
    """

    timezone = ZoneInfo(TIMEZONE)

    now = datetime.now(timezone)

    dates: list[str] = []

    if SHOW_TODAY:
        dates.append(
            now.strftime("%Y%m%d")
        )

    if SHOW_TOMORROW:
        tomorrow = now + timedelta(days=1)

        dates.append(
            tomorrow.strftime("%Y%m%d")
        )

    return dates


# ============================================================
# HTTP
# ============================================================

def fetch_json(
    url: str,
) -> dict:
    """
    Scarica JSON dalla sorgente.

    Non utilizziamo un browser User-Agent falso:
    alcune infrastrutture ESPN possono rifiutare richieste
    che sembrano provenire da browser contraffatti.
    """

    request = urllib.request.Request(
        url=url,
        headers={
            "Accept": "application/json",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:

            status_code = response.status

            if status_code < 200 or status_code >= 300:
                raise RuntimeError(
                    f"HTTP {status_code} da {url}"
                )

            raw_data = response.read()

    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"HTTP {error.code} da {url}"
        ) from error

    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Errore di rete durante il recupero "
            f"di {url}: {error.reason}"
        ) from error

    try:
        decoded = raw_data.decode(
            "utf-8"
        )

        data = json.loads(
            decoded
        )

    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:

        raise RuntimeError(
            f"Risposta non JSON ricevuta da {url}"
        ) from error

    if not isinstance(data, dict):
        raise RuntimeError(
            f"Risposta JSON non valida da {url}"
        )

    return data


# ============================================================
# GENERIC HELPERS
# ============================================================

def safe_string(
    value,
) -> str | None:
    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    return text


def safe_int(
    value,
) -> int | None:
    if value is None:
        return None

    try:
        return int(value)
    except (
        TypeError,
        ValueError,
    ):
        return None


def get_nested(
    data: dict,
    *keys: str,
):
    current = data

    for key in keys:
        if not isinstance(current, dict):
            return None

        current = current.get(key)

    return current


def extract_logo(
    team: dict,
) -> str | None:

    logos = team.get(
        "logos",
        [],
    )

    if isinstance(logos, list):
        for logo in logos:
            if not isinstance(
                logo,
                dict,
            ):
                continue

            href = safe_string(
                logo.get("href")
            )

            if href:
                return href

    logo = team.get(
        "logo"
    )

    return safe_string(
        logo
    )


# ============================================================
# STATUS
# ============================================================

def normalize_status(
    event: dict,
) -> str:

    status_type = get_nested(
        event,
        "status",
        "type",
    )

    if not isinstance(
        status_type,
        dict,
    ):
        return "SCHEDULED"

    state = (
        safe_string(
            status_type.get(
                "state"
            )
        )
        or ""
    ).lower()

    completed = bool(
        status_type.get(
            "completed",
            False,
        )
    )

    detail = (
        safe_string(
            status_type.get(
                "detail"
            )
        )
        or ""
    ).lower()

    if state == "in":
        if (
            "halftime" in detail
            or "half" in detail
        ):
            return "HALFTIME"

        return "LIVE"

    if state == "post":
        return "FINISHED"

    if state == "canceled":
        return "CANCELLED"

    if state == "postponed":
        return "POSTPONED"

    if completed:
        return "FINISHED"

    return "SCHEDULED"


# ============================================================
# MINUTE / PERIOD
# ============================================================

def extract_clock(
    event: dict,
) -> tuple[int | None, str | None]:

    competitions = event.get(
        "competitions",
        [],
    )

    if not isinstance(
        competitions,
        list,
    ):
        return None, None

    if not competitions:
        return None, None

    competition = competitions[0]

    if not isinstance(
        competition,
        dict,
    ):
        return None, None

    status = event.get(
        "status",
        {},
    )

    if not isinstance(
        status,
        dict,
    ):
        return None, None

    display_clock = safe_string(
        status.get(
            "displayClock"
        )
    )

    period = safe_string(
        status.get(
            "period"
        )
    )

    minute = None

    if display_clock:
        try:
            parts = display_clock.split(":")

            if parts:
                minute = int(
                    float(parts[0])
                )

        except (
            ValueError,
            TypeError,
        ):
            minute = None

    return minute, period


# ============================================================
# TEAMS
# ============================================================

def extract_competitors(
    event: dict,
) -> tuple[
    dict | None,
    dict | None,
]:

    competitions = event.get(
        "competitions",
        [],
    )

    if not isinstance(
        competitions,
        list,
    ):
        return None, None

    if not competitions:
        return None, None

    competition = competitions[0]

    if not isinstance(
        competition,
        dict,
    ):
        return None, None

    competitors = competition.get(
        "competitors",
        [],
    )

    if not isinstance(
        competitors,
        list,
    ):
        return None, None

    home = None
    away = None

    for competitor in competitors:

        if not isinstance(
            competitor,
            dict,
        ):
            continue

        home_away = safe_string(
            competitor.get(
                "homeAway"
            )
        )

        if home_away == "home":
            home = competitor

        elif home_away == "away":
            away = competitor

    return home, away


def extract_team(
    competitor: dict | None,
) -> tuple[
    str | None,
    str | None,
    str | None,
    str | None,
    int | None,
]:

    if not isinstance(
        competitor,
        dict,
    ):
        return (
            None,
            None,
            None,
            None,
            None,
        )

    team = competitor.get(
        "team",
        {},
    )

    if not isinstance(
        team,
        dict,
    ):
        team = {}

    team_id = safe_string(
        team.get(
            "id"
        )
    )

    name = (
        safe_string(
            team.get(
                "displayName"
            )
        )
        or safe_string(
            team.get(
                "name"
            )
        )
    )

    short_name = (
        safe_string(
            team.get(
                "shortDisplayName"
            )
        )
        or safe_string(
            team.get(
                "abbreviation"
            )
        )
    )

    logo = extract_logo(
        team
    )

    score = safe_int(
        competitor.get(
            "score"
        )
    )

    return (
        team_id,
        name,
        short_name,
        logo,
        score,
    )


# ============================================================
# EVENT NORMALIZATION
# ============================================================

def normalize_event(
    event: dict,
    competition: SourceCompetition,
) -> RawEvent | None:

    event_id = safe_string(
        event.get(
            "id"
        )
    )

    if not event_id:
        return None

    start_time = safe_string(
        event.get(
            "date"
        )
    )

    if not start_time:
        return None

    home, away = extract_competitors(
        event
    )

    (
        home_id,
        home_name,
        home_short_name,
        home_logo,
        home_score,
    ) = extract_team(
        home
    )

    (
        away_id,
        away_name,
        away_short_name,
        away_logo,
        away_score,
    ) = extract_team(
        away
    )

    title = safe_string(
        event.get(
            "name"
        )
    )

    if not title:

        if (
            home_name
            and away_name
        ):
            title = (
                f"{home_name} - "
                f"{away_name}"
            )

        else:
            title = (
                competition.key
            )

    status = normalize_status(
        event
    )

    minute, period = extract_clock(
        event
    )

    return RawEvent(
        source="ESPN",

        source_event_id=event_id,

        competition_key=competition.key,

        competition_name=(
            competition.key
        ),

        sport=competition.sport,

        title=title,

        start_time=start_time,

        status=status,

        home_team_id=home_id,
        home_team_name=home_name,
        home_team_short_name=home_short_name,
        home_team_logo=home_logo,

        away_team_id=away_id,
        away_team_name=away_name,
        away_team_short_name=away_short_name,
        away_team_logo=away_logo,

        home_score=home_score,
        away_score=away_score,

        period=period,
        minute=minute,
    )


# ============================================================
# SINGLE COMPETITION
# ============================================================

def fetch_competition_date(
    competition: SourceCompetition,
    date_value: str,
) -> list[RawEvent]:

    url = build_scoreboard_url(
        competition=competition,
        date_value=date_value,
    )

    data = fetch_json(
        url
    )

    events = data.get(
        "events",
        [],
    )

    if not isinstance(
        events,
        list,
    ):
        return []

    normalized: list[RawEvent] = []

    for event in events:

        if not isinstance(
            event,
            dict,
        ):
            continue

        normalized_event = normalize_event(
            event=event,
            competition=competition,
        )

        if normalized_event is not None:
            normalized.append(
                normalized_event
            )

    return normalized


# ============================================================
# ALL COMPETITIONS
# ============================================================

def fetch_all_events() -> list[RawEvent]:
    """
    Recupera tutti gli eventi disponibili
    per oggi e domani.

    Se una singola competizione non è disponibile
    sulla sorgente, quella competizione viene saltata.

    Non vengono mai creati eventi sostitutivi.
    """

    dates = get_requested_dates()

    all_events: list[RawEvent] = []

    for competition in ALL_COMPETITIONS:

        for date_value in dates:

            try:
                events = fetch_competition_date(
                    competition=competition,
                    date_value=date_value,
                )

            except Exception as error:
                print(
                    "[SPORTS] "
                    f"{competition.key} "
                    f"{date_value} "
                    f"non disponibile: "
                    f"{error}"
                )

                continue

            all_events.extend(
                events
            )

            print(
                "[SPORTS] "
                f"{competition.key} "
                f"{date_value}: "
                f"{len(events)} eventi"
            )

    return deduplicate_events(
        all_events
    )


# ============================================================
# DEDUPLICATION
# ============================================================

def deduplicate_events(
    events: list[RawEvent],
) -> list[RawEvent]:

    unique: dict[
        tuple[str, str],
        RawEvent,
    ] = {}

    for event in events:

        key = (
            event.source,
            event.source_event_id,
        )

        if key not in unique:
            unique[key] = event

    result = list(
        unique.values()
    )

    result.sort(
        key=lambda item: (
            item.start_time,
            item.competition_key,
            item.title,
        )
    )

    return result


# ============================================================
# PUBLIC ENTRY POINT
# ============================================================

def get_real_events() -> list[RawEvent]:
    """
    Entry point utilizzato dal generatore principale.
    """

    events = fetch_all_events()

    print(
        "[SPORTS] "
        f"Totale eventi reali recuperati: "
        f"{len(events)}"
    )

    return events
