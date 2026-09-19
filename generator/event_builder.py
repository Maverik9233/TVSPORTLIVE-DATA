from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from zoneinfo import ZoneInfo

from channel_matcher import (
    Channel,
    ChannelMatch,
    match_broadcasters,
)
from config import (
    JSON_VERSION,
    PREFER_ITALIAN_CHANNELS,
    TIMEZONE,
)
from liveonsat import (
    LiveOnSatEvent,
    event_titles_match,
)
from sports_sources import RawEvent
from sky_serie_c_channels import (
    fetch_sky_serie_c_channel_map,
    find_channels_for_match,
)
from competition_flags import (
    competition_flag_url,
    competition_logo_url,
)
from team_logos import resolve_team_logo


# ============================================================
# TVSPORTLIVE - EVENT BUILDER
# ============================================================


@dataclass(frozen=True)
class BuiltCompetition:
    id: str
    name: str
    sport: str
    country: str | None
    country_flag_url: str | None
    logo_url: str | None
    priority: int


@dataclass(frozen=True)
class BuiltTeam:
    id: str
    name: str
    short_name: str | None
    logo_url: str | None
    country: str | None
    country_flag_url: str | None


@dataclass(frozen=True)
class BuiltEvent:
    id: str
    title: str
    sport: str

    competition_id: str | None

    home_team_id: str | None
    away_team_id: str | None

    start_time: str
    end_time: str | None

    status: str

    home_score: int | None
    away_score: int | None

    channels: tuple[str, ...]


@dataclass(frozen=True)
class BuiltEventsDocument:
    version: int
    generated_at: str

    competitions: tuple[BuiltCompetition, ...]
    teams: tuple[BuiltTeam, ...]
    events: tuple[BuiltEvent, ...]


# ============================================================
# COMPETITION NAMES
# ============================================================

COMPETITION_NAMES = {
    "serie_a": "Serie A",
    "serie_b": "Serie B",
    "serie_c": "Serie C",
    "coppa_italia": "Coppa Italia",
    "supercoppa_italiana": "Supercoppa Italiana",
    "champions_league": "UEFA Champions League",
    "europa_league": "UEFA Europa League",
    "conference_league": "UEFA Conference League",
    "uefa_super_cup": "UEFA Super Cup",
    "fifa_world_cup": "FIFA World Cup",
    "fifa_club_world_cup": "FIFA Club World Cup",
    "premier_league": "Premier League",
    "la_liga": "La Liga",
    "bundesliga": "Bundesliga",
    "ligue_1": "Ligue 1",
    "primeira_liga": "Primeira Liga",
    "eredivisie": "Eredivisie",
    "eerste_divisie": "Eerste Divisie",
    "championship": "Championship",
    "la_liga_2": "La Liga 2",
    "bundesliga_2": "2. Bundesliga",
    "liga_profesional": "Liga Profesional",
    "brasileirao": "Brasileirão",
    "mls": "MLS",
    "liga_mx": "Liga MX",
    "copa_libertadores": "Copa Libertadores",
    "copa_sudamericana": "Copa Sudamericana",
    "formula_1": "Formula 1",
    "motogp": "MotoGP",
    "atp": "ATP",
    "wta": "WTA",
    "euroleague": "EuroLeague",
    "nba": "NBA",
    "wnba": "WNBA",
    "nbl": "NBL",
}


COMPETITION_PRIORITIES = {
    "serie_a": 100,
    "serie_b": 95,
    "serie_c": 90,
    "champions_league": 100,
    "europa_league": 95,
    "conference_league": 90,
    "uefa_super_cup": 100,
    "fifa_world_cup": 110,
    "fifa_club_world_cup": 105,
    "coppa_italia": 90,
    "supercoppa_italiana": 95,
    "premier_league": 85,
    "la_liga": 85,
    "bundesliga": 85,
    "ligue_1": 80,
    "primeira_liga": 75,
    "eredivisie": 75,
    "eerste_divisie": 55,
    "championship": 72,
    "la_liga_2": 65,
    "bundesliga_2": 68,
    "liga_profesional": 70,
    "brasileirao": 72,
    "mls": 70,
    "liga_mx": 68,
    "copa_libertadores": 88,
    "copa_sudamericana": 82,
    "formula_1": 100,
    "motogp": 100,
    "atp": 80,
    "wta": 80,
    "euroleague": 85,
    "nba": 85,
    "wnba": 75,
    "nbl": 60,
}


