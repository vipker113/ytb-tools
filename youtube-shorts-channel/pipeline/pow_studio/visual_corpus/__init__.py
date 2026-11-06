#!/usr/bin/env python3
"""
Studio v9 Local Visual Corpus (`pow_studio.visual_corpus`).

Provides `$0` local semantic visual search over `assets/raw_footage/` on Apple Silicon (`mps`)
or CPU, scene-cut-aware clip windowing, provenance-gated indexing, hybrid visual+metadata
percentile retrieval with MMR diversification, cross-episode usage ledger penalties, and
gold-set recall benchmarking.

All heavy ML dependencies (`torch`, `transformers`) are lazy-imported so `pow_studio` works
unchanged when `requirements-ml.txt` is not installed.
"""

from __future__ import annotations

from .embedder import (
    DEFAULT_MODEL_ALIAS,
    MODEL_REGISTRY,
    HashMockEmbedder,
    HuggingFaceVisualEmbedder,
    VisualEmbedder,
    get_embedder,
    is_ml_available,
)

__all__ = [
    "DEFAULT_MODEL_ALIAS",
    "MODEL_REGISTRY",
    "HashMockEmbedder",
    "HuggingFaceVisualEmbedder",
    "VisualEmbedder",
    "get_embedder",
    "is_ml_available",
]
