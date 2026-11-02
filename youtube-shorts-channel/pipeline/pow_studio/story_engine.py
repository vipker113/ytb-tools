#!/usr/bin/env python3
"""
Stage 1 & Stage 2: Intelligent Documentary Storytelling, Topic Opportunity,
Opening Hook Optimization & Audience Retention Engine (`pow_studio.story_engine` v6.0).

Implements Part 2 (Sections 3.1-3.4) and Part 7 (Section 8) of the Proof of Wonder
Next-Generation Documentary Production Studio:
1. `evaluate_topic_opportunity()` — Multi-perspective topic assessment across 10 documentary
   criteria and multi-angle candidate ranking (balancing factual evidence, visual potential,
   narrative curiosity, and originality while penalizing unsupported sensationalism).
2. `evaluate_opening_hook_candidates()` — Evaluates multiple 1-3s opening hook concepts across
   clarity, visual impact, curiosity, factual accuracy, story relevance, and promise fulfillment.
3. `audit_narrative_momentum()` & `build_narrative_map()` — Reviews scripts for all 10 momentum
   failure modes (weak openings, unnecessary intros, repeated info, information droughts,
   premature explanations, unsupported dramatic claims, filler, weak transitions, unbuilt
   climaxes, and weak/CTA endings).
4. `generate_retention_plan()` — Produces a timestamped, duration-aware Retention Plan table
   anchored to actual story beats and configurable target duration (default 70-90s).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from .schema import EpisodeManifest, HookCandidateSpec
from .script_linter import AI_SMELL_PHRASES, _split_sentences
from .style_profile import DocumentaryStyleProfile

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
    "by", "from", "up", "into", "over", "under", "as", "is", "are", "was", "were", "be",
    "been", "being", "it", "its", "this", "that", "these", "those", "they", "them", "their",
    "what", "which", "who", "how", "when", "where", "why", "than", "then", "so", "not",
    "can", "could", "would", "may", "might", "also", "just", "even", "more", "most", "out",
}

GENERIC_INTRO_PATTERNS = [
    r"^\s*welcome\s+(?:back\s+)?to\b",
    r"\bproof\s+of\s+wonder\b",
    r"^\s*in\s+today'?s\s+video\b",
    r"^\s*today\s+we(?:'re|\s+are)\s+(?:going\s+to|exploring|looking\s+at)\b",
    r"^\s*have\s+you\s+ever\s+wondered\b",
    r"^\s*let'?s\s+talk\s+about\b",
]

GENERIC_OUTRO_CTA_PATTERNS = [
    r"\blike\s+and\s+subscribe\b",
    r"\bhit\s+(?:that\s+|the\s+)?subscribe\b",
    r"\bfollow\s+for\s+more\b",
    r"\bsmash\s+(?:that\s+|the\s+)?like\b",
    r"\bleave\s+a\s+comment\s+below\s+and\s+subscribe\b",
    r"\bdon'?t\s+forget\s+to\s+(?:like|subscribe|follow)\b",
]

UNSUPPORTED_SENSATIONAL_PATTERNS = [
    r"\bdefies\s+(?:all\s+)?(?:laws\s+of\s+)?physics\b",
    r"\b100%\s+unexplained\b",
    r"\bno\s+scientist\s+can\s+explain\b",
    r"\bproof\s+of\s+aliens\b",
    r"\bsupernatural\b",
    r"\bimpossible\s+according\s+to\s+science\b",
]

FILLER_INTENSIFIER_PATTERNS = [
    r"\btruly\s+(?:mind[- ]blowing|unbelievable|incredible)\b",
    r"\butterly\s+(?:bizarre|insane|shocking)\b",
    r"\bneedless\s+to\s+say\b",
    r"\bas\s+a\s+matter\s+of\s+fact\b",
    r"\bbasically\b",
]


@dataclass
class TopicAngleCandidate:
    angle_id: str
    title: str
    framing_summary: str
    archetype: str  # e.g., "visual_phenomenon", "scientific_discovery", "extreme_survival", "planetary_analog"
    surprise_level: float  # 0-10
    visual_reveal_strength: float  # 0-10
    familiarity_balance: float  # 0-10 (relatable entry point + unfamiliar mechanism)
    meaningful_mystery: float  # 0-10
    counterintuitive_fact: float  # 0-10
    unanswered_question: float  # 0-10
    scientific_explanation_value: float  # 0-10
    authentic_footage_feasibility: float  # 0-10
    credible_evidence_depth: float  # 0-10
    story_arc_completeness: float  # 0-10
    sensationalism_risk: float = 0.0  # 0-10 (higher = hype outruns evidence)
    notes: str = ""


@dataclass
class EvaluatedTopicAngle:
    angle_id: str
    title: str
    archetype: str
    framing_summary: str
    factual_evidence_score: float
    visual_potential_score: float
    narrative_interest_score: float
    originality_score: float
    sensationalism_penalty: float
    composite_score: float
    recommended: bool = False
    rationale: str = ""


def evaluate_topic_opportunity(
    topic_name: str,
    category: str,
    angles: list[TopicAngleCandidate],
) -> dict[str, Any]:
    """
    Evaluate a documentary topic across all 10 criteria and rank candidate angles.
    Selects the angle with the strongest combination of factual evidence (30%),
    visual potential (25%), narrative interest (25%), and originality (20%),
    explicitly penalizing sensationalism when evidence or authentic footage is weak.
    """
    if not angles:
        raise ValueError("Provide at least one TopicAngleCandidate for opportunity evaluation.")

    evaluated: list[EvaluatedTopicAngle] = []
    for a in angles:
        factual_ev = 0.55 * a.credible_evidence_depth + 0.45 * a.scientific_explanation_value
        visual_pot = 0.55 * a.visual_reveal_strength + 0.45 * a.authentic_footage_feasibility
        narrative_int = (
            0.30 * a.meaningful_mystery
            + 0.25 * a.surprise_level
            + 0.25 * a.story_arc_completeness
            + 0.20 * a.unanswered_question
        )
        originality = 0.55 * a.counterintuitive_fact + 0.45 * a.familiarity_balance

        # Penalize sensational angles whose hype exceeds credible evidence or real footage availability
        hype_gap = max(0.0, a.surprise_level - min(a.credible_evidence_depth, a.authentic_footage_feasibility))
        sens_pen = round(0.35 * a.sensationalism_risk + 0.25 * hype_gap, 3)

        composite = round(
            0.30 * factual_ev
            + 0.25 * visual_pot
            + 0.25 * narrative_int
            + 0.20 * originality
            - sens_pen,
            3,
        )
        evaluated.append(
            EvaluatedTopicAngle(
                angle_id=a.angle_id,
                title=a.title,
                archetype=a.archetype,
                framing_summary=a.framing_summary,
                factual_evidence_score=round(factual_ev, 2),
                visual_potential_score=round(visual_pot, 2),
                narrative_interest_score=round(narrative_int, 2),
                originality_score=round(originality, 2),
                sensationalism_penalty=round(sens_pen, 2),
                composite_score=composite,
                rationale=a.notes,
            )
        )

    evaluated.sort(key=lambda x: x.composite_score, reverse=True)
    evaluated[0].recommended = True
    winner = evaluated[0]

    return {
        "topic": topic_name,
        "category": category,
        "evaluated_angles_count": len(evaluated),
        "selected_angle_id": winner.angle_id,
        "selected_angle_title": winner.title,
        "selection_rationale": (
            f"Selected '{winner.title}' ({winner.archetype}) with composite score {winner.composite_score:.2f}/10 "
            f"(Evidence={winner.factual_evidence_score:.2f}, Visuals={winner.visual_potential_score:.2f}, "
            f"Narrative={winner.narrative_interest_score:.2f}, Originality={winner.originality_score:.2f}, "
            f"SensationalismPenalty=-{winner.sensationalism_penalty:.2f})."
        ),
        "angles": [asdict(e) for e in evaluated],
    }


def _content_tokens(text: str) -> set[str]:
    toks = [w.lower() for w in re.findall(r"[a-zA-Z0-9']+", text)]
    return {t for t in toks if len(t) >= 3 and t not in STOPWORDS}


def evaluate_opening_hook_candidates(
    manifest: EpisodeManifest,
    style: Optional[DocumentaryStyleProfile] = None,
) -> dict[str, Any]:
    """
    Evaluate multiple opening hook concepts (Section 8) based on:
    - Immediate clarity (1-3 seconds, concise syntax, zero channel-intro throat clearing)
    - Visual impact (authentic subject/motion on Frame 0)
    - Curiosity (concrete question, contrast, or physical paradox)
    - Factual accuracy (free of unsupported sensational claims)
    - Relevance to main story (token alignment with core episode body)
    - Promise fulfillment (fulfilled cleanly in later script segments)
    """
    style = style or manifest.resolve_style_profile()
    body_text = " ".join(s.text for s in manifest.narration_segments[1:])
    body_tokens = _content_tokens(body_text)
    seg_by_id = {s.seg_id: s.text for s in manifest.narration_segments}
    reg_by_file = {a.local_file: a for a in manifest.assets_register}

    candidates = list(manifest.hook_candidates)
    if not candidates and manifest.narration_segments:
        s0 = manifest.narration_segments[0]
        sh0 = manifest.shots[0] if manifest.shots else None
        candidates = [
            HookCandidateSpec(
                hook_id="H01",
                archetype=manifest.opening_hook_type,
                spoken_line=_split_sentences(s0.text)[0] if _split_sentences(s0.text) else s0.text,
                opening_visual=sh0.visual_desc if sh0 else "Opening documentary frame",
                src_file=sh0.src_file if sh0 else None,
                promise_fulfilled_in_seg_id=manifest.editorial_formula.layer2_pivot_seg_id,
                rationale="Primary manifest opening hook",
            )
        ]

    preferred_archs = set(style.narrative_retention.preferred_hook_archetypes)
    scored: list[dict[str, Any]] = []

    for c in candidates:
        words = re.findall(r"[A-Za-z0-9'-]+", c.spoken_line)
        wc = len(words)
        est_speak_s = round(wc / 2.65, 2)

        # 1. Immediate clarity (ideal 8-18 words, ~2.5-6.5s full sentence, core noun in first 3s)
        has_generic_intro = any(re.search(p, c.spoken_line, re.I) for p in GENERIC_INTRO_PATTERNS)
        clarity = 9.4
        if wc > style.viral_retention.max_hook_first_sentence_words:
            clarity -= min(3.5, 0.35 * (wc - style.viral_retention.max_hook_first_sentence_words))
        if wc < 5:
            clarity -= 1.8
        if has_generic_intro:
            clarity -= 4.5

        # 2. Visual impact (verified real asset + clear visual subject description)
        vis_impact = 7.5
        if c.src_file and c.src_file in reg_by_file:
            asset = reg_by_file[c.src_file]
            vis_impact = 9.4 if asset.media_type == "video" else (8.8 if asset.media_type == "photo" else 6.8)
        elif len(c.opening_visual.split()) >= 6:
            vis_impact = 8.4

        # 3. Curiosity (contrast, paradox, unexpected number/scale, or concrete mystery)
        curiosity = 7.4
        if c.archetype in preferred_archs:
            curiosity += 0.8
        if re.search(r"\b(?:but|yet|instead|straight out of|beneath|inside|without|never|nobody knew|why)\b", c.spoken_line, re.I):
            curiosity += 0.9
        if re.search(r"\d+|five-story|hundred|thousand|million|degree|meter|mile", c.spoken_line, re.I):
            curiosity += 0.6
        curiosity = min(9.8, curiosity)

        # 4. Factual accuracy (penalize clickbait / false suspense / unsupported absolutes)
        accuracy = 9.5
        if any(re.search(p, c.spoken_line, re.I) for p in UNSUPPORTED_SENSATIONAL_PATTERNS):
            accuracy -= 5.0
        if re.search(r"\byou won'?t believe\b|\bwait until the end\b|\bshocking secret\b", c.spoken_line, re.I):
            accuracy -= 4.0

        # 5. Story relevance (content token overlap with body narration)
        hook_toks = _content_tokens(c.spoken_line + " " + c.opening_visual)
        overlap = len(hook_toks & body_tokens) / float(max(1, min(len(hook_toks), 6)))
        relevance = min(9.8, 6.2 + 3.8 * min(1.0, overlap))

        # 6. Promise fulfillment (check target payoff segment exists and resolves topic)
        fulfill = 7.5
        if c.promise_fulfilled_in_seg_id and c.promise_fulfilled_in_seg_id in seg_by_id:
            payoff_toks = _content_tokens(seg_by_id[c.promise_fulfilled_in_seg_id] + " " + body_text)
            if len(hook_toks & payoff_toks) >= 1:
                fulfill = 9.5
            else:
                fulfill = 8.2

        total = round(
            0.22 * clarity
            + 0.20 * vis_impact
            + 0.20 * curiosity
            + 0.16 * accuracy
            + 0.12 * relevance
            + 0.10 * fulfill,
            2,
        )
        scored.append(
            {
                "hook_id": c.hook_id,
                "archetype": c.archetype,
                "spoken_line": c.spoken_line,
                "word_count": wc,
                "estimated_spoken_s": est_speak_s,
                "opening_visual": c.opening_visual,
                "src_file": c.src_file,
                "promise_fulfilled_in_seg_id": c.promise_fulfilled_in_seg_id,
                "scores": {
                    "immediate_clarity": round(max(0.0, clarity), 2),
                    "visual_impact": round(vis_impact, 2),
                    "curiosity": round(curiosity, 2),
                    "factual_accuracy": round(max(0.0, accuracy), 2),
                    "relevance_to_story": round(relevance, 2),
                    "promise_fulfillment": round(fulfill, 2),
                },
                "composite_hook_score": total,
                "rationale": c.rationale,
            }
        )

    scored.sort(key=lambda x: x["composite_hook_score"], reverse=True)
    if scored:
        scored[0]["recommended"] = True
    return {
        "slug": manifest.slug,
        "evaluated_count": len(scored),
        "recommended_hook_id": scored[0]["hook_id"] if scored else None,
        "recommended_score": scored[0]["composite_hook_score"] if scored else None,
        "candidates": scored,
    }


def _infer_beat_for_segment(idx: int, total: int, seg_id: str, manifest: EpisodeManifest) -> str:
    seg = manifest.narration_segments[idx]
    if seg.narrative_beat:
        return seg.narrative_beat
    if idx == 0:
        return "opening_hook"
    if idx == total - 1:
        return "final_impression"
    if seg_id == manifest.editorial_formula.layer2_pivot_seg_id:
        return "escalation"
    if seg_id == manifest.editorial_formula.scientific_caveat_seg_id:
        return "payoff"
    u = idx / float(max(1, total - 1))
    if u <= 0.26:
        return "curiosity_gap"
    if u <= 0.68:
        return "evidence_and_discovery"
    return "payoff"


def build_narrative_map(
    manifest: EpisodeManifest,
    wt: Optional[dict[str, Any]] = None,
    target_duration_s: Optional[float] = None,
) -> list[dict[str, Any]]:
    """
    Construct a section-by-section Narrative Map explaining the timing, narrative beat,
    viewer question, new information, visual reveal, emotional direction, and retention
    purpose of every script segment.
    """
    segs = manifest.narration_segments
    n = len(segs)
    wt_segs = {s["seg_id"]: s for s in (wt or {}).get("segments", [])}

    # Estimate timing when pre-TTS (`wt is None`)
    raw_ests: list[tuple[float, float]] = []
    cursor = 0.10
    for s in segs:
        wc = max(1, len(s.text.split()))
        dur = wc / 2.55
        raw_ests.append((cursor, cursor + dur))
        cursor += dur + s.pause_after_s

    scale = 1.0
    if not wt_segs and target_duration_s and cursor > 1.0:
        scale = float(target_duration_s) / cursor

    # Map shots overlapping each segment for visual reveal lookup
    manifest_total_s = manifest.shots[-1].end_s if manifest.shots else max(1.0, cursor * scale)

    default_emotions = {
        "opening_hook": "Immediate visual shock & curiosity",
        "curiosity_gap": "Intrigue & puzzled anticipation",
        "evidence_and_discovery": "Grounded investigative focus",
        "escalation": "Controlled surprise & deepening wonder",
        "payoff": "Intellectual clarity & scientific respect",
        "final_impression": "Lasting awe & seamless reflective resonance",
    }
    default_purposes = {
        "opening_hook": "Stop scroll within 1-3s with a verified anomaly and clear story promise",
        "curiosity_gap": "Establish the central 'how/why' question without giving away the deeper layer",
        "evidence_and_discovery": "Deliver progressive empirical observations and real fieldwork visuals",
        "escalation": "Pivot past the surface answer into a deeper, unexpected scientific clue",
        "payoff": "Resolve the core mystery honestly while qualifying what remains under study",
        "final_impression": "Leave a memorable scientific insight without weakening the ending via generic CTAs",
    }

    narrative_map: list[dict[str, Any]] = []
    for idx, seg in enumerate(segs):
        beat = _infer_beat_for_segment(idx, n, seg.seg_id, manifest)
        if seg.seg_id in wt_segs:
            t0 = float(wt_segs[seg.seg_id]["start"])
            t1 = float(wt_segs[seg.seg_id]["end"])
        else:
            t0 = round(raw_ests[idx][0] * scale, 2)
            t1 = round(raw_ests[idx][1] * scale, 2)

        # Find shots overlapping `[t0, t1]` normalized to manifest shot timeline
        total_ref = float(wt["total_duration_s"]) if (wt and wt.get("total_duration_s")) else (cursor * scale)
        u0 = t0 / max(1e-6, total_ref)
        u1 = t1 / max(1e-6, total_ref)
        ms0, ms1 = u0 * manifest_total_s, u1 * manifest_total_s
        matching_shots = [
            sh for sh in manifest.shots if max(sh.start_s, ms0) < min(sh.end_s, ms1 + 0.15)
        ]
        vis_rev = seg.visual_reveal or (
            "; ".join(f"{sh.sid}: {sh.visual_desc[:68]}" for sh in matching_shots[:2])
            if matching_shots
            else "Authentic documentary evidence"
        )

        viewer_q = seg.viewer_question
        if not viewer_q:
            if beat == "opening_hook":
                viewer_q = "Is this real, and how can this exist on Earth?"
            elif beat == "curiosity_gap":
                viewer_q = "What physical or biological mechanism produces this?"
            elif beat == "evidence_and_discovery":
                viewer_q = "How did scientists test and verify what is inside?"
            elif beat == "escalation":
                viewer_q = "Wait—what deeper clue was hiding beyond the obvious explanation?"
            elif beat == "payoff":
                viewer_q = "What does the evidence actually prove—and what remains open?"
            else:
                viewer_q = "What bigger truth about our planet or universe does this reveal?"

        new_info = seg.new_information or (_split_sentences(seg.text)[0] if _split_sentences(seg.text) else seg.text)

        narrative_map.append(
            {
                "seg_id": seg.seg_id,
                "start_s": round(t0, 2),
                "end_s": round(t1, 2),
                "time_window": f"{t0:.1f}–{t1:.1f}s",
                "narrative_beat": beat,
                "viewer_question": viewer_q,
                "new_information": new_info,
                "visual_reveal": vis_rev,
                "emotional_direction": seg.emotional_direction or default_emotions.get(beat, "Documentary focus"),
                "retention_purpose": seg.retention_purpose or default_purposes.get(beat, "Advance narrative momentum"),
                "text": seg.text,
            }
        )
    return narrative_map


def audit_narrative_momentum(
    manifest: EpisodeManifest,
    style: Optional[DocumentaryStyleProfile] = None,
    wt: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Review script structure and narrative momentum (Part 2, Section 3.3), detecting:
    1. Weak openings
    2. Unnecessary introductions (channel name / throat clearing)
    3. Repeated information across non-adjacent segments
    4. Long stretches without new concrete information (info droughts)
    5. Explanations that arrive too early without escalation
    6. Unsupported dramatic claims
    7. Unnecessary filler / AI clichés
    8. Weak transitions between story beats
    9. Climaxes without sufficient buildup
    10. Conclusions that fail to deliver payoff or use generic subscribe CTAs
    """
    style = style or manifest.resolve_style_profile()
    nmap = build_narrative_map(manifest, wt=wt)
    segs = manifest.narration_segments

    issues: list[dict[str, str]] = []
    warnings: list[str] = []
    errors: list[str] = []

    def _flag(severity: str, category: str, seg_id: str, detail: str) -> None:
        issues.append({"severity": severity, "category": category, "seg_id": seg_id, "detail": detail})
        msg = f"[{category}:{seg_id}] {detail}"
        if severity == "error":
            errors.append(msg)
        else:
            warnings.append(msg)

    if not segs:
        return {"momentum_pass": False, "errors": ["Empty narration_segments"], "warnings": [], "issues": [], "narrative_map": []}

    # 1 & 2. Opening hook strength & unnecessary introductions
    open_txt = segs[0].text.strip()
    if style.narrative_retention.forbid_generic_channel_intro:
        for pat in GENERIC_INTRO_PATTERNS:
            if re.search(pat, open_txt, re.I):
                _flag(
                    "error",
                    "unnecessary_introduction",
                    segs[0].seg_id,
                    f"Opening starts with generic intro/channel name ('{open_txt[:55]}...'); open immediately on the intriguing verified fact or visual.",
                )
                break

    first_sent = _split_sentences(open_txt)[0] if _split_sentences(open_txt) else open_txt
    first_wc = len(re.findall(r"[A-Za-z0-9'-]+", first_sent))
    if first_wc > style.viral_retention.max_hook_first_sentence_words + 4:
        _flag(
            "warning",
            "weak_opening",
            segs[0].seg_id,
            f"Opening sentence takes {first_wc} words before landing its hook; aim for <= {style.viral_retention.max_hook_first_sentence_words} words.",
        )

    # 3. Repeated information across non-adjacent segments
    seg_toks = [_content_tokens(s.text) for s in segs]
    for i in range(len(segs)):
        for j in range(i + 2, len(segs)):
            if len(seg_toks[i]) >= 5 and len(seg_toks[j]) >= 5:
                inter = seg_toks[i] & seg_toks[j]
                jacc = len(inter) / float(len(seg_toks[i] | seg_toks[j]))
                if jacc >= 0.42:
                    _flag(
                        "warning",
                        "repeated_information",
                        f"{segs[i].seg_id}->{segs[j].seg_id}",
                        f"High content overlap ({jacc:.0%}: {', '.join(sorted(inter)[:5])}) repeats earlier information.",
                    )

    # 4. Long stretches without concrete new information (numbers, mechanisms, or pivot cues)
    drought_acc_s = 0.0
    drought_start_seg = segs[0].seg_id
    for entry in nmap:
        dur_s = max(0.5, float(entry["end_s"]) - float(entry["start_s"]))
        txt = entry["text"]
        has_concrete_fact = bool(
            re.search(
                r"\d+|%|meter|mile|kilometer|year|century|decade|chem|iron|brine|microb|radar|sample|discover|oxidiz|pressur|temperatur|oxygen|planet|glacier|ocean",
                txt,
                re.I,
            )
        )
        if not has_concrete_fact:
            if drought_acc_s == 0.0:
                drought_start_seg = entry["seg_id"]
            drought_acc_s += dur_s
            if drought_acc_s > style.narrative_retention.max_info_drought_s:
                _flag(
                    "warning",
                    "information_drought",
                    f"{drought_start_seg}..{entry['seg_id']}",
                    f"Stretch of {drought_acc_s:.1f}s without concrete empirical facts or mechanisms (> {style.narrative_retention.max_info_drought_s:.1f}s).",
                )
        else:
            drought_acc_s = 0.0

    # 5 & 9. Premature explanation & climax without buildup
    total_dur = max(1.0, float(nmap[-1]["end_s"]))
    payoff_entries = [e for e in nmap if e["narrative_beat"] == "payoff"]
    escalation_entries = [e for e in nmap if e["narrative_beat"] == "escalation"]
    evidence_entries = [e for e in nmap if e["narrative_beat"] == "evidence_and_discovery"]

    if payoff_entries:
        first_payoff_frac = float(payoff_entries[0]["start_s"]) / total_dur
        if first_payoff_frac < style.narrative_retention.min_central_payoff_time_fraction and not escalation_entries:
            _flag(
                "warning",
                "premature_explanation",
                payoff_entries[0]["seg_id"],
                f"Central payoff arrives at {first_payoff_frac:.0%} of runtime with no subsequent escalation beat; viewers lose reason to keep watching.",
            )
        if not evidence_entries and not escalation_entries and len(segs) >= 4:
            _flag(
                "warning",
                "climax_without_buildup",
                payoff_entries[0]["seg_id"],
                "Payoff reached without preceding evidence_and_discovery or escalation beats.",
            )

    # 6 & 7. Unsupported dramatic claims & filler / AI clichés
    for s in segs:
        for pat in UNSUPPORTED_SENSATIONAL_PATTERNS:
            m = re.search(pat, s.text, re.I)
            if m:
                _flag(
                    "error",
                    "unsupported_dramatic_claim",
                    s.seg_id,
                    f"Unsupported sensational claim '{m.group(0)}' violates documentary scientific credibility.",
                )
        for pat in FILLER_INTENSIFIER_PATTERNS:
            m = re.search(pat, s.text, re.I)
            if m:
                _flag("warning", "unnecessary_filler", s.seg_id, f"Empty dramatic filler '{m.group(0)}'; replace with concrete evidence.")
        for pat, reason in AI_SMELL_PHRASES:
            m = re.search(pat, s.text, re.I)
            if m:
                _flag("error" if style.viral_retention.block_ai_cliche_phrases else "warning", "ai_cliche_filler", s.seg_id, f"'{m.group(0)}' — {reason}")

    # 8. Weak beat transitions (3+ consecutive segments starting with identical first word)
    starters = [re.findall(r"[A-Za-z']+", s.text)[0].lower() if re.findall(r"[A-Za-z']+", s.text) else "" for s in segs]
    for k in range(len(starters) - 2):
        if starters[k] and starters[k] == starters[k + 1] == starters[k + 2]:
            _flag(
                "warning",
                "weak_beat_transitions",
                segs[k + 2].seg_id,
                f"Three consecutive segments start with '{starters[k]}', creating repetitive mechanical transitions.",
            )

    # 10. Weak conclusion / generic subscribe CTA
    last_txt = segs[-1].text.strip()
    if style.narrative_retention.forbid_generic_subscribe_outro:
        for pat in GENERIC_OUTRO_CTA_PATTERNS:
            if re.search(pat, last_txt, re.I):
                _flag(
                    "error",
                    "weak_conclusion_generic_cta",
                    segs[-1].seg_id,
                    "Ending weakens final documentary impression with a generic like/subscribe/follow request.",
                )
                break

    return {
        "slug": manifest.slug,
        "style_profile": style.profile_name,
        "segment_count": len(segs),
        "estimated_or_actual_duration_s": round(total_dur, 2),
        "momentum_pass": len(errors) == 0,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
        "narrative_map": nmap,
    }


