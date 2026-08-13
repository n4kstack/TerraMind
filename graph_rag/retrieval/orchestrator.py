from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeout
from dataclasses import dataclass
import logging
import os
from typing import Dict, List, Optional

from .adapters import default_adapters
from .context_builder import build_external_context
from .grounding_policy import GroundingDecision, evaluate_grounding
from .normalizer import normalize_records
from .query_builder import build_query_profile
from .reranker import score_documents
from .structured_logger import RetrievalStructuredLogger
from .types import RetrievalResult, SourceCallLog

logger = logging.getLogger(__name__)


@dataclass
class RetrievalPipelineOutput:
    retrieval: RetrievalResult
    context_text: str
    grounding: GroundingDecision
    capability_matrix: List[Dict]


class ExternalRetrievalOrchestrator:
    """Model-agnostic external retrieval pipeline for Graph RAG grounding."""

    def __init__(self):
        self.adapters = default_adapters()
        self.logger = RetrievalStructuredLogger()
        self.min_docs = int(os.getenv("GRAPH_RAG_MIN_RETRIEVAL_DOCS", "5"))
        self.max_docs = int(os.getenv("GRAPH_RAG_MAX_RETRIEVAL_DOCS", "10"))
        # Measured at ~9s across all ten sources on a normal day, so 45s is
        # generous headroom while still leaving the bulk of the request budget
        # for generation.
        self.retrieval_budget_seconds = float(os.getenv("GRAPH_RAG_RETRIEVAL_BUDGET", "45"))

    def capability_matrix(self) -> List[Dict]:
        return [a.capability().__dict__ for a in self.adapters]

    def run(self, user_query: str, parsed_intent, has_local_kb_context: bool) -> RetrievalPipelineOutput:
        profile = build_query_profile(user_query, parsed_intent)

        all_docs = []
        source_counts: Dict[str, int] = defaultdict(int)
        all_logs: List[SourceCallLog] = []
        capability_by_source: Dict[str, Dict] = {}

        # Adapters are independent network calls, so run them concurrently.
        # Sequentially this loop cost ~60s; the slowest single source now sets
        # the floor instead of the sum of all ten.
        def _run(adapter):
            try:
                return adapter, adapter.search(profile)
            except Exception:
                # A failing source must never take down the pipeline.
                return adapter, ([], [])

        # ...and even the slowest single source is capped. Concurrency alone
        # left this unbounded: an adapter issues up to ten sequential requests
        # at 12s each, so one unresponsive host could hold the whole request for
        # two minutes and leave nothing in the budget for generation. Stragglers
        # are abandoned and whatever finished in time is used.
        results = []
        # Deliberately not a `with` block: its __exit__ calls shutdown(wait=True),
        # which re-joins the very stragglers the timeout just abandoned and hands
        # back the time we saved. Shut down without waiting instead — an
        # in-flight request finishes into a result nobody reads.
        pool = ThreadPoolExecutor(max_workers=len(self.adapters) or 1)
        futures = {pool.submit(_run, a): a for a in self.adapters}
        try:
            for fut in as_completed(futures, timeout=self.retrieval_budget_seconds):
                try:
                    results.append(fut.result())
                except Exception:
                    results.append((futures[fut], ([], [])))
        except FuturesTimeout:
            slow = [futures[f].source_name for f in futures if not f.done()]
            logger.warning(
                "External retrieval hit its %.0fs budget; proceeding without: %s",
                self.retrieval_budget_seconds,
                ", ".join(slow) or "-",
            )
            for f, adapter in futures.items():
                if f.done():
                    try:
                        results.append(f.result())
                    except Exception:
                        results.append((adapter, ([], [])))
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

        for adapter, (raw_records, logs) in results:
            capability = adapter.capability()
            capability_by_source[adapter.source_name] = capability.__dict__

            normalized_docs = normalize_records(
                adapter.source_name,
                raw_records,
                profile,
                source_group=capability.source_group,
                enrichment_only=capability.enrichment_only,
            )
            for call in logs:
                call.normalized_item_count = len(normalized_docs)
                self.logger.log_call(call)
            all_logs.extend(logs)

            source_counts[adapter.source_name] += len(normalized_docs)
            all_docs.extend(normalized_docs)

        all_docs = self._dedupe_across_sources(all_docs)
        ranked_docs = score_documents(profile, all_docs)
        final_docs = self._apply_source_group_policy(ranked_docs)

        retrieval = RetrievalResult(
            query_profile=profile,
            documents=final_docs,
            source_counts=dict(source_counts),
            source_logs=all_logs,
        )
        self.logger.log_summary(profile.user_query, retrieval.source_counts, all_logs)

        context_text = build_external_context(final_docs)
        grounding = evaluate_grounding(
            total_external_docs=retrieval.total_docs,
            metadata_only=retrieval.metadata_only,
            has_local_kb_context=has_local_kb_context,
        )

        return RetrievalPipelineOutput(
            retrieval=retrieval,
            context_text=context_text,
            grounding=grounding,
            capability_matrix=list(capability_by_source.values()),
        )

    @staticmethod
    def _dedupe_across_sources(docs):
        """
        Drop the same paper arriving from more than one source.

        AGRICOLA and PubAg are both served by the NAL Primo index, and OpenAlex
        and Europe PMC overlap heavily by DOI, so without this the same study
        can occupy several context slots. The richest copy wins, so a record
        with a full abstract is preferred over a bare catalogue entry.
        """
        best = {}
        order = []
        for doc in docs:
            doi = (getattr(doc, "doi", "") or "").strip().lower()
            key = f"doi:{doi}" if doi else f"title:{(doc.title or '').strip().lower()}"
            if not key or key in ("doi:", "title:"):
                continue
            incumbent = best.get(key)
            if incumbent is None:
                best[key] = doc
                order.append(key)
            elif len(doc.abstract or "") > len(incumbent.abstract or ""):
                best[key] = doc
        return [best[k] for k in order]

    def _apply_source_group_policy(self, ranked_docs):
        primary_docs = [d for d in ranked_docs if not getattr(d, "enrichment_only", False)]
        enrichment_docs = [d for d in ranked_docs if getattr(d, "enrichment_only", False)]

        # Evidence quality decides the primary tier, not source identity. The
        # previous rule pinned AGRIS to the top and capped every other source at
        # two documents; because the AGRIS adapter reads a catalogue of dataset
        # descriptors, that reliably buried real abstracts under metadata stubs.
        quality_rank = {"high": 0, "medium": 1, "metadata_only": 2}
        primary_docs.sort(
            key=lambda d: (
                quality_rank.get(getattr(d, "evidence_quality", "metadata_only"), 2),
                -float(getattr(d, "retrieval_confidence", 0.0) or 0.0),
            )
        )

        if primary_docs:
            enrichment_cap = min(4, max(2, len(primary_docs) // 2))
            selected = primary_docs + enrichment_docs[:enrichment_cap]
        else:
            # If primary evidence is unavailable, return a small enrichment fallback set.
            selected = enrichment_docs[:4]

        # Ensure a useful evidence floor (5+) whenever ranked docs are available.
        selected_keys = {(d.source.lower(), d.title.lower(), d.url.lower()) for d in selected}
        if len(selected) < self.min_docs:
            for doc in ranked_docs:
                key = (doc.source.lower(), doc.title.lower(), doc.url.lower())
                if key in selected_keys:
                    continue
                selected.append(doc)
                selected_keys.add(key)
                if len(selected) >= self.min_docs:
                    break

        return selected[: max(self.min_docs, self.max_docs)]
