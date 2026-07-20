from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str


class SearchRequest(BaseModel):
    query: str = Field(min_length=2)
    top_k: int | None = None


class RetrievedChunk(BaseModel):
    chunk_id: int
    source: str
    row_index: int
    content: str
    score: float


class SearchResponse(BaseModel):
    query: str
    results: list[RetrievedChunk]


class ChatRequest(BaseModel):
    question: str = Field(min_length=2)
    top_k: int | None = None


class ChatResponse(BaseModel):
    question: str
    answer: str
    citations: list[RetrievedChunk]


class IngestRequest(BaseModel):
    csv_path: str
    max_rows: int | None = None


class IngestResponse(BaseModel):
    csv_path: str
    total_rows: int
    indexed_chunks: int
    message: str


class IngestDocumentsRequest(BaseModel):
    input_path: str = "input"
    patterns: list[str] | None = None
    prefer_docling: bool = False
    chunk_size: int = Field(default=1200, ge=200, le=5000)
    chunk_overlap: int = Field(default=150, ge=0, le=1000)


class IngestDocumentsResponse(BaseModel):
    input_path: str
    indexed_documents: int
    indexed_chunks: int
    message: str


class DocumentRow(BaseModel):
    row_index: int
    payload: dict[str, Any]
