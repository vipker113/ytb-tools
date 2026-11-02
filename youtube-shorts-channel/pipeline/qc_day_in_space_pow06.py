#!/usr/bin/env python3
"""Post-render QC for Proof of Wonder #06."""
import json, os, re, subprocess, sys, difflib
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = "/Applications/code/science-knowledge/youtube-shorts-channel"
sys.path.insert(0, f"{ROOT}/pipeline")
import build_day_in_space_pow06 as B  # noqa: E402

OUT, MP4, SCR = B.OUT, B.FINAL_MP4, f"{B.SCR}/qc"
os.makedirs(SCR, exist_ok=True)
FB = ImageFont.truetype(B.FONT_BOLD, 22); FM = ImageFont.truetype(B.FONT_MED, 16); FT = ImageFont.truetype(B.FONT_BOLD, 30)
report = {}


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def grab(t, path, scale=None, exact_frame=None):
    if exact_frame is not None:
        sc = f",scale={scale[0]}:{scale[1]}" if scale else ""
        run(["ffmpeg", "-y", "-i", MP4, "-vf", f"select='eq(n\\,{exact_frame})'{sc}", "-vsync", "0", "-frames:v", "1", path])
    else:
        vf = ["-vf", f"scale={scale[0]}:{scale[1]}"] if scale else []
        run(["ffmpeg", "-y", "-ss", f"{max(0.0, t - 1.5):.3f}", "-i", MP4, "-ss", f"{min(1.5, t):.3f}", "-frames:v", "1", *vf, path])
    return Image.open(path).convert("RGB")


