#!/usr/bin/env python3
"""
Entrypoint wrapper for Proof of Wonder Documentary Pipeline v3.0.

Allows running `pow_studio.cli` from any working directory without manually setting `PYTHONPATH`:
  /Applications/code/science-knowledge/MoneyPrinterTurbo/.venv/bin/python \
    youtube-shorts-channel/pipeline/run_documentary.py all \
    --manifest youtube-shorts-channel/episodes/hidden_earth_blood_falls_v3_documentary.yaml
"""

from __future__ import annotations

import sys
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from pow_studio.cli import app  # noqa: E402

if __name__ == "__main__":
    app()
