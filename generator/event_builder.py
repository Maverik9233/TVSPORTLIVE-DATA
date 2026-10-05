from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from zoneinfo import ZoneInfo

from livesoccertv_source import (
    LiveSoccerTvEvent,
    fetch_livesoccertv_events,
    match_livesoccertv_event,
)
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
    title_match_score,
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

    # Stemmi diretti sull'evento (app non dipende solo da teams[])
    home_logo_url: str | None = None
    away_logo_url: str | None = None


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
    "bjk_cup": "Billie Jean King Cup",
    "davis_cup": "Davis Cup",
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
    "league_one": "League One",
    "league_two": "League Two",
    "national_league": "National League",
    "la_liga_2": "La Liga 2",
    "bundesliga_2": "2. Bundesliga",
    "bundesliga_3": "3. Liga",
    "ligue_2": "Ligue 2",
    "coppa_italia_serie_c": "Coppa Italia Serie C",
    "liga_profesional": "Liga Profesional",
    "brasileirao": "Brasileirão",
    "mls": "MLS",
    "liga_mx": "Liga MX",
    "copa_libertadores": "Copa Libertadores",
    "copa_sudamericana": "Copa Sudamericana",
    "formula_1": "Formula 1",
    "uefa_u21": "Europei Under 21",
    "elite_league_u20": "Elite League U20",
    "fifa_friendly_u19": "Youth U19",
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
    "league_one": 58,
    "league_two": 52,
    "national_league": 48,
    "la_liga_2": 65,
    "bundesliga_2": 68,
    "bundesliga_3": 55,
    "ligue_2": 62,
    "coppa_italia_serie_c": 70,
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
    "league_one": "England",
    "league_two": "England",
    "national_league": "England",
    "la_liga_2": "Spain",
    "bundesliga_2": "Germany",
    "bundesliga_3": "Germany",
    "ligue_2": "France",
    "coppa_italia_serie_c": "Italy",
    "liga_profesional": "Argentina",
    "brasileirao": "Brazil",
    "mls": "USA",
    "bjk_cup": "International",
    "davis_cup": "International",
    "super_lig": "Turkey",
    "turkiye_1_lig": "Turkey",
    "ekstraklasa": "Poland",
    "polska_1_liga": "Poland",
    "kategoria_superiore": "Albania",
    "super_league_ch": "Switzerland",
    "challenge_league_ch": "Switzerland",
    "hnl": "Croatia",
    "jupiler_pro": "Belgium",
    "challenger_pro": "Belgium",
    "cyprus_1": "Cyprus",
    "malta_premier": "Malta",
    "russian_premier": "Russia",
    "bulgaria_first": "Bulgaria",
    "chinese_super_league": "China",
    "saudi_pro_league": "Saudi Arabia",
    "scottish_premiership": "Scotland",
    "scottish_championship": "Scotland",
    "liga_1_peru": "Peru",
    "primera_chile": "Chile",
    "liga_betplay": "Colombia",
    "liga_uruguaya": "Uruguay",

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
    # Solo leghe dove senza override non avremmo MAI un canale IT
    # e i diritti sono noti a livello di competizione (non di singola gara).
    # Per tutto il resto: SOLO LiveOnSat / Sky articoli Serie C.
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
}

# DISABILITATO: non inventare canali se LiveOnSat non ha la partita.
# Prima metteva Sky/DAZN/TV su TUTTE le WNBA/NBA/tennis → canali a caso.
SPORT_BROADCASTER_FALLBACKS: dict[str, tuple[str, ...]] = {}

# MotoGP Italia: LiveOnSat non ha pagina affidabile.
# Diritti fissi: Sky Sport MotoGP / Uno / NOW; TV8 spesso Sprint/qualifiche in chiaro.
MOTOGP_ITALY_BROADCASTERS: tuple[str, ...] = (
    "Sky Sport MotoGP",
    "Sky Sport Uno",
    "NOW",
    "TV8",
)

