from __future__ import annotations

import json
import re
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from config import (
    CHANNELS_URL,
    REQUEST_TIMEOUT_SECONDS,
    USER_AGENT,
)


@dataclass(frozen=True)
class Channel:
    id: str
    name: str
    country: str
    priority: int
    logo_url: str | None = None
    aliases: tuple[str, ...] = ()
    enabled: bool = True


@dataclass(frozen=True)
class ChannelMatch:
    channel_id: str
    channel_name: str
    score: int


def _local_channels_path() -> Path:
    # generator/ -> project root -> data/channels.txt
    return (
        Path(__file__).resolve().parent.parent
        / "data"
        / "channels.txt"
    )


def _download_channels() -> str:
    # 1) Preferisci file locale (output del merge_channels)
    local = _local_channels_path()
    if local.is_file() and local.stat().st_size > 100:
        print(f"[CHANNELS] Uso file locale: {local}")
        return local.read_text(encoding="utf-8", errors="replace")

    # 2) Fallback: download da GitHub
    print(f"[CHANNELS] Download remoto: {CHANNELS_URL}")
    request = urllib.request.Request(
        CHANNELS_URL,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/plain,*/*",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:
            return response.read().decode(
                "utf-8",
                errors="replace",
            )

    except urllib.error.HTTPError as error:
        body = error.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            "Impossibile scaricare channels.txt: "
            f"HTTP {error.code} - {body[:500]}"
        ) from error

    except urllib.error.URLError as error:
        raise RuntimeError(
            "Impossibile raggiungere channels.txt: "
            f"{error}"
        ) from error


def load_channels() -> list[Channel]:
    raw_text = _download_channels()

    try:
        data = json.loads(raw_text)

    except json.JSONDecodeError as error:
        raise RuntimeError(
            "channels.txt non contiene JSON valido."
        ) from error

    if not isinstance(data, dict):
        raise RuntimeError(
            "channels.txt deve contenere un oggetto JSON."
        )

    channels_data = data.get("channels")

    if not isinstance(channels_data, list):
        raise RuntimeError(
            "channels.txt non contiene un array "
            "'channels' valido."
        )

    channels: list[Channel] = []

    for item in channels_data:
        if not isinstance(item, dict):
            continue

        channel_id = str(
            item.get("id", "")
        ).strip()

        channel_name = str(
            item.get("name", "")
        ).strip()

        if not channel_id or not channel_name:
            continue

        country = str(
            item.get(
                "country",
                "INTERNATIONAL",
            )
        ).strip().upper()

        try:
            priority = int(
                item.get(
                    "priority",
                    0,
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            priority = 0

        logo_url = item.get("logoUrl")

        if not isinstance(
            logo_url,
            str,
        ):
            logo_url = None

        aliases_data = item.get(
            "aliases",
            [],
        )

        aliases: list[str] = []

        if isinstance(
            aliases_data,
            list,
        ):
            for alias in aliases_data:
                if isinstance(
                    alias,
                    str,
                ):
                    alias = alias.strip()

                    if alias:
                        aliases.append(alias)

        enabled = item.get(
            "enabled",
            True,
        )

        if not isinstance(
            enabled,
            bool,
        ):
            enabled = True

        channels.append(
            Channel(
                id=channel_id,
                name=channel_name,
                country=country,
                priority=priority,
                logo_url=logo_url,
                aliases=tuple(aliases),
                enabled=enabled,
            )
        )

    return channels



# Alias extra per digitali terrestri IT (LiveOnSat / guide TV → id canale)
FTA_NAME_ALIASES: dict[str, tuple[str, ...]] = {
    "rai 1": ("rai 1", "rai uno", "rai1", "rai uno hd"),
    "rai 2": ("rai 2", "rai due", "rai2", "rai due hd"),
    "rai 3": ("rai 3", "rai tre", "rai3"),
    "rai sport": ("rai sport", "raisport", "rai sport hd"),
    "italia 1": ("italia 1", "italia uno", "italia1"),
    "italia 2": ("italia 2", "italia due", "italia2"),
    "canale 5": ("canale 5", "canale5", "c5"),
    "rete 4": ("rete 4", "rete4"),
    "canale 20": ("canale 20", "20 mediaset", "canale 20 mediaset"),
    "tv8": ("tv8", "tv 8", "tv8 italia", "tv8 hd"),
    "cielo": ("cielo", "cielo tv", "cielo hd"),
    "nove": ("nove", "n9ve", "channel 9"),
    "la7": ("la7", "la 7", "la7 hd"),
}


def _normalize(value: str) -> str:
    value = unicodedata.normalize(
        "NFKD",
        value,
    )

    value = (
        value
        .encode(
            "ascii",
            "ignore",
        )
        .decode("ascii")
    )

    value = value.casefold().strip()

    # LiveOnSat: "DAZN Deutsch ($/geo/R)", "Megogo ... 📺"
    value = re.sub(
        r"\(\s*\$?\s*/?\s*geo\s*/?\s*R?\s*\)",
        " ",
        value,
        flags=re.I,
    )
    value = re.sub(r"\(\$/?geo[^)]*\)", " ", value, flags=re.I)
    value = re.sub(r"\$/?geo/?r?", " ", value, flags=re.I)

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value,
    )

    tokens = value.split()
    # sinonimi frequenti LiveOnSat ↔ channels.txt
    synonyms = {
        "deutsch": "deutschland",
        "deutschland": "deutschland",
        "espana": "spain",
        "espana": "spain",
        "espaa": "spain",  # after ascii strip ñ
    }
    tokens = [synonyms.get(tok, tok) for tok in tokens]
    # togli token inutili
    noise = {"hd", "sd", "fhd", "uhd", "geo", "r", "$", "online", "app"}
    tokens = [tok for tok in tokens if tok not in noise]

    return " ".join(tokens)


