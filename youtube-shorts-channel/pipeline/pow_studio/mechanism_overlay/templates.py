#!/usr/bin/env python3
"""
Trusted parameterized ManimCE scene templates for Studio v9 Mechanism Overlays
(`pow_studio.mechanism_overlay.templates`).

Coordinate convention (`pixel_width=1080, pixel_height=1920, frame_width=9.0, frame_height=16.0`):
  - `1.0` Manim unit == `120` pixels on both X and Y axes.
  - Canvas top-left `(0, 0)` -> `(-4.5, +8.0)`; bottom-right `(1080, 1920)` -> `(+4.5, -8.0)`.
  - Broadcast safe zone `y_px in [215, 1380]` -> `Y_manim in [-3.50, +6.208]`.
  - Uses bundled `Be Vietnam Pro` / `Anton` via Pango + Unicode (`°C`, `×`, `²`) — ZERO LaTeX needed.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np

SAFE_X_MIN_M = -4.12  # ~46 px
SAFE_X_MAX_M = 4.12   # ~1034 px
SAFE_Y_MIN_M = -3.38  # ~1365 px (safely above 1380 px caption ceiling)
SAFE_Y_MAX_M = 6.10   # ~228 px  (safely below 215 px UI ceiling)


def norm_to_manim(nx: float, ny: float, clamp_safe: bool = True) -> np.ndarray:
    x = (float(nx) - 0.5) * 9.0
    y = (0.5 - float(ny)) * 16.0
    if clamp_safe:
        x = float(np.clip(x, SAFE_X_MIN_M, SAFE_X_MAX_M))
        y = float(np.clip(y, SAFE_Y_MIN_M, SAFE_Y_MAX_M))
    return np.array([x, y, 0.0], dtype=np.float64)


def region_bounds_manim(region: dict[str, float]) -> tuple[float, float, float, float]:
    """Return `(x_left, x_right, y_bottom, y_top)` in Manim units, clamped to safe zone."""
    rx = float(region.get("x", 0.08))
    ry = float(region.get("y", 0.14))
    rw = float(region.get("w", 0.84))
    rh = float(region.get("h", 0.30))
    p_tl = norm_to_manim(rx, ry, clamp_safe=True)
    p_br = norm_to_manim(rx + rw, ry + rh, clamp_safe=True)
    x0, x1 = min(p_tl[0], p_br[0]), max(p_tl[0], p_br[0])
    y0, y1 = min(p_tl[1], p_br[1]), max(p_tl[1], p_br[1])
    if x1 - x0 < 1.2:
        mid_x = 0.5 * (x0 + x1)
        x0, x1 = max(SAFE_X_MIN_M, mid_x - 1.2), min(SAFE_X_MAX_M, mid_x + 1.2)
    if y1 - y0 < 1.0:
        mid_y = 0.5 * (y0 + y1)
        y0, y1 = max(SAFE_Y_MIN_M, mid_y - 0.8), min(SAFE_Y_MAX_M, mid_y + 0.8)
    return x0, x1, y0, y1


def register_studio_fonts() -> str:
    """Register bundled studio TTFs with Pango and return primary sans font family."""
    import manimpango

    fonts_dir = Path(__file__).resolve().parents[3] / "assets" / "fonts"
    for fname in ("BeVietnamPro-Bold.ttf", "BeVietnamPro-Medium.ttf", "Anton-Regular.ttf"):
        fp = fonts_dir / fname
        if fp.exists():
            try:
                manimpango.register_font(str(fp))
            except Exception:
                pass
    avail = set(manimpango.list_fonts())
    return "Be Vietnam Pro" if "Be Vietnam Pro" in avail else "Sans"


def clamp_mobject_to_safe_zone(mobj: Any) -> Any:
    """Shift or gently scale `mobj` if any edge protrudes outside the broadcast safe zone."""
    max_w = SAFE_X_MAX_M - SAFE_X_MIN_M - 0.16
    max_h = SAFE_Y_MAX_M - SAFE_Y_MIN_M - 0.16
    if mobj.width > max_w:
        mobj.scale_to_fit_width(max_w)
    if mobj.height > max_h:
        mobj.scale_to_fit_height(max_h)

    dx = 0.0
    dy = 0.0
    if mobj.get_left()[0] < SAFE_X_MIN_M:
        dx = SAFE_X_MIN_M - float(mobj.get_left()[0])
    elif mobj.get_right()[0] > SAFE_X_MAX_M:
        dx = SAFE_X_MAX_M - float(mobj.get_right()[0])

    if mobj.get_bottom()[1] < SAFE_Y_MIN_M:
        dy = SAFE_Y_MIN_M - float(mobj.get_bottom()[1])
    elif mobj.get_top()[1] > SAFE_Y_MAX_M:
        dy = SAFE_Y_MAX_M - float(mobj.get_top()[1])

    if abs(dx) > 1e-4 or abs(dy) > 1e-4:
        mobj.shift(np.array([dx, dy, 0.0]))
    return mobj


def render_template_scene(
    template: str,
    params: dict[str, Any],
    region: dict[str, float],
    honesty_label: str,
    duration_s: float,
    fps: int,
    media_dir: Path,
    output_stem: str,
) -> Path:
    """Render one transparent `qtrle` ARGB `.mov` using ManimCE and return its path."""
    import manim as m
    from manim import (
         DOWN,
        LEFT,
        ORIGIN,
        RIGHT,
        UP,
         AddTextLetterByLetter,
        Arrow,
        Circle,
        Create,
        CubicBezier,
        DashedVMobject,
        Dot,
        FadeIn,
        FadeOut,
        Line,
        RoundedRectangle,
        Scene,
        Text,
        ValueTracker,
        VGroup,
        VMobject,
        always_redraw,
        tempconfig,
    )

    font_family = register_studio_fonts()
    x0, x1, y0, y1 = region_bounds_manim(region)
    cx = 0.5 * (x0 + x1)
    cy = 0.5 * (y0 + y1)
    rw = x1 - x0
    rh = y1 - y0

    accent = str(params.get("color") or "#FFA94D")
    scrim_fill = "#080D18"
    total_t = max(1.2, float(duration_s))
    intro_t = min(0.55, 0.25 * total_t)
    outro_t = min(0.30, 0.15 * total_t)
    main_t = max(0.35, total_t - intro_t - outro_t)

    def _pill(content: Any, border_col: str = accent, pad_x: float = 0.28, pad_y: float = 0.18, fill_op: float = 0.78) -> Any:
        bg = RoundedRectangle(
            corner_radius=0.14,
            width=min(SAFE_X_MAX_M - SAFE_X_MIN_M - 0.2, content.width + 2 * pad_x),
            height=content.height + 2 * pad_y,
            fill_color=scrim_fill,
            fill_opacity=fill_op,
            stroke_color=border_col,
            stroke_width=2.2,
            stroke_opacity=0.85,
        )
        bg.move_to(content.get_center())
        return VGroup(bg, content)

    class _OverlayScene(Scene):
        def construct(self) -> None:
            if template == "pressure_ripple":
                c_pt = params.get("center")
                origin_pt = (
                    norm_to_manim(c_pt[0], c_pt[1], clamp_safe=True)
                    if isinstance(c_pt, (list, tuple)) and len(c_pt) >= 2
                    else np.array([cx, cy + 0.18 * rh, 0.0])
                )
                n_rings = max(2, min(6, int(params.get("rings") or 4)))
                max_r = min(0.44 * rw, 0.42 * rh, 2.35)
                # Clamp center so rings stay inside safe zone
                origin_pt[0] = float(np.clip(origin_pt[0], SAFE_X_MIN_M + max_r + 0.1, SAFE_X_MAX_M - max_r - 0.1))
                origin_pt[1] = float(np.clip(origin_pt[1], SAFE_Y_MIN_M + max_r + 0.55, SAFE_Y_MAX_M - max_r - 0.1))

                phase = ValueTracker(0.0)
                core = Dot(point=origin_pt, radius=0.07, color="#FFFFFF")

                def _draw_rings() -> Any:
                    grp = VGroup()
                    ph = float(phase.get_value())
                    for k in range(n_rings):
                        u = (ph + k / float(n_rings)) % 1.0
                        rad = 0.14 + u * (max_r - 0.14)
                        op = max(0.08, (1.0 - u) * 0.88)
                        ring = Circle(
                            radius=rad,
                            stroke_color=accent,
                            stroke_width=3.6 * (1.0 - 0.45 * u),
                            stroke_opacity=op,
                        ).move_to(origin_pt)
                        grp.add(ring)
                    return grp

                rings_mob = always_redraw(_draw_rings)
                lbl_str = str(params.get("label") or "").strip()
                sub_str = str(params.get("sublabel") or "").strip()
                badge_grp = VGroup()
                if lbl_str:
                    t_main = Text(lbl_str, font=font_family, font_size=26, color="#FFF8EE", weight="BOLD")
                    items = [t_main]
                    if sub_str:
                        t_sub = Text(sub_str, font=font_family, font_size=19, color="#BBD0EE")
                        t_sub.next_to(t_main, DOWN, buff=0.08)
                        items.append(t_sub)
                    txt_v = VGroup(*items)
                    pill = _pill(txt_v)
                    pill.move_to(origin_pt + np.array([0.0, -(max_r + 0.36), 0.0]))
                    clamp_mobject_to_safe_zone(pill)
                    badge_grp.add(pill)

                all_grp = VGroup(core, badge_grp)
                self.play(FadeIn(all_grp), FadeIn(rings_mob), run_time=intro_t)
                self.play(phase.animate.set_value(max(1.2, main_t / float(params.get("period_s") or 1.25))), run_time=main_t, rate_func=m.linear)
                self.play(FadeOut(all_grp), FadeOut(rings_mob), run_time=outro_t)

            elif template == "wave_frequency_scale":
                raw_ticks = params.get("ticks") or [
                    {"label": "261.6 Hz  MIDDLE C", "sub": "Musical reference"},
                    {"label": "20 Hz  HEARING FLOOR", "sub": "Human ear limit"},
                    {"label": "PERSEUS B-FLAT", "sub": "57 octaves below • 10M yr/wave"},
                ]
                title_str = str(params.get("title") or params.get("label") or "ACOUSTIC SCALE").strip()
                marker_str = str(params.get("marker_label") or params.get("marker_value") or "-57 OCTAVES").strip()

                card_w = min(rw, 7.2)
                card_h = min(max(rh, 3.6), 5.6)
                panel = RoundedRectangle(
                    corner_radius=0.20,
                    width=card_w,
                    height=card_h,
                    fill_color=scrim_fill,
                    fill_opacity=0.76,
                    stroke_color=accent,
                    stroke_width=2.2,
                    stroke_opacity=0.82,
                ).move_to(np.array([cx, cy, 0.0]))
                clamp_mobject_to_safe_zone(panel)
                pc = panel.get_center()

                hdr = Text(title_str, font=font_family, font_size=21, color=accent, weight="BOLD")
                hdr.move_to(pc + np.array([0.0, 0.5 * card_h - 0.34, 0.0]))
                if hdr.width > card_w - 0.5:
                    hdr.scale_to_fit_width(card_w - 0.5)

                spine_x = pc[0] - 0.5 * card_w + 0.62
                y_top = pc[1] + 0.5 * card_h - 0.86
                y_bot = pc[1] - 0.5 * card_h + 1.32
                spine_bg = Line([spine_x, y_top, 0], [spine_x, y_bot, 0], stroke_color="#496592", stroke_width=5, stroke_opacity=0.75)

                tick_mobs = VGroup()
                n_t = max(2, len(raw_ticks))
                for idx, tk in enumerate(raw_ticks):
                    u = idx / float(n_t - 1)
                    ty = y_top - u * (y_top - y_bot)
                    lbl = tk.get("label", "") if isinstance(tk, dict) else str(tk)
                    sub = tk.get("sub", "") if isinstance(tk, dict) else ""
                    dot = Dot([spine_x, ty, 0], radius=0.075, color=accent if idx == n_t - 1 else "#8CC8FF")
                    t1 = Text(str(lbl), font=font_family, font_size=22, color="#FFFFFF", weight="BOLD")
                    if t1.width > card_w - 1.25:
                        t1.scale_to_fit_width(card_w - 1.25)
                    t1.next_to(dot, RIGHT, buff=0.22)
                    row_g = VGroup(dot, t1)
                    if sub:
                        t2 = Text(str(sub), font=font_family, font_size=17, color="#B8CBE8")
                        if t2.width > card_w - 1.25:
                            t2.scale_to_fit_width(card_w - 1.25)
                        t2.next_to(t1, DOWN, aligned_edge=LEFT, buff=0.05)
                        row_g.add(t2)
                    tick_mobs.add(row_g)

                prog = ValueTracker(0.0)
                active_line = always_redraw(
                    lambda: Line(
                        [spine_x, y_top, 0],
                        [spine_x, y_top - float(prog.get_value()) * (y_top - y_bot), 0],
                        stroke_color=accent,
                        stroke_width=7.0,
                    )
                )

                badge_txt = Text(marker_str, font=font_family, font_size=28, color=accent, weight="BOLD")
                badge = _pill(badge_txt, border_col=accent, pad_x=0.24, pad_y=0.10, fill_op=0.88)
                badge.move_to(pc + np.array([0.35, -0.5 * card_h + 0.42, 0.0]))
                clamp_mobject_to_safe_zone(badge)

                base_g = VGroup(panel, hdr, spine_bg, tick_mobs)
                self.play(FadeIn(base_g), run_time=intro_t)
                self.add(active_line)
                drop_t = max(0.25, 0.65 * main_t)
                hold_rem = max(0.10, main_t - drop_t)
                self.play(prog.animate.set_value(1.0), FadeIn(badge), run_time=drop_t)
                self.wait(hold_rem)
                self.play(FadeOut(base_g), FadeOut(active_line), FadeOut(badge), run_time=outro_t)

            elif template == "value_callout_gauge":
                v_from = float(params.get("value_from", 0.0))
                v_to = float(params.get("value_to", 100.0))
                decimals = int(params.get("decimals", 0))
                unit = str(params.get("unit") or "").strip()
                label = str(params.get("label") or "MEASURED").strip()
                pt_raw = params.get("point")

                val_tracker = ValueTracker(v_from)

                def _make_readout() -> Any:
                    v_cur = float(val_tracker.get_value())
                    num_s = f"{v_cur:,.{decimals}f}" if decimals > 0 else f"{int(round(v_cur)):,}"
                    full_s = f"{num_s} {unit}".strip()
                    t_num = Text(full_s, font=font_family, font_size=40, color="#FFFFFF", weight="BOLD")
                    t_lbl = Text(label, font=font_family, font_size=20, color=accent, weight="BOLD")
                    t_lbl.next_to(t_num, UP, aligned_edge=LEFT, buff=0.08)
                    vg = VGroup(t_lbl, t_num)
                    card = _pill(vg, border_col=accent, pad_x=0.30, pad_y=0.20, fill_op=0.82)
                    card.move_to(np.array([cx, cy, 0.0]))
                    return clamp_mobject_to_safe_zone(card)

                readout_mob = always_redraw(_make_readout)
                extras = VGroup()
                if isinstance(pt_raw, (list, tuple)) and len(pt_raw) >= 2:
                    t_pt = norm_to_manim(pt_raw[0], pt_raw[1], clamp_safe=True)
                    ring = Circle(radius=0.18, stroke_color=accent, stroke_width=3.2).move_to(t_pt)
                    card_anchor = np.array([cx, cy, 0.0])
                    vec = t_pt - card_anchor
                    dist = float(np.linalg.norm(vec[:2]))
                    if dist > 0.75:
                        u_vec = vec / dist
                        leader = Line(
                            card_anchor + u_vec * 0.55,
                            t_pt - u_vec * 0.20,
                            stroke_color=accent,
                            stroke_width=2.6,
                            stroke_opacity=0.85,
                        )
                        extras.add(leader)
                    extras.add(ring)

                self.play(FadeIn(readout_mob), Create(extras) if len(extras) else FadeIn(extras), run_time=intro_t)
                cnt_t = max(0.25, 0.62 * main_t)
                self.play(val_tracker.animate.set_value(v_to), run_time=cnt_t)
                self.wait(max(0.10, main_t - cnt_t))
                self.play(FadeOut(readout_mob), FadeOut(extras), run_time=outro_t)

            elif template == "flow_arrows":
                raw_path = params.get("path") or [[0.25, 0.48], [0.50, 0.36], [0.75, 0.28]]
                pts = [norm_to_manim(p[0], p[1], clamp_safe=True) for p in raw_path if len(p) >= 2]
                if len(pts) < 2:
                    pts = [np.array([x0 + 0.4, cy - 0.5, 0.0]), np.array([x1 - 0.4, cy + 0.5, 0.0])]
                n_arrows = max(1, min(5, int(params.get("count") or 3)))
                lbl_str = str(params.get("label") or "").strip()

                arrows = VGroup()
                segs = len(pts) - 1
                for i in range(n_arrows):
                    offset_y = (i - 0.5 * (n_arrows - 1)) * 0.28
                    shift_v = np.array([0.0, offset_y, 0.0])
                    for s_i in range(segs):
                        p_a = pts[s_i] + shift_v
                        p_b = pts[s_i + 1] + shift_v
                        p_a[1] = float(np.clip(p_a[1], SAFE_Y_MIN_M + 0.15, SAFE_Y_MAX_M - 0.15))
                        p_b[1] = float(np.clip(p_b[1], SAFE_Y_MIN_M + 0.15, SAFE_Y_MAX_M - 0.15))
                        arr = Arrow(p_a, p_b, buff=0.06, stroke_width=4.5, color=accent, max_tip_length_to_length_ratio=0.22)
                        arrows.add(arr)

                badge = VGroup()
                if lbl_str:
                    t = Text(lbl_str, font=font_family, font_size=24, color="#FFFFFF", weight="BOLD")
                    p_card = _pill(t, border_col=accent)
                    p_card.move_to(pts[-1] + np.array([0.0, 0.52, 0.0]))
                    clamp_mobject_to_safe_zone(p_card)
                    badge.add(p_card)

                self.play(Create(arrows), FadeIn(badge), run_time=intro_t + 0.35 * main_t)
                self.wait(max(0.10, 0.65 * main_t))
                self.play(FadeOut(arrows), FadeOut(badge), run_time=outro_t)

            elif template == "scale_bar_compare":
                len_lbl = str(params.get("length_label") or "SUBJECT").strip()
                ref_lbl = str(params.get("reference_label") or "REFERENCE").strip()
                ratio = float(np.clip(float(params.get("ratio", 1.8)), 0.2, 5.0))

                card_w = min(rw, 6.8)
                card_h = min(max(rh, 3.0), 4.4)
                panel = RoundedRectangle(
                    corner_radius=0.18,
                    width=card_w,
                    height=card_h,
                    fill_color=scrim_fill,
                    fill_opacity=0.78,
                    stroke_color=accent,
                    stroke_width=2.0,
                ).move_to(np.array([cx, cy, 0.0]))
                clamp_mobject_to_safe_zone(panel)
                pc = panel.get_center()

                max_bar_w = card_w - 1.2
                if ratio >= 1.0:
                    w_subj = max_bar_w
                    w_ref = max(0.65, max_bar_w / ratio)
                else:
                    w_ref = max_bar_w
                    w_subj = max(0.65, max_bar_w * ratio)

                left_x = pc[0] - 0.5 * card_w + 0.55
                y_a = pc[1] + 0.42
                y_b = pc[1] - 0.62

                bar_a = Line([left_x, y_a, 0], [left_x + w_subj, y_a, 0], stroke_color=accent, stroke_width=14)
                bar_b = Line([left_x, y_b, 0], [left_x + w_ref, y_b, 0], stroke_color="#89B8FF", stroke_width=14)
                ta = Text(len_lbl, font=font_family, font_size=23, color="#FFFFFF", weight="BOLD").next_to(bar_a, UP, aligned_edge=LEFT, buff=0.14)
                tb = Text(ref_lbl, font=font_family, font_size=21, color="#C7DCF8").next_to(bar_b, UP, aligned_edge=LEFT, buff=0.14)

                grp = VGroup(panel, ta, tb)
                self.play(FadeIn(grp), Create(bar_a), Create(bar_b), run_time=intro_t + 0.30 * main_t)
                self.wait(max(0.10, 0.70 * main_t))
                self.play(FadeOut(grp), FadeOut(bar_a), FadeOut(bar_b), run_time=outro_t)

            elif template == "trajectory_trace":
                raw_path = params.get("path") or [[0.18, 0.55], [0.46, 0.34], [0.80, 0.26]]
                pts = [norm_to_manim(p[0], p[1], clamp_safe=True) for p in raw_path if len(p) >= 2]
                if len(pts) < 2:
                    pts = [np.array([x0 + 0.4, y0 + 0.4, 0.0]), np.array([x1 - 0.4, y1 - 0.4, 0.0])]
                lbl_str = str(params.get("label") or "").strip()

                curve = VMobject(stroke_color=accent, stroke_width=4.5)
                curve.set_points_smoothly(pts)
                guide = DashedVMobject(curve.copy().set_stroke(color="#9BB8E8", width=2.0, opacity=0.45), num_dashes=22)

                u_tr = ValueTracker(0.0)
                beacon = always_redraw(
                    lambda: Dot(curve.point_from_proportion(float(np.clip(u_tr.get_value(), 0.0, 1.0))), radius=0.10, color="#FFFFFF")
                )

                badge = VGroup()
                if lbl_str:
                    t = Text(lbl_str, font=font_family, font_size=23, color="#FFFFFF", weight="BOLD")
                    p_card = _pill(t, border_col=accent)
                    p_card.move_to(pts[-1] + np.array([0.0, 0.46, 0.0]))
                    clamp_mobject_to_safe_zone(p_card)
                    badge.add(p_card)

                self.play(FadeIn(guide), FadeIn(beacon), FadeIn(badge), run_time=intro_t)
                trace_t = max(0.25, 0.68 * main_t)
                self.play(Create(curve), u_tr.animate.set_value(1.0), run_time=trace_t)
                self.wait(max(0.10, main_t - trace_t))
                self.play(FadeOut(guide), FadeOut(curve), FadeOut(beacon), FadeOut(badge), run_time=outro_t)

            else:  # label_leader
                pt_raw = params.get("point") or [0.50, 0.44]
                kfs = params.get("track_keyframes")
                txt_str = str(params.get("text") or params.get("label") or "FEATURE").strip()
                sub_str = str(params.get("subtext") or "").strip()

                u_tr = ValueTracker(0.0)

                def _interp_point() -> np.ndarray:
                    if isinstance(kfs, list) and len(kfs) >= 2:
                        u = float(np.clip(u_tr.get_value(), 0.0, 1.0))
                        sorted_kf = sorted(kfs, key=lambda r: float(r[0]))
                        for i in range(len(sorted_kf) - 1):
                            u0, x_a, y_a = float(sorted_kf[i][0]), float(sorted_kf[i][1]), float(sorted_kf[i][2])
                            u1, x_b, y_b = float(sorted_kf[i + 1][0]), float(sorted_kf[i + 1][1]), float(sorted_kf[i + 1][2])
                            if u0 <= u <= u1 or i == len(sorted_kf) - 2:
                                w = (u - u0) / max(1e-4, u1 - u0)
                                w = float(np.clip(w, 0.0, 1.0))
                                return norm_to_manim(x_a + w * (x_b - x_a), y_a + w * (y_b - y_a), clamp_safe=True)
                    return norm_to_manim(pt_raw[0], pt_raw[1], clamp_safe=True)

                def _draw_callout() -> Any:
                    tp = _interp_point()
                    ring = Circle(radius=0.22, stroke_color=accent, stroke_width=3.2).move_to(tp)
                    t1 = Text(txt_str, font=font_family, font_size=24, color="#FFFFFF", weight="BOLD")
                    items = [t1]
                    if sub_str:
                        t2 = Text(sub_str, font=font_family, font_size=18, color="#C2D5F0")
                        t2.next_to(t1, DOWN, aligned_edge=LEFT, buff=0.05)
                        items.append(t2)
                    card = _pill(VGroup(*items), border_col=accent)
                    dy = 0.88 if tp[1] < (SAFE_Y_MAX_M - 1.3) else -0.88
                    dx = 0.75 if tp[0] < 0.0 else -0.75
                    card.move_to(tp + np.array([dx, dy, 0.0]))
                    clamp_mobject_to_safe_zone(card)
                    cc = card.get_center()
                    vec = cc - tp
                    dist = max(1e-4, float(np.linalg.norm(vec[:2])))
                    u_v = vec / dist
                    leader = Line(tp + u_v * 0.24, cc - u_v * 0.42, stroke_color=accent, stroke_width=2.6)
                    return VGroup(ring, leader, card)

                callout = always_redraw(_draw_callout)
                self.play(FadeIn(callout), run_time=intro_t)
                self.play(u_tr.animate.set_value(1.0), run_time=main_t, rate_func=m.linear)
                self.play(FadeOut(callout), run_time=outro_t)

    media_dir.mkdir(parents=True, exist_ok=True)
    with tempconfig(
        {
            "pixel_width": 1080,
            "pixel_height": 1920,
            "frame_width": 9.0,
            "frame_height": 16.0,
            "frame_rate": int(fps),
            "transparent": True,
            "media_dir": str(media_dir),
            "output_file": output_stem,
            "verbosity": "ERROR",
            "disable_caching": True,
        }
    ):
        _OverlayScene().render()

    candidates = list(media_dir.rglob(f"{output_stem}.mov"))
    if not candidates:
        candidates = [p for p in media_dir.rglob("*.mov") if "partial_movie_files" not in p.parts]
    if not candidates:
        raise RuntimeError(f"Manim did not produce {output_stem}.mov under {media_dir}")
    return candidates[0]
