"""
Shared client for the USDA National Agricultural Library Primo REST API.

Both AGRICOLA (the NAL catalogue) and PubAg (NAL's article index) are served
by the same Primo/Ex Libris backend. The public web pages at
``pubag.nal.usda.gov`` and ``catalog.nal.usda.gov`` are JavaScript shells with
no server-rendered results, and the old ``catalog.nal.usda.gov/api/v1/``
endpoint no longer resolves at all - which is why both adapters returned zero
records. ``primaws/rest/pub/pnxs`` is the JSON API those pages call, and it
needs no key.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import requests

from ..types import QueryProfile, SourceCallLog

PRIMO_ENDPOINT = "https://search.nal.usda.gov/primaws/rest/pub/pnxs"
PRIMO_VID = "01NAL_INST:MAIN"


def _first(value) -> str:
    """Primo wraps nearly every display field in a single-element list."""
    if isinstance(value, list):
        return str(value[0]).strip() if value else ""
    return str(value or "").strip()


def _join(value) -> str:
    if isinstance(value, list):
        return " ".join(str(v).strip() for v in value if str(v).strip())
    return str(value or "").strip()


def _record_from_doc(doc: Dict) -> Dict:
    """Flatten one Primo ``pnx`` document into the normalizer's schema."""
    pnx = doc.get("pnx") or {}
    display = pnx.get("display") or {}
    addata = pnx.get("addata") or {}
    links = pnx.get("links") or {}

    title = _first(display.get("title"))
    # Abstracts live in addata.abstract; display.description is a fallback.
    abstract = _join(addata.get("abstract")) or _join(display.get("description"))

    url = ""
    for link in links.get("linktorsrc") or []:
        if "$$U" in str(link):
            url = str(link).split("$$U")[-1].split("$$")[0]
            break
    if not url:
        rec_id = doc.get("@id") or _first(display.get("source"))
        if rec_id:
            url = f"https://search.nal.usda.gov/discovery/search?vid={PRIMO_VID}&query=any,contains,{rec_id}"

    return {
        "title": title,
        "abstract": abstract,
        "snippet": abstract[:350],
        "authors": display.get("creator") or addata.get("au") or [],
        "year": _first(display.get("creationdate")) or _first(addata.get("date")),
        "doi": _first(addata.get("doi")),
        "url": url,
        "document_type": _first(display.get("type")) or "article",
    }


def primo_search(
    source_name: str,
    profile: QueryProfile,
    scope: str,
    limit: int = 8,
    timeout: float = 20.0,
) -> Tuple[List[Dict], List[SourceCallLog]]:
    """Query NAL Primo from a QueryProfile and return normalizer-ready records."""
    queries = [
        q
        for q in (
            profile.threat_query,
            profile.crop_query,
            profile.broad_query,
            profile.fallback_query,
        )
        if (q or "").strip()
    ]
    return primo_search_queries(source_name, queries, scope, limit=limit, timeout=timeout)


def primo_search_queries(
    source_name: str,
    queries: List[str],
    scope: str,
    limit: int = 8,
    timeout: float = 20.0,
) -> Tuple[List[Dict], List[SourceCallLog]]:
    """
    Query NAL Primo from a plain list of search strings.

    Kept separate from ``primo_search`` so callers outside the adapter pipeline
    (the diagnosis enrichment path) can reuse this client without constructing
    a QueryProfile.
    """
    # Preserve order, drop duplicates, and keep the call budget small.
    seen_q, ordered = set(), []
    for q in queries:
        q = (q or "").strip()
        if q and q not in seen_q:
            seen_q.add(q)
            ordered.append(q)
    ordered = ordered[:2]

    records: List[Dict] = []
    logs: List[SourceCallLog] = []
    seen_titles = set()

    for query in ordered:
        params = {
            "q": f"any,contains,{query}",
            "vid": PRIMO_VID,
            "tab": scope,
            "scope": scope,
            "limit": limit,
            "offset": 0,
            "lang": "en",
            "sort": "rank",
        }
        call = SourceCallLog(
            source=source_name,
            query=query,
            url=PRIMO_ENDPOINT,
            method="GET",
            payload=params,
        )
        try:
            resp = requests.get(PRIMO_ENDPOINT, params=params, timeout=timeout)
            call.status_code = resp.status_code
            call.raw_sample = (resp.text or "")[:900]
            call.response_type = "json"

            if resp.status_code in {401, 403, 429}:
                call.blocked_error = True
                logs.append(call)
                continue

            parsed = []
            if resp.status_code == 200:
                for doc in (resp.json() or {}).get("docs") or []:
                    rec = _record_from_doc(doc)
                    key = rec["title"].lower()
                    if not rec["title"] or key in seen_titles:
                        continue
                    seen_titles.add(key)
                    parsed.append(rec)

            call.parsed_item_count = len(parsed)
            call.preview_items = parsed[:3]
            records.extend(parsed)
        except requests.Timeout:
            call.timeout_error = True
        except Exception as exc:  # network/JSON errors must not kill the pipeline
            call.other_error = str(exc)
        logs.append(call)

    return records, logs
