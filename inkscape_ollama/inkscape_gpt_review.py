#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""InkscapeGPT review mode entry point."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from inkscape_gpt import InkscapeGPTReviewExtension

if __name__ == "__main__":
    InkscapeGPTReviewExtension().run()
