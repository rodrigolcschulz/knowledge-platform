import json
import os
from typing import Any
from urllib import error, request

import gradio as gr

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
GRADIO_SERVER_NAME = os.getenv("GRADIO_SERVER_NAME", "127.0.0.1")
GRADIO_SERVER_PORT = int(os.getenv("GRADIO_SERVER_PORT", "7860"))
API_TIMEOUT_SECONDS = float(os.getenv("API_TIMEOUT_SECONDS", "900"))
DEFAULT_INPUT_PATH = "input"


def _post_json(path: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    url = f"{API_BASE_URL}{path}"
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url=url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=API_TIMEOUT_SECONDS) as response:
            data = response.read().decode("utf-8")
            parsed = json.loads(data) if data else {}
            return parsed, None
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return None, f"HTTP {exc.code} em {path}: {detail}"
    except error.URLError as exc:
        return None, f"Falha de conexao com API em {API_BASE_URL}: {exc.reason}"
    except TimeoutError:
        return None, (
            "Timeout ao chamar API. "
            f"Ajuste API_TIMEOUT_SECONDS (atual: {API_TIMEOUT_SECONDS:g}s) se a ingestao demorar mais."
        )
    except json.JSONDecodeError as exc:
        return None, f"Resposta invalida da API: {exc}"


def run_ingest(input_path: str, prefer_docling: bool, chunk_size: int, chunk_overlap: int) -> tuple[str, str]:
    payload: dict[str, Any] = {
        "input_path": input_path,
        "patterns": ["*.pdf", "*.txt", "*.md", "*.markdown"],
        "prefer_docling": bool(prefer_docling),
        "chunk_size": int(chunk_size),
        "chunk_overlap": int(chunk_overlap),
    }

    data, err = _post_json("/ingest/documents", payload)
    if err:
        return err, ""

    summary = (
        "Ingestao concluida com sucesso\n"
        f"Entrada: {data.get('input_path')}\n"
        f"Documentos indexados: {data.get('indexed_documents')}\n"
        f"Chunks indexados: {data.get('indexed_chunks')}"
    )
    return summary, json.dumps(data, ensure_ascii=False, indent=2)


def run_search(query: str, top_k: int) -> tuple[list[list[Any]], str]:
    payload = {"query": query, "top_k": int(top_k)}
    data, err = _post_json("/search", payload)
    if err:
        return [], err

    rows = []
    for item in data.get("results", []):
        rows.append(
            [
                item.get("chunk_id"),
                item.get("source"),
                item.get("row_index"),
                round(float(item.get("score", 0.0)), 4),
                item.get("content", "")[:260],
            ]
        )

    return rows, json.dumps(data, ensure_ascii=False, indent=2)


def run_chat(question: str, top_k: int) -> tuple[str, list[list[Any]], str]:
    payload = {"question": question, "top_k": int(top_k)}
    data, err = _post_json("/chat", payload)
    if err:
        return err, [], ""

    citations = []
    for item in data.get("citations", []):
        citations.append(
            [
                item.get("chunk_id"),
                item.get("source"),
                item.get("row_index"),
                round(float(item.get("score", 0.0)), 4),
            ]
        )

    return (
        data.get("answer", ""),
        citations,
        json.dumps(data, ensure_ascii=False, indent=2),
    )


with gr.Blocks(title="Knowledge Platform - Documents RAG Demo") as demo:
    gr.Markdown(
        "# Knowledge Platform - Demo Documents\n"
        "Interface simples para ingestao de PDF/TXT/MD, busca semantica e chat usando a API FastAPI."
    )
    gr.Markdown(f"API alvo: {API_BASE_URL}")
    gr.Markdown(f"Timeout de chamada API: {API_TIMEOUT_SECONDS:g}s")

    with gr.Tab("1) Ingest Documents"):
        ingest_input_path = gr.Textbox(value=DEFAULT_INPUT_PATH, label="Pasta ou arquivo de entrada")
        ingest_prefer_docling = gr.Checkbox(value=False, label="Preferir Docling para PDF/DOCX")
        ingest_chunk_size = gr.Slider(300, 3000, value=1200, step=50, label="Chunk size")
        ingest_chunk_overlap = gr.Slider(0, 1000, value=150, step=25, label="Chunk overlap")
        ingest_button = gr.Button("Ingerir documentos", variant="primary")
        ingest_summary = gr.Textbox(label="Resumo", lines=5)
        ingest_json = gr.Code(label="Resposta JSON", language="json")

        ingest_button.click(
            fn=run_ingest,
            inputs=[ingest_input_path, ingest_prefer_docling, ingest_chunk_size, ingest_chunk_overlap],
            outputs=[ingest_summary, ingest_json],
        )

    with gr.Tab("2) Search"):
        search_query = gr.Textbox(label="Consulta", placeholder="Ex: cargos que usam mais python")
        search_top_k = gr.Slider(1, 20, value=5, step=1, label="Top K")
        search_button = gr.Button("Buscar", variant="primary")
        search_table = gr.Dataframe(
            headers=["chunk_id", "source", "row_index", "score", "content_preview"],
            datatype=["number", "str", "number", "number", "str"],
            wrap=True,
            label="Resultados",
        )
        search_json = gr.Code(label="Resposta JSON", language="json")

        search_button.click(
            fn=run_search,
            inputs=[search_query, search_top_k],
            outputs=[search_table, search_json],
        )

    with gr.Tab("3) Chat"):
        chat_question = gr.Textbox(
            label="Pergunta",
            placeholder="Ex: quais padroes aparecem entre cargo e tempo de experiencia?",
        )
        chat_top_k = gr.Slider(1, 20, value=5, step=1, label="Top K")
        chat_button = gr.Button("Perguntar", variant="primary")
        chat_answer = gr.Textbox(label="Resposta", lines=8)
        chat_citations = gr.Dataframe(
            headers=["chunk_id", "source", "row_index", "score"],
            datatype=["number", "str", "number", "number"],
            wrap=True,
            label="Citacoes",
        )
        chat_json = gr.Code(label="Resposta JSON", language="json")

        chat_button.click(
            fn=run_chat,
            inputs=[chat_question, chat_top_k],
            outputs=[chat_answer, chat_citations, chat_json],
        )


if __name__ == "__main__":
    demo.launch(server_name=GRADIO_SERVER_NAME, server_port=GRADIO_SERVER_PORT)
