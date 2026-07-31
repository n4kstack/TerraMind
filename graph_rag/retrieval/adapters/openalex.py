"""
OpenAlex adapter.

Replaces the ASABE adapter, whose endpoint (``elibrary.asabe.org/search``)
resets the connection on every request - it is not retrievable without an
agreement with ASABE. OpenAlex is free, needs no key, indexes agricultural
engineering and plant science comprehensively, and - unlike the catalogue
sources - carries real abstracts.
"""

from __future__ import annotations

import os
from typing import Dict, List, Tuple

import requests

from .base import AdapterCapability, SourceAdapter
from ..types import QueryProfile, SourceCallLog

OPENALEX_ENDPOINT = "https://api.openalex.org/works"
# OpenAlex asks for a contact address to use the faster "polite pool".
CONTACT = os.getenv("OPENALEX_CONTACT_EMAIL", "terramind-research@example.org")


def _decode_abstract(inverted: Dict) -> str:
    """OpenAlex stores abstracts as {word: [positions]}; rebuild the text."""
    if not isinstance(inverted, dict) or not inverted:
        return ""
    positions: Dict[int, str] = {}
    for word, idxs in inverted.items():
        if isinstance(idxs, list):
            for i in idxs:
                positions[i] = word
    if not positions:
        return ""
    return " ".join(positions[i] for i in sorted(positions))


class OpenAlexAdapter(SourceAdapter):
    source_name = "OpenAlex"

    def capability(self) -> AdapterCapability:
        return AdapterCapability(
            source="OpenAlex",
            access_type="public REST API (no key)",
            expected_result_type="peer-reviewed metadata + full abstracts",
            full_text_likely=False,
            metadata_only_likely=False,
            reliability="high",
            source_group="primary_research",
            enrichment_only=False,
            notes="Open bibliographic index; abstracts reconstructed from inverted index.",
        )

    def build_requests(self, profile: QueryProfile) -> List[Dict]:
        # Unused: search() is overridden to decode the inverted abstract index.
        return []

    def search(self, profile: QueryProfile) -> Tuple[List[Dict], List[SourceCallLog]]:
        queries = [
            q for q in (profile.threat_query, profile.crop_query, profile.broad_query)
            if (q or "").strip()
        ]
        seen_q, ordered = set(), []
        for q in queries:
            if q not in seen_q:
                seen_q.add(q)
                ordered.append(q)

        records: List[Dict] = []
        logs: List[SourceCallLog] = []
        seen_titles = set()

        for query in ordered[:2]:
            params = {
                "search": query,
                "per-page": 8,
                "mailto": CONTACT,
                # Reviews and retracted work are poor operational guidance.
                "filter": "is_retracted:false",
            }
            call = SourceCallLog(
                source=self.source_name,
                query=query,
                url=OPENALEX_ENDPOINT,
                method="GET",
                payload=params,
            )
            try:
                resp = requests.get(OPENALEX_ENDPOINT, params=params, timeout=self.timeout_seconds)
                call.status_code = resp.status_code
                call.raw_sample = (resp.text or "")[:900]
                call.response_type = "json"

                if resp.status_code in {401, 403, 429}:
                    call.blocked_error = True
                    logs.append(call)
                    continue

                parsed = []
                if resp.status_code == 200:
                    for work in (resp.json() or {}).get("results") or []:
                        title = (work.get("title") or "").strip()
                        if not title or title.lower() in seen_titles:
                            continue
                        seen_titles.add(title.lower())
                        abstract = _decode_abstract(work.get("abstract_inverted_index") or {})
                        loc = work.get("primary_location") or {}
                        parsed.append({
                            "title": title,
                            "abstract": abstract,
                            "snippet": abstract[:350],
                            "authors": [
                                (a.get("author") or {}).get("display_name", "")
                                for a in (work.get("authorships") or [])[:6]
                            ],
                            "year": work.get("publication_year"),
                            "doi": (work.get("doi") or "").replace("https://doi.org/", ""),
                            "url": loc.get("landing_page_url") or work.get("id") or "",
                            "pdf_url": loc.get("pdf_url") or "",
                            "document_type": work.get("type") or "article",
                        })

                call.parsed_item_count = len(parsed)
                call.preview_items = parsed[:3]
                records.extend(parsed)
            except requests.Timeout:
                call.timeout_error = True
            except Exception as exc:
                call.other_error = str(exc)
            logs.append(call)

        return records, logs
