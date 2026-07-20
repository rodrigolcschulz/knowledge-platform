import json
import math
from contextlib import contextmanager
from typing import Any, Generator

import psycopg
import pandas as pd

from app.config import settings


@contextmanager
def get_connection() -> Generator[psycopg.Connection, None, None]:
    conn = psycopg.connect(settings.postgres_dsn, autocommit=True)
    try:
        yield conn
    finally:
        conn.close()


def to_vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.10f}" for value in values) + "]"


def sanitize_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: sanitize_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_json_value(item) for item in value]
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def ensure_schema(embedding_dims: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        with conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS rag_chunks (
                    id BIGSERIAL PRIMARY KEY,
                    source TEXT NOT NULL,
                    row_index INT NOT NULL,
                    content TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    embedding VECTOR({embedding_dims}) NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS rag_chunks_row_idx ON rag_chunks(row_index);")
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS rag_chunks_embedding_idx
                ON rag_chunks USING hnsw (embedding vector_cosine_ops);
                """
            )


def reset_source(source: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rag_chunks WHERE source = %s", (source,))


def insert_chunk(source: str, row_index: int, content: str, payload: dict[str, Any], embedding: list[float]) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rag_chunks(source, row_index, content, payload, embedding)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    source,
                    row_index,
                    content,
                    json.dumps(sanitize_json_value(payload), ensure_ascii=False, allow_nan=False),
                    to_vector_literal(embedding),
                ),
            )


def similarity_search(query_embedding: list[float], top_k: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    source,
                    row_index,
                    content,
                    payload,
                    (1 - (embedding <=> %s::vector)) AS score
                FROM rag_chunks
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (to_vector_literal(query_embedding), to_vector_literal(query_embedding), top_k),
            )
            rows = cur.fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        results.append(
            {
                "chunk_id": int(row[0]),
                "source": str(row[1]),
                "row_index": int(row[2]),
                "content": str(row[3]),
                "payload": row[4],
                "score": float(row[5]),
            }
        )
    return results
