from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

try:
    from serie_c_source import fetch_serie_c_events
except ImportError:
    def fetch_serie_c_events():
        return []

try:
    from diretta_serie_c_source import fetch_diretta_serie_c_events
except ImportError:
    def fetch_diretta_serie_c_events():
        return []

try:
    from diretta_tennis_source import fetch_diretta_tennis_events
except ImportError:
    def fetch_diretta_tennis_events():
        print("[TENNIS] diretta_tennis_source.py mancante — skip")
        return []

try:
    from tennis_cup_source import fetch_tennis_cup_events
except ImportError:
    def fetch_tennis_cup_events():
        return []

try:
    from motogp_source import fetch_motogp_events
except ImportError:
    def fetch_motogp_events():
        return []

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
# - ESPN per le competizioni normalmente disponibili
# - Fonte ufficiale Lega Serie C per la Serie C
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
    goals: list | None = None
    cards: list | None = None
    broadcasts: list | None = None


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
        key="eerste_divisie",
        sport="FOOTBALL",
        league="ned.2",
        name="Eerste Divisie",
    ),
    SourceCompetition(
        key="championship",
        sport="FOOTBALL",
        league="eng.2",
        name="Championship",
    ),
    SourceCompetition(
        key="la_liga_2",
        sport="FOOTBALL",
        league="esp.2",
        name="La Liga 2",
    ),
    SourceCompetition(
        key="bundesliga_2",
        sport="FOOTBALL",
        league="ger.2",
        name="2. Bundesliga",
    ),
    SourceCompetition(
        key="liga_profesional",
        sport="FOOTBALL",
        league="arg.1",
        name="Liga Profesional",
    ),
    SourceCompetition(
        key="brasileirao",
        sport="FOOTBALL",
        league="bra.1",
        name="Brasileirão",
    ),
    SourceCompetition(
        key="mls",
        sport="FOOTBALL",
        league="usa.1",
        name="MLS",
    ),
    SourceCompetition(
        key="serie_a_women",
        sport="FOOTBALL",
        league="ita.w.1",
        name="Serie A Femminile",
    ),
    SourceCompetition(
        key="wsl",
        sport="FOOTBALL",
        league="eng.w.1",
        name="Women's Super League",
    ),
    SourceCompetition(
        key="liga_f",
        sport="FOOTBALL",
        league="esp.w.1",
        name="Liga F",
    ),
    SourceCompetition(
        key="frauen_bundesliga",
        sport="FOOTBALL",
        league="ger.w.1",
        name="Frauen-Bundesliga",
    ),
    SourceCompetition(
        key="premiere_ligue_f",
        sport="FOOTBALL",
        league="fra.w.1",
        name="Première Ligue",
    ),
    SourceCompetition(
        key="nwsl",
        sport="FOOTBALL",
        league="usa.nwsl",
        name="NWSL",
    ),
    SourceCompetition(
        key="uwcl",
        sport="FOOTBALL",
        league="uefa.wchampions",
        name="UWCL",
    ),

    # --- Europa est / Balcani / Mediterraneo / Asia ---
    SourceCompetition(
        key="super_lig",
        sport="FOOTBALL",
        league="tur.1",
        name="Süper Lig",
    ),
    SourceCompetition(
        key="turkiye_1_lig",
        sport="FOOTBALL",
        league="tur.2",
        name="1. Lig Turchia",
    ),
    SourceCompetition(
        key="ekstraklasa",
        sport="FOOTBALL",
        league="pol.1",
        name="Ekstraklasa",
    ),
    SourceCompetition(
        key="polska_1_liga",
        sport="FOOTBALL",
        league="pol.2",
        name="I Liga Polonia",
    ),
    SourceCompetition(
        key="kategoria_superiore",
        sport="FOOTBALL",
        league="alb.1",
        name="Kategoria Superiore",
    ),
    SourceCompetition(
        key="super_league_ch",
        sport="FOOTBALL",
        league="sui.1",
        name="Super League Svizzera",
    ),
    SourceCompetition(
        key="challenge_league_ch",
        sport="FOOTBALL",
        league="sui.2",
        name="Challenge League",
    ),
    SourceCompetition(
        key="hnl",
        sport="FOOTBALL",
        league="cro.1",
        name="HNL Croazia",
    ),
    SourceCompetition(
        key="jupiler_pro",
        sport="FOOTBALL",
        league="bel.1",
        name="Pro League Belgio",
    ),
    SourceCompetition(
        key="challenger_pro",
        sport="FOOTBALL",
        league="bel.2",
        name="Challenger Pro League",
    ),
    SourceCompetition(
        key="cyprus_1",
        sport="FOOTBALL",
        league="cyp.1",
        name="First Division Cipro",
    ),
    SourceCompetition(
        key="malta_premier",
        sport="FOOTBALL",
        league="mlt.1",
        name="Premier League Malta",
    ),
    SourceCompetition(
        key="russian_premier",
        sport="FOOTBALL",
        league="rus.1",
        name="Premier Liga Russia",
    ),
    SourceCompetition(
        key="bulgaria_first",
        sport="FOOTBALL",
        league="bul.1",
        name="efbet Liga",
    ),
    SourceCompetition(
        key="chinese_super_league",
        sport="FOOTBALL",
        league="chn.1",
        name="Chinese Super League",
    ),
    SourceCompetition(
        key="saudi_pro_league",
        sport="FOOTBALL",
        league="ksa.1",
        name="Saudi Pro League",
    ),
    SourceCompetition(
        key="scottish_premiership",
        sport="FOOTBALL",
        league="sco.1",
        name="Scottish Premiership",
    ),
    SourceCompetition(
        key="scottish_championship",
        sport="FOOTBALL",
        league="sco.2",
        name="Scottish Championship",
    ),
    # Sudamerica extra
    SourceCompetition(
        key="liga_1_peru",
        sport="FOOTBALL",
        league="per.1",
        name="Liga 1 Perú",
    ),
    SourceCompetition(
        key="primera_chile",
        sport="FOOTBALL",
        league="chi.1",
        name="Primera División Chile",
    ),
    SourceCompetition(
        key="liga_betplay",
        sport="FOOTBALL",
        league="col.1",
        name="Liga BetPlay",
    ),
    SourceCompetition(
        key="liga_uruguaya",
        sport="FOOTBALL",
        league="uru.1",
        name="Liga Uruguay",
    ),


    SourceCompetition(
        key="liga_mx",
        sport="FOOTBALL",
        league="mex.1",
        name="Liga MX",
    ),
    SourceCompetition(
        key="copa_libertadores",
        sport="FOOTBALL",
        league="conmebol.libertadores",
        name="Copa Libertadores",
    ),
    SourceCompetition(
        key="copa_sudamericana",
        sport="FOOTBALL",
        league="conmebol.sudamericana",
        name="Copa Sudamericana",
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

    SourceCompetition(
        key="uefa_nations_league",
        sport="FOOTBALL",
        league="uefa.nations",
        name="UEFA Nations League",
    ),
    SourceCompetition(
        key="fifa_friendly",
        sport="FOOTBALL",
        league="fifa.friendly",
        name="Amichevoli",
    ),
    SourceCompetition(
        key="fifa_friendly_u21",
        sport="FOOTBALL",
        league="fifa.friendly_u21",
        name="Amichevoli U21",
    ),
    SourceCompetition(
        key="fifa_friendly_u20",
        sport="FOOTBALL",
        league="fifa.u20.friendly",
        name="Amichevoli U20",
    ),
    SourceCompetition(
        key="uefa_u21",
        sport="FOOTBALL",
        league="uefa.euro_u21",
        name="Europeo Under 21",
    ),
    SourceCompetition(
        key="uefa_u21_qual",
        sport="FOOTBALL",
        league="uefa.euro_u21_qual",
        name="Qual. Europeo U21",
    ),
    SourceCompetition(
        key="uefa_u19",
        sport="FOOTBALL",
        league="uefa.euro.u19",
        name="Europeo Under 19",
    ),
    SourceCompetition(
        key="fifa_u20_world",
        sport="FOOTBALL",
        league="fifa.world.u20",
        name="Mondiale Under 20",
    ),
    SourceCompetition(
        key="fifa_u17_world",
        sport="FOOTBALL",
        league="fifa.world.u17",
        name="Mondiale Under 17",
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
    SourceCompetition(
        key="wnba",
        sport="BASKETBALL",
        league="wnba",
        name="WNBA",
    ),
    SourceCompetition(
        key="nbl",
        sport="BASKETBALL",
        league="nbl",
        name="NBL",
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
#
# Le funzioni rimangono disponibili per compatibilità,
# ma la Serie C NON viene più utilizzata da fetch_all_events().
#
# La fonte attiva della Serie C è serie_c_source.py,
# che recupera il calendario dalla fonte ufficiale.
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

    candidates.sort(
        key=lambda item: safe_int(
            item.get("id")
        ) or 0,
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

    if status_type == "postponed":
        return "POSTPONED"

    if status_type == "finished":
        return "FINISHED"

    if status_type in {
        "inprogress",
        "in_progress",
    }:
        return "LIVE"

    if status_type == "halftime":
        return "HALFTIME"

    if status_code in {
        "canceled",
        "cancelled",
    }:
        return "CANCELLED"

    if status_code == "postponed":
        return "POSTPONED"

    if status_code == "finished":
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
        time_value.get("current")
    )

    if current is None:
        return None, period

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
        home_score = safe_int(
            home_score_data.get(
                "current"
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
        away_score = safe_int(
            away_score_data.get(
                "current"
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
            if isinstance(
                event,
                dict,
            )
        )

    return events


def fetch_serie_c_events_for_date_range(
    dates: list[str],
) -> list[RawEvent]:
    """
    Compatibilità con il vecchio percorso SofaScore.

    La Serie C non viene più utilizzata da
    fetch_all_events(), quindi questa funzione non viene
    chiamata nel normale workflow.
    """

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
# SERIE C - FONTE UFFICIALE
# ============================================================


def convert_serie_c_event(
    event,
) -> RawEvent:
    """
    Converte un SerieCEvent proveniente da
    serie_c_source.py nel formato comune RawEvent.
    """
    minute = None
    period = None
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Europe/Rome"))
        start = event.start_time
        if start.tzinfo is None:
            start = start.replace(tzinfo=ZoneInfo("Europe/Rome"))
        if str(event.status).upper() == "LIVE":
            elapsed = int((now - start).total_seconds() // 60)
            if elapsed < 0:
                elapsed = 0
            # stima grezza 1° / 2° tempo
            if elapsed <= 45:
                minute = min(elapsed, 45)
                period = "1H"
            elif elapsed <= 60:
                minute = 45
                period = "HT"
            else:
                minute = min(elapsed - 15, 90)  # ~intervallo 15 min
                period = "2H"
        elif str(event.status).upper() == "FINISHED":
            period = "FT"
    except Exception:
        minute = None
        period = None

    return RawEvent(
        source="SERIEC",
        source_event_id=event.source_event_id,
        competition_key=event.competition_key,
        competition_name=event.competition_name,
        sport=event.sport,
        title=event.title,
        start_time=event.start_time.isoformat(),
        end_time=event.end_time.isoformat(),
        status=event.status,
        home_team_id=event.home_team_id,
        home_team_name=event.home_team_name,
        home_team_short_name=event.home_team_short_name,
        home_team_logo=event.home_logo_url,
        away_team_id=event.away_team_id,
        away_team_name=event.away_team_name,
        away_team_short_name=event.away_team_short_name,
        away_team_logo=event.away_logo_url,
        home_score=event.home_score,
        away_score=event.away_score,
        period=period,
        minute=minute,
        country=event.country,
    )


def fetch_official_serie_c_events() -> list[RawEvent]:
    """
    Recupera la Serie C esclusivamente dalla fonte
    ufficiale implementata in serie_c_source.py.
    """

    events = []
    try:
        events = list(fetch_serie_c_events())
    except Exception as error:
        print(
            "[SPORTS] "
            f"Serie C - errore fonte ufficiale: "
            f"{error}"
        )
        events = []

    # Fallback / integrazione diretta.it (oggi spesso più aggiornata)
    try:
        diretta_events = list(fetch_diretta_serie_c_events())
    except Exception as error:
        print(f"[SPORTS] Serie C - errore diretta.it: {error}")
        diretta_events = []

    if not events and diretta_events:
        print(f"[SPORTS] Serie C - uso diretta.it: {len(diretta_events)} eventi")
        events = diretta_events
    elif diretta_events:
        # unisci per nome+orario, preferisci score da diretta se ufficiale senza score
        def key(e):
            return (
                e.start_time.strftime("%Y%m%d%H%M") if hasattr(e.start_time, "strftime") else str(e.start_time)[:16],
                (e.home_team_name or "").lower(),
                (e.away_team_name or "").lower(),
            )
        by_key = {key(e): e for e in events}
        for de in diretta_events:
            k = key(de)
            if k not in by_key:
                events.append(de)
                by_key[k] = de
            else:
                existing = by_key[k]
                if getattr(existing, "home_score", None) is None and de.home_score is not None:
                    existing.home_score = de.home_score
                    existing.away_score = de.away_score
                if getattr(existing, "status", "") == "SCHEDULED" and de.status in ("LIVE", "FINISHED"):
                    existing.status = de.status
        print(f"[SPORTS] Serie C - ufficiale+diretta: {len(events)} eventi")

    normalized: list[RawEvent] = []

    for event in events:
        try:
            normalized.append(
                convert_serie_c_event(
                    event
                )
            )
        except Exception as error:
            print(
                "[SPORTS] "
                "Serie C - impossibile convertire "
                f"evento {getattr(event, 'source_event_id', '?')}: "
                f"{error}"
            )

    print(
        "[SPORTS] "
        "Serie C - fonte ufficiale: "
        f"{len(normalized)} eventi"
    )

    return normalized


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
            now
            + timedelta(
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

            if (
                status_code < 200
                or status_code >= 300
            ):
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
            "Errore di rete durante il recupero "
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
                if href.startswith("http://"):
                    href = "https://" + href[len("http://"):]
                return href

    logo = safe_string(
        team.get(
            "logo"
        )
    )
    if logo:
        if logo.startswith("http://"):
            logo = "https://" + logo[len("http://"):]
        return logo

    # Fallback: CDN ESPN da id squadra (club e nazionali)
    tid = safe_string(team.get("id"))
    if tid and tid.isdigit():
        return (
            "https://a.espncdn.com/i/teamlogos/soccer/500/"
            f"{tid}.png"
        )

    return None


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
    """
    Minuto e periodo ESPN.

    Per il calcio lo status utile è spesso su
    competitions[0].status (displayClock tipo "67:00"),
    non solo su event.status.
    """
    status = event.get("status")
    if not isinstance(status, dict):
        status = {}

    competitions = event.get("competitions") or []
    if isinstance(competitions, list) and competitions:
        comp0 = competitions[0]
        if isinstance(comp0, dict):
            comp_status = comp0.get("status")
            if isinstance(comp_status, dict):
                # preferisci status della competition
                status = {**status, **comp_status}

    display_clock = safe_string(status.get("displayClock"))
    period_raw = status.get("period")
    type_info = status.get("type") if isinstance(status.get("type"), dict) else {}

    period: str | None = None
    type_name = safe_string(type_info.get("name")) or ""
    type_detail = (safe_string(type_info.get("detail")) or "").lower()
    type_short = (safe_string(type_info.get("shortDetail")) or "").lower()

    if "half" in type_detail or "half" in type_short or "STATUS_HALFTIME" in type_name:
        period = "HT"
    elif period_raw is not None:
        try:
            p = int(period_raw)
            if p == 1:
                period = "1H"
            elif p == 2:
                period = "2H"
            elif p >= 3:
                period = "ET"
            else:
                period = str(p)
        except (TypeError, ValueError):
            period = safe_string(period_raw)

    minute = None
    if display_clock:
        try:
            # "67:00" o "67'" o "90+3"
            cleaned = display_clock.replace("'", "").strip()
            if "+" in cleaned:
                # es. 90+3 → minuto 90 (added gestito altrove se serve)
                base = cleaned.split("+")[0]
                minute = int(float(base.split(":")[0]))
            else:
                minute = int(float(cleaned.split(":")[0]))
        except (ValueError, TypeError):
            minute = None

    return minute, period


def extract_match_incidents(
    event: dict,
) -> tuple[list[dict], list[dict]]:
    """
    Gol e cartellini da competitions[0].details (ESPN).

    Ritorna (goals, cards) come liste di dict:
      {minute, player, team, type}
    """
    goals: list[dict] = []
    cards: list[dict] = []

    competitions = event.get("competitions") or []
    if not isinstance(competitions, list) or not competitions:
        return goals, cards

    comp0 = competitions[0]
    if not isinstance(comp0, dict):
        return goals, cards

    details = comp0.get("details") or []
    if not isinstance(details, list):
        return goals, cards

    # mappa competitor id -> home/away
    team_side: dict[str, str] = {}
    for c in comp0.get("competitors") or []:
        if not isinstance(c, dict):
            continue
        cid = safe_string((c.get("team") or {}).get("id") if isinstance(c.get("team"), dict) else c.get("id"))
        ha = safe_string(c.get("homeAway"))
        if cid and ha:
            team_side[cid] = ha

    for detail in details:
        if not isinstance(detail, dict):
            continue

        type_info = detail.get("type") if isinstance(detail.get("type"), dict) else {}
        type_text = (
            safe_string(type_info.get("text"))
            or safe_string(type_info.get("type"))
            or ""
        ).lower()

        clock = detail.get("clock") if isinstance(detail.get("clock"), dict) else {}
        clock_str = safe_string(clock.get("displayValue")) or safe_string(
            detail.get("clock") if not isinstance(detail.get("clock"), dict) else None
        )

        athletes = detail.get("athletesInvolved") or []
        player = None
        if isinstance(athletes, list) and athletes:
            a0 = athletes[0]
            if isinstance(a0, dict):
                player = safe_string(a0.get("displayName")) or safe_string(
                    a0.get("shortName")
                )

        team = detail.get("team") if isinstance(detail.get("team"), dict) else {}
        team_id = safe_string(team.get("id"))
        side = team_side.get(team_id or "", "")

        item = {
            "minute": clock_str,
            "player": player,
            "team": side or team_id,
            "type": type_text,
        }

        if "goal" in type_text or "score" in type_text:
            goals.append(item)
        elif "yellow" in type_text or "red" in type_text or "card" in type_text:
            cards.append(item)

    return goals, cards


def extract_espn_broadcasts(event: dict) -> list[str]:
    """
    Canali dichiarati da ESPN nello scoreboard (quando presenti).
    """
    names: list[str] = []

    def add(name: str | None) -> None:
        if not name:
            return
        n = name.strip()
        if not n or n in names:
            return
        low = n.lower()
        if low in {"tbd", "n/a", "none", "-"}:
            return
        names.append(n)

    competitions = event.get("competitions") or []
    if not isinstance(competitions, list):
        return names

    for comp in competitions:
        if not isinstance(comp, dict):
            continue
        for b in comp.get("broadcasts") or []:
            if not isinstance(b, dict):
                continue
            for n in b.get("names") or []:
                add(
                    safe_string(n)
                    if isinstance(n, str)
                    else (str(n) if n is not None else None)
                )
            add(b.get("name") if isinstance(b.get("name"), str) else None)

        for b in comp.get("geoBroadcasts") or []:
            if not isinstance(b, dict):
                continue
            media = b.get("media") if isinstance(b.get("media"), dict) else {}
            if isinstance(media.get("shortName"), str):
                add(media.get("shortName"))
            if isinstance(media.get("displayName"), str):
                add(media.get("displayName"))
            btype = b.get("type")
            if isinstance(btype, dict) and isinstance(btype.get("shortName"), str):
                add(btype.get("shortName"))

    return names


def _norm_team(name: str | None) -> str:
    if not name:
        return ""
    import re as _re
    s = name.lower().strip()
    s = _re.sub(r"[^a-z0-9àèéìòù\s]", " ", s)
    s = " ".join(s.split())
    # togli suffix comuni
    for w in ("calcio", "fc", "ac", "as", "us", "ssd", "asd", "virtus"):
        s = s.replace(f" {w}", "").replace(f"{w} ", "")
    return s.strip()


def _teams_match(a: str | None, b: str | None) -> bool:
    na, nb = _norm_team(a), _norm_team(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if na in nb or nb in na:
        return True
    # token overlap
    ta, tb = set(na.split()), set(nb.split())
    if not ta or not tb:
        return False
    inter = ta & tb
    return len(inter) >= 1 and (len(inter) / min(len(ta), len(tb))) >= 0.5


def enrich_serie_c_from_espn(
    serie_c_events: list,
) -> list:
    """
    Arricchisce eventi Serie C (fonte ufficiale) con score/gol/cartellini ESPN
    quando ita.3 è disponibile. Match per nomi squadra.
    """
    if not serie_c_events:
        return serie_c_events

    # trova SourceCompetition serie_c
    competition = None
    for c in ALL_COMPETITIONS:
        if c.key == "serie_c":
            competition = c
            break
    if competition is None:
        return serie_c_events

    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo("Europe/Rome"))
    dates = []
    for d in (0, 1):
        dates.append((now + timedelta(days=d)).strftime("%Y%m%d"))

    espn_raw: list[dict] = []
    for date_value in dates:
        try:
            url = build_scoreboard_url(competition, date_value)
            data = fetch_json(url)
            events = data.get("events") or []
            if isinstance(events, list):
                espn_raw.extend([e for e in events if isinstance(e, dict)])
            print(f"[SERIE C] ESPN {date_value}: {len(events)} eventi")
        except Exception as error:
            print(f"[SERIE C] ESPN {date_value} non disponibile: {error}")

    if not espn_raw:
        print("[SERIE C] Nessun dato ESPN da mergiare (score/gol da fonte ufficiale)")
        return serie_c_events

    # prepara lista (home, away, event_dict)
    espn_matches = []
    for ev in espn_raw:
        home, away = extract_competitors(ev)
        if not home or not away:
            continue
        ht = (home.get("team") or {}) if isinstance(home.get("team"), dict) else {}
        at = (away.get("team") or {}) if isinstance(away.get("team"), dict) else {}
        hname = safe_string(ht.get("displayName") or ht.get("name") or home.get("displayName"))
        aname = safe_string(at.get("displayName") or at.get("name") or away.get("displayName"))
        espn_matches.append((hname, aname, ev, home, away))

    enriched = 0
    for event in serie_c_events:
        if not isinstance(event, RawEvent):
            continue
        for hname, aname, ev, home, away in espn_matches:
            if not (
                _teams_match(event.home_team_name, hname)
                and _teams_match(event.away_team_name, aname)
            ) and not (
                _teams_match(event.home_team_name, aname)
                and _teams_match(event.away_team_name, hname)
            ):
                continue

            # score
            hs = safe_int(home.get("score"))
            aws = safe_int(away.get("score"))
            if hs is not None:
                event.home_score = hs
            if aws is not None:
                event.away_score = aws

            # clock / status
            minute, period = extract_clock(ev)
            if minute is not None:
                event.minute = minute
            if period:
                event.period = period

            # goals / cards da details scoreboard
            goals, cards = extract_match_incidents(ev)
            if goals:
                event.goals = goals
            if cards:
                event.cards = cards

            # se manca detail, prova summary
            if not goals and not cards:
                eid = safe_string(ev.get("id"))
                if eid:
                    try:
                        sum_url = (
                            "https://site.api.espn.com/apis/site/v2/sports/soccer/"
                            f"{competition.league}/summary?event={eid}"
                        )
                        summary = fetch_json(sum_url)
                        # summary a volte ha competitions[0].details
                        goals2, cards2 = extract_match_incidents(summary)
                        if not goals2 and isinstance(summary.get("header"), dict):
                            goals2, cards2 = extract_match_incidents(
                                {"competitions": (summary.get("header") or {}).get("competitions") or summary.get("competitions") or []}
                            )
                        if goals2:
                            event.goals = goals2
                        if cards2:
                            event.cards = cards2
                    except Exception as err:
                        print(f"[SERIE C] summary {eid}: {err}")

            enriched += 1
            break

    print(f"[SERIE C] ESPN merge: {enriched}/{len(serie_c_events)} arricchiti")
    return serie_c_events


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

    goals, cards = extract_match_incidents(event)
    broadcasts = extract_espn_broadcasts(event)

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
        goals=goals or None,
        cards=cards or None,
        broadcasts=broadcasts or None,
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
# ALL COMPETITIONS
# ============================================================



def convert_motogp_event(event) -> RawEvent:
    """Converte MotoGPEvent (motogp_source) in RawEvent.

    MotoGP non è una partita casa/ospite: niente team fittizi
    (il circuito come 'home' faceva comportamenti strani in app).
    """
    return RawEvent(
        source="motogp_official",
        source_event_id=event.source_event_id,
        competition_key="motogp",
        competition_name="MotoGP",
        sport="MOTOGP",
        title=event.title,
        start_time=event.start_time.isoformat(),
        end_time=event.end_time.isoformat() if event.end_time else None,
        status=event.status,
        home_team_id=None,
        home_team_name=None,
        home_team_short_name=None,
        home_team_logo=None,
        away_team_id=None,
        away_team_name=None,
        away_team_short_name=None,
        away_team_logo=None,
        home_score=None,
        away_score=None,
        period=None,
        minute=None,
        country=event.country,
    )



# ============================================================
# TENNIS (ATP / WTA) — partite singole via ESPN header API
#
# Lo scoreboard ESPN tennis restituisce solo i TORNEI
# (es. "SP Open"), non i match "Giocatore A - Giocatore B".
# L'API header espone le partite con competitors (athlete).
# ============================================================


def fetch_tennis_header_events(
    competition: SourceCompetition,
) -> list[RawEvent]:
    league = (competition.league or competition.key or "").strip().lower()
    if league not in {"atp", "wta"}:
        return []

    url = (
        "https://site.web.api.espn.com/apis/v2/scoreboard/header"
        f"?sport=tennis&league={league}"
    )

    try:
        data = fetch_json(url)
    except Exception as error:
        print(f"[TENNIS] {league} header non disponibile: {error}")
        return []

    sports = data.get("sports") or []
    if not sports or not isinstance(sports, list):
        return []

    leagues = sports[0].get("leagues") or []
    if not leagues or not isinstance(leagues, list):
        return []

    raw_events = leagues[0].get("events") or []
    if not isinstance(raw_events, list):
        return []

    results: list[RawEvent] = []

    for item in raw_events:
        if not isinstance(item, dict):
            continue

        # competitionId è unico per match; event id è solo il torneo
        match_id = safe_string(
            item.get("competitionId")
        ) or safe_string(item.get("id"))

        if not match_id:
            continue

        start_time = safe_string(item.get("date"))
        if not start_time:
            continue

        competitors = item.get("competitors") or []
        if not isinstance(competitors, list) or len(competitors) < 2:
            continue

        # home / away o order
        home = None
        away = None
        for comp in competitors:
            if not isinstance(comp, dict):
                continue
            ha = (comp.get("homeAway") or "").lower()
            if ha == "home":
                home = comp
            elif ha == "away":
                away = comp
        if home is None or away is None:
            ordered = sorted(
                [c for c in competitors if isinstance(c, dict)],
                key=lambda c: int(c.get("order") or 0),
            )
            if len(ordered) >= 2:
                home, away = ordered[0], ordered[1]
            else:
                continue

        def player_fields(comp: dict) -> tuple:
            pid = safe_string(comp.get("id"))
            name = (
                safe_string(comp.get("displayName"))
                or safe_string(comp.get("name"))
                or "Player"
            )
            short = (
                safe_string(comp.get("shortName"))
                or safe_string(comp.get("abbreviation"))
                or name
            )
            logo = safe_string(comp.get("logo"))
            return pid, name, short, logo

        home_id, home_name, home_short, home_logo = player_fields(home)
        away_id, away_name, away_short, away_logo = player_fields(away)

        title = f"{home_name} - {away_name}"

        tournament = (
            safe_string(item.get("name"))
            or safe_string(item.get("shortName"))
            or competition.name
            or league.upper()
        )

        # Status ESPN header: pre / in / post
        status_raw = (safe_string(item.get("status")) or "pre").lower()
        full_status = item.get("fullStatus") or {}
        type_info = {}
        if isinstance(full_status, dict):
            type_info = full_status.get("type") or {}
        state = (
            safe_string(type_info.get("state"))
            or status_raw
        ).lower()

        if state in {"in", "live"} or status_raw == "in":
            status = "LIVE"
        elif state in {"post", "final"} or status_raw == "post":
            status = "FINISHED"
        else:
            status = "SCHEDULED"

        # Punteggio tennis ESPN header:
        #   score = "6-4 6-2" oppure set vinti "2"
        #   linescores = games per set + winner
        def parse_tennis_side(comp: dict) -> tuple[int | None, str | None]:
            lines = comp.get("linescores") or comp.get("linescore")
            if isinstance(lines, list) and lines:
                sets_won = 0
                games_parts: list[str] = []
                for ls in lines:
                    if not isinstance(ls, dict):
                        continue
                    if ls.get("winner") is True:
                        sets_won += 1
                    v = ls.get("setScore")
                    if v is None:
                        v = ls.get("score")
                    if v is None:
                        v = ls.get("value")
                    if v is not None:
                        try:
                            games_parts.append(str(int(float(v))))
                        except (TypeError, ValueError):
                            games_parts.append(str(v))
                    tb = ls.get("tiebreak")
                    if tb is None:
                        tb = ls.get("tieBreakScore")
                    if tb is not None and games_parts:
                        games_parts[-1] = f"{games_parts[-1]}({tb})"
                detail = " ".join(games_parts) if games_parts else None
                return sets_won, detail

            raw = comp.get("score")
            if isinstance(raw, (int, float)):
                return int(raw), None
            if isinstance(raw, str):
                s = raw.strip()
                if not s or s in {"-", "—"}:
                    return None, None
                if s.isdigit():
                    return int(s), None
                # "6-4 6-2" o "1-6 6-7(2-7)" → conta set vinti
                sets_won = 0
                for part in s.replace(",", " ").split():
                    core = part.split("(")[0]
                    if "-" not in core:
                        continue
                    left, _, right = core.partition("-")
                    try:
                        if int(left) > int(right):
                            sets_won += 1
                    except ValueError:
                        continue
                return sets_won, s
            return None, None

        home_score, home_detail = parse_tennis_side(home)
        away_score, away_detail = parse_tennis_side(away)

        # period = stringa leggibile set (es. "6-4 6-2")
        period = None
        raw_home_score = home.get("score")
        if isinstance(raw_home_score, str) and "-" in raw_home_score:
            period = raw_home_score.strip()
        elif home_detail and away_detail:
            period = f"{home_detail} | {away_detail}"
        elif home_detail:
            period = home_detail

        location = safe_string(item.get("location")) or safe_string(
            (item.get("venue") or {}).get("fullName")
            if isinstance(item.get("venue"), dict)
            else None
        )

        # competition_name: torneo (WTA / ATP restano competition_key)
        results.append(
            RawEvent(
                source="ESPN_TENNIS",
                source_event_id=f"{league}_{match_id}",
                competition_key=competition.key,
                competition_name=(
                    f"{tournament} ({location})" if location and tournament and location.lower() not in tournament.lower()
                    else (tournament or competition.name or league.upper())
                ),
                sport="TENNIS",
                title=title,
                start_time=start_time,
                end_time=None,
                status=status,
                home_team_id=f"espn_tennis_{home_id}" if home_id else None,
                home_team_name=home_name,
                home_team_short_name=home_short,
                home_team_logo=home_logo,
                away_team_id=f"espn_tennis_{away_id}" if away_id else None,
                away_team_name=away_name,
                away_team_short_name=away_short,
                away_team_logo=away_logo,
                home_score=home_score,
                away_score=away_score,
                period=period,
                minute=None,
                country=None,
            )
        )

    print(f"[TENNIS] {league}: {len(results)} partite (header API)")
    return results


def fetch_official_motogp_events() -> list[RawEvent]:
    try:
        events = fetch_motogp_events()
    except Exception as error:
        print(f"[MOTOGP] Fonte ufficiale non disponibile: {error}")
        return []

    return [convert_motogp_event(event) for event in events]


def fetch_all_events() -> list[RawEvent]:
    dates = get_requested_dates()

    all_events: list[RawEvent] = []

    # --------------------------------------------------------
    # ESPN
    #
    # Tutte le competizioni ESPN tranne Serie C.
    # La Serie C viene gestita esclusivamente dalla fonte
    # ufficiale della Lega Serie C.
    # --------------------------------------------------------

    for competition in ALL_COMPETITIONS:

        if competition.key == "serie_c":
            continue

        # MotoGP: ESPN scoreboard non disponibile (HTTP 400).
        # Fonte ufficiale: motogp.com via motogp_source.py
        if competition.key == "motogp":
            continue

        # ATP / WTA: scoreboard = solo tornei (1 riga per Open).
        # Partite "A - B" dalla header API (una volta, non per data).
        if competition.key in {"atp", "wta"}:
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

    # --------------------------------------------------------
    # TENNIS — diretta.it (ATP, WTA, Challenger, ITF, BJK Cup…)
    # ESPN header resta solo fallback se diretta fallisce.
    # --------------------------------------------------------
    tennis_ok = False
    try:
        tennis_events = fetch_diretta_tennis_events()
        all_events.extend(tennis_events)
        tennis_ok = len(tennis_events) > 0
        print(f"[TENNIS] diretta.it: {len(tennis_events)} incontri")
    except Exception as error:
        print(f"[TENNIS] diretta.it errore: {error}")

    if not tennis_ok:
        for competition in ALL_COMPETITIONS:
            if competition.key not in {"atp", "wta"}:
                continue
            try:
                tennis_events = fetch_tennis_header_events(competition)
                all_events.extend(tennis_events)
            except Exception as error:
                print(f"[TENNIS] ESPN {competition.key} errore: {error}")

    # --------------------------------------------------------
    # SERIE C
    #
    # Fonte unica:
    # generator/serie_c_source.py
    #
    # Non viene più usato SofaScore nel percorso principale.
    # --------------------------------------------------------

    serie_c_events = (
        fetch_official_serie_c_events()
    )
    try:
        serie_c_events = enrich_serie_c_from_espn(serie_c_events)
    except Exception as error:
        print(f"[SERIE C] enrich ESPN errore: {error}")

    all_events.extend(
        serie_c_events
    )

    # --------------------------------------------------------
    # MOTOGP
    # Fonte ufficiale: www.motogp.com/en/calendar
    # --------------------------------------------------------

    motogp_events = (
        fetch_official_motogp_events()
    )

    all_events.extend(
        motogp_events
    )


    # --------------------------------------------------------
    # Billie Jean King Cup + Davis Cup (diretta.it)
    # --------------------------------------------------------
    try:
        cup_events = fetch_tennis_cup_events()
        all_events.extend(cup_events)
    except Exception as error:
        print(f"[TENNIS CUP] non disponibile: {error}")

    # --------------------------------------------------------
    # DEDUPLICAZIONE
    # --------------------------------------------------------

    return deduplicate_events(
        all_events
    )


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
