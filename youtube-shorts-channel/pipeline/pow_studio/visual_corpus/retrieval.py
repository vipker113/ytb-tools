#!/usr/bin/env python3
"""
Hybrid visual + metadata percentile retrieval, MMR diversification, mislabel detection,
contact-strip generation, and online poster pre-screening (`pow_studio.visual_corpus.retrieval`).
"""

from __future__ import annotations

import io
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ..footage_sources.base import USER_AGENT
from ..media_classifier import GENUINE_MOVING_CLASSES
from .corpus import LoadedCorpus, default_corpus_dir, load_corpus, read_usage_ledger
from .embedder import DEFAULT_MODEL_ALIAS, VisualEmbedder, get_embedder


def compute_empirical_percentiles(scores: np.ndarray) -> np.ndarray:
    """
    Map raw similarity scores `(N,)` to `[0.0, 1.0]` empirical percentiles within the corpus.
    Invariant to model family logit temperature (CLIP ~0.25 vs SigLIP ~0.05).
    """
    n = int(scores.shape[0])
    if n == 0:
        return np.zeros((0,), dtype=np.float32)
    if n == 1:
        return np.ones((1,), dtype=np.float32)
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(n, dtype=np.float32)
    ranks[order] = np.arange(n, dtype=np.float32) / float(n - 1)
    return ranks


