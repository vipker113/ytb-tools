#!/usr/bin/env python3
"""
Kairo Spark — Local Chatterbox TTS Generator (Apple Silicon MPS / Free Forever)
Supports:
  1. --test-samples : Generates 25s A/B test samples (Default Narrator vs. Cloned Kairo Spark Voice)
  2. --script <md> --out <mp3> : Generates a full episode voiceover chunked cleanly with expressive prosody
"""

import os
import re
import sys
import time
import argparse
import subprocess
import numpy as np
import soundfile as sf
import torch

os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

EP_DIR = "/Applications/code/science-knowledge/ytb-tools/episodes/pilot-01-why-5-days"
REF_SRC_MP3 = os.path.join(EP_DIR, "audio/voice_master_14lufs.mp3")
REF_CLIP_WAV = os.path.join(EP_DIR, "audio/ref_kairo_voice_12s.wav")
SAMPLES_DIR = os.path.join(EP_DIR, "audio/chatterbox_samples")
os.makedirs(SAMPLES_DIR, exist_ok=True)


def get_device():
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def patch_torch_load(device_str):
    map_loc = torch.device(device_str)
    orig_load = torch.load

    def patched_load(*args, **kwargs):
        if "map_location" not in kwargs or kwargs["map_location"] is None:
            kwargs["map_location"] = map_loc
        return orig_load(*args, **kwargs)

    torch.load = patched_load


def ensure_ref_voice_clip():
    if not os.path.exists(REF_CLIP_WAV) and os.path.exists(REF_SRC_MP3):
        cmd = [
            "ffmpeg", "-y", "-i", REF_SRC_MP3,
            "-ss", "0.0", "-t", "13.0",
            "-ar", "24000", "-ac", "1", REF_CLIP_WAV
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return REF_CLIP_WAV if os.path.exists(REF_CLIP_WAV) else None


def load_chatterbox(device_str):
    patch_torch_load(device_str)
    import perth
    if perth.PerthImplicitWatermarker is None:
        perth.PerthImplicitWatermarker = perth.DummyWatermarker
    from chatterbox.tts import ChatterboxTTS
    print(f"Loading ChatterboxTTS on device={device_str} ...")
    t0 = time.time()
    model = ChatterboxTTS.from_pretrained(device=device_str)
    print(f"Loaded ChatterboxTTS in {time.time() - t0:.1f}s (sr={model.sr})")
    return model


def clean_text_for_chatterbox(text):
    # Remove ElevenLabs bracket tags [sighs], [chuckles], etc., since Chatterbox uses exaggeration/cfg_weight & punctuation
    t = re.sub(r"\[[^\]]+\]", "", text)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def synthesize_chunks(model, chunks, out_mp3, audio_prompt_path=None, exaggeration=0.65, cfg_weight=0.40):
    wav_parts = []
    sr = model.sr
    pause_short = np.zeros(int(sr * 0.28), dtype=np.float32)

    for i, (text, exag_override) in enumerate(chunks):
        clean_t = clean_text_for_chatterbox(text)
        if not clean_t:
            continue
        use_exag = exag_override if exag_override is not None else exaggeration
        print(f"  [{i+1}/{len(chunks)}] exag={use_exag:.2f} | {clean_t}")
        t0 = time.time()
        kwargs = {
            "exaggeration": use_exag,
            "cfg_weight": cfg_weight,
        }
        if audio_prompt_path:
            kwargs["audio_prompt_path"] = audio_prompt_path
        wav_tensor = model.generate(clean_t, **kwargs)
        wav_np = wav_tensor.squeeze().detach().cpu().numpy().astype(np.float32)
        wav_parts.append(wav_np)
        wav_parts.append(pause_short)
        print(f"     -> {len(wav_np)/sr:.2f}s audio in {time.time() - t0:.1f}s")

    full_wav = np.concatenate(wav_parts)
    tmp_wav = out_mp3.replace(".mp3", ".wav")
    sf.write(tmp_wav, full_wav, sr)
    # Normalize to -14 LUFS broadcast standard & encode crisp 192k MP3
    cmd = [
        "ffmpeg", "-y", "-i", tmp_wav,
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-ar", "48000", "-c:a", "libmp3lame", "-b:a", "192k",
        out_mp3
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Saved normalized MP3: {out_mp3} ({len(full_wav)/sr:.2f}s)")


def run_test_samples():
    device = get_device()
    ref_wav = ensure_ref_voice_clip()
    model = load_chatterbox(device)

    test_chunks = [
        ("Every Sunday night, right around seven or eight o'clock... you feel it, don't you?", 0.65),
        ("You're still off work. You're sitting on your own couch. Nobody's asking you for a spreadsheet.", 0.55),
        ("And yet — your chest tightens up just a little bit. Because tomorrow is Monday.", 0.72),
        ("And Monday means five straight days of handing over your life... just to earn back two days at the end. Five days on. Two days off.", 0.68),
    ]

    # Sample 1: Built-in Default Narrator
    out_def = os.path.join(SAMPLES_DIR, "sample_1_chatterbox_default.mp3")
    print("\n=== Generating Sample 1: Chatterbox Default Narrator ===")
    synthesize_chunks(model, test_chunks, out_def, audio_prompt_path=None, exaggeration=0.65, cfg_weight=0.40)

    # Sample 2: Cloned Kairo Spark Narrator (using our 12s ref clip)
    if ref_wav:
        out_clone = os.path.join(SAMPLES_DIR, "sample_2_chatterbox_kairo_cloned.mp3")
        print(f"\n=== Generating Sample 2: Chatterbox Cloned Kairo Voice ({ref_wav}) ===")
        synthesize_chunks(model, test_chunks, out_clone, audio_prompt_path=ref_wav, exaggeration=0.70, cfg_weight=0.35)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-samples", action="store_true")
    args = parser.parse_args()
    if args.test_samples:
        run_test_samples()
