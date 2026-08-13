"""
AGRIS Open Data Set - local record index.

The AGRIS adapter used to search ``graph rag source/AGRIS.ODS.xml`` directly.
That file is only the DCAT *catalogue*: its entries describe the 1186 available
subsets ("Subset: RO2 ... contributed by Forest Research and Management
Institute"), not the research they contain. Searching it returned dataset
descriptors for every query, which is why AGRIS evidence was metadata-only.

The catalogue's ``dcat:downloadURL`` entries point at the real data, e.g.
``https://agris.fao.org/ods/AGRIS.ODS.IN0.xml``. Those files are plain static
XML, are NOT behind the Cloudflare challenge that blocks agris.fao.org's search
and API routes, and contain ``dctypes:BibliographicResource`` records with
titles, authors, dates and full ``dc:description`` abstracts, under CC-BY-4.0.

This module downloads a configured set of those subsets once, caches them on
disk, and exposes a keyword search over the parsed records.
"""

from __future__ import annotations

import logging
import os
import re
import threading
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

DC = "{http://purl.org/dc/elements/1.1/}"
DCTYPES = "{http://purl.org/dc/dcmitype/}"

ODS_URL_TEMPLATE = "https://agris.fao.org/ods/AGRIS.ODS.{code}.xml"

# Defaults favour Indian agricultural research, matching this project's scope:
#   IN0 Indian Council of Agricultural Research   IN8 (large Indian subset)
#   IMK Indian Institute of Horticultural Research
#   IN3 Indian Society for Plantation Crops       IME Indian Society for Spices
DEFAULT_SUBSETS = ["IN0", "IN8", "IMK", "IN3", "IME"]

CACHE_DIR = Path(__file__).resolve().parents[1] / "cache" / "agris_ods"
DOWNLOAD_TIMEOUT = float(os.getenv("AGRIS_ODS_TIMEOUT", "120"))
USER_AGENT = "TerraMind/1.0 (agricultural advisory; AGRIS ODS CC-BY-4.0 reuse)"

_lock = threading.Lock()
_records: Optional[List[Dict]] = None
_warmup_thread: Optional[threading.Thread] = None
_warmup_lock = threading.Lock()


def is_ready() -> bool:
    """True once the subsets are downloaded and parsed."""
    return _records is not None


def start_warmup() -> None:
    """
    Build the index on a background thread.

    Called at application startup so the first user question does not pay for
    it. On a cold container this downloads ~150 MB of subsets (IN0 alone is
    144 MB) and, before this existed, it did so *inside* the first request
    while holding ``_lock`` — which is precisely how a first-ever query
    exhausted the client's budget while a retry, arriving after the download
    finished, returned instantly.
    """
    global _warmup_thread
    with _warmup_lock:
        if _records is not None:
            return
        if _warmup_thread is not None and _warmup_thread.is_alive():
            return

        def _warm():
            try:
                load_records()
            except Exception as exc:  # never take the app down for a cache warm
                logger.warning("AGRIS ODS warmup failed: %s", exc)

        _warmup_thread = threading.Thread(
            target=_warm, name="agris-ods-warmup", daemon=True
        )
        _warmup_thread.start()
        logger.info("AGRIS ODS warmup started in background")


def configured_subsets() -> List[str]:
    raw = os.getenv("AGRIS_ODS_SUBSETS", "").strip()
    if raw:
        return [c.strip().upper() for c in raw.split(",") if c.strip()]
    return list(DEFAULT_SUBSETS)


def _cache_path(code: str) -> Path:
    return CACHE_DIR / f"AGRIS.ODS.{code}.xml"


