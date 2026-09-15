from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from config import (
    CHANNELS_URL,
    REQUEST_TIMEOUT_SECONDS,
    USER_AGENT,
)


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
            "Impossibile raggiungere "
            "channels.txt: "
            f"{error}"
        ) from error


def load_channels() -> list[dict]:
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

    channels = data.get("channels")

    if not isinstance(channels, list):
        raise RuntimeError(
            "channels.txt non contiene "
            "un array 'channels' valido."
        )

    valid_channels: list[dict] = []

    for channel in channels:
        if not isinstance(channel, dict):
            continue

        channel_id = str(
            channel.get("id", "")
        ).strip()

        channel_name = str(
            channel.get("name", "")
        ).strip()

        if not channel_id or not channel_name:
            continue

        valid_channels.append(channel)

    return valid_channels


def _normalize(value: str) -> str:
    value = value.lower().strip()

    value = (
        value.replace("à", "a")
        .replace("è", "e")
        .replace("é", "e")
        .replace("ì", "i")
        .replace("ò", "o")
        .replace("ù", "u")
    )

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


def _channel_names(channel: dict) -> list[str]:
    names = []

    name = channel.get("name")

    if isinstance(name, str) and name.strip():
        names.append(name)

    aliases = channel.get("aliases", [])

    if isinstance(aliases, list):
        for alias in aliases:
            if isinstance(alias, str) and alias.strip():
                names.append(alias)

    return names


def _match_score(
    broadcaster: str,
    channel: dict,
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

    for channel_name in _channel_names(channel):
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
    channels: list[dict],
) -> ChannelMatch | None:
    best_match: ChannelMatch | None = None

    for channel in channels:
        if not channel.get(
            "enabled",
            True,
        ):
            continue

        channel_id = str(
            channel.get("id", "")
        ).strip()

        channel_name = str(
            channel.get("name", "")
        ).strip()

        if not channel_id or not channel_name:
            continue

        score = _match_score(
            broadcaster,
            channel,
        )

        if score <= 0:
            continue

        candidate = ChannelMatch(
            channel_id=channel_id,
            channel_name=channel_name,
            score=score,
        )

        if (
            best_match is None
            or candidate.score
            > best_match.score
        ):
            best_match = candidate

    return best_match


def match_broadcasters(
    broadcasters: list[str],
    channels: list[dict],
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

        matches.append(match)

    return matches


def match_liveonsat_event(
    broadcasters: list[str],
    channels: list[dict],
) -> list[ChannelMatch]:
    return match_broadcasters(
        broadcasters=broadcasters,
        channels=channels,
    )


def match_liveonsat_events(
    liveonsat_events,
    channels: list[dict],
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
