#!/usr/bin/env python3
"""
Step 1: Declarative Versioned Episode Manifest Schema (`pow_studio.schema` v6.0).

Defines strongly typed Pydantic v2 models for declarative YAML/JSON documentary
production, integrating with reusable Category Production Profiles (`DocumentaryStyleProfile`)
and Custom Voice Studio (`VoiceDirectionProfile`), while preserving 100% backward
compatibility with `v3`/`v4` manifests and `legacy_v2` fallback:
- Versioned manifest metadata (`manifest_version`, `script_version`, `subtitle_version`)
- Narrative retention beats (`narrative_beat`, `viewer_question`, `new_information`, `visual_reveal`)
- Custom Voice Studio modes (`directed_tts`, `uploaded_narration`, `voice_reference`) + delivery tags
- Cinematic shot perspectives (`camera_perspective`), adaptive complexity, and 5-layer scene audio
- Multi-concept subject-first thumbnail specifications (`thumbnail_spec` + `thumbnail_concepts`)
- Non-destructive write protection across all completed channel outputs
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Optional

import yaml
from pydantic import BaseModel, Field, model_validator

from .style_profile import DocumentaryStyleProfile, load_style_profile

INSET_OR_DASHBOARD_SHOT_KINDS = {
    "still_window",
    "video_window",
    "study_card",
    "svs_flyover",
    "fig1_map",
    "fig1_sites",
    "microscopy_dual",
}

PROTECTED_COMPLETED_OUTPUT_DIRS = {
    # Legacy v2 projects
    "blood-falls-20261028",
    "blood-falls-20261028-v2-studio",
    "brine-pools-20261029",
    # Completed Hidden Earth episodes (DO NOT OVERWRITE)
    "blood-falls-v3-documentary",
    "brine-pools-v4-documentary",
    "forbidden-zones-earth-v4-documentary",
    "gemstone-mine-secrets-v4-documentary",
    "lava-cave-gold-v4-documentary",
    "unreal-places-earth-v4-documentary",
    # Completed Space & Universe episodes (DO NOT OVERWRITE)
    "day-in-the-life-of-an-astronaut",
    "fermi-paradox-v4-documentary",
    "how-high-could-you-jump-on-other-planets",
    "mars-helicopter-1-percent-air",
    "venus-hotter-than-mercury",
}

CameraPerspectiveLiteral = Literal[
    "extreme_wide",
    "wide",
    "medium",
    "close_up",
    "macro",
    "aerial",
    "first_person_pov",
    "scientific_fieldwork",
    "satellite_or_telescope",
    "labeled_visualization",
]

NarrativeBeatLiteral = Literal[
    "opening_hook",
    "curiosity_gap",
    "evidence_and_discovery",
    "escalation",
    "payoff",
    "final_impression",
]

HookArchetypeLiteral = Literal[
    "surprising_visual",
    "unexpected_fact",
    "strong_contrast",
    "paradox",
    "credible_mystery",
    "unusual_real_event",
]

AudioLayerLiteral = Literal[
    "narration",
    "music",
    "ambience",
    "natural_sounds",
    "cinematic_sfx",
]


class EditorialFormulaSpec(BaseModel):
    """Enforces the channel's signature Two-Layer Mystery + Caveat structure."""

    hook_max_start_s: float = Field(default=2.0, description="Opening visual & verbal hook must engage within 2s")
    layer2_pivot_seg_id: str = Field(description="Segment ID where surface explanation pivots to deeper/recent research")
    scientific_caveat_seg_id: str = Field(description="Segment ID stating explicit scientific limitations/caveats")
    min_real_evidence_ratio: float = Field(default=0.80, ge=0.50, le=1.00)


class CoverVariantSpec(BaseModel):
    """Legacy v2 burned-in card cover specification (disabled by default in v3+)."""

    variant_id: str = Field(description="e.g. 'A' or 'B'")
    cover_text: str = Field(min_length=2, max_length=28, description="Short high-contrast hook text on Frame 0")
    kicker_text: str = Field(default="PROOF OF WONDER  •  HIDDEN EARTH")
    accent_rgb: tuple[int, int, int] = Field(default=(228, 72, 52))


