"""Free sounds from the web with no key, no account and no login. Only `find` and `fetch` touch the network.

Sources (each verified live on 2026-11-24, see references/sources.md):
  kit      wyzowl/sfx-kit on GitHub: 320 CC0 sounds made for video, animation and interfaces, each with notes on
           what it is for and where its sync point is. The first place to look for a ready-made sound.
  commons  Wikimedia Commons: recordings of real things (doors, glass, water, animals, machines). Licence is per file
           (CC0, public domain, CC BY, CC BY-SA) and is written into the sidecar. Good raw material for transforms.

Every fetched file gets a .json sidecar with its source page, author and licence. Nothing is filtered by licence:
the licence is recorded and the user decides.
"""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "sfx-fetch/0.1 (local tool)"
KIT_RAW = "https://raw.githubusercontent.com/wyzowl/sfx-kit/main/"
KIT_PAGE = "https://github.com/wyzowl/sfx-kit"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"


def _get(url, timeout=30, tries=3):
    """GET with a timeout and a short retry, so a slow server can't hang the session."""
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504):
                raise RuntimeError(f"{e.code} {e.reason} for {url}") from e
            last = e
            wait = e.headers.get("Retry-After", "") if e.headers else ""
            if wait.isdigit():                                # the server said how long to back off
                time.sleep(min(int(wait), 120))
                continue
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
        time.sleep(5 * 3 ** attempt)                          # 5 s, 15 s, 45 s
    host = urllib.parse.urlparse(url).netloc
    raise RuntimeError(f"could not reach {host} ({last}). If this is 429 Too Many Requests, wait a minute: search slowly, a few requests a minute")


def _strip_html(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()


# ---------------------------------------------------------------- the kit
def kit_catalog(cache_dir):
    """The kit's catalogue (sounds.json), cached beside the fetched sounds so repeat searches are offline."""
    cache = Path(cache_dir) / "kit-sounds.json"
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(_get(KIT_RAW + "sounds.json"))
    return json.loads(cache.read_text())


def kit_find(words, cache_dir, category=None):
    """Rank kit sounds by how many of the words appear in their name, tags, description and uses."""
    cat = kit_catalog(cache_dir)
    terms = [w.lower() for w in words]
    hits = []
    for s in cat["sounds"]:
        if category and s.get("category") != category:
            continue
        hay = " ".join([s.get("id", ""), s.get("name", ""), s.get("category", ""), s.get("description", ""),
                        " ".join(s.get("tags", [])), " ".join(s.get("use_for", []))]).lower()
        score = sum(hay.count(t) for t in terms)
        if score or not terms:
            hits.append((score, s))
    hits.sort(key=lambda h: -h[0])
    return [{"id": "kit:" + s["id"], "name": s["name"], "category": s["category"], "seconds": s.get("duration"),
             "licence": "CC0-1.0", "about": s.get("description", ""), "use_for": s.get("use_for", []),
             "avoid_for": s.get("avoid_for", []), "sync": s.get("sync", {})} for _, s in hits]


def kit_categories(cache_dir):
    cat = kit_catalog(cache_dir)
    out = {}
    for s in cat["sounds"]:
        out[s["category"]] = out.get(s["category"], 0) + 1
    return out


def _kit_fetch(sound_id, out_dir):
    cat = kit_catalog(out_dir)
    s = next((x for x in cat["sounds"] if x["id"] == sound_id), None)
    if s is None:
        raise RuntimeError(f"the kit has no sound with id {sound_id!r}; search with `sfx.py find <words> --source kit`")
    url = KIT_RAW + urllib.parse.quote(s["file"])
    info = {"source": "wyzowl/sfx-kit", "id": "kit:" + sound_id, "page": KIT_PAGE, "url": url, "licence": "CC0-1.0",
            "licence_url": "https://creativecommons.org/publicdomain/zero/1.0/", "author": "Wyzowl", "attribution_required": False,
            "name": s["name"], "about": s.get("description", ""), "use_for": s.get("use_for", []), "avoid_for": s.get("avoid_for", []),
            "sync": s.get("sync", {}), "timing": s.get("timing", {}), "seconds": s.get("duration")}
    return url, f"kit_{sound_id}{Path(s['file']).suffix}", info


# ---------------------------------------------------------------- Wikimedia Commons
def commons_find(words, limit=20, max_seconds=30.0, free_only=False):
    """Search Commons for audio files. Returns real recordings with their licence; the caller judges relevance.

    Commons search is noisy (spoken-word pronunciation clips, music, MIDI), so results are limited to short audio.
    """
    # Commons holds hundreds of thousands of spoken-word pronunciation clips (Lingua Libre, "LL-Q..." titles); leave them out
    q = " ".join(words) + ' filetype:audio -intitle:"LL-Q" -pronunciation' + (" haslicense:unrestricted" if free_only else "")
    url = COMMONS_API + "?" + urllib.parse.urlencode({
        "action": "query", "format": "json", "formatversion": "2", "generator": "search", "gsrsearch": q, "gsrnamespace": "6",
        "gsrlimit": str(min(limit * 3, 50)), "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
        "iiextmetadatafilter": "LicenseShortName|LicenseUrl|Artist|AttributionRequired|ImageDescription"})
    data = json.loads(_get(url))
    out = []
    for page in sorted(data.get("query", {}).get("pages", []), key=lambda p: p.get("index", 0)):
        ii = (page.get("imageinfo") or [{}])[0]
        mime, dur = ii.get("mime", ""), ii.get("duration")
        if not mime.startswith("audio/") or mime == "audio/midi" or (dur is not None and dur > max_seconds):
            continue
        meta = {k: v.get("value", "") for k, v in ii.get("extmetadata", {}).items()}
        out.append({"id": "commons:" + page["title"], "name": page["title"].removeprefix("File:"), "seconds": dur, "mime": mime,
                    "bytes": ii.get("size"), "licence": meta.get("LicenseShortName", "unknown"),
                    "author": _strip_html(meta.get("Artist", "")), "about": _strip_html(meta.get("ImageDescription", "")),
                    "page": ii.get("descriptionurl", "")})
        if len(out) >= limit:
            break
    return out


def _commons_fetch(title):
    url = COMMONS_API + "?" + urllib.parse.urlencode({
        "action": "query", "format": "json", "formatversion": "2", "titles": title, "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata", "iiextmetadatafilter": "LicenseShortName|LicenseUrl|Artist|AttributionRequired|ImageDescription"})
    pages = json.loads(_get(url)).get("query", {}).get("pages", [])
    if not pages or not pages[0].get("imageinfo"):
        raise RuntimeError(f"Commons has no file titled {title!r}")
    ii = pages[0]["imageinfo"][0]
    meta = {k: v.get("value", "") for k, v in ii.get("extmetadata", {}).items()}
    name = title.removeprefix("File:")
    info = {"source": "Wikimedia Commons", "id": "commons:" + title, "page": ii.get("descriptionurl", ""), "url": ii["url"].split("?")[0],
            "licence": meta.get("LicenseShortName", "unknown"), "licence_url": meta.get("LicenseUrl", ""),
            "author": _strip_html(meta.get("Artist", "")), "attribution_required": meta.get("AttributionRequired", "") == "true",
            "name": name, "about": _strip_html(meta.get("ImageDescription", "")), "seconds": ii.get("duration")}
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")
    return info["url"], "commons_" + safe, info


# ---------------------------------------------------------------- fetch
def fetch(ref, out_dir, group=None):
    """Download one sound by id (kit:<id>, commons:File:<title>) and write its sidecar. Never overwrites."""
    out_dir = Path(out_dir)
    if ref.startswith("kit:"):
        url, fname, info = _kit_fetch(ref[4:], out_dir)
    elif ref.startswith("commons:"):
        url, fname, info = _commons_fetch(ref[8:])
    else:
        raise RuntimeError("ids look like kit:<id> or commons:File:<title>; get them from `sfx.py find`")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / fname
    if path.exists():
        return path, json.loads(path.with_suffix(".json").read_text()), False
    data = _get(url, timeout=120)
    with open(path, "xb") as fh:
        fh.write(data)
    info["fetched"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    info["file"] = path.name
    if group:
        info["group"] = group
    path.with_suffix(".json").write_text(json.dumps(info, indent=1))
    return path, info, True
