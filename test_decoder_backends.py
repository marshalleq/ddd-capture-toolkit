#!/usr/bin/env python3
"""Tests for decoder_backends.py: command lines, progress parsing, and refusals."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from decoder_backends import select_decoder, ansi_stripped
from project_flags import DECODE_FLAGS, decode_arguments, decode_flag_state


def test_registry():
    assert select_decoder('vhs-decode').key == 'vhs-decode'
    assert select_decoder('tape-decode').key == 'tape-decode'
    try:
        select_decoder('nonsense')
    except ValueError as e:
        assert 'Unknown decoder backend' in str(e)
    else:
        raise AssertionError('unknown decoder key was accepted')


def test_vhs_decode_command():
    d = select_decoder('vhs-decode')
    tokens, structural, problems = decode_arguments(None, 'vhs-decode')
    assert not problems
    cmd, problems = d.build_command('/x/vhs-decode', {'video_standard': 'pal', 'tape_speed': 'LP'},
                                    tokens, structural, 'in.flac', '/o/out', threads=3)
    assert not problems
    assert cmd == ['/x/vhs-decode', '--tf', 'vhs', '-t', '3', '--ts', 'LP', '--pal',
                   '--no_resample', '--ire0_adjust', 'in.flac', '/o/out']
    assert d.parse_progress('File Frame 1000: VHS') == 1000
    assert d.parse_progress('something else') is None


def test_tape_decode_command():
    d = select_decoder('tape-decode')
    tokens, structural, problems = decode_arguments(
        None, 'tape-decode', '--sub_deemphasis --high_boost 1.5 --chroma_trap')
    assert not problems, problems
    cmd, problems = d.build_command('/x/tape-decode', {'video_standard': 'ntsc', 'tape_speed': 'EP'},
                                    tokens, structural, 'in.ddd.flac', '/o/out', threads=3)
    assert not problems, problems
    assert cmd[:3] == ['/x/tape-decode', 'decode', '--profile']
    assert cmd[3] == 'NTSC_VHS_EP'
    assert '--ire0-adjust' in cmd and '--subdeemp' in cmd and '--chroma-trap' in cmd
    assert cmd[cmd.index('--high-boost') + 1] == '1.5'
    assert '--no_resample' not in cmd and '--no-resample' not in cmd
    assert cmd[cmd.index('--luma-out') + 1] == '/o/out.tbc'
    assert cmd[cmd.index('--chroma-out') + 1] == '/o/out_chroma.tbc'
    assert cmd[cmd.index('--metadata-out') + 1] == '/o/out.tbc.json'
    assert cmd[cmd.index('--mt-threads') + 1] == '4'
    assert cmd[-1] == 'in.ddd.flac'
    assert select_decoder('tape-decode').profile({'video_standard': 'pal', 'tape_speed': 'SP'}) == 'PAL_VHS'


def test_free_form_follows_the_chosen_decoder():
    # either spelling is accepted and written the way the chosen decoder wants it
    assert decode_arguments(None, 'tape-decode', '--nodd')[0][-1] == '--no-dod'
    assert decode_arguments(None, 'tape-decode', '--no-dod')[0][-1] == '--no-dod'
    assert decode_arguments(None, 'vhs-decode', '--subdeemp')[0][-1] == '--sub_deemphasis'
    # a value follows its flag
    assert decode_arguments(None, 'tape-decode', '--high_boost 2')[0][-2:] == ['--high-boost', '2']
    # anything the toolkit does not know passes through for the decoder to judge
    assert decode_arguments(None, 'tape-decode', '--notch 3.58')[0][-2:] == ['--notch', '3.58']


def test_unsupported_and_forced_settings():
    assert decode_flag_state(DECODE_FLAGS['no_resample'], 'tape-decode') == 'forced'
    assert decode_flag_state(DECODE_FLAGS['no_resample'], 'vhs-decode') == 'supported'
    assert decode_flag_state(DECODE_FLAGS['ire0_adjust'], 'tape-decode') == 'supported'
    # forced: nothing is passed, so the setting cannot be turned off
    tokens, _, _ = decode_arguments(None, 'tape-decode')
    assert not any('resample' in t for t in tokens)
    # a setting a decoder lacks is a problem when asked for in free-form
    fake = dict(DECODE_FLAGS['chroma_trap']['engines'])
    del DECODE_FLAGS['chroma_trap']['engines']['tape-decode']
    try:
        assert decode_flag_state(DECODE_FLAGS['chroma_trap'], 'tape-decode') == 'unsupported'
        _, _, problems = decode_arguments(None, 'tape-decode', '--chroma_trap')
        assert problems and 'not available in tape-decode' in problems[0]
    finally:
        DECODE_FLAGS['chroma_trap']['engines'].update(fake)


def test_sample_rate_is_passed_to_the_decoder():
    td = select_decoder('tape-decode')
    cmd, _ = td.build_command('/x/td', {'sample_rate_mhz': 20.0}, [], set(), 'in.flac', '/o/out')
    assert cmd[cmd.index('--frequency') + 1] == '20'
    cmd, _ = td.build_command('/x/td', {}, [], set(), 'in.flac', '/o/out')
    assert cmd[cmd.index('--frequency') + 1] == '40'
    vd = select_decoder('vhs-decode')
    cmd, _ = vd.build_command('/x/vd', {'sample_rate_mhz': 20.0}, [], set(), 'in.flac', '/o/out')
    assert cmd[cmd.index('-f') + 1] == '20'
    cmd, _ = vd.build_command('/x/vd', {'sample_rate_mhz': 40.0}, [], set(), 'in.flac', '/o/out')
    assert '-f' not in cmd


def test_tape_decode_skip_chroma():
    d = select_decoder('tape-decode')
    tokens, structural, _ = decode_arguments(None, 'tape-decode', '--skip_chroma --nodd')
    cmd, problems = d.build_command('/x/td', {}, tokens, structural, 'in.flac', '/o/out')
    assert not problems
    assert '--chroma-out' not in cmd and '--no-dod' in cmd and '--skip_chroma' not in cmd


def test_tape_decode_refuses_what_it_cannot_do():
    d = select_decoder('tape-decode')
    _, problems = d.build_command('/x/td', {}, [], set(), 'in.flac', '/o/out', segment=(100, 500))
    assert any('segment' in p for p in problems)
    assert d.input_problem('capture.lds')
    assert d.input_problem('capture.ldf')
    assert d.input_problem('capture.ddd.flac') is None


def test_tape_decode_progress():
    d = select_decoder('tape-decode')
    line = ansi_stripped('\x1b[2m2026-10-31T21:59:34Z\x1b[0m  \x1b[32m INFO \x1b[0m  '
                         'tape_decode::writer: Decoded 500 fields so far in 7.167s (34.88 FPS)')
    assert d.parse_progress(line) == 250
    assert d.parse_progress('Unexpected vsync arbitrage') is None


def test_tape_decode_stale_outputs_and_failure_reason():
    d = select_decoder('tape-decode')
    with tempfile.TemporaryDirectory() as tmp:
        base = os.path.join(tmp, 'Cap')
        assert d.stale_outputs(base) == []
        with open(base + '.tbc', 'wb') as f:
            f.write(b'x')
        assert d.stale_outputs(base) == [base + '.tbc']
    reason = d.failure_reason(1, ['noise', 'error: failed to read FLAC'])
    assert 'failed to read FLAC' in reason


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"{len(tests)} decoder backend checks passed")


if __name__ == '__main__':
    main()