class ThumbnailSpecModel(BaseModel):
    """Subject-first documentary thumbnail concept specification (zero boxes/rings)."""

    concept_id: str = Field(default="A", description="Concept identifier, e.g. 'A', 'B', 'C'")
    concept_rationale: str = Field(default="", description="Editorial hypothesis behind this thumbnail concept")
    src_file: Optional[str] = Field(default=None, description="Asset filename in register; defaults to opening shot asset")
    src_time_s: Optional[float] = Field(default=None, description="Timestamp (s) if `src_file` is a video")
    crop_box: Optional[tuple[int, int, int, int]] = None
    headline_text: str = Field(
        default="",
        description="High-impact <=6-word hook headline (use '|' or newline for explicit 2-line split); empty for pure subject",
    )
    kicker_text: str = Field(default="", description="Optional crisp <=6-word uppercase context eyebrow (no box)")
    accent_line_index: int = Field(default=1, ge=0, le=2, description="Which stacked headline line receives accent_rgb")
    accent_rgb: tuple[int, int, int] = Field(default=(255, 212, 59), description="High-contrast focal line RGB")
    clarity_boost: bool = Field(default=True, description="Apply optical dehaze, S-curve & micro-contrast pop")
    shadow_lift: float = Field(
        default=0.0,
        ge=0.0,
        le=0.60,
        description="Optional selective shadow/midtone lift (0.0-0.60) for night-sky, cave, or deep-sea foreground subjects",
    )
    alt_headlines: list[str] = Field(default_factory=list, description="Optional alternative hook texts exported as A/B covers")
    cx: Optional[float] = Field(default=None, ge=0.05, le=0.95)
    cy: Optional[float] = Field(default=None, ge=0.05, le=0.95)
    zoom: float = Field(default=1.02, ge=1.0, le=1.5)
    text_position: Literal["auto", "top", "bottom"] = "auto"


class NarrationSegmentSpec(BaseModel):
    seg_id: str
    text: str
    tts_text: Optional[str] = Field(
        default=None,
        description="Optional phonetic/spoken override sent to TTS while keeping canonical `text` in subtitles",
    )
    annotated_text: Optional[str] = Field(
        default=None,
        description="Optional pre-generation bracket-annotated text block ([DELIVERY: ...], [PACE: ...], [EMPHASIS: ...], [PAUSE AFTER: ...])",
    )
    delivery: Optional[str] = Field(
        default=None,
        description="Optional Voice Studio delivery tag (e.g. 'MYSTERIOUS', 'SURPRISED BUT CONTROLLED', 'CINEMATIC REVEAL')",
    )
    emotional_tone: Optional[str] = Field(
        default=None,
        description="Intended emotional tone (e.g. 'curious_restraint', 'authoritative_clarity', 'controlled_wonder', 'reflective')",
    )
    pace: Optional[Literal["SLOW", "NATURAL", "MODERATE", "FAST"]] = None
    energy: Optional[int] = Field(default=None, ge=1, le=5, description="Delivery intensity from 1 to 5")
    emotional_intensity: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Fine intensity scalar 0.0-1.0")
    pitch_direction: Optional[Literal["falling", "steady", "gentle_rise", "low_intimate"]] = None
    sentence_rhythm: Optional[Literal["measured", "flowing", "deliberate_staccato", "reflective_slow"]] = None
    pause_before_s: float = Field(default=0.0, ge=0.0, le=1.5, description="Optional brief anticipatory pause before segment")
    pronunciation_overrides: dict[str, str] = Field(default_factory=dict, description="Segment-specific phonetic overrides")
    vocal_consistency: Literal["locked", "expressive_bounded"] = "locked"
    rate: str = Field(default="+0%", description="Explicit prosody rate override, e.g. '+0%', '-3%', '+2%'")
    pitch: str = Field(default="+0Hz", description="Explicit prosody pitch contour, e.g. '+0Hz', '-1Hz'")
    pause_after_s: float = Field(default=0.34, ge=0.05, le=3.0)
    emphasis_words: list[str] = Field(
        default_factory=list,
        description="Scientific keywords/phrases emphasized in delivery and optionally highlighted on vocal onset",
    )
    # Retention & Narrative Engineering fields (Part 2, Sections 3.2-3.4)
    narrative_beat: Optional[NarrativeBeatLiteral] = None
    viewer_question: str = Field(default="", description="Active curiosity question in the viewer's mind")
    new_information: str = Field(default="", description="Concrete new fact, mechanism, or discovery delivered")
    visual_reveal: str = Field(default="", description="Key authentic visual revealed during this segment")
    emotional_direction: str = Field(default="", description="Intended emotional tone (e.g. 'Hushed intrigue -> awe')")
    retention_purpose: str = Field(default="", description="Why this beat sustains viewer momentum")


class SoundbiteSpec(BaseModel):
    bite_id: str
    insert_after_seg_id: str
    audio_file: str
    src_start_s: float
    src_end_s: float
    speaker_name: str
    speaker_role: str
    context_label: str
    verbatim_transcript: str
    pause_after_s: float = 0.32


