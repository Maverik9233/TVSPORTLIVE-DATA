```python
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
# Fonti:
#   - ESPN per le competizioni normalmente disponibili
#   - SofaScore per la Serie C italiana
#
# NON crea eventi fittizi.
# NON gestisce LiveOnSat.
# NON gestisce i canali.
# ============================================================


@dataclass(frozen=True)
class SourceCompetition:
    key: str
    sport: str
    league: str
    name: str | None = None


@dataclass
class RawEvent:
    source: str
    source_event_id: str

    competition_key: str
    competition_name: str

    sport: str

    title: str
    start_time: str
    end_time: str | None

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
# DEFAULT DURATIONS
# ============================================================

DEFAULT_DURATIONS_MINUTES = {
    "FOOTBALL": 120,
    "BASKETBALL": 150,
    "TENNIS": 180,
    "FORMULA_1": 150,
    "MOTOGP": 120,
}


def default_duration_minutes(sport: str) -> int:
    return DEFAULT_DURATIONS_MINUTES.get(
        sport,
        120,
    )


# ============================================================
# COMPETITIONS
# ============================================================

SOCCER_COMPETITIONS = (
    SourceCompetition(
        key="serie_a",
        sport="FOOTBALL",
        league="ita.1",
        name="Serie A",
    ),
    SourceCompetition(
        key="serie_b",
        sport="FOOTBALL",
        league="ita.2",
        name="Serie B",
    ),
    SourceCompetition(
        key="serie_c",
        sport="FOOTBALL",
        league="ita.3",
        name="Serie C",
    ),
    SourceCompetition(
        key="coppa_italia",
        sport="FOOTBALL",
        league="ita.coppa_italia",
        name="Coppa Italia",
    ),
    SourceCompetition(
        key="premier_league",
        sport="FOOTBALL",
        league="eng.1",
        name="Premier League",
    ),
    SourceCompetition(
        key="la_liga",
        sport="FOOTBALL",
        league="esp.1",
        name="La Liga",
    ),
    SourceCompetition(
        key="bundesliga",
        sport="FOOTBALL",
        league="ger.1",
        name="Bundesliga",
    ),
    SourceCompetition(
        key="ligue_1",
        sport="FOOTBALL",
        league="fra.1",
        name="Ligue 1",
    ),
    SourceCompetition(
        key="primeira_liga",
        sport="FOOTBALL",
        league="por.1",
        name="Primeira Liga",
    ),
    SourceCompetition(
        key="eredivisie",
        sport="FOOTBALL",
        league="ned.1",
        name="Eredivisie",
    ),
    SourceCompetition(
        key="champions_league",
        sport="FOOTBALL",
        league="uefa.champions",
        name="Champions League",
    ),
    SourceCompetition(
        key="europa_league",
        sport="FOOTBALL",
        league="uefa.europa",
        name="Europa League",
    ),
    SourceCompetition(
        key="conference_league",
        sport="FOOTBALL",
        league="uefa.europa.conf",
        name="Conference League",
    ),
    SourceCompetition(
        key="fifa_world_cup",
        sport="FOOTBALL",
        league="fifa.world",
        name="FIFA World Cup",
    ),
    SourceCompetition(
        key="fifa_club_world_cup",
        sport="FOOTBALL",
        league="fifa.cwc",
        name="FIFA Club World Cup",
    ),
)


OTHER_COMPETITIONS = (
    SourceCompetition(
        key="formula_1",
        sport="FORMULA_1",
        league="f1",
        name="Formula 1",
    ),
    SourceCompetition(
        key="motogp",
        sport="MOTOGP",
        league="motogp",
        name="MotoGP",
    ),
    SourceCompetition(
        key="atp",
        sport="TENNIS",
        league="atp",
        name="ATP",
    ),
    SourceCompetition(
        key="wta",
        sport="TENNIS",
        league="wta",
        name="WTA",
    ),
    SourceCompetition(
        key="nba",
        sport="BASKETBALL",
        league="nba",
        name="NBA",
    ),
    SourceCompetition(
        key="euroleague",
        sport="BASKETBALL",
        league="euroleague",
        name="EuroLeague",
    ),
)


ALL_COMPETITIONS = (
    *SOCCER_COMPETITIONS,
    *OTHER_COMPETITIONS,
)


# ============================================================
# ESPN
# ============================================================

ESPN_BASE_URL = (
    "https://site.api.espn.com/apis/site/v2/sports"
)


def build_scoreboard_url(
    competition: SourceCompetition,
    date_value: str,
) -> str:
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
# SOFASCORE - SERIE C
# ============================================================

SOFASCORE_BASE_URL = (
    "https://www.sofascore.com/api/v1"
)

SOFASCORE_SERIE_C_TOURNAMENTS = {
    "serie_c_girone_a": 11445,
    "serie_c_girone_b": 11446,
    "serie_c_girone_c": 11447,
}


def build_sofascore_tournament_url(
    tournament_id: int,
    path: str,
    page: int = 0,
) -> str:
    return (
        f"{SOFASCORE_BASE_URL}/"
        f"unique-tournament/{tournament_id}/"
        f"{path}/{page}"
    )


def build_sofascore_seasons_url(
    tournament_id: int,
) -> str:
    return (
        f"{SOFASCORE_BASE_URL}/"
        f"unique-tournament/{tournament_id}/seasons"
    )


def build_sofascore_team_logo_url(
    team_id: int | str | None,
) -> str | None:
    if team_id is None:
        return None

    value = safe_string(team_id)

    if not value:
        return None

    return (
        "https://img.sofascore.com/api/v1/team/"
        f"{value}/image"
    )


def get_sofascore_current_season_id(
    tournament_id: int,
) -> int | None:
    try:
        data = fetch_json(
            build_sofascore_seasons_url(
                tournament_id
            )
        )

    except Exception as error:
        print(
            "[SOFASCORE] "
            f"Impossibile recuperare le stagioni "
            f"del torneo {tournament_id}: {error}"
        )
        return None

    seasons = data.get(
        "seasons",
        [],
    )

    if not isinstance(
        seasons,
        list,
    ):
        return None

    current_year = datetime.now(
        ZoneInfo(TIMEZONE)
    ).year

    candidates: list[dict] = []

    for season in seasons:
        if not isinstance(
            season,
            dict,
        ):
            continue

        season_id = safe_int(
            season.get("id")
        )

        if season_id is None:
            continue

        candidates.append(
            season
        )

    if not candidates:
        return None

    # Prima cerca una stagione che contenga l'anno corrente
    for season in candidates:
        name = (
            safe_string(
                season.get("name")
            )
            or ""
        )

        if str(current_year) in name:
            season_id = safe_int(
                season.get("id")
            )

            if season_id is not None:
                return season_id

    # Poi prova l'anno successivo, utile nella parte finale
    # della stagione corrente.
    for season in candidates:
        name = (
            safe_string(
                season.get("name")
            )
            or ""
        )

        if str(current_year + 1) in name:
            season_id = safe_int(
                season.get("id")
            )

            if season_id is not None:
                return season_id

    # Fallback: stagione con ID più alto.
    candidates.sort(
        key=lambda item: safe_int(
            item.get("id")
        )
        or 0,
        reverse=True,
    )

    return safe_int(
        candidates[0].get("id")
    )


def normalize_sofascore_status(
    event: dict,
) -> str:
    status = event.get(
        "status",
        {},
    )

    if not isinstance(
        status,
        dict,
    ):
        return "SCHEDULED"

    status_type = (
        safe_string(
            status.get("type")
        )
        or ""
    ).lower()

    status_code = (
        safe_string(
            status.get("code")
        )
        or ""
    ).lower()

    if status_type in {
        "canceled",
        "cancelled",
    }:
        return "CANCELLED"

    if status_type in {
        "postponed",
    }:
        return "POSTPONED"

    if status_type in {
        "finished",
    }:
        return "FINISHED"

    if status_type in {
        "inprogress",
        "in_progress",
    }:
        return "LIVE"

    if status_type in {
        "halftime",
    }:
        return "HALFTIME"

    if status_code in {
        "canceled",
        "cancelled",
    }:
        return "CANCELLED"

    if status_code in {
        "postponed",
    }:
        return "POSTPONED"

    if status_code in {
        "finished",
    }:
        return "FINISHED"

    if status_code in {
        "inprogress",
        "in_progress",
    }:
        return "LIVE"

    return "SCHEDULED"


def extract_sofascore_clock(
    event: dict,
) -> tuple[int | None, str | None]:
    status = event.get(
        "status",
        {},
    )

    if not isinstance(
        status,
        dict,
    ):
        return None, None

    period = (
        safe_string(
            status.get("period1")
        )
        or safe_string(
            status.get("period")
        )
    )

    time_value = event.get(
        "time",
        {},
    )

    if not isinstance(
        time_value,
        dict,
    ):
        return None, period

    current = safe_int(
        time_value.get(
            "current"
        )
    )

    if current is None:
        return None, period

    # SofaScore può esporre il tempo in secondi.
    # Per il calcio lo trasformiamo in minuti.
    minute = current // 60

    return minute, period


def extract_sofascore_team(
    team: dict | None,
) -> tuple[
    str | None,
    str | None,
    str | None,
    str | None,
]:
    if not isinstance(
        team,
        dict,
    ):
        return (
            None,
            None,
            None,
            None,
        )

    team_id = safe_string(
        team.get("id")
    )

    name = (
        safe_string(
            team.get("name")
        )
        or safe_string(
            team.get("shortName")
        )
    )

    short_name = (
        safe_string(
            team.get("shortName")
        )
        or safe_string(
            team.get("nameCode")
        )
    )

    logo = build_sofascore_team_logo_url(
        team_id
    )

    return (
        team_id,
        name,
        short_name,
        logo,
    )


def normalize_sofascore_event(
    event: dict,
    competition_key: str,
    competition_name: str,
) -> RawEvent | None:
    event_id = safe_string(
        event.get("id")
    )

    if not event_id:
        return None

    start_timestamp = safe_int(
        event.get("startTimestamp")
    )

    if start_timestamp is None:
        return None

    start_time = datetime.fromtimestamp(
        start_timestamp,
        tz=ZoneInfo("UTC"),
    ).isoformat().replace(
        "+00:00",
        "Z",
    )

    end_timestamp = safe_int(
        event.get("endTimestamp")
    )

    if end_timestamp is not None:
        end_time = datetime.fromtimestamp(
            end_timestamp,
            tz=ZoneInfo("UTC"),
        ).isoformat().replace(
            "+00:00",
            "Z",
        )
    else:
        end_time = (
            datetime.fromtimestamp(
                start_timestamp,
                tz=ZoneInfo("UTC"),
            )
            + timedelta(
                minutes=default_duration_minutes(
                    "FOOTBALL"
                )
            )
        ).isoformat().replace(
            "+00:00",
            "Z",
        )

    home_team = event.get(
        "homeTeam"
    )

    away_team = event.get(
        "awayTeam"
    )

    (
        home_id,
        home_name,
        home_short_name,
        home_logo,
    ) = extract_sofascore_team(
        home_team
    )

    (
        away_id,
        away_name,
        away_short_name,
        away_logo,
    ) = extract_sofascore_team(
        away_team
    )

    if not home_name and not away_name:
        return None

    title = safe_string(
        event.get("slug")
    )

    if home_name and away_name:
        title = (
            f"{home_name} - {away_name}"
        )

    if not title:
        title = competition_name

    home_score = None
    away_score = None

    home_score_data = event.get(
        "homeScore"
    )

    away_score_data = event.get(
        "awayScore"
    )

    if isinstance(
        home_score_data,
        dict,
    ):
        home_score = (
            safe_int(
                home_score_data.get(
                    "current"
                )
            )
        )
        if home_score is None:
            home_score = safe_int(
                home_score_data.get(
                    "normaltime"
                )
            )
    else:
        home_score = safe_int(
            home_score_data
        )

    if isinstance(
        away_score_data,
        dict,
    ):
        away_score = (
            safe_int(
                away_score_data.get(
                    "current"
                )
            )
        )
        if away_score is None:
            away_score = safe_int(
                away_score_data.get(
                    "normaltime"
                )
            )
    else:
        away_score = safe_int(
            away_score_data
        )

    minute, period = extract_sofascore_clock(
        event
    )

    return RawEvent(
        source="SOFASCORE",
        source_event_id=event_id,
        competition_key=competition_key,
        competition_name=competition_name,
        sport="FOOTBALL",
        title=title,
        start_time=start_time,
        end_time=end_time,
        status=normalize_sofascore_status(
            event
        ),
        home_team_id=(
            f"sofascore_{home_id}"
            if home_id
            else None
        ),
        home_team_name=home_name,
        home_team_short_name=home_short_name,
        home_team_logo=home_logo,
        away_team_id=(
            f"sofascore_{away_id}"
            if away_id
            else None
        ),
        away_team_name=away_name,
        away_team_short_name=away_short_name,
        away_team_logo=away_logo,
        home_score=home_score,
        away_score=away_score,
        period=period,
        minute=minute,
        country="IT",
    )


def get_sofascore_event_pages(
    tournament_id: int,
    season_id: int,
    path: str,
) -> list[dict]:
    events: list[dict] = []

    for page in range(0, 2):
        url = (
            f"{SOFASCORE_BASE_URL}/"
            f"unique-tournament/{tournament_id}/"
            f"season/{season_id}/"
            f"events/{path}/{page}"
        )

        try:
            data = fetch_json(
                url
            )

        except Exception as error:
            print(
                "[SOFASCORE] "
                f"Torneo {tournament_id}, "
                f"{path}/{page} non disponibile: "
                f"{error}"
            )
            continue

        page_events = data.get(
            "events",
            [],
        )

        if not isinstance(
            page_events,
            list,
        ):
            continue

        events.extend(
            event
            for event in page_events
            if isinstance(event, dict)
        )

    return events


def fetch_serie_c_events_for_date_range(
    dates: list[str],
) -> list[RawEvent]:
    wanted_dates = set(
        dates
    )

    result: list[RawEvent] = []

    for competition_key, tournament_id in (
        SOFASCORE_SERIE_C_TOURNAMENTS.items()
    ):
        season_id = get_sofascore_current_season_id(
            tournament_id
        )

        if season_id is None:
            print(
                "[SOFASCORE] "
                f"{competition_key}: "
                "stagione non trovata."
            )
            continue

        raw_events: list[dict] = []

        raw_events.extend(
            get_sofascore_event_pages(
                tournament_id=tournament_id,
                season_id=season_id,
                path="next",
            )
        )

        raw_events.extend(
            get_sofascore_event_pages(
                tournament_id=tournament_id,
                season_id=season_id,
                path="last",
            )
        )

        seen_ids: set[str] = set()

        for raw_event in raw_events:
            event_id = safe_string(
                raw_event.get("id")
            )

            if not event_id:
                continue

            if event_id in seen_ids:
                continue

            seen_ids.add(
                event_id
            )

            normalized = normalize_sofascore_event(
                event=raw_event,
                competition_key="serie_c",
                competition_name="Serie C",
            )

            if normalized is None:
                continue

            local_date = (
                datetime.fromisoformat(
                    normalized.start_time.replace(
                        "Z",
                        "+00:00",
                    )
                )
                .astimezone(
                    ZoneInfo(TIMEZONE)
                )
                .strftime("%Y%m%d")
            )

            if local_date not in wanted_dates:
                continue

            result.append(
                normalized
            )

        print(
            "[SOFASCORE] "
            f"{competition_key}: "
            f"{sum(1 for event in result if event.competition_key == 'serie_c')} "
            "eventi Serie C trovati cumulativamente."
        )

    return result


# ============================================================
# DATE
# ============================================================

def get_requested_dates() -> list[str]:
    timezone = ZoneInfo(
        TIMEZONE
    )

    now = datetime.now(
        timezone
    )

    dates: list[str] = []

    if SHOW_TODAY:
        dates.append(
            now.strftime("%Y%m%d")
        )

    if SHOW_TOMORROW:
        tomorrow = (
            now + timedelta(
                days=1
            )
        )

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
    request = urllib.request.Request(
        url=url,
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
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

    if not isinstance(
        data,
        dict,
    ):
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

    text = str(
        value
    ).strip()

    if not text:
        return None

    return text


def safe_int(
    value,
) -> int | None:
    if value is None:
        return None

    try:
        return int(
            value
        )

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
        if not isinstance(
            current,
            dict,
        ):
            return None

        current = current.get(
            key
        )

    return current


def extract_logo(
    team: dict,
) -> str | None:
    logos = team.get(
        "logos",
        [],
    )

    if isinstance(
        logos,
        list,
    ):
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
# ESPN STATUS
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

    if state in {
        "canceled",
        "cancelled",
    }:
        return "CANCELLED"

    if state == "postponed":
        return "POSTPONED"

    if completed:
        return "FINISHED"

    return "SCHEDULED"


# ============================================================
# ESPN MINUTE / PERIOD
# ============================================================

def extract_clock(
    event: dict,
) -> tuple[int | None, str | None]:
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
            parts = display_clock.split(
                ":"
            )

            if parts:
                minute = int(
                    float(
                        parts[0]
                    )
                )

        except (
            ValueError,
            TypeError,
        ):
            minute = None

    return minute, period


# ============================================================
# ESPN TEAMS
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
# ESPN EVENT NORMALIZATION
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
                competition.name
                or competition.key
            )

    status = normalize_status(
        event
    )

    minute, period = extract_clock(
        event
    )

    end_time = safe_string(
        event.get(
            "endDate"
        )
    )

    if not end_time:
        try:
            start_dt = datetime.fromisoformat(
                start_time.replace(
                    "Z",
                    "+00:00",
                )
            )

            end_time = (
                start_dt
                + timedelta(
                    minutes=default_duration_minutes(
                        competition.sport
                    )
                )
            ).isoformat().replace(
                "+00:00",
                "Z",
            )

        except ValueError:
            end_time = None

    return RawEvent(
        source="ESPN",
        source_event_id=event_id,
        competition_key=competition.key,
        competition_name=(
            competition.name
            or competition.key
        ),
        sport=competition.sport,
        title=title,
        start_time=start_time,
        end_time=end_time,
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
        country=(
            "IT"
            if competition.key
            in {
                "serie_a",
                "serie_b",
                "serie_c",
                "coppa_italia",
            }
            else None
        ),
    )


# ============================================================
# ESPN SINGLE COMPETITION
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
    dates = get_requested_dates()

    all_events: list[RawEvent] = []

    for competition in ALL_COMPETITIONS:

        # La Serie C viene recuperata da SofaScore.
        if competition.key == "serie_c":
            continue

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

    # Serie C da SofaScore.
    try:
        serie_c_events = (
            fetch_serie_c_events_for_date_range(
                dates=dates
            )
        )

        all_events.extend(
            serie_c_events
        )

        print(
            "[SPORTS] Serie C: "
            f"{len(serie_c_events)} eventi"
        )

    except Exception as error:
        print(
            "[SPORTS] Serie C non disponibile: "
            f"{error}"
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
    events = fetch_all_events()

    print(
        "[SPORTS] "
        f"Totale eventi reali recuperati: "
        f"{len(events)}"
    )

    return events
```
