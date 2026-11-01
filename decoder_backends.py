#!/usr/bin/env python3
"""
Decoder backends: how the toolkit runs the RF -> TBC decode.

A backend answers these questions:
  - is it installed, and where?                (available / executable)
  - what command line decodes this capture?    (build_command)
  - what output files does it write?           (output_files)
  - which line of its output is progress?      (parse_progress)
  - how many cores does one decode want?       (cores_wanted)
  - which capture file formats can it read?    (input_problem)

Exactly one backend is used, chosen with "decoder_backend" in config/config.json.
There is no automatic selection and no fallback: if the chosen decoder is not
installed or cannot read the capture, the job fails with a message saying so.

To add a backend, subclass DecoderBackend, set `key` and `label`, implement the
methods and call register_decoder() at import time.
"""

import os
import re
import shutil

DEFAULT_DECODER = 'tape-decode'

_DECODERS = {}


def register_decoder(backend):
    _DECODERS[backend.key] = backend
    return backend


class DecoderBackend:
    key = ''
    label = ''
    command_name = ''               # program name looked up in PATH
    install_hint = 'Run setup.sh to install it.'

    def executable(self):
        return shutil.which(self.command_name)

    def available(self):
        return self.executable() is not None

    def input_problem(self, input_file):
        """Return a message if this decoder cannot read input_file, else None."""
        return None

    def build_command(self, exe, job_params, tokens, structural, input_file, output_base,
                      segment=None, threads=3):
        """Return (argv, problems).

        tokens      the decode settings already in this decoder's own spelling
                    (see project_flags.decode_arguments)
        structural  settings this backend applies itself rather than as a flag
        problems    anything asked for that this decoder cannot do; the caller
                    fails the job with them."""
        raise NotImplementedError

    def output_files(self, output_base):
        """Return (luma_tbc, metadata_json) paths a successful decode must leave."""
        return output_base + '.tbc', output_base + '.tbc.json'

    def stale_outputs(self, output_base):
        """Existing non-empty files this decoder would refuse to write over."""
        return []

    def parse_progress(self, line):
        """Return the absolute number of frames done if this line says so, else None."""
        return None

    def cores_wanted(self, threads):
        return max(2, threads + 1)

    def failure_reason(self, return_code, output_tail):
        """Explain a failed or empty decode from the tail of its output."""
        if return_code != 0:
            reason = f"{self.command_name} exited with code {return_code}"
        else:
            reason = f"{self.command_name} finished but wrote no decoded output"
        if output_tail:
            reason += f". Last output: {output_tail[-1].strip()[:160]}"
        return reason


class VhsDecodeBackend(DecoderBackend):
    key = 'vhs-decode'
    label = 'vhs-decode (upstream Python decoder)'
    command_name = 'vhs-decode'

    def build_command(self, exe, job_params, tokens, structural, input_file, output_base,
                      segment=None, threads=3):
        cmd = [exe, '--tf', 'vhs', '-t', str(threads),
               '--ts', job_params.get('tape_speed', 'SP')]
        cmd.append('--pal' if job_params.get('video_standard', 'pal').lower() == 'pal' else '--ntsc')
        if job_params.get('sample_rate_mhz', 40) != 40:
            cmd.extend(['-f', str(job_params['sample_rate_mhz'])])
        cmd.extend(tokens)
        if segment:
            start, length = segment
            cmd.extend(['-s', str(start), '-l', str(length)])
        cmd.extend([input_file, output_base])
        return cmd, []

    def parse_progress(self, line):
        m = re.search(r'File Frame (\d+):', line)
        return int(m.group(1)) if m else None

    def failure_reason(self, return_code, output_tail):
        reason = super().failure_reason(return_code, output_tail)
        tail = output_tail or []
        if any('Existing decode files found' in l for l in tail):
            # vhs-decode lists the files it refuses to overwrite after that line
            found = [os.path.basename(l.strip()) for l in tail if l.strip().startswith(os.sep)]
            return ("vhs-decode will not decode over an earlier decode's files"
                    + (f" ({', '.join(found)})" if found else "")
                    + ". Delete them to decode again, or re-run the decode with overwrite")
        if any('without handling any frames' in l for l in tail):
            return (f"{self.command_name} finished but wrote no decoded output. It read no frames "
                    "from the input: check the RF file and video standard, and that "
                    "ld-ldf-reader works (run check_dependencies.py)")
        return reason


