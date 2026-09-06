import argparse
import csv
import io
import sys
import zipfile
from pathlib import Path

import httpx

# Some NHTSA fields can exceed Python's default CSV field-size limit.
csv.field_size_limit(sys.maxsize)

# Allow `from app...` imports when this script is run from the project root.
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Base, SessionLocal, engine
from app.models import TSBChunk
from app.services.llm import get_embeddings


# Use NHTSA's current Manufacturer Communications export.
URLS = [
    "https://static.nhtsa.gov/odi/ffdd/tsbs/MFR_COMMS_RECEIVED_2020-2024.zip",
]

YEARS = {2020, 2021, 2022, 2023, 2024}
TARGET_NAMES = {"HONDA CIVIC", "TOYOTA RAV4"}


def normalize_key(value: str) -> str:
    return " ".join(
        str(value).replace("_", " ").strip().lower().split()
    )


def normalize_text(value: str) -> str:
    return " ".join(
        str(value or "").strip().upper().split()
    )


def get_value(row: dict, *candidates: str) -> str:
    normalized = {
        normalize_key(k): str(v or "").strip()
        for k, v in row.items()
        if k is not None
    }

    for candidate in candidates:
        value = normalized.get(normalize_key(candidate))
        if value is not None:
            return value

    return ""


def canonical_vehicle(
    make: str,
    model: str,
) -> tuple[str, str] | None:
    """
    Map NHTSA model variants into our two MVP vehicle families.
    """
    make = normalize_text(make)
    model = normalize_text(model)

    model_compact = (
        model.replace(" ", "")
        .replace("-", "")
    )

    if make == "HONDA" and "CIVIC" in model:
        return "HONDA", "CIVIC"

    if make == "TOYOTA" and "RAV4" in model_compact:
        return "TOYOTA", "RAV4"

    return None


def download(
    url: str,
    target: Path,
) -> None:
    if target.exists():
        print(f"Using cached file: {target}")
        return

    print(f"Downloading {url}")

    with httpx.stream(
        "GET",
        url,
        follow_redirects=True,
        timeout=120.0,
    ) as response:
        response.raise_for_status()

        with target.open("wb") as f:
            for chunk in response.iter_bytes():
                f.write(chunk)

    print(f"Saved to: {target}")


def read_data_members(path: Path):
    """
    Read either CSV or tab-separated TXT files from the NHTSA ZIP.
    """
    with zipfile.ZipFile(path) as zf:
        members = [
            name
            for name in zf.namelist()
            if name.lower().endswith(
                (".csv", ".txt")
            )
        ]

        if not members:
            raise RuntimeError(
                f"No CSV/TSV file found inside {path.name}. "
                f"Members: {zf.namelist()[:10]}"
            )

        for member in members:
            print(f"Reading {member}")

            delimiter = (
                "\t"
                if member.lower().endswith(".txt")
                else ","
            )

            with zf.open(member) as raw:
                text = io.TextIOWrapper(
                    raw,
                    encoding="utf-8-sig",
                    errors="replace",
                    newline="",
                )

                reader = csv.DictReader(
                    text,
                    delimiter=delimiter,
                )

                if not reader.fieldnames:
                    continue

                print(
                    f"Detected columns: "
                    f"{reader.fieldnames[:12]}"
                )

                for row in reader:
                    yield row


def chunk_text(
    text: str,
    size: int = 1500,
    overlap: int = 180,
) -> list[str]:
    text = " ".join(
        (text or "").split()
    )

    if not text:
        return []

    if len(text) <= size:
        return [text]

    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = min(
            len(text),
            start + size,
        )

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = end - overlap

    return chunks


