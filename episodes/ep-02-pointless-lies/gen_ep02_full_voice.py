#!/usr/bin/env python3
"""
Generate FULL Episode #2 Voiceover using Chatterbox TTS (Apple Silicon MPS)
with the EXACT voice clone & cadence approved by the user on ep02_hook_voice_chatterbox.mp3.
Saves per-segment WAVs, full normalized -14.0 LUFS MP3, and segment timing metadata.
"""

import os
import sys
import json
import time
import subprocess
import numpy as np
import soundfile as sf

sys.path.insert(0, "/Applications/code/science-knowledge/ytb-tools/scripts")
import kairo_chatterbox_tts as kc

EP_DIR = "/Applications/code/science-knowledge/ytb-tools/episodes/ep-02-pointless-lies"
AUDIO_DIR = os.path.join(EP_DIR, "audio")
CHUNKS_DIR = os.path.join(AUDIO_DIR, "full_chunks")
os.makedirs(CHUNKS_DIR, exist_ok=True)

# Full Verified Human Script (script_verified_human.md) split into natural conversational breath chunks
# Format: (seg_id, act_label, text, exaggeration, post_pause_sec)
SCRIPT_CHUNKS = [
    # ACT I: The Monday Morning Coffee Machine
    (1, "ACT_1", "Why do we lie even when telling the truth wouldn't cost us anything?", 0.58, 0.55),
    (2, "ACT_1", "Think about a normal Monday morning. You're standing by the coffee machine, still half asleep, and a coworker looks over and asks, Hey, how was your weekend?", 0.55, 0.45),
    (3, "ACT_1", "Now, if you actually answered honestly, what would you say?", 0.54, 0.35),
    (4, "ACT_1", "Maybe the real truth is that you barely left your apartment. You spent most of Saturday on your phone, ate dinner straight out of a takeout container at four in the afternoon, and went to bed early.", 0.52, 0.45),
    (5, "ACT_1", "What would happen if you said that out loud? Nobody's going to fire you. Nobody's going to judge you for resting on a Saturday.", 0.56, 0.35),
    (6, "ACT_1", "Most likely, your coworker would just say, Honestly, that sounds great, and go back to making their coffee.", 0.55, 0.45),
    (7, "ACT_1", "Nothing bad happens if you tell the truth here. And yet, before you even think about it, you hear yourself say, Oh, it was nice! Got a few things done, caught up on some reading, went for a walk in the park.", 0.64, 0.45),
    (8, "ACT_1", "Then you walk back to your desk and realize you haven't set foot in a park in three weeks.", 0.56, 0.65),

    # ACT II: Bella DePaulo's Diary Study (1996)
    (9, "ACT_2", "Most of us have done some version of this. Saying, I'm on my way! when you haven't put your shoes on yet.", 0.58, 0.35),
    (10, "ACT_2", "Smiling and pretending you've heard of a band just so you don't have to stop the conversation.", 0.54, 0.40),
    (11, "ACT_2", "It doesn't mean you're manipulative. It's a habit almost everyone shares, and psychologists have actually measured how often it happens.", 0.54, 0.50),
    (12, "ACT_2", "Back in 1996, psychologist Bella DePaulo at the University of Virginia asked 147 ordinary people, college students and working adults, to keep a small diary for a week.", 0.53, 0.35),
    (13, "ACT_2", "Every time they misled someone, even slightly, they wrote it down.", 0.54, 0.45),
    (14, "ACT_2", "On average, people told one or two lies a day, coming up in roughly a quarter of their daily social interactions.", 0.56, 0.40),
    (15, "ACT_2", "More than seventy percent of those lies weren't about hiding something serious, getting money, or staying out of trouble.", 0.55, 0.38),
    (16, "ACT_2", "People lied about liking a sandwich that was dry, about why they were five minutes late, or about having seen a movie someone brought up at lunch.", 0.56, 0.40),
    (17, "ACT_2", "When DePaulo asked them afterward if anything bad would have happened if they'd just told the truth, most of them said no. Not really.", 0.55, 0.65),

    # ACT III: Why the Truth Feels Like More Work
    (18, "ACT_3", "Sometimes, telling the truth is just more trouble than it's worth. Not because you're afraid of getting caught. You just don't feel like explaining yourself.", 0.56, 0.50),
    (19, "ACT_3", "We're used to thinking that honesty is simple and lying takes effort. For a big lie, making up a whole story under pressure, that's definitely true.", 0.54, 0.35),
    (20, "ACT_3", "In casual conversation, though, it often works the other way around.", 0.58, 0.50),
    (21, "ACT_3", "Say a friend texts on Friday evening asking if you want to grab drinks. The honest reason you don't want to go isn't that you're upset with them.", 0.54, 0.35),
    (22, "ACT_3", "You're just tired, your week was long, and you've been looking forward to staying home in comfortable clothes.", 0.52, 0.45),
    (23, "ACT_3", "If you give that unfiltered answer, you often end up managing their reaction. They might wonder if you're mad at them, or try to talk you into it.", 0.55, 0.30),
    (24, "ACT_3", "Come on, just for one drink, it'll get you out of the house. Now a simple reply turns into a back-and-forth you don't really want to have.", 0.62, 0.40),
    (25, "ACT_3", "Compare that to: I'd love to, I just have a headache coming on.", 0.56, 0.38),
    (26, "ACT_3", "Nobody feels rejected, nobody argues with a headache, and the conversation wraps up in five seconds.", 0.56, 0.40),
    (27, "ACT_3", "Calling in an easy excuse isn't really about deception. It's just a way to avoid unnecessary friction.", 0.55, 0.65),

    # ACT IV: Avoiding Awkward Silence (Robert Feldman, 2002)
    (28, "ACT_4", "Avoiding plans makes sense. What's stranger are the lies that slip out when we're just making small talk.", 0.56, 0.45),
    (29, "ACT_4", "Someone mentions a neighborhood restaurant, or a book everybody's talking about, and you hear yourself say, Oh yeah, I've been meaning to go back there, even though you've never walked through the door.", 0.58, 0.40),
    (30, "ACT_4", "You're not even trying to impress them. You just didn't want the conversation to hit a wall.", 0.55, 0.50),
    (31, "ACT_4", "Psychologist Robert Feldman at the University of Massachusetts tested how naturally this happens in 2002.", 0.53, 0.35),
    (32, "ACT_4", "He paired up strangers, asked them to chat for ten minutes so they could get to know each other, and recorded the conversation.", 0.53, 0.35),
    (33, "ACT_4", "Afterward, he had each person watch the video back and point out every statement that wasn't completely accurate.", 0.54, 0.45),
    (34, "ACT_4", "Before watching the tape, almost everyone assumed they'd been totally honest.", 0.55, 0.38),
    (35, "ACT_4", "Once they saw the footage, around sixty percent realized they'd told at least one lie in just ten minutes, averaging nearly three small inaccuracies per conversation.", 0.58, 0.42),
    (36, "ACT_4", "People exaggerated how much they liked something, claimed familiarity with things they barely knew, and nodded along with opinions they didn't actually share.", 0.55, 0.38),
    (37, "ACT_4", "Most of it happened automatically because nobody wants to look odd or kill the flow of a normal chat. If the blunt truth creates an awkward pause, we smooth it over without noticing.", 0.55, 0.65),

    # ACT V: Why You Can't Take It Back
    (38, "ACT_5", "Once one of those small lies leaves your mouth, a funny thing happens: it's almost impossible to walk it back.", 0.58, 0.45),
    (39, "ACT_5", "Imagine telling a coworker you went hiking over the weekend, and then two seconds later stopping and saying, Wait, I don't know why I said that. I didn't go hiking. I stayed home all weekend.", 0.60, 0.40),
    (40, "ACT_5", "Confessing to a major secret makes sense to people. Confessing to a meaningless lie about a weekend walk just makes the whole moment deeply uncomfortable.", 0.56, 0.45),
    (41, "ACT_5", "So you don't correct it. When they follow up with, Oh nice, where did you go?, you name a trail you drove past last summer, just to close out a conversation neither of you even cared about a minute ago.", 0.58, 0.40),
    (42, "ACT_5", "One casual phrase pulls a second one behind it.", 0.56, 0.65),

    # ACT VI: The Quiet Cost (Sharot & Garrett 2016 + Aldert Vrij)
    (43, "ACT_6", "When a white lie is isolated, it seems harmless. Polite untruths help daily life run smoothly.", 0.53, 0.45),
    (44, "ACT_6", "In 2016, neuroscientists Tali Sharot and Neil Garrett studied what happens in the brain during repeated small dishonesty.", 0.54, 0.35),
    (45, "ACT_6", "Using fMRI scans, they focused on the amygdala, a region closely tied to the emotional tension or guilt people feel when doing something uncomfortable.", 0.54, 0.42),
    (46, "ACT_6", "What they found was interesting. As people repeatedly benefited from dishonesty, their emotional response to it gradually weakened.", 0.56, 0.38),
    (47, "ACT_6", "In other words, something that felt uncomfortable at first could become easier to do over time.", 0.55, 0.50),
    (48, "ACT_6", "There's also a simpler, everyday cost that deception researcher Aldert Vrij has studied for years: mental fatigue.", 0.56, 0.38),
    (49, "ACT_6", "Holding back what you actually think, or keeping track of two versions of the same small story, takes real attention.", 0.54, 0.40),
    (50, "ACT_6", "If you've ever walked away from a long social gathering feeling strangely drained even though nothing went wrong, part of that exhaustion comes from quietly editing yourself all evening.", 0.55, 0.65),

    # ACT VII: Taking a One-Second Beat
    (51, "ACT_7", "Stopping every white lie isn't realistic, and being bluntly honest at all times would probably just make life harder for the people around you.", 0.53, 0.45),
    (52, "ACT_7", "Most pointless lies happen in the first split second after someone asks a casual question, before you've decided what you actually want to say.", 0.55, 0.38),
    (53, "ACT_7", "Simply taking a half-second pause before replying, Hmm, honestly, breaks the automatic response just enough to give you a choice.", 0.56, 0.48),
    (54, "ACT_7", "When a question doesn't really carry high stakes, it helps to be a little more ordinary.", 0.54, 0.38),
    (55, "ACT_7", "The next time someone asks what you did over the weekend, saying, Honestly, I didn't do much at all, and I needed it, almost never lands poorly.", 0.57, 0.40),
    (56, "ACT_7", "More often than not, the other person looks noticeably relieved and says, Yeah, me too.", 0.58, 0.55),
    (57, "ACT_7", "We tell small, pointless lies because we're trying to look a little busier, a little more interesting, or easier to talk to.", 0.54, 0.38),
    (58, "ACT_7", "Everyone ends up protecting an image nobody was judging that closely anyway.", 0.56, 0.45),
    (59, "ACT_7", "Usually, real connection doesn't start when two people trade impressive weekend stories.", 0.55, 0.38),
    (60, "ACT_7", "It starts the moment someone admits they stayed home and did nothing, and makes it safe for the other person to tell the truth, too.", 0.58, 0.80),
]


