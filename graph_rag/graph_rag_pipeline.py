import json
import os
import re
import time
from dataclasses import asdict
from typing import Dict, Optional

import requests

from app.chatbot.client import generate as llm_generate, OllamaError

from .domain_policy import classify_query, refusal_message, smalltalk_reply
from .graph_builder import AgroKGBuilder
from .intent_parser import IntentParser, ParsedIntent
from .query_engine import GraphQueryEngine, QueryContext
from .retrieval import ExternalRetrievalOrchestrator


class GraphRAGPipeline:
    """End-to-end GraphRAG pipeline: parse -> query KG -> generate answer."""

    def __init__(
        self,
        ollama_base_url: Optional[str] = None,
        ollama_model: Optional[str] = None,
    ):
        self.ollama_base_url = ollama_base_url or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self.ollama_model = ollama_model or os.getenv(
            "GRAPH_RAG_MODEL",
            os.getenv("OPENROUTER_MODEL_NAME", os.getenv("GEMINI_MODEL_NAME", "nvidia/nemotron-3-ultra-550b-a55b:free")),
        )
        self.ollama_fallback_model = os.getenv(
            "GRAPH_RAG_FALLBACK_MODEL",
            "",
        )
        self.ollama_model_candidates = [
            x.strip()
            for x in os.getenv("GRAPH_RAG_MODEL_CANDIDATES", "").split(",")
            if x.strip()
        ]
        self.ollama_timeout = int(os.getenv("GRAPH_RAG_OLLAMA_TIMEOUT", "300"))
        self.ollama_max_wait_seconds = int(os.getenv("GRAPH_RAG_OLLAMA_MAX_WAIT", "0"))
        self.ollama_connect_timeout = float(os.getenv("GRAPH_RAG_OLLAMA_CONNECT_TIMEOUT", "10"))
        self.ollama_retries = max(0, int(os.getenv("GRAPH_RAG_OLLAMA_RETRIES", "1")))
        self.graph_rag_llm_max_tokens = int(os.getenv("GRAPH_RAG_LLM_MAX_TOKENS", "4000"))
        self.graph_rag_llm_retry_max_tokens = int(os.getenv("GRAPH_RAG_LLM_RETRY_MAX_TOKENS", "5000"))
        self.enable_external_sources = os.getenv("GRAPH_RAG_ENABLE_EXTERNAL_SOURCES", "true").lower() in {
            "1", "true", "yes", "on"
        }
        self.external_top_k = int(os.getenv("GRAPH_RAG_EXTERNAL_TOP_K", "4"))
        self.external_max_chars = int(os.getenv("GRAPH_RAG_EXTERNAL_MAX_CHARS", "700"))

        # Wall-clock ceiling for one /query, and the reason a first-ever question
        # used to fail and then succeed on retry.
        #
        # The SPA aborts at 180s (AUGNOSIS_TIMEOUT_MS). The server had no ceiling
        # at all: OPENROUTER_TIMEOUT is 240s for a *single* call, and a request
        # can make several in sequence — primary, fallback model, completion
        # retry. So on a cold model the first call ran past 180s, the browser
        # gave up with nothing, and the server carried on and finished. That
        # finish is what made attempt two fast: the model was now warm at
        # OpenRouter, so the identical question returned in time and looked like
        # the retry had "fixed" it.
        #
        # Budgeting below the client's abort inverts that: generation now yields
        # first, and yields the graph-grounded answer rather than nothing.
        self.request_budget_seconds = float(os.getenv("GRAPH_RAG_REQUEST_BUDGET", "150"))
        # Below this, another round trip cannot plausibly land, so spend what is
        # left returning what we already have.
        self.min_generation_seconds = float(os.getenv("GRAPH_RAG_MIN_GENERATION", "25"))

        self.kg_builder = AgroKGBuilder()
        self.kg_builder.build()

        self.intent_parser = IntentParser(self.kg_builder)
        self.query_engine = GraphQueryEngine(self.kg_builder)
        self.external_orchestrator = ExternalRetrievalOrchestrator()

    def run(self, user_query: str, use_llm: bool = True) -> Dict:
        # Clock starts here, not at first generation: retrieval spends from the
        # same budget the browser is counting down.
        self._deadline = time.monotonic() + self.request_budget_seconds
        parsed: ParsedIntent = self.intent_parser.parse(user_query)

        # Anything not recognisably agricultural stops here. It previously fell
        # through to a general-purpose prompt, which answered whatever it was
        # asked — including programming questions — while the response still
        # carried the knowledge-graph grounding banner.
        domain = classify_query(
            user_query,
            has_domain_entities=self._has_domain_entities(parsed),
        )
        if domain != "agriculture":
            return self._non_agriculture_result(user_query, parsed, domain, use_llm)

        qctx = self.query_engine.query(
            crop_name=parsed.crop,
            pest_name=parsed.pest,
            disease_name=parsed.disease,
            climate_conditions=parsed.climate_conditions,
            soil_type=parsed.soil_type,
            pesticide_name=parsed.pesticide,
        )

        kg_context_text = self.query_engine.format_context_for_llm(qctx)
        has_local_kb_context = bool(qctx.pests_found or qctx.diseases_found or qctx.treatments)

        external_context_text, external_meta, grounding = self._build_external_context(
            user_query,
            parsed,
            has_local_kb_context=has_local_kb_context,
        )
        kg_context_text = self._inject_external_signals(kg_context_text, external_meta)

        if grounding.get("allow_generation") and grounding.get("message"):
            external_context_text = (
                f"GROUNDING NOTE: {grounding['message']}\n\n"
                + (external_context_text or "")
            ).strip()

        if use_llm and grounding.get("allow_generation", True):
            answer = self._generate_with_ollama(user_query, parsed, kg_context_text, external_context_text)
        elif use_llm and not grounding.get("allow_generation", True):
            answer = grounding.get("message") or "No reliable external evidence retrieved from configured sources."
        else:
            answer = self._fallback_response(parsed, kg_context_text)

        return {
            "query": user_query,
            "parsed_intent": asdict(parsed),
            "context": asdict(qctx),
            "kg_context_text": kg_context_text,
            "response": answer,
            "engine": {
                "type": "graph_rag",
                "llm_model": self.ollama_model if use_llm else None,
                "llm_enabled": bool(use_llm),
                "ollama_base_url": self.ollama_base_url,
                "external_sources": external_meta,
                "grounding": grounding,
                "graph_stimulation": {
                    "external_evidence_docs": int(external_meta.get("total_results", 0)),
                    "external_evidence_injected": bool(external_meta.get("context_used", False)),
                },
            },
        }

    @staticmethod
    def _has_domain_entities(parsed: Optional[ParsedIntent]) -> bool:
        """
        Did the intent parser resolve anything against the knowledge graph?

        A stronger admit signal than any word list, because it means the query
        named something the graph actually knows about.
        """
        if parsed is None:
            return False
        if any([
            bool(parsed.crop),
            bool(parsed.pest),
            bool(parsed.disease),
            bool(parsed.soil_type),
            bool(parsed.pesticide),
            bool(parsed.climate_conditions),
        ]):
            return True

        intent_type = str(getattr(parsed, "intent_type", "") or "").lower()
        return any(
            token in intent_type
            for token in ["crop", "pest", "disease", "soil", "fert", "irrig", "agri"]
        )

    def _non_agriculture_result(
        self,
        user_query: str,
        parsed: ParsedIntent,
        domain: str,
        use_llm: bool,
    ) -> Dict:
        """
        Answer courtesy, decline everything else — and in both cases return an
        empty context.

        The empty context is the second half of the fix. `context` drives the
        "Grounded in knowledge graph / High confidence / Sources" panel in the
        UI, so returning a populated one here is what stamped a Python tutorial
        with ICAR and EPPO attribution.
        """
        answer = (
            smalltalk_reply(user_query, assistant="TerraMind")
            if domain == "smalltalk"
            else refusal_message(assistant="AugNosis")
        )

        return {
            "query": user_query,
            "parsed_intent": asdict(parsed),
            "context": asdict(QueryContext()),
            "kg_context_text": "",
            "response": answer,
            "engine": {
                "type": "graph_rag",
                "llm_model": None,  # No model was consulted, so claim none.
                "llm_enabled": bool(use_llm),
                "ollama_base_url": self.ollama_base_url,
                "external_sources": {
                    "enabled": bool(self.enable_external_sources),
                    "attempted": False,
                    "total_results": 0,
                    "context_used": False,
                    "source_counts": {},
                    "skipped_non_agriculture": True,
                },
                "grounding": {
                    "allow_generation": False,
                    "message": f"Query classified as {domain}; outside the agricultural domain.",
                    "conservative_mode": True,
                    "metadata_limited": False,
                },
                "graph_stimulation": {
                    "external_evidence_docs": 0,
                    "external_evidence_injected": False,
                },
                "domain": domain,
            },
        }

    def _inject_external_signals(self, kg_context_text: str, external_meta: Dict) -> str:
        if not external_meta.get("context_used"):
            return kg_context_text

        lines = [
            "EXTERNAL EVIDENCE SIGNALS:",
            f"- Primary docs: {external_meta.get('primary_results', 0)}",
            f"- Enrichment docs: {external_meta.get('enrichment_results', 0)}",
            f"- AGRIS docs: {external_meta.get('agris_results', 0)}",
            f"- FAOSTAT docs: {external_meta.get('faostat_results', 0)}",
            f"- CGIAR docs: {external_meta.get('cgiar_results', 0)}",
            f"- ClimateData docs: {external_meta.get('climate_results', 0)}",
            f"- SoilData docs: {external_meta.get('soil_results', 0)}",
            f"- AGRICOLA docs: {external_meta.get('agricola_results', 0)}",
            f"- PubAg docs: {external_meta.get('pubag_results', 0)}",
            f"- CABI docs: {external_meta.get('cabi_results', 0)}",
            f"- AgEcon docs: {external_meta.get('agecon_results', 0)}",
            f"- ASABE docs: {external_meta.get('asabe_results', 0)}",
        ]

        source_group_counts = external_meta.get("source_group_counts") or {}
        if source_group_counts:
            group_bits = [f"{k}={v}" for k, v in sorted(source_group_counts.items())]
            lines.append("- Source groups: " + ", ".join(group_bits))

        base = (kg_context_text or "").strip()
        if not base:
            return "\n".join(lines)
        return f"{base}\n\n" + "\n".join(lines)

    def _remaining_budget(self) -> float:
        """Seconds left before the browser stops listening. Never negative."""
        deadline = getattr(self, "_deadline", None)
        if deadline is None:
            return self.request_budget_seconds
        return max(0.0, deadline - time.monotonic())

    def _can_afford_another_call(self) -> bool:
        return self._remaining_budget() >= self.min_generation_seconds

    def _generate_with_ollama(
        self,
        user_query: str,
        parsed: ParsedIntent,
        kg_context_text: str,
        external_context_text: str,
    ) -> str:
        prompt = self._build_prompt(user_query, parsed, kg_context_text, external_context_text)

        # Retrieval may already have eaten the budget on a bad network day. The
        # graph answer is real content, so returning it beats spending the
        # user's remaining patience on a call that cannot land.
        if not self._can_afford_another_call():
            return self._fallback_response(parsed, kg_context_text)

        try:
            answer = llm_generate(
                prompt,
                self.ollama_model,
                self.graph_rag_llm_max_tokens,
                timeout=self._remaining_budget(),
            )
            if answer:
                return self._finalize_answer(
                    answer,
                    "",
                    user_query,
                    parsed,
                    kg_context_text,
                    external_context_text,
                )
            return self._fallback_response(parsed, kg_context_text)
        except OllamaError as exc:
            fallback_answer = self._try_fallback_model(
                exc,
                user_query,
                parsed,
                kg_context_text,
                external_context_text,
            )
            if fallback_answer:
                return self._finalize_answer(
                    fallback_answer,
                    "",
                    user_query,
                    parsed,
                    kg_context_text,
                    external_context_text,
                )
            reason = str(exc).strip()
            if len(reason) > 320:
                reason = reason[:320].rstrip() + "..."

            return (
                "Graph context is available, but OpenRouter generation failed for the current model and fallbacks. "
                f"Reason: {reason}\n\n"
                + self._fallback_response(parsed, kg_context_text)
            )
        except Exception as exc:
            return (
                "Graph context is available, but OpenRouter generation failed. "
                f"Reason: {exc}.\n\n"
                + self._fallback_response(parsed, kg_context_text)
            )

    def _finalize_answer(
        self,
        answer: str,
        url: str,
        user_query: str,
        parsed: ParsedIntent,
        kg_context_text: str,
        external_context_text: str,
    ) -> str:
        candidate = (answer or "").strip()
        if not candidate:
            return self._fallback_response(parsed, kg_context_text)

        # A tidier answer is not worth losing the answer. If the completion pass
        # cannot finish inside the budget, ship the slightly rough one.
        if self._is_incomplete_response(candidate) and self._can_afford_another_call():
            completed = self._retry_for_complete_response(
                url,
                user_query,
                parsed,
                kg_context_text,
                external_context_text,
            )
            if completed:
                candidate = completed

        return self._append_minimum_completion(candidate)

    def _post_with_retry(self, url: str, payload: Dict, max_wait_seconds: Optional[int] = None) -> requests.Response:
        last_exc: Optional[Exception] = None
        budget = int(max_wait_seconds or self.ollama_max_wait_seconds)
        unlimited_wait = budget <= 0
        start = time.monotonic()

        for attempt in range(self.ollama_retries + 1):
            if unlimited_wait:
                remaining_budget = None
            else:
                elapsed = time.monotonic() - start
                remaining_budget = budget - elapsed
                if remaining_budget <= 0:
                    break

            req_payload = payload
            if attempt > 0:
                req_payload = json.loads(json.dumps(payload))
                options = req_payload.setdefault("options", {})
                base_predict = int(options.get("num_predict", 512))
                options["num_predict"] = max(180, int(base_predict * (0.8 ** attempt)))

            try:
                if unlimited_wait:
                    request_timeout = (self.ollama_connect_timeout, None)
                else:
                    request_timeout = (
                        self.ollama_connect_timeout,
                        min(self.ollama_timeout, max(5.0, remaining_budget)),
                    )

                return requests.post(
                    url,
                    json=req_payload,
                    timeout=request_timeout,
                )
            except requests.exceptions.ReadTimeout as exc:
                last_exc = exc
                continue
            except requests.exceptions.RequestException as exc:
                last_exc = exc
                break

        if last_exc is not None:
            raise last_exc
        if unlimited_wait:
            raise requests.exceptions.ReadTimeout("Ollama request exceeded retry policy")
        raise requests.exceptions.ReadTimeout(
            f"Timed out after {budget}s waiting for Ollama response"
        )

    def _try_fallback_model(
        self,
        triggering_error: Exception,
        user_query: str,
        parsed: ParsedIntent,
        kg_context_text: str,
        external_context_text: str,
    ) -> Optional[str]:
        prompt = self._build_prompt(user_query, parsed, kg_context_text, external_context_text)
        current = (self.ollama_model or "").strip()
        fallbacks = []

        if self.ollama_fallback_model:
            fallbacks.append(self.ollama_fallback_model.strip())
        fallbacks.extend(self.ollama_model_candidates)

        # Safe default candidates when running OpenRouter free-tier models.
        if current == "nvidia/nemotron-3-ultra-550b-a55b:free":
            fallbacks.extend([
                "nvidia/nemotron-3-super-120b-a12b:free",
                "google/gemma-4-31b-it:free",
            ])

        # Preserve order and remove duplicates/primary model.
        unique_candidates = []
        seen = set()
        for model in fallbacks:
            if not model or model == current or model in seen:
                continue
            seen.add(model)
            unique_candidates.append(model)

        if not unique_candidates:
            return None

        for fallback_model in unique_candidates:
            # Walking the whole candidate list is how a slow primary turned into
            # a multi-minute request: each fallback got the full 240s of its own.
            # Stop as soon as the remaining budget cannot seat another call.
            if not self._can_afford_another_call():
                return None
            try:
                answer = llm_generate(
                    prompt,
                    fallback_model,
                    max(1000, self.graph_rag_llm_max_tokens - 120),
                    timeout=self._remaining_budget(),
                )
                if answer:
                    return answer
            except Exception:
                continue

        return None

    def _build_prompt(
        self,
        user_query: str,
        parsed: ParsedIntent,
        kg_context_text: str,
        external_context_text: str,
    ) -> str:
        role_lines = [
            "You are an agricultural advisory assistant for working farmers and agronomists.",
            "You answer the exact question asked, using only the facts the user actually gave you.",
            "You are concise. A focused, correct, short answer beats an exhaustive one.",
        ]

        parsed_block = json.dumps(asdict(parsed), ensure_ascii=True, indent=2)

        return (
            "\n".join(role_lines)
            + "\n\n"
            + f"USER QUERY:\n{user_query}\n\n"
            + "PARSED INTENT (low-confidence machine guess - it is often wrong.\n"
            + "Trust the USER QUERY text over this block. If a field here is not\n"
            + "actually present in the user's words, ignore it entirely):\n"
            + parsed_block
            + "\n\n"
            + "GRAPH CONTEXT (local agronomic knowledge graph):\n"
            + (kg_context_text or "(no graph context found)")
            + "\n\n"
            + "EXTERNAL RESEARCH CONTEXT (AGRIS/AGRICOLA etc.):\n"
            + (external_context_text or "(no external context used)")
            + "\n\n"
            # ── 1. Pests are not diseases ────────────────────────────────
            + "RULE 1 - PESTS AND DISEASES ARE DIFFERENT THINGS:\n"
            + "- PEST = animal: insect, mite, nematode, slug, rodent, bird.\n"
            + "  (aphids, borers, beetles, thrips, whitefly, armyworm, mites)\n"
            + "- DISEASE = pathogen: fungus, oomycete, bacterium, virus.\n"
            + "  (rusts, blights, blotches, mildews, wilts, mosaic viruses)\n"
            + "- Never file a fungal disease under 'pests'.\n"
            + "- If the user asked about PESTS, lead with pests and keep the\n"
            + "  disease section short and clearly labelled as additional context.\n"
            + "- If the user asked about DISEASES, do the reverse.\n"
            + "- If they asked about both or were vague, cover both evenly.\n"
            + "\n"
            # ── 2. Do not invent facts the user never supplied ────────────
            + "RULE 2 - NEVER ASSUME UNSTATED CONDITIONS:\n"
            + "- Do NOT invent a growth stage. If the user did not state one,\n"
            + "  express stage-dependent risk conditionally instead:\n"
            + "  'High ONLY if the crop is at flowering; low before that'.\n"
            + "- Do NOT invent a temperature. 'Humid' does not mean 'warm'.\n"
            + "  If temperature is unknown, say which temperature band each\n"
            + "  threat needs, and note the risk flips outside that band.\n"
            + "  (Example: stripe rust needs cool 10-15 C and fades above ~22 C,\n"
            + "  so it is NOT automatically high risk in humid weather.)\n"
            + "- Do NOT invent a location, season, variety, or sowing date.\n"
            + "- State the 2-4 assumptions you had to make, in one short line.\n"
            + "\n"
            # ── 3. Chemicals are jurisdiction-bound ──────────────────────
            + "RULE 3 - CHEMICAL CONTROL:\n"
            + "- Use ACTIVE INGREDIENT names only (e.g. 'prothioconazole').\n"
            + "- NEVER name commercial products or brands. No trade names,\n"
            + "  no registered-trademark symbols, no product-specific dose rates.\n"
            + "- Give FRAC/IRAC group codes so the user can plan rotation.\n"
            + "- Registration differs by country. Do not present any product as\n"
            + "  available to this user. One short caveat line is enough - do not\n"
            + "  repeat the disclaimer in every row.\n"
            + "\n"
            # ── 4. Evidence must earn its place ──────────────────────────
            + "RULE 4 - EVIDENCE:\n"
            + "- Cite a source ONLY if you have an actual finding from it.\n"
            + "- If the retrieved records are metadata-only (titles/IDs with no\n"
            + "  abstract or result), they support nothing. OMIT the evidence\n"
            + "  section entirely. Do not list record IDs, and do not write a\n"
            + "  paragraph explaining that the evidence was insufficient.\n"
            + "  At most one short line: 'Based on established epidemiology\n"
            + "  rather than the retrieved records.'\n"
            + "- Never pad the answer with sources that add no information.\n"
            + "\n"
            # ── 5. Shape and length ─────────────────────────────────────
            + "OUTPUT FORMAT (GitHub-flavoured markdown, rendered in a NARROW\n"
            + "chat column - keep tables to 3 columns maximum):\n"
            + "\n"
            + "## Short answer\n"
            + "2-3 sentences. Directly answer what was asked, ranked. No preamble.\n"
            + "\n"
            + "## <Pests|Diseases - whichever was asked about>\n"
            + "A table: | Name (common + scientific) | Risk | Conditional on |\n"
            + "Max 5 rows. 'Conditional on' names the stage/temperature that\n"
            + "would raise or drop that risk. Rank highest risk first.\n"
            + "\n"
            + "## <The other category>\n"
            + "Same table shape, max 4 rows, clearly marked as secondary.\n"
            + "\n"
            + "## Why humid conditions drive this\n"
            + "3-5 bullets max. Mechanism only: moisture -> biology -> crop damage.\n"
            + "\n"
            + "## Scout now\n"
            + "3-5 bullets: what to physically look for, where on the plant, and\n"
            + "the action threshold. Concrete and checkable.\n"
            + "\n"
            + "## Control options\n"
            + "Short. Active ingredients + FRAC/IRAC codes + resistance rotation.\n"
            + "Cultural/preventive measures first where they genuinely help.\n"
            + "\n"
            + "## To narrow this down\n"
            + "Ask for exactly the 3-4 missing facts that would most change the\n"
            + "ranking above - typically location, growth stage, temperature, and\n"
            + "how many consecutive wet days. Phrase as a short bulleted ask.\n"
            + "\n"
            + "HARD LIMITS:\n"
            + "- Target 450 words. Never exceed 700.\n"
            + "- Omit any section that would only restate another one.\n"
            + "- No emoji. No hype. No 'Bottom Line' or motivational closers.\n"
            + "- Prefer plain language; keep scientific names but skip jargon\n"
            + "  the farmer cannot act on.\n"
        )

    def _looks_truncated(self, text: str) -> bool:
        stripped = (text or "").strip()
        if not stripped:
            return True

        if stripped.endswith(":"):
            return True

        if re.search(r"\*\*$", stripped):
            return True

        if re.search(r"\b(and|or|with|for|in|on|to|during|under|requires|include|includes)\s*$", stripped, flags=re.IGNORECASE):
            return True

        if not re.search(r"[.!?]$", stripped):
            return True

        return False

    def _build_external_context(self, user_query: str, parsed: ParsedIntent, has_local_kb_context: bool):
        default_meta = {
            "enabled": bool(self.enable_external_sources),
            "attempted": False,
            "agris_called": False,
            "faostat_called": False,
            "cgiar_called": False,
            "climate_called": False,
            "soil_called": False,
            "agricola_called": False,
            "pubag_called": False,
            "cabi_called": False,
            "agecon_called": False,
            "asabe_called": False,
            "agris_results": 0,
            "faostat_results": 0,
            "cgiar_results": 0,
            "climate_results": 0,
            "soil_results": 0,
            "agricola_results": 0,
            "pubag_results": 0,
            "cabi_results": 0,
            "agecon_results": 0,
            "asabe_results": 0,
            "total_results": 0,
            "primary_results": 0,
            "enrichment_results": 0,
            "context_used": False,
            "source_counts": {},
            "source_group_counts": {},
        }
        default_grounding = {
            "allow_generation": True,
            "message": "",
            "conservative_mode": False,
            "metadata_limited": False,
        }

        if not self.enable_external_sources:
            return "", default_meta, default_grounding

        try:
            output = self.external_orchestrator.run(
                user_query=user_query,
                parsed_intent=parsed,
                has_local_kb_context=has_local_kb_context,
            )

            source_counts = output.retrieval.source_counts
            selected_docs = output.retrieval.documents
            source_group_counts = {}
            selected_source_counts = {}
            primary_results = 0
            enrichment_results = 0
            for doc in selected_docs:
                group = getattr(doc, "source_group", "research") or "research"
                source_group_counts[group] = source_group_counts.get(group, 0) + 1
                source_name = getattr(doc, "source", "") or "unknown"
                selected_source_counts[source_name] = selected_source_counts.get(source_name, 0) + 1
                if getattr(doc, "enrichment_only", False):
                    enrichment_results += 1
                else:
                    primary_results += 1

            def _count(source_name: str) -> int:
                return int(source_counts.get(source_name, 0) or 0)

            meta = {
                "enabled": True,
                "attempted": True,
                "agris_called": _count("AGRIS") > 0,
                "faostat_called": _count("FAOSTAT") > 0,
                "cgiar_called": _count("CGIAR") > 0,
                "climate_called": _count("ClimateData") > 0,
                "soil_called": _count("SoilData") > 0,
                "agricola_called": _count("AGRICOLA") > 0,
                "pubag_called": _count("PubAg") > 0,
                "cabi_called": _count("CABI") > 0,
                "agecon_called": _count("AgEcon") > 0,
                "asabe_called": _count("ASABE") > 0,
                "agris_results": _count("AGRIS"),
                "faostat_results": _count("FAOSTAT"),
                "cgiar_results": _count("CGIAR"),
                "climate_results": _count("ClimateData"),
                "soil_results": _count("SoilData"),
                "agricola_results": _count("AGRICOLA"),
                "pubag_results": _count("PubAg"),
                "cabi_results": _count("CABI"),
                "agecon_results": _count("AgEcon"),
                "asabe_results": _count("ASABE"),
                "total_results": output.retrieval.total_docs,
                "primary_results": primary_results,
                "enrichment_results": enrichment_results,
                "context_used": bool(output.context_text),
                "source_counts": source_counts,
                "selected_source_counts": selected_source_counts,
                "source_group_counts": source_group_counts,
                "source_call_logs": [x.to_dict() for x in output.retrieval.source_logs],
            }

            grounding = {
                "allow_generation": output.grounding.allow_generation,
                "message": output.grounding.message,
                "conservative_mode": output.grounding.conservative_mode,
                "metadata_limited": output.grounding.metadata_limited,
            }

            return output.context_text, meta, grounding
        except Exception:
            return "", default_meta, {
                "allow_generation": has_local_kb_context,
                "message": "No reliable external evidence retrieved from configured sources.",
                "conservative_mode": True,
                "metadata_limited": True,
            }

    def _should_use_external_context(self, parsed: ParsedIntent, user_query: str) -> bool:
        if not self.enable_external_sources:
            return False

        if not parsed.crop:
            return False

        if parsed.disease:
            return True

        disease_terms = {
            "disease", "blight", "blast", "mildew", "rust", "wilt",
            "spot", "rot", "fungal", "bacterial", "viral", "leaf",
        }
        query_tokens = set(re.findall(r"[a-zA-Z]+", (user_query or "").lower()))
        return bool(disease_terms & query_tokens)

    def _derive_disease_hint(self, user_query: str) -> str:
        text = (user_query or "").lower()
        for key in [
            "bacterial blight",
            "sheath blight",
            "blast",
            "powdery mildew",
            "leaf spot",
            "rust",
            "wilt",
            "rot",
        ]:
            if key in text:
                return key
        return "disease management"

    def _run_async(self, coro):
        try:
            return asyncio.run(coro)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

    def _format_external_context(
        self,
        agris_results,
        agricola_results,
        pubag_results,
        cabi_results,
        agecon_results,
        asabe_results,
    ) -> str:
        if (
            not agris_results
            and not agricola_results
            and not pubag_results
            and not cabi_results
            and not agecon_results
            and not asabe_results
        ):
            return ""

        lines = []
        sources = [
            ("AGRIS", agris_results),
            ("AGRICOLA", agricola_results),
            ("PubAg", pubag_results),
            ("CABI", cabi_results),
            ("AgEcon", agecon_results),
            ("ASABE", asabe_results),
        ]

        for source_name, source_results in sources:
            if not source_results:
                continue
            lines.append(f"{source_name}:")
            for text in source_results[: self.external_top_k]:
                snippet = str(text).strip().replace("\n", " ")[: self.external_max_chars]
                if snippet:
                    lines.append(f"- {snippet}")

        return "\n".join(lines).strip()

    def _retry_for_complete_response(
        self,
        url: str,
        user_query: str,
        parsed: ParsedIntent,
        kg_context_text: str,
        external_context_text: str,
    ) -> Optional[str]:
        retry_prompt = (
            self._build_prompt(user_query, parsed, kg_context_text, external_context_text)
            + "\nIMPORTANT: Produce the complete answer, ending with the"
            + " 'To narrow this down' section. No unfinished bullets or sentences."
        )
        try:
            candidate = llm_generate(
                retry_prompt,
                self.ollama_model,
                self.graph_rag_llm_retry_max_tokens,
                timeout=self._remaining_budget(),
            )
            if candidate and not self._is_incomplete_response(candidate):
                return candidate
        except Exception:
            return None
        return None

    def _is_incomplete_response(self, text: str) -> bool:
        stripped = (text or "").strip()
        if not stripped:
            return True

        # Anchors from the current output format. "To narrow this down" is the
        # final section, so its absence is a genuine early-stop signal. Keep
        # this list minimal - every false positive costs a full retry.
        required_sections = [
            "Short answer",
            "To narrow this down",
        ]
        missing_sections = [s for s in required_sections if s.lower() not in stripped.lower()]
        if missing_sections:
            return True

        if stripped.endswith(":"):
            return True

        last_line = stripped.splitlines()[-1].strip()
        if re.match(r"^[-*]\s*(\*\*[^*]+\*\*\s*:)?\s*$", last_line):
            return True

        if re.search(r"\b(apply|use|spray|treat)\s*$", last_line, flags=re.IGNORECASE):
            return True

        return False

    def _append_minimum_completion(self, text: str) -> str:
        cleaned = text.rstrip()

        cleaned = re.sub(
            r"\n+#{0,3}\s*5\)?\s*Optional comparisons\s*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"\n+#{0,3}\s*6\)?\s*Confidence note\s*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        if cleaned.endswith(":"):
            cleaned += " Follow local label guidance with crop-specific products and PHI restrictions."

        if re.search(r"\b(and|or|of|to|for|with|in|on|at|from|by|during|under)\s*$", cleaned, flags=re.IGNORECASE):
            cleaned += " all product labels and local advisories."

        last_line = cleaned.splitlines()[-1].strip() if cleaned else ""
        if not re.search(r"[.!?]$", cleaned) and not re.match(r"^(#{1,6}|\d+\))", last_line):
            cleaned += "."

        cleaned = re.sub(
            r"\bAvoid\.\s*$",
            "Avoid incompatible tank mixes unless compatibility is confirmed.",
            cleaned,
            flags=re.IGNORECASE,
        )

        # Deliberately no boilerplate sections are appended here. Bolting on
        # canned "Actionable Recommendations" text produced exactly the generic,
        # off-format filler the prompt forbids, and it fired on every answer
        # because the section names it looked for were from an older format.
        # Repairing a dangling sentence is fine; inventing agronomic advice is not.
        return cleaned

    def _fallback_response(self, parsed: ParsedIntent, kg_context_text: str) -> str:
        lines = []
        lines.append("Situation summary:")
        lines.append(f"- Detected intent: {parsed.intent_type}")

        if parsed.crop:
            crop_name = self.kg_builder.G.nodes[parsed.crop].get("name_en", parsed.crop)
            lines.append(f"- Crop: {crop_name}")

        if parsed.climate_conditions:
            lines.append(f"- Climate flags: {', '.join(parsed.climate_conditions)}")

        lines.append("")
        lines.append("Actionable graph findings:")
        if kg_context_text.strip():
            lines.append(kg_context_text)
        else:
            lines.append("- No strong graph matches found for this query.")
            lines.append("- Suggestion: specify crop + visible symptom + weather condition.")

        lines.append("")
        lines.append("Safety notes:")
        lines.append("- Follow product label dose, PHI, and local agriculture advisories.")
        lines.append("- Avoid tank mixes unless compatibility is explicitly confirmed.")

        return "\n".join(lines)
