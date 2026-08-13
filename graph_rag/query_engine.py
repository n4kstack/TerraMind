from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class QueryContext:
    crop: Optional[str] = None
    pests_found: List[Dict] = field(default_factory=list)
    diseases_found: List[Dict] = field(default_factory=list)
    treatments: List[Dict] = field(default_factory=list)
    soil_conflicts: List[Dict] = field(default_factory=list)
    tank_mix_warnings: List[Dict] = field(default_factory=list)
    climate_risk_assessment: List[Dict] = field(default_factory=list)
    high_risk_pests_now: List[str] = field(default_factory=list)
    high_risk_diseases_now: List[str] = field(default_factory=list)
    urgent_actions: List[str] = field(default_factory=list)
    data_sources: List[str] = field(default_factory=list)
    # Starts low and is raised only by what the traversal actually finds. The
    # default used to be "high", so an empty context — including one built for a
    # query the graph knew nothing about — still reported high confidence.
    confidence: str = "low"
    warnings: List[str] = field(default_factory=list)


class GraphQueryEngine:
    """Traverses AgroKG to assemble structured contexts for generation."""

    def __init__(self, kg_builder):
        self.G = kg_builder.G
        self.resolve = kg_builder.resolve_node

    def query(
        self,
        crop_name: str = None,
        pest_name: str = None,
        disease_name: str = None,
        climate_conditions: List[str] = None,
        soil_type: str = None,
        pesticide_name: str = None,
    ) -> QueryContext:
        ctx = QueryContext()

        crop_id = self.resolve(crop_name) if crop_name else None
        pest_id = self.resolve(pest_name) if pest_name else None
        disease_id = self.resolve(disease_name) if disease_name else None
        soil_id = self.resolve(soil_type) if soil_type else None

        explicit_pesticides = []
        if pesticide_name:
            candidates = [x.strip() for x in str(pesticide_name).split(",") if x.strip()]
            for cand in candidates:
                pid = self.resolve(cand)
                if pid and pid in self.G.nodes and self.G.nodes[pid].get("node_type") == "pesticide":
                    explicit_pesticides.append(pid)

        if crop_id:
            ctx.crop = self.G.nodes[crop_id].get("name_en")
            ctx.pests_found = self._get_crop_pests(crop_id)
            ctx.diseases_found = self._get_crop_diseases(crop_id)

        if pest_id:
            ctx.treatments.extend(self._get_pest_treatments(pest_id))
            ctx.climate_risk_assessment.extend(self._get_pest_climate_risk(pest_id))

        if disease_id:
            ctx.treatments.extend(self._get_disease_treatments(disease_id))

        for pid in explicit_pesticides:
            p_node = self.G.nodes[pid]
            ctx.treatments.append(
                {
                    "pesticide_id": pid,
                    "name_en": p_node.get("name_en"),
                    "name_hi": p_node.get("name_hi"),
                    "type": p_node.get("type"),
                    "chemical_class": p_node.get("chemical_class"),
                    "dose_range": p_node.get("dose_range"),
                    "dose_unit": p_node.get("dose_unit"),
                    "phi_days": p_node.get("phi_days"),
                    "max_applications": p_node.get("max_applications"),
                    "who_class": p_node.get("who_class"),
                    "efficacy": "contextual",
                    "timing": "as per label and advisor",
                    "notes": "Directly requested in query",
                    "re_entry_hours": p_node.get("re_entry_hours"),
                }
            )

        if ctx.treatments:
            seen = set()
            deduped = []
            for t in ctx.treatments:
                pid = t.get("pesticide_id")
                if not pid or pid in seen:
                    continue
                seen.add(pid)
                deduped.append(t)
            ctx.treatments = deduped

        if climate_conditions:
            ctx.high_risk_pests_now = self._get_high_risk_pests_for_climate(climate_conditions, crop_id=crop_id)
            ctx.high_risk_diseases_now = self._get_high_risk_diseases_for_climate(climate_conditions, crop_id=crop_id)
            ctx.urgent_actions = self._generate_urgent_actions(
                ctx.high_risk_pests_now,
                ctx.high_risk_diseases_now,
                climate_conditions,
            )

        if soil_id and ctx.treatments:
            ctx.soil_conflicts = self._check_soil_conflicts(
                soil_id,
                [t["pesticide_id"] for t in ctx.treatments if "pesticide_id" in t],
            )

        if len(ctx.treatments) > 1:
            pesticide_ids = [t["pesticide_id"] for t in ctx.treatments if "pesticide_id" in t]
            ctx.tank_mix_warnings = self._check_tank_mix_safety(pesticide_ids)

        # Cite only what the traversal actually consulted.
        #
        # This block used to assign all four sources unconditionally, so every
        # answer — including ones where the graph matched nothing at all —
        # arrived stamped "Grounded in knowledge graph" with ICAR, PPDB and EPPO
        # attribution. Sources are the entire trust proposition of this feature
        # (MASTER §5.3); citing ones that were never opened is worse than citing
        # none, because it is unfalsifiable from the UI.
        has_protection_data = bool(ctx.pests_found or ctx.diseases_found)
        has_graph_content = bool(
            ctx.crop or has_protection_data or ctx.treatments or ctx.climate_risk_assessment
        )

        sources: List[str] = []
        if has_graph_content:
            sources.append("TerraMind AgroKG v1.0")
        if has_protection_data or ctx.treatments:
            sources.append("ICAR recommendations")
        if ctx.treatments:
            sources.append("PPDB pesticide database")
        if has_protection_data:
            sources.append("EPPO crop protection data")
        ctx.data_sources = sources

        if ctx.treatments and has_protection_data:
            ctx.confidence = "high"
        elif has_graph_content:
            ctx.confidence = "medium"
        else:
            ctx.confidence = "low"

        return ctx

    def _get_crop_pests(self, crop_id: str) -> List[Dict]:
        results = []
        for _, pest_id, edge_data in self.G.out_edges(crop_id, data=True):
            if edge_data.get("relation") != "SUSCEPTIBLE_TO":
                continue

            pest_node = self.G.nodes[pest_id]
            control_options = []
            for _, pesticide_id, ctrl_data in self.G.out_edges(pest_id, data=True):
                if ctrl_data.get("relation") == "CONTROLLED_BY":
                    p_node = self.G.nodes[pesticide_id]
                    dr = p_node.get("dose_range", ("?", "?"))
                    control_options.append(
                        {
                            "pesticide_id": pesticide_id,
                            "name": p_node.get("name_en"),
                            "efficacy": ctrl_data.get("efficacy"),
                            "dose": f"{dr[0]}-{dr[1]} {p_node.get('dose_unit', '')}",
                            "phi_days": p_node.get("phi_days"),
                            "who_class": p_node.get("who_class"),
                            "timing": ctrl_data.get("timing"),
                            "notes": ctrl_data.get("notes", ""),
                        }
                    )

            efficacy_order = {"high": 0, "medium": 1, "low": 2}
            control_options.sort(key=lambda x: efficacy_order.get(x.get("efficacy", "low"), 3))

            peak_climates = []
            for _, climate_id, clim_data in self.G.out_edges(pest_id, data=True):
                if clim_data.get("relation") == "PEAKS_DURING":
                    peak_climates.append(
                        {
                            "condition": climate_id,
                            "effect": clim_data.get("effect"),
                            "risk_multiplier": clim_data.get("risk_multiplier", 1.0),
                        }
                    )

            results.append(
                {
                    "pest_id": pest_id,
                    "name_en": pest_node.get("name_en"),
                    "name_hi": pest_node.get("name_hi"),
                    "scientific_name": pest_node.get("scientific_name"),
                    "type": pest_node.get("type"),
                    "damage_type": pest_node.get("damage_type"),
                    "affected_parts": pest_node.get("affected_plant_parts", []),
                    "severity_on_crop": edge_data.get("severity"),
                    "growth_stage": edge_data.get("growth_stage", []),
                    "season": edge_data.get("season"),
                    "economic_threshold": pest_node.get("economic_threshold"),
                    "notes": edge_data.get("notes", ""),
                    "control_options": control_options,
                    "peak_conditions": peak_climates,
                }
            )

        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        results.sort(key=lambda x: severity_order.get(x.get("severity_on_crop", "low"), 4))
        return results

    def _get_crop_diseases(self, crop_id: str) -> List[Dict]:
        results = []
        for _, disease_id, edge_data in self.G.out_edges(crop_id, data=True):
            if edge_data.get("relation") != "VULNERABLE_TO":
                continue

            d_node = self.G.nodes[disease_id]
            treatments = self._get_disease_treatments(disease_id)

            climate_risks = []
            for _, clim_id, clim_data in self.G.out_edges(disease_id, data=True):
                if clim_data.get("relation") == "FAVORED_BY":
                    climate_risks.append(
                        {
                            "condition": clim_id,
                            "effect": clim_data.get("effect"),
                            "risk_multiplier": clim_data.get("risk_multiplier", 1.0),
                        }
                    )

            results.append(
                {
                    "disease_id": disease_id,
                    "name_en": d_node.get("name_en"),
                    "name_hi": d_node.get("name_hi"),
                    "type": d_node.get("type"),
                    "pathogen": d_node.get("pathogen"),
                    "symptoms": d_node.get("symptoms", []),
                    "affected_parts": d_node.get("affected_parts", []),
                    "severity": edge_data.get("severity"),
                    "economic_impact": d_node.get("economic_impact"),
                    "season": edge_data.get("season"),
                    "notes": edge_data.get("notes", ""),
                    "treatments": treatments,
                    "climate_risks": climate_risks,
                }
            )

        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        results.sort(key=lambda x: severity_order.get(x.get("severity", "low"), 4))
        return results

    def _get_pest_treatments(self, pest_id: str) -> List[Dict]:
        results = []
        for _, pesticide_id, edge_data in self.G.out_edges(pest_id, data=True):
            if edge_data.get("relation") == "CONTROLLED_BY":
                p_node = self.G.nodes[pesticide_id]
                results.append(
                    {
                        "pesticide_id": pesticide_id,
                        "name_en": p_node.get("name_en"),
                        "name_hi": p_node.get("name_hi"),
                        "type": p_node.get("type"),
                        "chemical_class": p_node.get("chemical_class"),
                        "dose_range": p_node.get("dose_range"),
                        "dose_unit": p_node.get("dose_unit"),
                        "phi_days": p_node.get("phi_days"),
                        "max_applications": p_node.get("max_applications"),
                        "who_class": p_node.get("who_class"),
                        "efficacy": edge_data.get("efficacy"),
                        "timing": edge_data.get("timing"),
                        "notes": edge_data.get("notes", ""),
                        "re_entry_hours": p_node.get("re_entry_hours"),
                    }
                )

        efficacy_order = {"high": 0, "medium": 1, "low": 2}
        results.sort(key=lambda x: efficacy_order.get(x.get("efficacy", "low"), 3))
        return results

    def _get_disease_treatments(self, disease_id: str) -> List[Dict]:
        results = []
        for _, pesticide_id, edge_data in self.G.out_edges(disease_id, data=True):
            if edge_data.get("relation") == "TREATED_BY":
                p_node = self.G.nodes[pesticide_id]
                results.append(
                    {
                        "pesticide_id": pesticide_id,
                        "name_en": p_node.get("name_en"),
                        "name_hi": p_node.get("name_hi"),
                        "type": p_node.get("type"),
                        "chemical_class": p_node.get("chemical_class"),
                        "dose_range": p_node.get("dose_range"),
                        "dose_unit": p_node.get("dose_unit"),
                        "phi_days": p_node.get("phi_days"),
                        "max_applications": p_node.get("max_applications"),
                        "who_class": p_node.get("who_class"),
                        "efficacy": edge_data.get("efficacy"),
                        "timing": edge_data.get("timing"),
                        "spray_interval_days": edge_data.get("spray_interval_days"),
                        "notes": edge_data.get("notes", ""),
                        "re_entry_hours": p_node.get("re_entry_hours"),
                    }
                )

        efficacy_order = {"high": 0, "medium": 1, "low": 2}
        results.sort(key=lambda x: efficacy_order.get(x.get("efficacy", "low"), 3))
        return results

    def _get_pest_climate_risk(self, pest_id: str) -> List[Dict]:
        results = []
        for _, climate_id, edge_data in self.G.out_edges(pest_id, data=True):
            if edge_data.get("relation") == "PEAKS_DURING":
                c_node = self.G.nodes[climate_id]
                results.append(
                    {
                        "climate_condition": climate_id,
                        "climate_name": c_node.get("name_en"),
                        "effect": edge_data.get("effect"),
                        "mechanism": edge_data.get("mechanism"),
                        "risk_multiplier": edge_data.get("risk_multiplier", 1.0),
                    }
                )
        return results

    def _get_high_risk_pests_for_climate(self, climate_conditions: List[str], crop_id: str = None) -> List[str]:
        climate_ids = set()
        for c in climate_conditions:
            resolved = self.resolve(c)
            if resolved:
                climate_ids.add(resolved)

        if not climate_ids:
            return []

        crop_pests = set()
        if crop_id:
            for _, pest_id, edge_data in self.G.out_edges(crop_id, data=True):
                if edge_data.get("relation") == "SUSCEPTIBLE_TO":
                    crop_pests.add(pest_id)

        pest_risks = {}
        for pest_id in self.G.nodes:
            node_data = self.G.nodes[pest_id]
            if node_data.get("node_type") != "pest":
                continue
            if crop_id and crop_pests and pest_id not in crop_pests:
                continue
            for _, clim_id, edge_data in self.G.out_edges(pest_id, data=True):
                if edge_data.get("relation") == "PEAKS_DURING" and clim_id in climate_ids:
                    multiplier = edge_data.get("risk_multiplier", 1.0)
                    if pest_id not in pest_risks or multiplier > pest_risks[pest_id]:
                        pest_risks[pest_id] = multiplier

        sorted_pests = sorted(pest_risks.items(), key=lambda x: x[1], reverse=True)
        return [p for p, _ in sorted_pests]

    def _get_high_risk_diseases_for_climate(self, climate_conditions: List[str], crop_id: str = None) -> List[str]:
        climate_ids = set()
        for c in climate_conditions:
            resolved = self.resolve(c)
            if resolved:
                climate_ids.add(resolved)

        if not climate_ids:
            return []

        crop_diseases = set()
        if crop_id:
            for _, disease_id, edge_data in self.G.out_edges(crop_id, data=True):
                if edge_data.get("relation") == "VULNERABLE_TO":
                    crop_diseases.add(disease_id)

        disease_risks = {}
        for disease_id in self.G.nodes:
            node_data = self.G.nodes[disease_id]
            if node_data.get("node_type") != "disease":
                continue
            if crop_id and crop_diseases and disease_id not in crop_diseases:
                continue
            for _, clim_id, edge_data in self.G.out_edges(disease_id, data=True):
                if edge_data.get("relation") == "FAVORED_BY" and clim_id in climate_ids:
                    multiplier = edge_data.get("risk_multiplier", 1.0)
                    if disease_id not in disease_risks or multiplier > disease_risks[disease_id]:
                        disease_risks[disease_id] = multiplier

        sorted_d = sorted(disease_risks.items(), key=lambda x: x[1], reverse=True)
        return [d for d, _ in sorted_d]

    def _check_soil_conflicts(self, soil_id: str, pesticide_ids: List[str]) -> List[Dict]:
        conflicts = []
        for pest_id in pesticide_ids:
            if pest_id not in self.G.nodes:
                continue
            for _, s_id, edge_data in self.G.out_edges(pest_id, data=True):
                if edge_data.get("relation") == "CONFLICTS_WITH" and s_id == soil_id:
                    p_node = self.G.nodes[pest_id]
                    conflicts.append(
                        {
                            "pesticide": p_node.get("name_en"),
                            "soil": soil_id,
                            "conflict_type": edge_data.get("conflict_type"),
                            "severity": edge_data.get("severity"),
                            "reason": edge_data.get("reason"),
                            "recommendation": edge_data.get("recommendation"),
                        }
                    )
        return conflicts

    def _check_tank_mix_safety(self, pesticide_ids: List[str]) -> List[Dict]:
        warnings = []
        seen_pairs = set()

        for i, p1 in enumerate(pesticide_ids):
            for p2 in pesticide_ids[i + 1 :]:
                pair = tuple(sorted([p1, p2]))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                if not (p1 in self.G.nodes and p2 in self.G.nodes):
                    continue
                for _, target, edge_data in self.G.out_edges(p1, data=True):
                    if edge_data.get("relation") == "INCOMPATIBLE_WITH" and target == p2:
                        n1 = self.G.nodes[p1]
                        n2 = self.G.nodes[p2]
                        warnings.append(
                            {
                                "pesticide_a": n1.get("name_en"),
                                "pesticide_b": n2.get("name_en"),
                                "reason": edge_data.get("reason"),
                                "severity": edge_data.get("severity"),
                            }
                        )
        return warnings

    def _generate_urgent_actions(self, high_risk_pests: List[str], high_risk_diseases: List[str], climate_conditions: List[str]) -> List[str]:
        actions = []
        for pest_id in high_risk_pests[:3]:
            if pest_id in self.G.nodes:
                p_node = self.G.nodes[pest_id]
                actions.append(
                    f"Monitor for {p_node.get('name_en')} ({p_node.get('scientific_name')}) - population peaks in current conditions. "
                    f"Check economic threshold: {p_node.get('economic_threshold', 'consult advisor')}"
                )

        for disease_id in high_risk_diseases[:2]:
            if disease_id in self.G.nodes:
                d_node = self.G.nodes[disease_id]
                actions.append(
                    f"High risk of {d_node.get('name_en')} in current {', '.join(climate_conditions)} conditions. "
                    "Apply preventive fungicide if not already done."
                )

        return actions

    def format_context_for_llm(self, ctx: QueryContext) -> str:
        lines = []

        if ctx.crop:
            lines.append(f"CROP: {ctx.crop}")
            lines.append("")

        if ctx.high_risk_pests_now:
            lines.append("HIGH RISK PESTS (current conditions):")
            for pest_id in ctx.high_risk_pests_now[:4]:
                if pest_id in self.G.nodes:
                    n = self.G.nodes[pest_id]
                    lines.append(f"  - {n.get('name_en')} ({n.get('scientific_name')}) - {n.get('damage_type')} pest")
            lines.append("")

        if ctx.high_risk_diseases_now:
            lines.append("HIGH RISK DISEASES (current conditions):")
            for disease_id in ctx.high_risk_diseases_now[:3]:
                if disease_id in self.G.nodes:
                    n = self.G.nodes[disease_id]
                    lines.append(f"  - {n.get('name_en')} ({n.get('type')} disease)")
            lines.append("")

        if ctx.urgent_actions:
            lines.append("RECOMMENDED IMMEDIATE ACTIONS:")
            for i, action in enumerate(ctx.urgent_actions, 1):
                lines.append(f"  {i}. {action}")
            lines.append("")

        if ctx.treatments:
            lines.append("TREATMENT OPTIONS (ranked by efficacy):")
            for t in ctx.treatments[:5]:
                dr = t.get("dose_range")
                dose = f"{dr[0]}-{dr[1]} {t.get('dose_unit', '')}" if isinstance(dr, tuple) else "see label"
                lines.append(
                    f"  - {t.get('name_en')} ({t.get('efficacy', '?')} efficacy) | Dose: {dose} | "
                    f"PHI: {t.get('phi_days', '?')} days | WHO Class: {t.get('who_class', '?')}"
                )
                if t.get("notes"):
                    lines.append(f"    Note: {t['notes']}")
            lines.append("")

        if ctx.soil_conflicts:
            lines.append("SOIL COMPATIBILITY WARNINGS:")
            for c in ctx.soil_conflicts:
                lines.append(
                    f"  - {c['pesticide']} CONFLICTS with {c['soil']} ({c['conflict_type']}, {c['severity']} severity)"
                )
                lines.append(f"    Reason: {c['reason']}")
                lines.append(f"    Use instead: {c['recommendation']}")
            lines.append("")

        if ctx.tank_mix_warnings:
            lines.append("TANK MIX INCOMPATIBILITIES:")
            for w in ctx.tank_mix_warnings:
                lines.append(
                    f"  - DO NOT MIX: {w['pesticide_a']} + {w['pesticide_b']} ({w['severity']} - {w['reason']})"
                )
            lines.append("")

        if ctx.data_sources:
            lines.append(f"Sources: {', '.join(ctx.data_sources)}")

        return "\n".join(lines)


