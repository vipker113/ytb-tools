#!/usr/bin/env python3
"""
Gold-set benchmark for Studio v9 Visual Corpus (`pow_studio.visual_corpus.eval`).

Compares the v8 lexical token baseline against open-weights multimodal models (`clip-b32`,
`siglip-b16`, `clip-l14`) on both:
  1. `visual_desc` queries (direct visual description; carries mild hindsight optimism bias), and
  2. `narration_concept` queries (`associated_narration_concept` / spoken segment text — blind
     narration-to-footage retrieval without clip-title hints).
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np

from ..schema import EpisodeManifest
from .corpus import LoadedCorpus, default_corpus_dir, ensure_model_embeddings, load_corpus
from .embedder import VisualEmbedder, get_embedder

_STOP_TOKENS = {
    "the", "and", "for", "with", "from", "into", "under", "over", "that", "this",
    "these", "those", "their", "there", "where", "when", "what", "which", "while",
    "have", "has", "had", "were", "was", "are", "been", "being", "than", "then",
    "shot", "wide", "close", "medium", "video", "footage", "photo", "image",
}


def _tokenize(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{3,}", (text or "").lower()) if w not in _STOP_TOKENS}


@dataclass
class GoldQuery:
    query_id: str
    episode_slug: str
    shot_id: str
    src_file: str
    src_in: float
    shot_dur: float
    visual_desc: str
    narration_query: str


def build_gold_queries(
    manifest_paths: list[Path],
    indexed_files: set[str],
) -> list[GoldQuery]:
    """Extract ground-truth `(query -> src_file + [src_in, src_in + dur])` pairs from manifests."""
    gold: list[GoldQuery] = []
    seen_keys: set[tuple[str, str, float]] = set()

    for mp in sorted(manifest_paths):
        try:
            ep = EpisodeManifest.from_yaml(mp)
        except Exception:
            continue
        seg_map = {s.seg_id: s.text for s in ep.narration_segments}
        all_nar = [s.text for s in ep.narration_segments]

        for idx, sh in enumerate(ep.shots):
            if sh.src_file not in indexed_files:
                continue
            if sh.kind in ("diagram", "study_card"):
                continue
            dur = round(max(0.5, float(sh.end_s) - float(sh.start_s)), 2)
            dedup_key = (ep.slug, sh.src_file, round(float(sh.src_in), 1))
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            nar_q = (sh.associated_narration_concept or "").strip()
            if not nar_q and sh.associated_seg_id and sh.associated_seg_id in seg_map:
                nar_q = seg_map[sh.associated_seg_id]
            if not nar_q and all_nar:
                seg_idx = min(len(all_nar) - 1, int(round(idx * len(all_nar) / max(1, len(ep.shots)))))
                nar_q = all_nar[seg_idx]
            if not nar_q:
                nar_q = sh.story_beat or sh.visual_desc

            vdesc = (sh.visual_desc or "").strip()
            if len(vdesc) < 8:
                continue

            gold.append(
                GoldQuery(
                    query_id=f"{ep.slug}:{sh.sid}",
                    episode_slug=ep.slug,
                    shot_id=sh.sid,
                    src_file=sh.src_file,
                    src_in=float(sh.src_in),
                    shot_dur=dur,
                    visual_desc=vdesc,
                    narration_query=nar_q,
                )
            )
    return gold


def _is_window_hit(rec: dict[str, Any], g: GoldQuery, slack_s: float = 1.25) -> bool:
    if rec.get("local_file") != g.src_file:
        return False
    if rec.get("is_still"):
        return True
    ws = float(rec.get("start_s") or 0.0)
    we = float(rec.get("end_s") or 0.0)
    gs = max(0.0, g.src_in - slack_s)
    ge = g.src_in + g.shot_dur + slack_s
    return not (we < gs or ws > ge)


def _score_rankings(
    ranked_indices_per_query: list[list[int]],
    records: list[dict[str, Any]],
    gold: list[GoldQuery],
) -> dict[str, float]:
    if not gold:
        return {
            "queries": 0,
            "win_r1": 0.0,
            "win_r5": 0.0,
            "win_r10": 0.0,
            "win_mrr": 0.0,
            "file_r1": 0.0,
            "file_r5": 0.0,
            "file_r10": 0.0,
            "file_mrr": 0.0,
        }

    w1 = w5 = w10 = 0
    f1 = f5 = f10 = 0
    w_mrr = 0.0
    f_mrr = 0.0

    for q_idx, g in enumerate(gold):
        order = ranked_indices_per_query[q_idx]
        first_win_rank: Optional[int] = None
        for r_pos, doc_i in enumerate(order[:50], start=1):
            if _is_window_hit(records[doc_i], g):
                first_win_rank = r_pos
                break

        # Deduplicate by local_file for file-level recall
        seen_files: list[str] = []
        for doc_i in order:
            lf = str(records[doc_i].get("local_file") or "")
            if lf and lf not in seen_files:
                seen_files.append(lf)
                if len(seen_files) >= 50:
                    break

        first_file_rank: Optional[int] = None
        for r_pos, lf in enumerate(seen_files, start=1):
            if lf == g.src_file:
                first_file_rank = r_pos
                break

        if first_win_rank is not None:
            w_mrr += 1.0 / float(first_win_rank)
            if first_win_rank <= 1:
                w1 += 1
            if first_win_rank <= 5:
                w5 += 1
            if first_win_rank <= 10:
                w10 += 1

        if first_file_rank is not None:
            f_mrr += 1.0 / float(first_file_rank)
            if first_file_rank <= 1:
                f1 += 1
            if first_file_rank <= 5:
                f5 += 1
            if first_file_rank <= 10:
                f10 += 1

    n = float(len(gold))
    return {
        "queries": int(len(gold)),
        "win_r1": round(w1 / n, 4),
        "win_r5": round(w5 / n, 4),
        "win_r10": round(w10 / n, 4),
        "win_mrr": round(w_mrr / n, 4),
        "file_r1": round(f1 / n, 4),
        "file_r5": round(f5 / n, 4),
        "file_r10": round(f10 / n, 4),
        "file_mrr": round(f_mrr / n, 4),
    }


def _rank_token_baseline(queries: list[str], records: list[dict[str, Any]], eligible_mask: list[int]) -> list[list[int]]:
    doc_toks = [_tokenize(str(records[i].get("metadata_text") or "")) for i in eligible_mask]
    rankings: list[list[int]] = []
    for q in queries:
        qt = _tokenize(q)
        denom = float(max(1, len(qt)))
        scored: list[tuple[float, int]] = []
        for pos, doc_i in enumerate(eligible_mask):
            overlap = len(qt & doc_toks[pos]) / denom
            mcls = str(records[doc_i].get("source_media_class") or "")
            bonus = 0.02 if mcls == "REAL_VIDEO_ACTION" else 0.0
            scored.append((overlap + bonus, doc_i))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        rankings.append([doc_i for _, doc_i in scored])
    return rankings


def _rank_dense(
    queries: list[str],
    corpus: LoadedCorpus,
    embedder: VisualEmbedder,
    eligible_mask: list[int],
    tag_weight: float,
) -> list[list[int]]:
    q_mat = embedder.embed_texts(queries, batch_size=32)  # (Q, D)
    vis_sub = corpus.embeddings[eligible_mask]  # (E, D)
    tag_sub = corpus.tag_embeddings[eligible_mask]  # (E, D)
    sims = (1.0 - tag_weight) * (q_mat @ vis_sub.T) + tag_weight * (q_mat @ tag_sub.T)  # (Q, E)
    rankings: list[list[int]] = []
    for q_i in range(sims.shape[0]):
        order_sub = np.argsort(-sims[q_i], kind="mergesort")
        rankings.append([eligible_mask[int(k)] for k in order_sub])
    return rankings


def run_corpus_evaluation(
    manifest_paths: list[Path],
    models: list[str],
    corpus_dir: Optional[Path] = None,
    report_md_path: Optional[Path] = None,
    embedder_override: Optional[VisualEmbedder] = None,
) -> dict[str, Any]:
    """Run apples-to-apples gold-set evaluation across Token Baseline and multimodal models."""
    cdir = Path(corpus_dir).resolve() if corpus_dir else default_corpus_dir().resolve()
    base = load_corpus(cdir, repair_on_mismatch=True)
    if not base.records:
        raise RuntimeError(f"Corpus at {cdir} is empty; run corpus-ingest first.")

    eligible_mask = [
        i for i, r in enumerate(base.records) if r.get("license_status") in ("verified", "declared")
    ]
    indexed_files = {str(base.records[i]["local_file"]) for i in eligible_mask}
    gold = build_gold_queries(manifest_paths, indexed_files=indexed_files)

    vdesc_queries = [g.visual_desc for g in gold]
    nar_queries = [g.narration_query for g in gold]

    methods: dict[str, dict[str, Any]] = {}

    # 1. Lexical Token Baseline (current v8 approach)
    t0 = time.perf_counter()
    tok_vdesc = _score_rankings(_rank_token_baseline(vdesc_queries, base.records, eligible_mask), base.records, gold)
    tok_nar = _score_rankings(_rank_token_baseline(nar_queries, base.records, eligible_mask), base.records, gold)
    methods["token-baseline-v8"] = {
        "visual_desc": tok_vdesc,
        "narration_concept": tok_nar,
        "perf": {"query_eval_s": round(time.perf_counter() - t0, 3), "images_per_sec": None, "peak_rss_mb": None},
    }

    # 2. Dense Multimodal Models (both Pure Visual w=0.0 and Hybrid w=0.30)
    for m_alias in models:
        emb = embedder_override or get_embedder(model_alias=m_alias)
        m_corpus, perf = ensure_model_embeddings(cdir, model_alias=m_alias, embedder=emb)
        if not perf.get("images_per_sec"):
            import resource
            from PIL import Image

            sample_imgs: list[Image.Image] = []
            for rec in m_corpus.records[:64]:
                tp = cdir / str(rec.get("thumb_rel") or "")
                if tp.exists():
                    with Image.open(tp) as im:
                        sample_imgs.append(im.convert("RGB"))
            if sample_imgs:
                _ = emb.embed_images(sample_imgs[:4], batch_size=4)  # warmup
                tb0 = time.perf_counter()
                _ = emb.embed_images(sample_imgs, batch_size=24)
                dt = max(1e-4, time.perf_counter() - tb0)
                perf["images_per_sec"] = round(len(sample_imgs) / dt, 1)
                perf["peak_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024.0 * 1024.0), 1)

        t_q0 = time.perf_counter()
        pure_vdesc = _score_rankings(_rank_dense(vdesc_queries, m_corpus, emb, eligible_mask, tag_weight=0.0), m_corpus.records, gold)
        pure_nar = _score_rankings(_rank_dense(nar_queries, m_corpus, emb, eligible_mask, tag_weight=0.0), m_corpus.records, gold)
        hyb_vdesc = _score_rankings(_rank_dense(vdesc_queries, m_corpus, emb, eligible_mask, tag_weight=0.30), m_corpus.records, gold)
        hyb_nar = _score_rankings(_rank_dense(nar_queries, m_corpus, emb, eligible_mask, tag_weight=0.30), m_corpus.records, gold)
        perf_full = {**perf, "query_eval_s": round(time.perf_counter() - t_q0, 3), "device": emb.device}

        methods[f"{m_alias}:visual-only"] = {
            "model_alias": m_alias,
            "mode": "visual_only",
            "visual_desc": pure_vdesc,
            "narration_concept": pure_nar,
            "perf": perf_full,
        }
        methods[f"{m_alias}:hybrid-70-30"] = {
            "model_alias": m_alias,
            "mode": "hybrid",
            "visual_desc": hyb_vdesc,
            "narration_concept": hyb_nar,
            "perf": perf_full,
        }

    # Pick recommended model based on Hybrid File Recall@5 + Window Recall@5 on narration_concept + visual_desc
    best_hybrid_key = max(
        (k for k in methods if k.endswith(":hybrid-70-30")),
        key=lambda k: (
            0.55 * methods[k]["narration_concept"]["file_r5"]
            + 0.45 * methods[k]["visual_desc"]["win_r5"]
        ),
        default="token-baseline-v8",
    )
    recommended_model = methods[best_hybrid_key].get("model_alias", models[0] if models else "clip-b32")
    beats_baseline = (
        methods[best_hybrid_key]["visual_desc"]["file_r5"] > tok_vdesc["file_r5"]
        or methods[best_hybrid_key]["narration_concept"]["file_r5"] > tok_nar["file_r5"]
        or methods[best_hybrid_key]["visual_desc"]["win_r5"] > tok_vdesc["win_r5"]
    )

    summary = {
        "gold_queries_count": len(gold),
        "licensed_windows_evaluated": len(eligible_mask),
        "unique_licensed_files": len(indexed_files),
        "recommended_model": recommended_model,
        "recommended_method": best_hybrid_key,
        "exceeds_token_baseline": beats_baseline,
        "methods": methods,
    }

    (cdir / "corpus_eval.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    if report_md_path is not None:
        md = _format_eval_markdown(summary)
        report_md_path.parent.mkdir(parents=True, exist_ok=True)
        report_md_path.write_text(md, encoding="utf-8")

    return summary


def _format_eval_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Studio v9 Visual Corpus Benchmark (`docs/v9_corpus_eval.md`)",
        "",
        "## 1. Evaluation Setup & Bias Disclosure",
        f"- **Licensed Corpus Windows Evaluated:** `{summary['licensed_windows_evaluated']}` across `{summary['unique_licensed_files']}` licensed files (`license_status in {{verified, declared}}`).",
        f"- **Gold Shot Queries:** `{summary['gold_queries_count']}` deduplicated `(episode, src_file, src_in)` shots from production manifests.",
        "- **Query Suites:**",
        "  1. **`visual_desc`** — shot visual description from YAML. *Bias note:* authored after an editor/agent inspected the footage, so absolute scores carry mild optimism bias.",
        "  2. **`narration_concept`** — spoken narration concept (`associated_narration_concept` / segment text). Tests blind **narration-to-pixels** retrieval before clip selection.",
        "- **Recommended Configuration:** "
        f"`{summary['recommended_method']}` (`exceeds_token_baseline={summary['exceeds_token_baseline']}`).",
        "",
        "## 2. Suite A — `visual_desc` Queries (Window & File Recall)",
        "",
        "| Method | Win R@1 | Win R@5 | Win R@10 | Win MRR | File R@1 | File R@5 | File R@10 | File MRR |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, m in summary["methods"].items():
        s = m["visual_desc"]
        lines.append(
            f"| `{name}` | {s['win_r1']:.3f} | **{s['win_r5']:.3f}** | {s['win_r10']:.3f} | {s['win_mrr']:.3f} "
            f"| {s['file_r1']:.3f} | **{s['file_r5']:.3f}** | {s['file_r10']:.3f} | {s['file_mrr']:.3f} |"
        )

    lines.extend(
        [
            "",
            "## 3. Suite B — Blind `narration_concept` Queries (Window & File Recall)",
            "",
            "| Method | Win R@1 | Win R@5 | Win R@10 | Win MRR | File R@1 | File R@5 | File R@10 | File MRR |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for name, m in summary["methods"].items():
        s = m["narration_concept"]
        lines.append(
            f"| `{name}` | {s['win_r1']:.3f} | **{s['win_r5']:.3f}** | {s['win_r10']:.3f} | {s['win_mrr']:.3f} "
            f"| {s['file_r1']:.3f} | **{s['file_r5']:.3f}** | {s['file_r10']:.3f} | {s['file_mrr']:.3f} |"
        )

    lines.extend(
        [
            "",
            "## 4. Apple M2 Pro (`mps`, 16 GB RAM) Throughput & Memory",
            "",
            "| Method | Device | Throughput (img/s) | Peak RSS (MB) | Query Eval Time (s) |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for name, m in summary["methods"].items():
        p = m.get("perf") or {}
        ips = f"{p['images_per_sec']:.1f}" if p.get("images_per_sec") else "—"
        rss = f"{p['peak_rss_mb']:.1f}" if p.get("peak_rss_mb") else "—"
        dev = p.get("device") or "cpu"
        lines.append(f"| `{name}` | `{dev}` | {ips} | {rss} | {p.get('query_eval_s', 0.0):.3f} |")

    lines.append("")
    return "\n".join(lines)
