"""
External data source fetchers for enriching the Graph RAG knowledge base.
==========================================================================
Provides async functions to retrieve agricultural research documents from
AGRIS (FAO) and AGRICOLA (USDA NAL) APIs.  Results are cached locally as
JSON files so the same (crop, disease) pair never triggers a repeat call.
"""

import asyncio
import json
import logging
import re
import html
from pathlib import Path
from typing import List

import httpx

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(__file__).resolve().parent / "cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

_TIMEOUT = 10.0
_MAX_RETRIES = 3
_BACKOFF_FACTORS = [1, 2, 4]


def _sanitize_key(crop: str, disease: str) -> str:
    """Build a filesystem-safe cache key from crop + disease strings."""
    safe = re.sub(r"[^a-zA-Z0-9]", "_", f"{crop}__{disease}").lower()
    return safe


def _load_cache(cache_key: str, source: str) -> List[str] | None:
    """Return cached results for *source*, or ``None`` if cache miss."""
    path = _CACHE_DIR / f"{cache_key}_{source}.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            # An empty cached result is treated as a miss, not a hit. The old
            # endpoints returned nothing for every query, so empty files were
            # written for each crop/disease pair; honouring them would pin the
            # fetchers at zero results forever even after they were repaired.
            if not data:
                logger.info("Cache STALE-EMPTY for %s [%s]; refetching", cache_key, source)
                return None
            logger.info("Cache HIT for %s [%s]", cache_key, source)
            return data
        except Exception as exc:
            logger.warning("Cache read error for %s [%s]: %s", cache_key, source, exc)
    return None


def _format_record(record: dict) -> str:
    """Flatten a retrieval record dict into the 'title. abstract' form callers expect."""
    title = str(record.get("title") or "").strip()
    abstract = str(record.get("abstract") or record.get("snippet") or "").strip()
    if not title and not abstract:
        return ""
    text = f"{title}. {abstract}".strip() if title else abstract
    return text if text != "." else ""


def _save_cache(cache_key: str, source: str, results: List[str]) -> None:
    """Persist fetched results to local JSON cache."""
    path = _CACHE_DIR / f"{cache_key}_{source}.json"
    try:
        path.write_text(json.dumps(results, ensure_ascii=False), encoding="utf-8")
        logger.info("Cached %d results for %s [%s]", len(results), cache_key, source)
    except Exception as exc:
        logger.warning("Cache write error for %s [%s]: %s", cache_key, source, exc)


def _extract_html_candidates(raw_html: str, crop: str, disease: str) -> List[str]:
    if not raw_html:
        return []

    text = re.sub(r"<script[\\s\\S]*?</script>", " ", raw_html, flags=re.IGNORECASE)
    text = re.sub(r"<style[\\s\\S]*?</style>", " ", text, flags=re.IGNORECASE)

    blocks = []
    blocks.extend(re.findall(r"<h[1-4][^>]*>([\\s\\S]*?)</h[1-4]>", text, flags=re.IGNORECASE))
    blocks.extend(re.findall(r"<a[^>]*>([\\s\\S]*?)</a>", text, flags=re.IGNORECASE))
    blocks.extend(re.findall(r"<p[^>]*>([\\s\\S]*?)</p>", text, flags=re.IGNORECASE))

    keywords = {t.lower() for t in re.findall(r"[a-zA-Z]{3,}", f"{crop} {disease}")}
    scored = []
    seen = set()

    for block in blocks:
        cleaned = re.sub(r"<[^>]+>", " ", block)
        cleaned = html.unescape(cleaned)
        cleaned = re.sub(r"\\s+", " ", cleaned).strip()
        if len(cleaned) < 30 or len(cleaned) > 280:
            continue
        if cleaned.lower() in seen:
            continue
        seen.add(cleaned.lower())

        lower = cleaned.lower()
        score = sum(1 for k in keywords if k in lower)
        if score > 0:
            scored.append((score, cleaned))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored[:10]]


