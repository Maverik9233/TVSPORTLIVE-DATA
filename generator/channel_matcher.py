from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Iterable

from config import (
    CHANNELS_URL,
    REQUEST_TIMEOUT_SECONDS,
    USER_AGENT,
)
from liveonsat import LiveOnSatEvent


# ============================================================
# TVSPORTLIVE - CHANNEL MATCHER
#
# Legge channels.txt da Dropbox e collega i broadcaster
# trovati da LiveOnSat ai Channel definiti dall'utente.
#
# IMPORTANTE:
#
#   channels.txt = sorgente MANUALE dei canali e degli stream
#
# LiveOnSat NON fornisce gli URL di riproduzione.
#
# Il risultato di questo modulo è solamente:
#
#   broadcaster LiveOnSat
#          ↓
#   Channel.id
#
# Gli URL rimangono quelli presenti in channels.txt.
# ============================================================


@dataclass(frozen=True)
class ChannelSource:
    id: str
    url: str
    stream_type: str
    enabled: bool
    priority: int


@dataclass(frozen=True)
class Channel:
    id: str
    name: str
    country: str
    priority: int
    logo_url: str | None
    aliases: tuple[str, ...]
    enabled: bool
    sources: tuple[ChannelSource, ...]


@dataclass(frozen=True)
class ChannelMatch:
    broadcaster: str
    channel_id: str
    channel_name: str
    country: str
    score: int


# ============================================================
# HTTP
# ============================================================

