from sentence_transformers import SentenceTransformer

from app.config import settings


class EmbeddingService:
    def __init__(self) -> None:
        self._model = SentenceTransformer(settings.embedding_model)

    @property
    def dimensions(self) -> int:
        return self._model.get_sentence_embedding_dimension()

    def embed(self, text: str) -> list[float]:
        vector = self._model.encode(text, normalize_embeddings=True)
        return vector.tolist()


embedding_service = EmbeddingService()
