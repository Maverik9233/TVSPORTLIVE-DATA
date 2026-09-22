"""
LiveSoccerTV — fonte secondaria di programmazione TV.

Scarica le schedule di oggi/domani e restituisce
titolo partita + lista broadcaster (nomi canale).
Usato in merge con LiveOnSat + ESPN broadcasts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
import re

from config import REQUEST_TIMEOUT_SECONDS, USER_AGENT

TIMEZONE = ZoneInfo("Europe/Rome")
BASE = "https://www.livesoccertv.com"


@dataclass
class LiveSoccerTvEvent:
    title: str
    home: str
    away: str
    broadcasters: list[str] = field(default_factory=list)
    start_hint: Optional[str] = None


def _download(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9,it;q=0.8",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8", errors="replace")


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _split_teams(title: str) -> tuple[str, str]:
    for sep in (" vs ", " VS ", " v ", " - "):
        if sep in title:
            a, b = title.split(sep, 1)
            return a.strip(), b.strip()
    return title.strip(), ""


def _parse_schedule_html(html: str) -> list[LiveSoccerTvEvent]:
    events: list[LiveSoccerTvEvent] = []
    rows = re.findall(
        r'<tr[^>]*class="[^"]*matchrow[^"]*"[^>]*>(.*?)</tr>',
        html,
        re.S | re.I,
    )
    for row in rows:
        name_m = re.search(
            r'class="match-name-col"[^>]*>.*?<a[^>]*>(.*?)</a>',
            row,
            re.S | re.I,
        )
        if not name_m:
            name_m = re.search(
                r'href="/match/[^"]*"[^>]*>(.*?)</a>',
                row,
                re.S | re.I,
            )
        if not name_m:
            continue
        title = _clean(name_m.group(1))
        if not title or " vs " not in title.lower() and " v " not in title.lower():
            # still accept "A vs B" variations
            if " vs " not in title and " VS " not in title and " v " not in title:
                continue

        broadcasters: list[str] = []
        # /channels/slug">Name
        for ch in re.findall(
            r'/channels/[^"]+"[^>]*>([^<]+)',
            row,
            re.I,
        ):
            name = _clean(ch)
            if name and name not in broadcasters:
                broadcasters.append(name)

        # title="Fox Sports 2 USA (live stream...)"
        for t in re.findall(r'title="([^"]{3,120})"', row):
            t = _clean(t)
            if not t or t.lower() == title.lower():
                continue
            if " vs " in t.lower():
                continue
            # strip parenthetical
            t = re.sub(r"\s*\([^)]*\)\s*$", "", t).strip()
            t = t.replace("&hellip;", "").strip()
            if len(t) < 2 or len(t) > 60:
                continue
            if t not in broadcasters:
                broadcasters.append(t)

        # data-channel-name on expanded bits (rare in row)
        for n in re.findall(
            r'data-channel-name="([^"]+)"',
            row,
            re.I,
        ):
            n = _clean(n)
            if n and n not in broadcasters:
                broadcasters.append(n)

        home, away = _split_teams(title)
        events.append(
            LiveSoccerTvEvent(
                title=title,
                home=home,
                away=away,
                broadcasters=broadcasters,
            )
        )

    return events


def fetch_livesoccertv_events() -> list[LiveSoccerTvEvent]:
    now = datetime.now(TIMEZONE)
    days = [
        now.strftime("%Y-%m-%d"),
        (now + timedelta(days=1)).strftime("%Y-%m-%d"),
    ]
    all_events: list[LiveSoccerTvEvent] = []
    seen: set[str] = set()

    for day in days:
        url = f"{BASE}/schedules/{day}/"
        try:
            print(f"[LIVESOCCERTV] Download {url}")
            html = _download(url)
            page = _parse_schedule_html(html)
            print(f"[LIVESOCCERTV] {day}: {len(page)} partite")
            for ev in page:
                key = ev.title.lower()
                if key in seen:
                    continue
                seen.add(key)
                all_events.append(ev)
        except Exception as error:
            print(f"[LIVESOCCERTV] Errore {day}: {error}")

    print(f"[LIVESOCCERTV] Totale: {len(all_events)}")
    return all_events


def _norm(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return " ".join(s.split())


def match_livesoccertv_event(
    home_name: str | None,
    away_name: str | None,
    title: str | None,
    lst_events: list[LiveSoccerTvEvent],
) -> LiveSoccerTvEvent | None:
    if not lst_events:
        return None
    nh = _norm(home_name or "")
    na = _norm(away_name or "")
    nt = _norm(title or "")

    best = None
    best_score = 0
    for ev in lst_events:
        eh, ea = _norm(ev.home), _norm(ev.away)
        score = 0
        if nh and eh and (nh in eh or eh in nh):
            score += 2
        if na and ea and (na in ea or ea in na):
            score += 2
        if nh and ea and (nh in ea or ea in nh):
            score += 1
        if na and eh and (na in eh or eh in na):
            score += 1
        if nt and _norm(ev.title):
            # token overlap
            th = set(nt.split())
            te = set(_norm(ev.title).split())
            inter = th & te
            if len(inter) >= 2:
                score += 1
        if score > best_score:
            best_score = score
            best = ev
    if best_score >= 3:
        return best
    return None


def fetch_livesoccertv_broadcasters_for_title(title: str) -> list[str]:
    """Compat: cerca in cache della giornata."""
    try:
        events = fetch_livesoccertv_events()
    except Exception:
        return []
    n = _norm(title)
    for ev in events:
        if _norm(ev.title) == n or n in _norm(ev.title):
            return list(ev.broadcasters)
    return []


if __name__ == "__main__":
    for e in fetch_livesoccertv_events()[:10]:
        print(e.title, "->", e.broadcasters[:6])
