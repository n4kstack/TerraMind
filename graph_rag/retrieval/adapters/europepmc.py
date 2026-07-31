"""
Europe PMC adapter.

Replaces the CABI adapter, which returns HTTP 403 for every request: CABI
Digital Library content is subscription-gated and bot-protected, so it cannot
be retrieved without an institutional entitlement. Europe PMC is free, needs no
key, and covers plant pathology, entomology and agronomy with full abstracts.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import requests

from .base import AdapterCapability, SourceAdapter
from ..types import QueryProfile, SourceCallLog

EPMC_ENDPOINT = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


class EuropePmcAdapter(SourceAdapter):
    source_name = "EuropePMC"

    def capability(self) -> AdapterCapability:
        return AdapterCapability(
            source="EuropePMC",
            access_type="public REST API (no key)",
            expected_result_type="peer-reviewed metadata + full abstracts",
            full_text_likely=True,
            metadata_only_likely=False,
            reliability="high",
            source_group="primary_research",
            enrichment_only=False,
            notes="Life-science literature incl. plant pathology and entomology.",
        )

    def build_requests(self, profile: QueryProfile) -> List[Dict]:
        # Unused: search() is overridden for Europe PMC's result envelope.
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
                "query": query,
                "format": "json",
                "pageSize": 8,
                "resultType": "core",  # "core" is what includes abstractText
                "sort": "CITED desc",
            }
            call = SourceCallLog(
                source=self.source_name,
                query=query,
                url=EPMC_ENDPOINT,
                method="GET",
                payload=params,
            )
            try:
                resp = requests.get(EPMC_ENDPOINT, params=params, timeout=self.timeout_seconds)
                call.status_code = resp.status_code
                call.raw_sample = (resp.text or "")[:900]
                call.response_type = "json"

                if resp.status_code in {401, 403, 429}:
                    call.blocked_error = True
                    logs.append(call)
                    continue

                parsed = []
                if resp.status_code == 200:
                    results = ((resp.json() or {}).get("resultList") or {}).get("result") or []
                    for item in results:
                        title = (item.get("title") or "").strip()
                        if not title or title.lower() in seen_titles:
                            continue
                        seen_titles.add(title.lower())
                        abstract = (item.get("abstractText") or "").strip()
                        doi = (item.get("doi") or "").strip()
                        pmid = item.get("pmid") or item.get("id") or ""
                        parsed.append({
                            "title": title,
                            "abstract": abstract,
                            "snippet": abstract[:350],
                            "authors": [item.get("authorString") or ""],
                            "year": item.get("pubYear"),
                            "doi": doi,
                            "url": (
                                f"https://doi.org/{doi}" if doi
                                else f"https://europepmc.org/article/MED/{pmid}"
                            ),
                            "document_type": item.get("pubType") or "article",
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
