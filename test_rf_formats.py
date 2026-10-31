#!/usr/bin/env python3
"""
Checks for native .ddd.flac capture support (rf_formats, project discovery,
workflow status, frame counts for progress/ETA, capture backends).

Run:  python3 test_rf_formats.py
No hardware, no external tools. Builds small synthetic projects in a temp folder.
"""

import os
import struct
import sys
import tempfile

import rf_formats
from project_discovery import ProjectDiscovery
from workflow_analyzer import WorkflowAnalyzer, WorkflowStep, StepStatus

FAILED = []


def check(name, condition, detail=""):
    print(f"  {'PASS' if condition else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not condition else ""))
    if not condition:
        FAILED.append(name)


def flac_header(total_samples, rate_label=40000, tags=None):
    """Minimal FLAC header: 'fLaC' + STREAMINFO (+ VORBIS_COMMENT when tags are given)."""
    info = struct.pack('>HHBBB', 4096, 4096, 0, 0, 0) + struct.pack('>BBB', 0, 0, 0)
    packed = (rate_label << 44) | (0 << 41) | (15 << 36) | total_samples   # mono, 16 bit
    info += struct.pack('>Q', packed) + b'\x00' * 16
    out = b'fLaC' + bytes([0x00 if tags else 0x80]) + struct.pack('>I', len(info))[1:] + info
    if tags:
        vendor = b'test'
        body = struct.pack('<I', len(vendor)) + vendor + struct.pack('<I', len(tags))
        for key, value in tags.items():
            comment = f'{key}={value}'.encode()
            body += struct.pack('<I', len(comment)) + comment
        out += bytes([0x84]) + struct.pack('>I', len(body))[1:] + body
    return out


def make(path, size=2 * 1024 * 1024, head=b''):
    with open(path, 'wb') as f:
        f.write(head)
        f.write(b'\0' * max(0, size - len(head)))


def test_names():
    print("\nrf_formats: names")
    check("suffix .ddd.flac", rf_formats.rf_suffix('/a/Foo.ddd.flac') == '.ddd.flac')
    check("plain .flac is not RF", rf_formats.rf_suffix('/a/Foo.flac') is None)
    check("base of .ddd.flac", rf_formats.rf_base_path('/a/Foo.ddd.flac') == '/a/Foo')
    check("base of .lds", rf_formats.rf_base_path('/a/Foo.lds') == '/a/Foo')
    check("tbc name from native", rf_formats.rf_with_suffix('/a/Foo.ddd.flac', '.tbc') == '/a/Foo.tbc')
    check("tbc name from lds", rf_formats.rf_with_suffix('/a/Foo.lds', '.tbc') == '/a/Foo.tbc')
    check("non-RF path gets suffix appended", rf_formats.rf_with_suffix('/a/Foo.xyz', '.tbc') == '/a/Foo.xyz.tbc')
    check("metadata native", rf_formats.capture_metadata_path('/a/Foo.ddd.flac') == '/a/Foo.ddd.yaml')
    check("metadata legacy", rf_formats.capture_metadata_path('/a/Foo.lds') == '/a/Foo.json')
    check("primary capture", rf_formats.is_primary_capture('x.ddd.flac') and rf_formats.is_primary_capture('x.lds')
          and not rf_formats.is_primary_capture('x.ldf'))


def test_durations(tmp):
    print("\nrf_formats: capture duration (drives frame counts, progress and ETA)")
    # native: header + DDD_SAMPLE_RATE_HZ tag win over the yaml (they travel with the file)
    p = os.path.join(tmp, 'n1.ddd.flac')
    make(p, head=flac_header(400_000_000, tags={'DDD_SAMPLE_RATE_HZ': '40000000'}))
    with open(os.path.join(tmp, 'n1.ddd.yaml'), 'w') as f:
        f.write('"capture":\n  "duration_seconds": 99.0\n  "samples": 400556032\n')
    check("header+tag duration preferred", abs(rf_formats.capture_duration_seconds(p) - 10.0) < 1e-6,
          str(rf_formats.capture_duration_seconds(p)))
    # a 20 Msps capture: label 20000, real rate in the tag
    p20 = os.path.join(tmp, 'n20.ddd.flac')
    make(p20, head=flac_header(156_000_000, rate_label=20000, tags={'DDD_SAMPLE_RATE_HZ': '20000000'}))
    check("20 Msps duration", abs(rf_formats.capture_duration_seconds(p20) - 7.8) < 1e-6)
    # no tags: label x 1000
    p2 = os.path.join(tmp, 'n2.ddd.flac')
    make(p2, head=flac_header(315_621_376))
    d = rf_formats.capture_duration_seconds(p2)
    check("header-only duration (label x 1000)", d is not None and abs(d - 7.8905344) < 1e-6, str(d))
    # MISRC-style tags
    pm = os.path.join(tmp, 'm1.ddd.flac')
    make(pm, head=flac_header(400556, tags={'RF_TOTAL_SAMPLES': '400556032', 'RF_SAMPLE_RATE': '40000000'}))
    check("MISRC-style tags", abs(rf_formats.capture_duration_seconds(pm) - 10.0139008) < 1e-6)
    # header unusable (0 samples, e.g. unfinished) -> yaml
    p0 = os.path.join(tmp, 'n0.ddd.flac')
    make(p0, head=flac_header(0))
    with open(os.path.join(tmp, 'n0.ddd.yaml'), 'w') as f:
        f.write('"capture":\n  "duration_seconds": 12.5\n')
    check("falls back to yaml when header has no length", rf_formats.capture_duration_seconds(p0) == 12.5)
    # .ddd.s16 has no header: yaml only
    ps = os.path.join(tmp, 's1.ddd.s16')
    make(ps)
    with open(os.path.join(tmp, 's1.ddd.yaml'), 'w') as f:
        f.write('"capture":\n  "samples": 800000000\n  "sample_rate_hz": 40000000\n')
    check("s16 duration from yaml samples/rate", rf_formats.capture_duration_seconds(ps) == 20.0)
    # legacy json
    p3 = os.path.join(tmp, 'l1.lds')
    make(p3)
    with open(os.path.join(tmp, 'l1.json'), 'w') as f:
        f.write('{"captureInfo": {"durationInMilliseconds": 60000}}')
    check("legacy json duration", rf_formats.capture_duration_seconds(p3) == 60.0)
    check("missing metadata -> None", rf_formats.capture_duration_seconds(os.path.join(tmp, 'zzz.lds')) is None)

    from parallel_vhs_decode import ParallelVHSDecoder
    dec = ParallelVHSDecoder()
    check("PAL frames from file header", dec.get_frame_count_from_json(p, 'pal') == 250)
    check("NTSC frames from header", dec.get_frame_count_from_json(p2, 'ntsc') == int(7.8905344 * 29.97))
    check("PAL frames legacy (unchanged)", dec.get_frame_count_from_json(p3, 'pal') == 1500)


def test_discovery_and_status(tmp):
    print("\nproject discovery + workflow status")
    d = os.path.join(tmp, 'proj')
    os.makedirs(d)
    # Native project: RF, audio, metadata
    make(os.path.join(d, 'Movie.ddd.flac'), head=flac_header(400_000_000))
    make(os.path.join(d, 'Movie.flac'))
    with open(os.path.join(d, 'Movie.ddd.yaml'), 'w') as f:
        f.write('"capture":\n  "duration_seconds": 10.0\n')
    # Legacy project
    make(os.path.join(d, 'Old.lds'))
    make(os.path.join(d, 'Old.flac'))
    with open(os.path.join(d, 'Old.json'), 'w') as f:
        f.write('{}')

    projects = {p.name: p for p in ProjectDiscovery().discover_projects([d])}
    check("both projects found, one each", set(projects) == {'Movie', 'Old'}, str(sorted(projects)))
    m = projects['Movie']
    check("native RF is the video capture", m.capture_files.get('video', '').endswith('Movie.ddd.flac'))
    check("plain .flac is the audio, not the RF", m.capture_files.get('audio', '').endswith('Movie.flac'))
    check("yaml is the metadata", m.capture_files.get('metadata', '').endswith('Movie.ddd.yaml'))
    check("legacy project unchanged", projects['Old'].capture_files.get('video', '').endswith('Old.lds'))

    an = WorkflowAnalyzer()
    st = an.analyze_project_workflow(m)
    s = st.steps
    check("native: CAPTURE complete", s[WorkflowStep.CAPTURE] in (StepStatus.COMPLETE, StepStatus.VALIDATED), str(s[WorkflowStep.CAPTURE]))
    check("native: DECODE ready", s[WorkflowStep.DECODE] == StepStatus.READY, str(s[WorkflowStep.DECODE]))
    check("native: COMPRESS not offered", s[WorkflowStep.COMPRESS] == StepStatus.COMPLETE, str(s[WorkflowStep.COMPRESS]))
    check("native: COMPRESS shown as N/A",
          an.get_step_display_status(s[WorkflowStep.COMPRESS], m, WorkflowStep.COMPRESS, 1) == 'N/A')
    so = an.analyze_project_workflow(projects['Old']).steps
    check("legacy: COMPRESS still ready", so[WorkflowStep.COMPRESS] == StepStatus.READY, str(so[WorkflowStep.COMPRESS]))
    check("legacy: COMPRESS display unchanged",
          an.get_step_display_status(so[WorkflowStep.COMPRESS], projects['Old'], WorkflowStep.COMPRESS, 2) != 'N/A')
    check("job name matching for native input",
          an._is_job_for_project(type('J', (), {'input_file': os.path.join(d, 'Movie.ddd.flac'),
                                                 'output_file': os.path.join(d, 'Movie.tbc')})(), m))


def test_validation_log(tmp):
    print("\nvalidation log base names")
    import validation_log
    p = os.path.join(tmp, 'V.ddd.flac')
    make(p, size=1024)
    make(os.path.join(tmp, 'V.ddd.yaml'), size=100)
    make(os.path.join(tmp, 'V.flac'), size=1024)
    check("log path anchored to project name", validation_log.get_log_path(p) == os.path.join(tmp, 'V_validation.log'),
          validation_log.get_log_path(p))
    roles = validation_log.find_capture_originals(p)
    check("originals include native roles", set(roles) == {'ddd_flac', 'ddd_yaml', 'flac'}, str(sorted(roles)))


def test_backends():
    print("\ncapture backends")
    import capture_backends as cb
    g, lg = cb._BACKENDS['ddd-gui'], cb._BACKENDS['ddd-legacy']
    check("native backend writes .ddd.flac", g.rf_suffix == '.ddd.flac' and g.rf_path('/c', 'n').endswith('n.ddd.flac'))
    check("legacy backend writes .lds", lg.rf_suffix == '.lds')
    check("backend suffixes are RF formats the toolkit understands",
          rf_formats.rf_suffix('x' + g.rf_suffix) == g.rf_suffix and rf_formats.rf_suffix('x' + lg.rf_suffix) == lg.rf_suffix)


def test_staging(tmp):
    print("\nstage command for a native capture")
    import time
    import post_capture_hash
    import workflow_control_centre as wcc
    from workflow_analyzer import WorkflowAnalyzer

    d = os.path.join(tmp, 'stage')
    os.makedirs(d)
    keep = ['S.tbc', 'S.tbc.json', 'S_chroma.tbc', 'S.log']          # regenerable decode outputs
    move = ['S.ddd.flac', 'S.ddd.yaml', 'S.flac', 'S.capture.log']   # the archive set
    make(os.path.join(d, 'S.ddd.flac'), head=flac_header(400_000_000))
    for name in ['S.ddd.yaml', 'S.flac', 'S.capture.log'] + keep:
        make(os.path.join(d, name), size=2 * 1024 * 1024 if name.endswith(('.flac', '.tbc')) else 200)

    project = {p.name: p for p in ProjectDiscovery().discover_projects([d])}['S']
    centre = wcc.WorkflowControlCentre.__new__(wcc.WorkflowControlCentre)
    centre.workflow_analyzer = WorkflowAnalyzer()
    centre.current_projects = [project]
    centre.message = ''

    centre.handle_stage_project(1)
    check("refused before hashes exist", 'Refusing to stage' in centre.message, centre.message)
    check("nothing moved when refused", all(os.path.exists(os.path.join(d, n)) for n in move))

    post_capture_hash.prompt_and_hash_originals(
        os.path.join(d, 'S.ddd.flac'), os.path.join(d, 'S.flac'), os.path.join(d, 'S.ddd.yaml'), countdown_seconds=0)
    centre.handle_stage_project(1)
    for _ in range(50):
        time.sleep(0.1)
        if os.path.isdir(os.path.join(d, 'S.backup')) and 'Staged' in centre.message:
            break
    backup = os.path.join(d, 'S.backup')
    moved = sorted(os.listdir(backup)) if os.path.isdir(backup) else []
    check("archive set moved into S.backup/", all(n in moved for n in move), str(moved))
    check("decode outputs stay put", all(os.path.exists(os.path.join(d, n)) for n in keep))


def test_tool_health(tmp):
    print("\nld helper health (unmanaged and broken copies)")
    import stat
    import tool_health

    prefix = os.path.join(tmp, 'env')
    inside = os.path.join(prefix, 'bin')
    stale = os.path.join(tmp, 'usr-bin')
    os.makedirs(inside)
    os.makedirs(stale)

    def script(folder, name, body):
        path = os.path.join(folder, name)
        with open(path, 'w') as f:
            f.write('#!/bin/sh\n' + body + '\n')
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        return path

    script(inside, 'ld-ldf-reader', 'echo usage')
    script(stale, 'ld-ldf-reader', 'echo "ld-ldf-reader: error while loading shared libraries: libavcodec.so.61: cannot open shared object file" >&2; exit 127')
    script(stale, 'ld-chroma-decoder', 'echo usage')
    script(inside, 'ld-process-vbi', 'echo usage')

    saved_path = os.environ.get('PATH', '')
    try:
        os.environ['PATH'] = os.pathsep.join([stale, inside, saved_path])
        r = tool_health.check_tool('ld-ldf-reader', prefix)
        check("stale reader found first", r['path'] == os.path.join(stale, 'ld-ldf-reader'))
        check("stale reader is unmanaged", not r['managed'])
        check("stale reader cannot start", bool(r['problem']) and 'libavcodec.so.61' in r['problem'], str(r['problem']))
        check("hidden environment copy is reported", r['shadows'] == os.path.join(inside, 'ld-ldf-reader'), str(r['shadows']))
        check("reader_problem explains it", 'cannot start' in (tool_health.reader_problem(prefix) or ''))
        lines, severity = tool_health.format_report(r)
        check("report severity is fail", severity == 'fail')
        w = tool_health.check_tool('ld-chroma-decoder', prefix)
        check("working unmanaged copy is a warning", tool_health.format_report(w)[1] == 'warn' and not w['problem'])

        os.environ['PATH'] = os.pathsep.join([inside, stale, saved_path])
        ok = tool_health.check_tool('ld-ldf-reader', prefix)
        check("environment copy first is healthy", ok['managed'] and not ok['problem'] and tool_health.reader_problem(prefix) is None)
        check("healthy report severity ok", tool_health.format_report(ok)[1] == 'ok')
        # starts here only because LD_LIBRARY_PATH is set
        script(stale, 'ld-process-vits', '[ -n "$LD_LIBRARY_PATH" ] || { echo "x: error while loading shared libraries: libz.so.1" >&2; exit 127; }; echo ok')
        os.environ['PATH'] = os.pathsep.join([stale, saved_path])
        os.environ['LD_LIBRARY_PATH'] = '/somewhere/lib'
        fr = tool_health.check_tool('ld-process-vits', prefix)
        check("starts only with LD_LIBRARY_PATH -> fragile", fr['fragile'] and not fr['problem'], str(fr))
        check("fragile is a warning", tool_health.format_report(fr)[1] == 'warn')
        del os.environ['LD_LIBRARY_PATH']
        # command line for each flavour of ld-ldf-reader
        py = script(inside, 'ld-ldf-reader-pystyle', 'echo py')
        binary = os.path.join(inside, 'ld-ldf-reader-binary')
        with open(binary, 'wb') as f:
            f.write(b'\x7fELF' + b'\0' * 60)
        check("python-style reader: -s option", tool_health.ldf_reader_argv(py, 'f.flac', 5) == [py, '-s', '5', 'f.flac'])
        check("python-style reader: no offset", tool_health.ldf_reader_argv(py, 'f.flac') == [py, 'f.flac'])
        check("compiled reader: positional offset", tool_health.ldf_reader_argv(binary, 'f.flac', 5) == [binary, 'f.flac', '5'])
        check("compiled reader: no offset", tool_health.ldf_reader_argv(binary, 'f.flac') == [binary, 'f.flac'])
        check("missing tool is reported not found", tool_health.check_tool('ld-no-such-tool', prefix)['path'] is None)
    finally:
        os.environ['PATH'] = saved_path
        os.environ.pop('LD_LIBRARY_PATH', None)


def test_no_hardcoded_capture_program():
    """Only capture_backends.py may name the capture program; everything else asks the backend."""
    print("no hard-coded capture program")
    here = os.path.dirname(os.path.abspath(__file__))
    offenders = []
    for name in sorted(os.listdir(here)):
        if not name.endswith('.py') or name in ('capture_backends.py', 'test_rf_formats.py'):
            continue
        with open(os.path.join(here, name), encoding='utf-8') as f:
            for number, line in enumerate(f, 1):
                if ("'DomesdayDuplicator'" in line or '"DomesdayDuplicator"' in line
                        or "'--output-file'" in line):
                    offenders.append(f"{name}:{number}")
    check("capture programs are started only through the backend", not offenders, ', '.join(offenders))


def main():
    test_no_hardcoded_capture_program()
    with tempfile.TemporaryDirectory() as tmp:
        test_names()
        test_durations(tmp)
        test_discovery_and_status(tmp)
        test_validation_log(tmp)
        test_backends()
        test_staging(tmp)
        test_tool_health(tmp)
    print()
    if FAILED:
        print(f"{len(FAILED)} FAILED: {', '.join(FAILED)}")
        sys.exit(1)
    print("All checks passed.")


if __name__ == '__main__':
    main()
