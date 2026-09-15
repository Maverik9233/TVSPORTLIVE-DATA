from __future__ import annotations

import json
import re
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass

from config import (
    CHANNELS_URL,
    REQUEST_TIMEOUT_SECONDS,
    USER_AGENT,
)


@dataclass(frozen=True)
class Channel:
    id: str
    name: str
    country: str
    priority: int
    logo_url: str | None = None
    aliases: tuple[str, ...] = ()
    enabled: bool = True


@dataclass(frozen=True)
class ChannelMatch:
    channel_id: str
    channel_name: str
    score: int


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


def load_channels() -> list[Channel]:

    raw_text = _download_channels()

    try:
        data = json.loads(
            raw_text
        )

    except json.JSONDecodeError as error:

        raise RuntimeError(
            "channels.txt non contiene JSON valido."
        ) from error

    if not isinstance(data, dict):

        raise RuntimeError(
            "channels.txt deve contenere un oggetto JSON."
        )

    channels_data = data.get(
        "channels"
    )

    if not isinstance(
        channels_data,
        list,
    ):

        raise RuntimeError(
            "channels.txt non contiene un array "
            "'channels' valido."
        )

    channels: list[Channel] = []

    for item in channels_data:

        if not isinstance(
            item,
            dict,
        ):
            continue

        channel_id = str(
            item.get(
                "id",
                "",
            )
        ).strip()

        channel_name = str(
            item.get(
                "name",
                "",
            )
        ).strip()

        if not channel_id or not channel_name:
            continue

        country = str(
            item.get(
                "country",
                "INTERNATIONAL",
            )
        ).strip().upper()

        try:
            priority = int(
                item.get(
                    "priority",
                    0,
                )
            )

        except (
            TypeError,
            ValueError,
        ):
            priority = 0

        logo_url = item.get(
            "logoUrl"
        )

        if not isinstance(
            logo_url,
            str,
        ):
            logo_url = None

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

                if isinstance(
                    alias,
                    str,
                ):

                    alias = alias.strip()

                    if alias:
                        aliases.append(
                            alias
                        )

        enabled = item.get(
            "enabled",
            True,
        )

        if not isinstance(
            enabled,
            bool,
        ):
            enabled = True

        channels.append(
            Channel(
                id=channel_id,
                name=channel_name,
                country=country,
                priority=priority,
                logo_url=logo_url,
                aliases=tuple(
                    aliases
                ),
                enabled=enabled,
            )
        )

    return channels


# ============================================================
# NORMALIZATION
# ============================================================

def _normalize(value: str) -> str:

    value = unicodedata.normalize(
        "NFKD",
        value,
    )

    value = (
        value
        .encode(
            "ascii",
            "ignore",
        )
        .decode(
            "ascii"
        )
    )

    value = value.casefold().strip()

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value,
    )

    return " ".join(
        value.split()
    )


def _compact(value: str) -> str:
    return _normalize(value).replace(
        " ",
        "",
    )


def _channel_names(
    channel: Channel,
) -> list[str]:

    names = [
        channel.name,
    ]

    names.extend(
        channel.aliases
    )

    return names


def _id_matches_name(
    channel: Channel,
) -> bool:

    normalized_id = _normalize(
        channel.id
    )

    normalized_name = _normalize(
        channel.name
    )

    return bool(
        normalized_id
        and normalized_name
        and normalized_id == normalized_name
    )


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

        if (
            broadcaster_normalized
            == channel_normalized
        ):

            best_score = max(
                best_score,
                100,
            )

            continue

        if (
            broadcaster_compact
            == channel_compact
        ):

            best_score = max(
                best_score,
                95,
            )

            continue

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


def find_best_channel(
    broadcaster: str,
    channels: list[Channel],
) -> ChannelMatch | None:

    best_match: ChannelMatch | None = None
    best_channel: Channel | None = None

    for channel in channels:

        if not channel.enabled:
            continue

        if not channel.id or not channel.name:
            continue

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

        if best_match is None:

            best_match = candidate
            best_channel = channel
            continue

        # Punteggio superiore.
        if candidate.score > best_match.score:

            best_match = candidate
            best_channel = channel
            continue

        if candidate.score < best_match.score:
            continue

        # A parità di punteggio preferiamo il canale
        # il cui ID rappresenta direttamente il nome.
        candidate_is_canonical = _id_matches_name(
            channel
        )

        best_is_canonical = (
            best_channel is not None
            and _id_matches_name(
                best_channel
            )
        )

        if (
            candidate_is_canonical
            and not best_is_canonical
        ):

            best_match = candidate
            best_channel = channel
            continue

        if (
            candidate_is_canonical
            == best_is_canonical
            and best_channel is not None
            and channel.priority
            < best_channel.priority
        ):

            best_match = candidate
            best_channel = channel

    return best_match


def match_broadcasters(
    broadcasters: list[str],
    channels: list[Channel],
) -> list[ChannelMatch]:

    matches: list[ChannelMatch] = []

    seen_ids: set[str] = set()

    for broadcaster in broadcasters:

        if not broadcaster:
            continue

        match = find_best_channel(
            broadcaster=broadcaster,
            channels=channels,
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


def match_liveonsat_event(
    broadcasters: list[str],
    channels: list[Channel],
) -> list[ChannelMatch]:

    return match_broadcasters(
        broadcasters=broadcasters,
        channels=channels,
    )


def match_liveonsat_events(
    liveonsat_events,
    channels: list[Channel],
) -> dict:

    result = {}

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
                channels=channels,
            )
        )

    return result
