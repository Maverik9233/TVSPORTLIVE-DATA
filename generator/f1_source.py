
"""
Formula 1 — fonte dedicata.

Usa ESPN header API (FP1/FP2/FP3/Qualifying/Race).
Ogni sessione ha un competitionId univoco.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from config import (
    REQUEST_TIMEOUT_SECONDS,
    SHOW_TODAY,
    SHOW_TOMORROW,
    TIMEZONE,
    USER_AGENT,
)

HEADER_URL = (
    "https://site.web.api.espn.com/apis/v2/scoreboard/header"
    "?sport=racing&league=f1"
)


def _fetch_json(url: str) -> dict:
    request = urllib.request.Request(
        url=url,
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            "Referer": "https://www.espn.com/",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def _allowed_dates():
    now = datetime.now(ZoneInfo(TIMEZONE))
    dates = set()
    if SHOW_TODAY:
        dates.add(now.date())
    if SHOW_TOMORROW:
        dates.add((now + timedelta(days=1)).date())
    if not dates:
        dates.add(now.date())
    return dates


def fetch_f1_events() -> list:
    """Ritorna list[RawEvent] — import lazy per evitare cicli."""
    from sports_sources import RawEvent

    try:
        data = _fetch_json(HEADER_URL)
    except Exception as error:
        print(f"[F1] header API errore: {error}")
        return []

    try:
        events_raw = data["sports"][0]["leagues"][0]["events"]
    except (KeyError, IndexError, TypeError) as error:
        print(f"[F1] struttura header inattesa: {error}")
        return []

    if not isinstance(events_raw, list):
        return []

    allowed = _allowed_dates()
    results: list[RawEvent] = []

    for item in events_raw:
        if not isinstance(item, dict):
            continue

        # competitionId = sessione unica (FP3, Qualy, Race…)
        session_id = str(
            item.get("competitionId") or item.get("id") or ""
        ).strip()
        if not session_id:
            continue

        start_time = str(item.get("date") or "").strip()
        if not start_time:
            continue

        try:
            start_dt = datetime.fromisoformat(
                start_time.replace("Z", "+00:00")
            ).astimezone(ZoneInfo(TIMEZONE))
        except ValueError:
            continue

        if start_dt.date() not in allowed:
            continue

        ctype = item.get("competitionType") if isinstance(item.get("competitionType"), dict) else {}
        note = str(item.get("note") or "").strip()
        session = (
            note
            or str(ctype.get("text") or "").strip()
            or str(ctype.get("abbreviation") or "").strip()
            or "Session"
        )
        abbr = str(ctype.get("abbreviation") or session).replace(" ", "_")

        gp_name = (
            str(item.get("name") or "").strip()
            or str(item.get("shortName") or "").strip()
            or "Formula 1"
        )
        title = f"{gp_name} - {session}"

        status_raw = str(item.get("status") or "").lower()
        if status_raw in {"in", "live"}:
            status = "LIVE"
        elif status_raw in {"post", "final"}:
            status = "FINISHED"
        else:
            status = "SCHEDULED"

        broadcasts = []
        for b in item.get("broadcasts") or []:
            if isinstance(b, dict):
                n = b.get("name") or b.get("shortName") or b.get("type")
                if n:
                    broadcasts.append(str(n))

        results.append(
            RawEvent(
                source="F1",
                source_event_id=f"{session_id}_{abbr}",
                competition_key="formula_1",
                competition_name="Formula 1",
                sport="FORMULA_1",
                title=title,
                start_time=start_time if start_time.endswith("Z") else start_time,
                end_time=None,
                status=status,
                period=session,
                broadcasts=broadcasts or None,
            )
        )

    print(f"[F1] {len(results)} sessioni oggi/domani")
    for e in results:
        print(f"  [F1] {e.status} {e.start_time} {e.title}")
    return results


if __name__ == "__main__":
    for e in fetch_f1_events():
        print(e.status, e.start_time, e.title, e.source_event_id)