def _compact(value: str) -> str:
    return _normalize(value).replace(
        " ",
        "",
    )


def _channel_names(
    channel: Channel,
) -> list[str]:
    return [
        channel.name,
        *channel.aliases,
    ]


def _id_matches_name(
    channel: Channel,
) -> bool:
    normalized_id = _normalize(
        channel.id
    )

    normalized_name = _normalize(
        channel.name
    )

    return bool(
        normalized_id
        and normalized_name
        and normalized_id == normalized_name
    )


def _token_sequence_in(
    needle: list[str],
    haystack: list[str],
) -> bool:
    if not needle or not haystack:
        return False

    size = len(needle)

    if size > len(haystack):
        return False

    for index in range(len(haystack) - size + 1):
        if haystack[index:index + size] == needle:
            return True

    return False


def _match_score(
    broadcaster: str,
    channel: Channel,
) -> int:
    broadcaster_normalized = _normalize(broadcaster)
    broadcaster_tokens = broadcaster_normalized.split()

    if not broadcaster_tokens:
        return 0

    best_score = 0

    for channel_name in _channel_names(channel):
        channel_normalized = _normalize(channel_name)
        channel_tokens = channel_normalized.split()

        if not channel_tokens:
            continue

        if broadcaster_normalized == channel_normalized:
            best_score = max(best_score, 100)
            continue

        if _compact(broadcaster) == _compact(channel_name):
            best_score = max(best_score, 98)
            continue

        # Confronto per sequenza di token, non per semplice
        # substring: evita che "Sky Sport 2" venga considerato
        # uguale a "Sky Sport 252".
        if _token_sequence_in(
            channel_tokens,
            broadcaster_tokens,
        ):
            best_score = max(best_score, 90)
            continue

        # Token broadcaster dentro nome canale: solo se il
        # broadcaster ha almeno 2 token (evita "DAZN" → dazn_1_pt)
        if len(broadcaster_tokens) >= 2 and _token_sequence_in(
            broadcaster_tokens,
            channel_tokens,
        ):
            best_score = max(best_score, 85)

        # DAZN Italia ↔ DAZN 1 Italia / DAZN 2 Italia (numero in mezzo)
        # Stesso per Sky Sport Calcio ↔ Sky Sport Calcio HD, ecc.
        if len(broadcaster_tokens) >= 2:
            bset = set(broadcaster_tokens)
            cset = set(channel_tokens)
            # tutti i token del broadcaster presenti nel canale (non obbligatoriamente contigui)
            if bset <= cset:
                # evita match deboli 1 token brand alone già escluso
                # evita Sky Sport 2 ⊂ Sky Sport 252: se needle ha un numero, deve combaciare
                nums_b = {t for t in broadcaster_tokens if t.isdigit()}
                nums_c = {t for t in channel_tokens if t.isdigit()}
                if not nums_b or nums_b & nums_c:
                    best_score = max(best_score, 93)
            # caso speciale: broadcaster "dazn italia" e canale contiene dazn + italia
            if (
                "dazn" in bset
                and ("italia" in bset or "italy" in bset)
                and "dazn" in cset
                and ("italia" in cset or "italy" in cset)
            ):
                best_score = max(best_score, 95)
            if (
                "sky" in bset
                and "calcio" in bset
                and "sky" in cset
                and "calcio" in cset
            ):
                best_score = max(best_score, 94)

    return best_score

