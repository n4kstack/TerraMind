"""
Chatbot Service - Main Orchestrator
====================================
Ties together all RAG components:
  detect intent  ->  embed query  ->  FAISS search  ->  guardrail check  ->
  build intent-aware prompt  ->  call Ollama  ->  post-process  ->  respond

This is the single entry-point called by the API endpoint.
"""

import logging
import re
from typing import Optional

from app.core.config import RETRIEVAL_TOP_K, MAX_CONTEXT_CHUNKS
from app.chatbot.ingestion.embedder import embed_query
from app.chatbot import document_registry
from app.chatbot.context_builder import build_full_prompt, get_refusal_message
from app.chatbot.client import generate as ollama_generate, OllamaError
from app.services.retrieval_guardrails import run_guardrails
from graph_rag.domain_policy import classify_query, refusal_message, smalltalk_reply
from app.services.intent_detector import detect_user_intent, Intent

logger = logging.getLogger(__name__)


# ── Post-processing: strip unrelated sections from LLM output ────────────────

# Mapping of intents to heading patterns that should NOT appear in the response
_FORBIDDEN_SECTIONS: dict[str, list[re.Pattern]] = {
    "pesticide": [
        re.compile(r"^#{1,4}\s*(Symptoms?|Signs?)\s*$", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^#{1,4}\s*(Causes?|Reasons?)\s*$", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^#{1,4}\s*(Prevention|Precautions?)\s*$", re.MULTILINE | re.IGNORECASE),
    ],
    "symptoms": [
        re.compile(r"^#{1,4}\s*(Causes?|Reasons?)\s*$", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^#{1,4}\s*(Treatment|Pesticide|Fungicide|Management|Control)\s*$", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^#{1,4}\s*(Prevention|Precautions?)\s*$", re.MULTILINE | re.IGNORECASE),
    ],
    "cause": [
        re.compile(r"^#{1,4}\s*(Symptoms?|Signs?)\s*$", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^#{1,4}\s*(Treatment|Pesticide|Fungicide|Management|Control)\s*$", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^#{1,4}\s*(Prevention|Precautions?)\s*$", re.MULTILINE | re.IGNORECASE),
    ],
    "prevention": [
        re.compile(r"^#{1,4}\s*(Symptoms?|Signs?)\s*$", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^#{1,4}\s*(Causes?|Reasons?)\s*$", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^#{1,4}\s*(Treatment|Pesticide|Fungicide|Management|Control)\s*$", re.MULTILINE | re.IGNORECASE),
    ],
    "severity": [
        re.compile(r"^#{1,4}\s*(Symptoms?|Signs?)\s*$", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^#{1,4}\s*(Causes?|Reasons?)\s*$", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^#{1,4}\s*(Prevention|Precautions?)\s*$", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^#{1,4}\s*(Treatment|Pesticide|Fungicide|Management|Control)\s*$", re.MULTILINE | re.IGNORECASE),
    ],
}

# Sections that should NEVER appear regardless of intent
_ALWAYS_FORBIDDEN = [
    re.compile(r"^#{1,4}\s*(References?|Sources?|Conclusion)\s*$", re.MULTILINE | re.IGNORECASE),
]


def _strip_forbidden_sections(answer: str, intent: Intent) -> str:
    """
    Post-processing pass: remove any markdown sections that shouldn't
    appear for the detected intent.

    Works by finding forbidden heading lines and removing everything from
    that heading until the next heading of equal or higher level (or end).
    """
    forbidden = _FORBIDDEN_SECTIONS.get(intent, []) + _ALWAYS_FORBIDDEN

    # Check if any forbidden pattern matches
    has_violations = any(p.search(answer) for p in forbidden)
    if not has_violations:
        return answer

    logger.info(
        "Post-processing: stripping forbidden sections for intent=%s", intent
    )

    lines = answer.split("\n")
    result_lines: list[str] = []
    skip_until_next_heading = False
    skipped_heading_level = 0

    for line in lines:
        stripped = line.strip()

        # Check if this line is a heading
        heading_match = re.match(r"^(#{1,4})\s+", stripped)

        if heading_match:
            heading_level = len(heading_match.group(1))

            # If we're skipping and hit a heading of equal or higher level, stop skipping
            if skip_until_next_heading and heading_level <= skipped_heading_level:
                skip_until_next_heading = False

            # Check if this heading is forbidden
            is_forbidden = any(p.match(stripped) for p in forbidden)
            if is_forbidden:
                skip_until_next_heading = True
                skipped_heading_level = heading_level
                continue

        if skip_until_next_heading:
            continue

        result_lines.append(line)

    cleaned = "\n".join(result_lines).strip()
    # Remove excessive blank lines left after stripping
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def ask(
    question: str,
    top_k: int | None = None,
    identified_crop: Optional[str] = None,
    identified_class: Optional[str] = None,
) -> dict:
    """
    Process a user question through the intent-aware RAG pipeline.

    Parameters
    ----------
    question : str
        The user's question.
    top_k : int, optional
        Number of retrieval results (default from config).
    identified_crop : str, optional
        Crop from diagnosis context (e.g. ``"Tomato"``).
    identified_class : str, optional
        Disease class from diagnosis context (e.g. ``"Tomato___Late_blight"``).

    Returns
    -------
    dict
        Keys: ``answer``, ``allowed``, ``reason``, ``sources``, ``intent``.
    """
    k = top_k or RETRIEVAL_TOP_K

    # ── 1. Detect user intent ────────────────────────────────────────────
    intent = detect_user_intent(question)
    logger.info("Detected intent: %s  (query=%r)", intent, question[:80])

    # ── 1b. Domain gate ──────────────────────────────────────────────────
    # Runs before retrieval: there is no point embedding and searching for a
    # question this assistant will not answer, and courtesy deserves a reply
    # rather than the refusal template.
    domain = classify_query(question)
    if domain == "smalltalk":
        return {
            "answer": smalltalk_reply(question, assistant="TerraMind"),
            "allowed": True,
            "reason": "smalltalk",
            "sources": [],
            "intent": intent,
        }
    if domain == "off_topic":
        logger.info("Domain policy BLOCKED (query=%r)", question[:80])
        return {
            "answer": refusal_message(assistant="TerraMind"),
            "allowed": False,
            "reason": "off_topic",
            "sources": [],
            "intent": intent,
        }

    # ── 2. Ensure index is loaded ────────────────────────────────────────
    try:
        document_registry.ensure_loaded()
    except FileNotFoundError as exc:
        logger.error("Vector store not found: %s", exc)
        return {
            "answer": "The document index has not been built yet. Please run the index builder first.",
            "allowed": False,
            "reason": "index_missing",
            "sources": [],
            "intent": intent,
        }

    # ── 3. Build the query ───────────────────────────────────────────────
    # If diagnosis context is provided, enrich the query to bias retrieval
    enriched_query = question
    if identified_crop:
        enriched_query = f"{identified_crop} {enriched_query}"
    if identified_class:
        label = identified_class.replace("___", " ").replace("__", " ").replace("_", " ")
        enriched_query = f"{label} {enriched_query}"

    # ── 4. Embed & search ────────────────────────────────────────────────
    query_vec = embed_query(enriched_query)
    results = document_registry.search(query_vec, top_k=k)

    # ── 5. Guardrails ────────────────────────────────────────────────────
    allowed, reason = run_guardrails(question, results)
    if not allowed:
        logger.info("Guardrail BLOCKED  (reason=%s)", reason)
        return {
            "answer": get_refusal_message(),
            "allowed": False,
            "reason": reason,
            "sources": [],
            "intent": intent,
        }

    # ── 6. Build intent-aware prompt ─────────────────────────────────────
    context_chunks = results[:MAX_CONTEXT_CHUNKS]
    prompt = build_full_prompt(
        question=question,
        chunks=context_chunks,
        intent=intent,
        identified_crop=identified_crop,
        identified_class=identified_class,
    )

    # ── 7. Call Ollama ───────────────────────────────────────────────────
    try:
        answer = ollama_generate(prompt)
    except OllamaError as exc:
        logger.error("Ollama error: %s", exc)
        return {
            "answer": f"LLM service error: {exc}",
            "allowed": False,
            "reason": "llm_error",
            "sources": [],
            "intent": intent,
        }

    # ── 8. False-refusal safety net ──────────────────────────────────────
    # The small LLM sometimes regurgitates refusal text from its prompt
    # even when the query is valid. If guardrails passed but the LLM
    # refused anyway, retry with a simpler direct prompt.
    _REFUSAL_FINGERPRINTS = [
        "I'm designed to assist with crop diseases",
        "Please ask a question related to the diagnosed crop",
        "I cannot assist with",
        "not related to agriculture",
        "I don't have enough information",
        "don't have enough specific information",
        "unable to provide",
        "I'm not able to",
        "outside my scope",
        "beyond my expertise",
    ]
    is_false_refusal = any(fp.lower() in answer.lower() for fp in _REFUSAL_FINGERPRINTS)

    if is_false_refusal:
        logger.warning(
            "False refusal detected (intent=%s). Retrying with simplified prompt.",
            intent,
        )
        # Build a direct, minimal prompt that won't confuse the small model
        context_text = "\n\n".join(c["text"] for c in context_chunks)
        diag_hint = ""
        if identified_crop:
            diag_hint += f"Crop: {identified_crop}. "
        if identified_class:
            label = identified_class.replace("___", " ").replace("__", " ").replace("_", " ")
            diag_hint += f"Condition: {label}. "

        retry_prompt = (
            f"You are an agricultural expert. "
            f"{diag_hint}"
            f"Using the information below, answer the question.\n\n"
            f"{context_text}\n\n"
            f"Question: {question}\n\n"
            f"Answer:"
        )
        try:
            answer = ollama_generate(retry_prompt)
        except OllamaError:
            pass  # keep the original answer if retry also fails

        # Check again - if still refusing, force a context-based answer
        still_refusing = any(fp.lower() in answer.lower() for fp in _REFUSAL_FINGERPRINTS)
        if still_refusing and context_chunks:
            logger.warning("Retry also produced false refusal. Using context summary.")
            crop_label = identified_crop or "your crop"
            answer = (
                f"Here's what I found about {crop_label}:\n\n"
                f"{context_chunks[0]['text'][:500]}"
            )

    # ── 9. Post-processing: strip unrelated sections ─────────────────────
    answer = _strip_forbidden_sections(answer, intent)

    # ── 10. Assemble sources ─────────────────────────────────────────────
    sources = [
        {
            "file_name": c["file_name"],
            "page": c["page"],
            "snippet": c["text"][:200] + ("…" if len(c["text"]) > 200 else ""),
            "score": round(c["score"], 4),
        }
        for c in context_chunks
    ]

    return {
        "answer": answer,
        "allowed": True,
        "reason": "ok",
        "sources": sources,
        "intent": intent,
    }
