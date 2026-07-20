from pathlib import Path

from fastapi import FastAPI, HTTPException
from openai import OpenAIError
from psycopg import Error as PsycopgError

from app.document_ingestion import ingest_documents
from app.generation import generate_answer
from app.ingestion import ingest_csv
from app.retrieval import search
from app.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    IngestDocumentsRequest,
    IngestDocumentsResponse,
    IngestRequest,
    IngestResponse,
    RetrievedChunk,
    SearchRequest,
    SearchResponse,
)

app = FastAPI(title="Knowledge Platform RAG", version="0.1.0")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/ingest/csv", response_model=IngestResponse)
def ingest_csv_endpoint(payload: IngestRequest) -> IngestResponse:
    csv_file = Path(payload.csv_path)
    if not csv_file.exists():
        raise HTTPException(status_code=404, detail="CSV file not found")

    try:
        total_rows, indexed_chunks = ingest_csv(str(csv_file), max_rows=payload.max_rows)
    except PsycopgError as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc

    return IngestResponse(
        csv_path=str(csv_file),
        total_rows=total_rows,
        indexed_chunks=indexed_chunks,
        message="CSV indexed successfully",
    )


@app.post("/ingest/documents", response_model=IngestDocumentsResponse)
def ingest_documents_endpoint(payload: IngestDocumentsRequest) -> IngestDocumentsResponse:
    input_path = Path(payload.input_path)
    if not input_path.exists():
        raise HTTPException(status_code=404, detail="Input path not found")

    if payload.chunk_overlap >= payload.chunk_size:
        raise HTTPException(status_code=400, detail="chunk_overlap must be smaller than chunk_size")

    try:
        indexed_documents, indexed_chunks = ingest_documents(
            input_path=str(input_path),
            patterns=payload.patterns,
            prefer_docling=payload.prefer_docling,
            chunk_size=payload.chunk_size,
            chunk_overlap=payload.chunk_overlap,
        )
    except PsycopgError as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return IngestDocumentsResponse(
        input_path=str(input_path),
        indexed_documents=indexed_documents,
        indexed_chunks=indexed_chunks,
        message="Documents indexed successfully",
    )


@app.post("/search", response_model=SearchResponse)
def search_endpoint(payload: SearchRequest) -> SearchResponse:
    try:
        rows = search(payload.query, top_k=payload.top_k)
    except PsycopgError as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc

    results = [
        RetrievedChunk(
            chunk_id=item["chunk_id"],
            source=item["source"],
            row_index=item["row_index"],
            content=item["content"],
            score=item["score"],
        )
        for item in rows
    ]
    return SearchResponse(query=payload.query, results=results)


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequest) -> ChatResponse:
    try:
        rows = search(payload.question, top_k=payload.top_k)
    except PsycopgError as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc

    if not rows:
        return ChatResponse(
            question=payload.question,
            answer="Nao encontrei contexto relevante para responder.",
            citations=[],
        )

    try:
        answer = generate_answer(payload.question, rows)
    except OpenAIError as exc:
        raise HTTPException(status_code=503, detail=f"LLM provider unavailable: {exc}") from exc

    citations = [
        RetrievedChunk(
            chunk_id=item["chunk_id"],
            source=item["source"],
            row_index=item["row_index"],
            content=item["content"],
            score=item["score"],
        )
        for item in rows
    ]
    return ChatResponse(question=payload.question, answer=answer, citations=citations)
