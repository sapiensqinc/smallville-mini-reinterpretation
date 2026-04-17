"""Embedding wrapper around Gemini's embedding model.

We cache embeddings in-memory keyed by the exact input text, so re-embedding
the same memory description during retrieval is free.
"""
from __future__ import annotations

import logging
import os

import numpy as np
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class Embedder:
    def __init__(self, model: str, api_key: str | None = None):
        api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set.")
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._cache: dict[str, np.ndarray] = {}

    def embed(self, text: str) -> np.ndarray:
        if text in self._cache:
            return self._cache[text]
        resp = self._client.models.embed_content(
            model=self._model,
            contents=text,
            config=types.EmbedContentConfig(task_type="SEMANTIC_SIMILARITY"),
        )
        # google-genai returns a list of ContentEmbedding objects
        embedding_values = resp.embeddings[0].values
        vec = np.array(embedding_values, dtype=np.float32)
        # normalize once, so downstream cosine sim is just a dot product
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        self._cache[text] = vec
        return vec

    @staticmethod
    def cosine(a: np.ndarray, b: np.ndarray) -> float:
        # assumes both already normalized
        return float(np.dot(a, b))
