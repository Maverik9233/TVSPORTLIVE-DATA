from __future__ import annotations

import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from html import unescape
from typing import Iterable

from config import REQUEST_TIMEOUT_SECONDS, TIMEZONE, USER_AGENT


# ============================================================
# TVSPORTLIVE - LIVEONSAT
#
# LiveOnSat viene utilizzato ESCLUSIVAMENTE come fonte per
# sapere quali broadcaster trasmettono un determinato evento.
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
# URL PRINCIPALI
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

def fetch_html(
    url: str,
) -> str:

    request = urllib.request.Request(
        url=url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,"
                "application/xhtml+xml"
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

    try:

        return data.decode(
            "utf-8",
            errors="replace",
        )

    except Exception as error:

        raise RuntimeError(
            f"Impossibile decodificare "
            f"la pagina LiveOnSat: {url}"
        ) from error


# ============================================================
# HTML CLEANING
# ============================================================

def html_to_text(
    html: str,
) -> str:

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

    text = re.sub(
        r"(?i)<br\s*/?>",
        "\n",
        text,
    )

    text = re.sub(
        r"(?i)</(?:div|p|li|tr|td|th|h1|h2|h3|h4|h5|h6)>",
        "\n",
        text,
    )

    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
    )

    text = unescape(
        text
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
            lines.append(
                line
            )

    return "\n".join(
        lines
    )


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_text(
    value: str,
) -> str:

    value = unescape(
        value
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


def normalize_broadcaster(
    value: str,
) -> str | None:

    value = normalize_text(
        value
    )

    if not value:
        return None

    # Rimuoviamo solamente i marcatori utilizzati da
    # LiveOnSat per indicare restrizioni/app/streaming.
    #
    # NON eliminiamo il nome del broadcaster.
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

    value = normalize_text(
        value
    )

    return value or None


# ============================================================
# BROADCASTER FILTER
# ============================================================

def looks_like_broadcaster(
    line: str,
) -> bool:

    line = normalize_text(
        line
    )

    if not line:
        return False

    lower = line.lower()

    # Elementi strutturali della pagina.
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
        "st:",
        "round ",
        "week ",
        "girone ",
    )

    if any(
        item in lower
        for item in blocked
    ):
        return False

    # Un broadcaster deve avere una lunghezza ragionevole.
    if len(line) < 2 or len(line) > 120:
        return False

    # Una data pura non è un broadcaster.
    if re.fullmatch(
        r"\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}",
        line,
    ):
        return False

    # Gli orari non sono broadcaster.
    if re.fullmatch(
        r"\d{1,2}:\d{2}",
        line,
    ):
        return False

    return True


# ============================================================
# MATCH TITLE
# ============================================================

def normalize_event_title(
    title: str,
) -> str:

    title = normalize_text(
        title
    )

    title = title.lower()

    title = title.replace(
        " v ",
        " - ",
    )

    title = title.replace(
        " vs ",
        " - ",
    )

    title = title.replace(
        " vs. ",
        " - ",
    )

    title = re.sub(
        r"\s*-\s*",
        " - ",
        title,
    )

    return title.strip()


def event_titles_match(
    first: str,
    second: str,
) -> bool:

    a = normalize_event_title(
        first
    )

    b = normalize_event_title(
        second
    )

    if not a or not b:
        return False

    if a == b:
        return True

    if a in b or b in a:
        return True

    return False


# ============================================================
# EVENT EXTRACTION
# ============================================================

_EVENT_PATTERN = re.compile(
    r"^(?P<competition>.+?)"
    r"\s+(?:Image\s+)?"
    r"(?P<title>[^|]+?)"
    r"\s+(?:Image\s+)?"
    r"ST:\s*(?P<time>\d{1,2}:\d{2})$",
    re.IGNORECASE,
)


def parse_event_header(
    line: str,
) -> tuple[
    str,
    str,
    str,
] | None:

    line = normalize_text(
        line
    )

    match = _EVENT_PATTERN.match(
        line
    )

    if not match:
        return None

    competition = normalize_text(
        match.group(
            "competition"
        )
    )

    title = normalize_text(
        match.group(
            "title"
        )
    )

    start_time = normalize_text(
        match.group(
            "time"
        )
    )

    if not competition:
        return None

    if not title:
        return None

    if not start_time:
        return None

    return (
        competition,
        title,
        start_time,
    )


# ============================================================
# BROADCASTER COLLECTION
# ============================================================

def collect_broadcasters(
    lines: Iterable[str],
    start_index: int,
) -> tuple[str, ...]:

    broadcasters: list[str] = []

    for line in lines:

        line = normalize_text(
            line
        )

        if not line:
            continue

        # Il prossimo evento interrompe la raccolta.
        if parse_event_header(
            line
        ) is not None:
            break

        if not looks_like_broadcaster(
            line
        ):
            continue

        broadcaster = normalize_broadcaster(
            line
        )

        if not broadcaster:
            continue

        if broadcaster not in broadcasters:
            broadcasters.append(
                broadcaster
            )

    return tuple(
        broadcasters
    )


# ============================================================
# PAGE PARSER
# ============================================================

def parse_liveonsat_page(
    html: str,
) -> list[LiveOnSatEvent]:

    text = html_to_text(
        html
    )

    lines = [
        normalize_text(line)
        for line in text.splitlines()
        if normalize_text(line)
    ]

    result: list[LiveOnSatEvent] = []

    index = 0

    while index < len(lines):

        parsed = parse_event_header(
            lines[index]
        )

        if parsed is None:
            index += 1
            continue

        (
            competition,
            title,
            start_time,
        ) = parsed

        broadcasters = collect_broadcasters(
            lines=lines[index + 1:],
            start_index=index + 1,
        )

        result.append(
            LiveOnSatEvent(
                title=title,
                start_time=start_time,
                competition=competition,
                broadcasters=broadcasters,
            )
        )

        index += 1

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
            event.competition,
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
# MATCHING WITH SPORTS EVENTS
# ============================================================

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

        if (
            candidate_title in normalized_title
            or normalized_title in candidate_title
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
# PUBLIC FETCH FUNCTIONS
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
    """
    Recupera gli eventi LiveOnSat disponibili.

    Se una sezione non è raggiungibile, viene saltata.
    Nessun evento viene inventato.
    """

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