def collect_records(
    paths: list[Path],
    max_docs_per_vehicle: int,
):
    seen: set[tuple] = set()

    counts = {
        name: 0
        for name in TARGET_NAMES
    }

    records: list[dict] = []

    # If the schema ever changes again, these samples make
    # the problem obvious instead of silently returning zero.
    sample_pairs: list[tuple[str, str]] = []

    for path in paths:
        for row in read_data_members(path):

            make_raw = get_value(
                row,
                "Make",
                "MAKETXT",
            )

            model_raw = get_value(
                row,
                "Model",
                "MODELTXT",
            )

            if (
                len(sample_pairs) < 8
                and (make_raw or model_raw)
            ):
                pair = (
                    make_raw,
                    model_raw,
                )

                if pair not in sample_pairs:
                    sample_pairs.append(pair)

            canonical = canonical_vehicle(
                make_raw,
                model_raw,
            )

            if canonical is None:
                continue

            make, model = canonical
            target_name = f"{make} {model}"

            year_text = get_value(
                row,
                "Model Year",
                "ModelYear",
                "YEARTXT",
            ).strip()

            try:
                year = int(
                    float(year_text)
                )
            except (ValueError, TypeError):
                continue

            if year not in YEARS:
                continue

            if counts[target_name] >= max_docs_per_vehicle:
                if all(
                    value >= max_docs_per_vehicle
                    for value in counts.values()
                ):
                    break

                continue

            document_id = get_value(
                row,
                "TSB/Document ID",
                "Document ID",
                "TSB Document ID",
                "BULNO",
            )

            nhtsa_id = get_value(
                row,
                "NHTSA ID Number",
                "NHTSA ID",
                "ID",
            )

            summary = get_value(
                row,
                "Concise Summary",
                "Summary",
                "SUMMARY",
                "Communication Summary",
            )

            if not summary:
                continue

            identity = (
                document_id
                or nhtsa_id
                or summary[:120]
            )

            key = (
                identity,
                make,
                model,
                year,
            )

            if key in seen:
                continue

            seen.add(key)

            stable_id = str(identity)[:150]

            document_id = (
                document_id
                or stable_id
            )[:160]

            nhtsa_id = (
                nhtsa_id
                or stable_id
            )[:64]

            records.append(
                {
                    "nhtsa_id": nhtsa_id,
                    "document_id": document_id,
                    "make": make,
                    "model": model,
                    "model_year": year,
                    "component": get_value(
                        row,
                        "NHTSA Components",
                        "Component",
                        "Components",
                        "COMPNAME",
                    )[:256],
                    "communication_type": get_value(
                        row,
                        "Communication Type",
                        "Type",
                    )[:128],
                    "summary": summary,
                }
            )

            counts[target_name] += 1

            if all(
                value >= max_docs_per_vehicle
                for value in counts.values()
            ):
                break

        if all(
            value >= max_docs_per_vehicle
            for value in counts.values()
        ):
            break

    print(
        f"Collected records: {counts}"
    )

    if not records:
        print(
            f"Sample make/model values seen: "
            f"{sample_pairs}"
        )

    return records


def embed_in_batches(
    texts: list[str],
    batch_size: int = 64,
) -> list[list[float]]:
    embeddings = get_embeddings()

    vectors: list[list[float]] = []
    total = len(texts)

    for start in range(
        0,
        total,
        batch_size,
    ):
        batch = texts[
            start:start + batch_size
        ]

        end = min(
            start + len(batch),
            total,
        )

        print(
            f"Embedding chunks "
            f"{start + 1}-{end} "
            f"of {total}..."
        )

        vectors.extend(
            embeddings.embed_documents(
                batch
            )
        )

    return vectors


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Ingest NHTSA manufacturer communications "
            "for Civic/RAV4 RAG."
        )
    )

    parser.add_argument(
        "--max-docs-per-vehicle",
        type=int,
        default=150,
    )

    parser.add_argument(
        "--clear",
        action="store_true",
        help=(
            "Clear existing TSB chunks "
            "before ingesting."
        ),
    )

    args = parser.parse_args()

    raw_dir = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "raw"
    )

    raw_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    zip_paths: list[Path] = []

    for url in URLS:
        path = (
            raw_dir
            / url.rsplit("/", 1)[-1]
        )

        download(
            url,
            path,
        )

        zip_paths.append(path)

    docs = collect_records(
        zip_paths,
        args.max_docs_per_vehicle,
    )

    if not docs:
        raise RuntimeError(
            "No matching Civic/RAV4 manufacturer "
            "communications were found. "
            "Detected columns and sample make/model "
            "values were printed above."
        )

    texts: list[str] = []
    metadata: list[dict] = []

    for doc in docs:
        for chunk in chunk_text(
            doc["summary"]
        ):
            texts.append(chunk)
            metadata.append(doc)

    if not texts:
        raise RuntimeError(
            "Records were found, but no usable "
            "text chunks were generated."
        )

    print(
        f"Preparing {len(texts)} chunks "
        f"from {len(docs)} official NHTSA "
        f"manufacturer-communication records."
    )

    vectors = embed_in_batches(
        texts
    )

    if len(vectors) != len(texts):
        raise RuntimeError(
            f"Embedding count mismatch: "
            f"{len(vectors)} vectors for "
            f"{len(texts)} chunks."
        )

    Base.metadata.create_all(
        bind=engine
    )

    with SessionLocal() as db:

        if args.clear:
            deleted = db.query(
                TSBChunk
            ).delete()

            print(
                f"Cleared {deleted} "
                f"existing TSB chunks."
            )

        for text, vector, meta in zip(
            texts,
            vectors,
            metadata,
        ):
            db.add(
                TSBChunk(
                    chunk_text=text,
                    embedding=vector,
                    nhtsa_id=meta["nhtsa_id"],
                    document_id=meta["document_id"],
                    make=meta["make"],
                    model=meta["model"],
                    model_year=meta["model_year"],
                    component=meta["component"],
                    communication_type=meta[
                        "communication_type"
                    ],
                    summary=meta["summary"],
                )
            )

        db.commit()

    print(
        f"Inserted {len(texts)} "
        f"TSB/manufacturer-communication chunks."
    )

    print(
        "TSB RAG ingestion complete."
    )


if __name__ == "__main__":
    main()