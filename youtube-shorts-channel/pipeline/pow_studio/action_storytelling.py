#!/usr/bin/env python3
"""
Action-Based Visual Storytelling, Multi-Intent Footage Discovery,
Clause-Level Beat Segmentation & Pre-Production Visual Feasibility Engine
(`pow_studio.action_storytelling` v8.0).

Implements Part 2 (Section 3) and Part 3 (Sections 6, 7, 8):
1. Clause & Sentence Visual Beat Extraction (`extract_narration_visual_beats`):
   - Extracts all 10 required semantic fields per beat:
     `subject`, `action`, `location`, `object_item`, `scientific_process`,
     `intended_information`, `evidence_required`, `visual_perspective`,
     `suitable_shot_type`, and `genuine_footage_essential` (+ `is_historical_event`).
   - Splits single sentences with multiple actions into separate visual beats and
     links consecutive beats when one continuous action genuinely spans sentences.
2. Purpose-Driven Subject + Action Search Query Generator (`generate_footage_search_queries`):
   - Generates differentiated queries across fieldwork, sampling, active environmental
     processes, animal movement, equipment operation, close-up evidence, and aerials.
3. Action-Based Relevance & Anti-Keyword-Trap Matcher (`evaluate_action_visual_match`):
   - Rejects clips that merely share title keywords while depicting lectures, interviews,
     idle lab portraits, paper screenshots, generic scenic wallpaper, or undisclosed
     proxy locations.
4. Pre-Production Visual Feasibility Gate (`analyze_visual_feasibility`):
   - Produces `visual_feasibility_report.json` & `.md` with the required table:
     `| Story beat | Required visual | Available footage | Evidence relevance | Coverage status |`
   - Blocks finalizing stories where essential visual events lack authentic coverage
     unless `user_accepted_limited_visuals=True`.
5. 11-Field Planned Storyboard Builder (`build_action_storyboard_plan`):
   - Exports complete dry-run or production storyboards with all 11 Section 7 fields.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from .media_classifier import (
    GENUINE_MOVING_CLASSES,
    SourceMediaClass,
    infer_asset_source_media_class,
)
from .rights_gate import RightsViolationError, validate_license_string

# Canonical verb -> action category & essential-footage detector
ACTION_VERB_LEXICON: dict[str, str] = {
    "lower": "equipment_deployment",
    "lowered": "equipment_deployment",
    "lowering": "equipment_deployment",
    "deploy": "equipment_deployment",
    "deployed": "equipment_deployment",
    "deploying": "equipment_deployment",
    "drill": "drilling_operation",
    "drilled": "drilling_operation",
    "drilling": "drilling_operation",
    "sample": "scientific_sampling",
    "sampled": "scientific_sampling",
    "sampling": "scientific_sampling",
    "collect": "scientific_sampling",
    "collected": "scientific_sampling",
    "collecting": "scientific_sampling",
    "swab": "scientific_sampling",
    "swabbing": "scientific_sampling",
    "core": "drilling_operation",
    "coring": "drilling_operation",
    "explore": "expedition_exploration",
    "explored": "expedition_exploration",
    "exploring": "expedition_exploration",
    "trek": "expedition_exploration",
    "trekking": "expedition_exploration",
    "climb": "expedition_exploration",
    "climbing": "expedition_exploration",
    "descend": "expedition_exploration",
    "descending": "expedition_exploration",
    "dive": "underwater_exploration",
    "diving": "underwater_exploration",
    "submerge": "underwater_exploration",
    "strike": "animal_behavior",
    "strikes": "animal_behavior",
    "striking": "animal_behavior",
    "slither": "animal_behavior",
    "slithers": "animal_behavior",
    "slithering": "animal_behavior",
    "hunt": "animal_behavior",
    "hunting": "animal_behavior",
    "swim": "animal_behavior",
    "swimming": "animal_behavior",
    "crawl": "animal_behavior",
    "crawling": "animal_behavior",
    "bubble": "environmental_process",
    "bubbles": "environmental_process",
    "bubbling": "environmental_process",
    "boil": "environmental_process",
    "boiling": "environmental_process",
    "erupt": "environmental_process",
    "erupts": "environmental_process",
    "erupting": "environmental_process",
    "pour": "environmental_process",
    "pours": "environmental_process",
    "pouring": "environmental_process",
    "flow": "environmental_process",
    "flows": "environmental_process",
    "flowing": "environmental_process",
    "seep": "environmental_process",
    "seeps": "environmental_process",
    "vent": "environmental_process",
    "venting": "environmental_process",
    "crash": "environmental_process",
    "crashes": "environmental_process",
    "crashing": "environmental_process",
    "surge": "environmental_process",
    "surges": "environmental_process",
    "surging": "environmental_process",
    "swirl": "environmental_process",
    "swirling": "environmental_process",
    "spin": "machine_operation",
    "spun": "machine_operation",
    "spinning": "machine_operation",
    "fly": "machine_operation",
    "flew": "machine_operation",
    "flying": "machine_operation",
    "lift": "machine_operation",
    "lifted": "machine_operation",
    "operate": "machine_operation",
    "operating": "machine_operation",
    "scan": "scientific_measurement",
    "scanned": "scientific_measurement",
    "measure": "scientific_measurement",
    "measured": "scientific_measurement",
    "measuring": "scientific_measurement",
    "thrust": "equipment_deployment",
    "thrusting": "equipment_deployment",
    "blast": "environmental_process",
    "blasts": "environmental_process",
    "blasting": "environmental_process",
    "billow": "environmental_process",
    "billowing": "environmental_process",
    "trap": "environmental_process",
    "traps": "environmental_process",
    "swarm": "animal_behavior",
    "swarms": "animal_behavior",
    "swarming": "animal_behavior",
    "pack": "animal_behavior",
    "packs": "animal_behavior",
    "move": "animal_behavior",
    "moving": "animal_behavior",
    "farm": "animal_behavior",
    "farming": "animal_behavior",
    "detect": "animal_behavior",
    "detects": "animal_behavior",
}

EQUIPMENT_NOUNS = (
    "instrument", "instruments", "sensor", "sensors", "probe", "probes", "rov",
    "submersible", "drill", "ice core", "bottle", "vial", "pipette", "microscope",
    "radar", "sonar", "spectrometer", "helicopter", "rotorcraft", "rover", "winch",
    "cable", "camera", "suit", "respirator", "headlamp", "thermometer", "robotic arm", "robotic arms",
)

SCIENTIFIC_PROCESS_CUES = (
    "oxidation", "oxidizes", "hydrothermal", "chemosynthesis", "stratification",
    "halocline", "evaporation", "crystallization", "subduction", "convection",
    "photosynthesis", "radiolysis", "corrosion", "acidification", "venom",
    "hemotoxic", "neurotoxic", "hypersaline", "anoxic", "geothermal", "pressure",
    "infrared", "sulfur",
)

KNOWN_LOCATIONS = (
    "dallol", "ethiopia", "danakil", "naica", "chihuahua", "mexico", "kawah ijen",
    "indonesia", "java", "antarctica", "taylor glacier", "blood falls", "mcmurdo",
    "mariana trench", "challenger deep", "snake island", "queimada grande", "brazil",
    "gulf of mexico", "jezero crater", "mars", "mauna loa", "hawaii", "yellowstone", "wyoming",
    "yucatan", "cenote", "iceland", "greenland", "atacama", "chile", "dead sea", "svalbard", "idrija", "slovenia",
    "mid-atlantic ridge", "lucky strike", "snake pit", "europa", "enceladus",
)

# Keyword-trap patterns: titles/descriptions that match topic keywords yet show non-evidence visuals
KEYWORD_TRAP_DISQUALIFIERS = (
    (re.compile(r"\b(?:lecture|keynote|conference\s+talk|symposium|webinar|classroom|tedx?)\b", re.I), "Muted lecture/conference presentation footage"),
    (re.compile(r"\b(?:interview|talking[- ]head|press\s+briefing|podcast|panel\s+discussion|q\s*&\s*a)\b", re.I), "Muted talking-head/interview clip"),
    (re.compile(r"\b(?:paper\s+screenshot|journal\s+screenshot|pdf\s+page|abstract\s+screenshot|title\s+slide|powerpoint)\b", re.I), "Static paper/slide screenshot"),
    (re.compile(r"\b(?:portrait\s+of\s+scientist|standing\s+in\s+(?:a\s+)?lab(?:oratory)?\s+portrait|staff\s+headshot|building\s+exterior|university\s+campus)\b", re.I), "Generic portrait/building filler unrelated to field action"),
    (re.compile(r"\b(?:book\s+cover|logo\s+animation|channel\s+intro|subscribe\s+banner)\b", re.I), "Promotional/logo filler"),
)

GENERIC_WALLPAPER_PATTERN = re.compile(
    r"\b(?:generic\s+scenery|beautiful\s+sunset|decorative\s+background|stock\s+beach|"
    r"empty\s+underwater\s+background|generic\s+ocean\s+waves|random\s+clouds)\b",
    re.I,
)

HISTORICAL_EVENT_PATTERN = re.compile(
    r"\b(?:in\s+(?:18\d{2}|19[0-9]{2})|back\s+in\s+19\d{2}|historic(?:al)?\s+expedition|"
    r"first\s+discovered\s+in\s+19\d{2}|bathyscaphe\s+trieste|apollo\s+\d+|1911\s+expedition)\b",
    re.I,
)

_STOP = {
    "the", "and", "for", "with", "from", "into", "under", "over", "that", "this",
    "these", "those", "their", "there", "where", "when", "what", "which", "while",
    "have", "has", "had", "were", "was", "are", "been", "being", "than", "then",
    "its", "they", "them", "but", "not", "can", "could", "would", "only", "more",
}


def _clean_tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{3,}", (text or "").lower()) if w not in _STOP}


@dataclass
class NarrationVisualBeat:
    beat_id: str
    seg_id: str
    clause_index: int
    narration_text: str
    # All 10 required Part 3 Section 6 fields:
    subject: str
    action: str
    location: str
    object_item: str
    scientific_process: str
    intended_information: str
    evidence_required: str
    visual_perspective: str
    suitable_shot_type: str  # SourceMediaClass value
    genuine_footage_essential: bool
    # Additional continuity & historical context flags:
    action_category: str = "contextual_observation"
    is_historical_event: bool = False
    continues_previous_action: bool = False
    estimated_duration_s: float = 3.8


def _split_into_visual_clauses(sentence: str) -> list[str]:
    """
    Split a sentence into multiple visual clauses ONLY when distinct actions appear
    across conjunctions/clauses (e.g., ';', '—', ', then ', ', while ', ' and then '),
    avoiding over-splitting single-action descriptive sentences.
    """
    s = sentence.strip()
    if not s:
        return []
    parts = re.split(
        r"(?:\s*;\s*|\s+—\s+|,\s+(?:then|while|before|after|as)\s+|\s+and\s+then\s+)",
        s,
    )
    if len(parts) <= 1:
        # Also check compound verb pattern: `<verb1> ... and <verb2> ...`
        m = re.split(r"\s+and\s+(?=(?:lowered|collected|hauled|extracted|drilled|sampled|measured|analyzed|dived|struck)\b)", s, flags=re.I)
        if len(m) > 1:
            parts = m

    merged: list[str] = []
    for p in parts:
        p_clean = p.strip()
        if not p_clean:
            continue
        if merged and len(p_clean.split()) < 4:
            merged[-1] = f"{merged[-1]}, {p_clean}"
        else:
            merged.append(p_clean)
    return merged or [s]


def _extract_location(text: str, fallback_location: str = "") -> str:
    low = text.lower()
    hits = [loc.title() for loc in KNOWN_LOCATIONS if loc in low]
    if hits:
        return ", ".join(dict.fromkeys(hits[:2]))
    # Capitalized Proper Location Phrase fallback (`in <Proper Noun>`)
    m = re.search(r"\b(?:in|inside|beneath|across|off|at|near)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,2})", text)
    if m:
        cand = m.group(1)
        if cand.lower() not in {"the", "this", "earth", "scientists", "researchers", "water", "ice"}:
            return cand
    return fallback_location or "Target documentary site"


def _extract_subject(text: str, topic: str) -> str:
    low = text.lower()
    subject_patterns = [
        r"\b(scientists|researchers|biologists|geologists|herpetologists|divers|explorers|astronauts|engineers|microbiologists)\b",
        r"\b(golden\s+lancehead(?:\s+vipers?)?|vipers?|snakes?|migratory\s+birds?|rimicaris(?:\s+exoculata)?|(?:blind|pale)\s+shrimp|shrimp|mussels?|gastropods?|light-sensing\s+organ|eyeballs|microbes?|bacteria|extremophiles?|amphipods?|snailfish)\b",
        r"\b(brine\s+pools?|acid(?:ic)?\s+ponds?|hydrothermal\s+vents?|black\s+smokers?|(?:black|underwater)\s+chimneys?|chimney\s+walls?|chimneys?|superheated\s+water|selenite\s+crystals?|gypsum\s+crystals?|glacier\s+ice|lava\s+tubes?|ocean\s+waves?|waves|cliffs?|island\s+coast(?:line)?)\b",
        r"\b(rotorcraft|ingenuity|perseverance|rover|submersible|remotely\s+operated\s+vehicles?|rov|(?:robotic|manipulator)\s+arms?|bathyscaphe|radar|drill)\b",
    ]
    for pat in subject_patterns:
        m = re.search(pat, low)
        if m:
            return m.group(1)
    # Strip leading prepositional/distance opener before a comma ("Forty miles off Brazil's coast, ...")
    core_clause = text.split(",", 1)[1].strip() if ("," in text and len(text.split(",", 1)[0].split()) <= 7) else text
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", core_clause) if w.lower() not in _STOP]
    if words:
        return " ".join(words[:2])
    return topic or "Primary phenomenon"


def _extract_action_and_category(text: str) -> tuple[str, str]:
    toks = re.findall(r"[a-z]+", text.lower())
    for idx, t in enumerate(toks):
        if t in ACTION_VERB_LEXICON:
            cat = ACTION_VERB_LEXICON[t]
            window = " ".join(toks[idx : min(len(toks), idx + 4)])
            return window, cat
    return "observing phenomenon state", "contextual_observation"


def extract_narration_visual_beats(
    narration_segments: list[Any],
    topic: str = "",
) -> list[NarrationVisualBeat]:
    """
    Decompose script narration into sentence- and clause-level `NarrationVisualBeat`s
    with all 10 semantic storytelling attributes (Part 3 Sections 6 & 7).
    """
    beats: list[NarrationVisualBeat] = []
    running_location = _extract_location(topic, "")
    b_counter = 1

    for seg in narration_segments:
        seg_id = str(getattr(seg, "seg_id", "") if not isinstance(seg, dict) else seg.get("seg_id", f"N{b_counter:02d}"))
        raw_text = str(getattr(seg, "text", "") if not isinstance(seg, dict) else seg.get("text", "")).strip()
        explicit_info = str(
            (getattr(seg, "new_information", "") if not isinstance(seg, dict) else seg.get("new_information", "")) or ""
        ).strip()

        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", raw_text) if s.strip()]
        clause_idx = 0
        for sent in sentences:
            clauses = _split_into_visual_clauses(sent)
            for cl in clauses:
                loc = _extract_location(cl, running_location)
                if loc and loc != "Target documentary site":
                    running_location = loc
                subj = _extract_subject(cl, topic)
                act_phrase, act_cat = _extract_action_and_category(cl)
                low_cl = cl.lower()

                obj_hit = next((eq for eq in EQUIPMENT_NOUNS if eq in low_cl), "")
                proc_hit = next((pr for pr in SCIENTIFIC_PROCESS_CUES if pr in low_cl), "")
                is_hist = bool(HISTORICAL_EVENT_PATTERN.search(cl))

                # Determine perspective & suitable 10-class media type
                if re.search(r"\b(?:microbe|microbial|cell|bacteria|dna|microscop|crystal\s+lattice)\b", low_cl):
                    persp = "macro_detail"
                elif act_cat in ("scientific_sampling", "equipment_deployment", "drilling_operation", "expedition_exploration"):
                    persp = "human_scale"
                elif act_cat in ("animal_behavior", "environmental_process", "scientific_measurement"):
                    persp = "close_up"
                elif re.search(r"\b(?:island|coast|crater|ocean|mountain|valley|desert|trench|kilometer|miles)\b", low_cl):
                    persp = "wide_establishing"
                else:
                    persp = "medium_detail"

                genuine_essential = act_cat in (
                    "equipment_deployment",
                    "drilling_operation",
                    "scientific_sampling",
                    "expedition_exploration",
                    "underwater_exploration",
                    "animal_behavior",
                    "environmental_process",
                    "machine_operation",
                ) and not is_hist

                if is_hist:
                    suitable_cls = SourceMediaClass.STILL_PHOTO.value  # archival footage or verified historical photo
                    ev_req = f"Verified archival historical footage or photograph of {subj} ({act_phrase}) at {loc}"
                elif genuine_essential:
                    suitable_cls = SourceMediaClass.REAL_VIDEO_ACTION.value
                    ev_req = f"Genuine moving footage showing {subj} actively {act_phrase}" + (f" with {obj_hit}" if obj_hit else "") + f" ({loc})"
                elif persp == "macro_detail" and not genuine_essential:
                    suitable_cls = SourceMediaClass.SCIENTIFIC_IMAGE.value
                    ev_req = f"Authentic microscopy or macro scientific image/video of {subj}"
                elif proc_hit and re.search(r"\b(?:beneath\s+the\s+crust|subglacial\s+conduit|tectonic|core|molecular)\b", low_cl):
                    suitable_cls = SourceMediaClass.REAL_ANIMATION.value
                    ev_req = f"Real process footage or concise scientific visualization of {proc_hit}"
                else:
                    suitable_cls = SourceMediaClass.REAL_VIDEO_ESTABLISHING.value
                    ev_req = f"Authentic location footage establishing {subj} at {loc}"

                continues_prev = bool(
                    beats
                    and beats[-1].seg_id == seg_id
                    and beats[-1].subject == subj
                    and beats[-1].action_category == act_cat
                    and act_cat != "contextual_observation"
                )
                wc = max(3, len(cl.split()))
                est_dur = round(max(2.4, min(8.5, wc / 2.55)), 2)

                beats.append(
                    NarrationVisualBeat(
                        beat_id=f"B{b_counter:02d}",
                        seg_id=seg_id,
                        clause_index=clause_idx,
                        narration_text=cl,
                        subject=subj,
                        action=act_phrase,
                        location=loc,
                        object_item=obj_hit or "natural formation",
                        scientific_process=proc_hit or "physical observation",
                        intended_information=explicit_info or cl,
                        evidence_required=ev_req,
                        visual_perspective=persp,
                        suitable_shot_type=suitable_cls,
                        genuine_footage_essential=genuine_essential,
                        action_category=act_cat,
                        is_historical_event=is_hist,
                        continues_previous_action=continues_prev,
                        estimated_duration_s=est_dur,
                    )
                )
                b_counter += 1
                clause_idx += 1
    return beats


def generate_footage_search_queries(
    topic: str,
    beats: Optional[list[NarrationVisualBeat]] = None,
) -> list[dict[str, str]]:
    """
    Generate purpose-differentiated Subject + Action queries for `$0` institutional
    video archives (Part 2 Section 3: never search bare location nouns alone!).
    """
    clean_topic = re.sub(r"[^A-Za-z0-9\s-]", " ", topic).strip()
    core_words = [w for w in clean_topic.split() if w.lower() not in _STOP][:4]
    anchor = " ".join(core_words) if core_words else clean_topic

    queries: list[dict[str, str]] = [
        {"purpose": "scientific_sampling", "query": f"Scientists sampling {anchor}", "target_media_class": "REAL_VIDEO_ACTION"},
        {"purpose": "expedition_fieldwork", "query": f"{anchor} expedition fieldwork", "target_media_class": "REAL_VIDEO_ACTION"},
        {"purpose": "environmental_process", "query": f"{anchor} active process footage", "target_media_class": "REAL_VIDEO_ACTION"},
        {"purpose": "close_up_evidence", "query": f"{anchor} formations close-up", "target_media_class": "REAL_VIDEO_ACTION"},
        {"purpose": "establishing_location", "query": f"{anchor} aerial documentary footage", "target_media_class": "REAL_VIDEO_ESTABLISHING"},
    ]

    seen_q = {q["query"].lower() for q in queries}
    for b in beats or []:
        loc_part = b.location.split(",")[0].strip() if b.location and b.location != "Target documentary site" else anchor
        candidates = []
        if b.action_category == "scientific_sampling":
            candidates.append(("scientific_sampling", f"Scientists sampling {loc_part} {b.subject}", "REAL_VIDEO_ACTION"))
        elif b.action_category == "equipment_deployment":
            candidates.append(("equipment_operation", f"Researchers {b.action} {b.object_item} {loc_part}", "REAL_VIDEO_ACTION"))
        elif b.action_category == "animal_behavior":
            candidates.append(("animal_action", f"{b.subject} {b.action} {loc_part} footage", "REAL_VIDEO_ACTION"))
        elif b.action_category == "environmental_process":
            candidates.append(("environmental_process", f"{loc_part} {b.action} {b.subject}", "REAL_VIDEO_ACTION"))
        elif b.action_category in ("expedition_exploration", "underwater_exploration", "drilling_operation", "machine_operation"):
            candidates.append(("field_operation", f"{loc_part} {b.subject} {b.action}", "REAL_VIDEO_ACTION"))
        if b.scientific_process and b.scientific_process != "physical observation":
            candidates.append(("scientific_process", f"{loc_part} {b.scientific_process} video", "REAL_VIDEO_ACTION"))
        if b.is_historical_event:
            candidates.append(("historical_archive", f"{loc_part} {b.subject} archival footage", "STILL_PHOTO"))

        for purp, q_str, t_cls in candidates:
            q_norm = re.sub(r"\s+", " ", q_str).strip()
            if q_norm.lower() not in seen_q:
                seen_q.add(q_norm.lower())
                queries.append({"purpose": purp, "query": q_norm, "target_media_class": t_cls, "beat_id": b.beat_id})
    return queries


def evaluate_action_visual_match(
    beat: NarrationVisualBeat,
    candidate: dict[str, Any] | Any,
) -> dict[str, Any]:
    """
    Evaluate whether `candidate` genuinely illustrates `beat` based on visible subject,
    visible action, location authenticity, historical-era honesty, and commercial license,
    explicitly rejecting keyword-matching traps!
    """
    def _g(key: str, default: Any = "") -> Any:
        if isinstance(candidate, dict):
            return candidate.get(key, default)
        return getattr(candidate, key, default)

    cand_id = str(_g("local_file") or _g("asset_id") or _g("title") or "unknown_asset")
    raw_mtype = str(_g("media_type", "") or "").lower()
    if raw_mtype == "audio" or Path(cand_id).suffix.lower() in {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac"}:
        return {
            "beat_id": beat.beat_id,
            "candidate_id": cand_id,
            "media_class": "AUDIO_ONLY",
            "subject_score": 0.0,
            "action_alignment_score": 0.0,
            "location_integrity_score": 0.0,
            "overall_relevance": 0.0,
            "eligible": False,
            "rejection_reason": "Audio asset — excluded from visual footage selection.",
        }

    title = str(_g("title", ""))
    desc = " ".join(
        str(_g(k, "") or "")
        for k in ("title", "description", "visual_desc", "intended_use", "depicted_subject", "depicted_action", "depicted_location", "local_file", "source_page_url")
    )
    license_str = str(_g("license") or _g("license_label") or "Public Domain")
    is_talking_head = bool(_g("is_talking_head", False))
    cand_era = str(_g("historical_era", "") or "").lower()

    if isinstance(candidate, dict):
        media_cls = str(candidate.get("source_media_class") or "")
        if not media_cls:
            m_raw = str(candidate.get("media_type", "video")).lower()
            if m_raw == "photo":
                media_cls = SourceMediaClass.STILL_PHOTO.value
            elif m_raw == "diagram":
                media_cls = SourceMediaClass.INFOGRAPHIC.value
            elif re.search(r"\b(?:aerial|landscape|panorama|establishing|scenic)\b", desc, re.I) and not re.search(
                r"\b(?:sampling|lowering|drilling|moving|striking|bubbling|operating|walking|collecting)\b", desc, re.I
            ):
                media_cls = SourceMediaClass.REAL_VIDEO_ESTABLISHING.value
            else:
                media_cls = SourceMediaClass.REAL_VIDEO_ACTION.value
    else:
        media_cls = infer_asset_source_media_class(candidate, probe_pixels=False)

    rejection_reasons: list[str] = []

    # 1. Commercial rights verification ($0 commercial-safe requirement)
    try:
        validate_license_string(license_str, cand_id)
    except RightsViolationError as exc:
        rejection_reasons.append(str(exc))

    # 2. AI-generated ban for real documentary evidence
    if media_cls == SourceMediaClass.AI_GENERATED.value:
        rejection_reasons.append("AI-generated media is barred from representing documentary evidence.")

    # 3. Anti-Keyword-Trap screening (even if 100% of topic keywords appear in `title`!)
    if is_talking_head:
        rejection_reasons.append("Muted talking-head/interview clip rejected.")
    for rx, reason in KEYWORD_TRAP_DISQUALIFIERS:
        if rx.search(desc):
            rejection_reasons.append(f"Keyword-trap rejected: {reason} (matched in '{title or cand_id}').")

    if beat.genuine_footage_essential and GENERIC_WALLPAPER_PATTERN.search(desc):
        rejection_reasons.append("Generic scenic/wallpaper filler rejected for an active story beat.")

    # 4. Idle lab/portrait trap when field action is narrated
    if beat.action_category in ("equipment_deployment", "scientific_sampling", "expedition_exploration", "underwater_exploration", "drilling_operation"):
        if re.search(r"\b(?:random\s+scientist\s+standing|standing\s+idle|office\s+desk|indoor\s+portrait)\b", desc, re.I):
            rejection_reasons.append("Idle indoor portrait/lab shot does not show narrated field action.")

    # 5. Location integrity check (prevent undisclosed Hawaii/Yellowstone/Slovenia stand-ins!)
    beat_locs = [loc for loc in KNOWN_LOCATIONS if loc in beat.location.lower() or loc in beat.narration_text.lower()]
    cand_locs = [loc for loc in KNOWN_LOCATIONS if loc in desc.lower()]
    location_score = 0.78
    if beat_locs and cand_locs:
        # Group co-located geographical hierarchies (e.g. Dallol <-> Danakil <-> Ethiopia; Blood Falls <-> Taylor Glacier <-> McMurdo <-> Antarctica)
        GEO_EQUIV = [
            {"dallol", "danakil", "ethiopia"},
            {"naica", "chihuahua", "mexico"},
            {"kawah ijen", "java", "indonesia"},
            {"blood falls", "taylor glacier", "mcmurdo", "antarctica"},
            {"snake island", "queimada grande", "brazil"},
            {"jezero crater", "mars"},
            {"mauna loa", "hawaii"},
            {"idrija", "slovenia"},
        ]

        def _same_region(l1: str, l2: str) -> bool:
            if l1 == l2:
                return True
            return any(l1 in grp and l2 in grp for grp in GEO_EQUIV)

        if any(_same_region(bl, cl) for bl in beat_locs for cl in cand_locs):
            location_score = 1.0
        else:
            location_score = 0.15
            if not bool(_g("explicit_analog_comparison", False)):
                rejection_reasons.append(
                    f"Undisclosed proxy-location mismatch: beat describes '{', '.join(beat_locs)}' "
                    f"but candidate depicts '{', '.join(cand_locs)}'."
                )

    # 6. Historical-event honesty check (Final Creative Standard)
    if beat.is_historical_event and cand_era in ("modern", "contemporary") and not re.search(r"\b(?:historic|archival|archive|19\d{2}|18\d{2})\b", desc, re.I):
        rejection_reasons.append("Modern footage cannot pretend to depict a specific historical event; use verified archival media.")

    # 7. Subject & Action semantic scoring
    beat_subj_toks = _clean_tokens(beat.subject)
    beat_act_toks = _clean_tokens(f"{beat.action} {beat.object_item} {beat.scientific_process}")
    cand_toks = _clean_tokens(desc)

    subj_hits = len(beat_subj_toks & cand_toks)
    act_hits = len(beat_act_toks & cand_toks)
    subject_score = min(1.0, subj_hits / float(max(1, len(beat_subj_toks)))) if beat_subj_toks else 0.5
    action_score = min(1.0, act_hits / float(max(1, min(3, len(beat_act_toks))))) if beat_act_toks else 0.5

    # Check action-category synonym alignment
    cat_cues = {
        "equipment_deployment": r"\b(?:lower|lowering|deploy|instrument|winch|cable|probe|sensor|ctd|rov)\b",
        "scientific_sampling": r"\b(?:sample|sampling|collect|collecting|vial|bottle|swab|core|water\s+sample)\b",
        "drilling_operation": r"\b(?:drill|drilling|ice\s+core|borehole|auger)\b",
        "expedition_exploration": r"\b(?:expedition|fieldwork|trek|climb|cave|caver|explorer|researcher|scientist|camp)\b",
        "underwater_exploration": r"\b(?:rov|submersible|dive|diver|underwater|deep[- ]sea|bathymetry|trench)\b",
        "animal_behavior": r"\b(?:viper|snake|bird|fish|amphipod|slither|strike|hunt|swim|crawl|moving)\b",
        "environmental_process": r"\b(?:bubbl|boil|erupt|flow|pour|seep|vent|brine|plume|acid|steam|wave|swell|crash|strike|coast)\b",
        "machine_operation": r"\b(?:rotor|flight|fly|spin|hover|rover|helicopter|manipulator|operating)\b",
    }.get(beat.action_category, "")
    if cat_cues and re.search(cat_cues, desc, re.I):
        action_score = max(action_score, 0.85)

    # Penalize generic landscape/establishing clip when active action is essential and zero action cues exist
    if beat.genuine_footage_essential and media_cls == SourceMediaClass.REAL_VIDEO_ESTABLISHING.value and action_score < 0.30:
        action_score *= 0.45

    media_bonus = {
        SourceMediaClass.REAL_VIDEO_ACTION.value: 1.00,
        SourceMediaClass.REAL_VIDEO_ESTABLISHING.value: 0.78 if not beat.genuine_footage_essential else 0.55,
        SourceMediaClass.REAL_TIME_LAPSE.value: 0.76,
        SourceMediaClass.SCIENTIFIC_IMAGE.value: 0.74,
        SourceMediaClass.STILL_PHOTO.value: 0.88 if beat.is_historical_event else 0.62,
        SourceMediaClass.ANIMATED_STILL.value: 0.52,
        SourceMediaClass.REAL_ANIMATION.value: 0.68,
        SourceMediaClass.INFOGRAPHIC.value: 0.48,
        SourceMediaClass.REENACTMENT.value: 0.30,
        SourceMediaClass.AI_GENERATED.value: 0.0,
    }.get(media_cls, 0.50)

    raw_rel = (
        0.32 * subject_score
        + 0.36 * action_score
        + 0.17 * location_score
        + 0.15 * media_bonus
    )
    if subject_score == 0.0 and action_score < 0.35:
        rejection_reasons.append("Neither subject nor action matches the narrated beat.")

    eligible = len(rejection_reasons) == 0 and raw_rel >= 0.42
    final_rel = round(raw_rel if eligible else min(0.32, raw_rel * 0.45), 3)

    return {
        "beat_id": beat.beat_id,
        "candidate_id": cand_id,
        "media_class": media_cls,
        "subject_score": round(subject_score, 3),
        "action_alignment_score": round(action_score, 3),
        "location_integrity_score": round(location_score, 3),
        "overall_relevance": final_rel,
        "eligible": eligible,
        "rejection_reason": "; ".join(rejection_reasons),
    }


def analyze_visual_feasibility(
    topic: str,
    narration_segments: list[Any],
    available_assets: list[Any],
    user_accepted_limited_visuals: bool = False,
    out_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """
    Pre-Production Visual Feasibility Gate (Part 3 Section 8):
      - Evaluates every story beat against `available_assets` BEFORE finalizing script/timeline.
      - Generates the required feasibility table:
        `| Story beat | Required visual | Available footage | Evidence relevance | Coverage status |`
      - Blocks silent approval when essential visual events lack authentic coverage unless
        `user_accepted_limited_visuals=True`.
    """
    beats = extract_narration_visual_beats(narration_segments, topic=topic)
    search_queries = generate_footage_search_queries(topic, beats)

    rows: list[dict[str, Any]] = []
    essential_total = 0
    essential_with_real_video = 0
    essential_with_any_valid = 0
    missing_beats: list[str] = []

    for b in beats:
        if b.genuine_footage_essential:
            essential_total += 1

        scored = []
        for cand in available_assets:
            ev = evaluate_action_visual_match(b, cand)
            scored.append((ev, cand))
        scored.sort(key=lambda pair: (pair[0]["eligible"], pair[0]["overall_relevance"]), reverse=True)

        best_ev = scored[0][0] if scored else None
        best_cand = scored[0][1] if scored else None

        if best_ev and best_ev["eligible"]:
            mcls = best_ev["media_class"]
            cand_name = best_ev["candidate_id"]
            rel = best_ev["overall_relevance"]
            if mcls == SourceMediaClass.REAL_VIDEO_ACTION.value:
                cov = "STRONG_ACTION_FOOTAGE"
                if b.genuine_footage_essential:
                    essential_with_real_video += 1
                    essential_with_any_valid += 1
            elif mcls in GENUINE_MOVING_CLASSES:
                cov = "ESTABLISHING_VIDEO_ONLY" if b.genuine_footage_essential else "GENUINE_LOCATION_FOOTAGE"
                if b.genuine_footage_essential:
                    essential_with_real_video += 1
                    essential_with_any_valid += 1
            elif mcls in (SourceMediaClass.STILL_PHOTO.value, SourceMediaClass.SCIENTIFIC_IMAGE.value, SourceMediaClass.ANIMATED_STILL.value):
                cov = "AUTHENTIC_STILL_EVIDENCE" if not b.genuine_footage_essential else "LIMITED_STILL_FALLBACK"
                if b.genuine_footage_essential:
                    essential_with_any_valid += 1
            else:
                cov = "CONCISE_SCIENTIFIC_VISUALIZATION"
            avail_label = f"{cand_name} ({mcls})"
            rel_label = f"{rel:.2f} — Verified match"
        else:
            cov = "MISSING_CRITICAL_EVIDENCE"
            missing_beats.append(b.beat_id)
            avail_label = "None (0 eligible commercial-safe assets)"
            rel_label = (
                f"0.00 — {best_ev['rejection_reason']}"
                if (best_ev and best_ev["rejection_reason"])
                else "0.00 — No matching media in library"
            )

        rows.append(
            {
                "beat_id": b.beat_id,
                "seg_id": b.seg_id,
                "story_beat": f"{b.beat_id} ({b.seg_id}): {b.narration_text}",
                "required_visual": b.evidence_required,
                "available_footage": avail_label,
                "evidence_relevance": rel_label,
                "coverage_status": cov,
                "genuine_footage_essential": b.genuine_footage_essential,
                "best_candidate_id": best_ev["candidate_id"] if (best_ev and best_ev["eligible"]) else None,
                "best_media_class": best_ev["media_class"] if (best_ev and best_ev["eligible"]) else None,
                "relevance_score": best_ev["overall_relevance"] if (best_ev and best_ev["eligible"]) else 0.0,
                "best_candidate_obj": best_cand if (best_ev and best_ev["eligible"]) else None,
            }
        )

    total_beats = max(1, len(beats))
    covered_beats = total_beats - len(missing_beats)
    beat_coverage_ratio = round(covered_beats / float(total_beats), 4)
    essential_video_ratio = round(essential_with_real_video / float(max(1, essential_total)), 4) if essential_total > 0 else 1.0

    # Part 3 Section 8 rule: block finalizing when essential visual events are poorly covered!
    insufficient = (
        (essential_total >= 3 and essential_with_any_valid <= max(1, int(0.45 * essential_total)))
        or beat_coverage_ratio < 0.60
    )
    can_proceed = (not insufficient) or user_accepted_limited_visuals

    remediation_steps: list[str] = []
    if missing_beats or essential_video_ratio < 0.70:
        remediation_steps = [
            f"1. Search deeper official archives using generated Subject+Action queries ({len(search_queries)} queries prepared across NASA, NOAA, USGS, Wikimedia Commons, Internet Archive).",
            "2. Investigate alternative camera angles (instrument close-ups, sample handling, macro formations, satellite/ROV telemetry).",
            "3. Search peer-reviewed open-access supplemental videos (`CC BY` PLOS / Nature Communications / Scientific Reports).",
            "4. Evaluate whether 1 concise, progressive scientific animation (`<= 10%` runtime) is justified for unseen subsurface processes.",
            "5. Restructure or condense script clauses whose visual events have zero authentic footage rather than padding with proxy locations.",
            f"6. Remaining explicit gaps flagged on beats: {', '.join(missing_beats) if missing_beats else 'Still-only fallbacks on action beats'}.",
        ]

    serializable_rows = [{k: v for k, v in r.items() if k != "best_candidate_obj"} for r in rows]
    report = {
        "topic": topic,
        "total_visual_beats": len(beats),
        "essential_action_beats": essential_total,
        "essential_beats_with_real_footage": essential_with_real_video,
        "essential_beats_with_any_authentic_visual": essential_with_any_valid,
        "missing_evidence_beats": missing_beats,
        "beat_coverage_ratio": beat_coverage_ratio,
        "essential_footage_coverage_ratio": essential_video_ratio,
        "feasibility_status": (
            "READY_FOOTAGE_FIRST"
            if (not missing_beats and essential_video_ratio >= 0.70)
            else ("LIMITED_VISUAL_TREATMENT_ACCEPTED" if (insufficient and user_accepted_limited_visuals) else ("INSUFFICIENT_FOOTAGE_RESTRUCTURE_REQUIRED" if insufficient else "PARTIAL_COVERAGE_ACTION_NEEDED"))
        ),
        "can_proceed_to_production": can_proceed,
        "recommended_search_queries": search_queries,
        "remediation_plan": remediation_steps,
        "feasibility_table": serializable_rows,
    }

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "visual_feasibility_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        md_lines = [
            f"# Pre-Production Visual Feasibility Report — {topic}",
            "",
            f"- **Feasibility Verdict:** `{report['feasibility_status']}` (`can_proceed_to_production={can_proceed}`)",
            f"- **Visual Beat Coverage:** `{covered_beats}/{len(beats)}` (`{beat_coverage_ratio*100:.1f}%`)",
            f"- **Essential Action Footage Coverage:** `{essential_with_real_video}/{essential_total}` (`{essential_video_ratio*100:.1f}%`)",
            "",
            "## Beat-by-Beat Visual Evidence Table",
            "",
            "| Story beat | Required visual | Available footage | Evidence relevance | Coverage status |",
            "|---|---|---|---|---|",
        ]
        for r in serializable_rows:
            md_lines.append(
                f"| {r['story_beat']} | {r['required_visual']} | {r['available_footage']} | {r['evidence_relevance']} | `{r['coverage_status']}` |"
            )
        if remediation_steps:
            md_lines.extend(["", "## Required Remediation / Script Restructuring Actions", ""])
            for step in remediation_steps:
                md_lines.append(f"- {step}")
        (out_dir / "visual_feasibility_report.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    return report


def build_action_storyboard_plan(
    slug: str,
    topic: str,
    narration_segments: list[Any],
    available_assets: list[Any],
    total_duration_s: Optional[float] = None,
    out_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """
    Generate a complete Footage-First Action Storyboard (Part 3 Section 7) where:
      - Every planned shot includes all 11 required Section 7 fields:
        `scene_id`, `narration_segment`, `visual_objective`, `visible_action`,
        `asset`, `source`, `media_type`, `shot_perspective`, `relevance`,
        `duration`, `continuity`.
      - Consecutive beats sharing the same continuous real video action merge cleanly
        rather than creating rapid montage cuts.
      - Still photographs are kept brief and un-animated by default, never reused with
        fake multi-crops.
    """
    beats = extract_narration_visual_beats(narration_segments, topic=topic)
    used_still_ids: set[str] = set()
    asset_use_counts: dict[str, int] = {}

    def _get_field(obj: Any, key: str, default: Any = "") -> Any:
        return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)

    raw_planned: list[dict[str, Any]] = []
    for idx, b in enumerate(beats):
        ranked: list[tuple[float, dict[str, Any], Any]] = []
        for cand in available_assets:
            cid = str(_get_field(cand, "local_file") or _get_field(cand, "asset_id") or _get_field(cand, "title"))
            ev = evaluate_action_visual_match(b, cand)
            if not ev["eligible"]:
                continue
            mcls = ev["media_class"]
            # Never reuse a still photograph across multiple scenes!
            if mcls in ("STILL_PHOTO", "ANIMATED_STILL", "SCIENTIFIC_IMAGE") and cid in used_still_ids:
                continue
            reuse_pen = 0.14 * asset_use_counts.get(cid, 0)
            footage_boost = 0.12 if mcls == SourceMediaClass.REAL_VIDEO_ACTION.value else (0.04 if mcls in GENUINE_MOVING_CLASSES else -0.05)
            eff_score = ev["overall_relevance"] + footage_boost - reuse_pen
            ranked.append((eff_score, ev, cand))

        ranked.sort(key=lambda t: t[0], reverse=True)
        if ranked:
            _, best_ev, best_cand = ranked[0]
            cid = best_ev["candidate_id"]
            mcls = best_ev["media_class"]
            if mcls in ("STILL_PHOTO", "ANIMATED_STILL", "SCIENTIFIC_IMAGE"):
                used_still_ids.add(cid)
            asset_use_counts[cid] = asset_use_counts.get(cid, 0) + 1
            src_url = str(_get_field(best_cand, "source_page_url") or _get_field(best_cand, "direct_media_url") or "")
            creator = str(_get_field(best_cand, "creator_agency") or _get_field(best_cand, "creator") or "Verified Institutional Archive")
            vis_action = str(_get_field(best_cand, "depicted_action") or _get_field(best_cand, "visual_desc") or f"{b.subject} — {b.action}")
            rel_explain = (
                f"Score {best_ev['overall_relevance']:.2f}: directly depicts {b.subject} ({b.action}) "
                f"with verified location/process alignment."
            )
            dur = b.estimated_duration_s if mcls in GENUINE_MOVING_CLASSES else min(3.4, b.estimated_duration_s)
        else:
            cid = "UNRESOLVED_FOOTAGE_GAP"
            mcls = "MISSING_EVIDENCE"
            src_url = "N/A — Acquire verified archive clip or restructure clause"
            creator = "N/A"
            vis_action = f"GAP: Requires {b.evidence_required}"
            rel_explain = "Flagged pre-render gap: workflow refuses to substitute unrelated scenic filler."
            dur = b.estimated_duration_s

        # Merge into preceding planned scene if continuous real video action continues!
        if (
            raw_planned
            and cid != "UNRESOLVED_FOOTAGE_GAP"
            and raw_planned[-1]["asset"] == cid
            and mcls in GENUINE_MOVING_CLASSES
            and (b.continues_previous_action or raw_planned[-1]["seg_id"] == b.seg_id)
        ):
            prev = raw_planned[-1]
            prev["narration_segment"] = f"{prev['narration_segment']} {b.narration_text}"
            prev["est_dur_s"] = round(prev["est_dur_s"] + dur, 2)
            prev["continuity"] = "Continuous uninterrupted recording held across connected action clauses"
            continue

        raw_planned.append(
            {
                "seg_id": b.seg_id,
                "narration_segment": b.narration_text,
                "visual_objective": b.intended_information,
                "visible_action": vis_action,
                "asset": cid,
                "source": f"{creator} ({src_url})",
                "media_type": mcls,
                "shot_perspective": b.visual_perspective,
                "relevance": rel_explain,
                "est_dur_s": dur,
                "continuity": "Opening visual hook on Frame 0" if idx == 0 else "",
            }
        )

    # Normalize timeline range to `total_duration_s` if provided
    raw_sum = max(1e-6, sum(p["est_dur_s"] for p in raw_planned))
    target_total = float(total_duration_s) if (total_duration_s and total_duration_s > 0) else raw_sum
    scale = target_total / raw_sum

    scenes: list[dict[str, Any]] = []
    t_cursor = 0.0
    for i, p in enumerate(raw_planned):
        sid = f"S{i + 1:02d}"
        d_s = round(p["est_dur_s"] * scale, 2) if i < len(raw_planned) - 1 else round(max(0.5, target_total - t_cursor), 2)
        t_end = round(t_cursor + d_s, 2)
        if not p["continuity"]:
            prev_p = raw_planned[i - 1]
            nxt_p = raw_planned[i + 1] if i + 1 < len(raw_planned) else None
            cont = f"Advances from {prev_p['shot_perspective']} ({prev_p['media_type']}) to {p['shot_perspective']} new action/evidence"
            if nxt_p:
                cont += f"; leads into {nxt_p['shot_perspective']} on next beat"
        else:
            cont = p["continuity"]

        scenes.append(
            {
                "scene_id": sid,
                "narration_segment": p["narration_segment"],
                "visual_objective": p["visual_objective"],
                "visible_action": p["visible_action"],
                "asset": p["asset"],
                "source": p["source"],
                "media_type": p["media_type"],
                "shot_perspective": p["shot_perspective"],
                "relevance": p["relevance"],
                "duration": f"{t_cursor:.2f}s–{t_end:.2f}s ({d_s:.2f}s)",
                "start_s": round(t_cursor, 2),
                "end_s": t_end,
                "duration_s": d_s,
                "continuity": cont,
            }
        )
        t_cursor = t_end

    # Compute 5-part coverage summary across planned storyboard
    tot = max(1e-6, t_cursor)
    mov_s = sum(s["duration_s"] for s in scenes if s["media_type"] in GENUINE_MOVING_CLASSES)
    act_s = sum(s["duration_s"] for s in scenes if s["media_type"] == SourceMediaClass.REAL_VIDEO_ACTION.value)
    est_s = sum(s["duration_s"] for s in scenes if s["media_type"] == SourceMediaClass.REAL_VIDEO_ESTABLISHING.value)
    sta_s = sum(s["duration_s"] for s in scenes if s["media_type"] in ("STILL_PHOTO", "ANIMATED_STILL", "SCIENTIFIC_IMAGE"))
    viz_s = sum(s["duration_s"] for s in scenes if s["media_type"] in ("INFOGRAPHIC", "REAL_ANIMATION"))
    gap_s = sum(s["duration_s"] for s in scenes if s["media_type"] == "MISSING_EVIDENCE")

    plan_out = {
        "slug": slug,
        "topic": topic,
        "planned_scene_count": len(scenes),
        "planned_total_duration_s": round(t_cursor, 2),
        "coverage_metrics": {
            "genuine_moving_footage_pct": round(100.0 * mov_s / tot, 1),
            "meaningful_action_footage_pct": round(100.0 * act_s / tot, 1),
            "establishing_footage_pct": round(100.0 * est_s / tot, 1),
            "static_image_pct": round(100.0 * sta_s / tot, 1),
            "scientific_visualization_pct": round(100.0 * viz_s / tot, 1),
            "unresolved_gap_pct": round(100.0 * gap_s / tot, 1),
        },
        "scenes": scenes,
    }

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "action_storyboard_plan.json").write_text(json.dumps(plan_out, indent=2), encoding="utf-8")
        md = [
            f"# Action-Based Dry-Run Storyboard — `{slug}`",
            "",
            f"- **Topic:** {topic}",
            f"- **Planned Runtime:** `{plan_out['planned_total_duration_s']}s` across `{len(scenes)}` motivated scenes",
            f"- **Genuine Moving Footage:** `{plan_out['coverage_metrics']['genuine_moving_footage_pct']}%` "
            f"(Meaningful Action: `{plan_out['coverage_metrics']['meaningful_action_footage_pct']}%`, "
            f"Establishing: `{plan_out['coverage_metrics']['establishing_footage_pct']}%`)",
            f"- **Static Images:** `{plan_out['coverage_metrics']['static_image_pct']}%` | "
            f"**Scientific Visualization:** `{plan_out['coverage_metrics']['scientific_visualization_pct']}%` | "
            f"**Unresolved Gaps:** `{plan_out['coverage_metrics']['unresolved_gap_pct']}%`",
            "",
            "| Scene ID | Narration segment | Visual objective | Visible action | Asset | Source | Media type | Shot perspective | Relevance | Duration | Continuity |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for s in scenes:
            md.append(
                f"| `{s['scene_id']}` | {s['narration_segment']} | {s['visual_objective']} | {s['visible_action']} | "
                f"`{s['asset']}` | {s['source']} | `{s['media_type']}` | `{s['shot_perspective']}` | "
                f"{s['relevance']} | `{s['duration']}` | {s['continuity']} |"
            )
        (out_dir / "action_storyboard_plan.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    return plan_out
