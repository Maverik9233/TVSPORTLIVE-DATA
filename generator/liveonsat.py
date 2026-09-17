from __future__ import annotations

import re
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Iterable

from config import REQUEST_TIMEOUT_SECONDS, USER_AGENT


# ============================================================
# TVSPORTLIVE - LIVEONSAT
#
# LiveOnSat viene utilizzato come fonte per associare gli
# eventi sportivi ai broadcaster televisivi.
#
# NON vengono recuperati:
#   - link streaming
#   - player
#   - URL video
#   - sorgenti IPTV
#
# Gli URL reali dei canali rimangono esclusivamente
# all'interno di channels.txt.
# ============================================================


@dataclass(frozen=True)
class LiveOnSatEvent:
    title: str
    start_time: str
    competition: str
    broadcasters: tuple[str, ...]


# ============================================================
# URL
# ============================================================

LIVEONSAT_ITALY_FOOTBALL_URL = (
    "https://www.liveonsat.com/"
    "europe-italy-all-football.php"
)

LIVEONSAT_INTERNATIONAL_FOOTBALL_URL = (
    "https://www.liveonsat.com/"
    "international-all-football.php"
)

LIVEONSAT_FORMULA_1_URL = (
    "https://www.liveonsat.com/"
    "x-formula1.php"
)


# ============================================================
# HTTP
# ============================================================

def fetch_html(url: str) -> str:
    request = urllib.request.Request(
        url=url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,"
                "application/xhtml+xml,"
                "application/xml;q=0.9,"
                "*/*;q=0.8"
            ),
            "Accept-Language": (
                "it-IT,it;q=0.9,en;q=0.8"
            ),
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:

            if response.status < 200 or response.status >= 300:
                raise RuntimeError(
                    f"HTTP {response.status} da LiveOnSat: {url}"
                )

            data = response.read()

    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"HTTP {error.code} da LiveOnSat: {url}"
        ) from error

    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Errore di rete verso LiveOnSat: "
            f"{error.reason}"
        ) from error

    return data.decode(
        "utf-8",
        errors="replace",
    )


# ============================================================
# HTML -> TEXT
# ============================================================

