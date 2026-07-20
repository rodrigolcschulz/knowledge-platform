from pathlib import Path
from typing import Any

from pypdf import PdfReader

from app.embeddings import embedding_service
from app.vectorstore import ensure_schema, insert_chunk, reset_source

_DOCLING_CONVERTER: Any | None = None
_DOCLING_UNAVAILABLE = False


def _extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    pages: list[str] = []
    for idx, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            pages.append(f"## Page {idx}\n\n{text}")
    return "\n\n".join(pages)


def _extract_text_like(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def _extract_with_docling(path: Path) -> str:
    # Optional dependency path for richer PDF/DOCX conversion when available.
    global _DOCLING_CONVERTER
    global _DOCLING_UNAVAILABLE

    if _DOCLING_UNAVAILABLE:
        return ""

    try:
        if _DOCLING_CONVERTER is None:
            from docling.document_converter import DocumentConverter

            _DOCLING_CONVERTER = DocumentConverter()
    except Exception:
        _DOCLING_UNAVAILABLE = True
        return ""

    try:
        result = _DOCLING_CONVERTER.convert(str(path))
        doc = result.document
        markdown = doc.export_to_markdown()
        return (markdown or "").strip()
    except Exception:
        return ""


def extract_document_text(path: Path, prefer_docling: bool = True) -> str:
    suffix = path.suffix.lower()

    if prefer_docling and suffix in {".pdf", ".docx"}:
        markdown = _extract_with_docling(path)
        if markdown:
            return markdown

    if suffix == ".pdf":
        return _extract_pdf_text(path)

    if suffix in {".txt", ".md", ".markdown"}:
        return _extract_text_like(path)

    return ""


def chunk_text(text: str, chunk_size: int = 1200, chunk_overlap: int = 150) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        return []

    chunks: list[str] = []
    start = 0
    step = max(1, chunk_size - chunk_overlap)

    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_size)
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(cleaned):
            break
        start += step

    return chunks


def ingest_documents(
    input_path: str,
    patterns: list[str] | None = None,
    prefer_docling: bool = True,
    chunk_size: int = 1200,
    chunk_overlap: int = 150,
) -> tuple[int, int]:
    base_path = Path(input_path)
    if not base_path.exists():
        raise FileNotFoundError(f"Input path not found: {input_path}")

    include_patterns = patterns or ["*.pdf", "*.txt", "*.md", "*.markdown"]

    files: list[Path] = []
    if base_path.is_file():
        files = [base_path]
    else:
        for pattern in include_patterns:
            files.extend(base_path.rglob(pattern))

    files = sorted({f.resolve() for f in files})

    ensure_schema(embedding_service.dimensions)

    indexed_chunks = 0
    indexed_docs = 0

    for file_path in files:
        source = file_path.name
        reset_source(source)

        text = extract_document_text(file_path, prefer_docling=prefer_docling)
        if not text:
            continue

        chunks = chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        if not chunks:
            continue

        indexed_docs += 1
        for idx, content in enumerate(chunks):
            embedding = embedding_service.embed(content)
            payload: dict[str, Any] = {
                "type": "document",
                "path": str(file_path),
                "chunk_index": idx,
            }
            insert_chunk(
                source=source,
                row_index=idx,
                content=content,
                payload=payload,
                embedding=embedding,
            )
            indexed_chunks += 1

    return indexed_docs, indexed_chunks