# ── Module-level async report generation ─────────────────────────────────────

import asyncio
import logging as _logging

from backend.app.core.runtime_config import REPORT_OLLAMA_NUM_PREDICT

_report_logger = _logging.getLogger("graph_rag.report_generator")


def _fallback_structured_report(
    crop: str,
    disease: str,
    confidence: float,
    context_chunks: List[str],
) -> Dict:
    """Return a safe structured report when LLM output is unavailable/unparseable."""
    disease_display = (disease or "Unknown").replace("___", " - ").replace("__", " ").replace("_", " ")
    conf_pct = max(0.0, min(100.0, float(confidence or 0.0) * 100.0))
    context_hint = "Context-informed" if context_chunks else "General advisory"

    return {
        "crop_identified": crop or "Unknown",
        "disease_identified": disease_display,
        "disease_overview": (
            f"{context_hint} report for {disease_display} on {crop}. "
            f"Model confidence was {conf_pct:.1f}%."
        ),
        "symptoms": "Look for affected leaf tissue, discoloration, lesions, and progressive canopy damage.",
        "causes": "Often linked to pathogen pressure, favorable humidity, poor sanitation, and susceptible crop stage.",
        "severity": "Moderate to high if unmanaged during active spread windows.",
        "immediate_steps": "Scout hotspot patches, remove heavily infected tissue, avoid overhead irrigation, and improve field hygiene.",
        "treatment": "Use crop-labeled integrated control measures (cultural + biological/chemical) following local recommendations.",
        "prevention": "Use clean seed/planting material, resistant varieties where available, balanced nutrition, and preventive scouting.",
        "possible_impact": "If unmanaged, disease may reduce vigor, quality, and final yield with added input costs.",
        "monitoring_advice": "Monitor every 2-3 days during humid weather and reassess treatment efficacy after interventions.",
    }