class SfxCueSpec(BaseModel):
    sfx_name: str = Field(description="Name of CC0/PD stem in assets/sfx_cc0/ or audio_asset_registry, e.g. 'glacial_sub_drop'")
    anchor_type: Literal["time_s", "shot_start", "seg_start"] = "shot_start"
    anchor_ref: str = Field(description="Shot ID, Segment ID, or float seconds string")
    offset_s: float = 0.0
    gain_db: float = Field(default=-24.0, le=-10.0, description="Always subtle beneath speech")
    purpose: str = Field(default="", description="Explicit narrative/visual reason this sound effect exists")
    visual_event: str = Field(default="", description="Visible on-screen event synchronized with this sound")


class ScaleCalloutAnnotation(BaseModel):
    """Explicit opt-in hairline ring annotation (disabled by default in pow_documentary_v3+)."""

    kind: Literal["scale_ring"] = "scale_ring"
    norm_x: float = Field(ge=0.05, le=0.95)
    norm_y: float = Field(ge=0.08, le=0.85)
    ring_radius_px: int = Field(default=38, ge=16, le=120)
    label_title: str
    label_subtitle: str = ""
    side: Literal["left", "right", "top"] = "right"
    reveal_delay_s: float = 0.35


class LocatorPinAnnotation(BaseModel):
    """Explicit opt-in corner map card (disabled by default in pow_documentary_v3+)."""

    kind: Literal["antarctica_locator", "region_locator"] = "antarctica_locator"
    map_region: Literal["antarctica", "gulf_of_mexico", "red_sea"] = "antarctica"
    place_title: str = "TAYLOR GLACIER"
    coords_label: str = "77.7°S, 162.3°E"
    pin_u: float = Field(default=0.58, ge=0.0, le=1.0)
    pin_v: float = Field(default=0.73, ge=0.0, le=1.0)
    reveal_delay_s: float = 0.25


