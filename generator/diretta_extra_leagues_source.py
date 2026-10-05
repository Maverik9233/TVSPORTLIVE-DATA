"""
Campionati extra da diretta.it (stesso feed Flashscore delle Serie C).

- 3. Liga (Germania)
- Coppa Italia Serie C
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
import re

from config import REQUEST_TIMEOUT_SECONDS, USER_AGENT

TIMEZONE = ZoneInfo("Europe/Rome")

# (url, competition_key, competition_name, team_id_prefix)
LEAGUE_PAGES: tuple[tuple[str, str, str, str], ...] = (
    (
        "https://www.diretta.it/calcio/germania/3-liga/",
        "bundesliga_3",
        "3. Liga",
        "ger3",
    ),
    (
        "https://www.diretta.it/calcio/germania/3-liga/calendario/",
        "bundesliga_3",
        "3. Liga",
        "ger3",
    ),
    (
        "https://www.diretta.it/calcio/italia/coppa-italia-serie-c/",
        "coppa_italia_serie_c",
        "Coppa Italia Serie C",
        "cisc",
    ),
    (
        "https://www.diretta.it/calcio/italia/coppa-italia-serie-c/calendario/",
        "coppa_italia_serie_c",
        "Coppa Italia Serie C",
        "cisc",
    ),
)


@dataclass
class DirettaLeagueEvent:
    source_event_id: str
    competition_key: str
    competition_name: str
    sport: str
    title: str
    start_time: datetime
    end_time: datetime
    status: str
    home_team_id: str
    home_team_name: str
    home_team_short_name: str
    away_team_id: str
    away_team_name: str
    away_team_short_name: str
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    country: str = "International"


def _slug(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9àèéìòùäöüß]+", "_", s)
    return s.strip("_") or "team"


def _download(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8", errors="replace")


def _field(block: str, key: str) -> Optional[str]:
    m = re.search(rf"(?:^|¬){re.escape(key)}÷([^¬~]+)", block)
    return m.group(1).strip() if m else None


def _status_from_ab(ab: Optional[str], start: datetime, now: datetime) -> str:
    if ab == "2":
        return "LIVE"
    if ab == "3":
        return "FINISHED"
    if ab == "1":
        end = start + timedelta(minutes=130)
        if now >= end:
            return "FINISHED"
        if now >= start:
            return "LIVE"
        return "SCHEDULED"
    end = start + timedelta(minutes=130)
    if now >= end:
        return "FINISHED"
    if now >= start:
        return "LIVE"
    return "SCHEDULED"


def _parse_scores(block: str) -> tuple[Optional[int], Optional[int]]:
    def to_int(v: Optional[str]) -> Optional[int]:
        if v is None:
            return None
        try:
            return int(v)
        except ValueError:
            return None

    bc, bd = to_int(_field(block, "BC")), to_int(_field(block, "BD"))
    ag, at = to_int(_field(block, "AG")), to_int(_field(block, "AT"))
    as_, az = to_int(_field(block, "AS")), to_int(_field(block, "AZ"))
    ab = _field(block, "AB")
    if ab == "3" and bc is not None and bd is not None:
        if (bc, bd) != (0, 0) or (ag is None and at is None):
            return bc, bd
    if ag is not None and at is not None:
        return ag, at
    if as_ is not None and az is not None:
        return as_, az
    if bc is not None and bd is not None:
        return bc, bd
    return None, None


def _parse_page(
    html: str,
    now: datetime,
    competition_key: str,
    competition_name: str,
    team_prefix: str,
    country: str,
) -> list[DirettaLeagueEvent]:
    today = now.date()
    tomorrow = (now + timedelta(days=1)).date()
    events: list[DirettaLeagueEvent] = []
    seen: set[str] = set()

    parts = re.split(r"[¬~]*AA÷", html)
    for block in parts[1:]:
        eid = block.split("¬")[0].strip()
        if not eid or len(eid) > 40:
            continue

        ts = _field(block, "AD")
        if not ts or not ts.isdigit():
            continue
        try:
            start = datetime.fromtimestamp(int(ts), TIMEZONE)
        except (ValueError, OSError):
            continue

        if start.date() not in {today, tomorrow}:
            continue

        home = _field(block, "AE")
        away = _field(block, "AF")
        if not home or not away:
            continue
        if home.lower() == away.lower():
            continue

        home_score, away_score = _parse_scores(block)
        status = _status_from_ab(_field(block, "AB"), start, now)
        end = start + timedelta(minutes=130)

        source_id = f"diretta_{competition_key}_{eid}"
        if source_id in seen:
            continue
        seen.add(source_id)

        events.append(
            DirettaLeagueEvent(
                source_event_id=source_id,
                competition_key=competition_key,
                competition_name=competition_name,
                sport="FOOTBALL",
                title=f"{home} - {away}",
                start_time=start,
                end_time=end,
                status=status,
                home_team_id=f"{team_prefix}_{_slug(home)}",
                home_team_name=home,
                home_team_short_name=home,
                away_team_id=f"{team_prefix}_{_slug(away)}",
                away_team_name=away,
                away_team_short_name=away,
                home_score=home_score,
                away_score=away_score,
                country=country,
            )
        )

    return events


def fetch_diretta_extra_league_events() -> list[DirettaLeagueEvent]:
    now = datetime.now(TIMEZONE)
    all_events: list[DirettaLeagueEvent] = []
    seen: set[tuple] = set()

    for url, key, name, prefix in LEAGUE_PAGES:
        country = "Germany" if key == "bundesliga_3" else "Italy"
        try:
            print(f"[DIRETTA EXTRA] Download: {name} → {url}")
            html = _download(url)
            page_events = _parse_page(html, now, key, name, prefix, country)
            print(f"[DIRETTA EXTRA] {name}: {len(page_events)} eventi oggi/domani")
            for ev in page_events:
                k = (
                    ev.competition_key,
                    ev.start_time.strftime("%Y%m%d%H%M"),
                    ev.home_team_name.lower(),
                    ev.away_team_name.lower(),
                )
                if k in seen:
                    continue
                seen.add(k)
                all_events.append(ev)
        except Exception as error:
            print(f"[DIRETTA EXTRA] Errore {name} ({url}): {error}")

    all_events.sort(key=lambda e: (e.start_time, e.competition_key, e.home_team_name))
    print(f"[DIRETTA EXTRA] Totale: {len(all_events)}")
    return all_events


if __name__ == "__main__":
    for e in fetch_diretta_extra_league_events():
        print(
            e.competition_key,
            e.start_time.strftime("%d/%m %H:%M"),
            e.status,
            e.title,
            f"{e.home_score}-{e.away_score}",
        )
