#!/usr/bin/env python3
"""Compatibility entry point for the full source-path DMA ownership harness.

The runner explicitly reports the still-unresolved issued-timeout path. Use
--require-timeout-contained as the release gate; this source-only correction
must not be promoted to a firmware candidate while that gate fails.
"""
import pathlib, subprocess, sys
subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name('test-dma-ownership.py')), *sys.argv[1:]], check=True)
