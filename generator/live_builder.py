from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from config import JSON_VERSION
from sports_sources import RawEvent


# ============================================================
# TVSPORTLIVE - LIVE BUILDER
# ============================================================

@dataclass(frozen=True)
class BuiltLiveState:
    event_id: str
    status: str

    home_score: int | None
    away_score: int | None

    minute: int | None
    added_time: int | None

    period: str | None

    current_lap: int | None
    total_laps: int | None

    position: int | None

    # Testo breve per UI, es. "12' Rossi; 45' Bianchi"
    goals_text: str | None = None
    # es. "33' Giallo Verdi; 70' Rosso Neri"
    cards_text: str | None = None

    updated_at: str = ""


@dataclass(frozen=True)
class BuiltLiveDocument:
    version: int
    generated_at: str
    live: tuple[BuiltLiveState, ...]


# ============================================================
# EVENT ID
# ============================================================

def build_event_id(
    raw_event: RawEvent,
) -> str:
    return (
        f"{raw_event.source.lower()}_"
        f"{raw_event.source_event_id}"
    )


# ============================================================
# LIVE STATUS
# ============================================================

LIVE_STATUSES = {
    "LIVE",
    "HALFTIME",
}


def is_live_event(
    event: RawEvent,
) -> bool:
    return (
        event.status.upper()
        in LIVE_STATUSES
    )


# ============================================================
# ADDED TIME
# ============================================================

def extract_added_time(
    event: RawEvent,
) -> int | None:
    return None


# ============================================================
# FORMULA 1 / MOTOGP
# ============================================================

def extract_current_lap(
    event: RawEvent,
) -> int | None:
    return None


def extract_total_laps(
    event: RawEvent,
) -> int | None:
    return None


# ============================================================
# POSITION
# ============================================================

def extract_position(
    event: RawEvent,
) -> int | None:
    return None


# ============================================================
# LIVE STATE
# ============================================================

def _format_incidents(items: list | None, prefer_types: tuple[str, ...] | None = None) -> str | None:
    if not items:
        return None
    parts: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        minute = item.get("minute") or ""
        player = item.get("player") or "?"
        itype = (item.get("type") or "").lower()
        prefix = ""
        if "yellow" in itype:
            prefix = "🟨 "
        elif "red" in itype:
            prefix = "🟥 "
        elif "goal" in itype:
            prefix = "⚽ "
        part = f"{prefix}{minute} {player}".strip()
        parts.append(part)
    if not parts:
        return None
    return " · ".join(parts)


def build_live_state(
    event: RawEvent,
    updated_at: str,
) -> BuiltLiveState:

    return BuiltLiveState(
        event_id=build_event_id(
            event
        ),
        status=event.status,
        home_score=event.home_score,
        away_score=event.away_score,
        minute=event.minute,
        added_time=extract_added_time(
            event
        ),
        period=event.period,
        current_lap=extract_current_lap(
            event
        ),
        total_laps=extract_total_laps(
            event
        ),
        position=extract_position(
            event
        ),
        goals_text=_format_incidents(getattr(event, "goals", None)),
        cards_text=_format_incidents(getattr(event, "cards", None)),
        updated_at=updated_at,
    )


# ============================================================
# DOCUMENT BUILDER
# ============================================================

def build_live_document(
    events: Iterable[RawEvent],
    generated_at: str,
) -> BuiltLiveDocument:

    live_states: list[
        BuiltLiveState
    ] = []

    for event in events:
        if not is_live_event(
            event
        ):
            continue

        live_states.append(
            build_live_state(
                event=event,
                updated_at=generated_at,
            )
        )

    live_states.sort(
        key=lambda item:
            item.event_id
    )

    return BuiltLiveDocument(
        version=JSON_VERSION,
        generated_at=generated_at,
        live=tuple(
            live_states
        ),
    )


# ============================================================
# PUBLIC ENTRY POINT
# ============================================================

def build_live(
    events: Iterable[RawEvent],
    generated_at: str,
) -> BuiltLiveDocument:

    return build_live_document(
        events=events,
        generated_at=generated_at,
    )
