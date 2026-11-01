#!/usr/bin/env python3
"""Tests for benchmark/bench.py: variant parsing, summaries and the disturbance check."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'benchmark'))

import bench


def test_variant_parsing():
    v = bench.parse_variant('tape-decode@native:v1.0', '/w')
    assert (v.kind, v.label) == ('tape-decode', 'tape-decode native:v1.0')
    v = bench.parse_variant('vhs-decode@v0.4.0#v0.4.0 compiled', '/w')
    assert (v.kind, v.label) == ('vhs-decode', 'v0.4.0 compiled')
    for bad in ('nonsense', 'exe=/no/such/file:tape-decode', 'exe=' + sys.executable + ':other'):
        try:
            bench.parse_variant(bad, '/w')
        except ValueError:
            continue
        raise AssertionError(f'{bad} was accepted')


def test_summary_ignores_disturbed_and_warmup_runs():
    runs = {'a': [{'fps': 99.0, 'cpu_s': 1, 'peak_rss_mb': 1, 'warmup': True},
                  {'fps': 10.0, 'cpu_s': 100, 'peak_rss_mb': 500, 'warmup': False},
                  {'fps': 11.0, 'cpu_s': 110, 'peak_rss_mb': 600, 'warmup': False},
                  {'fps': 1.0, 'cpu_s': 5, 'peak_rss_mb': 5, 'warmup': False, 'disturbed_by': [123]}],
            'b': [{'error': 'boom', 'warmup': True}]}
    rows = {r['variant']: r for r in bench.summarise(runs, 'pal', 'a')}
    assert rows['a']['fps'] == 10.5 and rows['a']['runs'] == 2
    assert abs(rows['a']['hour_min'] - 90000 / 10.5 / 60) < 1e-9
    assert rows['b']['error'] == 'boom'
    table = bench.format_table(list(rows.values()), {'a': 'A', 'b': 'B'}, 'a')
    assert 'FAILED: boom' in table and '1.00x' in table


def test_foreign_decoders_found_by_name_but_not_our_own_tree():
    table = {10: (1, 100, 'tape-decode decode --profile X'), 11: (10, 50, 'tape-decode worker'),
             12: (1, 100, '/usr/bin/vhs-decode --tf vhs'), 13: (1, 10, 'python bench.py --sample x'),
             14: (1, 10, 'bash')}
    mine = bench.descendants(table, 10)
    assert mine == {10, 11}
    assert bench.foreign_decoders(table, mine) == [12]


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"{len(tests)} benchmark checks passed")


if __name__ == '__main__':
    main()