def fetch_channels_json() -> dict:
    """
    Scarica channels.txt da Dropbox.

    Il file ha estensione .txt ma il contenuto deve essere
    JSON valido compatibile con ChannelsResponse.
    """

    request = urllib.request.Request(
        url=CHANNELS_URL,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/plain,*/*",
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
                    f"HTTP {response.status} "
                    f"durante il download di channels.txt"
                )

            raw_data = response.read()

    except urllib.error.HTTPError as error:

        raise RuntimeError(
            f"HTTP {error.code} "
            f"durante il download di channels.txt"
        ) from error

    except urllib.error.URLError as error:

        raise RuntimeError(
            "Errore di rete durante il download "
            f"di channels.txt: {error.reason}"
        ) from error

    try:

        text = raw_data.decode(
            "utf-8",
            errors="replace",
        )

        data = json.loads(
            text
        )

    except json.JSONDecodeError as error:

        raise RuntimeError(
            "channels.txt non contiene JSON valido."
        ) from error

    if not isinstance(
        data,
        dict,
    ):
        raise RuntimeError(
            "channels.txt deve contenere un oggetto JSON."
        )

    return data


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(
    value: str,
) -> str:
    """
    Normalizza un nome per il confronto.

    Esempio:

        Sky Sport Calcio HD
        SKY SPORT CALCIO

    diventano confrontabili.
    """

    value = value.strip().lower()

    replacements = {
        "à": "a",
        "á": "a",
        "è": "e",
        "é": "e",
        "ì": "i",
        "í": "i",
        "ò": "o",
        "ó": "o",
        "ù": "u",
        "ú": "u",
    }

    for source, target in replacements.items():
        value = value.replace(
            source,
            target,
        )

    value = re.sub(
        r"[\(\)\[\]\{\}]",
        " ",
        value,
    )

    value = re.sub(
        r"[_\-\/]+",
        " ",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def compact_text(
    value: str,
) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "",
        normalize_text(
            value
        ),
    )


# ============================================================
# HD / UHD / 4K NORMALIZATION
# ============================================================

def remove_quality_suffix(
    value: str,
) -> str:

    value = normalize_text(
        value
    )

    patterns = (
        r"\bhd\b",
        r"\bfhd\b",
        r"\bufhd\b",
        r"\buhd\b",
        r"\b4k\b",
        r"\b8k\b",
        r"\bitalia hd\b",
    )

    for pattern in patterns:

        value = re.sub(
            pattern,
            " ",
            value,
            flags=re.IGNORECASE,
        )

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


# ============================================================
# CHANNEL PARSING
# ============================================================

def parse_channel_source(
    data: dict,
) -> ChannelSource:

    source_id = str(
        data.get(
            "id",
            "",
        )
    ).strip()

    url = str(
        data.get(
            "url",
            "",
        )
    ).strip()

    stream_type = str(
        data.get(
            "type",
            "AUTO",
        )
    ).strip().upper()

    enabled = bool(
        data.get(
            "enabled",
            True,
        )
    )

    try:
        priority = int(
            data.get(
                "priority",
                0,
            )
        )
    except (
        TypeError,
        ValueError,
    ):
        priority = 0

    if not source_id:
        raise ValueError(
            "Channel source senza id."
        )

    return ChannelSource(
        id=source_id,
        url=url,
        stream_type=stream_type,
        enabled=enabled,
        priority=priority,
    )


def parse_channel(
    data: dict,
) -> Channel:

    channel_id = str(
        data.get(
            "id",
            "",
        )
    ).strip()

    name = str(
        data.get(
            "name",
            "",
        )
    ).strip()

    if not channel_id:
        raise ValueError(
            "Canale senza id."
        )

    if not name:
        raise ValueError(
            f"Il canale {channel_id} "
            "non ha un nome."
        )

    country = str(
        data.get(
            "country",
            "INTERNATIONAL",
        )
    ).strip().upper()

    try:
        priority = int(
            data.get(
                "priority",
                100,
            )
        )
    except (
        TypeError,
        ValueError,
    ):
        priority = 100

    logo_url = data.get(
        "logoUrl"
    )

    if logo_url is not None:
        logo_url = str(
            logo_url
        ).strip() or None

    aliases_data = data.get(
        "aliases",
        [],
    )

    if not isinstance(
        aliases_data,
        list,
    ):
        aliases_data = []

    aliases: list[str] = []

    for alias in aliases_data:

        if alias is None:
            continue

        alias_text = str(
            alias
        ).strip()

        if (
            alias_text
            and alias_text not in aliases
        ):
            aliases.append(
                alias_text
            )

    sources_data = data.get(
        "sources",
        [],
    )

    if not isinstance(
        sources_data,
        list,
    ):
        sources_data = []

    sources: list[ChannelSource] = []

    for source_data in sources_data:

        if not isinstance(
            source_data,
            dict,
        ):
            continue

        try:

            source = parse_channel_source(
                source_data
            )

        except ValueError as error:

            print(
                "[CHANNELS] "
                f"Source ignorata: {error}"
            )

            continue

        sources.append(
            source
        )

    return Channel(
        id=channel_id,
        name=name,
        country=country,
        priority=priority,
        logo_url=logo_url,
        aliases=tuple(
            aliases
        ),
        enabled=bool(
            data.get(
                "enabled",
                True,
            )
        ),
        sources=tuple(
            sources
        ),
    )


def load_channels() -> list[Channel]:
    """
    Carica e valida tutti i canali da channels.txt.
    """

    data = fetch_channels_json()

    channels_data = data.get(
        "channels",
        [],
    )

    if not isinstance(
        channels_data,
        list,
    ):
        raise RuntimeError(
            "Il campo 'channels' "
            "di channels.txt deve essere una lista."
        )

    channels: list[Channel] = []

    seen_ids: set[str] = set()

    for channel_data in channels_data:

        if not isinstance(
            channel_data,
            dict,
        ):
            continue

        try:

            channel = parse_channel(
                channel_data
            )

        except ValueError as error:

            print(
                "[CHANNELS] "
                f"Canale ignorato: {error}"
            )

            continue

        if channel.id in seen_ids:

            print(
                "[CHANNELS] "
                f"ID duplicato ignorato: "
                f"{channel.id}"
            )

            continue

        seen_ids.add(
            channel.id
        )

        channels.append(
            channel
        )

    print(
        "[CHANNELS] "
        f"Canali caricati: {len(channels)}"
    )

    return channels


# ============================================================
# MATCH SCORING
# ============================================================

def score_name_match(
    broadcaster: str,
    candidate: str,
) -> int:

    broadcaster_normalized = normalize_text(
        broadcaster
    )

    candidate_normalized = normalize_text(
        candidate
    )

    if not broadcaster_normalized:
        return 0

    if not candidate_normalized:
        return 0

    # Corrispondenza perfetta.
    if (
        broadcaster_normalized
        == candidate_normalized
    ):
        return 1000

    # Corrispondenza senza spazi/punteggiatura.
    if (
        compact_text(
            broadcaster
        )
        == compact_text(
            candidate
        )
    ):
        return 950

    broadcaster_base = remove_quality_suffix(
        broadcaster
    )

    candidate_base = remove_quality_suffix(
        candidate
    )

    # Esempio:
    #
    # Sky Sport Calcio HD
    # Sky Sport Calcio
    #
    if (
        broadcaster_base
        == candidate_base
    ):
        return 900

    if (
        compact_text(
            broadcaster_base
        )
        == compact_text(
            candidate_base
        )
    ):
        return 850

    # Una stringa completa contenuta nell'altra.
    if (
        broadcaster_normalized
        in candidate_normalized
    ):
        return 700

    if (
        candidate_normalized
        in broadcaster_normalized
    ):
        return 650

    broadcaster_compact = compact_text(
        broadcaster
    )

    candidate_compact = compact_text(
        candidate
    )

    if (
        broadcaster_compact
        and broadcaster_compact
        in candidate_compact
    ):
        return 600

    if (
        candidate_compact
        and candidate_compact
        in broadcaster_compact
    ):
        return 550

    return 0


# ============================================================
# SINGLE CHANNEL MATCH
# ============================================================

def find_best_channel(
    broadcaster: str,
    channels: Iterable[Channel],
) -> ChannelMatch | None:

    best_match: ChannelMatch | None = None

    for channel in channels:

        if not channel.enabled:
            continue

        # ----------------------------------------------------
        # Nome principale
        # ----------------------------------------------------

        score = score_name_match(
            broadcaster=broadcaster,
            candidate=channel.name,
        )

        if score > 0:

            candidate = ChannelMatch(
                broadcaster=broadcaster,
                channel_id=channel.id,
                channel_name=channel.name,
                country=channel.country,
                score=score,
            )

            if (
                best_match is None
                or candidate.score
                > best_match.score
            ):
                best_match = candidate

        # ----------------------------------------------------
        # Alias
        # ----------------------------------------------------

        for alias in channel.aliases:

            alias_score = score_name_match(
                broadcaster=broadcaster,
                candidate=alias,
            )

            if alias_score <= 0:
                continue

            # Un alias è leggermente meno forte
            # di una corrispondenza perfetta
            # sul nome principale.
            alias_score -= 10

            candidate = ChannelMatch(
                broadcaster=broadcaster,
                channel_id=channel.id,
                channel_name=channel.name,
                country=channel.country,
                score=alias_score,
            )

            if (
                best_match is None
                or candidate.score
                > best_match.score
            ):
                best_match = candidate

    return best_match


# ============================================================
# MULTIPLE BROADCASTERS
# ============================================================

def match_broadcasters(
    broadcasters: Iterable[str],
    channels: Iterable[Channel],
) -> list[ChannelMatch]:

    channels_list = list(
        channels
    )

    matches: list[ChannelMatch] = []

    already_matched_ids: set[str] = set()

    for broadcaster in broadcasters:

        broadcaster = broadcaster.strip()

        if not broadcaster:
            continue

        match = find_best_channel(
            broadcaster=broadcaster,
            channels=channels_list,
        )

        if match is None:

            print(
                "[MATCH] "
                f"Nessun canale trovato per: "
                f"{broadcaster}"
            )

            continue

        # Evitiamo di aggiungere lo stesso Channel.id
        # più volte allo stesso evento.
        if match.channel_id in already_matched_ids:
            continue

        already_matched_ids.add(
            match.channel_id
        )

        matches.append(
            match
        )

        print(
            "[MATCH] "
            f"{broadcaster} -> "
            f"{match.channel_name} "
            f"[{match.channel_id}] "
            f"score={match.score}"
        )

    return matches


# ============================================================
# EVENT MATCHING
# ============================================================

def match_liveonsat_event(
    event: LiveOnSatEvent,
    channels: Iterable[Channel],
) -> list[ChannelMatch]:

    return match_broadcasters(
        broadcasters=event.broadcasters,
        channels=channels,
    )


def match_liveonsat_events(
    events: Iterable[LiveOnSatEvent],
    channels: Iterable[Channel],
) -> dict[str, list[ChannelMatch]]:

    channels_list = list(
        channels
    )

    result: dict[
        str,
        list[ChannelMatch],
    ] = {}

    for event in events:

        matches = match_liveonsat_event(
            event=event,
            channels=channels_list,
        )

        key = (
            f"{event.title}|"
            f"{event.start_time}"
        )

        result[key] = matches

    return result


# ============================================================
# PUBLIC ENTRY POINT
# ============================================================

def get_channels_for_broadcasters(
    broadcasters: Iterable[str],
) -> list[ChannelMatch]:
    """
    Funzione di comodo utilizzata dal generatore principale.
    """

    channels = load_channels()

    return match_broadcasters(
        broadcasters=broadcasters,
        channels=channels,
    )