COMPETITION_COUNTRIES = {
    "serie_a": "Italy",
    "serie_b": "Italy",
    "serie_c": "Italy",
    "coppa_italia": "Italy",
    "supercoppa_italiana": "Italy",
    "premier_league": "England",
    "la_liga": "Spain",
    "bundesliga": "Germany",
    "ligue_1": "France",
    "primeira_liga": "Portugal",
    "eredivisie": "Netherlands",
    "eerste_divisie": "Netherlands",
    "championship": "England",
    "la_liga_2": "Spain",
    "bundesliga_2": "Germany",
    "liga_profesional": "Argentina",
    "brasileirao": "Brazil",
    "mls": "USA",
    "nba": "USA",
    "wnba": "USA",
    "nbl": "Australia",
    "liga_mx": "Mexico",
    "copa_libertadores": "South America",
    "copa_sudamericana": "South America",
}


# ============================================================
# BROADCASTER OVERRIDES
# ============================================================

COMPETITION_BROADCASTER_OVERRIDES = {
    "coppa_italia": (
        "Italia 1",
    ),
    "premier_league": (
        "Sky Sport Calcio",
        "Sky Sport Uno",
        "NOW",
    ),
    "championship": (
        "Sky Sport Calcio",
        "Sky Sport Uno",
        "NOW",
    ),
    "la_liga": (
        "DAZN 1 Italia",
        "DAZN 2 Italia",
    ),
    "la_liga_2": (
        "DAZN 1 Italia",
    ),
    "bundesliga": (
        "Sky Sport Uno",
        "Sky Sport Calcio",
    ),
    "bundesliga_2": (
        "Sky Sport Uno",
    ),
    "eredivisie": (
        "Ziggo Sport",
        "Sky Sport Uno",
    ),
    "eerste_divisie": (
        "Ziggo Sport",
    ),
    "ligue_1": (
        "DAZN 1 Italia",
    ),
    "primeira_liga": (
        "Sport TV 1 Portugal",
        "Sky Sport Uno",
    ),
    "liga_profesional": (
        "Sky Sport Uno",
        "DAZN 1 Italia",
    ),
    "brasileirao": (
        "Sky Sport Uno",
        "DAZN 1 Italia",
    ),
    "mls": (
        "Sky Sport Uno",
        "DAZN 1 Italia",
    ),
    "liga_mx": (
        "Sky Sport Uno",
    ),
    "copa_libertadores": (
        "Sky Sport Uno",
        "Sky Sport Calcio",
        "DAZN 1 Italia",
    ),
    "copa_sudamericana": (
        "Sky Sport Uno",
        "DAZN 1 Italia",
    ),
    "nba": (
        "Sky Sport Basket",
        "Sky Sport Uno",
        "NBA TV",
        "DAZN 1 Italia",
        "Eurosport 1",
    ),
    "wnba": (
        "Sky Sport Basket",
        "Sky Sport Uno",
        "DAZN 1 Italia",
    ),
    "nbl": (
        "Sky Sport Basket",
        "Sky Sport Uno",
    ),
    "euroleague": (
        "Sky Sport Basket",
        "Sky Sport Uno",
        "Eurosport 1",
        "DAZN 1 Italia",
    ),
    "atp": (
        "Sky Sport Tennis",
        "Sky Sport Uno",
        "Eurosport 1",
        "Eurosport 2",
        "SuperTennis",
        "Tennis Channel",
    ),
    "wta": (
        "Sky Sport Tennis",
        "Sky Sport Uno",
        "Eurosport 1",
        "Eurosport 2",
        "SuperTennis",
        "Tennis Channel",
    ),
    # Serie C: diritti Sky/NOW. LiveOnSat indica spesso solo
    # "Sky Go Italy"; i canali numerati (251+) sono quelli
    # usati da Sky per le gare in contemporanea.
    "serie_c": (
        "Sky Sport Calcio",
        "Sky Sport 251",
        "Sky Sport 252",
        "Sky Sport 253",
        "Sky Sport 254",
        "Sky Sport 255",
        "Sky Sport 256",
        "Sky Sport 257",
        "Sky Sport 258",
        "Sky Sport 259",
        "Sky Go Italy",
        "NOW",
    ),
    "motogp": (
        "Sky Sport Uno",
        "Sky Sport MotoGP",
        "DAZN 1 Italia",
        "NOW",
    ),
}

