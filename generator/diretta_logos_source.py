"""
Loghi club/nazionali da diretta.it → CDN static.flashscore.com

Non usa ESPN. Aggiorna data/team_logos_cache.json
"""
from __future__ import annotations

import re
from urllib.request import Request, urlopen

from config import REQUEST_TIMEOUT_SECONDS, USER_AGENT
from team_logo_cache import load_cache, remember_logo, save_cache

# Pagine lega diretta.it (estendi pure la lista)
DIRETTA_LEAGUE_PAGES = (
    "https://www.diretta.it/calcio/italia/serie-a/",
    "https://www.diretta.it/calcio/italia/serie-b/",
    "https://www.diretta.it/calcio/italia/serie-c-girone-a/",
    "https://www.diretta.it/calcio/italia/serie-c-girone-b/",
    "https://www.diretta.it/calcio/italia/serie-c-girone-c/",
    "https://www.diretta.it/calcio/inghilterra/premier-league/",
    "https://www.diretta.it/calcio/inghilterra/championship/",
    "https://www.diretta.it/calcio/spagna/laliga/",
    "https://www.diretta.it/calcio/spagna/laliga2/",
    "https://www.diretta.it/calcio/germania/bundesliga/",
    "https://www.diretta.it/calcio/germania/2-bundesliga/",
    "https://www.diretta.it/calcio/francia/ligue-1/",
    "https://www.diretta.it/calcio/portogallo/liga-portugal/",
    "https://www.diretta.it/calcio/olanda/eredivisie/",
    "https://www.diretta.it/calcio/turchia/super-lig/",
    "https://www.diretta.it/calcio/belgio/jupiler-pro-league/",
    "https://www.diretta.it/calcio/scozia/premiership/",
    "https://www.diretta.it/calcio/svizzera/super-league/",
    "https://www.diretta.it/calcio/argentina/liga-profesional/",
    "https://www.diretta.it/calcio/brasile/serie-a/",
    "https://www.diretta.it/calcio/usa/mls/",
    "https://www.diretta.it/calcio/messico/liga-mx/",
    "https://www.diretta.it/calcio/arabia-saudita/saudi-professional-league/",
    "https://www.diretta.it/calcio/cina/super-league/",
    "https://www.diretta.it/",  # homepage: nazionali / miste
)


def _download(url: str) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
            "Accept": "text/html",
        },
    )
    with urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as r:
        return r.read().decode("utf-8", errors="replace")


def _field(block: str, key: str) -> str | None:
    m = re.search(rf"(?:^|¬){re.escape(key)}÷([^¬~]+)", block)
    return m.group(1).strip() if m else None


def _logo_url(filename: str | None) -> str | None:
    if not filename:
        return None
    f = filename.strip()
    if not f.endswith(".png") and not f.endswith(".jpg"):
        return None
    if f.startswith("http"):
        return f
    return f"https://static.flashscore.com/res/image/data/{f}"


def parse_logos_from_html(html: str) -> dict[str, str]:
    """nome squadra → URL logo"""
    found: dict[str, str] = {}
    parts = re.split(r"[¬~]*AA÷", html)
    for block in parts[1:]:
        home = _field(block, "AE")
        away = _field(block, "AF")
        oa = _logo_url(_field(block, "OA"))
        ob = _logo_url(_field(block, "OB"))
        if home and oa:
            found[home] = oa
        if away and ob:
            found[away] = ob
    # anche link statici espliciti nel HTML
    for m in re.finditer(
        r"https://static\.flashscore\.com/res/image/data/[A-Za-z0-9_.-]+\.png",
        html,
    ):
        pass  # solo con nome squadra contano
    return found


def fetch_diretta_team_logos() -> dict[str, str]:
    all_logos: dict[str, str] = {}
    for url in DIRETTA_LEAGUE_PAGES:
        try:
            print(f"[DIRETTA LOGOS] {url}")
            html = _download(url)
            page = parse_logos_from_html(html)
            print(f"[DIRETTA LOGOS]   → {len(page)} squadre")
            all_logos.update(page)
        except Exception as e:
            print(f"[DIRETTA LOGOS] errore {url}: {e}")
    print(f"[DIRETTA LOGOS] Totale unici: {len(all_logos)}")
    return all_logos


def update_cache_from_diretta() -> int:
    logos = fetch_diretta_team_logos()
    cache = load_cache()
    for name, url in logos.items():
        remember_logo(cache, team_id=None, team_name=name, logo_url=url)
    save_cache(cache)
    return len(logos)


if __name__ == "__main__":
    n = update_cache_from_diretta()
    print("Scritti", n, "loghi in cache")
