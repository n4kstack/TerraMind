from __future__ import annotations

from typing import Dict, List, Tuple

from .base import AdapterCapability, SourceAdapter
from .nal_primo import primo_search
from ..types import QueryProfile, SourceCallLog


class AgricolaAdapter(SourceAdapter):
    """
    AGRICOLA via the USDA NAL Primo REST API.

    The previous implementation called ``catalog.nal.usda.gov/api/v1/``, which
    no longer resolves (DNS/connection failure), so this adapter returned zero
    records on every query.
    """

    source_name = "AGRICOLA"

    def capability(self) -> AdapterCapability:
        return AdapterCapability(
            source="AGRICOLA",
            access_type="NAL Primo REST API (public, no key)",
            expected_result_type="bibliographic metadata + abstracts",
            full_text_likely=False,
            metadata_only_likely=False,
            reliability="high",
            source_group="primary_research",
            enrichment_only=False,
            notes="USDA National Agricultural Library catalogue via search.nal.usda.gov.",
        )

    def build_requests(self, profile: QueryProfile) -> List[Dict]:
        # Unused: search() is overridden because Primo needs bespoke parsing.
        return []

    def search(self, profile: QueryProfile) -> Tuple[List[Dict], List[SourceCallLog]]:
        return primo_search(self.source_name, profile, scope="agricola")
