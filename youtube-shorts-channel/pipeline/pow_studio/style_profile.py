#!/usr/bin/env python3
"""
Centralized Reusable Documentary Production Style & Category Profile Engine (`pow_studio.style_profile` v6.0).

Loads channel-wide defaults from `youtube-shorts-channel/config/proof_of_wonder_style.yaml`
or category-specific reusable Production Profiles from `youtube-shorts-channel/config/profiles/*.yaml`
(`cinematic_science_documentary`, `mysterious_earth_exploration`, `space_discovery`,
`deep_ocean_documentary`), and merges any explicit per-episode overrides.

Controls storytelling structure, visual scoring weights, 9:16 subject-aware composition,
5-layer sound engineering, documentary subtitle typography, and QA thresholds without
forcing rigid cookie-cutter edits across episodes.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Literal, Optional

import yaml
from pydantic import BaseModel, Field

CHANNEL_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STYLE_YAML = CHANNEL_ROOT / "config" / "proof_of_wonder_style.yaml"
PROFILES_DIR = CHANNEL_ROOT / "config" / "profiles"


class OutputStyleConfig(BaseModel):
    aspect_ratio: str = "9:16"
    width: int = 1080
    height: int = 1920
    fps: int = 30
    video_codec_master: str = "libx264"
    video_crf_master: int = 15
    video_preset_master: str = "medium"
    video_profile: str = "high"
    pixel_format: str = "yuv420p"
    color_space: str = "bt709"
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    audio_sample_rate_hz: int = 48000
    audio_channels: int = 2
    target_loudness_lufs: float = -16.0


class CompositionStyleConfig(BaseModel):
    fill_canvas_edge_to_edge: bool = True
    allow_inset_frames: bool = False
    allow_blurred_pillarbox_backgrounds: bool = False
    allow_decorative_borders: bool = False
    never_stretch_aspect_ratio: bool = True
    never_hallucinate_outpainting: bool = True
    subject_reframe_mode: Literal["salient_auto_or_keyframed", "manual_only"] = "salient_auto_or_keyframed"
    keep_subject_above_subtitle_zone_y: int = 1480
    min_cropped_source_height_px: int = 540
    max_upscale_factor_warn: float = 2.35
    min_post_crop_laplacian_std: float = 4.2
    enable_synthetic_25d_parallax: bool = True
    still_max_zoom_delta: float = 0.055
    still_max_pan_delta_norm: float = 0.06


class OverlaysStyleConfig(BaseModel):
    show_source_banners_in_video: bool = False
    show_closing_credit_card_in_video: bool = False
    show_animated_circles_or_rings: bool = False
    show_locator_hud_cards: bool = False
    show_callout_warning_badges: bool = False
    show_dashboard_study_cards: bool = False
    burn_opening_cover_card_into_video: bool = False
    allow_minimal_context_captions: bool = True
    max_context_labels_per_video: int = 7
    context_label_max_words: int = 7
    allow_cinema_chapter_stamps: bool = True
    max_chapter_stamps_per_video: int = 5


class VisualScoringWeightsConfig(BaseModel):
    """Configurable 7-dimension asset scoring weights (Part 3, Section 4.2)."""

    direct_relevance: float = 0.30
    visual_clarity: float = 0.20
    authenticity: float = 0.20
    technical_quality: float = 0.10
    composition_potential: float = 0.10
    motion_storytelling: float = 0.05
    license_verification: float = 0.05
    min_direct_relevance_floor: float = 0.35


class AssetSelectionStyleConfig(BaseModel):
    zero_cost_budget_strict: bool = True
    location_authentic_mode: bool = False
    forbid_muted_talking_heads: bool = True
    target_moving_footage_ratio: float = 0.80
    max_still_photo_ratio: float = 0.15
    max_single_still_duration_s: float = 5.5
    forbid_consecutive_still_shots: bool = True
    forbid_repeated_same_image_zoom: bool = True
    prefer_human_fieldwork_interaction: bool = True
    min_human_interaction_shots: int = 3
    min_distinct_perspectives: int = 4
    min_authentic_evidence_ratio: float = 0.85
    max_illustrative_diagram_ratio: float = 0.18
    scoring_weights: VisualScoringWeightsConfig = Field(default_factory=VisualScoringWeightsConfig)
    priority_hierarchy: list[str] = Field(
        default_factory=lambda: [
            "1_actual_subject_or_human_interaction_with_phenomenon_video",
            "2_relevant_real_world_closeup_or_wide_video",
            "3_genuine_hands_on_scientific_fieldwork_or_expedition_video",
            "4_authentic_scientific_observation_or_experiment_video",
            "5_real_photograph_only_briefly_when_video_unavailable",
            "6_minimal_clearly_labeled_scientific_diagram",
        ]
    )
    max_uses_per_asset: int = 2
    max_duration_share_per_asset: float = 0.32
    require_narration_alignment_audit: bool = True
    require_scientific_claim_status: bool = True
    allowed_commercial_licenses: list[str] = Field(
        default_factory=lambda: [
            "Public Domain",
            "CC0",
            "CC BY",
            "100% Original First-Party Graphic",
        ]
    )
    auto_append_credits_to_youtube_description: bool = True


class NarrativeRetentionStyleConfig(BaseModel):
    """Configurable storytelling & retention architecture (Part 2, Sections 3.1-3.4)."""

    category_focus: str = "Evidence-based scientific & natural wonders"
    default_target_duration_range_s: tuple[float, float] = (70.0, 90.0)
    preferred_beat_structure: list[str] = Field(
        default_factory=lambda: [
            "opening_hook",
            "curiosity_gap",
            "evidence_and_discovery",
            "escalation",
            "payoff",
            "final_impression",
        ]
    )
    preferred_hook_archetypes: list[str] = Field(
        default_factory=lambda: [
            "surprising_visual",
            "paradox",
            "credible_mystery",
            "unexpected_fact",
        ]
    )
    max_info_drought_s: float = 14.5
    min_central_payoff_time_fraction: float = 0.30
    forbid_generic_channel_intro: bool = True
    forbid_generic_subscribe_outro: bool = True


class PacingStyleConfig(BaseModel):
    narration_first_required: bool = True
    adaptive_duration_enabled: bool = True
    reference_shot_duration_range_s: tuple[float, float] = (3.6, 7.2)
    min_shot_duration_s: float = 2.4
    max_shot_duration_s: float = 15.0
    establishing_wide_bonus_s: float = 0.9
    high_complexity_bonus_s: float = 0.8
    prefer_sentence_and_clause_boundaries: bool = True
    speech_pause_snap_tolerance_s: float = 0.35
    default_transition: Literal["cut", "dissolve"] = "cut"
    allowed_transitions: list[str] = Field(default_factory=lambda: ["cut", "dissolve"])
    dissolve_duration_s: float = 0.60
    dissolve_range_s: tuple[float, float] = (0.45, 1.00)
    max_dissolve_fraction_of_cuts: float = 0.45


class ColorScienceStyleConfig(BaseModel):
    enable_filmic_grade: bool = True
    cast_tame_strength: float = 0.22
    luma_grain_sigma: float = 2.3


class ViralRetentionStyleConfig(BaseModel):
    max_opening_still_duration_s: float = 2.3
    max_hook_first_sentence_words: int = 18
    max_spoken_sentence_words: int = 24
    block_ai_cliche_phrases: bool = True
    block_jargon_lists: bool = True
    enforce_seamless_loop_tail: bool = True
    max_ending_tail_pause_s: float = 0.55


class SoundDesignStyleConfig(BaseModel):
    default_voice: str = "en-GB-RyanNeural"
    default_voice_profile: str = "cinematic_documentary"
    scene_audio_profile: Literal[
        "polar_glacial",
        "subterranean_earth",
        "space_vacuum_restrained",
        "deep_ocean_abyss",
        "volcanic_abyss",
        "scientific_discovery",
        "wildlife_field",
    ] = "scientific_discovery"
    enable_5layer_mixing: bool = True
    enable_broadcast_vocal_mastering: bool = True
    enable_diegetic_nat_sound: bool = True
    forbid_fake_space_transmissions: bool = True
    studio_room_tone_dbfs: float = -52.0
    target_bed_lufs: float = -26.5
    music_layer_gain_db: float = -20.5
    ambience_layer_gain_db: float = -21.5
    natural_sounds_layer_gain_db: float = -15.5
    cinematic_sfx_layer_gain_db: float = -25.0
    music_duck_under_speech_db: float = -10.5
    min_audible_bed_margin_lu: float = 8.5
    max_audible_bed_margin_lu: float = 16.5
    min_natural_dynamics_lra_lu: float = 1.4
    min_speech_crest_factor_db: float = 9.5
    max_true_peak_dbtp: float = -1.2
    max_unintended_silence_s: float = 1.15


class SubtitlesStyleConfig(BaseModel):
    enabled: bool = True
    font_size_px: int = 48
    line_height_px: int = 60
    max_lines_per_cue: int = 2
    max_line_width_px: int = 880
    vertical_center_y_px: int = 1515
    style: Literal[
        "cinema_boxless",
        "minimal_editorial",
        "scientific_plain",
        "clean_scrim",
        "legacy_pill",
    ] = "cinema_boxless"
    scrim_rgba: tuple[int, int, int, int] = (6, 10, 18, 186)
    text_rgba: tuple[int, int, int, int] = (252, 253, 255, 255)
    stroke_width_px: int = 4
    enable_keyword_color_flash: bool = True
    emphasis_mode: Literal["color_accent", "subtle_warm", "none"] = "color_accent"
    word_by_word_animation: bool = False
    min_first_cue_start_s: float = 0.08


class OpeningAndThumbnailStyleConfig(BaseModel):
    max_central_subject_delay_s: float = 1.2
    forbid_intro_logos_and_title_cards: bool = True
    thumbnail_aspect_ratio: str = "9:16"
    thumbnail_subject_first: bool = True
    thumbnail_text_mode: Literal["none", "minimal_headline", "cinema_hook", "legacy_card"] = "cinema_hook"
    thumbnail_max_words: int = 6
    thumbnail_concepts_count: int = 3
    thumbnail_forbid_boxes_badges_rings: bool = True
    thumbnail_max_bytes: int = 1_950_000


class QAStyleConfig(BaseModel):
    require_exact_dimensions_and_fps: bool = True
    require_zero_black_frames: bool = True
    require_full_canvas_coverage_audit: bool = True
    max_letterbox_or_border_band_px: int = 6
    require_overlay_cleanliness_audit: bool = True
    min_whisper_normalized_match_ratio: float = 0.96
    min_wcag_caption_contrast_ratio: float = 7.0
    protect_existing_episode_outputs: bool = True
    export_visual_contact_sheets: bool = True


class DocumentaryStyleProfile(BaseModel):
    profile_name: str = "pow_documentary_v3"
    profile_version: str = "6.0.0"
    description: str = "Proof of Wonder Authentic Full-Screen Documentary Profile"
    output: OutputStyleConfig = Field(default_factory=OutputStyleConfig)
    narrative_retention: NarrativeRetentionStyleConfig = Field(default_factory=NarrativeRetentionStyleConfig)
    composition: CompositionStyleConfig = Field(default_factory=CompositionStyleConfig)
    color_science: ColorScienceStyleConfig = Field(default_factory=ColorScienceStyleConfig)
    overlays: OverlaysStyleConfig = Field(default_factory=OverlaysStyleConfig)
    asset_selection: AssetSelectionStyleConfig = Field(default_factory=AssetSelectionStyleConfig)
    viral_retention: ViralRetentionStyleConfig = Field(default_factory=ViralRetentionStyleConfig)
    sound_design: SoundDesignStyleConfig = Field(default_factory=SoundDesignStyleConfig)
    pacing: PacingStyleConfig = Field(default_factory=PacingStyleConfig)
    subtitles: SubtitlesStyleConfig = Field(default_factory=SubtitlesStyleConfig)
    opening_and_thumbnail: OpeningAndThumbnailStyleConfig = Field(default_factory=OpeningAndThumbnailStyleConfig)
    qa: QAStyleConfig = Field(default_factory=QAStyleConfig)


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = deepcopy(v)
    return out


LEGACY_V2_PROFILE_DICT: dict[str, Any] = {
    "profile_name": "legacy_v2",
    "profile_version": "2.1.0",
    "composition": {
        "fill_canvas_edge_to_edge": False,
        "allow_inset_frames": True,
        "allow_blurred_pillarbox_backgrounds": True,
        "allow_decorative_borders": True,
        "enable_synthetic_25d_parallax": True,
        "still_max_zoom_delta": 0.14,
        "still_max_pan_delta_norm": 0.15,
    },
    "overlays": {
        "show_source_banners_in_video": True,
        "show_closing_credit_card_in_video": True,
        "show_animated_circles_or_rings": True,
        "show_locator_hud_cards": True,
        "show_callout_warning_badges": True,
        "show_dashboard_study_cards": True,
        "burn_opening_cover_card_into_video": True,
    },
    "asset_selection": {
        "target_moving_footage_ratio": 0.15,
        "max_still_photo_ratio": 0.90,
        "max_single_still_duration_s": 12.0,
        "forbid_consecutive_still_shots": False,
        "prefer_human_fieldwork_interaction": False,
        "min_human_interaction_shots": 0,
        "require_narration_alignment_audit": False,
        "require_scientific_claim_status": False,
    },
    "subtitles": {
        "font_size_px": 44,
        "line_height_px": 58,
        "vertical_center_y_px": 1656,
        "style": "legacy_pill",
        "scrim_rgba": (8, 12, 20, 214),
        "stroke_width_px": 3,
        "enable_keyword_color_flash": True,
    },
    "opening_and_thumbnail": {
        "thumbnail_text_mode": "legacy_card",
        "thumbnail_forbid_boxes_badges_rings": False,
    },
    "qa": {
        "require_full_canvas_coverage_audit": False,
        "require_overlay_cleanliness_audit": False,
    },
    "viral_retention": {
        "max_opening_still_duration_s": 12.0,
        "block_ai_cliche_phrases": False,
        "block_jargon_lists": False,
        "enforce_seamless_loop_tail": False,
        "max_ending_tail_pause_s": 3.0,
    },
    "color_science": {
        "enable_filmic_grade": False,
        "luma_grain_sigma": 0.0,
    },
}


def list_available_production_profiles() -> list[str]:
    """Return built-in and YAML-configured Production Profile names."""
    names = ["pow_documentary_v3", "legacy_v2"]
    if PROFILES_DIR.exists():
        for p in sorted(PROFILES_DIR.glob("*.yaml")):
            if p.stem not in names:
                names.append(p.stem)
    return names


def load_style_profile(
    profile_ref: str = "pow_documentary_v3",
    overrides: Optional[dict[str, Any]] = None,
) -> DocumentaryStyleProfile:
    """
    Resolve a reusable `DocumentaryStyleProfile` by preset name (`cinematic_science_documentary`,
    `mysterious_earth_exploration`, `space_discovery`, `deep_ocean_documentary`, `pow_documentary_v3`,
    `legacy_v2`) or explicit YAML file path, layered cleanly atop base channel defaults and any
    optional per-episode dictionary overrides.
    """
    if profile_ref == "legacy_v2":
        data = deepcopy(LEGACY_V2_PROFILE_DICT)
    else:
        base_data = (
            yaml.safe_load(DEFAULT_STYLE_YAML.read_text(encoding="utf-8")) or {}
            if DEFAULT_STYLE_YAML.exists()
            else DocumentaryStyleProfile().model_dump()
        )
        cand_direct = Path(profile_ref)
        cand_named = PROFILES_DIR / f"{profile_ref}.yaml"
        if cand_direct.exists() and cand_direct.is_file():
            prof_patch = yaml.safe_load(cand_direct.read_text(encoding="utf-8")) or {}
            data = _deep_merge(base_data, prof_patch)
        elif profile_ref != "pow_documentary_v3" and cand_named.exists():
            prof_patch = yaml.safe_load(cand_named.read_text(encoding="utf-8")) or {}
            data = _deep_merge(base_data, prof_patch)
        else:
            data = base_data

    if overrides:
        data = _deep_merge(data, overrides)
    return DocumentaryStyleProfile.model_validate(data)