def main():
    dev = kc.get_device()
    ref = kc.ensure_ref_voice_clip()
    model = kc.load_chatterbox(dev)
    sr = model.sr

    wav_parts = []
    manifest = []
    cursor = 0.0
    t_all = time.time()

    for seg_id, act, text, exag, pause_s in SCRIPT_CHUNKS:
        chunk_wav_path = os.path.join(CHUNKS_DIR, f"seg_{seg_id:02d}.wav")
        if os.path.exists(chunk_wav_path):
            wav_np, file_sr = sf.read(chunk_wav_path, dtype="float32")
            assert file_sr == sr
            dur = len(wav_np) / sr
            print(f"[{seg_id:02d}/{len(SCRIPT_CHUNKS)}] CACHED {dur:.2f}s | {text[:60]}...")
        else:
            t0 = time.time()
            wav_tensor = model.generate(
                text,
                audio_prompt_path=ref,
                exaggeration=exag,
                cfg_weight=0.40,
            )
            wav_np = wav_tensor.squeeze().detach().cpu().numpy().astype(np.float32)
            # Trim tiny trailing silence > 0.35s if Chatterbox pads end, keeping natural decay
            sf.write(chunk_wav_path, wav_np, sr)
            dur = len(wav_np) / sr
            print(f"[{seg_id:02d}/{len(SCRIPT_CHUNKS)}] {dur:.2f}s (gen {time.time()-t0:.1f}s) | {text[:60]}...", flush=True)

        seg_start = cursor
        seg_end = cursor + dur
        manifest.append({
            "id": seg_id,
            "act": act,
            "start": round(seg_start, 3),
            "end": round(seg_end, 3),
            "duration": round(dur, 3),
            "pause_after": pause_s,
            "text": text,
            "wav": chunk_wav_path,
        })
        wav_parts.append(wav_np)
        wav_parts.append(np.zeros(int(sr * pause_s), dtype=np.float32))
        cursor = seg_end + pause_s

    full_wav = np.concatenate(wav_parts)
    raw_wav = os.path.join(AUDIO_DIR, "ep02_full_voice_raw.wav")
    out_mp3 = os.path.join(AUDIO_DIR, "ep02_full_voice_14lufs.mp3")
    sf.write(raw_wav, full_wav, sr)

    subprocess.run([
        "ffmpeg", "-y", "-i", raw_wav,
        "-af", "loudnorm=I=-14.0:TP=-1.2:LRA=11",
        "-ar", "48000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "192k",
        out_mp3
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    manifest_path = os.path.join(AUDIO_DIR, "ep02_full_segments.json")
    with open(manifest_path, "w") as f:
        json.dump({
            "total_duration": round(len(full_wav) / sr, 3),
            "sample_rate": sr,
            "segments": manifest,
        }, f, indent=2)

    print(f"DONE FULL VOICEOVER: {out_mp3} ({len(full_wav)/sr:.2f}s) in {time.time()-t_all:.1f}s", flush=True)


if __name__ == "__main__":
    main()
