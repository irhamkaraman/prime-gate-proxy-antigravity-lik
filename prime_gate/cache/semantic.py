"""
Semantic Vector Embedding and Similarity Engine for Prime Gate.
Powered by FastEmbed (ONNX Runtime, CPU-only, ultra-lightweight memory footprint).
Supports multilingual models (Indonesian, English, 50+ languages) and prefix-aware
embedding for E5 family models ("query: " / "passage: ").
"""

import logging
import threading
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

logger = logging.getLogger("prime_gate.cache.semantic")

DEFAULT_MULTILINGUAL_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
FALLBACK_FAST_MODEL = "BAAI/bge-small-en-v1.5"


class SemanticVectorEngine:
    """
    High-performance vector embedding and cosine similarity engine.
    Defaults to FastEmbed's multilingual MiniLM (384 dimensions, ~117MB, ONNX CPU).
    Supports E5 family models with automatic 'query: ' and 'passage: ' prefix handling.
    """

    _lock = threading.Lock()
    _model_instance = None
    _init_attempted = False
    _model_name = DEFAULT_MULTILINGUAL_MODEL
    _model_dimension: Optional[int] = None

    @classmethod
    def set_model_name(cls, name: str) -> bool:
        """Configures the active embedding model name. Reinitializes if changed."""
        clean_name = (name or "").strip()
        if not clean_name:
            clean_name = DEFAULT_MULTILINGUAL_MODEL

        with cls._lock:
            if clean_name != cls._model_name:
                cls._model_name = clean_name
                cls._model_instance = None
                cls._init_attempted = False
                cls._model_dimension = None
                logger.info(f"Active embedding model changed to '{cls._model_name}'")
                return True
        return False

    @classmethod
    def get_model_name(cls) -> str:
        """Returns the currently configured model name."""
        return cls._model_name

    @classmethod
    def get_model(cls):
        """Lazy-loads and returns the singleton FastEmbed TextEmbedding instance."""
        if cls._model_instance is not None:
            return cls._model_instance

        with cls._lock:
            if cls._model_instance is not None:
                return cls._model_instance
            if cls._init_attempted and cls._model_instance is None:
                return None

            cls._init_attempted = True
            try:
                from fastembed import TextEmbedding
                logger.info(f"Loading FastEmbed model '{cls._model_name}'...")
                cls._model_instance = TextEmbedding(model_name=cls._model_name)
                logger.info(f"FastEmbed model '{cls._model_name}' loaded successfully.")
                return cls._model_instance
            except Exception as e:
                logger.warning(
                    f"FastEmbed model '{cls._model_name}' unavailable ({e}). "
                    f"Attempting fallback to '{FALLBACK_FAST_MODEL}'..."
                )
                try:
                    from fastembed import TextEmbedding
                    cls._model_instance = TextEmbedding(model_name=FALLBACK_FAST_MODEL)
                    cls._model_name = FALLBACK_FAST_MODEL
                    logger.info(f"Loaded fallback model '{FALLBACK_FAST_MODEL}'.")
                    return cls._model_instance
                except Exception as fallback_err:
                    logger.error(f"Fallback FastEmbed model also failed: {fallback_err}")
                    cls._model_instance = None
                    return None

    @classmethod
    def is_available(cls) -> bool:
        """Returns True if the semantic embedding model is ready for inference."""
        return cls.get_model() is not None

    @classmethod
    def get_embedding_dimension(cls) -> int:
        """Returns the vector dimension for the active model (default: 384)."""
        if cls._model_dimension is not None:
            return cls._model_dimension

        # Perform a dummy embedding of 1 word to detect dimension
        sample = cls.embed_text("probe", is_query=False)
        if sample is not None:
            cls._model_dimension = len(sample)
            return cls._model_dimension
        return 384

    @classmethod
    def apply_e5_prefix(cls, text: str, is_query: bool = False) -> str:
        """Applies E5-family prefixes ('query: ' or 'passage: ') if model requires it."""
        model_lower = cls._model_name.lower()
        if "e5" in model_lower:
            prefix = "query: " if is_query else "passage: "
            if not text.startswith(prefix):
                return f"{prefix}{text}"
        return text

    @classmethod
    def embed_text(cls, text: str, is_query: bool = False) -> Optional[np.ndarray]:
        """
        Generates a unit-normalized float32 vector for the input text.
        Applies E5 prefixes automatically if an E5 family model is configured.
        """
        clean_text = text.strip()
        if not clean_text:
            return None

        clean_text = cls.apply_e5_prefix(clean_text, is_query=is_query)

        model = cls.get_model()
        if model is None:
            return None

        try:
            embeddings = list(model.embed([clean_text]))
            if not embeddings:
                return None
            vec = np.array(embeddings[0], dtype=np.float32)
            # Normalize vector for instant cosine dot product
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            if cls._model_dimension is None:
                cls._model_dimension = len(vec)
            return vec
        except Exception as e:
            logger.error(f"Semantic embedding generation failed for '{clean_text[:40]}...': {e}")
            return None

    @classmethod
    def embed_query(cls, text: str) -> Optional[np.ndarray]:
        """Helper to embed incoming search query (applies 'query: ' prefix for E5)."""
        return cls.embed_text(text, is_query=True)

    @classmethod
    def embed_passage(cls, text: str) -> Optional[np.ndarray]:
        """Helper to embed cached document / prompt (applies 'passage: ' prefix for E5)."""
        return cls.embed_text(text, is_query=False)

    @staticmethod
    def vector_to_blob(vec: np.ndarray) -> bytes:
        """Serializes a float32 numpy vector into a compact binary BLOB."""
        return vec.astype(np.float32).tobytes()

    @staticmethod
    def blob_to_vector(blob: bytes) -> Optional[np.ndarray]:
        """Deserializes binary BLOB into a normalized float32 numpy vector."""
        if not blob:
            return None
        try:
            return np.frombuffer(blob, dtype=np.float32)
        except Exception as e:
            logger.error(f"Failed to deserialize vector BLOB: {e}")
            return None

    @classmethod
    def compute_similarity(cls, vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        """
        Computes cosine similarity between two unit-normalized vectors.
        For unit vectors, cosine similarity is simply the dot product.
        """
        return float(np.dot(vec_a, vec_b))

    @classmethod
    def find_best_semantic_match(
        cls,
        query_vec: np.ndarray,
        candidate_entries: List[Dict[str, Any]],
        threshold: float = 0.93,
    ) -> Optional[Tuple[Dict[str, Any], float]]:
        """
        Scans a list of candidate cache entries (with 'embedding' BLOB or np.ndarray).
        Finds the candidate with the highest cosine similarity >= threshold.

        Args:
            query_vec: Unit-normalized query vector.
            candidate_entries: List of dicts representing cached records with 'embedding'.
            threshold: Minimum cosine similarity score (0.0 to 1.0) to qualify as a Hit.

        Returns:
            Tuple of (best_matching_entry, similarity_score) or None.
        """
        if query_vec is None or not candidate_entries:
            return None

        best_entry = None
        best_score = -1.0

        for entry in candidate_entries:
            emb = entry.get("embedding")
            if emb is None:
                continue

            if isinstance(emb, (bytes, bytearray, memoryview)):
                cand_vec = cls.blob_to_vector(bytes(emb))
            elif isinstance(emb, np.ndarray):
                cand_vec = emb
            else:
                continue

            if cand_vec is None or len(cand_vec) != len(query_vec):
                continue

            # Dot product on unit-normalized vectors
            sim = float(np.dot(query_vec, cand_vec))
            if sim > best_score:
                best_score = sim
                best_entry = entry

        if best_entry is not None and best_score >= threshold:
            return best_entry, best_score

        return None
