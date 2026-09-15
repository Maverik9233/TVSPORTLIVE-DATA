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


# ============================================================
# TVSPORTLIVE - CHANNEL MATCHER
#
# Scarica channels.txt dal repository GitHub e trasforma
# i dati JSON in oggetti Channel.
#
# Mantiene compatibilità con event_builder.py:
#
#   Channel
#   ChannelMatch
#   load_channels()
#   find_best_channel()
#   match_broadcasters()
#   match_liveonsat_event()
#   match_liveonsat_events()
# ============================================================


# ============================================================
# CHANNEL
# ============================================================

@dataclass(frozen=True)
class Channel:
    id: str
    name: str
    country: str = "INTERNATIONAL"
    priority: int = 100
    aliases: tuple[str, ...] = ()


# ============================================================
# CHANNEL MATCH
# ============================================================

@dataclass(frozen=True)
class ChannelMatch:
    channel_id: str
    channel_name: str
    score: int


# ============================================================
# DOWNLOAD
# ============================================================

def _download_channels() -> str:
    request = urllib.request.Request(
        CHANNELS_URL,
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

            return response.read().decode(
                "utf-8",
                errors="replace",
            )

    except urllib.error.HTTPError as error:

        body = error.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            "Impossibile scaricare channels.txt: "
            f"HTTP {error.code} - {body[:500]}"
        ) from error

    except urllib.error.URLError as error:

        raise RuntimeError(
            "Impossibile raggiungere channels.txt: "
            f"{error}"
        ) from error


# ============================================================
# LOAD CHANNELS
# ============================================================