# Fallback per sport quando LiveOnSat non matcha
# (tennis/basket spesso hanno titoli torneo, non "A vs B")
SPORT_BROADCASTER_FALLBACKS: dict[str, tuple[str, ...]] = {
    "TENNIS": (
        "Sky Sport Tennis",
        "Eurosport 1",
        "Eurosport 2",
        "SuperTennis",
        "Sky Sport Uno",
        "Tennis Channel",
    ),
    "BASKETBALL": (
        "Sky Sport Basket",
        "NBA TV",
        "Sky Sport Uno",
        "DAZN 1 Italia",
        "Eurosport 1",
    ),
    "MOTOGP": (
        "Sky Sport Uno",
        "Sky Sport MotoGP",
        "DAZN 1 Italia",
        "NOW",
    ),
    "FORMULA_1": (
        "Sky Sport F1",
        "Sky Sport Uno",
        "NOW",
    ),
}


# ============================================================
# TEAM ID
# ============================================================

def build_team_id(
    raw_team_id: str | None,
    team_name: str | None,
) -> str | None:

    if raw_team_id:
        normalized_raw_id = raw_team_id.strip()

        if not normalized_raw_id:
            return None

        # SofaScore fornisce già ID nel formato
        # "sofascore_123".
        if normalized_raw_id.lower().startswith(
            "sofascore_"
        ):
            return normalized_raw_id

        # ESPN fornisce il proprio ID numerico.
        if normalized_raw_id.lower().startswith(
            "espn_"
        ):
            return normalized_raw_id

        return (
            f"espn_{normalized_raw_id}"
        )

    if not team_name:
        return None

    normalized = (
        team_name
        .strip()
        .lower()
    )

    normalized = (
        normalized
        .replace(
            " ",
            "_",
        )
        .replace(
            "-",
            "_",
        )
    )

    while "__" in normalized:
        normalized = normalized.replace(
            "__",
            "_",
        )

    return (
        f"team_{normalized}"
    )


# ============================================================
# COMPETITION
# ============================================================

def build_competition(
    event: RawEvent,
) -> BuiltCompetition:

    competition_id = (
        event.competition_key
    )

    name = (
        COMPETITION_NAMES.get(
            competition_id
        )
        or event.competition_name
        or competition_id
    )

    priority = (
        COMPETITION_PRIORITIES.get(
            competition_id,
            50,
        )
    )

    country = COMPETITION_COUNTRIES.get(
        competition_id
    )

    flag_url = competition_flag_url(
        competition_id
    )

    # logoUrl = bandiera così l'app attuale (che legge logoUrl) la mostra
    logo_url = competition_logo_url(
        competition_id
    )

    return BuiltCompetition(
        id=competition_id,
        name=name,
        sport=event.sport,
        country=country,
        country_flag_url=flag_url,
        logo_url=logo_url,
        priority=priority,
    )


# ============================================================
# TEAM
# ============================================================

def build_team(
    team_id: str | None,
    team_name: str | None,
    team_short_name: str | None,
    team_logo: str | None,
) -> BuiltTeam | None:

    if not team_name:
        return None

    final_id = build_team_id(
        raw_team_id=team_id,
        team_name=team_name,
    )

    if not final_id:
        return None

    resolved_logo = resolve_team_logo(
        team_name=team_name,
        existing_logo=team_logo,
        competition_key=None,
    )

    return BuiltTeam(
        id=final_id,
        name=team_name,
        short_name=team_short_name,
        logo_url=resolved_logo,
        country=None,
        country_flag_url=None,
    )


# ============================================================
# LIVEONSAT EVENT MATCH
# ============================================================

def get_matching_liveonsat_event(
    raw_event: RawEvent,
    liveonsat_events: Iterable[LiveOnSatEvent],
) -> LiveOnSatEvent | None:

    candidates = list(
        liveonsat_events
    )

    exact_matches: list[
        LiveOnSatEvent
    ] = []

    for candidate in candidates:
        if event_titles_match(
            raw_event.title,
            candidate.title,
        ):
            exact_matches.append(
                candidate
            )

    if not exact_matches:
        return None

    return min(
        exact_matches,
        key=lambda candidate:
            time_difference_seconds(
                raw_event.start_time,
                candidate.start_time,
            ),
    )