class ShotSpecModel(BaseModel):
    sid: str
    start_s: float = Field(ge=0.0)
    end_s: float = Field(gt=0.0)
    kind: Literal[
        "triptych_hook",
        "still_parallax_25d",
        "still_full",
        "still_window",
        "video_full",
        "video_window",
        "study_card",
        "svs_flyover",
        "diagram",
        "fig1_map",
        "fig1_sites",
        "microscopy_dual",
    ]
    src_file: str
    secondary_src_file: Optional[str] = None
    tertiary_src_file: Optional[str] = None
    triptych_labels: list[str] = Field(
        default_factory=list,
        description="Optional 3 sleek micro-labels for triptych_hook bands",
    )
    triptych_centers_y: tuple[float, float, float] = Field(
        default=(0.45, 0.52, 0.58),
        description="Normalized vertical centers (cy) for top, middle, and bottom triptych bands",
    )
    camera_perspective: CameraPerspectiveLiteral = Field(
        default="wide",
        description="Cinematic shot perspective classification for visual variety planning",
    )
    visual_complexity: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="Visual detail complexity driving adaptive scene duration",
    )
    spoken_importance: Literal["context", "key_fact", "central_reveal"] = Field(
        default="key_fact",
        description="Editorial weight of narration spoken over this shot",
    )
    camera_movement: Literal["static", "gentle_drift", "tracking", "aerial_sweep", "handheld_field"] = Field(
        default="gentle_drift",
        description="Camera motion character inside source clip or reframing trajectory",
    )
    scene_audio_layers: list[AudioLayerLiteral] = Field(
        default_factory=lambda: ["narration", "music", "ambience", "natural_sounds"],
        description="Active soundscape stems appropriate for this scene",
    )
    crop_box: Optional[tuple[int, int, int, int]] = None
    reframe_mode: Literal["manual", "auto_salient", "keyframed"] = "manual"
    reframe_keyframes: list[tuple[float, float, float]] = Field(
        default_factory=list,
        description="Optional [(norm_u, cx, cy), ...] trajectory for smooth subject tracking",
    )
    crop_rationale: str = Field(default="", description="Why this 9:16 crop preserves essential subject clarity")
    cx0: float = 0.50
    cy0: float = 0.50
    cx1: float = 0.50
    cy1: float = 0.50
    z0: float = 1.02
    z1: float = 1.04
    contrast_gain: float = Field(
        default=1.0,
        ge=0.7,
        le=1.6,
        description="Optional subtle linear contrast normalization",
    )
    shadow_lift: float = Field(
        default=0.0,
        ge=0.0,
        le=0.55,
        description="Optional selective shadow/midtone lift (0.0-0.55) to preserve foreground human scale",
    )
    parallax_px: float = Field(default=0.0, ge=0.0, le=36.0)
    src_in: float = 0.0
    secondary_src_in: float = 0.0
    tertiary_src_in: float = 0.0
    nat_audio_gain_db: Optional[float] = Field(
        default=None,
        le=-3.0,
        description="Optional diegetic field-audio gain (dB) extracted directly from this video shot's real audio track",
    )

    # Pacing & Transition controls
    transition_in: Literal["cut", "dissolve"] = "cut"
    transition_duration_s: float = Field(default=0.0, ge=0.0, le=1.5)
    transition_reason: str = Field(default="Clean cut aligned to narration boundary")

    # Restrained context, cinema chapter stamps & legacy fields
    chapter_stamp: Optional[str] = Field(default=None)
    chapter_stamp_duration_s: float = Field(default=2.6, ge=0.8, le=6.0)
    context_note: Optional[str] = Field(
        default=None,
        description="Optional brief plain-text context (<= 7 words, borderless) only when essential for comprehension/honesty",
    )
    is_talking_head: bool = Field(
        default=False,
        description="True if footage depicts a muted presenter/interviewee speaking with lip motion",
    )
    label: Optional[str] = None
    callout: Optional[str] = None
    card_badge: Optional[str] = None
    card_title: Optional[str] = None
    card_subtitle: Optional[str] = None
    card_bullets: list[str] = Field(default_factory=list)
    card_bg_white: bool = True
    scale_annotation: Optional[ScaleCalloutAnnotation] = None
    locator_annotation: Optional[LocatorPinAnnotation] = None

    # Visual-to-Narration & Scientific Integrity metadata
    is_real_evidence: bool = True
    has_human_interaction: bool = Field(
        default=False,
        description="True when real footage/photo depicts scientists or people actively interacting with the phenomenon, field site, or samples",
    )
    associated_seg_id: Optional[str] = Field(default=None, description="Explicit narration segment ID supported by this shot")
    associated_narration_concept: str = Field(default="", description="Exact narration sentence/concept supported by this shot")
    editorial_rationale: str = Field(default="", description="Why this shot belongs at this exact point in the story")
    subject_match_kind: Literal[
        "direct_subject",
        "direct_location",
        "contextual_fieldwork",
        "representative_organism_microscopy",
        "illustrative_diagram",
    ] = "direct_subject"
    scientific_claim_status: Literal[
        "verified_fact",
        "credible_hypothesis",
        "unresolved_question",
        "contextual_observation",
        "illustrative_visualization",
    ] = "verified_fact"
    # Footage-First v8.0 Action-Based Storytelling & Repetition-Control metadata
    visual_objective: str = Field(default="", description="What the viewer should understand from this shot")
    visible_action: str = Field(default="", description="Concrete visible action or physical process shown in frame")
    continuity_note: str = Field(default="", description="Relationship with preceding and following shots")
    progression_type: Optional[str] = Field(
        default=None,
        description="Meaningful progression dimension ('new_action', 'new_information', 'new_perspective', 'new_subject', 'new_evidence', 'new_process_stage', 'environment_change')",
    )
    essential_historical_or_scientific_evidence: bool = Field(
        default=False,
        description="True when a historical or scientific still photograph genuinely requires extended viewing",
    )
    intentional_callback: bool = Field(
        default=False,
        description="True when returning to an earlier image/clip serves a deliberate narrative payoff",
    )
    callback_purpose: str = Field(default="", description="Narrative justification for an intentional visual callback")
    disable_artificial_still_motion: Optional[bool] = Field(
        default=None,
        description="Hold still photographs cleanly without artificial zoom/pan/parallax when True",
    )
    explicit_analog_comparison: bool = Field(
        default=False,
        description="True ONLY when narration explicitly discloses that a terrestrial/laboratory analog site is shown",
    )
    story_beat: str
    visual_desc: str


class CaptionGroupSpec(BaseModel):
    seg_id: str
    first_word_idx: int = Field(ge=0)
    last_word_idx: int = Field(ge=0)
    text: str


SourceMediaTypeLiteral = Literal[
    "REAL_VIDEO_ACTION",
    "REAL_VIDEO_ESTABLISHING",
    "REAL_TIME_LAPSE",
    "STILL_PHOTO",
    "ANIMATED_STILL",
    "SCIENTIFIC_IMAGE",
    "INFOGRAPHIC",
    "REAL_ANIMATION",
    "AI_GENERATED",
    "REENACTMENT",
]