def load_channels() -> list[Channel]:
    raw_text = _download_channels()

    try:
        data = json.loads(raw_text)

    except json.JSONDecodeError as error:

        raise RuntimeError(
            "channels.txt non contiene JSON valido."
        ) from error

    if not isinstance(data, dict):

        raise RuntimeError(
            "channels.txt deve contenere "
            "un oggetto JSON."
        )

    channels_data = data.get("channels")

    if not isinstance(channels_data, list):

        raise RuntimeError(
            "channels.txt non contiene "
            "un array 'channels' valido."
        )

    channels: list[Channel] = []

    for item in channels_data:

        if not isinstance(item, dict):
            continue

        channel_id = str(
            item.get("id", "")
        ).strip()

        channel_name = str(
            item.get("name", "")
        ).strip()

        if not channel_id or not channel_name:
            continue

        country = str(
            item.get(
                "country",
                "INTERNATIONAL",
            )
        ).strip()

        if not country:
            country = "INTERNATIONAL"

        try:
            priority = int(
                item.get(
                    "priority",
                    100,
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            priority = 100

        aliases_data = item.get(
            "aliases",
            [],
        )

        aliases: list[str] = []

        if isinstance(
            aliases_data,
            list,
        ):

            for alias in aliases_data:

                if not isinstance(
                    alias,
                    str,
                ):
                    continue

                alias = alias.strip()

                if alias:
                    aliases.append(alias)

        elif isinstance(
            aliases_data,
            str,
        ):

            alias = aliases_data.strip()

            if alias:
                aliases.append(alias)

        channels.append(
            Channel(
                id=channel_id,
                name=channel_name,
                country=country,
                priority=priority,
                aliases=tuple(
                    aliases
                ),
            )
        )

    return channels


# ============================================================
# NORMALIZATION
# ============================================================

def _normalize(
    value: str,
) -> str:

    value = value.lower().strip()

    value = (
        value
        .replace("à", "a")
        .replace("á", "a")
        .replace("â", "a")
        .replace("ä", "a")
        .replace("ã", "a")
        .replace("å", "a")
        .replace("è", "e")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("ë", "e")
        .replace("ì", "i")
        .replace("í", "i")
        .replace("î", "i")
        .replace("ï", "i")
        .replace("ò", "o")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("ö", "o")
        .replace("õ", "o")
        .replace("ù", "u")
        .replace("ú", "u")
        .replace("û", "u")
        .replace("ü", "u")
        .replace("ç", "c")
        .replace("ñ", "n")
    )

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value,
    )

    return " ".join(
        value.split()
    )


def _compact(
    value: str,
) -> str:

    return _normalize(
        value
    ).replace(
        " ",
        "",
    )


# ============================================================
# CHANNEL NAMES
# ============================================================

def _channel_names(
    channel: Channel,
) -> tuple[str, ...]:

    names: list[str] = [
        channel.name
    ]

    names.extend(
        channel.aliases
    )

    return tuple(
        name
        for name in names
        if isinstance(
            name,
            str,
        )
        and name.strip()
    )


# ============================================================
# MATCH SCORE
# ============================================================

def _match_score(
    broadcaster: str,
    channel: Channel,
) -> int:

    broadcaster_normalized = _normalize(
        broadcaster
    )

    broadcaster_compact = _compact(
        broadcaster
    )

    if not broadcaster_normalized:
        return 0

    best_score = 0

    for channel_name in _channel_names(
        channel
    ):

        channel_normalized = _normalize(
            channel_name
        )

        channel_compact = _compact(
            channel_name
        )

        if not channel_normalized:
            continue

        # ----------------------------------------------------
        # Corrispondenza esatta
        # ----------------------------------------------------

        if (
            broadcaster_normalized
            == channel_normalized
        ):

            best_score = max(
                best_score,
                100,
            )

            continue

        # ----------------------------------------------------
        # Corrispondenza esatta senza spazi
        # ----------------------------------------------------

        if (
            broadcaster_compact
            == channel_compact
        ):

            best_score = max(
                best_score,
                95,
            )

            continue

        # ----------------------------------------------------
        # Una stringa contiene l'altra
        # ----------------------------------------------------

        if (
            broadcaster_normalized
            in channel_normalized
            or channel_normalized
            in broadcaster_normalized
        ):

            best_score = max(
                best_score,
                80,
            )

            continue

        # ----------------------------------------------------
        # Contenimento senza spazi
        # ----------------------------------------------------

        if (
            broadcaster_compact
            in channel_compact
            or channel_compact
            in broadcaster_compact
        ):

            best_score = max(
                best_score,
                70,
            )

    return best_score


# ============================================================
# FIND BEST CHANNEL
# ============================================================

def find_best_channel(
    broadcaster: str,
    channels: Iterable[Channel],
) -> ChannelMatch | None:

    best_match: ChannelMatch | None = None

    for channel in channels:

        score = _match_score(
            broadcaster=broadcaster,
            channel=channel,
        )

        if score <= 0:
            continue

        candidate = ChannelMatch(
            channel_id=channel.id,
            channel_name=channel.name,
            score=score,
        )

        if (
            best_match is None
            or candidate.score
            > best_match.score
        ):

            best_match = candidate

    return best_match


# ============================================================
# MATCH BROADCASTERS
# ============================================================

def match_broadcasters(
    broadcasters: Iterable[str],
    channels: Iterable[Channel],
) -> list[ChannelMatch]:

    channels_list = list(
        channels
    )

    matches: list[ChannelMatch] = []

    seen_ids: set[str] = set()

    for broadcaster in broadcasters:

        if not isinstance(
            broadcaster,
            str,
        ):
            continue

        broadcaster = broadcaster.strip()

        if not broadcaster:
            continue

        match = find_best_channel(
            broadcaster=broadcaster,
            channels=channels_list,
        )

        if match is None:
            continue

        if match.channel_id in seen_ids:
            continue

        seen_ids.add(
            match.channel_id
        )

        matches.append(
            match
        )

    return matches


# ============================================================
# LIVEONSAT EVENT MATCHING
# ============================================================

def match_liveonsat_event(
    broadcasters: Iterable[str],
    channels: Iterable[Channel],
) -> list[ChannelMatch]:

    return match_broadcasters(
        broadcasters=broadcasters,
        channels=channels,
    )


def match_liveonsat_events(
    liveonsat_events,
    channels: Iterable[Channel],
) -> dict:

    result = {}

    channels_list = list(
        channels
    )

    for event in liveonsat_events:

        event_id = getattr(
            event,
            "event_id",
            None,
        )

        broadcasters = getattr(
            event,
            "broadcasters",
            [],
        )

        if not event_id:
            continue

        result[event_id] = (
            match_liveonsat_event(
                broadcasters=broadcasters,
                channels=channels_list,
            )
        )

    return result
