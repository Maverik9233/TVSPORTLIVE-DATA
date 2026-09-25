
"""
Nazionali youth e amichevoli da diretta.it (feed Flashscore).

Copre: U19, U20, U21, Elite League U20, Europei U*, Mondiali U*,
Amichevoli Nazionali (quando presenti nel feed oggi/domani).
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from config import REQUEST_TIMEOUT_SECONDS, USER_AGENT, TIMEZONE, SHOW_TODAY, SHOW_TOMORROW

FSIGN = "SW9D1eZo"
FEED_URL = "https://www.diretta.it/x/feed/f_1_{day}_1_it-it_1"

# Solo youth U17–U21 (+ Elite League U20). Nations League resta su ESPN.
YOUTH_OR_INTL = re.compile(
    r"U1[79]|U2[01]|Under\s*1[79]|Under\s*2[01]|"
    r"Elite League U20|Europei U1[79]|Europei U2[01]|Mondiali U|"
    r"COSAFA Championship U|South American Games U|"
    r"Amichevoli.*U2[01]|Amichevoli.*U1[79]",
    re.I,
)


def _download(day_offset: int) -> str:
    url = FEED_URL.format(day=day_offset)
    req = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Referer": "https://www.diretta.it/",
            "Accept": "*/*",
            "Accept-Language": "it-IT,it;q=0.9",
            "X-Fsign": FSIGN,
        },
    )
    with urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8", errors="replace")


def _field(block: str, key: str) -> str | None:
    m = re.search(rf"(?:^|[¬~]){re.escape(key)}÷([^¬]+)", block)
    return m.group(1).strip() if m else None


def _status(ab: str | None) -> str:
    if ab == "2":
        return "LIVE"
    if ab == "3":
        return "FINISHED"
    if ab in {"4", "5"}:
        return "SCHEDULED"
    return "SCHEDULED"


def _competition_key(tournament: str) -> str:
    t = (tournament or "").upper()
    if "U21" in t or "UNDER 21" in t:
        return "uefa_u21" if "EUROPA" in t or "UEFA" in t or "EUROPEI" in t else "fifa_friendly_u21"
    if "U20" in t or "UNDER 20" in t:
        if "MONDIAL" in t or "WORLD" in t:
            return "fifa_u20_world"
        if "ELITE" in t:
            return "elite_league_u20"
        return "fifa_friendly_u20"
    if "U19" in t or "UNDER 19" in t:
        if "EUROPA" in t or "EUROPEI" in t or "UEFA" in t:
            return "uefa_u19"
        return "fifa_friendly_u19"
    if "U17" in t or "UNDER 17" in t:
        return "fifa_u17_world"
    if "NATIONS LEAGUE" in t or "UEFA NATIONS" in t:
        return "uefa_nations_league"
    if "AMICHEVOLI NAZIONALI" in t or "FRIENDLY" in t:
        return "fifa_friendly"
    return "fifa_friendly"


def _competition_name(tournament: str) -> str:
    t = re.sub(r"\s+", " ", (tournament or "Nazionali")).strip()
    # drop continent prefix "EUROPA: "
    if ":" in t:
        t = t.split(":", 1)[1].strip()
    if len(t) > 80:
        t = t[:77] + "..."
    return t


def _logo(filename: str | None) -> str | None:
    if not filename:
        return None
    f = filename.split(";")[0].strip()
    if not f.endswith((".png", ".jpg", ".svg")):
        return None
    return f"https://static.flashscore.com/res/image/data/{f}"


def _parse_feed(data: str) -> list:
    from sports_sources import RawEvent

    events: list[RawEvent] = []
    # Blocchi torneo: ~ZA÷... fino al prossimo ~ZA÷
    for tblock in re.split(r"(?=~ZA÷)", data):
        za = _field(tblock, "ZA")
        if not za or not YOUTH_OR_INTL.search(za):
            continue

        # Partite: ~AA÷id¬AD÷timestamp¬...AE÷home¬...AF÷away
        for mblock in re.split(r"(?=~AA÷)", tblock):
            if "~AA÷" not in mblock and not mblock.startswith("AA÷"):
                continue
            eid = _field(mblock, "AA")
            home = _field(mblock, "AE")
            away = _field(mblock, "AF")
            if not eid or not home or not away:
                continue

            ts = _field(mblock, "AD")
            start_time = None
            if ts and ts.isdigit():
                start_time = datetime.fromtimestamp(
                    int(ts), tz=timezone.utc
                ).strftime("%Y-%m-%dT%H:%M:%SZ")
            if not start_time:
                continue

            ab = _field(mblock, "AB")
            status = _status(ab)

            hs = _field(mblock, "AG")
            as_ = _field(mblock, "AH")
            home_score = int(hs) if hs and hs.isdigit() else None
            away_score = int(as_) if as_ and as_.isdigit() else None

            ckey = _competition_key(za)
            cname = _competition_name(za)

            events.append(
                RawEvent(
                    source="DIRETTA",
                    source_event_id=f"dir_{eid}",
                    competition_key=ckey,
                    competition_name=cname,
                    sport="FOOTBALL",
                    title=f"{home} - {away}",
                    start_time=start_time,
                    end_time=None,
                    status=status,
                    home_team_id=f"diretta_{eid}_h",
                    home_team_name=home,
                    home_team_short_name=home,
                    home_team_logo=_logo(_field(mblock, "OA")),
                    away_team_id=f"diretta_{eid}_a",
                    away_team_name=away,
                    away_team_short_name=away,
                    away_team_logo=_logo(_field(mblock, "OB")),
                    home_score=home_score,
                    away_score=away_score,
                    period=None,
                    minute=None,
                    country=None,
                )
            )
    return events


def fetch_diretta_youth_intl_events() -> list:
    all_events = []
    seen = set()
    days = []
    if SHOW_TODAY:
        days.append(0)
    if SHOW_TOMORROW:
        days.append(1)
    if not days:
        days = [0, 1]

    for day in days:
        try:
            print(f"[DIRETTA YOUTH/INTL] Feed day={day}")
            data = _download(day)
            page = _parse_feed(data)
            print(f"[DIRETTA YOUTH/INTL] day={day}: {len(page)} incontri")
            for ev in page:
                if ev.source_event_id in seen:
                    continue
                seen.add(ev.source_event_id)
                all_events.append(ev)
        except Exception as error:
            print(f"[DIRETTA YOUTH/INTL] Errore day={day}: {error}")

    print(f"[DIRETTA YOUTH/INTL] Totale: {len(all_events)}")
    return all_events


if __name__ == "__main__":
    for e in fetch_diretta_youth_intl_events()[:20]:
        print(e.status, e.competition_key, e.title, e.start_time)