class TapeDecodeBackend(DecoderBackend):
    """namazso/tape-decode-rs: the Rust port of vhs-decode."""
    key = 'tape-decode'
    label = 'tape-decode (Rust decoder, namazso/tape-decode-rs)'
    command_name = 'tape-decode'
    install_hint = 'Run setup.sh to install it (build-scripts/install-tape-decode.sh).'

    SAMPLE_RATE_MHZ = 40            # the Domesday Duplicator captures at 40 MHz

    def input_problem(self, input_file):
        if not input_file.lower().endswith('.flac'):
            return (f"tape-decode reads FLAC captures (.flac / .ddd.flac); "
                    f"{os.path.basename(input_file)} is not one. Convert it with: "
                    f"python3 convert_to_flac.py {input_file}   (or set decoder_backend to vhs-decode)")
        return None

    def profile(self, job_params):
        standard = job_params.get('video_standard', 'pal').upper()
        speed = job_params.get('tape_speed', 'SP').upper()
        suffix = '' if speed == 'SP' else '_' + speed
        return f"{standard}_VHS{suffix}"

    def build_command(self, exe, job_params, tokens, structural, input_file, output_base,
                      segment=None, threads=3):
        problems = []
        if segment:
            problems.append("tape-decode cannot decode just a segment (no start/length option); "
                            "turn segment mode off for this project or set decoder_backend to vhs-decode")
        cmd = [exe, 'decode', '--profile', self.profile(job_params),
               '--frequency', str(job_params.get('sample_rate_mhz', self.SAMPLE_RATE_MHZ)), '--input-format', 'flac']
        cmd.extend(tokens)
        cmd.extend(['--luma-out', output_base + '.tbc'])
        if 'skip_chroma' not in structural:
            cmd.extend(['--chroma-out', output_base + '_chroma.tbc'])
        cmd.extend(['--metadata-out', output_base + '.tbc.json',
                    '--mt-threads', str(self.cores_wanted(threads)), input_file])
        return cmd, problems

    def stale_outputs(self, output_base):
        found = []
        for suffix in ('.tbc', '_chroma.tbc', '.tbc.json'):
            path = output_base + suffix
            if os.path.isfile(path) and os.path.getsize(path) > 0:
                found.append(path)
        return found

    def parse_progress(self, line):
        # "Decoded 500 fields so far in 7.167s (34.88 FPS)" (two fields per frame)
        m = re.search(r'Decoded (\d+) fields so far', line)
        return int(m.group(1)) // 2 if m else None

    def cores_wanted(self, threads):
        # One worker thread per core was fastest on the benchmark (4 cores, 4 threads)
        return max(2, threads + 1)

    def failure_reason(self, return_code, output_tail):
        reason = super().failure_reason(return_code, output_tail)
        for line in reversed(output_tail or []):
            if line.lstrip().lower().startswith('error:'):
                return f"tape-decode failed: {line.strip()[:200]}"
        return reason


register_decoder(VhsDecodeBackend())
register_decoder(TapeDecodeBackend())


def select_decoder(key=None):
    """
    Return the decoder backend to use.

    key: a registered key, or None to read "decoder_backend" from the config
    (default 'tape-decode'). An unknown key is an error.
    """
    if key is None:
        from config import load_config
        key = load_config().get('decoder_backend', DEFAULT_DECODER)
    backend = _DECODERS.get(key)
    if backend is None:
        raise ValueError(f"Unknown decoder backend '{key}'. Known: {', '.join(sorted(_DECODERS))}.")
    return backend


def ansi_stripped(line):
    return re.sub(r'\x1b\[[0-9;]*m', '', line)
