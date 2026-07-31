from __future__ import annotations

from typing import Dict, List, Tuple

from .base import AdapterCapability, SourceAdapter
from .nal_primo import primo_search
from ..types import QueryProfile, SourceCallLog


class PubAgAdapter(SourceAdapter):
    """
    PubAg via the USDA NAL Primo REST API.

    The previous implementation scraped ``pubag.nal.usda.gov``, which redirects
    to a Primo JavaScript single-page app. The HTML returned is a ~4 KB shell
    with no results in it, so scraping yielded zero records every time.
    """

    source_name = "PubAg"

    def capability(self) -> AdapterCapability:
        return AdapterCapability(
            source="PubAg",
            access_type="NAL Primo REST API (public, no key)",
            expected_result_type="journal article metadata + abstracts",
            full_text_likely=False,
            metadata_only_likely=False,
            reliability="high",
            source_group="primary_research",
            enrichment_only=False,
            notes="USDA NAL peer-reviewed article index via search.nal.usda.gov.",
        )

    def build_requests(self, profile: QueryProfile) -> List[Dict]:
        # Unused: search() is overridden because Primo needs bespoke parsing.
        return []

    def search(self, profile: QueryProfile) -> Tuple[List[Dict], List[SourceCallLog]]:
        return primo_search(self.source_name, profile, scope="pubag")