async def _fetch_html_source(source: str, crop: str, disease: str, url: str, params: dict) -> List[str]:
    cache_key = _sanitize_key(crop, disease)
    cached = _load_cache(cache_key, source)
    if cached is not None:
        return cached

    query = f"{crop} {disease}".replace("_", " ")
    results: List[str] = []

    for attempt in range(_MAX_RETRIES):
        try:
            logger.info("%s fetch attempt %d/%d for '%s'", source.upper(), attempt + 1, _MAX_RETRIES, query)
            async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()

            results = _extract_html_candidates(resp.text, crop, disease)
            logger.info("%s returned %d candidate snippets for '%s'", source.upper(), len(results), query)
            break
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            backoff = _BACKOFF_FACTORS[attempt] if attempt < len(_BACKOFF_FACTORS) else 4
            logger.warning(
                "%s attempt %d failed (%s). Retrying in %ds…",
                source.upper(), attempt + 1, type(exc).__name__, backoff,
            )
            await asyncio.sleep(backoff)
        except Exception as exc:
            logger.error("%s unexpected error: %s", source.upper(), exc)
            break

    _save_cache(cache_key, source, results)
    return results


# ── AGRIS (FAO) ─────────────────────────────────────────────────────────────


async def fetch_agris(crop: str, disease: str) -> List[str]:
    """
    Fetch agricultural research abstracts from AGRIS (FAO).

    Parameters
    ----------
    crop : str
        The crop name (e.g. ``"Tomato"``).
    disease : str
        The disease name or label (e.g. ``"Late_blight"``).

    Returns
    -------
    list[str]
        List of plain-text strings (title + abstract per document).
    """
    cache_key = _sanitize_key(crop, disease)
    cached = _load_cache(cache_key, "agris")
    if cached is not None:
        return cached

    query = f"{crop} {disease}".replace("_", " ")
    results: List[str] = []

    # Preferred path: the local AGRIS Open Data Set index of real bibliographic
    # records. The agris.fao.org search endpoint below is Cloudflare-protected
    # (HTTP 403) and returned nothing for every crop/disease pair, which is why
    # diagnosis enrichment was a silent no-op.
    try:
        from graph_rag.retrieval import agris_ods

        ods_hits = await asyncio.to_thread(
            agris_ods.search, [query, crop, f"{disease} management".replace("_", " ")], 8
        )
        results = [_format_record(rec) for rec in ods_hits]
        results = [r for r in results if r]
        if results:
            logger.info("AGRIS ODS returned %d documents for '%s'", len(results), query)
            _save_cache(cache_key, "agris", results)
            return results
    except Exception as exc:
        logger.warning("AGRIS ODS lookup failed for '%s': %s", query, exc)

    url = "https://agris.fao.org/agris-search/search.do"
    params = {"query": query, "format": "json"}

    for attempt in range(_MAX_RETRIES):
        try:
            logger.info(
                "AGRIS fetch attempt %d/%d for '%s'", attempt + 1, _MAX_RETRIES, query
            )
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()

            data = resp.json()
            records = data if isinstance(data, list) else data.get("results", data.get("records", []))
            if isinstance(records, list):
                for rec in records[:10]:
                    title = rec.get("title", rec.get("dcTitle", ""))
                    abstract = rec.get("abstract", rec.get("dcDescription", ""))
                    if isinstance(title, list):
                        title = " ".join(str(t) for t in title)
                    if isinstance(abstract, list):
                        abstract = " ".join(str(a) for a in abstract)
                    text = f"{title}. {abstract}".strip()
                    if text and text != ".":
                        results.append(text)

            logger.info("AGRIS returned %d documents for '%s'", len(results), query)
            break

        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            backoff = _BACKOFF_FACTORS[attempt] if attempt < len(_BACKOFF_FACTORS) else 4
            logger.warning(
                "AGRIS attempt %d failed (%s). Retrying in %ds…",
                attempt + 1, type(exc).__name__, backoff,
            )
            await asyncio.sleep(backoff)
        except Exception as exc:
            logger.error("AGRIS unexpected error: %s", exc)
            break

    _save_cache(cache_key, "agris", results)
    return results


# ── AGRICOLA (USDA NAL) ─────────────────────────────────────────────────────


