from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from channel_matcher import load_channels
from config import validate_configuration
from event_builder import build_events_document
from json_writer import write_all
from live_builder import build_live
from liveonsat import get_liveonsat_events
from sports_sources import fetch_all_events
from team_logo_cache import ingest_raw_events
from diretta_logos_source import update_cache_from_diretta


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIRECTORY = PROJECT_ROOT / "data"


def _generated_at() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def run() -> None:
    print("=" * 60)
    print("TVSPORTLIVE DATA GENERATOR")
    print("=" * 60)

    print()
    print("[1/6] Verifica configurazione...")

    validate_configuration()

    print("Configurazione OK.")

    print()
    print("[2/6] Recupero eventi sportivi...")

    raw_events = fetch_all_events()

    print(
        "Eventi sportivi recuperati: "
        f"{len(raw_events)}"
    )

    print()
    print("[2b/6] Loghi da diretta.it (Flashscore CDN)...")
    try:
        n = update_cache_from_diretta()
        print(f"[LOGOS] Diretta: {n} stemmi in cache")
    except Exception as error:
        print(f"[LOGOS] Diretta non disponibile: {error}")

    print()
    print("[2c/6] Integrazione loghi dagli eventi...")
    try:
        ingest_raw_events(raw_events)
    except Exception as error:
        print(f"[LOGOS] Cache eventi non aggiornata: {error}")

    if not raw_events:
        raise RuntimeError(
            "Nessun evento sportivo recuperato. "
            "Generazione annullata per evitare "
            "di sovrascrivere events.txt con dati vuoti."
        )

    print()
    print("[3/6] Recupero programmazione TV (LiveOnSat + LiveSoccerTV)...")

    liveonsat_events = get_liveonsat_events()

    print(
        "Eventi LiveOnSat recuperati: "
        f"{len(liveonsat_events)}"
    )

    print()
    print("[4/6] Caricamento canali...")

    channels = load_channels()

    print(
        "Canali disponibili: "
        f"{len(channels)}"
    )

    if not channels:
        raise RuntimeError(
            "Nessun canale disponibile. "
            "Generazione annullata."
        )

    generated_at = _generated_at()

    print()
    print("[5/6] Costruzione eventi e stato live...")

    events_document = build_events_document(
        raw_events=raw_events,
        liveonsat_events=liveonsat_events,
        channels=channels,
        generated_at=generated_at,
    )

    live_document = build_live(
        events=raw_events,
        generated_at=generated_at,
    )

    print(
        "Competizioni generate: "
        f"{len(events_document.competitions)}"
    )

    print(
        "Squadre generate: "
        f"{len(events_document.teams)}"
    )

    print(
        "Eventi generati: "
        f"{len(events_document.events)}"
    )

    print(
        "Eventi live generati: "
        f"{len(live_document.live)}"
    )

    if not events_document.events:
        raise RuntimeError(
            "Il documento events.txt è vuoto. "
            "Generazione annullata."
        )

    print()
    print("[6/6] Scrittura dei file JSON...")

    events_file, live_file = write_all(
        events_document=events_document,
        live_document=live_document,
    )

    print(
        f"Generato: {events_file}"
    )

    print(
        f"Generato: {live_file}"
    )

    print()
    print("=" * 60)
    print("TVSPORTLIVE - GENERAZIONE COMPLETATA")
    print("=" * 60)

    print()
    print("I file sono disponibili in:")
    print(f"  {DATA_DIRECTORY}")


if __name__ == "__main__":
    try:
        run()

    except KeyboardInterrupt:
        print()
        print(
            "Generazione interrotta manualmente."
        )
        raise SystemExit(130)

    except Exception as error:
        print()
        print("=" * 60)
        print("ERRORE DURANTE LA GENERAZIONE")
        print("=" * 60)
        print(str(error))
        raise SystemExit(1)
