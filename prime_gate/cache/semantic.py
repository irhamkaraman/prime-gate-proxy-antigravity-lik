"""
Semantic Vector Embedding and Similarity Engine for Prime Gate.
Powered by FastEmbed (ONNX Runtime, CPU-only, ultra-lightweight memory footprint).
"""

import logging
import threading
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

logger = logging.getLogger("prime_gate.cache.semantic")


class SemanticVectorEngine:
    """
    High-performance vector embedding and cosine similarity engine.
    Uses FastEmbed's BAAI/bge-small-en-v1.5 model (384 dimensions, ~67MB, ONNX CPU).
    Provides microsecond cosine similarity calculation using normalized vector dot products.
    """

    _lock = threading.Lock()
    _model_instance = None
    _init_attempted = False
    _model_name = "BAAI/bge-small-en-v1.5"

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
                    f"FastEmbed model initialization unavailable ({e}). "
                    f"Semantic cache will gracefully fallback to Exact Hash matching."
                )
                cls._model_instance = None
                return None

    @classmethod
    def is_available(cls) -> bool:
        """Returns True if the semantic embedding model is ready for inference."""
        return cls.get_model() is not None

    @classmethod
    def embed_text(cls, text: str) -> Optional[np.ndarray]:
        """
        Generates a 384-dimensional normalized float32 vector for the input text.
        Returns None if text is empty or model is unavailable.
        """
        clean_text = text.strip()
        if not clean_text:
            return None

        model = cls.get_model()
        if model is None:
            return None

        try:
            # fastembed embed returns a generator of numpy arrays
            embeddings = list(model.embed([clean_text]))
            if not embeddings:
                return None
            vec = np.array(embeddings[0], dtype=np.float32)
            # Normalize vector for instant cosine similarity: cos(u, v) = u_norm . v_norm
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            return vec
        except Exception as e:
            logger.error(f"Semantic embedding generation failed: {e}")
            return None

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
            query_vec: Unit-normalized query vector (384-dim).
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
