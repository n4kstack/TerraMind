from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Dict, List

from .base import AdapterCapability, SourceAdapter
from .. import agris_ods
from ..types import QueryProfile, SourceCallLog


class AgrisAdapter(SourceAdapter):
    source_name = "AGRIS"

    def capability(self) -> AdapterCapability:
        return AdapterCapability(
            source="AGRIS",
            access_type="AGRIS Open Data Set XML subsets (CC-BY-4.0)",
            expected_result_type="bibliographic metadata + abstracts",
            full_text_likely=False,
            metadata_only_likely=False,
            reliability="high",
            source_group="primary_research",
            enrichment_only=False,
            notes=(
                "Searches real AGRIS bibliographic records downloaded from "
                "agris.fao.org/ods/ (see retrieval/agris_ods.py). Subsets are "
                "configurable via AGRIS_ODS_SUBSETS and default to Indian "
                "agricultural research (ICAR and allied societies). The DCAT "
                "catalogue under 'graph rag source' describes datasets rather "
                "than research, and is only a fallback."
            ),
        )

    def build_requests(self, profile: QueryProfile) -> List[Dict]:
        candidates = [
            profile.threat_query,
            profile.crop_query,
            profile.broad_query,
            profile.region_query,
            profile.fallback_query,
            profile.phrase_query,
        ]

        # Mandatory query expansion: weather, stage, and epidemiology variants.
        if profile.crop:
            weather = " ".join(profile.weather_terms) if profile.weather_terms else ""
            candidates.extend(
                [
                    f"{profile.crop} pest outbreak {weather} {profile.region or ''}".strip(),
                    f"{profile.crop} disease epidemiology {weather} {profile.growth_stage or ''}".strip(),
                    f"{profile.crop} integrated pest management {profile.region or ''}".strip(),
                    f"{profile.crop} fungal disease humidity temperature".strip(),
                ]
            )

        queries = []
        for q in candidates:
            q = (q or "").strip()
            if not q or q in queries:
                continue
            queries.append(q)

        queries = queries[:10]

        return [
            {
                "url": "https://agris.fao.org/search/en",
                "params": {
                    "area": "pest_control",
                    "q": q,
                },
                "query": q,
            }
            for q in queries
        ]

    def search(self, profile: QueryProfile) -> (List[Dict], List[SourceCallLog]):
        # Preferred path: the real AGRIS bibliographic records from the Open
        # Data Set subsets. The legacy paths below search the DCAT catalogue
        # (dataset descriptors, not research) and are kept only as a fallback
        # for when the ODS files cannot be downloaded.
        queries = [
            q for q in (
                profile.threat_query,
                profile.crop_query,
                profile.broad_query,
                profile.fallback_query,
            ) if (q or "").strip()
        ]
        ods_call = SourceCallLog(
            source=self.source_name,
            query=queries[0] if queries else "",
            url="https://agris.fao.org/ods/",
            method="ODS",
            payload={"mode": "agris_open_data_set_records"},
        )
        try:
            ods_records = agris_ods.search(queries, limit=8)
            ods_call.status_code = 200
            ods_call.response_type = "xml"
            ods_call.parsed_item_count = len(ods_records)
            ods_call.preview_items = ods_records[:3]
            if ods_records:
                return ods_records, [ods_call]
        except Exception as exc:
            ods_call.other_error = str(exc)

        local_records, local_logs = self._search_local_file(profile)
        if local_records:
            return local_records, [ods_call] + local_logs
        web_records, web_logs = super().search(profile)
        return web_records, [ods_call] + local_logs + web_logs

    def _search_local_file(self, profile: QueryProfile) -> (List[Dict], List[SourceCallLog]):
        source_file = self._find_local_source_file()
        queries = [
            q for q in [
                profile.threat_query,
                profile.crop_query,
                profile.broad_query,
                profile.region_query,
                profile.fallback_query,
            ]
            if q
        ]
        query_text = " ".join(queries)[:800] or profile.user_query
        call = SourceCallLog(
            source=self.source_name,
            query=query_text,
            url=str(source_file) if source_file else "local://graph rag source/AGRIS",
            method="FILE",
            payload={"mode": "local_file", "query_count": len(queries)},
        )

        if source_file is None:
            call.other_error = "Local AGRIS XML/ODS file not found"
            return [], [call]

        try:
            parsed_records = self._parse_local_source(source_file)
            filtered = self._filter_records_for_query(parsed_records, query_text)
            call.status_code = 200
            call.response_type = source_file.suffix.lower().lstrip(".") or "file"
            call.parsed_item_count = len(parsed_records)
            call.normalized_item_count = len(filtered)
            call.preview_items = filtered[:3]
            return filtered, [call]
        except Exception as exc:
            call.other_error = str(exc)
            return [], [call]

    def _find_local_source_file(self) -> Path | None:
        project_root = Path(__file__).resolve().parents[3]
        candidate_dirs = [
            project_root / "graph rag source",
            project_root / "graph_rag_source",
            project_root / "graph_rag" / "source",
        ]

        file_patterns = [
            "AGRIS.ODS.xml",
            "agris.ods.xml",
            "AGRIS*.xml",
            "agris*.xml",
            "AGRIS*.ods",
            "agris*.ods",
            "*.xml",
            "*.ods",
        ]

        for cdir in candidate_dirs:
            if not cdir.exists() or not cdir.is_dir():
                continue
            for pattern in file_patterns:
                matches = sorted(cdir.glob(pattern))
                if matches:
                    return matches[0]
        return None

    def _parse_local_source(self, source_file: Path) -> List[Dict]:
        suffix = source_file.suffix.lower()
        if suffix == ".xml":
            text = source_file.read_text(encoding="utf-8", errors="ignore")
            dcat_records = self._parse_agris_dcat_xml(text)
            if dcat_records:
                return dcat_records
            return self._parse_xml_text(text)

        if suffix == ".ods":
            if zipfile.is_zipfile(source_file):
                with zipfile.ZipFile(source_file, "r") as zf:
                    if "content.xml" in zf.namelist():
                        xml_text = zf.read("content.xml").decode("utf-8", errors="ignore")
                        dcat_records = self._parse_agris_dcat_xml(xml_text)
                        if dcat_records:
                            return dcat_records
                        return self._parse_xml_text(xml_text)
            text = source_file.read_text(encoding="utf-8", errors="ignore")
            dcat_records = self._parse_agris_dcat_xml(text)
            if dcat_records:
                return dcat_records
            return self._parse_xml_text(text)

        return []

    def _parse_agris_dcat_xml(self, text: str) -> List[Dict]:
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return []

        records: List[Dict] = []
        for elem in root.iter():
            if self._local_name(elem.tag) != "dataset":
                continue

            direct_values = self._collect_direct_tag_values(elem)
            nested_values = self._collect_tag_values(elem)

            title = self._pick(direct_values, ["title"]) or self._pick(nested_values, ["title"])
            dataset_id = self._pick(direct_values, ["identifier"]) or self._pick(nested_values, ["identifier"])
            description = self._pick(direct_values, ["description"]) or self._pick(nested_values, ["description"])

            # Skip wrapper nodes like <dcat:dataset> that only contain nested Dataset blocks.
            if not title and not dataset_id and not description:
                continue

            authors = self._pick_list(direct_values, ["creator", "publisher"])
            if not authors:
                authors = self._pick_list(nested_values, ["creator", "publisher"])

            year = self._pick(direct_values, ["modified", "date"]) or self._pick(nested_values, ["modified", "date"])
            url = self._pick(
                nested_values,
                ["downloadurl", "landingpage", "accessurl", "url", "link", "source"],
            )

            records.append(
                {
                    "source": "AGRIS",
                    "title": title or f"AGRIS Dataset {dataset_id}" if dataset_id else "AGRIS Dataset",
                    "abstract": description,
                    "authors": authors,
                    "year": year,
                    "doi": "",
                    "url": url,
                    "document_type": "metadata",
                    "dataset_id": dataset_id,
                }
            )

        return records

    def _parse_xml_text(self, text: str) -> List[Dict]:
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return []

        records: List[Dict] = []
        tag_candidates = ["record", "doc", "item", "entry", "row"]
        elems = []
        for elem in root.iter():
            local = self._local_name(elem.tag)
            if local in tag_candidates:
                elems.append(elem)

        if not elems:
            elems = list(root.iter())

        for elem in elems[:3000]:
            values = self._collect_tag_values(elem)
            title = self._pick(values, ["title", "dc:title", "name", "heading"]) 
            abstract = self._pick(values, ["abstract", "dc:description", "description", "summary"])
            authors = self._pick_list(values, ["author", "creator", "dc:creator"])
            year = self._pick(values, ["year", "date", "dc:date"])
            doi = self._pick(values, ["doi", "identifier"])
            url = self._pick(values, ["url", "link", "recordurl", "source"])

            if not title and not abstract:
                continue

            records.append(
                {
                    "source": "AGRIS",
                    "title": title,
                    "abstract": abstract,
                    "authors": authors,
                    "year": year,
                    "doi": doi,
                    "url": url,
                    "document_type": "metadata",
                }
            )

        deduped: List[Dict] = []
        seen = set()
        for rec in records:
            key = (rec.get("title", "").strip().lower(), rec.get("url", "").strip().lower())
            if key in seen:
                continue
            seen.add(key)
            deduped.append(rec)
        return deduped

    def _filter_records_for_query(self, records: List[Dict], query: str) -> List[Dict]:
        tokens = set(re.findall(r"[a-zA-Z]{3,}", (query or "").lower()))
        if not tokens:
            return records[:50]

        ranked = []
        for rec in records:
            hay = f"{rec.get('title', '')} {rec.get('abstract', '')}".lower()
            score = sum(1 for t in tokens if t in hay)
            if score > 0:
                ranked.append((score, rec))

        if not ranked:
            return records[:50]

        ranked.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in ranked[:50]]

    @staticmethod
    def _local_name(tag: str) -> str:
        if "}" in tag:
            return tag.split("}", 1)[1].lower()
        return str(tag).lower()

    def _collect_tag_values(self, elem: ET.Element) -> Dict[str, List[str]]:
        values: Dict[str, List[str]] = {}
        for child in elem.iter():
            key = self._local_name(child.tag)
            txt = (child.text or "").strip()
            if not txt:
                continue
            values.setdefault(key, []).append(txt)
        return values

    def _collect_direct_tag_values(self, elem: ET.Element) -> Dict[str, List[str]]:
        values: Dict[str, List[str]] = {}
        for child in list(elem):
            key = self._local_name(child.tag)
            txt = (child.text or "").strip()
            if not txt:
                continue
            values.setdefault(key, []).append(txt)
        return values

    @staticmethod
    def _pick(values: Dict[str, List[str]], keys: List[str]) -> str:
        for k in keys:
            lk = k.split(":")[-1].lower()
            if lk in values and values[lk]:
                return values[lk][0]
        return ""

    @staticmethod
    def _pick_list(values: Dict[str, List[str]], keys: List[str]) -> List[str]:
        for k in keys:
            lk = k.split(":")[-1].lower()
            if lk in values and values[lk]:
                return [x for x in values[lk] if x]
        return []
