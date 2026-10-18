"""Embeddings. Uses the organisers' model when R3_EMBED_MODEL points to it;
otherwise a dependency-free character n-gram embedder (clearly reported in the UI)."""
import hashlib
import os
import re
import warnings
import zlib
from pathlib import Path

import numpy as np

from . import config

DIM = 4096


class HashingEmbedder:
    """Character 3/4-grams + words, hashed. Robust to typos; needs only numpy."""
    name = "fallback-hashing-ngram"

    @staticmethod
    def _features(text):
        words = re.sub(r"[^a-z0-9 ]", " ", text.lower()).split()
        for w in words:
            yield "w:" + w
            p = f" {w} "
            for n in (3, 4):
                for i in range(len(p) - n + 1):
                    yield p[i:i + n]

    def encode(self, texts):
        M = np.zeros((len(texts), DIM), dtype=np.float32)
        for r, t in enumerate(texts):
            for f in self._features(t):
                M[r, zlib.crc32(f.encode()) % DIM] += 1.0
        M = np.log1p(M)
        n = np.linalg.norm(M, axis=1, keepdims=True)
        return M / np.maximum(n, 1e-9)


class SentenceTransformerEmbedder:
    def __init__(self, path):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(str(path), device="cpu")
        self.name = f"sentence-transformers:{Path(str(path)).name}"

    def encode(self, texts):
        v = self.model.encode(list(texts), batch_size=64, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(v, dtype=np.float32)


def get_embedder():
    path = os.getenv("R3_EMBED_MODEL")
    if path:
        try:
            return SentenceTransformerEmbedder(path)
        except Exception as e:  # loud, never silent
            warnings.warn(f"Could not load embedding model at {path!r} ({e}). Using fallback embedder.")
    return HashingEmbedder()


def encode_cached(embedder, texts, cache_key: str):
    """Embedding 5,000 products is slow once; cache the matrix on disk."""
    config.CACHE.mkdir(exist_ok=True)
    key = hashlib.sha1(f"{embedder.name}|{cache_key}|{len(texts)}".encode()).hexdigest()[:16]
    f = config.CACHE / f"emb_{key}.npy"
    if f.exists():
        return np.load(f)
    M = embedder.encode(texts)
    np.save(f, M)
    return M