class AssetLicenseSpec(BaseModel):
    local_file: str
    title: str
    creator_agency: str
    source_page_url: str
    direct_media_url: str
    license: str
    license_url: str
    required_attribution: str
    media_type: Optional[Literal["video", "photo", "diagram", "audio"]] = None
    source_media_class: Optional[SourceMediaTypeLiteral] = Field(
        default=None,
        description="Explicit 10-category source media classification preserved across rendering",
    )
    original_media_file: Optional[str] = Field(
        default=None,
        description="Original pre-transcode filename (e.g., original .jpg if pre-rendered to .mp4); prevents promoting a still photo to video",
    )
    canonical_source_id: Optional[str] = Field(
        default=None,
        description="Canonical source shoot/asset identifier used to detect multi-crops and sub-clip splits",
    )
    depicts_meaningful_action: Optional[bool] = None
    depicted_subject: str = ""
    depicted_action: str = ""
    depicted_location: str = ""
    historical_era: Optional[str] = None
    priority_tier: int = Field(
        default=1,
        ge=1,
        le=6,
        description="1=Subject/location video, 2=Close-up/wide video, 3=Fieldwork video, 4=Observation video, 5=Real photo, 6=Diagram",
    )
    intended_use: str = Field(default="Documentary visual evidence")
    is_first_party_original: bool = False
    allow_cropping: bool = True

    @model_validator(mode="after")
    def infer_media_type_if_omitted(self) -> "AssetLicenseSpec":
        from .media_classifier import STILL_EXTENSIONS, VIDEO_EXTENSIONS, infer_asset_source_media_class

        suf = Path(self.local_file).suffix.lower()
        orig_suf = Path(self.original_media_file).suffix.lower() if self.original_media_file else ""

        # Hard lineage rule (Part 2 Section 4): A JPEG/PNG converted into MP4 must remain a still photograph!
        if orig_suf in STILL_EXTENSIONS:
            self.media_type = "photo"
            if self.priority_tier == 1:
                self.priority_tier = 5
            if self.source_media_class is None or self.source_media_class in (
                "REAL_VIDEO_ACTION",
                "REAL_VIDEO_ESTABLISHING",
                "REAL_TIME_LAPSE",
            ):
                self.source_media_class = "ANIMATED_STILL" if suf in VIDEO_EXTENSIONS else "STILL_PHOTO"

        if self.media_type is None:
            if self.source_media_class in ("STILL_PHOTO", "ANIMATED_STILL", "SCIENTIFIC_IMAGE"):
                self.media_type = "photo"
                if self.priority_tier == 1:
                    self.priority_tier = 5
            elif self.source_media_class in ("INFOGRAPHIC", "REAL_ANIMATION"):
                self.media_type = "diagram"
                if self.priority_tier == 1:
                    self.priority_tier = 6
            elif self.is_first_party_original and suf in (".mp4", ".mov", ".webm"):
                self.media_type = "diagram"
                if self.priority_tier == 1:
                    self.priority_tier = 6
            elif suf in (".mp4", ".mov", ".webm", ".mkv", ".m4v", ".ogv"):
                self.media_type = "video"
            elif suf in (".wav", ".mp3", ".ogg", ".flac", ".m4a"):
                self.media_type = "audio"
            else:
                self.media_type = "photo"
                if self.priority_tier == 1:
                    self.priority_tier = 5

        if self.media_type != "audio" and self.source_media_class is None:
            self.source_media_class = infer_asset_source_media_class(self, probe_pixels=False)  # type: ignore[assignment]
        elif self.media_type == "photo" and self.source_media_class in (
            "REAL_VIDEO_ACTION",
            "REAL_VIDEO_ESTABLISHING",
            "REAL_TIME_LAPSE",
        ):
            self.source_media_class = "ANIMATED_STILL" if suf in VIDEO_EXTENSIONS else "STILL_PHOTO"
        return self


class FactualReferenceSpec(BaseModel):
    citation: str
    url: str
    doi: Optional[str] = None
    supported_claims: str


class HookCandidateSpec(BaseModel):
    """Structured opening hook candidate evaluated in Stage 2 Story Studio."""

    hook_id: str
    archetype: HookArchetypeLiteral
    spoken_line: str
    opening_visual: str
    src_file: Optional[str] = None
    promise_fulfilled_in_seg_id: Optional[str] = None
    rationale: str = ""


