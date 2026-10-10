"""
Unisce le liste canali modificabili in data/channels.txt (output).

Workflow consigliato (file leggeri su GitHub):
  data/channels_part1.txt   → lista IT / principale (ex channels.txt)
  data/channels_part2.txt   → seconda lista
  data/channels_part3.txt   → terza lista
  data/channels_partN.txt   → quante ne vuoi

  data/channels.txt         → SOLO OUTPUT del generatore (può essere 4MB+)
                              Non modificarlo a mano; l'app scarica questo.

Regole merge:
  - Nessuna fonte rimossa
  - Stesso id/nome/alias → un canale, sources unite
  - URL des-tro normalizzati
  - Titoli #### categoria ignorati
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

OUTPUT_FILE = DATA_DIR / "channels.txt"

HASH_FILE = DATA_DIR / ".channels_merge_hash"


def _hash_inputs(paths: list[Path]) -> str:
    """Hash stabile di nomi + contenuto di tutte le liste input."""
    h = hashlib.sha256()
    for path in sorted(paths, key=lambda p: p.name.lower()):
        h.update(path.name.encode("utf-8"))
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def _read_saved_hash() -> str | None:
    if not HASH_FILE.is_file():
        return None
    try:
        return HASH_FILE.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _write_saved_hash(value: str) -> None:
    try:
        HASH_FILE.write_text(value + "\n", encoding="utf-8")
    except OSError as error:
        print(f"[CHANNELS] Impossibile salvare hash merge: {error}")




def discover_channel_files(data_dir: Path | None = None) -> list[Path]:
    """
    Solo file di INPUT (liste modificabili su GitHub).

    NON usa channels.txt come input: quello è solo OUTPUT del merge
    (può superare 2–4 MB e non si edita a mano).

    Input accettati, in ordine:
      data/channels_part1.txt
      data/channels_part2.txt
      data/channels_partN.txt   (qualsiasi N)
      data/channels_extra*.txt  (opzionale)

    Se non c'è nessuna part*, in fallback legge channels.txt
    (compatibilità vecchi repo).
    """
    d = data_dir or DATA_DIR
    if not d.is_dir():
        return []

    part_re = re.compile(r"^channels_part(\d+)\.txt$", re.I)
    parts: list[tuple[int, Path]] = []
    extras: list[Path] = []

    for path in d.iterdir():
        if not path.is_file() or not path.name.lower().endswith(".txt"):
            continue
        name = path.name
        if name.endswith(".tmp") or name.endswith(".bak"):
            continue
        low = name.lower()
        if low == "channels.txt":
            # output only — skip as input
            continue
        m = part_re.match(name)
        if m:
            parts.append((int(m.group(1)), path))
            continue
        if low.startswith("channels_") or low.startswith("channels-"):
            extras.append(path)

    parts.sort(key=lambda x: x[0])
    extras.sort(key=lambda p: p.name.lower())
    ordered = [p for _, p in parts] + extras

    if not ordered:
        # fallback legacy: un solo channels.txt editabile
        base = d / "channels.txt"
        if base.is_file() and base.stat().st_size > 50:
            print(
                "[CHANNELS] Nessuna channels_part*.txt: "
                "uso channels.txt come input (legacy)."
            )
            return [base]

    return ordered


def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def fix_stream_url(url: str) -> str:
    """Normalizza URL Xtream des-tro (e simili) in HLS riproducibile."""
    if not url or not isinstance(url, str):
        return url
    u = url.strip()

    # des-tro.com: aggiungi /live/ e .m3u8
    if "des-tro.com" in u:
        if "/live/" in u and u.rstrip("/").endswith(".m3u8"):
            return u
        m = re.match(
            r"(https?://des-tro\.com:\d+)/([^/\s]+)/([^/\s]+)/(\d+)(?:\.m3u8)?/?$",
            u,
        )
        if m:
            base, user, passwd, cid = m.groups()
            return f"{base}/live/{user}/{passwd}/{cid}.m3u8"
        u2 = re.sub(r"(des-tro\.com:\d+)/", r"\1/live/", u, count=1)
        if not u2.endswith(".m3u8"):
            u2 = u2.rstrip("/") + ".m3u8"
        return u2

    # pattern generico xtream senza /live/ : host:port/user/pass/id numerico
    m = re.match(
        r"(https?://[^/\s]+:\d+)/([^/\s]+)/([^/\s]+)/(\d+)/?$",
        u,
    )
    if m and "/live/" not in u and not u.endswith(".m3u8"):
        base, user, passwd, cid = m.groups()
        # solo se sembra xtream (user/pass non path comuni)
        if user.lower() not in ("live", "play", "hls", "iptv"):
            return f"{base}/live/{user}/{passwd}/{cid}.m3u8"

    # Xtream generico: host:port/user/pass/id → /live/user/pass/id.m3u8
    if "/movie/" not in u and "/series/" not in u:
        m = re.match(
            r"(https?://[^/\s]+)/([^/\s]+)/([^/\s]+)/(\d+)(?:\.m3u8)?/?$",
            u,
        )
        if m and "/live/" not in u:
            base, user, passwd, cid = m.groups()
            return f"{base}/live/{user}/{passwd}/{cid}.m3u8"
        m2 = re.match(
            r"(https?://[^/\s]+)/live/([^/\s]+)/([^/\s]+)/(\d+)/?$",
            u,
        )
        if m2 and not u.rstrip("/").endswith(".m3u8"):
            base, user, passwd, cid = m2.groups()
            return f"{base}/live/{user}/{passwd}/{cid}.m3u8"

    return u



def is_category_header(name: str) -> bool:
    """True per titoli di categoria M3U tipo #### ES - VIX ####."""
    n = (name or "").strip()
    if not n:
        return True
    if re.search(r"#{2,}", n):
        return True
    if re.match(r"^#{1,}", n):
        return True
    if re.fullmatch(r"[#\s\-*=_]+", n):
        return True
    if n.upper() in ("NO MATCH",):
        return True
    return False

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _load_json_file(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return None
    if not text.startswith("{"):
        text = "{" + text
    if not text.endswith("}"):
        text = text + "}"
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"JSON non valido in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"{path} deve essere un oggetto JSON")
    return data


def _ensure_sources(ch: dict[str, Any]) -> list[dict[str, Any]]:
    sources = ch.get("sources")
    if not isinstance(sources, list):
        return []
    out: list[dict[str, Any]] = []
    for s in sources:
        if not isinstance(s, dict):
            continue
        url = fix_stream_url(str(s.get("url") or "").strip())
        if not url:
            continue
        out.append(
            {
                "id": str(s.get("id") or f"src_{len(out)+1}"),
                "url": url,
                "type": str(s.get("type") or "AUTO"),
                "enabled": bool(s.get("enabled", True)),
                "priority": int(s.get("priority") or len(out) + 1),
            }
        )
    return out


def _merge_channel(
    base: dict[str, Any],
    extra: dict[str, Any],
) -> dict[str, Any]:
    """Unisce extra in base: aliases + sources, senza togliere nulla."""
    aliases = list(base.get("aliases") or [])
    seen_a = {_norm(a) for a in aliases}
    for a in extra.get("aliases") or []:
        a = str(a).strip()
        if a and _norm(a) not in seen_a:
            aliases.append(a)
            seen_a.add(_norm(a))
    # anche il name dell'extra come alias
    en = str(extra.get("name") or "").strip()
    if en and _norm(en) not in seen_a:
        aliases.append(en)
        seen_a.add(_norm(en))
    base["aliases"] = aliases[:50]

    sources = list(base.get("sources") or [])
    urls = {s.get("url") for s in sources if s.get("url")}
    max_p = max((int(s.get("priority") or 1) for s in sources), default=0)
    for s in _ensure_sources(extra):
        if s["url"] in urls:
            continue
        max_p += 1
        s["priority"] = max_p
        s["id"] = f"{base['id']}_src_{max_p}"
        sources.append(s)
        urls.add(s["url"])
    base["sources"] = sources

    if not base.get("logoUrl") and extra.get("logoUrl"):
        base["logoUrl"] = extra["logoUrl"]

    # country: preferisci IT se uno dei due lo è
    bc = str(base.get("country") or "INTERNATIONAL").upper()
    ec = str(extra.get("country") or "INTERNATIONAL").upper()
    if bc != "IT" and ec == "IT":
        base["country"] = "IT"
    elif bc not in ("IT", "INTERNATIONAL"):
        base["country"] = "INTERNATIONAL" if bc not in ("IT", "GB") else bc

    return base


def merge_channel_files(
    part_files: tuple[Path, ...] | list[Path] | None = None,
    output_file: Path | None = None,
    force: bool = False,
) -> Path:
    """
    Legge le parti, unisce, scrive channels.txt.
    Se le part non sono cambiate (hash) e channels.txt esiste, salta il merge.
    Ritorna il path del file channels.txt (esistente o appena scritto).
    """
    parts = list(part_files) if part_files else discover_channel_files()
    out = output_file or OUTPUT_FILE

    if not parts:
        if out.is_file() and out.stat().st_size > 100:
            print("[CHANNELS] Nessuna part da unire: uso channels.txt esistente.")
            return out
        raise RuntimeError(
            "Nessun file canali trovato in data/ "
            "(channels_part*.txt) e channels.txt assente/vuoto."
        )

    current_hash = _hash_inputs(parts)
    saved_hash = _read_saved_hash()

    if (
        not force
        and saved_hash
        and saved_hash == current_hash
        and out.is_file()
        and out.stat().st_size > 100
    ):
        print(
            "[CHANNELS] Liste part invariate: merge saltato "
            f"(channels.txt già ok, {out.stat().st_size // 1024} KB)."
        )
        return out

    if saved_hash != current_hash:
        print("[CHANNELS] Liste part modificate (o primo merge): unisco…")
    else:
        print("[CHANNELS] channels.txt mancante/vuoto: unisco…")

    # Per non leggere due volte channels.txt come input e output:
    # se part2/part3 esistono, la base è channels.txt SOLO se non stiamo
    # riscrivendo sopra; leggiamo tutto in memoria prima.
    loaded: list[tuple[str, list[dict[str, Any]]]] = []
    for path in parts:
        data = _load_json_file(path)
        if data is None:
            print(f"[CHANNELS] Assente (ok): {path.name}")
            continue
        chans = data.get("channels")
        if not isinstance(chans, list):
            print(f"[CHANNELS] Skip {path.name}: manca array channels")
            continue
        print(f"[CHANNELS] Letto {path.name}: {len(chans)} canali")
        loaded.append((path.name, chans))

    if not loaded:
        raise RuntimeError(
            "Nessun file canali trovato in data/ "
            "(channels.txt / channels_part2.txt / channels_part3.txt)"
        )

    by_id: dict[str, dict[str, Any]] = {}
    index: dict[str, str] = {}  # norm name/alias -> id
    order: list[str] = []

    def register_keys(ch: dict[str, Any]) -> None:
        cid = ch["id"]
        index[_norm(cid)] = cid
        index[_norm(ch.get("name") or "")] = cid
        for a in ch.get("aliases") or []:
            index[_norm(str(a))] = cid

    for file_name, chans in loaded:
        for item in chans:
            if not isinstance(item, dict):
                continue
            cid = str(item.get("id") or "").strip()
            name = str(item.get("name") or "").strip()
            if not cid or not name:
                continue
            if is_category_header(name):
                continue

            country = str(item.get("country") or "INTERNATIONAL").strip().upper()
            if country not in ("IT", "INTERNATIONAL", "GB"):
                country = "INTERNATIONAL"

            normalized = {
                "id": cid,
                "name": name,
                "country": country,
                "priority": int(item.get("priority") or 100),
                "logoUrl": item.get("logoUrl"),
                "aliases": [
                    str(a).strip()
                    for a in (item.get("aliases") or [])
                    if str(a).strip()
                ],
                "enabled": bool(item.get("enabled", True)),
                "sources": _ensure_sources(item),
            }

            # match esistente?
            match_id = None
            if cid in by_id:
                match_id = cid
            else:
                for key in (
                    _norm(cid),
                    _norm(name),
                    *[_norm(a) for a in normalized["aliases"][:10]],
                ):
                    if key and key in index:
                        match_id = index[key]
                        break

            if match_id and match_id in by_id:
                by_id[match_id] = _merge_channel(by_id[match_id], normalized)
            else:
                by_id[cid] = normalized
                order.append(cid)
                register_keys(normalized)

    final = [by_id[i] for i in order if i in by_id]

    payload = {
        "version": 1,
        "generatedAt": _now(),
        "channels": final,
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(out)

    total_sources = sum(len(c.get("sources") or []) for c in final)
    print(
        f"[CHANNELS] Uniti: {len(final)} canali, "
        f"{total_sources} sorgenti → {out}"
    )
    try:
        _write_saved_hash(_hash_inputs(parts))
    except Exception as error:
        print(f"[CHANNELS] Hash non salvato: {error}")
    return out


def run_merge(force: bool = False) -> Path:
    """Unisce le part. force=True rifà sempre il merge."""
    return merge_channel_files(force=force)


if __name__ == "__main__":
    run_merge()
