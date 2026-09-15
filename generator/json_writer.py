from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import JSON_INDENT, JSON_VERSION
from event_builder import BuiltEventsDocument
from live_builder import BuiltLiveDocument


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"

EVENTS_OUTPUT_FILE = DATA_DIR / "events.txt"

LIVE_OUTPUT_FILE = DATA_DIR / "live.txt"


def _generated_at() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _write_json(
    path: Path,
    payload: dict[str, Any],
) -> Path:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as file:
        json.dump(
            payload,
            file,
            ensure_ascii=False,
            indent=JSON_INDENT,
        )
        file.write("\n")

    return path


def _competition_to_dict(
    competition,
) -> dict[str, Any]:
    return {
        "id": competition.id,
        "name": competition.name,
        "sport": competition.sport,
        "country": competition.country,
        "countryFlagUrl": (
            competition.country_flag_url
        ),
        "logoUrl": competition.logo_url,
        "priority": competition.priority,
    }


def _team_to_dict(
    team,
) -> dict[str, Any]:
    return {
        "id": team.id,
        "name": team.name,
        "shortName": team.short_name,
        "logoUrl": team.logo_url,
        "country": team.country,
        "countryFlagUrl": (
            team.country_flag_url
        ),
    }


def _event_to_dict(
    event,
) -> dict[str, Any]:
    return {
        "id": event.id,
        "title": event.title,
        "sport": event.sport,
        "competitionId": (
            event.competition_id
        ),
        "homeTeamId": (
            event.home_team_id
        ),
        "awayTeamId": (
            event.away_team_id
        ),
        "startTime": event.start_time,
        "status": event.status,
        "channels": list(event.channels),
    }


def _live_state_to_dict(
    live_state,
) -> dict[str, Any]:
    return {
        "eventId": live_state.event_id,
        "status": live_state.status,
        "homeScore": (
            live_state.home_score
        ),
        "awayScore": (
            live_state.away_score
        ),
        "minute": live_state.minute,
        "addedTime": (
            live_state.added_time
        ),
        "period": live_state.period,
        "currentLap": (
            live_state.current_lap
        ),
        "totalLaps": (
            live_state.total_laps
        ),
        "position": live_state.position,
        "updatedAt": live_state.updated_at,
    }


def build_events_json(
    document: BuiltEventsDocument,
) -> dict[str, Any]:
    return {
        "version": JSON_VERSION,
        "generatedAt": _generated_at(),
        "competitions": [
            _competition_to_dict(
                competition
            )
            for competition
            in document.competitions
        ],
        "teams": [
            _team_to_dict(team)
            for team
            in document.teams
        ],
        "events": [
            _event_to_dict(event)
            for event
            in document.events
        ],
    }


def build_live_json(
    document: BuiltLiveDocument,
) -> dict[str, Any]:
    return {
        "version": JSON_VERSION,
        "generatedAt": _generated_at(),
        "live": [
            _live_state_to_dict(
                live_state
            )
            for live_state
            in document.live
        ],
    }


def write_events_json(
    document: BuiltEventsDocument,
    output_file: Path = EVENTS_OUTPUT_FILE,
) -> Path:
    payload = build_events_json(
        document
    )

    return _write_json(
        path=output_file,
        payload=payload,
    )


def write_live_json(
    document: BuiltLiveDocument,
    output_file: Path = LIVE_OUTPUT_FILE,
) -> Path:
    payload = build_live_json(
        document
    )

    return _write_json(
        path=output_file,
        payload=payload,
    )


def write_all(
    events_document: BuiltEventsDocument,
    live_document: BuiltLiveDocument,
) -> tuple[Path, Path]:
    events_file = write_events_json(
        document=events_document
    )

    live_file = write_live_json(
        document=live_document
    )

    return (
        events_file,
        live_file,
    )
