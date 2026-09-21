from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from html.parser import HTMLParser
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from zoneinfo import ZoneInfo
import re

from config import REQUEST_TIMEOUT_SECONDS, USER_AGENT
from serie_c_logos import logo_from_static_map


TIMEZONE = ZoneInfo("Europe/Rome")

# Homepage contiene già le "Prossime Partite" di tutti i gironi.
# Le pagine girone restano come fallback.
SERIE_C_URLS = (
    "https://www.seriec.com/",
    "https://www.seriec.com/gironi/girone-a",
    "https://www.seriec.com/gironi/girone-b",
    "https://www.seriec.com/gironi/girone-c",
    "https://www.seriec.com/calendario",
)


@dataclass
class SerieCEvent:
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

    country: str = "Italy"

    home_logo_url: Optional[str] = None
    away_logo_url: Optional[str] = None


class _SerieCHtmlParser(HTMLParser):
    """
    Parser HTML leggero: estrae testo visibile + alt delle immagini
    (i nomi squadra compaiono spesso solo lì).
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.current_tag: Optional[str] = None
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = {
            str(k): str(v) for k, v in attrs if v is not None
        }
        self.current_tag = tag

        if tag in ("script", "style", "noscript"):
            self._skip_depth += 1
            return

        if self._skip_depth > 0:
            return

        if tag == "img":
            alt = attributes.get("alt", "").strip()
            if alt:
                clean_alt = re.sub(
                    r"^image:\s*", "", alt, flags=re.IGNORECASE
                ).strip()
                if clean_alt and len(clean_alt) > 1:
                    self.parts.append(clean_alt)

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript") and self._skip_depth > 0:
            self._skip_depth -= 1
        self.current_tag = None

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        text = " ".join(data.split()).strip()
        if text:
            self.parts.append(text)

    def text(self) -> str:
        return "\n".join(part for part in self.parts if part)


def _download(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
        },
    )

    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            data = response.read()
    except HTTPError as error:
        raise RuntimeError(f"HTTP {error.code} da {url}") from error
    except URLError as error:
        raise RuntimeError(f"Errore di rete da {url}: {error.reason}") from error
    except Exception as error:
        raise RuntimeError(f"Errore durante il download di {url}: {error}") from error

    for encoding in ("utf-8", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue

    return data.decode("utf-8", errors="replace")


def _normalize(value: str) -> str:
    value = value.upper()
    value = (
        value.replace("À", "A")
        .replace("È", "E")
        .replace("É", "E")
        .replace("Ì", "I")
        .replace("Ò", "O")
        .replace("Ù", "U")
    )
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _slug(value: str) -> str:
    value = _normalize(value)
    value = re.sub(r"[^A-Z0-9]+", "_", value)
    return value.strip("_").lower()


# Formato homepage ufficiale 2026/27:
#   6ª | 20/09 12:30
#   JUVENTUS NEXT GEN
#   JUV
#   Sky Sport
#   NOW
#   ALB
#   ALBINOLEFFE
DATE_LINE_RE = re.compile(
    r"^"
    r"(?:\d+[ªA]\s*\|\s*)?"          # opzionale "6ª |"
    r"(\d{1,2})/(\d{1,2})"           # giorno/mese
    r"(?:\s+(\d{1,2}):(\d{2}))?"     # ora opzionale
    r"$",
    re.IGNORECASE,
)

# Formato vecchio / calendario:
#   Gio 17 Set 18:30
LEGACY_DATE_RE = re.compile(
    r"^(?:LUN|MAR|MER|GIO|VEN|SAB|DOM)\s+"
    r"(\d{1,2})\s+"
    r"([A-ZÀÈÉÌÒÙ]{3})\s+"
    r"(\d{1,2}):(\d{2})$",
    re.IGNORECASE,
)

MONTHS_IT = {
    "GEN": 1, "FEB": 2, "MAR": 3, "APR": 4,
    "MAG": 5, "GIU": 6, "LUG": 7, "AGO": 8,
    "SET": 9, "OTT": 10, "NOV": 11, "DIC": 12,
}

IGNORED_EXACT = {
    "VS", "SKY SPORT", "NOW", "SKY", "RAI SPORT", "RAI", "RAI 2", "RAI2",
    "RISULTATI E CALENDARIO", "PROSSIME PARTITE",
    "GIRONE A", "GIRONE B", "GIRONE C", "SERIE C",
    "CALENDARIO", "LIVE", "HIGHLIGHTS",
    "COPPA ITALIA", "CLASSIFICA",
}

BROADCASTER_WORDS = {
    "SKY", "SPORT", "NOW", "RAI", "DAZN", "MEDIASET",
}



def _extract_team_logos(html: str) -> dict[str, str]:
    """
    Estrae le URL dei loghi squadra da seriec.com.
    Pattern tipico:
      /storage/app/media/loghi-squadre/Bari.png
      /storage/app/media/loghi-squadre/girone-c/scafatese-trasp-logo.png
    """
    logos: dict[str, str] = {}
    pattern = re.compile(
        r'(?:src|data-src)=["\']'
        r'([^"\']*loghi-squadre/[^"\']+\.(?:png|jpg|jpeg|webp|svg))'
        r'["\']',
        re.IGNORECASE,
    )
    base = "https://www.seriec.com"

    for match in pattern.finditer(html):
        path = match.group(1).strip()
        path = re.sub(r"/+", "/", path)
        filename = path.rsplit("/", 1)[-1]
        # es. Bari.png, scafatese-trasp-logo.png, Pescara_Calcio.png
        name_part = re.sub(
            r"(-trasp)?-?logo$|\.png$|\.jpg$|\.jpeg$|\.webp$|\.svg$",
            "",
            filename,
            flags=re.IGNORECASE,
        )
        name_part = name_part.replace("_", " ").replace("-", " ")
        key = _slug(name_part)
        if not key:
            continue
        url = path if path.startswith("http") else base + path
        # Preferisci path senza doppio slash
        url = url.replace("media//", "media/")
        if key not in logos:
            logos[key] = url

    return logos


def _logo_for_team(team_name: str, logos: dict[str, str]) -> Optional[str]:
    """
    1) Loghi trovati nel HTML di seriec.com
    2) Mappa statica (serie_c_logos.py) come fallback
    """
    if team_name and logos:
        key = _slug(team_name)
        if key in logos:
            return logos[key]

        variants = {
            key,
            key.replace("juventus_next_gen", "juventus"),
            key.replace("inter_under_23", "inter"),
            key.replace("atalanta_under_23", "atalanta"),
            key.replace("_under_23", ""),
            key.replace("_next_gen", ""),
            key.replace("_calcio", ""),
            key.replace("f_", ""),
        }
        for variant in variants:
            if variant in logos:
                return logos[variant]
            for logo_key, url in logos.items():
                if variant and (variant in logo_key or logo_key in variant):
                    return url

    # Fallback mappa statica
    return logo_from_static_map(team_name)


def _looks_like_team(value: str) -> bool:
    normalized = _normalize(value)

    if not normalized or len(normalized) < 2:
        return False

    if normalized in IGNORED_EXACT:
        return False

    if re.fullmatch(r"\d+\s*-\s*\d+", normalized):
        return False

    if re.fullmatch(r"\d{1,2}:\d{2}", normalized):
        return False

    if re.fullmatch(r"\d+", normalized):
        return False

    if DATE_LINE_RE.match(normalized) or LEGACY_DATE_RE.match(normalized):
        return False

    if normalized.startswith("GIORNATA ") or normalized.startswith("IMAGE:"):
        return False

    # Codici squadra corti (2-4 lettere) li trattiamo come team
    if re.fullmatch(r"[A-Z]{2,4}", normalized):
        return True

    # Evita righe che sono solo broadcaster
    tokens = set(normalized.split())
    if tokens and tokens.issubset(BROADCASTER_WORDS | {"SPORT"}):
        return False

    return True


def _parse_date_line(
    value: str,
    now: datetime,
) -> Optional[datetime]:
    """
    Interpreta:
      - 6ª | 20/09 12:30
      - 20/09 12:30
      - Gio 17 Set 18:30
    """
    normalized = _normalize(value)

    match = DATE_LINE_RE.match(normalized)
    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        hour = int(match.group(3) or 15)
        minute = int(match.group(4) or 0)
        year = now.year

        try:
            result = datetime(
                year, month, day, hour, minute, tzinfo=TIMEZONE
            )
        except ValueError:
            return None

        # Attraversamento anno
        if result < now - timedelta(days=180):
            try:
                result = result.replace(year=year + 1)
            except ValueError:
                return None

        return result

    match = LEGACY_DATE_RE.match(normalized)
    if match:
        day = int(match.group(1))
        month_name = match.group(2)
        hour = int(match.group(3))
        minute = int(match.group(4))
        month = MONTHS_IT.get(month_name)
        if month is None:
            return None

        year = now.year
        try:
            result = datetime(
                year, month, day, hour, minute, tzinfo=TIMEZONE
            )
        except ValueError:
            return None

        if result < now - timedelta(days=180):
            try:
                result = result.replace(year=year + 1)
            except ValueError:
                return None

        return result

    return None


def _pick_team_name(candidates: list[str]) -> Optional[str]:
    """
    Preferisce il nome lungo rispetto al codice a 2-4 lettere.
    """
    long_names: list[str] = []
    short_codes: list[str] = []

    for value in candidates:
        candidate = value.strip()
        if not _looks_like_team(candidate):
            continue
        normalized = _normalize(candidate)
        # Codici ufficiali sul sito sono quasi sempre 2-3 lettere (JUV, ALB, BA…).
        # Nomi come BARI, LECC, etc. vanno trattati come nome squadra.
        if re.fullmatch(r"[A-Z]{2,3}", normalized):
            short_codes.append(candidate)
        else:
            long_names.append(candidate)

    if long_names:
        return max(long_names, key=len)

    if short_codes:
        return short_codes[0]

    return None


def _find_event_blocks(
    text: str,
) -> list[tuple[str, str, str]]:
    """
    Restituisce liste di (date_time_raw, home, away).

    Supporta due layout:
    1) Homepage ufficiale (2026+):
         6ª | 20/09 12:30
         HOME FULL
         HOME CODE
         Sky Sport / NOW
         AWAY CODE
         AWAY FULL

    2) Layout legacy con VS o risultato.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    events: list[tuple[str, str, str]] = []

    i = 0
    while i < len(lines):
        current = lines[i]
        normalized = _normalize(current)

        is_date = bool(
            DATE_LINE_RE.match(normalized)
            or LEGACY_DATE_RE.match(normalized)
        )

        if not is_date:
            i += 1
            continue

        date_time = current
        window = lines[i + 1 : i + 14]

        # --- Layout homepage: HOME + CODE + broadcasters + CODE + AWAY ---
        team_candidates: list[str] = []
        for line in window:
            n = _normalize(line)
            if DATE_LINE_RE.match(n) or LEGACY_DATE_RE.match(n):
                break
            if n in IGNORED_EXACT:
                continue
            if re.fullmatch(r"\d+\s*-\s*\d+", n):
                continue
            if _looks_like_team(line):
                team_candidates.append(line)

        if len(team_candidates) >= 2:
            home = _pick_team_name(team_candidates[:3])
            remaining = [
                t for t in team_candidates
                if _normalize(t) != _normalize(home or "")
            ]
            away = _pick_team_name(remaining[:3])

            if home and away and _normalize(home) != _normalize(away):
                events.append((date_time, home, away))
                i += 1
                continue

        # --- Fallback legacy: VS ---
        vs_index = None
        for index, line in enumerate(window):
            if _normalize(line) == "VS":
                vs_index = index
                break

        if vs_index is not None:
            before = window[:vs_index]
            after = window[vs_index + 1 :]
            home = _pick_team_name(before)
            away = _pick_team_name(after)
            if home and away:
                events.append((date_time, home, away))
                i += 1
                continue

        # --- Fallback risultato: CASA / 2-1 / OSPITE ---
        if len(window) >= 3:
            home_c = window[0]
            result = window[1]
            away_c = window[2]
            if (
                _looks_like_team(home_c)
                and re.fullmatch(r"\d+\s*-\s*\d+", _normalize(result))
                and _looks_like_team(away_c)
            ):
                events.append((date_time, home_c, away_c))

        i += 1

    return events


