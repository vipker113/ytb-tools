#!/usr/bin/env python3
"""
Kairo Spark — Real-ESRGAN x4v3 (SRVGGNetCompact) Apple Silicon MPS Upscaler
Blends realesr-general-x4v3.pth + realesr-general-wdn-x4v3.pth (dn=0.5) to remove JPEG artifacts
and sharpen 2D Adobe Flash black ink outlines before Lanczos downsampling to razor-sharp 1920x1080.
"""

import os
import sys
import time
import glob
import argparse
import numpy as np
from PIL import Image
import torch
import torch.nn as nn
import torch.nn.functional as F

MODELS_DIR = "/Applications/code/science-knowledge/ytb-tools/scripts/models"
W_SHARP = os.path.join(MODELS_DIR, "realesr-general-x4v3.pth")
W_WDN = os.path.join(MODELS_DIR, "realesr-general-wdn-x4v3.pth")


class SRVGGNetCompact(nn.Module):
    def __init__(self, num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=32, upscale=4):
        super().__init__()
        self.upscale = upscale
        self.body = nn.ModuleList()
        self.body.append(nn.Conv2d(num_in_ch, num_feat, 3, 1, 1))
        self.body.append(nn.PReLU(num_parameters=num_feat))
        for _ in range(num_conv):
            self.body.append(nn.Conv2d(num_feat, num_feat, 3, 1, 1))
            self.body.append(nn.PReLU(num_parameters=num_feat))
        self.body.append(nn.Conv2d(num_feat, num_out_ch * upscale * upscale, 3, 1, 1))
        self.upsampler = nn.PixelShuffle(upscale)

    def forward(self, x):
        out = x
        for layer in self.body:
            out = layer(out)
        out = self.upsampler(out)
        base = F.interpolate(x, scale_factor=self.upscale, mode="nearest")
        return out + base


def load_model(device_str="mps", dn=0.5):
    device = torch.device(device_str if (device_str == "mps" and torch.backends.mps.is_available()) else "cpu")
    sd_s = torch.load(W_SHARP, map_location="cpu", weights_only=False)
    if "params" in sd_s:
        sd_s = sd_s["params"]
    if dn > 0 and os.path.exists(W_WDN):
        sd_w = torch.load(W_WDN, map_location="cpu", weights_only=False)
        if "params" in sd_w:
            sd_w = sd_w["params"]
        sd = {k: (1.0 - dn) * sd_s[k] + dn * sd_w[k] for k in sd_s}
    else:
        sd = sd_s
    model = SRVGGNetCompact(num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=32, upscale=4)
    model.load_state_dict(sd, strict=True)
    model.eval().to(device)
    return model, device


@torch.no_grad()
def upscale_pil(img: Image.Image, model, device, target_size=(1920, 1080), tile=512, pad=16):
    arr = np.array(img.convert("RGB"), dtype=np.float32) / 255.0
    h, w, _ = arr.shape
    scale = model.upscale
    out = np.zeros((h * scale, w * scale, 3), dtype=np.float32)

    # Tile inference for predictable low memory on MPS
    for y in range(0, h, tile):
        for x in range(0, w, tile):
            y0 = max(0, y - pad)
            x0 = max(0, x - pad)
            y1 = min(h, y + tile + pad)
            x1 = min(w, x + tile + pad)
            patch = arr[y0:y1, x0:x1, :]
            t = torch.from_numpy(patch).permute(2, 0, 1).unsqueeze(0).to(device)
            pred = model(t).clamp_(0, 1).squeeze(0).permute(1, 2, 0).cpu().numpy()

            # Valid interior region without pad overlap
            cy0 = (y - y0) * scale
            cx0 = (x - x0) * scale
            cy1 = cy0 + min(tile, h - y) * scale
            cx1 = cx0 + min(tile, w - x) * scale
            out[y * scale:min(h, y + tile) * scale, x * scale:min(w, x + tile) * scale, :] = pred[cy0:cy1, cx0:cx1, :]

    up_img = Image.fromarray((out * 255.0 + 0.5).astype(np.uint8), mode="RGB")
    if target_size:
        up_img = up_img.resize(target_size, Image.Resampling.LANCZOS)
    return up_img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Single image file or directory of PNG/JPG files")
    ap.add_argument("--output", required=True, help="Output file or directory")
    ap.add_argument("--dn", type=float, default=0.55, help="Denoise blend (0=sharp only, 1=wdn only)")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    args = ap.parse_args()

    t0 = time.time()
    model, device = load_model("mps", dn=args.dn)
    print(f"Loaded Real-ESRGAN x4v3 (dn={args.dn}) on {device} in {time.time()-t0:.2f}s")

    target = (args.width, args.height) if args.width > 0 else None

    if os.path.isfile(args.input):
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        ts = time.time()
        im = Image.open(args.input)
        res = upscale_pil(im, model, device, target_size=target)
        res.save(args.output, quality=96)
        print(f"Upscaled {os.path.basename(args.input)} {im.size} -> {res.size} in {time.time()-ts:.2f}s")
    else:
        os.makedirs(args.output, exist_ok=True)
        files = sorted(
            glob.glob(os.path.join(args.input, "*.png"))
            + glob.glob(os.path.join(args.input, "*.jpg"))
            + glob.glob(os.path.join(args.input, "*.jpeg"))
        )
        for i, fp in enumerate(files, 1):
            base = os.path.splitext(os.path.basename(fp))[0] + ".png"
            out_fp = os.path.join(args.output, base)
            ts = time.time()
            im = Image.open(fp)
            res = upscale_pil(im, model, device, target_size=target)
            res.save(out_fp)
            print(f"  [{i}/{len(files)}] {base}: {im.size} -> {res.size} ({time.time()-ts:.2f}s)")


if __name__ == "__main__":
    main()
