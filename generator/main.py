from __future__ import annotations

from pathlib import Path

from config import validate_configuration
from dropbox import publish_from_output
from event_builder import build_events_document
from json_writer import write_all
from live_builder import build_live
from liveonsat import get_liveonsat_events
from sports_sources import fetch_all_events
from channel_matcher import load_channels


# ============================================================
# TVSPORTLIVE - MAIN GENERATOR
# ============================================================


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIRECTORY = PROJECT_ROOT / "output"


def run() -> None:
    print("=" * 60)
    print("TVSPORTLIVE DATA GENERATOR")
    print("=" * 60)

    print()
    print("[1/7] Verifica configurazione...")

    validate_configuration()

    print("Configurazione OK.")

    print()
    print("[2/7] Recupero eventi sportivi...")

    raw_events = fetch_all_events()

    print(
        f"Eventi sportivi recuperati: "
        f"{len(raw_events)}"
    )

    if not raw_events:
        raise RuntimeError(
            "Nessun evento sportivo recuperato. "
            "Pubblicazione annullata per evitare "
            "di sovrascrivere events.txt con dati vuoti."
        )

    print()
    print("[3/7] Recupero programmazione LiveOnSat...")

    liveonsat_events = get_liveonsat_events()

    print(
        f"Eventi LiveOnSat recuperati: "
        f"{len(liveonsat_events)}"
    )

    print()
    print("[4/7] Caricamento canali...")

    channels = load_channels()

    print(
        f"Canali disponibili: "
        f"{len(channels)}"
    )

    if not channels:
        raise RuntimeError(
            "Nessun canale disponibile. "
            "Pubblicazione annullata."
        )

    print()
    print("[5/7] Costruzione eventi e stato live...")

    events_document = build_events_document(
        raw_events=raw_events,
        liveonsat_events=liveonsat_events,
        channels=channels,
    )

    live_document = build_live(
        raw_events=raw_events,
    )

    print(
        f"Competizioni generate: "
        f"{len(events_document.competitions)}"
    )

    print(
        f"Squadre generate: "
        f"{len(events_document.teams)}"
    )

    print(
        f"Eventi generati: "
        f"{len(events_document.events)}"
    )

    print(
        f"Eventi live generati: "
        f"{len(live_document.live)}"
    )

    if not events_document.events:
        raise RuntimeError(
            "Il documento events.txt è vuoto. "
            "Pubblicazione annullata."
        )

    print()
    print("[6/7] Scrittura dei file JSON...")

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
    print("[7/7] Pubblicazione su Dropbox...")

    publish_from_output(
        output_directory=OUTPUT_DIRECTORY,
    )

    print()
    print("=" * 60)
    print("TVSPORTLIVE - AGGIORNAMENTO COMPLETATO")
    print("=" * 60)


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
