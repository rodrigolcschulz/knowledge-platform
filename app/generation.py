from openai import OpenAI

from app.config import settings


def build_context(chunks: list[dict]) -> str:
    blocks: list[str] = []
    for c in chunks:
        blocks.append(
            f"[chunk_id={c['chunk_id']} row={c['row_index']} source={c['source']}]\n{c['content']}"
        )
    return "\n\n".join(blocks)


def fallback_answer(question: str, chunks: list[dict]) -> str:
    context_preview = "\n\n".join(chunk["content"][:260] for chunk in chunks[:3])
    return (
        "Resposta gerada sem provedor LLM configurado. "
        "Use OPENAI_API_KEY ou OPENAI_BASE_URL para respostas mais completas.\n\n"
        f"Pergunta: {question}\n\n"
        "Principais evidencias recuperadas:\n"
        f"{context_preview}"
    )


def generate_answer(question: str, chunks: list[dict]) -> str:
    if not settings.openai_api_key and not settings.openai_base_url:
        return fallback_answer(question, chunks)

    context = build_context(chunks)
    client_kwargs = {"api_key": settings.openai_api_key or "ollama"}
    if settings.openai_base_url:
        client_kwargs["base_url"] = settings.openai_base_url

    client = OpenAI(**client_kwargs)
    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "Voce e um assistente de analytics. "
                    "Responda apenas com base no contexto recuperado e cite as fontes "
                    "utilizando chunk_id e row. Se nao houver base suficiente, diga isso claramente."
                ),
            },
            {
                "role": "user",
                "content": f"Contexto:\n{context}\n\nPergunta:\n{question}",
            },
        ],
        temperature=0.1,
    )
    content = response.choices[0].message.content
    if isinstance(content, str):
        return content
    return "".join(part.text for part in content if hasattr(part, "text"))