class EpisodeManifest(BaseModel):
    manifest_version: str = Field(default="6.0", description="Versioned production manifest schema")
    script_version: str = Field(default="1.0", description="Approved script version identifier")
    subtitle_version: str = Field(default="1.0", description="Subtitle layout/phrasing version identifier")
    channel_name: str = "Proof of Wonder"
    playlist: str = "Hidden Earth"
    topic: str = Field(default="", description="Core scientific/documentary topic")
    slug: str
    style_profile: str = Field(
        default="pow_documentary_v3",
        description="Reusable Production Profile ('cinematic_science_documentary', 'mysterious_earth_exploration', 'space_discovery', 'deep_ocean_documentary', 'pow_documentary_v3', 'legacy_v2', or YAML path)",
    )
    style_overrides: dict[str, Any] = Field(default_factory=dict)
    primary_title: str
    alternative_title: str
    youtube_description: str
    hashtags: list[str]
    opening_hook_type: HookArchetypeLiteral = "surprising_visual"
    hook_candidates: list[HookCandidateSpec] = Field(default_factory=list)
    target_duration_min_s: float = 20.0
    target_duration_max_s: float = 240.0
    adaptive_duration_mode: bool = Field(
        default=True,
        description="Allow actual approved narration duration to govern video timeline without forcing a fixed template length",
    )
    enforce_target_duration_bounds: bool = Field(
        default=False,
        description="Only enforce strict target_duration_min_s..max_s when an episode explicitly locks hard duration bounds",
    )
    legacy_v6_fallback: bool = Field(
        default=False,
        description="Run legacy v6 audio/scene behavior when requested as a fallback",
    )
    enable_intelligent_scene_editing: bool = Field(
        default=True,
        description="Run Keep/Replace/Merge/Remove scene optimization against finalized narration",
    )
    adaptive_audio_profile: Literal[
        "auto",
        "minimal_documentary",
        "immersive_exploration",
        "mystery_and_discovery",
        "scientific_explanation",
    ] = "auto"

    # Custom Voice Studio & Advanced Voice Direction (Part 2 & Part 4)
    tts_provider: Literal["auto", "elevenlabs", "edge_tts"] = "auto"
    elevenlabs_model_id: str = Field(
        default="eleven_multilingual_v2",
        description="ElevenLabs model ('eleven_multilingual_v2', 'eleven_v3', 'eleven_turbo_v2_5', 'eleven_flash_v2_5')",
    )
    elevenlabs_voice_id: str = Field(
        default="",
        description="Optional ElevenLabs voice_id when ELEVENLABS_API_KEY is configured",
    )
    prefer_single_pass_narration: Optional[bool] = Field(
        default=None,
        description="Prefer generating complete narration in one request when voice direction is uniform/compatible",
    )
    voice_input_mode: Literal["directed_tts", "uploaded_narration", "voice_reference"] = "directed_tts"
    voice_direction_profile: Optional[str] = Field(
        default=None,
        description="Voice Direction Profile preset or YAML path (e.g. 'mysterious_discovery', 'cinematic_documentary')",
    )
    uploaded_narration_file: Optional[str] = Field(
        default=None,
        description="Mode A: Path to user-uploaded complete narration recording (.wav/.mp3/.m4a/.flac)",
    )
    uploaded_narration_clean_noise: bool = Field(
        default=False,
        description="Mode A: Apply gentle highpass + FFT noise floor reduction when needed",
    )
    voice_reference_file: Optional[str] = Field(
        default=None,
        description="Mode B: Path to user-uploaded voice reference audio sample",
    )
    voice_owner_consent: bool = Field(
        default=False,
        description="Mode B: Explicit voice owner consent confirmation (required before reference voice adaptation/cloning)",
    )
    annotated_voice_script_file: Optional[str] = Field(
        default=None,
        description="Optional path to external bracket-annotated voice direction script (.txt/.md)",
    )
    voice: str = "en-GB-RyanNeural"
    tts_pronunciations: dict[str, str] = Field(
        default_factory=dict,
        description="Whole-word phonetic respelling map for TTS",
    )

    # 5-Layer Sound Engineering
    ambience_preset: Literal[
        "polar_glacial",
        "deep_space",
        "deep_ocean",
        "volcanic_abyss",
        "subterranean_earth",
        "scientific_discovery",
        "wildlife_field",
        "ancient_archaeology",
        "minimal_investigation",
        "none",
    ] = "polar_glacial"
    ambience_ducked_lufs_target: float = -26.5
    nat_sound_bed_file: Optional[str] = Field(
        default=None,
        description="Optional real expedition video/audio filename providing authentic speech-free location ambience",
    )
    nat_sound_bed_range_s: tuple[float, float] = Field(
        default=(1.0, 38.0),
        description="(start_s, end_s) clean speech-free field-recording slice inside nat_sound_bed_file",
    )
    nat_sound_gain_db: float = Field(
        default=-15.5,
        le=-6.0,
        description="Base gain (dB) for real location nat-sound bed before dynamic speech ducking",
    )
    closing_credits_line1: Optional[str] = None
    raw_assets_dir: str
    extra_assets_dirs: list[str] = Field(default_factory=list)
    output_dir: str
    editorial_formula: EditorialFormulaSpec
    thumbnail_spec: Optional[ThumbnailSpecModel] = None
    thumbnail_concepts: list[ThumbnailSpecModel] = Field(
        default_factory=list,
        description="Optional multi-concept thumbnail definitions for mobile comparison",
    )
    cover_variants: list[CoverVariantSpec] = Field(default_factory=list)
    narration_segments: list[NarrationSegmentSpec] = Field(min_length=2)
    soundbites: list[SoundbiteSpec] = Field(default_factory=list)
    sfx_cues: list[SfxCueSpec] = Field(default_factory=list)
    shots: list[ShotSpecModel] = Field(min_length=1)
    caption_groups: list[CaptionGroupSpec] = Field(default_factory=list)
    assets_register: list[AssetLicenseSpec] = Field(min_length=1)
    excluded_sources_notes: list[str] = Field(default_factory=list)
    factual_references: list[FactualReferenceSpec] = Field(min_length=1)

    def resolve_style_profile(self) -> DocumentaryStyleProfile:
        return load_style_profile(self.style_profile, self.style_overrides)

    def all_asset_search_dirs(self) -> list[Path]:
        dirs = [Path(self.output_dir) / "work_clips", Path(self.raw_assets_dir)]
        for extra in self.extra_assets_dirs:
            dirs.append(Path(extra))
        return dirs

    def assert_output_dir_writable(self, allow_overwrite_protected: bool = False) -> None:
        style = self.resolve_style_profile()
        if not style.qa.protect_existing_episode_outputs or allow_overwrite_protected:
            return
        out_p = Path(self.output_dir).resolve()
        has_completed_mp4 = any(out_p.glob("*.mp4")) if out_p.exists() else False
        if out_p.name in PROTECTED_COMPLETED_OUTPUT_DIRS and has_completed_mp4:
            raise RuntimeError(
                f"Non-destructive protection blocked writing into completed project folder '{out_p}'. "
                "Choose a new output_dir/slug (e.g. 'blood-falls-v6-studio-pilot') or pass allow_overwrite_protected=True."
            )

    @model_validator(mode="after")
    def validate_editorial_and_timeline_integrity(self) -> "EpisodeManifest":
        style = self.resolve_style_profile()
        seg_ids = {s.seg_id for s in self.narration_segments}
        if self.editorial_formula.layer2_pivot_seg_id not in seg_ids:
            raise ValueError(f"layer2_pivot_seg_id '{self.editorial_formula.layer2_pivot_seg_id}' not in narration_segments")
        if self.editorial_formula.scientific_caveat_seg_id not in seg_ids:
            raise ValueError(f"scientific_caveat_seg_id '{self.editorial_formula.scientific_caveat_seg_id}' not in narration_segments")

        if self.voice_input_mode == "voice_reference" and self.voice_reference_file and not self.voice_owner_consent:
            raise ValueError(
                "Mode B (`voice_reference`) requires explicit `voice_owner_consent: true` confirming authorization from the voice owner."
            )

        # Validate contiguous non-overlapping shots starting at 0.0
        if abs(self.shots[0].start_s - 0.0) > 1e-3:
            raise ValueError(f"First shot must start at 0.0s (got {self.shots[0].start_s})")
        for a, b in zip(self.shots, self.shots[1:]):
            if abs(a.end_s - b.start_s) > 0.02:
                raise ValueError(f"Shot gap/overlap between {a.sid} (end={a.end_s}) and {b.sid} (start={b.start_s})")
            if a.end_s <= a.start_s:
                raise ValueError(f"Invalid shot duration in {a.sid}")

        # Enforce full-screen vertical layout (no inset frames or dashboard cards unless allowed by style)
        if not style.composition.allow_inset_frames:
            for s in self.shots:
                if s.kind in INSET_OR_DASHBOARD_SHOT_KINDS:
                    raise ValueError(
                        f"Shot {s.sid} uses inset/dashboard layout '{s.kind}', which is forbidden by style profile "
                        f"'{style.profile_name}' (fill_canvas_edge_to_edge=True, allow_inset_frames=False). "
                        "Use full-screen 'video_full', 'still_full', or 'diagram'."
                    )

        # Enforce context-label restraint
        if style.overlays.allow_minimal_context_captions:
            ctx_shots = [s for s in self.shots if s.context_note]
            if len(ctx_shots) > style.overlays.max_context_labels_per_video:
                raise ValueError(
                    f"Manifest defines {len(ctx_shots)} context_note labels, exceeding max_context_labels_per_video="
                    f"{style.overlays.max_context_labels_per_video}."
                )
            for s in ctx_shots:
                wc = len((s.context_note or "").split())
                if wc > style.overlays.context_label_max_words:
                    raise ValueError(
                        f"Shot {s.sid} context_note '{s.context_note}' has {wc} words (max {style.overlays.context_label_max_words})."
                    )

        total_s = self.shots[-1].end_s
        real_s = sum((s.end_s - s.start_s) for s in self.shots if s.is_real_evidence)
        ratio = real_s / max(1e-6, total_s)
        if ratio < self.editorial_formula.min_real_evidence_ratio:
            raise ValueError(
                f"Real visual evidence ratio {ratio:.2%} is below minimum {self.editorial_formula.min_real_evidence_ratio:.0%}"
            )

        # Ensure every shot's src_file (and secondary/tertiary_src_file and thumbnail_spec.src_file) is registered
        reg_files = {a.local_file for a in self.assets_register}
        for s in self.shots:
            if s.src_file not in reg_files:
                raise ValueError(f"Shot {s.sid} uses unregistered asset '{s.src_file}'")
            if s.secondary_src_file and s.secondary_src_file not in reg_files:
                raise ValueError(f"Shot {s.sid} uses unregistered secondary asset '{s.secondary_src_file}'")
            if s.tertiary_src_file and s.tertiary_src_file not in reg_files:
                raise ValueError(f"Shot {s.sid} uses unregistered tertiary asset '{s.tertiary_src_file}'")
            if s.kind == "triptych_hook" and (not s.secondary_src_file or not s.tertiary_src_file):
                raise ValueError(f"Shot {s.sid} of kind 'triptych_hook' requires src_file, secondary_src_file, and tertiary_src_file")
        if style.overlays.allow_cinema_chapter_stamps:
            ch_shots = [s for s in self.shots if s.chapter_stamp]
            if len(ch_shots) > style.overlays.max_chapter_stamps_per_video:
                raise ValueError(
                    f"Manifest defines {len(ch_shots)} chapter_stamp headers, exceeding max_chapter_stamps_per_video="
                    f"{style.overlays.max_chapter_stamps_per_video}."
                )
        if self.thumbnail_spec and self.thumbnail_spec.src_file and self.thumbnail_spec.src_file not in reg_files:
            raise ValueError(f"thumbnail_spec uses unregistered asset '{self.thumbnail_spec.src_file}'")
        for tc in self.thumbnail_concepts:
            if tc.src_file and tc.src_file not in reg_files:
                raise ValueError(f"thumbnail_concepts[{tc.concept_id}] uses unregistered asset '{tc.src_file}'")
        return self

    @classmethod
    def from_yaml(cls, path: str | Path) -> "EpisodeManifest":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        # Auto-remap legacy machine-specific `/Applications/code/science-knowledge/youtube-shorts-channel` paths
        # to the active `CHANNEL_ROOT` so manifests work identically when cloned on any other machine.
        channel_root_str = str(Path(__file__).resolve().parents[2])
        legacy_prefix = "/Applications/code/science-knowledge/youtube-shorts-channel"

        def _remap_path(val: Any) -> Any:
            if not isinstance(val, str) or not val:
                return val
            if val.startswith(legacy_prefix):
                return channel_root_str + val[len(legacy_prefix) :]
            p = Path(val)
            if not p.is_absolute():
                cand = Path(channel_root_str) / p
                if cand.exists() or val.startswith(("output/", "assets/", "episodes/", "config/")):
                    return str(cand)
            return val

        for k in ("raw_assets_dir", "output_dir", "uploaded_narration_file", "voice_reference_file", "annotated_voice_script_file"):
            if k in data:
                data[k] = _remap_path(data[k])
        if "extra_assets_dirs" in data and isinstance(data["extra_assets_dirs"], list):
            data["extra_assets_dirs"] = [_remap_path(x) for x in data["extra_assets_dirs"]]

        # Auto-detect legacy v2 manifests that predate `style_profile` if they rely on v2 boxed shots or cover_variants
        if "style_profile" not in data:
            uses_inset = any(s.get("kind") in INSET_OR_DASHBOARD_SHOT_KINDS for s in data.get("shots", []))
            if uses_inset:
                data["style_profile"] = "legacy_v2"
        return cls.model_validate(data)


def resolve_timed_shots(manifest: EpisodeManifest, total_frames_30fps: int, fps: int = 30) -> list[ShotSpecModel]:
    """
    Return a copy of `manifest.shots` snapped to exact `1/fps` frame boundaries
    matching `total_frames_30fps` (`0.000ms` audio/video duration drift).
    """
    from .scene_editor import load_or_optimize_timed_shots

    optimized = load_or_optimize_timed_shots(manifest, total_frames_30fps, fps=fps)
    if optimized is not None:
        return optimized
    shots = [s.model_copy(deep=True) for s in manifest.shots]
    n = len(shots)
    t_manifest = shots[-1].end_s
    if total_frames_30fps <= n:
        return shots

    frame_bounds = [0]
    for k in range(1, n):
        scaled_f = int(round((shots[k].start_s / t_manifest) * total_frames_30fps))
        lo = frame_bounds[-1] + 1
        hi = total_frames_30fps - (n - k)
        frame_bounds.append(max(lo, min(hi, scaled_f)))
    frame_bounds.append(total_frames_30fps)

    for k, s in enumerate(shots):
        s.start_s = round(frame_bounds[k] / float(fps), 4)
        s.end_s = round(frame_bounds[k + 1] / float(fps), 4)
    return shots
