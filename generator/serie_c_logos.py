from __future__ import annotations

import re
from typing import Optional


# ============================================================
# MAPPA STATICA LOGHI SERIE C
#
# Fallback quando seriec.com non espone l'immagine nel HTML.
# Aggiungi solo voci nuove (non rimuovere quelle esistenti).
#
# Chiavi = slug normalizzato (minuscolo, underscore).
# Valori = URL pubblici HTTPS.
# ============================================================

_BASE = "https://www.seriec.com/storage/app/media/loghi-squadre"

SERIE_C_LOGO_MAP: dict[str, str] = {
    # --- Loghi ufficiali seriec.com (verificati) ---
    "bari": f"{_BASE}/Bari.png",
    "catania": f"{_BASE}/CATANIA.png",
    "desenzano": f"{_BASE}/Desenzano.png",
    "folgore_caratese": f"{_BASE}/folgorecaratese-trasp-logo.png",
    "folgorecaratese": f"{_BASE}/folgorecaratese-trasp-logo.png",
    "grosseto": f"{_BASE}/Grosseto.png",
    "ostiamare": f"{_BASE}/ostiamare-trasp-logo.png",
    "pescara": f"{_BASE}/Pescara_Calcio.png",
    "pescara_calcio": f"{_BASE}/Pescara_Calcio.png",
    "reggiana": f"{_BASE}/Reggiana.png",
    "savoia": f"{_BASE}/loghi-squadre/girone-c/savoia-trasp-logo.png",
    "scafatese": f"{_BASE}/girone-c/scafatese-trasp-logo.png",
    "spezia": f"{_BASE}/Spezia.png",
    "vado": f"{_BASE}/girone-b/vado-trasp-logo.png",
    "foggia": f"{_BASE}/girone-c/foggia-calcio.png",
    "foggia_calcio": f"{_BASE}/girone-c/foggia-calcio.png",
}


def _slug(value: str) -> str:
    value = value.upper()
    for src, dst in (
        ("À", "A"), ("È", "E"), ("É", "E"),
        ("Ì", "I"), ("Ò", "O"), ("Ù", "U"),
    ):
        value = value.replace(src, dst)
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def logo_from_static_map(team_name: str) -> Optional[str]:
    """
    Restituisce l'URL logo dalla mappa statica, oppure None.
    """
    if not team_name:
        return None

    key = _slug(team_name)
    if not key:
        return None

    url = SERIE_C_LOGO_MAP.get(key)
    if url:
        return url

    for map_key, map_url in SERIE_C_LOGO_MAP.items():
        if key in map_key or map_key in key:
            return map_url

    return None