def generate_retention_plan(
    manifest: EpisodeManifest,
    wt: Optional[dict[str, Any]] = None,
    target_duration_s: Optional[float] = None,
    out_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """
    Generate the structured Audience Retention Plan (Part 2, Section 3.4) with exact columns:
    `| Time | Narrative beat | Viewer question | New information | Visual reveal | Emotional direction | Retention purpose |`
    """
    style = manifest.resolve_style_profile()
    if target_duration_s is None and wt is None:
        lo, hi = style.narrative_retention.default_target_duration_range_s
        # Respect episode target bounds when configured
        lo = max(lo, manifest.target_duration_min_s) if manifest.target_duration_min_s > 60 else manifest.target_duration_min_s
        hi = manifest.target_duration_max_s
        target_duration_s = None  # Use natural spoken duration unless caller requests scaling

    nmap = build_narrative_map(manifest, wt=wt, target_duration_s=target_duration_s)
    total_s = nmap[-1]["end_s"] if nmap else 0.0

    md_lines = [
        f"# Audience Retention Plan — `{manifest.slug}` (`{total_s:.1f}s` Target/Actual Runtime)",
        "",
        f"- **Production Profile:** `{style.profile_name}`",
        f"- **Configured Target Window:** `{manifest.target_duration_min_s:.0f}–{manifest.target_duration_max_s:.0f}s`",
        f"- **Timing Basis:** `{'Authoritative Narration Master (word_timings.json)' if wt else 'Pre-Generation Spoken Cadence Estimate'}`",
        "",
        "| Time | Narrative beat | Viewer question | New information | Visual reveal | Emotional direction | Retention purpose |",
        "|---|---|---|---|---|---|---|",
    ]
    rows: list[dict[str, Any]] = []
    for entry in nmap:
        row = {
            "time": entry["time_window"],
            "start_s": entry["start_s"],
            "end_s": entry["end_s"],
            "seg_id": entry["seg_id"],
            "narrative_beat": entry["narrative_beat"],
            "viewer_question": entry["viewer_question"],
            "new_information": entry["new_information"],
            "visual_reveal": entry["visual_reveal"],
            "emotional_direction": entry["emotional_direction"],
            "retention_purpose": entry["retention_purpose"],
        }
        rows.append(row)
        md_lines.append(
            f"| `{row['time']}` | **{row['narrative_beat']}** (`{row['seg_id']}`) | {row['viewer_question']} | "
            f"{row['new_information']} | {row['visual_reveal']} | {row['emotional_direction']} | {row['retention_purpose']} |"
        )

    plan_obj = {
        "slug": manifest.slug,
        "style_profile": style.profile_name,
        "target_duration_range_s": [manifest.target_duration_min_s, manifest.target_duration_max_s],
        "planned_duration_s": round(total_s, 2),
        "timing_source": "word_timings" if wt else "estimated_wpm",
        "rows": rows,
        "markdown_table": "\n".join(md_lines) + "\n",
    }

    target_out = out_dir or Path(manifest.output_dir)
    if target_out:
        target_out.mkdir(parents=True, exist_ok=True)
        (target_out / "retention_plan.json").write_text(json.dumps(plan_obj, indent=2), encoding="utf-8")
        (target_out / "retention_plan.md").write_text(plan_obj["markdown_table"], encoding="utf-8")

    return plan_obj
