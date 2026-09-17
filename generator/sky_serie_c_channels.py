from __future__ import annotations

import re
import unicodedata
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from config import REQUEST_TIMEOUT_SECONDS, USER_AGENT


SKY_SERIE_C_HUB = "https://sport.sky.it/calcio/serie-c"

# Articoli tipo:
# /calcio/serie-c/2026/09/15/serie-c-partite-sky-giornata-5
GIORNATA_ARTICLE_RE = re.compile(
    r"https://sport\.sky\.it/calcio/serie-c/"
    r"(\d{4})/(\d{2})/(\d{2})/"
    r"[^\"']*?(?:partite-sky-giornata|partite-sky-calendario-giornata|"
    r"le-gare-della-\d+-giornata)[^\"']*",
    re.IGNORECASE,
)

CHANNEL_RE = re.compile(
    r"Sky Sport\s+"
    r"(?:Calcio|Uno|Arena|Max|Mix|Football|Tennis|Basket|F1|MotoGP|"
    r"\d{3})",
    re.IGNORECASE,
)

MATCH_LINE_RE = re.compile(
    r"^([A-ZÀÈÉÌÒÙ0-9][A-Za-zÀ-ú0-9 .'\-]{1,40})"
    r"\s*[-–—]\s*"
    r"([A-ZÀÈÉÌÒÙ0-9][A-Za-zÀ-ú0-9 .'\-]{1,40})"
    r"[,.]?\s*$",
)


def _download(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
        },
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, Exception) as error:
        raise RuntimeError(f"Download fallito {url}: {error}") from error


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.casefold()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _html_to_lines(html: str) -> list[str]:
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.I)
    html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.DOTALL | re.I)
    text = re.sub(r"<[^>]+>", "\n", html)
    text = re.sub(r"[ \t]+", " ", text)
    return [line.strip() for line in text.splitlines() if line.strip()]


def find_latest_giornata_article_url() -> str | None:
    """Trova l'articolo Sky più recente con il programma canali della giornata."""
    try:
        html = _download(SKY_SERIE_C_HUB)
    except Exception as error:
        print(f"[SKY SERIE C] Hub non disponibile: {error}")
        return None

    candidates: list[tuple[str, str]] = []
    for match in GIORNATA_ARTICLE_RE.finditer(html):
        url = match.group(0)
        # chiave ordinabile YYYYMMDD
        date_key = match.group(1) + match.group(2) + match.group(3)
        candidates.append((date_key, url))

    if not candidates:
        print("[SKY SERIE C] Nessun articolo giornata trovato nell'hub")
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)
    latest = candidates[0][1]
    print(f"[SKY SERIE C] Articolo giornata: {latest}")
    return latest


def parse_channels_from_article(html: str) -> dict[str, tuple[str, ...]]:
    """
    Restituisce mapping:
      "team1 - team2" normalizzato -> ("Sky Sport 251", "Sky Sport Calcio", ...)
    """
    lines = _html_to_lines(html)
    result: dict[str, tuple[str, ...]] = {}

    i = 0
    while i < len(lines):
        line = lines[i]
        # Pulisce eventuali virgole finali
        clean = line.rstrip(",.;")
        match = MATCH_LINE_RE.match(clean)
        if not match:
            i += 1
            continue

        home = match.group(1).strip()
        away = match.group(2).strip()

        # Cerca canali nelle prossime 4 righe
        channels: list[str] = []
        for j in range(i + 1, min(i + 5, len(lines))):
            chunk = lines[j]
            if MATCH_LINE_RE.match(chunk.rstrip(",.;")):
                break
            for ch in CHANNEL_RE.findall(chunk):
                normalized_ch = re.sub(r"\s+", " ", ch).strip()
                # Canonical form
                normalized_ch = re.sub(
                    r"(?i)^sky sport\s+",
                    "Sky Sport ",
                    normalized_ch,
                )
                if normalized_ch not in channels:
                    channels.append(normalized_ch)

        if channels:
            key = _normalize(f"{home} - {away}")
            # Anche ordine inverso per matching flessibile
            key_rev = _normalize(f"{away} - {home}")
            result[key] = tuple(channels)
            result[key_rev] = tuple(channels)

        i += 1

    return result


def fetch_sky_serie_c_channel_map() -> dict[str, tuple[str, ...]]:
    """
    Scarica l'ultimo articolo giornata Sky e costruisce
    la mappa partita -> canali.
    """
    article_url = find_latest_giornata_article_url()
    if not article_url:
        return {}

    try:
        html = _download(article_url)
    except Exception as error:
        print(f"[SKY SERIE C] Articolo non scaricabile: {error}")
        return {}

    mapping = parse_channels_from_article(html)
    print(f"[SKY SERIE C] Partite con canali trovate: {len(mapping) // 2}")
    return mapping


def find_channels_for_match(
    title: str,
    channel_map: dict[str, tuple[str, ...]],
) -> tuple[str, ...]:
    """Cerca i canali per un titolo tipo 'SORRENTO - BARI'."""
    if not channel_map or not title:
        return ()

    key = _normalize(title)
    if key in channel_map:
        return channel_map[key]

    # Fallback: match parziale sui due team
    parts = re.split(r"\s+-\s+", title, maxsplit=1)
    if len(parts) != 2:
        return ()

    home_n = _normalize(parts[0])
    away_n = _normalize(parts[1])

    for map_key, channels in channel_map.items():
        if home_n in map_key and away_n in map_key:
            return channels

    return ()


if __name__ == "__main__":
    mapping = fetch_sky_serie_c_channel_map()
    print()
    seen: set[str] = set()
    for key, channels in mapping.items():
        if key in seen:
            continue
        # stampa solo ordine "home - away" (non il reverse)
        seen.add(key)
        print(key, "->", channels)