# 1. ffprobe
pr = json.loads(run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", MP4]).stdout)
v = next(s for s in pr["streams"] if s["codec_type"] == "video"); a = next(s for s in pr["streams"] if s["codec_type"] == "audio")
report["ffprobe"] = {"duration": float(pr["format"]["duration"]), "size_bytes": int(pr["format"]["size"]), "video_codec": v["codec_name"],
                     "profile": v.get("profile"), "width": v["width"], "height": v["height"], "fps": v["r_frame_rate"],
                     "avg_fps": v["avg_frame_rate"], "nb_frames": v.get("nb_frames"), "pix_fmt": v["pix_fmt"],
                     "audio_codec": a["codec_name"], "sample_rate": a["sample_rate"], "channels": a["channels"]}

# 2. blackdetect / loudness
bd = run(["ffmpeg", "-hide_banner", "-i", MP4, "-vf", "blackdetect=d=0.05:pix_th=0.10", "-an", "-f", "null", "-"]).stderr
report["black_segments"] = re.findall(r"black_start:\S+ black_end:\S+ black_duration:\S+", bd)
ln = run(["ffmpeg", "-hide_banner", "-i", MP4, "-af", "ebur128=peak=true", "-vn", "-f", "null", "-"]).stderr
summ = ln[ln.rfind("Summary:"):]
report["loudness"] = {"integrated_LUFS": float(re.search(r"I:\s+(-?[\d.]+) LUFS", summ).group(1)),
                      "LRA_LU": float(re.search(r"LRA:\s+(-?[\d.]+) LU", summ).group(1)),
                      "true_peak_dBTP": float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", summ).group(1))}

# 3. per-element loudness (narration vs sound bites) from the mix wav
tl = json.load(open(B.TIMELINE))
x = B.read_wav(B.MIX_WAV)
def seg_lufs(t0, t1):
    tmp = f"{SCR}/_seg.wav"; B.write_wav(tmp, x[int(t0 * B.SR):int(t1 * B.SR)])
    s = run(["ffmpeg", "-hide_banner", "-i", tmp, "-af", "ebur128", "-f", "null", "-"]).stderr
    s = s[s.rfind("Summary:"):]
    return float(re.search(r"I:\s+(-?[\d.]+) LUFS", s).group(1))
report["element_loudness"] = [{"id": e["id"], "kind": e["kind"], "LUFS": seg_lufs(e["speech_start"], e["speech_end"])} for e in tl["elements"]]

# 4. overlap check: no narration during any sound bite
els = tl["elements"]
over = []
for b in [e for e in els if e["kind"] == "soundbite"]:
    for n in [e for e in els if e["kind"] == "narration"]:
        if n["start"] < b["end"] and b["start"] < n["end"]:
            over.append((b["id"], n["id"]))
report["narration_soundbite_overlaps"] = over

# 5. Whisper the FINAL audio and compare with SRT text / timing
from faster_whisper import WhisperModel
run(["ffmpeg", "-y", "-i", MP4, "-vn", "-ac", "1", "-ar", "16000", f"{SCR}/final16k.wav"])
m = WhisperModel("medium.en", device="cpu", compute_type="int8", download_root=f"{ROOT}/assets/models")
segs, _ = m.transcribe(f"{SCR}/final16k.wav", language="en", word_timestamps=True, beam_size=5, condition_on_previous_text=False)
hw = [{"w": re.sub(r"[^a-z0-9']", "", w.word.lower()), "s": w.start, "e": w.end} for s in segs for w in s.words]
hw = [h for h in hw if h["w"]]
srt = open(B.SRT, encoding="utf-8").read().strip().split("\n\n")
cues = []
for blk in srt:
    ls = blk.splitlines()
    t0, t1 = ls[1].split(" --> ")
    f = lambda s: int(s[:2]) * 3600 + int(s[3:5]) * 60 + int(s[6:8]) + int(s[9:]) / 1000
    txt = " ".join(ls[2:]); txt = re.sub(r"^[A-Z .'-]+: ", "", txt)
    cues.append((f(t0), f(t1), txt))
ref = [re.sub(r"[^a-z0-9']", "", t.lower()) for _, _, txt in cues for t in txt.replace("-", " ").split()]
ref = [r for r in ref if r]
hyp = [h["w"] for h in hw]
sm = difflib.SequenceMatcher(None, ref, hyp, autojunk=False)
report["final_audio_vs_srt_word_match_ratio"] = round(sm.ratio(), 4)
report["final_audio_vs_srt_diffs"] = [(op, " ".join(ref[i1:i2]), " ".join(hyp[j1:j2])) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal"][:40]
# timing: for each cue, first ref word's matched hyp time vs cue start
offs = []
ri = 0
mapping = {}
for op, i1, i2, j1, j2 in sm.get_opcodes():
    if op == "equal":
        for k in range(i2 - i1):
            mapping[i1 + k] = j1 + k
for (t0, t1, txt) in cues:
    n = len([t for t in txt.replace("-", " ").split() if re.sub(r"[^a-z0-9']", "", t.lower())])
    if ri in mapping:
        offs.append(round(hw[mapping[ri]]["s"] - t0, 3))
    ri += n
report["cue_start_vs_heard_word_offset_s"] = {"n": len(offs), "median": float(np.median(offs)), "p95_abs": float(np.percentile(np.abs(offs), 95)), "max_abs": float(np.max(np.abs(offs)))}

# 6. Sheets
wins, _, total = B.shot_windows()
# contact sheet (one frame per shot)
cw, ch, cols = 216, 384, 8
rows = (len(wins) + cols - 1) // cols
cs = Image.new("RGB", (cols * (cw + 10) + 10, rows * (ch + 50) + 64), (14, 17, 25)); d = ImageDraw.Draw(cs)
d.text((14, 16), f"POW #06 — FINAL CONTACT SHEET ({B.SLUG}.mp4, {total:.2f}s, {len(wins)} shots)", font=FT, fill=(255, 255, 255))
for k, (s, f0, f1) in enumerate(wins):
    t = (f0 + f1) / 2 / B.FPS
    im = grab(t, f"{SCR}/cs_{k}.jpg", (cw, ch)); r, c = divmod(k, cols); X, Y = 10 + c * (cw + 10), 60 + r * (ch + 50)
    cs.paste(im, (X, Y)); d.text((X + 2, Y + ch + 4), f"{s.sid} {f0/B.FPS:.1f}-{f1/B.FPS:.1f}s", font=FB, fill=(255, 228, 96))
    d.text((X + 2, Y + ch + 28), s.src, font=FM, fill=(200, 210, 230))
cs.save(f"{OUT}/contact_sheet.jpg", quality=90)

# transitions: frame before/after every cut
tw, th = 162, 288
cuts = [f0 for s, f0, f1 in wins][1:]
cols = 6
rows = (len(cuts) + cols - 1) // cols
ts = Image.new("RGB", (cols * (2 * tw + 22) + 10, rows * (th + 40) + 60), (14, 17, 25)); d = ImageDraw.Draw(ts)
d.text((14, 14), "EVERY CUT: last frame before | first frame after", font=FT, fill=(255, 255, 255))
for k, f in enumerate(cuts):
    r, c = divmod(k, cols); X, Y = 10 + c * (2 * tw + 22), 56 + r * (th + 40)
    a_ = grab((f - 0.5) / B.FPS, f"{SCR}/tA.jpg", (tw, th)); b_ = grab((f + 0.5) / B.FPS, f"{SCR}/tB.jpg", (tw, th))
    ts.paste(a_, (X, Y)); ts.paste(b_, (X + tw + 4, Y))
    d.text((X, Y + th + 4), f"cut @ {f/B.FPS:.2f}s", font=FM, fill=(255, 228, 96))
ts.save(f"{OUT}/transitions_contact_sheet.jpg", quality=88)

# first 3 seconds
fw, fh = 252, 448
f3 = Image.new("RGB", (7 * (fw + 10) + 10, fh + 100), (14, 17, 25)); d = ImageDraw.Draw(f3)
d.text((14, 14), "FIRST 3 SECONDS (t = 0.0 … 3.0 s)", font=FT, fill=(255, 255, 255))
for k, t in enumerate([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]):
    f3.paste(grab(t, f"{SCR}/f3.jpg", (fw, fh)), (10 + k * (fw + 10), 56)); d.text((14 + k * (fw + 10), 62 + fh), f"t={t:.1f}s", font=FB, fill=(255, 228, 96))
f3.save(f"{OUT}/first_3_seconds_audit_sheet.jpg", quality=90)

# ending
en = Image.new("RGB", (6 * (fw + 10) + 10, fh + 100), (14, 17, 25)); d = ImageDraw.Draw(en)
d.text((14, 14), "ENDING (last 10 s)", font=FT, fill=(255, 255, 255))
for k, t in enumerate(np.linspace(total - 10, total - 0.05, 6)):
    en.paste(grab(t, f"{SCR}/en.jpg", (fw, fh)), (10 + k * (fw + 10), 56)); d.text((14 + k * (fw + 10), 62 + fh), f"t={t:.1f}s", font=FB, fill=(255, 228, 96))
en.save(f"{OUT}/ending_audit_sheet.jpg", quality=90)

# sound-bite frames (lip-sync / lower thirds)
sb = [e for e in els if e["kind"] == "soundbite"]
sbs = Image.new("RGB", (4 * (fw + 10) + 10, len(sb) * (fh + 40) + 60), (14, 17, 25)); d = ImageDraw.Draw(sbs)
d.text((14, 14), "SOUND-BITE SEGMENTS (speaker on screen, lower third, warm captions)", font=FT, fill=(255, 255, 255))
for r, e in enumerate(sb):
    for c, fr in enumerate([0.08, 0.3, 0.6, 0.92]):
        t = e["start"] + fr * (e["end"] - e["start"])
        sbs.paste(grab(t, f"{SCR}/sb.jpg", (fw, fh)), (10 + c * (fw + 10), 56 + r * (fh + 40)))
        d.text((14 + c * (fw + 10), 60 + r * (fh + 40) + fh), f"{e['id']} {t:.1f}s", font=FM, fill=(255, 228, 96))
sbs.save(f"{OUT}/soundbite_segments_sheet.jpg", quality=88)

json.dump(report, open(f"{OUT}/qc_measurements.json", "w"), indent=1)
print(json.dumps(report, indent=1)[:6000])
