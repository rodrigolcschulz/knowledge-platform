from pathlib import Path
from typing import Any

import pandas as pd

from app.embeddings import embedding_service
from app.vectorstore import ensure_schema, insert_chunk, reset_source


def normalize_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    return value


def row_to_text(row: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in row.items():
        value = normalize_value(value)
        if value is None:
            continue
        text_value = str(value).strip()
        if not text_value:
            continue
        parts.append(f"{key}: {text_value}")
    return "\n".join(parts)


def ingest_csv(csv_path: str, max_rows: int | None = None) -> tuple[int, int]:
    source = Path(csv_path).name

    df = pd.read_csv(csv_path)
    if max_rows is not None and max_rows > 0:
        df = df.head(max_rows)

    ensure_schema(embedding_service.dimensions)
    reset_source(source)

    indexed = 0
    for row_index, row in df.iterrows():
        payload = {key: normalize_value(value) for key, value in row.to_dict().items()}
        content = row_to_text(payload)
        if not content:
            continue

        embedding = embedding_service.embed(content)
        insert_chunk(
            source=source,
            row_index=int(row_index),
            content=content,
            payload=payload,
            embedding=embedding,
        )
        indexed += 1

    return len(df), indexed