def find_best_channel(
    broadcaster: str,
    channels: list[Channel],
) -> ChannelMatch | None:
    best_match: ChannelMatch | None = None
    best_channel: Channel | None = None
    b_low = (broadcaster or "").lower()

    # Canali IT non devono matchare versioni estere (TV8 Turkiye ≠ TV8 Italia)
    foreign_markers = (
        "turkiye", "turkey", "turk", "deutschland", "deutsch",
        "espana", "españa", "france", "uk", "usa", "brazil",
        "portugal", "nederland", "serbia", "croatia", "romania",
    )

    for channel in channels:
        if not channel.enabled:
            continue

        if not channel.id or not channel.name:
            continue

        score = _match_score(
            broadcaster=broadcaster,
            channel=channel,
        )

        if score <= 0:
            continue

        # Se il nome LiveOnSat ha un paese estero e il canale è IT
        # senza quel paese negli alias → scarta
        ch_country = (getattr(channel, "country", None) or "").upper()
        if ch_country in {"IT", "ITA", "ITALY"} or channel.id in {
            "tv8", "italia_1", "italia_2", "rai_1", "rai_2", "cielo",
            "canale_20_mediaset", "canale_5_mediaset",
        }:
            if any(m in b_low for m in foreign_markers):
                # eccezione: "Italia" / "Italy" nel nome broadcaster è ok
                if not any(x in b_low for x in ("italia", "italy", " italian")):
                    # TV8 Turkiye, DAZN Deutsch as only signal for italian dazn, etc.
                    if channel.id == "tv8" and ("turk" in b_low or "turkiye" in b_low):
                        continue
                    if channel.id.startswith("rai") and "turk" in b_low:
                        continue

        candidate = ChannelMatch(
            channel_id=channel.id,
            channel_name=channel.name,
            score=score,
        )

        if best_match is None:
            best_match = candidate
            best_channel = channel
            continue

        if candidate.score > best_match.score:
            best_match = candidate
            best_channel = channel
            continue

        if candidate.score < best_match.score:
            continue

        candidate_is_canonical = _id_matches_name(
            channel
        )

        best_is_canonical = (
            best_channel is not None
            and _id_matches_name(
                best_channel
            )
        )

        if (
            candidate_is_canonical
            and not best_is_canonical
        ):
            best_match = candidate
            best_channel = channel
            continue

        if (
            candidate_is_canonical
            == best_is_canonical
            and best_channel is not None
            and channel.priority
            < best_channel.priority
        ):
            best_match = candidate
            best_channel = channel

    return best_match



def _expand_sky_calcio_names(name: str) -> list[str]:
    """Calcio N ↔ Sky Sport (250+N). LiveOnSat / EPG / liste IPTV.

    Esempi:
      Sky Calcio 1 / Calcio 1  →  Sky Sport 251
      Sky Sport 252            →  Calcio 2, SKY CALCIO 2
    """
    out = [name]
    n = _normalize(name)
    if not n:
        return out

    m = re.search(r"(?:sky\s+)?(?:sport\s+)?calcio\s+(\d+)", n)
    if m:
        num = int(m.group(1))
        sky = 250 + num
        if 251 <= sky <= 269:
            out.extend(
                [
                    f"Sky Sport {sky}",
                    f"Sky Sport {sky} HD",
                    f"Sky Calcio {num}",
                    f"Calcio {num}",
                    f"SKY CALCIO {num}",
                    f"Sky Sport Calcio {num}",
                ]
            )

    m2 = re.search(r"sky\s+sport\s+(25[1-9]|26\d)\b", n)
    if m2:
        sky = int(m2.group(1))
        num = sky - 250
        out.extend(
            [
                f"Calcio {num}",
                f"Sky Calcio {num}",
                f"SKY CALCIO {num}",
                f"Sky Sport Calcio {num}",
                f"Sky Sport {sky}",
            ]
        )

    seen: set[str] = set()
    uniq: list[str] = []
    for x in out:
        k = x.casefold().strip()
        if k and k not in seen:
            seen.add(k)
            uniq.append(x)
    return uniq


def match_broadcasters(
    broadcasters: list[str],
    channels: list[Channel],
) -> list[ChannelMatch]:
    matches: list[ChannelMatch] = []

    seen_ids: set[str] = set()

    for broadcaster in broadcasters:
        if not broadcaster:
            continue

        # Prova nome originale + varianti Sky Calcio N ↔ Sky Sport 25x
        candidates = _expand_sky_calcio_names(broadcaster)
        best: ChannelMatch | None = None
        for cand in candidates:
            match = find_best_channel(
                broadcaster=cand,
                channels=channels,
            )
            if match is None:
                continue
            if match.score < 90:
                continue
            if best is None or match.score > best.score:
                best = match

        if best is None:
            continue

        if best.channel_id in seen_ids:
            continue

        seen_ids.add(best.channel_id)
        matches.append(best)

    return matches


def match_liveonsat_event(
    broadcasters: list[str],
    channels: list[Channel],
) -> list[ChannelMatch]:
    return match_broadcasters(
        broadcasters=broadcasters,
        channels=channels,
    )


def match_liveonsat_events(
    liveonsat_events,
    channels: list[Channel],
) -> dict:
    result = {}

    for event in liveonsat_events:
        event_id = getattr(
            event,
            "event_id",
            None,
        )

        broadcasters = getattr(
            event,
            "broadcasters",
            [],
        )

        if not event_id:
            continue

        result[event_id] = (
            match_liveonsat_event(
                broadcasters=broadcasters,
                channels=channels,
            )
        )

    return result
