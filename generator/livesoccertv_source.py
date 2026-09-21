"""
LiveSoccerTV — fonte secondaria broadcaster (in sviluppo).

Quando lo scraper sarà stabile, esporrà:
  fetch_livesoccertv_events() -> list di titoli + canali

Per ora i canali extra arrivano da:
  1) LiveOnSat
  2) ESPN broadcasts (campo RawEvent.broadcasts)
  3) override Serie C
"""

from __future__ import annotations


def fetch_livesoccertv_broadcasters_for_title(title: str) -> list[str]:
    # Placeholder: nessuna chiamata di rete finché non validato anti-403
    return []
