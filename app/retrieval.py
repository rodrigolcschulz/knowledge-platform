from app.config import settings
from app.embeddings import embedding_service
from app.vectorstore import similarity_search


def search(query: str, top_k: int | None = None) -> list[dict]:
    k = top_k or settings.top_k
    query_embedding = embedding_service.embed(query)
    return similarity_search(query_embedding, top_k=k)
