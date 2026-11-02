#!/usr/bin/env python3
"""
Top-0.5% YouTube Shorts Script, Prosody & Anti-AI Smell Linter (`pow_studio.script_linter`).

Evaluates episode narration before rendering to eliminate classic "AI / ChatGPT / Wikipedia"
tells and enforce high-retention documentary Shorts storytelling:
1. Blocks/flags LLM stock transitions & throat-clearing clichés ("Still, there's an important caveat",
   "Moreover", "It's worth noting", "delve", "tapestry", "testament to", etc.).
2. Enforces spoken breathability (short active sentences, zero 4-term Latin taxonomy lists that
   make TTS sound robotic).
3. Verifies 0–2.5s cold-open paradox hook tightness (<= 16 words in N01).
4. Enforces dynamic human prosody variation (flags flat +0% / +0Hz across all segments).
5. Enforces tight seamless-loop ending cadence (<= 0.55s tail silence instead of 1.4s dead air
   that kills YouTube Shorts auto-replay retention).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .schema import EpisodeManifest
    from .style_profile import DocumentaryStyleProfile


# Phrases that immediately betray LLM-written / corporate-essay scripts on YouTube Shorts
AI_SMELL_PHRASES: list[tuple[str, str]] = [
    (r"\bimportant caveat\b", "Academic/LLM cliché ('important caveat'); state the scientific nuance directly in conversational speech."),
    (r"\bit(?:'s| is) worth noting\b", "LLM filler ('it's worth noting'); cut directly to the fact."),
    (r"\bmoreover\b|\bfurthermore\b|\bin addition\b", "Essay transition ('moreover/furthermore'); never used in natural spoken storytelling."),
    (r"\bdelve(?:s|d)?\b|\btapestry\b|\btestament to\b|\bunderscores?\b", "High-frequency ChatGPT vocabulary tell."),
    (r"\bin conclusion\b|\bto sum up\b|\ball in all\b", "School-essay sign-off; end on a sharp visual/emotional payoff that loops into 0.0s."),
    (r"\bscientists have long been baffled\b|\bbaffled scientists for decades\b", "Tabloid AI-slop cliché; state the concrete physical mystery instead."),
    (r"\bbuckle up\b|\blet(?:'s| us) dive in\b|\bwithout further ado\b", "Generic AI YouTuber filler."),
]


def _count_syllables_approx(word: str) -> int:
    clean = re.sub(r"[^a-z]", "", word.lower())
    if len(clean) <= 3:
        return 1 if clean else 0
    clean = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", clean)
    clean = re.sub(r"^y", "", clean)
    vowels = re.findall(r"[aeiouy]{1,2}", clean)
    return max(1, len(vowels))


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def audit_viral_shorts_script(
    manifest: "EpisodeManifest",
    style: "DocumentaryStyleProfile",
) -> dict[str, Any]:
    """
    Audit narration script, spoken rhythm, prosody diversity, and loop-ending tightness.
    Returns structured diagnostics (`errors`, `warnings`, `metrics`, `anti_ai_pass`).
    """
    errors: list[str] = []
    warnings: list[str] = []

    segs = list(manifest.narration_segments)
    full_text = " ".join(s.text.strip() for s in segs)
    all_words = [w for w in re.findall(r"[A-Za-z0-9'-]+", full_text) if w]
    total_words = len(all_words)

    # 1. LLM phrase / cliché scan
    llm_hits: list[str] = []
    for pattern, reason in AI_SMELL_PHRASES:
        m = re.search(pattern, full_text, flags=re.IGNORECASE)
        if m:
            hit_msg = f"AI-script tell '{m.group(0)}': {reason}"
            llm_hits.append(hit_msg)
            if style.viral_retention.block_ai_cliche_phrases:
                errors.append(hit_msg)
            else:
                warnings.append(hit_msg)

    # 2. Cold-open hook tightness (N01)
    hook_words = 0
    if segs:
        first_sentences = _split_sentences(segs[0].text)
        first_sentence = first_sentences[0] if first_sentences else segs[0].text
        hook_words = len(re.findall(r"[A-Za-z0-9'-]+", first_sentence))
        if hook_words > style.viral_retention.max_hook_first_sentence_words:
            warnings.append(
                f"Opening hook sentence is {hook_words} words (> {style.viral_retention.max_hook_first_sentence_words}); "
                "tighten first sentence so the core contradiction lands within 2.5 seconds."
            )

    # 3. Spoken sentence length & multisyllabic jargon cluster check
    long_sentences: list[str] = []
    jargon_clusters: list[str] = []
    max_sent_words = 0

    for seg in segs:
        for sent in _split_sentences(seg.text):
            words = re.findall(r"[A-Za-z0-9'-]+", sent)
            wc = len(words)
            max_sent_words = max(max_sent_words, wc)
            if wc > style.viral_retention.max_spoken_sentence_words:
                msg = f"[{seg.seg_id}] Sentence has {wc} words (> {style.viral_retention.max_spoken_sentence_words}): '{sent[:72]}...'"
                long_sentences.append(msg)
                warnings.append(msg)

            # Check dense academic/Latin multisyllabic lists (>= 4 heavy scientific terms in one sentence)
            heavy_terms = [
                w for w in words if (_count_syllables_approx(w) >= 4 or len(w) >= 11) and len(w) >= 9
            ]
            if len(heavy_terms) >= 4:
                msg = (
                    f"[{seg.seg_id}] Dense jargon cluster ({len(heavy_terms)} heavy terms: {', '.join(heavy_terms[:5])}) "
                    "will sound robotic in TTS; translate into vivid plain spoken English."
                )
                jargon_clusters.append(msg)
                if style.viral_retention.block_jargon_lists:
                    errors.append(msg)
                else:
                    warnings.append(msg)

    # 4. Prosody diversity (prevent flat +0% / +0Hz robotic monotone unless directed script or uploaded human voice is active)
    has_sentence_voice_direction = bool(
        manifest.voice_input_mode == "uploaded_narration"
        or (manifest.annotated_voice_script_file and Path(manifest.annotated_voice_script_file).exists())
        or any(s.delivery or s.pace for s in segs)
    )
    flat_segs = (
        0
        if has_sentence_voice_direction
        else sum(
            1
            for s in segs
            if s.rate.strip() in ("+0%", "0%", "-0%") and s.pitch.strip() in ("+0Hz", "0Hz", "-0Hz")
        )
    )
    flat_ratio = (flat_segs / float(len(segs))) if segs else 0.0
    if len(segs) >= 4 and flat_ratio > 0.65:
        warnings.append(
            f"{flat_segs}/{len(segs)} narration segments use flat (+0%, +0Hz) prosody; "
            "shape rate/pitch across hook, twist, nuance, and payoff for natural human cadence."
        )

    # 5. Seamless-loop tail pause audit (prevent 1.4s dead air at end of Short)
    tail_pause_s = float(segs[-1].pause_after_s) if segs else 0.0
    if tail_pause_s > style.viral_retention.max_ending_tail_pause_s:
        msg = (
            f"Final segment pause_after_s ({tail_pause_s:.2f}s) exceeds seamless-loop cap "
            f"({style.viral_retention.max_ending_tail_pause_s:.2f}s); dead air at the end triggers swipe-aways."
        )
        if style.viral_retention.enforce_seamless_loop_tail:
            errors.append(msg)
        else:
            warnings.append(msg)

    return {
        "total_words": total_words,
        "hook_first_sentence_words": hook_words,
        "max_sentence_words": max_sent_words,
        "llm_cliche_hits": len(llm_hits),
        "jargon_cluster_hits": len(jargon_clusters),
        "flat_prosody_ratio": round(flat_ratio, 3),
        "ending_tail_pause_s": round(tail_pause_s, 3),
        "anti_ai_script_pass": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }
