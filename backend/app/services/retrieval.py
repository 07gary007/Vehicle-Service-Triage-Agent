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

    overlap = (
        query_tokens
        & document_tokens
    )

    return len(overlap) / len(query_tokens)


def search_tsb_chunks(
    year: int,
    make: str,
    model: str,
    query: str,
    k: int = 5,
) -> list[dict]:

    # ------------------------------------------------------------
    # 1. Embed the service concern
    # ------------------------------------------------------------

    vector = get_embeddings().embed_query(
        query
    )

    vector_score_expr = (
        1
        - TSBChunk.embedding.cosine_distance(
            vector
        )
    ).label("vector_score")

    # Pull more candidates than we ultimately return.
    candidate_limit = max(
        k * 6,
        20,
    )

    # ------------------------------------------------------------
    # 2. Metadata-filtered vector retrieval
    # ------------------------------------------------------------

    with SessionLocal() as db:
        stmt = (
            select(
                TSBChunk,
                vector_score_expr,
            )
            .where(
                TSBChunk.model_year == year,
                TSBChunk.make == make.upper(),
                TSBChunk.model == model.upper(),
            )
            .order_by(
                TSBChunk.embedding.cosine_distance(
                    vector
                )
            )
            .limit(
                candidate_limit
            )
        )

        rows = db.execute(
            stmt
        ).all()

    # ------------------------------------------------------------
    # 3. Hybrid relevance scoring
    #
    # Vector similarity gives semantic similarity.
    # Lexical overlap prevents obviously unrelated documents
    # from ranking highly merely because they share generic
    # customer-service language.
    # ------------------------------------------------------------

    ranked = []

    for row in rows:
        chunk = row.TSBChunk

        text_for_matching = " ".join(
            [
                chunk.component or "",
                chunk.summary or "",
                chunk.chunk_text or "",
            ]
        )

        vector_score = float(
            row.vector_score or 0.0
        )

        lexical_score = lexical_overlap(
            query,
            text_for_matching,
        )

        combined_score = (
            0.80 * vector_score
            + 0.20 * lexical_score
        )

        # --------------------------------------------------------
        # 4. Evidence threshold / abstention
        #
        # Do NOT return a document just because it happens to be
        # the least-bad match in the corpus.
        # --------------------------------------------------------

        relevant = (
            vector_score >= 0.30
            or (
                vector_score >= 0.24
                and lexical_score >= 0.20
            )
        )

        if not relevant:
            continue

        ranked.append(
            {
                "nhtsa_id": chunk.nhtsa_id,
                "document_id": chunk.document_id,
                "component": chunk.component,
                "communication_type": chunk.communication_type,
                "summary": chunk.summary,
                "chunk_text": chunk.chunk_text,
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
        )

    # ------------------------------------------------------------
    # 5. Re-rank and return only high-quality evidence
    # ------------------------------------------------------------

    ranked.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return ranked[:k]