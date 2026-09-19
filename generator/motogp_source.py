from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from config import REQUEST_TIMEOUT_SECONDS, TIMEZONE, USER_AGENT


MOTOGP_CALENDAR_URL = "https://www.motogp.com/en/calendar"

ROME = ZoneInfo(TIMEZONE if TIMEZONE else "Europe/Rome")


@dataclass
class MotoGPEvent:
    source_event_id: str
    title: str
    start_time: datetime
    end_time: datetime
    status: str
    location: str | None = None
    country: str | None = None
    image_url: str | None = None
    kind: str = "GP"


def _download(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,it;q=0.8",
        },
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, Exception) as error:
        raise RuntimeError(f"Download fallito {url}: {error}") from error


def _parse_calendar(html: str) -> list[dict[str, str]]:
    """
    Estrae gli eventi strutturati dalla pagina ufficiale MotoGP.
    Attributi data-structured-* sul sito ufficiale.
    """
    tags = re.findall(
        r"<[^>]+data-structured-start-date=\"[^\"]+\"[^>]*>",
        html,
    )
    events: list[dict[str, str]] = []
    for tag in tags:
        attrs = dict(
            re.findall(
                r'data-structured-([\w-]+)="([^"]*)"',
                tag,
            )
        )
        if attrs.get("start-date") and attrs.get("title"):
            events.append(attrs)
    return events


def _parse_iso(value: str) -> datetime:
    # 2026-09-18T08:00:00+02:00
    return datetime.fromisoformat(value)


def _map_status(raw: str, start: datetime, end: datetime, now: datetime) -> str:
    status = (raw or "").upper()
    if status == "FINISHED" or end < now:
        return "FINISHED"
    if status == "CURRENT" or (start <= now <= end):
        return "LIVE"
    return "SCHEDULED"


def _slug(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")[:48]


def build_session_events(
    raw: dict[str, str],
    requested_dates: set[date],
    now: datetime,
) -> list[MotoGPEvent]:
    """
    Dal weekend GP genera sessioni rilevanti (Sprint sabato, Race domenica)
    solo se cadono nelle date richieste (oggi/domani).
    Orari tipici europei (approssimati) se il sito dà solo il range weekend.
    """
    try:
        weekend_start = _parse_iso(raw["start-date"])
        weekend_end = _parse_iso(raw["end-date"])
    except Exception:
        return []

    title = (raw.get("title") or "MotoGP").strip()
    title = re.sub(r"\s+", " ", title)
    location = (raw.get("location") or "").strip() or None
    country = (raw.get("country") or "").strip() or None
    image = (raw.get("image") or "").strip() or None
    kind = (raw.get("kind") or "GP").strip()
    status_raw = raw.get("status") or ""

    # Solo Grand Prix (niente test)
    if kind.upper() not in {"GP", "RACE", ""}:
        if "TEST" in title.upper():
            return []

    # Giorno gara = giorno di fine weekend (di solito domenica)
    race_day = weekend_end.astimezone(ROME).date()
    sprint_day = race_day - timedelta(days=1)

    results: list[MotoGPEvent] = []

    def make(
        session_name: str,
        day: date,
        hour: int,
        minute: int,
        duration_h: float,
    ) -> MotoGPEvent | None:
        if day not in requested_dates:
            return None
        start = datetime(
            day.year,
            day.month,
            day.day,
            hour,
            minute,
            tzinfo=ROME,
        )
        end = start + timedelta(hours=duration_h)
        sid = f"motogp_{_slug(title)}_{session_name.lower()}_{day.isoformat()}"
        event_status = _map_status(status_raw, weekend_start, weekend_end, now)
        # Se la sessione è già passata oggi
        if end < now:
            event_status = "FINISHED"
        elif start <= now <= end:
            event_status = "LIVE"
        elif event_status == "LIVE" and now < start:
            event_status = "SCHEDULED"

        display = f"MotoGP - {title}"
        if session_name:
            display = f"MotoGP - {title} ({session_name})"

        return MotoGPEvent(
            source_event_id=sid,
            title=display,
            start_time=start,
            end_time=end,
            status=event_status,
            location=location,
            country=country,
            image_url=image,
            kind=session_name or kind,
        )

    # Sprint sabato ~15:00, Race domenica ~14:00 (orari Europa tipici)
    sprint = make("Sprint", sprint_day, 15, 0, 1.0)
    race = make("Race", race_day, 14, 0, 1.5)

    # Se il weekend è "CURRENT" e oggi è venerdì, mostra un evento Practice
    friday = race_day - timedelta(days=2)
    practice = make("Practice", friday, 15, 0, 1.5)

    for item in (practice, sprint, race):
        if item is not None:
            results.append(item)

    # Fallback: se nessuna sessione nei giorni richiesti ma il weekend
    # copre oggi, crea un evento generico "Weekend"
    if not results:
        for d in sorted(requested_dates):
            if weekend_start.astimezone(ROME).date() <= d <= weekend_end.astimezone(ROME).date():
                generic = make("Weekend", d, 10, 0, 8.0)
                if generic:
                    results.append(generic)
                break

    return results


def fetch_motogp_events(
    requested_dates: list[date] | None = None,
) -> list[MotoGPEvent]:
    """
    Scarica il calendario ufficiale MotoGP e restituisce
    gli eventi nelle date richieste (default: oggi e domani Rome).
    """
    now = datetime.now(ROME)
    if requested_dates is None:
        today = now.date()
        requested_dates = [today, today + timedelta(days=1)]

    date_set = set(requested_dates)

    print(f"[MOTOGP] Download calendario: {MOTOGP_CALENDAR_URL}")
    html = _download(MOTOGP_CALENDAR_URL)
    raw_events = _parse_calendar(html)
    print(f"[MOTOGP] Eventi calendario trovati: {len(raw_events)}")

    result: list[MotoGPEvent] = []
    seen: set[str] = set()

    for raw in raw_events:
        for event in build_session_events(raw, date_set, now):
            if event.source_event_id in seen:
                continue
            seen.add(event.source_event_id)
            result.append(event)

    print(f"[MOTOGP] Eventi oggi/domani: {len(result)}")
    for event in result:
        print(f"  {event.start_time.isoformat()} {event.title} [{event.status}]")

    return result


if __name__ == "__main__":
    fetch_motogp_events()