def time_difference_seconds(
    raw_start_time: str,
    liveonsat_time: str,
) -> int:

    try:
        event_dt = datetime.fromisoformat(
            raw_start_time
        )

    except ValueError:
        return 999999

    try:
        hour, minute = (
            liveonsat_time
            .strip()
            .split(":")
        )

        event_local = event_dt.astimezone(
            ZoneInfo(
                TIMEZONE
            )
        )

        liveonsat_minutes = (
            int(hour) * 60
            + int(minute)
        )

        event_minutes = (
            event_local.hour * 60
            + event_local.minute
        )

        difference = abs(
            event_minutes
            - liveonsat_minutes
        )

        difference = min(
            difference,
            1440 - difference,
        )

        return difference * 60

    except (
        ValueError,
        TypeError,
    ):
        return 999999


# ============================================================
# CHANNEL ORDER
# ============================================================

def sort_channel_matches(
    matches: Iterable[ChannelMatch],
    channels: Iterable[Channel],
) -> list[ChannelMatch]:

    channel_map = {
        channel.id: channel
        for channel in channels
    }

    def sort_key(
        match: ChannelMatch,
    ):
        channel = channel_map.get(
            match.channel_id
        )

        is_italian = (
            channel is not None
            and channel.country == "IT"
        )

        return (
            0 if (
                PREFER_ITALIAN_CHANNELS
                and is_italian
            ) else 1,

            -match.score,

            channel.priority
            if channel
            else 100,

            match.channel_name.casefold(),
        )

    return sorted(
        matches,
        key=sort_key,
    )


# ============================================================
# EVENT ID
# ============================================================

def build_event_id(
    raw_event: RawEvent,
) -> str:

    return (
        f"{raw_event.source.lower()}_"
        f"{raw_event.source_event_id}"
    )


# ============================================================
# CHANNEL BROADCASTERS
# ============================================================

def get_event_broadcasters(
    raw_event: RawEvent,
    liveonsat_match: LiveOnSatEvent | None,
    sky_serie_c_map: dict | None = None,
) -> list[str]:

    broadcasters: list[str] = []

    # 1) Canali precisi da articoli Sky (Serie C)
    if (
        raw_event.competition_key == "serie_c"
        and sky_serie_c_map
    ):
        sky_channels = find_channels_for_match(
            raw_event.title,
            sky_serie_c_map,
        )
        for broadcaster in sky_channels:
            if broadcaster not in broadcasters:
                broadcasters.append(broadcaster)

    # 2) LiveOnSat
    if liveonsat_match is not None:
        for broadcaster in (
            liveonsat_match.broadcasters
        ):
            if broadcaster not in broadcasters:
                broadcasters.append(
                    broadcaster
                )

    # 3) Override di competizione (fallback / integrazione)
    overrides = (
        COMPETITION_BROADCASTER_OVERRIDES.get(
            raw_event.competition_key,
            (),
        )
    )

    for broadcaster in overrides:
        if broadcaster not in broadcasters:
            broadcasters.append(
                broadcaster
            )

    # 4) Fallback per sport (tennis / basket / motogp / F1)
    #    Serve quando LiveOnSat non trova la partita
    #    e gli override di competizione non bastano.
    sport_key = (raw_event.sport or "").upper()
    for broadcaster in SPORT_BROADCASTER_FALLBACKS.get(sport_key, ()):
        if broadcaster not in broadcasters:
            broadcasters.append(broadcaster)

    return broadcasters


# ============================================================
# EVENT
# ============================================================

