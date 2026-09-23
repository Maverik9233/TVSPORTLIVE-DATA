#!/usr/bin/env python3
"""Scarica liste squadre ESPN e riempie data/team_logos_cache.json."""
from __future__ import annotations
import json
from urllib.request import Request, urlopen
from config import REQUEST_TIMEOUT_SECONDS, USER_AGENT
from sports_sources import ALL_COMPETITIONS
from team_logo_cache import load_cache, remember_logo, save_cache

def fetch(url: str) -> dict:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))

def main() -> None:
    cache = load_cache()
    for comp in ALL_COMPETITIONS:
        if getattr(comp, "sport", "") != "FOOTBALL":
            continue
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{comp.league}/teams?limit=500"
        try:
            data = fetch(url)
        except Exception as e:
            print(f"[SKIP] {comp.key}: {e}")
            continue
        sports = data.get("sports") or []
        leagues = (sports[0].get("leagues") or []) if sports else []
        teams = (leagues[0].get("teams") or []) if leagues else data.get("teams") or []
        n = 0
        for item in teams:
            team = item.get("team") if isinstance(item, dict) else None
            if not isinstance(team, dict):
                team = item if isinstance(item, dict) else None
            if not isinstance(team, dict):
                continue
            tid = str(team.get("id") or "")
            name = team.get("displayName") or team.get("name")
            logo = None
            for lg in team.get("logos") or []:
                if isinstance(lg, dict) and lg.get("href"):
                    logo = lg["href"]
                    break
            if not logo and tid.isdigit():
                logo = f"https://a.espncdn.com/i/teamlogos/soccer/500/{tid}.png"
            if tid:
                remember_logo(cache, f"espn_{tid}", name, logo)
                n += 1
        print(f"[OK] {comp.key}: {n} squadre")
    save_cache(cache)
    print("Salvato data/team_logos_cache.json")

if __name__ == "__main__":
    main()
