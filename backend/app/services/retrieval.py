import re

from sqlalchemy import select

from ..db import SessionLocal
from ..models import TSBChunk
from .llm import get_embeddings

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "by",
    "for",
    "from",
    "has",
    "have",
    "i",
    "in",
    "is",
    "it",
    "my",
    "of",
    "on",
    "or",
    "the",
    "this",
    "to",
    "was",
    "when",
    "while",
    "with",
}

QUERY_EXPANSIONS = {
    "shake": ["vibration", "steering wheel shake", "high speed vibration"],
    "shakes": [
        "vibration",
        "steering wheel shake",
        "high speed vibration",
        "wheel balance",
        "tire balance",
        "brake vibration",
    ],
    "shaking": [
        "vibration",
        "steering wheel shake",
        "high speed vibration",
        "wheel balance",
        "tire balance",
        "brake vibration",
    ],
    "grinding": ["brake noise", "scraping noise", "braking noise"],
    "reboots": ["display resets", "head unit restart", "infotainment reboot"],
    "rebooting": ["display resets", "head unit restart", "infotainment reboot"],
    "highway": ["high speed", "60 mph", "70 mph"],
}

THERMAL_SYMPTOM_TERMS = (
    "temperature gauge",
    "above normal",
    "overheat",
    "overheating",
    "overheated",
    "hot smell",
    "coolant",
)


def expand_query(query: str) -> list[str]:
    """Generate conservative, deterministic paraphrases without inventing a diagnosis."""
    variants = [" ".join((query or "").split())]
    lowered = (query or "").lower()
    for term, expansions in QUERY_EXPANSIONS.items():
        if term in lowered:
            variants.extend(f"{query} {expansion}" for expansion in expansions)
    # "Hot days" describes ambient conditions for many benign HVAC complaints;
    # it must not be expanded to overheating unless the complaint contains an
    # explicit thermal/safety signal. This prevents unrelated cooling-system
    # bulletins from contaminating routine A/C triage.
    if any(term in lowered for term in THERMAL_SYMPTOM_TERMS):
        for expansion in ["overheating", "temperature above normal", "cooling system"]:
            variants.append(f"{query} {expansion}")
    return list(dict.fromkeys(variant for variant in variants if variant))


def tokenize(text: str) -> set[str]:
    """
    Lightweight lexical tokenizer used as a second relevance signal
    alongside semantic vector similarity.
    """
    words = re.findall(
        r"[a-zA-Z0-9]+",
        (text or "").lower(),
    )

    return {
        word
        for word in words
        if len(word) > 2
        and word not in STOP_WORDS
    }


def lexical_overlap(
    query: str,
    document: str,
) -> float:
    query_tokens = tokenize(query)
    document_tokens = tokenize(document)

    if not query_tokens:
        return 0.0

    overlap = query_tokens & document_tokens
    score = len(overlap) / len(query_tokens)
    if query.strip().lower() in document.lower():
        score = min(1.0, score + 0.25)
    return score


def search_tsb_chunks(
    year: int,
    make: str,
    model: str,
    query: str,
    k: int = 5,
) -> list[dict]:

    variants = expand_query(query)
    candidate_limit = max(k * 8, 32)
    exact_rows = []

    # Retrieve against every conservative query variant, then merge by chunk.
    # This handles the language gap without allowing an LLM to invent symptoms.
    with SessionLocal() as db:
        for variant in variants:
            vector = get_embeddings().embed_query(variant)
            vector_score_expr = (
                1 - TSBChunk.embedding.cosine_distance(vector)
            ).label("vector_score")
            stmt = (
                select(TSBChunk, vector_score_expr)
                .where(
                    TSBChunk.model_year == year,
                    TSBChunk.make == make.upper(),
                    TSBChunk.model == model.upper(),
                )
                .order_by(TSBChunk.embedding.cosine_distance(vector))
                .limit(candidate_limit)
            )
            exact_rows.extend((row, variant, "exact") for row in db.execute(stmt).all())

        # If an exact model-year has no indexed records, search the same model
        # family across nearby years and label that evidence as a fallback.
        if not exact_rows:
            for variant in variants[:2]:
                vector = get_embeddings().embed_query(variant)
                vector_score_expr = (
                    1 - TSBChunk.embedding.cosine_distance(vector)
                ).label("vector_score")
                stmt = (
                    select(TSBChunk, vector_score_expr)
                    .where(
                        TSBChunk.make == make.upper(),
                        TSBChunk.model == model.upper(),
                    )
                    .order_by(TSBChunk.embedding.cosine_distance(vector))
                    .limit(candidate_limit)
                )
                exact_rows.extend((row, variant, "family_fallback") for row in db.execute(stmt).all())

    # ------------------------------------------------------------
    # 3. Hybrid relevance scoring
    #
    # Vector similarity gives semantic similarity.
    # Lexical overlap prevents obviously unrelated documents
    # from ranking highly merely because they share generic
    # customer-service language.
    # ------------------------------------------------------------

    best_by_document = {}

    for row, matched_query, vehicle_match in exact_rows:
        chunk = row.TSBChunk

        text_for_matching = " ".join(
            [
                chunk.component or "",
                chunk.summary or "",
                chunk.chunk_text or "",
                getattr(chunk, "search_text", "") or "",
            ]
        )

        vector_score = float(
            row.vector_score or 0.0
        )

        # Score lexical overlap against the variant that actually retrieved
        # this document. Otherwise query expansion helps vector search but is
        # ignored by the second hybrid signal.
        lexical_score = lexical_overlap(
            matched_query,
            text_for_matching,
        )

        combined_score = 0.70 * vector_score + 0.30 * lexical_score
        if vehicle_match == "family_fallback":
            combined_score *= 0.92

        # --------------------------------------------------------
        # 4. Evidence threshold / abstention
        #
        # Do NOT return a document just because it happens to be
        # the least-bad match in the corpus.
        # --------------------------------------------------------

        # Abstain on weak semantic matches unless the expanded query also has
        # meaningful lexical support. This is important for a safety workflow:
        # a least-bad bulletin is not the same as applicable evidence.
        relevant = vector_score >= 0.40 or (
            vector_score >= 0.30 and lexical_score >= 0.25
        )

        if not relevant:
            continue

        item = {
                "nhtsa_id": chunk.nhtsa_id,
                "document_id": chunk.document_id,
                "component": chunk.component,
                "communication_type": chunk.communication_type,
                "summary": chunk.summary,
                "chunk_text": chunk.chunk_text,
                "source_url": getattr(chunk, "source_url", None),
                "section_title": getattr(chunk, "section_title", ""),
                "page_number": getattr(chunk, "page_number", None),
                "vehicle_match": vehicle_match,
                "matched_query": matched_query,
                "vector_score": round(
                    vector_score,
                    4,
                ),
                "lexical_score": round(
                    lexical_score,
                    4,
                ),
                "score": round(
                    combined_score,
                    4,
                ),
            }
        document_key = (item["document_id"], item["model_year"] if "model_year" in item else year)
        current = best_by_document.get(document_key)
        if current is None or item["score"] > current["score"]:
            best_by_document[document_key] = item

    ranked = sorted(best_by_document.values(), key=lambda item: item["score"], reverse=True)
    return ranked[:k]
