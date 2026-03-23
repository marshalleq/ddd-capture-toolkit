#!/usr/bin/env python3
"""
Script to mimic audio alignment by creating dummy input and output files for testing
"""

import os

# Dummy paths
input_wav = "./dummy_input.wav"
output_wav = "./dummy_output.wav"
tbc_json = "./dummy_tbc.json"

# Create dummy files to simulate real inputs
open(input_wav, 'a').close()
open(output_wav, 'a').close()
open(tbc_json, 'a').close()

print(f"Created dummy input WAV file: {input_wav}")
print(f"Created dummy TBC JSON file: {tbc_json}")
print(f"Dummy output WAV will be created at: {output_wav}")
