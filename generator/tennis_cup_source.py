"""
Billie Jean King Cup + Davis Cup da diretta.it (Flashscore feed).

Fonte stabile con AA÷ / AE÷ / AF÷ / AD÷ (unix) / AB÷ status / AS÷ AT÷ set.
Copre singolare e doppio BJK + Davis Cup gruppo mondiale.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from config import REQUEST_TIMEOUT_SECONDS, USER_AGENT

TIMEZONE = ZoneInfo("Europe/Rome")

# Pagine ufficiali diretta.it (verificate 2026-09-24)
PAGES: tuple[tuple[str, str, str], ...] = (
    # competition_key, competition_name, url
    (
        "bjk_cup",
        "Billie Jean King Cup",
        "https://www.diretta.it/tennis/wta-singolare/billie-jean-king-cup-gruppo-mondiale/",
    ),
    (
        "bjk_cup",
        "Billie Jean King Cup",
        "https://www.diretta.it/tennis/wta-doppio/billie-jean-king-cup-gruppo-mondiale/",
    ),
    (
        "bjk_cup",
        "Billie Jean King Cup",
        "https://www.diretta.it/tennis/squadre-donne/billie-jean-king-cup-gruppo-mondiale/",
    ),
    (
        "davis_cup",
        "Davis Cup",
        "https://www.diretta.it/tennis/atp-singolare/coppa-davis-gruppo-mondiale/",
    ),
    (
        "davis_cup",
        "Davis Cup",
        "https://www.diretta.it/tennis/atp-doppio/coppa-davis-gruppo-mondiale/",
    ),
)


def _download(url: str) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
            "Accept": "text/html",
        },
    )
    with urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8", errors="replace")


def _field(block: str, key: str) -> str | None:
    m = re.search(rf"(?:^|¬){re.escape(key)}÷([^¬~]+)", block)
    return m.group(1).strip() if m else None


def _logo_url(raw: str | None) -> str | None:
    if not raw:
        return None
    # doppio: "file1.png;file2.png" → primo stemma
    first = raw.split(";")[0].strip()
    if not first.endswith((".png", ".jpg", ".webp")):
        return None
    if first.startswith("http"):
        return first
    return f"https://static.flashscore.com/res/image/data/{first}"


def _safe_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _status_from_ab(ab: str | None) -> str:
    """
    Flashscore/diretta AB:
      1 = non iniziato
      2 = in corso
      3 = finito
      altri = scheduled
    """
    code = _safe_int(ab)
    if code == 2:
        return "LIVE"
    if code == 3:
        return "FINISHED"
    return "SCHEDULED"


def _in_window(ts: int, now: datetime) -> bool:
    """Solo oggi e domani (fuso Europe/Rome)."""
    try:
        start = datetime.fromtimestamp(ts, tz=TIMEZONE)
    except (OverflowError, OSError, ValueError):
        return False
    today = now.date()
    return start.date() in {today, today + timedelta(days=1)}


def _parse_page(
    html: str,
    competition_key: str,
    competition_name: str,
    now: datetime,
) -> list:
    from sports_sources import RawEvent

    events: list = []
    parts = re.split(r"[¬~]*AA÷", html)
    for idx, block in enumerate(parts[1:]):
        eid = block.split("¬", 1)[0].strip() or f"{competition_key}_{idx}"
        home = _field(block, "AE") or _field(block, "CX")
        away = _field(block, "AF")
        if not home or not away:
            continue
        ad = _safe_int(_field(block, "AD"))
        if ad is None or not _in_window(ad, now):
            continue

        status = _status_from_ab(_field(block, "AB"))
        home_score = _safe_int(_field(block, "AS"))
        away_score = _safe_int(_field(block, "AT"))
        # dettaglio games ultimo set (opzionale)
        g_home = _field(block, "BC") or _field(block, "AG")
        g_away = _field(block, "BD")
        period = None
        if g_home is not None and g_away is not None:
            period = f"{g_home}-{g_away}"

        start = datetime.fromtimestamp(ad, tz=TIMEZONE).astimezone(
            ZoneInfo("UTC")
        )
        start_iso = (
            start.replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

        home_logo = _logo_url(_field(block, "OA"))
        away_logo = _logo_url(_field(block, "OB"))

        events.append(
            RawEvent(
                source="diretta_tennis_cup",
                source_event_id=f"{competition_key}_{eid}",
                competition_key=competition_key,
                competition_name=competition_name,
                sport="TENNIS",
                title=f"{home} - {away}",
                start_time=start_iso,
                end_time=None,
                status=status,
                home_team_id=None,
                home_team_name=home,
                home_team_short_name=home,
                home_team_logo=home_logo,
                away_team_id=None,
                away_team_name=away,
                away_team_short_name=away,
                away_team_logo=away_logo,
                home_score=home_score,
                away_score=away_score,
                period=period,
                minute=None,
                country=None,
            )
        )
    return events


def fetch_tennis_cup_events() -> list:
    now = datetime.now(TIMEZONE)
    all_events: list = []
    seen: set[str] = set()

    for competition_key, competition_name, url in PAGES:
        try:
            print(f"[TENNIS CUP] Download {url}")
            html = _download(url)
            page_events = _parse_page(
                html, competition_key, competition_name, now
            )
            print(
                f"[TENNIS CUP] {competition_key}: "
                f"{len(page_events)} eventi oggi/domani"
            )
            for ev in page_events:
                key = (
                    ev.competition_key,
                    ev.title.casefold(),
                    ev.start_time,
                )
                if key in seen:
                    continue
                seen.add(key)
                all_events.append(ev)
        except Exception as error:
            # Davis doppio può 404 fuori stagione: non blocca il resto
            print(f"[TENNIS CUP] Errore {url}: {error}")

    print(f"[TENNIS CUP] Totale: {len(all_events)}")
    return all_events


if __name__ == "__main__":
    for e in fetch_tennis_cup_events():
        print(
            e.status,
            e.home_score,
            e.away_score,
            e.title,
            e.start_time,
            e.competition_key,
        )