async def generate_diagnosis_report(
    crop: str, disease: str, confidence: float
) -> Dict:
    """
    Generate a structured diagnosis report using the Graph RAG pipeline + LLM.

    Orchestrates:
      1. Enrich the knowledge base with AGRIS + AGRICOLA data.
      2. Query FAISS vector index for top-5 context chunks.
      3. Query NetworkX graph for structured agronomic context.
    4. Build prompts and call the configured LLM (via ``asyncio.to_thread``).
      5. Parse and validate the JSON response.
      6. Retry once with a stricter prompt if parsing fails.

    Parameters
    ----------
    crop : str
        The identified crop name (top-1 CNN prediction).
    disease : str
        The identified disease class label (top-1 CNN prediction).
    confidence : float
        CNN prediction confidence (0–1).

    Returns
    -------
    dict
        Parsed report dict with 11 keys on success, or
        ``{"error": ..., "raw": ...}`` on failure.
    """
    _report_logger.info(
        "Generating diagnosis report — crop='%s', disease='%s', confidence=%.3f",
        crop, disease, confidence,
    )

    # ── Step 1: Enrich knowledge base ────────────────────────────────────
    try:
        from .graph_builder import enrich_graph_for_disease
        await enrich_graph_for_disease(crop, disease)
    except Exception as exc:
        _report_logger.error("Graph enrichment failed: %s", exc)

    # ── Step 2: Retrieve FAISS context ───────────────────────────────────
    context_chunks: List[str] = []
    try:
        from backend.app.chatbot.ingestion.embedder import embed_query
        from backend.app.chatbot import document_registry

        query_text = f"{crop} {disease} disease symptoms causes treatment"
        query_vec = embed_query(query_text)
        document_registry.ensure_loaded()
        faiss_results = document_registry.search(query_vec, top_k=5)
        for res in faiss_results:
            context_chunks.append(res["text"])
        _report_logger.info("Retrieved %d FAISS context chunks", len(context_chunks))
    except Exception as exc:
        _report_logger.warning("FAISS context retrieval failed: %s", exc)

    # ── Step 3: Retrieve NetworkX graph context ──────────────────────────
    try:
        from .graph_builder import AgroKGBuilder

        kb = AgroKGBuilder.load()
        q_engine = GraphQueryEngine(kb)
        qctx = q_engine.query(crop_name=crop, disease_name=disease)
        kg_text = q_engine.format_context_for_llm(qctx)
        if kg_text.strip():
            context_chunks.append("KNOWLEDGE GRAPH DATA:\n" + kg_text)
            _report_logger.info("Added graph context (%d chars)", len(kg_text))
    except Exception as exc:
        _report_logger.warning("Graph context retrieval failed: %s", exc)

    # ── Step 4: Build prompts ────────────────────────────────────────────
    from .report_prompt import build_system_prompt, build_user_prompt, parse_llm_response

    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(crop, disease, confidence, context_chunks)
    full_prompt = f"{system_prompt}\n\n{user_prompt}"

    # ── Step 5: Call configured LLM (sync client wrapped in asyncio.to_thread) ───
    from backend.app.chatbot.client import generate as llm_generate

    raw_response = ""
    try:
        _report_logger.info("Sending prompt to configured LLM via asyncio.to_thread…")
        raw_response = await asyncio.to_thread(
            llm_generate,
            full_prompt,
            None,
            REPORT_OLLAMA_NUM_PREDICT,
        )
        _report_logger.info("LLM responded (%d chars)", len(raw_response))

        # ── Step 5a: Parse response ──────────────────────────────────────
        parsed = parse_llm_response(raw_response)
        _report_logger.info("Report parsed successfully for %s / %s", crop, disease)
        return parsed

    except ValueError as parse_err:
        # ── Step 6: Retry with stricter prompt ───────────────────────────
        _report_logger.warning(
            "First parse attempt failed: %s — retrying with stricter prompt",
            parse_err,
        )
        strict_prompt = (
            full_prompt
            + "\n\nCRITICAL: Return ONLY raw JSON, nothing else. "
            "No explanation, no wrapper text."
        )
        try:
            raw_response_2 = await asyncio.to_thread(
                llm_generate,
                strict_prompt,
                None,
                REPORT_OLLAMA_NUM_PREDICT,
            )
            parsed = parse_llm_response(raw_response_2)
            _report_logger.info("Retry succeeded for %s / %s", crop, disease)
            return parsed
        except Exception as retry_err:
            _report_logger.error("Retry also failed: %s", retry_err)
            return _fallback_structured_report(crop, disease, confidence, context_chunks)

    except Exception as exc:
        _report_logger.error("LLM generation failed: %s", exc)
        return _fallback_structured_report(crop, disease, confidence, context_chunks)