def build_event(
    raw_event: RawEvent,
    liveonsat_events: Iterable[LiveOnSatEvent],
    channels: Iterable[Channel],
    sky_serie_c_map: dict | None = None,
) -> BuiltEvent:

    channels_list = list(
        channels
    )

    liveonsat_match = (
        get_matching_liveonsat_event(
            raw_event=raw_event,
            liveonsat_events=liveonsat_events,
        )
    )

    broadcasters = get_event_broadcasters(
        raw_event=raw_event,
        liveonsat_match=liveonsat_match,
        sky_serie_c_map=sky_serie_c_map,
    )

    channel_ids: list[str] = []

    if liveonsat_match is not None:
        print(
            "[EVENT] "
            f"{raw_event.title} -> "
            "LiveOnSat: "
            f"{', '.join(broadcasters) if broadcasters else 'nessun broadcaster'}"
        )
    else:
        print(
            "[EVENT] "
            f"{raw_event.title} -> "
            "nessuna corrispondenza LiveOnSat"
        )

    if broadcasters:
        channel_matches = match_broadcasters(
            broadcasters=broadcasters,
            channels=channels_list,
        )

        ordered_matches = sort_channel_matches(
            matches=channel_matches,
            channels=channels_list,
        )

        channel_ids = [
            match.channel_id
            for match in ordered_matches
        ]

    if channel_ids:
        print(
            "[EVENT] "
            f"{raw_event.title} -> "
            f"CANALI: {', '.join(channel_ids)}"
        )
    else:
        print(
            "[EVENT] "
            f"{raw_event.title} -> "
            "nessun canale compatibile"
        )

    home_team_id = build_team_id(
        raw_team_id=raw_event.home_team_id,
        team_name=raw_event.home_team_name,
    )

    away_team_id = build_team_id(
        raw_team_id=raw_event.away_team_id,
        team_name=raw_event.away_team_name,
    )

    return BuiltEvent(
        id=build_event_id(
            raw_event
        ),
        title=raw_event.title,
        sport=raw_event.sport,
        competition_id=raw_event.competition_key,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        start_time=raw_event.start_time,
        end_time=raw_event.end_time,
        status=raw_event.status,
        home_score=raw_event.home_score,
        away_score=raw_event.away_score,
        channels=tuple(
            channel_ids
        ),
    )


# ============================================================
# DOCUMENT
# ============================================================

def build_events_document(
    raw_events: Iterable[RawEvent],
    liveonsat_events: Iterable[LiveOnSatEvent],
    channels: Iterable[Channel],
    generated_at: str,
) -> BuiltEventsDocument:

    raw_events_list = list(
        raw_events
    )

    liveonsat_list = list(
        liveonsat_events
    )

    channels_list = list(
        channels
    )

    # Mappa canali precisi Serie C da articoli Sky (251-259 ecc.)
    sky_serie_c_map: dict = {}
    try:
        has_serie_c = any(
            getattr(ev, "competition_key", None) == "serie_c"
            for ev in raw_events_list
        )
        if has_serie_c:
            sky_serie_c_map = fetch_sky_serie_c_channel_map()
    except Exception as error:
        print(f"[SKY SERIE C] Mappa canali non disponibile: {error}")
        sky_serie_c_map = {}

    competitions: dict[
        str,
        BuiltCompetition,
    ] = {}

    teams: dict[
        str,
        BuiltTeam,
    ] = {}

    events: list[
        BuiltEvent
    ] = []

    for raw_event in raw_events_list:
        competition = build_competition(
            raw_event
        )

        competitions[
            competition.id
        ] = competition

        home_team = build_team(
            team_id=raw_event.home_team_id,
            team_name=raw_event.home_team_name,
            team_short_name=(
                raw_event.home_team_short_name
            ),
            team_logo=raw_event.home_team_logo,
        )

        if home_team is not None:
            teams[
                home_team.id
            ] = home_team

        away_team = build_team(
            team_id=raw_event.away_team_id,
            team_name=raw_event.away_team_name,
            team_short_name=(
                raw_event.away_team_short_name
            ),
            team_logo=raw_event.away_team_logo,
        )

        if away_team is not None:
            teams[
                away_team.id
            ] = away_team

        built_event = build_event(
            raw_event=raw_event,
            liveonsat_events=liveonsat_list,
            channels=channels_list,
            sky_serie_c_map=sky_serie_c_map,
        )

        events.append(
            built_event
        )

    competitions_list = sorted(
        competitions.values(),
        key=lambda item: (
            -item.priority,
            item.name.casefold(),
        ),
    )

    teams_list = sorted(
        teams.values(),
        key=lambda item:
            item.name.casefold(),
    )

    events.sort(
        key=lambda item: (
            item.start_time,
            item.title.casefold(),
        )
    )

    return BuiltEventsDocument(
        version=JSON_VERSION,
        generated_at=generated_at,
        competitions=tuple(
            competitions_list
        ),
        teams=tuple(
            teams_list
        ),
        events=tuple(
            events
        ),
    )


# ============================================================
# PUBLIC ENTRY POINT
# ============================================================

def build_events(
    raw_events: Iterable[RawEvent],
    liveonsat_events: Iterable[LiveOnSatEvent],
    channels: Iterable[Channel],
    generated_at: str,
) -> BuiltEventsDocument:

    return build_events_document(
        raw_events=raw_events,
        liveonsat_events=liveonsat_events,
        channels=channels,
        generated_at=generated_at,
    )