def _build_event(
    date_time: str,
    home: str,
    away: str,
    now: datetime,
    logos: dict[str, str] | None = None,
) -> Optional[SerieCEvent]:
    start = _parse_date_line(date_time, now)
    if start is None:
        return None

    # Solo oggi e domani (allineato a config SHOW_TODAY / SHOW_TOMORROW)
    today = now.date()
    tomorrow = (now + timedelta(days=1)).date()

    if start.date() not in {today, tomorrow}:
        return None

    home_clean = home.strip()
    away_clean = away.strip()

    if not home_clean or not away_clean:
        return None

    home_id = "serie_c_" + _slug(home_clean)
    away_id = "serie_c_" + _slug(away_clean)

    event_key = (
        f"{start.strftime('%Y%m%d_%H%M')}_"
        f"{_slug(home_clean)}_"
        f"{_slug(away_clean)}"
    )

    end = start + timedelta(minutes=130)

    logos = logos or {}

    # Status reale: la fonte ufficiale non espone "LIVE",
    # quindi lo deduciamo dall'orario (Europe/Rome).
    now_cmp = now if now.tzinfo else now.replace(tzinfo=TIMEZONE)
    start_cmp = start if start.tzinfo else start.replace(tzinfo=TIMEZONE)
    end_cmp = end if end.tzinfo else end.replace(tzinfo=TIMEZONE)

    if now_cmp >= end_cmp:
        status = "FINISHED"
    elif now_cmp >= start_cmp:
        status = "LIVE"
    else:
        status = "SCHEDULED"

    return SerieCEvent(
        source_event_id=event_key,
        competition_key="serie_c",
        competition_name="Serie C",
        sport="FOOTBALL",
        title=f"{home_clean} - {away_clean}",
        start_time=start,
        end_time=end,
        status=status,
        home_team_id=home_id,
        home_team_name=home_clean,
        home_team_short_name=home_clean,
        away_team_id=away_id,
        away_team_name=away_clean,
        away_team_short_name=away_clean,
        home_logo_url=_logo_for_team(home_clean, logos),
        away_logo_url=_logo_for_team(away_clean, logos),
    )


