"""Shared local embedding function for ChromaDB collections."""

from functools import lru_cache

from chromadb.utils import embedding_functions


@lru_cache(maxsize=1)
def get_embedding_function(model_name: str = "all-MiniLM-L6-v2"):
    """Load the Sentence Transformers embedding function once per process."""
    return embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model_name)
