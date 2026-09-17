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


TIMEZONE = ZoneInfo("Europe/Rome")

SERIE_C_URLS = (
    "https://www.seriec.com/calendario",
    "https://www.seriec.com/gironi/girone-a",
    "https://www.seriec.com/gironi/girone-b",
    "https://www.seriec.com/gironi/girone-c",
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
    Parser HTML molto semplice e robusto.

    Recupera:
    - testo visibile;
    - alt delle immagini, utile per i nomi delle squadre;
    - href;
    - class/id degli elementi quando disponibili.

    Non dipende da BeautifulSoup o altre librerie esterne.
    """

    def __init__(self) -> None:
        super().__init__(
            convert_charrefs=True
        )

        self.parts: list[str] = []

        self.current_tag: Optional[str] = None

        self.current_attrs: dict[str, str] = {}

        self.links: list[str] = []

        self.images: list[dict[str, str]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs,
    ) -> None:
        attributes = {
            str(key): str(value)
            for key, value in attrs
            if value is not None
        }

        self.current_tag = tag
        self.current_attrs = attributes

        if tag == "img":
            alt = attributes.get("alt", "").strip()
            src = attributes.get("src", "").strip()

            if alt or src:
                self.images.append(
                    {
                        "alt": alt,
                        "src": src,
                    }
                )

                # Nelle pagine della Lega Serie C i nomi delle
                # squadre possono essere presenti esclusivamente
                # nell'attributo alt dell'immagine. Aggiungiamolo
                # al testo estratto, mantenendo l'ordine del DOM.
                if alt:
                    clean_alt = re.sub(
                        r"^image:\s*",
                        "",
                        alt,
                        flags=re.IGNORECASE,
                    ).strip()

                    if clean_alt:
                        self.parts.append(clean_alt)

    def handle_startendtag(
        self,
        tag: str,
        attrs,
    ) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(
        self,
        tag: str,
    ) -> None:
        self.current_tag = None
        self.current_attrs = {}

    def handle_data(
        self,
        data: str,
    ) -> None:
        text = " ".join(
            data.split()
        ).strip()

        if not text:
            return

        self.parts.append(text)

        if self.current_tag == "a":
            self.links.append(text)

    def text(self) -> str:
        return "\n".join(
            part
            for part in self.parts
            if part
        )


def _download(
    url: str,
) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,"
                "application/xhtml+xml,"
                "application/xml;q=0.9,"
                "*/*;q=0.8"
            ),
            "Accept-Language": "it-IT,it;q=0.9",
        },
    )

    try:
        with urlopen(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:
            data = response.read()

    except HTTPError as error:
        raise RuntimeError(
            f"HTTP {error.code} da {url}"
        ) from error

    except URLError as error:
        raise RuntimeError(
            f"Errore di rete da {url}: {error.reason}"
        ) from error

    except Exception as error:
        raise RuntimeError(
            f"Errore durante il download di {url}: {error}"
        ) from error

    for encoding in (
        "utf-8",
        "latin-1",
    ):
        try:
            return data.decode(
                encoding
            )
        except UnicodeDecodeError:
            continue

    return data.decode(
        "utf-8",
        errors="replace",
    )


def _normalize(
    value: str,
) -> str:
    value = value.upper()

    value = (
        value
        .replace("À", "A")
        .replace("È", "E")
        .replace("É", "E")
        .replace("Ì", "I")
        .replace("Ò", "O")
        .replace("Ù", "U")
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def _slug(
    value: str,
) -> str:
    value = _normalize(value)

    value = re.sub(
        r"[^A-Z0-9]+",
        "_",
        value,
    )

    return value.strip("_").lower()


def _parse_date(
    value: str,
    now: datetime,
) -> Optional[datetime]:
    """
    Converte le date italiane presenti sul sito:

        Gio 17 Set 18:30
        Dom 20 Set 14:30

    nell'anno corretto.
    """

    months = {
        "GEN": 1,
        "FEB": 2,
        "MAR": 3,
        "APR": 4,
        "MAG": 5,
        "GIU": 6,
        "LUG": 7,
        "AGO": 8,
        "SET": 9,
        "OTT": 10,
        "NOV": 11,
        "DIC": 12,
    }

    match = re.search(
        r"\b"
        r"(?:LUN|MAR|MER|GIO|VEN|SAB|DOM)"
        r"\s+"
        r"(\d{1,2})"
        r"\s+"
        r"([A-ZÀÈÉÌÒÙ]{3})"
        r"\s+"
        r"(\d{1,2}):(\d{2})"
        r"\b",
        _normalize(value),
    )

    if not match:
        return None

    day = int(match.group(1))
    month_name = match.group(2)
    hour = int(match.group(3))
    minute = int(match.group(4))

    month = months.get(
        month_name
    )

    if month is None:
        return None

    year = now.year

    try:
        result = datetime(
            year,
            month,
            day,
            hour,
            minute,
            tzinfo=TIMEZONE,
        )
    except ValueError:
        return None

    # Se il calendario attraversa l'anno nuovo.
    if result < now - timedelta(days=180):
        result = result.replace(
            year=year + 1
        )

    return result


def _extract_team_names(
    text: str,
) -> list[str]:
    """
    Estrae nomi squadra da una porzione di calendario.

    Il sito presenta generalmente:

        SQUADRA CASA
        VS
        SQUADRA OSPITE

    oppure, per partite già concluse:

        SQUADRA CASA
        2 - 1
        SQUADRA OSPITE
    """

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    cleaned: list[str] = []

    ignored_exact = {
        "VS",
        "SKY SPORT",
        "NOW",
        "RISULTATI E CALENDARIO",
        "PROSSIME PARTITE",
        "GIRONE A",
        "GIRONE B",
        "GIRONE C",
        "SERIE C",
        "CALENDARIO",
        "STAGIONE 2026/2027",
    }

    for line in lines:
        normalized = _normalize(line)

        if normalized in ignored_exact:
            continue

        if re.fullmatch(
            r"\d+\s*-\s*\d+",
            normalized,
        ):
            continue

        if re.fullmatch(
            r"\d{1,2}:\d{2}",
            normalized,
        ):
            continue

        if re.fullmatch(
            r"\d+",
            normalized,
        ):
            continue

        if re.search(
            r"(?:GIO|VEN|SAB|DOM|LUN|MAR|MER)"
            r"\s+\d{1,2}\s+"
            r"[A-Z]{3}\s+"
            r"\d{1,2}:\d{2}",
            normalized,
        ):
            continue

        if normalized.startswith(
            "GIORNATA "
        ):
            continue

        if normalized.startswith(
            "IMAGE:"
        ):
            continue

        if len(normalized) < 3:
            continue

        cleaned.append(
            line
        )

    return cleaned


def _find_event_blocks(
    text: str,
) -> list[tuple[str, str, str]]:
    """
    Cerca blocchi calendario nel testo.

    Restituisce:
        (data_ora, squadra_casa, squadra_ospite)
    """

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    date_pattern = re.compile(
        r"^(?:"
        r"LUN|MAR|MER|GIO|VEN|SAB|DOM"
        r")\s+"
        r"\d{1,2}\s+"
        r"[A-ZÀÈÉÌÒÙ]{3}\s+"
        r"\d{1,2}:\d{2}$",
        re.IGNORECASE,
    )

    events: list[
        tuple[str, str, str]
    ] = []

    i = 0

    while i < len(lines):
        current = _normalize(
            lines[i]
        )

        if not date_pattern.match(
            current
        ):
            i += 1
            continue

        date_time = lines[i]

        candidate_lines = lines[
            i + 1:i + 12
        ]

        # Cerca il primo VS.
        vs_index = None

        for index, line in enumerate(
            candidate_lines
        ):
            if _normalize(line) == "VS":
                vs_index = index
                break

        if vs_index is not None:
            before = candidate_lines[
                :vs_index
            ]

            after = candidate_lines[
                vs_index + 1:
            ]

            home = _pick_team(
                before
            )

            away = _pick_team(
                after
            )

            if home and away:
                events.append(
                    (
                        date_time,
                        home,
                        away,
                    )
                )

                i += 1
                continue

        # Fallback per eventuali partite già concluse:
        # CASA / risultato / OSPITE.
        if len(candidate_lines) >= 3:
            home = candidate_lines[0]
            result = candidate_lines[1]
            away = candidate_lines[2]

            if (
                _looks_like_team(home)
                and re.fullmatch(
                    r"\d+\s*-\s*\d+",
                    _normalize(result),
                )
                and _looks_like_team(away)
            ):
                events.append(
                    (
                        date_time,
                        home,
                        away,
                    )
                )

        i += 1

    return events


def _looks_like_team(
    value: str,
) -> bool:
    normalized = _normalize(
        value
    )

    if normalized in {
        "VS",
        "SKY SPORT",
        "NOW",
    }:
        return False

    if re.fullmatch(
        r"\d+\s*-\s*\d+",
        normalized,
    ):
        return False

    if re.fullmatch(
        r"\d{1,2}:\d{2}",
        normalized,
    ):
        return False

    if len(normalized) < 3:
        return False

    return True


def _pick_team(
    values: list[str],
) -> Optional[str]:
    ignored = {
        "IMAGE",
        "IMAGE:",
        "SKY SPORT",
        "NOW",
        "SKY",
    }

    for value in values:
        candidate = value.strip()
        normalized = _normalize(candidate)

        if normalized in ignored:
            continue

        if _looks_like_team(candidate):
            return candidate

    return None


def _build_event(
    date_time: str,
    home: str,
    away: str,
    now: datetime,
) -> Optional[SerieCEvent]:
    start = _parse_date(
        date_time,
        now,
    )

    if start is None:
        return None

    # Generiamo solo oggi e domani.
    today = now.date()
    tomorrow = (
        now + timedelta(days=1)
    ).date()

    if start.date() not in {
        today,
        tomorrow,
    }:
        return None

    home_clean = home.strip()
    away_clean = away.strip()

    if not home_clean or not away_clean:
        return None

    home_id = (
        "serie_c_"
        + _slug(home_clean)
    )

    away_id = (
        "serie_c_"
        + _slug(away_clean)
    )

    event_key = (
        f"{start.strftime('%Y%m%d_%H%M')}_"
        f"{_slug(home_clean)}_"
        f"{_slug(away_clean)}"
    )

    end = start + timedelta(
        minutes=130
    )

    return SerieCEvent(
        source_event_id=event_key,
        competition_key="serie_c",
        competition_name="Serie C",
        sport="FOOTBALL",
        title=(
            f"{home_clean} - "
            f"{away_clean}"
        ),
        start_time=start,
        end_time=end,
        status="SCHEDULED",
        home_team_id=home_id,
        home_team_name=home_clean,
        home_team_short_name=home_clean,
        away_team_id=away_id,
        away_team_name=away_clean,
        away_team_short_name=away_clean,
    )


def _parse_page(
    html: str,
    now: datetime,
) -> list[SerieCEvent]:
    parser = _SerieCHtmlParser()

    parser.feed(html)

    text = parser.text()

    raw_events = _find_event_blocks(
        text
    )

    events: list[SerieCEvent] = []

    seen: set[str] = set()

    for (
        date_time,
        home,
        away,
    ) in raw_events:
        event = _build_event(
            date_time,
            home,
            away,
            now,
        )

        if event is None:
            continue

        if (
            event.source_event_id
            in seen
        ):
            continue

        seen.add(
            event.source_event_id
        )

        events.append(
            event
        )

    return events


def fetch_serie_c_events() -> list[SerieCEvent]:
    """
    Recupera gli eventi Serie C ufficiali
    per oggi e domani.

    La pagina ufficiale della Lega Serie C
    contiene già calendario e programmazione.
    """

    now = datetime.now(
        TIMEZONE
    )

    all_events: dict[
        str,
        SerieCEvent
    ] = {}

    for url in SERIE_C_URLS:
        try:
            print(
                f"[SERIE C] Download calendario: "
                f"{url}"
            )

            html = _download(
                url
            )

            events = _parse_page(
                html,
                now,
            )

            print(
                f"[SERIE C] Eventi trovati da "
                f"{url}: {len(events)}"
            )

            for event in events:
                all_events[
                    event.source_event_id
                ] = event

        except Exception as error:
            print(
                f"[SERIE C] Fonte non disponibile "
                f"{url}: {error}"
            )

    result = sorted(
        all_events.values(),
        key=lambda event: (
            event.start_time,
            event.home_team_name.lower(),
            event.away_team_name.lower(),
        ),
    )

    print(
        f"[SERIE C] Totale eventi oggi/domani: "
        f"{len(result)}"
    )

    return result


if __name__ == "__main__":
    events = fetch_serie_c_events()

    print()
    print(
        f"Serie C: {len(events)} eventi"
    )

    for event in events:
        print(
            event.start_time.strftime(
                "%Y-%m-%d %H:%M"
            ),
            "|",
            event.title,
        )