def _parse_page(html: str, now: datetime) -> list[SerieCEvent]:
    parser = _SerieCHtmlParser()
    parser.feed(html)
    page_text = parser.text()
    logos = _extract_team_logos(html)

    raw_events = _find_event_blocks(page_text)

    events: list[SerieCEvent] = []
    seen: set[str] = set()

    for date_time, home, away in raw_events:
        event = _build_event(date_time, home, away, now, logos=logos)
        if event is None:
            continue
        if event.source_event_id in seen:
            continue
        seen.add(event.source_event_id)
        events.append(event)

    return events


def fetch_serie_c_events() -> list[SerieCEvent]:
    """
    Recupera gli eventi Serie C ufficiali per oggi e domani
    dal sito della Lega Serie C.
    """
    now = datetime.now(TIMEZONE)

    all_events: dict[str, SerieCEvent] = {}
    all_logos: dict[str, str] = {}

    for url in SERIE_C_URLS:
        try:
            print(f"[SERIE C] Download calendario: {url}")
            html = _download(url)
            page_logos = _extract_team_logos(html)
            all_logos.update(page_logos)
            events = _parse_page(html, now)
            print(f"[SERIE C] Eventi trovati da {url}: {len(events)}")

            for event in events:
                all_events[event.source_event_id] = event

        except Exception as error:
            print(f"[SERIE C] Fonte non disponibile {url}: {error}")

    # Riapplica loghi aggregati (homepage + gironi)
    if all_logos:
        print(f"[SERIE C] Loghi squadra trovati: {len(all_logos)}")
        for event_id, event in list(all_events.items()):
            home_logo = event.home_logo_url or _logo_for_team(
                event.home_team_name, all_logos
            )
            away_logo = event.away_logo_url or _logo_for_team(
                event.away_team_name, all_logos
            )
            if home_logo != event.home_logo_url or away_logo != event.away_logo_url:
                all_events[event_id] = SerieCEvent(
                    source_event_id=event.source_event_id,
                    competition_key=event.competition_key,
                    competition_name=event.competition_name,
                    sport=event.sport,
                    title=event.title,
                    start_time=event.start_time,
                    end_time=event.end_time,
                    status=event.status,
                    home_team_id=event.home_team_id,
                    home_team_name=event.home_team_name,
                    home_team_short_name=event.home_team_short_name,
                    away_team_id=event.away_team_id,
                    away_team_name=event.away_team_name,
                    away_team_short_name=event.away_team_short_name,
                    home_score=event.home_score,
                    away_score=event.away_score,
                    country=event.country,
                    home_logo_url=home_logo,
                    away_logo_url=away_logo,
                )

    result = sorted(
        all_events.values(),
        key=lambda event: (
            event.start_time,
            event.home_team_name.lower(),
            event.away_team_name.lower(),
        ),
    )

    print(f"[SERIE C] Totale eventi oggi/domani: {len(result)}")
    return result


if __name__ == "__main__":
    events = fetch_serie_c_events()

    print()
    print(f"Serie C: {len(events)} eventi")

    for event in events:
        print(
            event.start_time.strftime("%Y-%m-%d %H:%M"),
            "|",
            event.title,
        )
