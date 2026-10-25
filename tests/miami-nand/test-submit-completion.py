#!/usr/bin/env python3
"""Compatibility entry point for the full source-path DMA ownership harness.

Use --require-timeout-contained as the joint source gate. The isolated candidate
also requires actual --provider, --driver-core and --virt-dma inputs so a
caller-only model cannot accidentally be mistaken for complete lifetime proof.
"""
import pathlib, subprocess, sys
subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name('test-dma-ownership.py')), *sys.argv[1:]], check=True)