def html_to_text(html: str) -> str:
    text = html

    text = re.sub(
        r"(?is)<script\b[^>]*>.*?</script>",
        " ",
        text,
    )

    text = re.sub(
        r"(?is)<style\b[^>]*>.*?</style>",
        " ",
        text,
    )

    text = re.sub(
        r"(?is)<noscript\b[^>]*>.*?</noscript>",
        " ",
        text,
    )

    # Le celle delle tabelle sono molto importanti:
    # LiveOnSat separa spesso competizione, partita,
    # orario e broadcaster in celle HTML differenti.
    text = re.sub(
        r"(?i)</?(?:td|th|tr|div|p|li|h1|h2|h3|h4|h5|h6)"
        r"\b[^>]*>",
        "\n",
        text,
    )

    text = re.sub(
        r"(?i)<br\s*/?>",
        "\n",
        text,
    )

    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
    )

    text = re.sub(
        r"&#x([0-9a-fA-F]+);",
        lambda match: chr(
            int(match.group(1), 16)
        ),
        text,
    )

    text = re.sub(
        r"&#([0-9]+);",
        lambda match: chr(
            int(match.group(1))
        ),
        text,
    )

    text = text.replace(
        "&nbsp;",
        " ",
    )

    text = text.replace(
        "\xa0",
        " ",
    )

    lines: list[str] = []

    for line in text.splitlines():
        line = re.sub(
            r"\s+",
            " ",
            line,
        ).strip()

        if line:
            lines.append(line)

    return "\n".join(lines)


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_text(value: str) -> str:
    value = str(value)

    value = (
        unicodedata
        .normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
    )

    value = value.replace(
        "\xa0",
        " ",
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def normalize_event_title(title: str) -> str:
    title = normalize_text(title).casefold()

    # ESPN può utilizzare "at", LiveOnSat utilizza
    # normalmente "v".
    title = re.sub(
        r"\s+\bat\b\s+",
        " - ",
        title,
    )

    title = re.sub(
        r"\s+\bvs?\.\s+",
        " - ",
        title,
    )

    title = re.sub(
        r"\s+\bvs?\s+",
        " - ",
        title,
    )

    title = re.sub(
        r"\s+-\s+",
        " - ",
        title,
    )

    title = re.sub(
        r"\s*-\s*",
        " - ",
        title,
    )

    title = re.sub(
        r"\s+",
        " ",
        title,
    )

    return title.strip()


# ============================================================
# BROADCASTER
# ============================================================

def normalize_broadcaster(
    value: str,
) -> str | None:

    value = normalize_text(value)

    if not value:
        return None

    # Estrae il nome canale da righe JS tipo:
    # CAPTION, 'Sky Go Italy [online] – 2026-09-19...');">Sky Go Italy [online]
    caption_match = re.search(
        r"CAPTION,\s*'([^']+)'",
        value,
        flags=re.IGNORECASE,
    )
    if caption_match:
        value = caption_match.group(1)
        # Rimuove timestamp nel caption
        value = re.sub(
            r"\s*[&ndash;\-–—]+\s*\d{4}-\d{2}-\d{2}.*$",
            "",
            value,
        )

    # Se c'è testo dopo il tag di chiusura JS, preferiscilo
    tail = re.search(
        r'">\s*([^<"\n]+)\s*$',
        value,
    )
    if tail:
        candidate = tail.group(1).strip()
        if candidate and len(candidate) > 2:
            value = candidate

    # Marcatori usati da LiveOnSat per indicare
    # restrizioni/app/streaming.
    value = re.sub(
        r"\s*\(\s*\$\/geo\/R\s*\)",
        "",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(
        r"\s*\(\s*geo\/R\s*\)",
        "",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(
        r"\s*\(\s*\$\/geo\s*\)",
        "",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(
        r"\s*\[online\]",
        "",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(
        r"\s*\[app\]",
        "",
        value,
        flags=re.IGNORECASE,
    )

    # Rimuove emoji e residui HTML
    value = re.sub(r"[📺📡🔴▶️]+", "", value)
    value = re.sub(r"&[a-z]+;", " ", value, flags=re.IGNORECASE)

    value = re.sub(r"\s+", " ", value)

    cleaned = value.strip()

    if not cleaned:
        return None

    # Scarta ancora rumore tecnico
    lower = cleaned.casefold()
    if lower in {
        "pos", "satellite", "freq", "symbol", "encryption",
        "liveonsat.com", "* iptv/stream", "iptv/stream",
    }:
        return None

    if re.fullmatch(r"[\d\.\,\°\s\*]+", cleaned):
        return None

    # Date tipo "Friday, 18th September"
    if re.search(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", lower):
        return None

    # Frequenze sat tipo "11.512 H" / "30000 - 3/4"
    if re.fullmatch(r"\d{1,2}\.\d{1,3}\s*[HV]", cleaned, re.I):
        return None
    if re.fullmatch(r"\d{4,5}\s*-\s*\d/\d", cleaned):
        return None
    if re.search(r"\bnagra|\bviaccess|\birdeto|\bconax|\bhd\s+nagra", lower):
        return None
    if lower.startswith("eutelsat") or lower.startswith("hotbird") or lower.startswith("astra"):
        return None

    return cleaned


def looks_like_broadcaster(line: str) -> bool:
    line = normalize_text(line)

    if not line:
        return False

    lower = line.casefold()

    # Header tecnici e rumore della tabella LiveOnSat
    blocked_exact = {
        "pos", "satellite", "freq", "symbol", "encryption",
        "liveonsat.com", "liveonsat", "* iptv/stream",
        "iptv/stream", "0.0&deg;", "0.000",
    }

    if lower in blocked_exact:
        return False

    blocked = (
        "liveonsat",
        "website last updated",
        "please note",
        "timezone =",
        "members",
        "football",
        "motor sport",
        "basketball",
        "no schedules",
        "image",
        "round ",
        "week ",
        "girone ",
        "st:",
        "onmouseout",
        "onmouseover",
        "return nd",
    )

    # Le righe CAPTION contengono il nome canale: lasciamole passare
    # (normalize_broadcaster le pulisce).
    if "caption" in lower and ("sky" in lower or "rai" in lower or "dazn" in lower or "now" in lower or "sport" in lower):
        return True

    if any(item in lower for item in blocked):
        return False

    if len(line) < 2 or len(line) > 120:
        return False

    if re.fullmatch(r"\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}", line):
        return False

    if re.fullmatch(r"\d{1,2}:\d{2}", line):
        return False

    # Solo numeri / gradi / frequenze
    if re.fullmatch(r"[\d\.\,\°\&deg;\s\*]+", line):
        return False

    return True


# ============================================================
# EVENT HEADER
# ============================================================

_SINGLE_LINE_EVENT_PATTERN = re.compile(
    r"^(?P<competition>.+?)"
    r"\s+(?:Image\s+)*"
    r"(?P<title>[^|]+?)"
    r"\s+(?:Image\s+)*"
    r"ST:\s*(?P<time>\d{1,2}:\d{2})$",
    re.IGNORECASE,
)


def _clean_event_part(value: str) -> str:
    value = normalize_text(value)

    value = re.sub(
        r"\bImage\b",
        " ",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def parse_event_header(
    lines: list[str],
    index: int,
) -> tuple[str, str, str, int] | None:

    if index < 0 or index >= len(lines):
        return None

    current = _clean_event_part(
        lines[index]
    )

    # --------------------------------------------------------
    # Formato compatto:
    #
    # Competition ... Title ... ST: 18:00
    # --------------------------------------------------------

    match = _SINGLE_LINE_EVENT_PATTERN.match(
        current
    )

    if match:
        competition = _clean_event_part(
            match.group("competition")
        )

        title = _clean_event_part(
            match.group("title")
        )

        start_time = match.group(
            "time"
        ).strip()

        if competition and title:
            return (
                competition,
                title,
                start_time,
                index + 1,
            )

    # --------------------------------------------------------
    # Formato LiveOnSat più comune:
    #
    # Competition
    # Title
    # ST: 18:00
    # --------------------------------------------------------

    if index + 2 < len(lines):

        competition = _clean_event_part(
            lines[index]
        )

        title = _clean_event_part(
            lines[index + 1]
        )

        time_line = _clean_event_part(
            lines[index + 2]
        )

        time_match = re.search(
            r"\bST:\s*(\d{1,2}:\d{2})\b",
            time_line,
            flags=re.IGNORECASE,
        )

        if (
            competition
            and title
            and time_match
            and not looks_like_broadcaster(
                competition
            )
        ):
            return (
                competition,
                title,
                time_match.group(1),
                index + 3,
            )

    # --------------------------------------------------------
    # Variante:
    #
    # Competition
    # Title ST: 18:00
    # --------------------------------------------------------

    if index + 1 < len(lines):

        competition = _clean_event_part(
            lines[index]
        )

        second_line = _clean_event_part(
            lines[index + 1]
        )

        time_match = re.search(
            r"\bST:\s*(\d{1,2}:\d{2})\b",
            second_line,
            flags=re.IGNORECASE,
        )

        if (
            competition
            and time_match
        ):
            title = _clean_event_part(
                second_line[
                    :time_match.start()
                ]
            )

            if title:
                return (
                    competition,
                    title,
                    time_match.group(1),
                    index + 2,
                )

    return None


# ============================================================
# BROADCASTER COLLECTION
# ============================================================

def collect_broadcasters(
    lines: list[str],
    start_index: int,
) -> tuple[str, ...]:

    broadcasters: list[str] = []

    index = start_index

    while index < len(lines):

        line = normalize_text(
            lines[index]
        )

        if not line:
            index += 1
            continue

        # Se incontriamo l'inizio di un nuovo evento,
        # termina la raccolta del precedente.
        if parse_event_header(
            lines,
            index,
        ) is not None:
            break

        if looks_like_broadcaster(line):

            broadcaster = normalize_broadcaster(
                line
            )

            if (
                broadcaster
                and broadcaster not in broadcasters
            ):
                broadcasters.append(
                    broadcaster
                )

        index += 1

    return tuple(
        broadcasters
    )


# ============================================================
# PAGE PARSER
# ============================================================

def parse_liveonsat_page(
    html: str,
) -> list[LiveOnSatEvent]:

    text = html_to_text(html)

    lines = [
        normalize_text(line)
        for line in text.splitlines()
        if normalize_text(line)
    ]

    result: list[LiveOnSatEvent] = []

    index = 0

    while index < len(lines):

        parsed = parse_event_header(
            lines,
            index,
        )

        if parsed is None:
            index += 1
            continue

        (
            competition,
            title,
            start_time,
            next_index,
        ) = parsed

        broadcasters = collect_broadcasters(
            lines=lines,
            start_index=next_index,
        )

        result.append(
            LiveOnSatEvent(
                title=title,
                start_time=start_time,
                competition=competition,
                broadcasters=broadcasters,
            )
        )

        # Saltiamo direttamente il blocco header.
        index = next_index

    return deduplicate_liveonsat_events(
        result
    )


# ============================================================
# DEDUPLICATION
# ============================================================

def deduplicate_liveonsat_events(
    events: list[LiveOnSatEvent],
) -> list[LiveOnSatEvent]:

    unique: dict[
        tuple[str, str, str],
        LiveOnSatEvent,
    ] = {}

    for event in events:

        key = (
            normalize_event_title(
                event.title
            ),
            event.start_time,
            normalize_text(
                event.competition
            ).casefold(),
        )

        if key not in unique:
            unique[key] = event
            continue

        existing = unique[key]

        broadcasters = list(
            existing.broadcasters
        )

        for broadcaster in event.broadcasters:
            if broadcaster not in broadcasters:
                broadcasters.append(
                    broadcaster
                )

        unique[key] = LiveOnSatEvent(
            title=existing.title,
            start_time=existing.start_time,
            competition=existing.competition,
            broadcasters=tuple(
                broadcasters
            ),
        )

    return list(
        unique.values()
    )


# ============================================================
# MATCHING
# ============================================================

def _team_parts_match(first: str, second: str) -> bool:
    """Confronta due nomi squadra ignorando differenze minori."""
    a = normalize_text(first).casefold()
    b = normalize_text(second).casefold()

    if not a or not b:
        return False

    if a == b:
        return True

    if a in b or b in a:
        return True

    a_tokens = set(re.findall(r"[a-z0-9]+", a))
    b_tokens = set(re.findall(r"[a-z0-9]+", b))

    if not a_tokens or not b_tokens:
        return False

    # Evita falsi positivi con token troppo generici.
    meaningful_a = {token for token in a_tokens if len(token) >= 3}
    meaningful_b = {token for token in b_tokens if len(token) >= 3}

    if not meaningful_a or not meaningful_b:
        return False

    common = meaningful_a & meaningful_b

    return (
        len(common) >= 1
        and (
            common == meaningful_a
            or common == meaningful_b
            or len(common) >= 2
        )
    )


def event_titles_match(
    first: str,
    second: str,
) -> bool:
    """
    Confronta i titoli degli eventi anche quando le due fonti
    usano l'ordine inverso delle squadre.

    Esempio:
        ESPN:       "AFC Bournemouth at Real Sociedad"
        LiveOnSat:  "Real Sociedad v Bournemouth"
    """
    a = normalize_event_title(first)
    b = normalize_event_title(second)

    if not a or not b:
        return False

    if a == b:
        return True

    if a in b or b in a:
        return True

    a_parts = [
        part.strip()
        for part in a.split("-")
        if part.strip()
    ]

    b_parts = [
        part.strip()
        for part in b.split("-")
        if part.strip()
    ]

    if len(a_parts) != 2 or len(b_parts) != 2:
        return False

    # Ordine normale: casa -> trasferta.
    if (
        _team_parts_match(a_parts[0], b_parts[0])
        and _team_parts_match(a_parts[1], b_parts[1])
    ):
        return True

    # Ordine invertito tra le due fonti.
    if (
        _team_parts_match(a_parts[0], b_parts[1])
        and _team_parts_match(a_parts[1], b_parts[0])
    ):
        return True

    return False

def find_broadcasters_for_event(
    event_title: str,
    events: Iterable[LiveOnSatEvent],
) -> tuple[str, ...]:

    normalized_title = normalize_event_title(
        event_title
    )

    if not normalized_title:
        return ()

    exact_matches: list[
        LiveOnSatEvent
    ] = []

    partial_matches: list[
        LiveOnSatEvent
    ] = []

    for candidate in events:

        candidate_title = normalize_event_title(
            candidate.title
        )

        if candidate_title == normalized_title:
            exact_matches.append(
                candidate
            )
            continue

        if event_titles_match(
            event_title,
            candidate.title,
        ):
            partial_matches.append(
                candidate
            )

    matches = (
        exact_matches
        if exact_matches
        else partial_matches
    )

    broadcasters: list[str] = []

    for match in matches:
        for broadcaster in match.broadcasters:

            if broadcaster not in broadcasters:
                broadcasters.append(
                    broadcaster
                )

    return tuple(
        broadcasters
    )


# ============================================================
# FETCHERS
# ============================================================

def fetch_italy_football_events() -> list[LiveOnSatEvent]:

    print(
        "[LIVEONSAT] "
        "Download calendario calcio Italia..."
    )

    html = fetch_html(
        LIVEONSAT_ITALY_FOOTBALL_URL
    )

    events = parse_liveonsat_page(
        html
    )

    print(
        "[LIVEONSAT] "
        f"Eventi calcio Italia trovati: "
        f"{len(events)}"
    )

    return events


def fetch_international_football_events() -> list[LiveOnSatEvent]:

    print(
        "[LIVEONSAT] "
        "Download calendario calcio internazionale..."
    )

    html = fetch_html(
        LIVEONSAT_INTERNATIONAL_FOOTBALL_URL
    )

    events = parse_liveonsat_page(
        html
    )

    print(
        "[LIVEONSAT] "
        f"Eventi calcio internazionale trovati: "
        f"{len(events)}"
    )

    return events


def fetch_formula_1_events() -> list[LiveOnSatEvent]:

    print(
        "[LIVEONSAT] "
        "Download calendario Formula 1..."
    )

    html = fetch_html(
        LIVEONSAT_FORMULA_1_URL
    )

    events = parse_liveonsat_page(
        html
    )

    print(
        "[LIVEONSAT] "
        f"Eventi Formula 1 trovati: "
        f"{len(events)}"
    )

    return events


# ============================================================
# PUBLIC ENTRY POINT
# ============================================================

def get_liveonsat_events() -> list[LiveOnSatEvent]:

    all_events: list[LiveOnSatEvent] = []

    loaders = (
        (
            "Italy Football",
            fetch_italy_football_events,
        ),
        (
            "International Football",
            fetch_international_football_events,
        ),
        (
            "Formula 1",
            fetch_formula_1_events,
        ),
    )

    for name, loader in loaders:

        try:

            events = loader()

            all_events.extend(
                events
            )

        except Exception as error:

            print(
                "[LIVEONSAT] "
                f"{name} non disponibile: "
                f"{error}"
            )

    result = deduplicate_liveonsat_events(
        all_events
    )

    print(
        "[LIVEONSAT] "
        f"Totale eventi LiveOnSat: "
        f"{len(result)}"
    )

    return result
