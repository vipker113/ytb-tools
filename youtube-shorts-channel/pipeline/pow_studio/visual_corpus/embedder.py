#!/usr/bin/env python3
"""
Model abstraction for `$0` open-weights multimodal embedding (`pow_studio.visual_corpus.embedder`).

Supports:
  - `clip-b32`   -> `openai/clip-vit-base-patch32` (default)
  - `siglip-b16` -> `google/siglip-base-patch16-224`
  - `clip-l14`   -> `openai/clip-vit-large-patch14`
  - `mock-hash`  -> deterministic NumPy-only embedder for offline unit tests (no Torch/network)

Device priority: `mps` -> `cuda` -> `cpu`.
Precision: `fp32` by default on `mps` to prevent half-precision NaNs; automatic batch-size
backoff and CPU fallback on memory pressure.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Optional, Protocol

import numpy as np
from PIL import Image

DEFAULT_MODEL_ALIAS = "clip-b32"

MODEL_REGISTRY: dict[str, dict[str, Any]] = {
    "clip-b32": {
        "hf_id": "openai/clip-vit-base-patch32",
        "family": "clip",
        "dim": 512,
        "max_length": 77,
    },
    "siglip-b16": {
        "hf_id": "google/siglip-base-patch16-224",
        "family": "siglip",
        "dim": 768,
        "max_length": 64,
    },
    "clip-l14": {
        "hf_id": "openai/clip-vit-large-patch14",
        "family": "clip",
        "dim": 768,
        "max_length": 77,
    },
}


def default_models_cache_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "assets" / "models" / "hf_cache"


def is_ml_available() -> tuple[bool, str]:
    """Return `(available, diagnostic_note)` without loading weights."""
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except ImportError as exc:
        return False, f"Optional ML group not installed ({exc}); install requirements-ml.txt"
    return True, "torch+transformers ready"


def _l2_normalize(arr: np.ndarray) -> np.ndarray:
    out = np.asarray(arr, dtype=np.float32)
    out = np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)
    if out.ndim == 1:
        norm = float(np.linalg.norm(out))
        return out / max(norm, 1e-8)
    norms = np.linalg.norm(out, axis=-1, keepdims=True)
    return out / np.maximum(norms, 1e-8)


class VisualEmbedder(Protocol):
    model_alias: str
    hf_id: str
    embed_dim: int
    device: str

    def embed_images(self, images: list[Image.Image], batch_size: int = 16) -> np.ndarray: ...
    def embed_texts(self, texts: list[str], batch_size: int = 32) -> np.ndarray: ...


class HashMockEmbedder:
    """
    Deterministic NumPy-only embedder used in offline unit tests so corpus indexing,
    crash recovery, MMR, and mislabel flags can be tested in <0.2s without GPU/network.
    Maps RGB quadrant colors + text tokens into a shared 64-D unit sphere.
    """

    def __init__(self, dim: int = 64) -> None:
        self.model_alias = "mock-hash"
        self.hf_id = "local/mock-hash-64"
        self.embed_dim = dim
        self.device = "cpu"

    def _token_vec(self, token: str) -> np.ndarray:
        digest = hashlib.sha256(token.lower().encode("utf-8")).digest()
        rng = np.random.default_rng(int.from_bytes(digest[:8], "little"))
        return rng.standard_normal(self.embed_dim).astype(np.float32)

    def embed_images(self, images: list[Image.Image], batch_size: int = 16) -> np.ndarray:
        if not images:
            return np.zeros((0, self.embed_dim), dtype=np.float32)
        rows: list[np.ndarray] = []
        for im in images:
            rgb = np.asarray(im.convert("RGB").resize((8, 8), Image.Resampling.BILINEAR), dtype=np.float32) / 255.0
            mean_rgb = rgb.mean(axis=(0, 1))
            vec = np.zeros(self.embed_dim, dtype=np.float32)
            # Map dominant color channels to synthetic semantic tokens ("red", "green", "blue", "dark", "bright")
            if mean_rgb[0] > mean_rgb[1] + 0.15 and mean_rgb[0] > mean_rgb[2] + 0.15:
                vec += 2.5 * self._token_vec("red") + 1.5 * self._token_vec("fire")
            elif mean_rgb[2] > mean_rgb[0] + 0.15 and mean_rgb[2] > mean_rgb[1] + 0.10:
                vec += 2.5 * self._token_vec("blue") + 1.5 * self._token_vec("ocean")
            elif mean_rgb[1] > mean_rgb[0] + 0.15 and mean_rgb[1] > mean_rgb[2] + 0.15:
                vec += 2.5 * self._token_vec("green") + 1.5 * self._token_vec("forest")
            if mean_rgb.mean() < 0.18:
                vec += 1.5 * self._token_vec("dark") + 1.2 * self._token_vec("abyss")
            elif mean_rgb.mean() > 0.80:
                vec += 1.5 * self._token_vec("bright") + 1.2 * self._token_vec("ice")
            flat = rgb.reshape(-1)
            vec[: min(self.embed_dim, flat.size)] += 0.35 * flat[: min(self.embed_dim, flat.size)]
            rows.append(vec)
        return _l2_normalize(np.stack(rows, axis=0))

    def embed_texts(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.embed_dim), dtype=np.float32)
        rows: list[np.ndarray] = []
        for t in texts:
            toks = re.findall(r"[a-z0-9]{2,}", (t or "").lower())
            if not toks:
                toks = ["empty"]
            vec = sum((self._token_vec(tok) for tok in toks), np.zeros(self.embed_dim, dtype=np.float32))
            rows.append(vec)
        return _l2_normalize(np.stack(rows, axis=0))


def _select_device(preferred: Optional[str] = None) -> str:
    import torch

    if preferred and preferred != "auto":
        return preferred
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _extract_feature_tensor(raw_out: Any) -> Any:
    """Unwrap tensor from HuggingFace `get_image_features` / `get_text_features` across versions."""
    import torch

    if isinstance(raw_out, torch.Tensor):
        return raw_out
    for attr in ("image_embeds", "text_embeds", "pooler_output", "last_hidden_state"):
        val = getattr(raw_out, attr, None)
        if isinstance(val, torch.Tensor):
            return val[:, 0, :] if val.ndim == 3 else val
    raise TypeError(f"Unsupported model feature output type: {type(raw_out)!r}")


class HuggingFaceVisualEmbedder:
    """Open-weights CLIP / SigLIP embedder running locally on `mps` or `cpu`."""

    def __init__(
        self,
        model_alias: str = DEFAULT_MODEL_ALIAS,
        device: Optional[str] = None,
        precision: str = "fp32",
        cache_dir: Optional[Path] = None,
    ) -> None:
        import torch
        from transformers import AutoModel, AutoProcessor

        spec = MODEL_REGISTRY.get(model_alias)
        if spec is None:
            raise ValueError(f"Unknown visual corpus model '{model_alias}'. Valid: {sorted(MODEL_REGISTRY)}")

        self.model_alias = model_alias
        self.hf_id = str(spec["hf_id"])
        self.family = str(spec["family"])
        self.embed_dim = int(spec["dim"])
        self.max_length = int(spec["max_length"])
        self.device = _select_device(device)
        self.precision = precision
        self.cache_dir = Path(cache_dir) if cache_dir else default_models_cache_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        torch_dtype = torch.float16 if (precision == "fp16" and self.device != "cpu") else torch.float32
        self._torch_dtype = torch_dtype
        self.processor = AutoProcessor.from_pretrained(self.hf_id, cache_dir=str(self.cache_dir))
        self.model = AutoModel.from_pretrained(
            self.hf_id,
            cache_dir=str(self.cache_dir),
            dtype=torch_dtype,
        )
        self.model.eval()
        self.model.to(self.device)

    def _clear_device_cache(self) -> None:
        import torch

        if self.device == "mps" and hasattr(torch, "mps"):
            try:
                torch.mps.empty_cache()
            except Exception:  # noqa: BLE001
                pass
        elif self.device == "cuda":
            torch.cuda.empty_cache()

    def _fallback_to_cpu(self) -> None:
        import torch

        self._clear_device_cache()
        self.device = "cpu"
        self._torch_dtype = torch.float32
        self.model = self.model.to(dtype=torch.float32, device="cpu")

    def embed_images(self, images: list[Image.Image], batch_size: int = 16) -> np.ndarray:
        import torch

        if not images:
            return np.zeros((0, self.embed_dim), dtype=np.float32)

        rgb_images = [im.convert("RGB") for im in images]
        cur_bs = max(1, int(batch_size))
        outputs: list[np.ndarray] = []
        idx = 0

        while idx < len(rgb_images):
            chunk = rgb_images[idx : idx + cur_bs]
            try:
                inputs = self.processor(images=chunk, return_tensors="pt")
                pixel_values = inputs["pixel_values"].to(device=self.device, dtype=self._torch_dtype)
                with torch.no_grad():
                    feats = _extract_feature_tensor(self.model.get_image_features(pixel_values=pixel_values))
                arr = feats.detach().to(dtype=torch.float32, device="cpu").numpy()
                if not np.isfinite(arr).all() and self.device != "cpu":
                    self._fallback_to_cpu()
                    continue
                outputs.append(arr)
                idx += len(chunk)
            except RuntimeError as exc:
                msg = str(exc).lower()
                if ("out of memory" in msg or "mps" in msg or "alloc" in msg) and cur_bs > 1:
                    cur_bs = max(1, cur_bs // 2)
                    self._clear_device_cache()
                    continue
                if self.device != "cpu":
                    self._fallback_to_cpu()
                    continue
                raise

        self._clear_device_cache()
        stacked = np.concatenate(outputs, axis=0)
        self.embed_dim = int(stacked.shape[-1])
        return _l2_normalize(stacked)

    def embed_texts(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        import torch

        if not texts:
            return np.zeros((0, self.embed_dim), dtype=np.float32)

        cleaned = [(t or "").strip() or "documentary footage" for t in texts]
        cur_bs = max(1, int(batch_size))
        outputs: list[np.ndarray] = []
        idx = 0

        while idx < len(cleaned):
            chunk = cleaned[idx : idx + cur_bs]
            try:
                padding_mode: Any = "max_length" if self.family == "siglip" else True
                inputs = self.processor(
                    text=chunk,
                    padding=padding_mode,
                    truncation=True,
                    max_length=self.max_length,
                    return_tensors="pt",
                )
                model_kwargs: dict[str, Any] = {"input_ids": inputs["input_ids"].to(self.device)}
                if "attention_mask" in inputs:
                    model_kwargs["attention_mask"] = inputs["attention_mask"].to(self.device)
                with torch.no_grad():
                    feats = _extract_feature_tensor(self.model.get_text_features(**model_kwargs))
                arr = feats.detach().to(dtype=torch.float32, device="cpu").numpy()
                if not np.isfinite(arr).all() and self.device != "cpu":
                    self._fallback_to_cpu()
                    continue
                outputs.append(arr)
                idx += len(chunk)
            except RuntimeError as exc:
                msg = str(exc).lower()
                if ("out of memory" in msg or "mps" in msg or "alloc" in msg) and cur_bs > 1:
                    cur_bs = max(1, cur_bs // 2)
                    self._clear_device_cache()
                    continue
                if self.device != "cpu":
                    self._fallback_to_cpu()
                    continue
                raise

        self._clear_device_cache()
        stacked = np.concatenate(outputs, axis=0)
        self.embed_dim = int(stacked.shape[-1])
        return _l2_normalize(stacked)


_EMBEDDER_CACHE: dict[tuple[str, str, str], VisualEmbedder] = {}


def get_embedder(
    model_alias: str = DEFAULT_MODEL_ALIAS,
    device: Optional[str] = None,
    precision: str = "fp32",
    cache_dir: Optional[Path] = None,
) -> VisualEmbedder:
    """Return a cached `VisualEmbedder` instance for `(model_alias, device, precision)`."""
    if model_alias == "mock-hash":
        return HashMockEmbedder()
    key = (model_alias, device or "auto", precision)
    if key not in _EMBEDDER_CACHE:
        _EMBEDDER_CACHE[key] = HuggingFaceVisualEmbedder(
            model_alias=model_alias,
            device=device,
            precision=precision,
            cache_dir=cache_dir,
        )
    return _EMBEDDER_CACHE[key]
