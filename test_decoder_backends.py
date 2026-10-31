#!/usr/bin/env python3
"""Tests for decoder_backends.py: command lines, progress parsing, and refusals."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from decoder_backends import select_decoder, ansi_stripped


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
    cmd, problems = d.build_command('/x/vhs-decode', {'video_standard': 'pal', 'tape_speed': 'LP'},
                                    ['--no_resample', '--ire0_adjust'], 'in.flac', '/o/out', threads=3)
    assert not problems
    assert cmd == ['/x/vhs-decode', '--tf', 'vhs', '-t', '3', '--ts', 'LP', '--pal',
                   '--no_resample', '--ire0_adjust', 'in.flac', '/o/out']
    assert d.parse_progress('File Frame 1000: VHS') == 1000
    assert d.parse_progress('something else') is None


def test_tape_decode_command():
    d = select_decoder('tape-decode')
    cmd, problems = d.build_command(
        '/x/tape-decode', {'video_standard': 'ntsc', 'tape_speed': 'EP'},
        ['--no_resample', '--ire0_adjust', '--sub_deemphasis', '--high_boost', '1.5'],
        'in.ddd.flac', '/o/out', threads=3)
    assert not problems, problems
    assert cmd[:3] == ['/x/tape-decode', 'decode', '--profile']
    assert cmd[3] == 'NTSC_VHS_EP'
    assert '--ire0-adjust' in cmd and '--subdeemp' in cmd
    assert cmd[cmd.index('--high-boost') + 1] == '1.5'
    assert '--no_resample' not in cmd
    assert cmd[cmd.index('--luma-out') + 1] == '/o/out.tbc'
    assert cmd[cmd.index('--chroma-out') + 1] == '/o/out_chroma.tbc'
    assert cmd[cmd.index('--metadata-out') + 1] == '/o/out.tbc.json'
    assert cmd[cmd.index('--mt-threads') + 1] == '4'
    assert cmd[-1] == 'in.ddd.flac'
    assert select_decoder('tape-decode').profile({'video_standard': 'pal', 'tape_speed': 'SP'}) == 'PAL_VHS'


def test_tape_decode_skip_chroma_and_nodd():
    d = select_decoder('tape-decode')
    cmd, problems = d.build_command('/x/td', {}, ['--skip_chroma', '--nodd'], 'in.flac', '/o/out')
    assert not problems
    assert '--chroma-out' not in cmd and '--no-dod' in cmd


def test_tape_decode_refuses_what_it_cannot_do():
    d = select_decoder('tape-decode')
    _, problems = d.build_command('/x/td', {}, ['--made_up_flag'], 'in.flac', '/o/out')
    assert any('--made_up_flag' in p for p in problems)
    _, problems = d.build_command('/x/td', {}, [], 'in.flac', '/o/out', segment=(100, 500))
    assert any('segment' in p for p in problems)
    _, problems = d.build_command('/x/td', {'additional_params': '--foo'}, [], 'in.flac', '/o/out')
    assert any('additional' in p for p in problems)
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