# Tennis Italia: LiveOnSat spesso non elenca SuperTennis+ / campi multipli
TENNIS_ITALY_BROADCASTERS: tuple[str, ...] = (
    "SuperTennis",
    "SuperTennis+ 1 HD",
    "SuperTennis+ 2 HD",
    "SuperTennis+ 3 HD",
    "SuperTennis+ 4 HD",
    "Sky Sport Tennis",
    "Sky Sport Tennis IT",
    "Sky Sport Uno",
    "NOW",
)

# NBA / basket IT
NBA_ITALY_BROADCASTERS: tuple[str, ...] = (
    "Sky Sport Basket",
    "Sky Sport Uno",
    "NBA TV",
    "NOW",
)

# UFC / MMA (diritti variabili: DAZN / ESPN / Sky)
UFC_BROADCASTERS: tuple[str, ...] = (
    "DAZN",
    "ESPN",
    "ESPN 2",
    "Sky Sport Uno",
    "Sky Sport Arena",
)

# NHL
NHL_BROADCASTERS: tuple[str, ...] = (
    "ESPN",
    "ESPN 2",
    "TNT Sports 1",
    "Sky Sport Arena",
    "Sky Sport Uno",
)

# Canali digitali terrestri IT spesso usati per Nazionale / Nations League
# (LiveOnSat a volte omette o sbaglia orario → match perso)
ITALY_NATIONAL_FTA: tuple[str, ...] = (
    "Rai 1",
    "Rai 2",
    "Canale 20 Mediaset",
    "TV8",
    "Cielo",
)



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
        team_id=final_id or team_id,
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
    """
    Abbinamento titolo + orario.
    Liste LiveOnSat >35 canali = spesso inquinate: si tengono solo
    i nomi FTA/Sky italiani riconosciuti, se le squadre coincidono.
    F1/MotoGP: match sede GP, una sola riga.
    """
    from liveonsat import title_match_score, LiveOnSatEvent as LOSEvent

    sport = (raw_event.sport or "").upper()
    is_racing = sport in {"FORMULA_1", "MOTOGP"}
    raw_title = raw_event.title or ""
    raw_low = raw_title.lower()

    # Da liste LiveOnSat "inquinate" (>35 canali) teniamo solo
    # canali IT chiari. Sky Calcio/Uno sì; TV8 solo se "Italia"
    # (mai TV8 Turkiye / TV8 generico senza paese).
    ITA_KEEP = (
        "rai 1", "rai 2", "rai uno", "rai due", "rai sport",
        "italia 1", "italia uno", "italia 2",
        "tv8 italia", "tv 8 italia", "tv8 italy",
        "canale 20", "20 mediaset", "canale 5",
        "cielo",
        "sky sport calcio", "sky sport uno", "sky calcio",
        "dazn 1 italia", "dazn 2 italia", "zona dazn",
    )

    def racing_score(cand_title: str) -> int:
        c = (cand_title or "").lower()
        for place in (
            "bahrain", "saudi", "jeddah", "australia", "melbourne", "japan",
            "suzuka", "china", "shanghai", "miami", "monaco", "spain",
            "barcelona", "canada", "montreal", "austria", "spielberg",
            "britain", "silverstone", "hungary", "budapest", "belgium",
            "spa", "netherlands", "zandvoort", "monza", "azerbaijan",
            "baku", "singapore", "austin", "mexico", "brazil", "sao paulo",
            "las vegas", "qatar", "abu dhabi", "malaysia", "imola",
        ):
            if place in raw_low and place in c:
                return 100
        return title_match_score(raw_title, cand_title)

    def team_tokens(title: str) -> set[str]:
        stop = {"vs", "v", "at", "the", "fc", "cf", "u21", "u20", "u19"}
        out = set()
        for w in (title or "").lower().replace("-", " ").split():
            w = "".join(ch for ch in w if ch.isalnum())
            if len(w) > 2 and w not in stop:
                out.add(w)
        return out

    def clean_bc(broadcasters, n_bc: int) -> list[str]:
        bl = list(broadcasters or ())
        if n_bc <= 35:
            return bl
        # lista inquinata: solo canali IT rilevanti
        kept = []
        for b in bl:
            low = (b or "").lower()
            if not any(k in low for k in ITA_KEEP):
                continue
            # TV8 solo se esplicitamente Italia (non Turkiye / generico)
            if "tv8" in low.replace(" ", "") or "tv 8" in low:
                if "turk" in low or "turkiye" in low:
                    continue
                if "italia" not in low and "italy" not in low:
                    continue
            kept.append(b)
        return kept

    raw_teams = team_tokens(raw_title)
    candidates: list[tuple[int, int, list, object]] = []

    for candidate in liveonsat_events:
        raw_bc = list(getattr(candidate, "broadcasters", ()) or ())
        n_bc = len(raw_bc)

        if is_racing:
            score = racing_score(candidate.title)
            if score < 70:
                continue
            candidates.append((score, 0, raw_bc, candidate))
            continue

        score = title_match_score(raw_title, candidate.title)
        if score < 80:
            continue
        tdiff = time_difference_seconds(
            raw_event.start_time,
            candidate.start_time,
        )
        cand_teams = team_tokens(candidate.title)
        same = len(raw_teams & cand_teams) >= 2

        if same:
            if tdiff > 8 * 3600:
                continue
            bc = clean_bc(raw_bc, n_bc)
        else:
            if score < 95 or tdiff > 45 * 60:
                continue
            if n_bc > 35:
                continue
            bc = raw_bc

        if not bc and n_bc > 35:
            continue
        candidates.append((score, tdiff, bc if bc else raw_bc, candidate))

    if not candidates:
        return None

    candidates.sort(key=lambda x: (-x[0], x[1]))
    best = candidates[0][3]

    if is_racing:
        return best

    merged: list[str] = []
    seen: set[str] = set()
    for score, tdiff, bc, cand in candidates:
        for b in bc:
            key = (b or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(b)

    if not merged:
        return best

    try:
        return LOSEvent(
            title=best.title,
            start_time=best.start_time,
            competition=getattr(best, "competition", "") or "",
            broadcasters=tuple(merged),
        )
    except TypeError:
        return best



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


def filter_channel_ids_for_sport(
    sport: str,
    channel_ids: list[str],
) -> list[str]:
    """
    Filtro generale: un canale "specializzato" non finisce
    su sport dove non ha senso (TV8 su NBA, F1 UK su Premier, ecc.).
    """
    sport = (sport or "").upper()

    # Famiglie di canali legate a uno sport
    F1 = {
        "sky_sport_f1", "sky_sports_f1_uk", "sky_sport_f1_de",
        "dazn_F1_es", "dazn_f1_es",
    }
    MOTO = {"sky_sport_motogp"}
    TENNIS = {
        "sky_sport_tennis",
        "supertennis",
        "supertennis_plus_1",
        "supertennis_plus_2",
        "supertennis_plus_3",
        "supertennis_plus_4",
        "tennis_channel",
        "tennis_tv",
        "skysports_tennis_uk",
    }
    BASKET = {"sky_sport_basket", "nba_tv", "nba_league_pass"}
    CALCIO_IT = {
        "sky_sport_calcio", "rai_1", "rai_2", "italia_1", "italia_2",
        "cielo", "canale_20_mediaset", "canale_5_mediaset", "tv8",
    }
    # TV8 a volte ha MotoGP/F1 in chiaro → permesso solo football + motogp
    FTA_IT = {"tv8", "rai_1", "rai_2", "cielo", "italia_1", "canale_20_mediaset"}

    blocked: set[str] = set()

    if sport == "BASKETBALL":
        blocked |= F1 | MOTO | TENNIS | CALCIO_IT | FTA_IT
        blocked |= {"sky_sport_calcio", "sky_sport_f1", "sky_sports_f1_uk"}
    elif sport == "TENNIS":
        blocked |= F1 | MOTO | BASKET | CALCIO_IT | FTA_IT
        blocked -= TENNIS  # keep tennis channels
        blocked |= {"sky_sport_calcio", "sky_sport_basket"}
    elif sport == "FORMULA_1":
        blocked |= MOTO | TENNIS | BASKET | CALCIO_IT | FTA_IT
        blocked |= {"sky_sport_calcio", "nba_tv", "tv8"}
    elif sport == "MOTOGP":
        blocked |= F1 | TENNIS | BASKET
        blocked |= {"sky_sport_calcio", "nba_tv", "sky_sports_f1_uk"}
        # TV8 ok in Italia per Sprint
    elif sport in {"MMA", "UFC"}:
        blocked |= F1 | MOTO | TENNIS | BASKET | CALCIO_IT
        blocked |= {"sky_sport_calcio", "sky_sport_tennis", "nba_tv"}
    elif sport in {"HOCKEY", "NHL"}:
        blocked |= F1 | MOTO | TENNIS | CALCIO_IT
        blocked |= {"sky_sport_calcio", "sky_sport_tennis", "sky_sport_motogp"}
    elif sport == "FOOTBALL":
        blocked |= F1 | MOTO | TENNIS | BASKET
        blocked |= {
            "sky_sport_f1", "sky_sports_f1_uk", "sky_sport_f1_de",
            "sky_sport_motogp", "sky_sport_tennis", "sky_sport_basket",
            "nba_tv", "dazn_F1_es",
        }

    out: list[str] = []
    seen: set[str] = set()
    for cid in channel_ids:
        if not cid or cid in seen or cid in blocked:
            continue
        seen.add(cid)
        out.append(cid)
    return out

def get_event_broadcasters(
    raw_event: RawEvent,
    liveonsat_match: LiveOnSatEvent | None,
    sky_serie_c_map: dict | None = None,
    livesoccertv_match: LiveSoccerTvEvent | None = None,
) -> list[str]:

    broadcasters: list[str] = []

    def add(name: str | None) -> None:
        if not name:
            return
        n = name.strip()
        if not n or n in broadcasters:
            return
        broadcasters.append(n)

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
            add(broadcaster)

    # 2) LiveOnSat
    if liveonsat_match is not None:
        for broadcaster in (
            liveonsat_match.broadcasters
        ):
            add(broadcaster)

    # 2b) LiveSoccerTV
    if livesoccertv_match is not None:
        for broadcaster in livesoccertv_match.broadcasters:
            add(broadcaster)

    # 2c) Canali dichiarati da ESPN (broadcasts nello scoreboard)
    espn_bc = getattr(raw_event, "broadcasts", None) or []
    for broadcaster in espn_bc:
        add(broadcaster)

    # 2d) MotoGP Italia — fonte diritti (LiveOnSat non copre MotoGP)
    if (raw_event.sport or "").upper() == "MOTOGP":
        for broadcaster in MOTOGP_ITALY_BROADCASTERS:
            add(broadcaster)

    # 2e) Tennis Italia — SuperTennis + Sky anche se LiveOnSat è vuoto
    if (raw_event.sport or "").upper() == "TENNIS":
        for broadcaster in TENNIS_ITALY_BROADCASTERS:
            add(broadcaster)

    # 2f) NBA / basket USA-IT
    if (raw_event.sport or "").upper() == "BASKETBALL" and (
        (raw_event.competition_key or "").lower() in {"nba", "wnba"}
        or "nba" in (raw_event.competition_name or "").lower()
    ):
        for broadcaster in NBA_ITALY_BROADCASTERS:
            add(broadcaster)

    # 2g) UFC / MMA
    if (raw_event.sport or "").upper() in {"MMA", "UFC"} or (
        (raw_event.competition_key or "").lower() in {"ufc", "mma"}
    ):
        for broadcaster in UFC_BROADCASTERS:
            add(broadcaster)

    # 2h) NHL
    if (raw_event.sport or "").upper() in {"HOCKEY", "NHL"} or (
        (raw_event.competition_key or "").lower() == "nhl"
    ):
        for broadcaster in NHL_BROADCASTERS:
            add(broadcaster)

    # 3) Override Serie C se ancora vuoto
    if (
        not broadcasters
        and raw_event.competition_key == "serie_c"
    ):
        for broadcaster in COMPETITION_BROADCASTER_OVERRIDES.get(
            "serie_c",
            (),
        ):
            add(broadcaster)

    # 4) Nessun fallback sport generico (evita canali a caso su WNBA ecc.)
    if not broadcasters and SPORT_BROADCASTER_FALLBACKS:
        sport = (raw_event.sport or "").upper()
        for broadcaster in SPORT_BROADCASTER_FALLBACKS.get(sport, ()):
            add(broadcaster)

    # 5) Nazionale italiana (Nations League / amichevoli):
    # se in titolo c'è Italy/Italia e manca qualunque canale IT noto,
    # aggiungi i digitali terrestri tipici (Rai / 20 / TV8 / Cielo).
    title_l = (raw_event.title or "").lower()
    is_italy_match = (
        (raw_event.sport or "").upper() == "FOOTBALL"
        and (
            "italy" in title_l
            or "italia" in title_l
        )
        and raw_event.competition_key
        in {
            "uefa_nations_league",
            "fifa_friendly",
            "fifa_world_cup",
            "uefa_euro",
            "uefa_u21",
        }
    )
    if is_italy_match:
        blob = " ".join(broadcasters).lower()
        has_it = any(
            x in blob
            for x in (
                "rai",
                "tv8",
                "cielo",
                "canale 20",
                "20 mediaset",
                "mediaset",
            )
        )
        if not has_it:
            for broadcaster in ITALY_NATIONAL_FTA:
                add(broadcaster)

    return broadcasters


# ============================================================
# EVENT
# ============================================================

def build_event(
    raw_event: RawEvent,
    liveonsat_events: Iterable[LiveOnSatEvent],
    channels: Iterable[Channel],
    sky_serie_c_map: dict | None = None,
    livesoccertv_events: Iterable[LiveSoccerTvEvent] | None = None,
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

    lst_list = list(livesoccertv_events or [])
    livesoccertv_match = match_livesoccertv_event(
        home_name=raw_event.home_team_name,
        away_name=raw_event.away_team_name,
        title=raw_event.title,
        lst_events=lst_list,
    )

    broadcasters = get_event_broadcasters(
        raw_event=raw_event,
        liveonsat_match=liveonsat_match,
        sky_serie_c_map=sky_serie_c_map,
        livesoccertv_match=livesoccertv_match,
    )

    channel_ids: list[str] = []

    sources = []
    if liveonsat_match is not None:
        sources.append("LiveOnSat")
    if livesoccertv_match is not None:
        sources.append("LiveSoccerTV")
    if getattr(raw_event, "broadcasts", None):
        sources.append("ESPN")
    src_label = "+".join(sources) if sources else "nessuna fonte TV"
    print(
        "[EVENT] "
        f"{raw_event.title} -> "
        f"{src_label}: "
        f"{', '.join(broadcasters) if broadcasters else 'nessun broadcaster'}"
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
        channel_ids = filter_channel_ids_for_sport(
            raw_event.sport,
            channel_ids,
        )

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

    home_logo = resolve_team_logo(
        team_name=raw_event.home_team_name,
        existing_logo=raw_event.home_team_logo,
        team_id=home_team_id or raw_event.home_team_id,
    )
    away_logo = resolve_team_logo(
        team_name=raw_event.away_team_name,
        existing_logo=raw_event.away_team_logo,
        team_id=away_team_id or raw_event.away_team_id,
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
        home_logo_url=home_logo,
        away_logo_url=away_logo,
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

    # LiveSoccerTV — seconda fonte programmazione
    livesoccertv_list: list = []
    try:
        livesoccertv_list = fetch_livesoccertv_events()
    except Exception as error:
        print(f"[LIVESOCCERTV] Non disponibile: {error}")
        livesoccertv_list = []

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
            livesoccertv_events=livesoccertv_list,
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

    
    # Riempi loghi mancanti sulle squadre (cache diretta.it)
    for tid, team in list(teams.items()):
        if team.logo_url:
            continue
        logo = resolve_team_logo(
            team_name=team.name,
            existing_logo=None,
            team_id=tid,
        )
        if logo:
            teams[tid] = BuiltTeam(
                id=team.id,
                name=team.name,
                short_name=team.short_name,
                logo_url=logo,
                country=team.country,
                country_flag_url=team.country_flag_url,
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