def _recent_hero_penalties(
    corpus_dir: Path,
    exclude_slug: Optional[str] = None,
    penalty_days: int = 30,
) -> tuple[set[str], dict[str, str]]:
    """Return `(penalized_canonical_ids, canonical_id -> last_slug)` for recent hero shots."""
    now = datetime.now(timezone.utc)
    penalized: set[str] = set()
    slug_by_canon: dict[str, str] = {}
    for row in read_usage_ledger(corpus_dir):
        slug = str(row.get("slug") or "")
        if not slug or slug == exclude_slug or not row.get("is_hero_shot"):
            continue
        ts_raw = str(row.get("rendered_at") or "")
        within_window = True
        if ts_raw and penalty_days > 0:
            try:
                dt = datetime.fromisoformat(ts_raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                within_window = (now - dt).days <= penalty_days
            except ValueError:
                within_window = True
        if within_window:
            cid = str(row.get("canonical_source_id") or row.get("local_file") or "")
            if cid:
                penalized.add(cid)
                slug_by_canon[cid] = slug
    return penalized, slug_by_canon


def search_corpus(
    query_text: str,
    top_k: int = 10,
    corpus: Optional[LoadedCorpus] = None,
    corpus_dir: Optional[Path] = None,
    model_alias: Optional[str] = None,
    embedder: Optional[VisualEmbedder] = None,
    metadata_tag_weight: float = 0.30,
    mmr_lambda: float = 0.30,
    genuine_only: bool = False,
    allowed_media_classes: Optional[set[str]] = None,
    min_height: int = 0,
    exclude_canonical_ids: Optional[set[str]] = None,
    current_episode_slug: Optional[str] = None,
    reuse_penalty_days: int = 30,
    require_commercial_license: bool = True,
) -> list[dict[str, Any]]:
    """
    Hybrid visual (`0.70`) + metadata (`0.30`) search with corpus-percentile normalization,
    commercial license gate, cross-episode hero-shot reuse penalty, and MMR diversification.
    """
    loaded = corpus or load_corpus(corpus_dir, model_alias=model_alias)
    if loaded.size == 0:
        return []

    active_alias = model_alias or loaded.meta.get("model_alias", DEFAULT_MODEL_ALIAS)
    emb_model = embedder or get_embedder(model_alias=active_alias)
    q_vec = emb_model.embed_texts([query_text])[0]  # (D,)

    vis_cos = loaded.embeddings @ q_vec
    tag_cos = loaded.tag_embeddings @ q_vec
    w_tag = float(np.clip(metadata_tag_weight, 0.0, 1.0))
    hybrid_raw = (1.0 - w_tag) * vis_cos + w_tag * tag_cos

    vis_pct = compute_empirical_percentiles(vis_cos)
    hyb_pct = compute_empirical_percentiles(hybrid_raw)

    penalized_canons, hero_slug_by_canon = _recent_hero_penalties(
        loaded.corpus_dir,
        exclude_slug=current_episode_slug,
        penalty_days=reuse_penalty_days,
    )
    excl = exclude_canonical_ids or set()

    eligible_indices: list[int] = []
    eff_scores = np.zeros(loaded.size, dtype=np.float32)

    for idx, rec in enumerate(loaded.records):
        if require_commercial_license and rec.get("license_status") not in ("verified", "declared"):
            continue
        mcls = str(rec.get("source_media_class") or "")
        if genuine_only and mcls not in GENUINE_MOVING_CLASSES:
            continue
        if allowed_media_classes and mcls not in allowed_media_classes:
            continue
        if min_height > 0 and int(rec.get("height") or 0) < min_height:
            continue
        canon_id = str(rec.get("canonical_source_id") or rec.get("local_file") or "")
        if canon_id in excl:
            continue

        score = 0.65 * float(hyb_pct[idx]) + 0.35 * float(vis_pct[idx])
        if mcls == "INFOGRAPHIC" and (not allowed_media_classes or "INFOGRAPHIC" not in allowed_media_classes):
            score -= 0.22
        if canon_id in penalized_canons:
            score -= 0.08
        eff_scores[idx] = score
        eligible_indices.append(idx)

    if not eligible_indices:
        return []

    # Pre-filter top pool before MMR (up to max(60, 6 * top_k)) for speed
    pool_limit = max(60, 6 * max(1, int(top_k)))
    eligible_indices.sort(key=lambda i: float(eff_scores[i]), reverse=True)
    pool = eligible_indices[:pool_limit]

    lam = float(np.clip(mmr_lambda, 0.0, 0.95))
    selected: list[int] = []
    selected_canons: set[str] = set()
    remaining = list(pool)

    while remaining and len(selected) < max(1, int(top_k)):
        if not selected or lam <= 1e-4:
            best_i = remaining[0]
        else:
            sel_embs = loaded.embeddings[selected]  # (S, D)
            best_i = remaining[0]
            best_mmr = -1e9
            for cand_i in remaining:
                sim_to_sel = float(np.max(sel_embs @ loaded.embeddings[cand_i]))
                sim_norm = max(0.0, sim_to_sel)
                same_canon_pen = (
                    0.10
                    if str(loaded.records[cand_i].get("canonical_source_id") or "") in selected_canons
                    else 0.0
                )
                mmr_val = (1.0 - lam) * float(eff_scores[cand_i]) - lam * sim_norm - same_canon_pen
                if mmr_val > best_mmr:
                    best_mmr = mmr_val
                    best_i = cand_i

        selected.append(best_i)
        selected_canons.add(str(loaded.records[best_i].get("canonical_source_id") or ""))
        remaining.remove(best_i)

    results: list[dict[str, Any]] = []
    for rank, idx in enumerate(selected, start=1):
        rec = loaded.records[idx]
        canon_id = str(rec.get("canonical_source_id") or rec.get("local_file") or "")
        results.append(
            {
                "rank": rank,
                "window_id": rec["window_id"],
                "local_file": rec["local_file"],
                "rel_path": rec["rel_path"],
                "start_s": rec["start_s"],
                "end_s": rec["end_s"],
                "duration_s": rec["duration_s"],
                "source_media_class": rec["source_media_class"],
                "is_real_moving_footage": rec["is_real_moving_footage"],
                "license": rec.get("license", ""),
                "license_status": rec.get("license_status", "unknown"),
                "canonical_source_id": canon_id,
                "thumb_rel": rec.get("thumb_rel", ""),
                "visual_cosine": round(float(vis_cos[idx]), 4),
                "tag_cosine": round(float(tag_cos[idx]), 4),
                "hybrid_cosine": round(float(hybrid_raw[idx]), 4),
                "visual_percentile": round(float(vis_pct[idx]), 4),
                "hybrid_percentile": round(float(hyb_pct[idx]), 4),
                "effective_score": round(float(eff_scores[idx]), 4),
                "recent_hero_reuse_slug": hero_slug_by_canon.get(canon_id),
                "metadata_text": rec.get("metadata_text", ""),
            }
        )
    return results


def lookup_file_visual_scores(
    query_text: str,
    corpus: Optional[LoadedCorpus] = None,
    corpus_dir: Optional[Path] = None,
    model_alias: Optional[str] = None,
    embedder: Optional[VisualEmbedder] = None,
    metadata_tag_weight: float = 0.30,
) -> dict[str, dict[str, Any]]:
    """
    Compute per-`local_file` best matching window scores (`visual_percentile`, `hybrid_percentile`,
    `best_window_id`, `start_s`, `end_s`, `thumb_rel`) across licensed corpus entries.
    """
    loaded = corpus or load_corpus(corpus_dir, model_alias=model_alias)
    if loaded.size == 0:
        return {}

    active_alias = model_alias or loaded.meta.get("model_alias", DEFAULT_MODEL_ALIAS)
    emb_model = embedder or get_embedder(model_alias=active_alias)
    q_vec = emb_model.embed_texts([query_text])[0]

    vis_cos = loaded.embeddings @ q_vec
    tag_cos = loaded.tag_embeddings @ q_vec
    w_tag = float(np.clip(metadata_tag_weight, 0.0, 1.0))
    hyb_raw = (1.0 - w_tag) * vis_cos + w_tag * tag_cos

    vis_pct = compute_empirical_percentiles(vis_cos)
    hyb_pct = compute_empirical_percentiles(hyb_raw)

    by_file: dict[str, dict[str, Any]] = {}
    for idx, rec in enumerate(loaded.records):
        if rec.get("license_status") not in ("verified", "declared"):
            continue
        lf = str(rec.get("local_file") or "")
        if not lf:
            continue
        vp = float(vis_pct[idx])
        cur = by_file.get(lf)
        if cur is None or vp > cur["visual_percentile"]:
            by_file[lf] = {
                "local_file": lf,
                "window_id": rec["window_id"],
                "start_s": rec["start_s"],
                "end_s": rec["end_s"],
                "thumb_rel": rec.get("thumb_rel", ""),
                "source_media_class": rec["source_media_class"],
                "visual_cosine": round(float(vis_cos[idx]), 4),
                "visual_percentile": round(vp, 4),
                "hybrid_percentile": round(float(hyb_pct[idx]), 4),
            }
    return by_file


def render_beat_matches_contact_strip(
    beat_rows: list[dict[str, Any]],
    corpus_dir: Path,
    out_path: Path,
) -> Optional[Path]:
    """
    Render a visual audit contact strip (`planning/beat_matches_strip.jpg`) showing each beat's
    Text Top-1 vs Visual Corpus Top-1 thumbnail and highlighting disagreements / mislabel flags.
    """
    if not beat_rows:
        return None

    cell_w, cell_h = 280, 168
    pad = 14
    header_h = 46
    row_h = cell_h + 44
    width = pad * 3 + cell_w * 2 + 380
    height = header_h + pad + len(beat_rows) * row_h

    canvas = Image.new("RGB", (width, max(120, height)), (14, 18, 26))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()

    draw.text((pad, 14), "STUDIO V9 BEAT MATCH AUDIT — TEXT TOP-1 vs VISUAL CORPUS TOP-1", fill=(235, 242, 255), font=font)

    def _load_thumb(thumb_rel: str) -> Image.Image:
        if thumb_rel:
            p = corpus_dir / thumb_rel
            if p.exists():
                try:
                    with Image.open(p) as im:
                        return im.convert("RGB").resize((cell_w, cell_h), Image.Resampling.BILINEAR)
                except Exception:
                    pass
        ph = Image.new("RGB", (cell_w, cell_h), (34, 40, 52))
        d = ImageDraw.Draw(ph)
        d.text((16, cell_h // 2 - 6), "No corpus thumbnail", fill=(150, 160, 175), font=font)
        return ph

    for r_idx, row in enumerate(beat_rows):
        y0 = header_h + r_idx * row_h
        disagree = bool(row.get("disagreement"))
        mislabel = bool(row.get("possible_mislabeled_asset"))
        border_col = (235, 85, 85) if mislabel else ((245, 190, 66) if disagree else (62, 180, 120))

        t_im = _load_thumb(str(row.get("text_top_thumb_rel") or ""))
        v_im = _load_thumb(str(row.get("visual_top_thumb_rel") or ""))

        x_t = pad
        x_v = pad * 2 + cell_w
        x_info = pad * 3 + cell_w * 2

        canvas.paste(t_im, (x_t, y0))
        canvas.paste(v_im, (x_v, y0))
        draw.rectangle([x_t - 2, y0 - 2, x_t + cell_w + 1, y0 + cell_h + 1], outline=border_col, width=2)
        draw.rectangle([x_v - 2, y0 - 2, x_v + cell_w + 1, y0 + cell_h + 1], outline=(90, 165, 250), width=2)

        t_lbl = f"TEXT: {str(row.get('text_top_candidate') or 'None')[:34]} (vp={row.get('text_top_visual_pct', 'n/a')})"
        v_lbl = f"VIS : {str(row.get('visual_top_candidate') or 'None')[:34]} (vp={row.get('visual_top_pct', 'n/a')})"
        draw.text((x_t, y0 + cell_h + 6), t_lbl, fill=(220, 226, 238), font=font)
        draw.text((x_v, y0 + cell_h + 6), v_lbl, fill=(170, 214, 255), font=font)

        beat_line = f"{row.get('beat_id', '')} ({row.get('seg_id', '')})"
        status_tag = "MISLABEL SUSPECT" if mislabel else ("DISAGREE" if disagree else "AGREE")
        draw.text((x_info, y0 + 6), f"{beat_line} [{status_tag}]", fill=border_col, font=font)
        nar = str(row.get("narration_text") or "")
        for ln_i in range(4):
            seg = nar[ln_i * 52 : (ln_i + 1) * 52]
            if seg:
                draw.text((x_info, y0 + 28 + ln_i * 18), seg, fill=(205, 212, 224), font=font)
        q_str = str(row.get("beat_query") or "")[:52]
        draw.text((x_info, y0 + 112), f"Q: {q_str}", fill=(145, 160, 182), font=font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, format="JPEG", quality=85)
    return out_path


def _fetch_poster_image(url: str, timeout_s: float = 8.0) -> Optional[Image.Image]:
    if not url:
        return None
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read(4_000_000)
        return Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        return None


def rank_online_candidates_by_thumbnail(
    query_text: str,
    candidates: list[dict[str, Any]],
    embedder: Optional[VisualEmbedder] = None,
    model_alias: str = DEFAULT_MODEL_ALIAS,
    image_fetcher: Optional[Callable[[str], Optional[Image.Image]]] = None,
) -> list[dict[str, Any]]:
    """
    Pre-screen online discovery candidates before downloading full HD videos by embedding their
    poster/preview thumbnails (`preview_image_url`) against `query_text`.
    Candidates without reachable thumbnails keep neutral `thumbnail_visual_pct = 0.5`.
    """
    if not candidates:
        return []
    emb_model = embedder or get_embedder(model_alias=model_alias)
    fetcher = image_fetcher or _fetch_poster_image

    imgs: list[Image.Image] = []
    img_cand_idxs: list[int] = []
    for idx, c in enumerate(candidates):
        purl = str(c.get("preview_image_url") or "")
        if not purl:
            continue
        im = fetcher(purl)
        if im is not None:
            imgs.append(im)
            img_cand_idxs.append(idx)

    out = [dict(c) for c in candidates]
    for c in out:
        c["thumbnail_visual_cosine"] = None
        c["thumbnail_visual_pct"] = 0.5

    if imgs:
        q_vec = emb_model.embed_texts([query_text])[0]
        im_vecs = emb_model.embed_images(imgs, batch_size=16)
        cos = im_vecs @ q_vec
        pcts = compute_empirical_percentiles(cos) if len(imgs) > 1 else np.clip((cos + 0.1) / 0.4, 0.0, 1.0)
        for pos, c_idx in enumerate(img_cand_idxs):
            out[c_idx]["thumbnail_visual_cosine"] = round(float(cos[pos]), 4)
            out[c_idx]["thumbnail_visual_pct"] = round(float(pcts[pos]), 4)

    out.sort(
        key=lambda r: (
            float(r.get("thumbnail_visual_pct") or 0.5),
            int(r.get("height") or 0),
        ),
        reverse=True,
    )
    return out
