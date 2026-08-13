"""
Retrieval Guardrails
====================
Three layers of restriction ensuring the chatbot never answers outside
the provided PDF context.

Layer 1 - Similarity threshold:  reject if best score < threshold
Layer 2 - Domain policy:  answer only agriculture (and plain courtesy)
Layer 3 - Empty retrieval:  reject if FAISS returns no results at all
"""

import logging
from typing import List, Tuple

from app.core.config import SIMILARITY_THRESHOLD

# Shared with AugNosis. Layer 2 used to be a local blocklist of off-topic
# keywords, which can only catch subjects somebody thought to enumerate — and
# it drifted out of step with the AugNosis pipeline, which had no domain gate
# at all. One classifier, one behaviour, both assistants.
from graph_rag.domain_policy import classify_query

logger = logging.getLogger(__name__)


def check_off_topic(question: str) -> bool:
    """Return ``True`` if the question is neither agricultural nor courtesy."""
    domain = classify_query(question)
    if domain == "off_topic":
        logger.info("Domain policy rejected: %r", question[:80])
        return True
    return False


def check_retrieval_quality(
    results: List[dict],
) -> Tuple[bool, str]:
    """
    Evaluate retrieval results and decide whether to allow an answer.

    Returns
    -------
    (allowed, reason)
        ``allowed`` is True if at least one chunk meets the similarity
        threshold.  ``reason`` explains why the answer is blocked (if so).
    """
    if not results:
        return False, "no_results"

    best_score = results[0].get("score", 0.0)
    if best_score < SIMILARITY_THRESHOLD:
        logger.info(
            "Best retrieval score %.3f < threshold %.3f -> refusing",
            best_score,
            SIMILARITY_THRESHOLD,
        )
        return False, "low_similarity"

    return True, "ok"


def run_guardrails(
    question: str,
    results: List[dict],
) -> Tuple[bool, str]:
    """
    Run all three guardrail layers.

    Returns
    -------
    (allowed, reason)
    """
    # Layer 2 - off-topic keyword check (runs before retrieval quality
    # because it's cheaper and catches blatant misuse)
    if check_off_topic(question):
        return False, "off_topic"

    # Layer 1 + 3 - retrieval quality / empty results
    return check_retrieval_quality(results)
