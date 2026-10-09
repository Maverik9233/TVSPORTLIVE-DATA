"""
Guida TV canali nazionali IT (futuro).

Obiettivo: leggere programmazione di Rai 1/2, TV8, Italia 1, Canale 5, Cielo…
e, se un programma sport coincide con un evento (F1, MotoGP, calcio),
aggiungere quel canale all'evento.

Per ora la F1/MotoGP usano override fissi (TV8 + Sky) in event_builder.py
perché LiveOnSat spesso omette TV8 sulle sessioni Sprint.

Possibili fonti EPG (da valutare stabilità):
- XMLTV pubblici IT (es. community IPTV/EPG)
- SuperGuidaTV / siti guida (scraping fragile)
- File statico data/italy_fta_guide.json curato a mano per weekend F1/MotoGP

Uso previsto (quando implementato):
  programmes = fetch_italy_fta_programmes(today, tomorrow)
  match_epg_to_events(events, programmes)  # aggiunge "TV8", "Rai 2", …
"""
from __future__ import annotations

from typing import Any


def fetch_italy_fta_programmes(*_args: Any, **_kwargs: Any) -> list[dict]:
    """Placeholder: nessuna EPG live ancora."""
    return []