def _download_subset(code: str) -> Optional[Path]:
    """Fetch one subset to the cache. Returns None if unavailable."""
    dest = _cache_path(code)
    if dest.exists() and dest.stat().st_size > 0:
        return dest

    url = ODS_URL_TEMPLATE.format(code=code)
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        resp = requests.get(url, timeout=DOWNLOAD_TIMEOUT, headers={"User-Agent": USER_AGENT})
        if resp.status_code != 200 or not resp.content:
            logger.warning("AGRIS ODS subset %s unavailable (HTTP %s)", code, resp.status_code)
            return None
        tmp = dest.with_suffix(".part")
        tmp.write_bytes(resp.content)
        tmp.replace(dest)
        logger.info("AGRIS ODS subset %s cached (%d bytes)", code, len(resp.content))
        return dest
    except Exception as exc:
        logger.warning("AGRIS ODS subset %s download failed: %s", code, exc)
        return None


def _parse_subset(path: Path, code: str) -> List[Dict]:
    """Stream one subset file into normalizer-ready record dicts."""
    records: List[Dict] = []
    try:
        for _event, elem in ET.iterparse(str(path), events=("end",)):
            if not elem.tag.endswith("BibliographicResource"):
                continue

            title = (elem.findtext(f"{DC}title") or "").strip()
            abstract = " ".join(
                (t.text or "").strip() for t in elem.findall(f"{DC}description")
            ).strip()
            if title:
                identifier = ""
                for ident in elem.findall(f"{DC}identifier"):
                    val = (ident.text or "").strip()
                    if val.startswith("http"):
                        identifier = val
                        break
                rec_id = elem.get("{http://www.w3.org/XML/1998/namespace}id") or ""
                records.append({
                    "title": title,
                    "abstract": abstract,
                    "snippet": abstract[:350],
                    "authors": [
                        (c.text or "").strip()
                        for c in elem.findall(f"{DC}creator")[:6]
                        if (c.text or "").strip()
                    ],
                    "year": (elem.findtext(f"{DC}date") or "").strip(),
                    "url": identifier or (
                        f"https://agris.fao.org/search/en/providers/{code}/records/{rec_id}"
                        if rec_id else "https://agris.fao.org/"
                    ),
                    "document_type": (elem.findtext(f"{DC}type") or "article").strip(),
                })
            elem.clear()
    except Exception as exc:
        logger.warning("AGRIS ODS parse failed for %s: %s", path.name, exc)
    return records


def load_records(force: bool = False) -> List[Dict]:
    """Download (once) and parse the configured subsets. Cached in memory."""
    global _records
    with _lock:
        if _records is not None and not force:
            return _records

        all_records: List[Dict] = []
        for code in configured_subsets():
            path = _download_subset(code)
            if path is None:
                continue
            subset_records = _parse_subset(path, code)
            logger.info("AGRIS ODS subset %s -> %d records", code, len(subset_records))
            all_records.extend(subset_records)

        _records = all_records
        logger.info("AGRIS ODS index ready: %d bibliographic records", len(all_records))
        return _records


def _tokenize(value: str) -> List[str]:
    return re.findall(r"[a-zA-Z]{3,}", (value or "").lower())


def search(queries: List[str], limit: int = 8) -> List[Dict]:
    """
    Rank cached AGRIS records by token overlap with the query terms.

    Never blocks on the index. If the warmup has not finished, this source sits
    the round out and the other nine adapters answer — a slightly thinner
    evidence set beats a request that overruns the client's timeout and shows
    the user nothing at all.
    """
    if not is_ready():
        start_warmup()
        logger.info("AGRIS ODS index still warming; skipping this source for now")
        return []

    records = load_records()
    if not records:
        return []

    tokens = set()
    for q in queries:
        tokens.update(_tokenize(q))
    if not tokens:
        return []

    scored = []
    for rec in records:
        hay = f"{rec['title']} {rec['abstract']}".lower()
        overlap = sum(1 for t in tokens if t in hay)
        if overlap < 2:  # a single common word is not a real match
            continue
        # Prefer records that actually carry an abstract.
        bonus = 1 if len(rec["abstract"]) > 350 else 0
        scored.append((overlap + bonus, rec))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [rec for _score, rec in scored[:limit]]
