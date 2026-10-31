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


def flac_header(total_samples, rate_label=40000):
    """Minimal FLAC header: 'fLaC' + STREAMINFO block with the given totals."""
    info = struct.pack('>HHBBB', 4096, 4096, 0, 0, 0) + struct.pack('>BBB', 0, 0, 0)
    packed = (rate_label << 44) | (0 << 41) | (15 << 36) | total_samples   # mono, 16 bit
    info += struct.pack('>Q', packed) + b'\x00' * 16
    return b'fLaC' + bytes([0x80]) + struct.pack('>I', len(info))[1:] + info


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
    # native with yaml
    p = os.path.join(tmp, 'n1.ddd.flac')
    make(p, head=flac_header(400_000_000))
    with open(os.path.join(tmp, 'n1.ddd.yaml'), 'w') as f:
        f.write('"capture":\n  "duration_seconds": 10.0139\n  "samples": 400556032\n')
    check("yaml duration", abs(rf_formats.capture_duration_seconds(p) - 10.0139) < 1e-6)
    # native, no yaml: FLAC header at 40 MHz
    p2 = os.path.join(tmp, 'n2.ddd.flac')
    make(p2, head=flac_header(315_621_376))
    d = rf_formats.capture_duration_seconds(p2)
    check("header-only duration", d is not None and abs(d - 7.8905344) < 1e-6, str(d))
    # legacy json
    p3 = os.path.join(tmp, 'l1.lds')
    make(p3)
    with open(os.path.join(tmp, 'l1.json'), 'w') as f:
        f.write('{"captureInfo": {"durationInMilliseconds": 60000}}')
    check("legacy json duration", rf_formats.capture_duration_seconds(p3) == 60.0)
    check("missing metadata -> None", rf_formats.capture_duration_seconds(os.path.join(tmp, 'zzz.lds')) is None)

    from parallel_vhs_decode import ParallelVHSDecoder
    dec = ParallelVHSDecoder()
    check("PAL frames from yaml", dec.get_frame_count_from_json(p, 'pal') == int(10.0139 * 25))
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


def main():
    with tempfile.TemporaryDirectory() as tmp:
        test_names()
        test_durations(tmp)
        test_discovery_and_status(tmp)
        test_validation_log(tmp)
        test_backends()
    print()
    if FAILED:
        print(f"{len(FAILED)} FAILED: {', '.join(FAILED)}")
        sys.exit(1)
    print("All checks passed.")


if __name__ == '__main__':
    main()
