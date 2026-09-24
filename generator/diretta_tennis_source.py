"""
Tennis da diretta.it (feed Flashscore).

Copre ATP, WTA, Challenger, ITF, Billie Jean King Cup, Davis Cup, doppi, ecc.
URL: /x/feed/f_2_{day}_1_it-it_1  con header X-Fsign
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from config import REQUEST_TIMEOUT_SECONDS, USER_AGENT

TIMEZONE = ZoneInfo("Europe/Rome")
FSIGN = "SW9D1eZo"
FEED_URL = "https://www.diretta.it/x/feed/f_2_{day}_1_it-it_1"


def _download(day_offset: int) -> str:
    url = FEED_URL.format(day=day_offset)
    req = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Referer": "https://www.diretta.it/tennis/",
            "Accept": "*/*",
            "Accept-Language": "it-IT,it;q=0.9",
            "X-Fsign": FSIGN,
        },
    )
    with urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8", errors="replace")


def _field(block: str, key: str) -> str | None:
    m = re.search(rf"(?:^|¬){re.escape(key)}÷([^¬]+)", block)
    return m.group(1).strip() if m else None


def _status(ab: str | None) -> str:
    # Flashscore: 1 scheduled, 2 live, 3 finished, 4 postponed, 5 cancelled…
    if ab == "2":
        return "LIVE"
    if ab == "3":
        return "FINISHED"
    if ab in {"4", "5"}:
        return "SCHEDULED"
    return "SCHEDULED"


def _competition_key(tournament: str) -> str:
    t = (tournament or "").upper()
    if "BILLIE" in t or "FED CUP" in t or "BJK" in t:
        return "wta"  # app filter tennis
    if "DAVIS" in t:
        return "atp"
    if "WTA" in t or "DONNE" in t or "WOMEN" in t:
        return "wta"
    if "ATP" in t or "UOMINI" in t or "MEN" in t:
        return "atp"
    return "wta"


def _competition_name(tournament: str) -> str:
    t = tournament or "Tennis"
    # abbrevia
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > 80:
        t = t[:77] + "..."
    return t


def _logo_url(filename: str | None) -> str | None:
    if not filename:
        return None
    # doppio: "a.png;b.png" → primo
    f = filename.split(";")[0].strip()
    if not f.endswith((".png", ".jpg")):
        return None
    return f"https://static.flashscore.com/res/image/data/{f}"


def _safe_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_feed(data: str) -> list:
    from sports_sources import RawEvent

    events: list[RawEvent] = []
    current_za: str | None = None
    current_zaf: str | None = None

    for part in re.split(r"(?=ZA÷|~AA÷|AA÷)", data):
        if "ZA÷" in part[:6] or part.startswith("~ZA÷") or part.startswith("ZA÷"):
            m = re.search(r"ZA÷([^¬]+)", part)
            if m:
                current_za = m.group(1)
            m = re.search(r"ZAF÷([^¬]+)", part)
            if m:
                current_zaf = m.group(1)

        if "AA÷" not in part:
            continue
        m = re.search(r"AA÷([^¬]+)¬(.+)", part, re.S)
        if not m:
            continue
        eid, block = m.group(1), m.group(2)
        home = _field(block, "AE")
        away = _field(block, "AF")
        if not home or not away:
            continue

        # Skip pure team-tie rows without individual players if desired —
        # keep "Italia D" ties as well for overview
        ts_raw = _field(block, "AD")
        if not ts_raw or not ts_raw.isdigit():
            continue
        ts = int(ts_raw)
        start = datetime.fromtimestamp(ts, tz=timezone.utc)

        # solo oggi / domani (Europe/Rome)
        now_local = datetime.now(TIMEZONE).date()
        start_local = start.astimezone(TIMEZONE).date()
        if start_local < now_local or start_local > now_local + timedelta(days=1):
            continue

        tournament = current_za or current_zaf or "Tennis"
        ab = _field(block, "AB")
        status = _status(ab)
        home_score = _safe_int(_field(block, "AG") or _field(block, "BC"))
        away_score = _safe_int(_field(block, "AT") or _field(block, "BD"))
        period = _field(block, "CR") or _field(block, "BX")

        # dettaglio set se presente nei campi games
        # period testuale: set score string se disponibile
        period_str = None
        if period and period.isdigit():
            period_str = f"Set {period}"
        # se finished/live e scores set
        if home_score is not None and away_score is not None:
            pass

        ckey = _competition_key(tournament)
        cname = _competition_name(tournament)

        events.append(
            RawEvent(
                source="diretta_tennis",
                source_event_id=eid,
                competition_key=ckey,
                competition_name=cname,
                sport="TENNIS",
                title=f"{home} - {away}",
                start_time=start.replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
                end_time=None,
                status=status,
                home_team_id=f"diretta_{eid}_h",
                home_team_name=home,
                home_team_short_name=home,
                home_team_logo=_logo_url(_field(block, "OA")),
                away_team_id=f"diretta_{eid}_a",
                away_team_name=away,
                away_team_short_name=away,
                away_team_logo=_logo_url(_field(block, "OB")),
                home_score=home_score,
                away_score=away_score,
                period=period_str,
                minute=None,
                country=None,
            )
        )

    return events


def fetch_diretta_tennis_events() -> list:
    all_events: list[RawEvent] = []
    seen: set[str] = set()
    for day in (0, 1):  # oggi, domani
        try:
            print(f"[DIRETTA TENNIS] Feed day={day}")
            data = _download(day)
            page = _parse_feed(data)
            print(f"[DIRETTA TENNIS] day={day}: {len(page)} incontri")
            for ev in page:
                if ev.source_event_id in seen:
                    continue
                seen.add(ev.source_event_id)
                all_events.append(ev)
        except Exception as error:
            print(f"[DIRETTA TENNIS] Errore day={day}: {error}")

    print(f"[DIRETTA TENNIS] Totale: {len(all_events)}")
    return all_events


if __name__ == "__main__":
    for e in fetch_diretta_tennis_events()[:15]:
        print(e.status, e.title, e.competition_name, e.home_score, e.away_score)