async def fetch_agricola(crop: str, disease: str) -> List[str]:
    """
    Fetch agricultural research records from AGRICOLA (USDA NAL).

    Parameters
    ----------
    crop : str
        The crop name (e.g. ``"Tomato"``).
    disease : str
        The disease name or label (e.g. ``"Late_blight"``).

    Returns
    -------
    list[str]
        List of plain-text strings (title + description per record).
    """
    cache_key = _sanitize_key(crop, disease)
    cached = _load_cache(cache_key, "agricola")
    if cached is not None:
        return cached

    query = f"{crop} {disease}".replace("_", " ")
    results: List[str] = []

    # Preferred path: the NAL Primo REST API. The catalog.nal.usda.gov endpoint
    # below no longer resolves at all, so this fetcher returned zero records for
    # every crop/disease pair.
    try:
        from graph_rag.retrieval.adapters.nal_primo import primo_search_queries

        records, _logs = await asyncio.to_thread(
            primo_search_queries,
            "AGRICOLA",
            [query, f"{crop} {disease} control".replace("_", " ")],
            "agricola",
            8,
        )
        results = [r for r in (_format_record(rec) for rec in records) if r]
        if results:
            logger.info("AGRICOLA (Primo) returned %d records for '%s'", len(results), query)
            _save_cache(cache_key, "agricola", results)
            return results
    except Exception as exc:
        logger.warning("AGRICOLA Primo lookup failed for '%s': %s", query, exc)

    url = "https://catalog.nal.usda.gov/api/v1/"
    params = {"query": query, "format": "json"}

    for attempt in range(_MAX_RETRIES):
        try:
            logger.info(
                "AGRICOLA fetch attempt %d/%d for '%s'",
                attempt + 1, _MAX_RETRIES, query,
            )
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()

            data = resp.json()
            records = data if isinstance(data, list) else data.get("results", data.get("records", []))
            if isinstance(records, list):
                for rec in records[:10]:
                    title = rec.get("title", "")
                    description = rec.get("abstract", rec.get("description", ""))
                    if isinstance(title, list):
                        title = " ".join(str(t) for t in title)
                    if isinstance(description, list):
                        description = " ".join(str(d) for d in description)
                    text = f"{title}. {description}".strip()
                    if text and text != ".":
                        results.append(text)

            logger.info("AGRICOLA returned %d documents for '%s'", len(results), query)
            break

        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            backoff = _BACKOFF_FACTORS[attempt] if attempt < len(_BACKOFF_FACTORS) else 4
            logger.warning(
                "AGRICOLA attempt %d failed (%s). Retrying in %ds…",
                attempt + 1, type(exc).__name__, backoff,
            )
            await asyncio.sleep(backoff)
        except Exception as exc:
            logger.error("AGRICOLA unexpected error: %s", exc)
            break

    _save_cache(cache_key, "agricola", results)
    return results


# ── Additional external sources for retrieval augmentation ────────────────


async def fetch_pubag(crop: str, disease: str) -> List[str]:
    query = f"{crop} {disease}".replace("_", " ")
    return await _fetch_html_source(
        "pubag",
        crop,
        disease,
        "https://pubag.nal.usda.gov/",
        {"q": query},
    )


async def fetch_cabi(crop: str, disease: str) -> List[str]:
    query = f"{crop} {disease}".replace("_", " ")
    return await _fetch_html_source(
        "cabi",
        crop,
        disease,
        "https://www.cabidigitallibrary.org/action/doSearch",
        {"AllField": query},
    )


async def fetch_agecon(crop: str, disease: str) -> List[str]:
    query = f"{crop} {disease}".replace("_", " ")
    return await _fetch_html_source(
        "agecon",
        crop,
        disease,
        "https://ageconsearch.umn.edu/search",
        {"q": query},
    )


async def fetch_asabe(crop: str, disease: str) -> List[str]:
    query = f"{crop} {disease}".replace("_", " ")
    return await _fetch_html_source(
        "asabe",
        crop,
        disease,
        "https://elibrary.asabe.org/search",
        {"q": query},
    )
