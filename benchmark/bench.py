#!/usr/bin/env python3
"""
Decoder benchmark: how fast does each decoder build decode the same capture on this machine?

    python3 benchmark/bench.py --sample Capture.ddd.flac [options]

Run it inside the toolkit's conda environment. It measures builds side by side, one after the
other, on the same sample, and prints a table with frames per second and the time an hour of
tape would take.

Variants (--variants, comma separated; default: tape-decode,vhs-decode):

  tape-decode              the tape-decode installed in the toolkit environment
  vhs-decode               the vhs-decode installed in the toolkit environment
  tape-decode@release      namazso's newest release binary for this CPU
  tape-decode@native[:REF] built from source for this CPU (REF = tag, branch or commit)
  tape-decode@generic[:REF] built from source without CPU-specific instructions
  vhs-decode@release       upstream's prebuilt AppImage (Linux)
  vhs-decode@REF[:generic] built from external/vhs-decode at REF (e.g. v0.4.0, efc3818f)
  exe=PATH:KIND            a program you already have; KIND is tape-decode or vhs-decode

Nothing here compiles anything itself: builds are done by the toolkit's own scripts in
build-scripts/ (the same ones setup.sh uses), into a scratch folder, so what is measured is what
setup installs, and the real installation is never touched. Decodes are run with the same command
lines the toolkit uses (decoder_backends.py) and pinned to the same kind of cores (cpu_affinity.py)
on Linux. macOS cannot pin, so a decode there runs unpinned.
"""

import argparse
import csv
import datetime
import json
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import decoder_backends  # noqa: E402
import project_flags  # noqa: E402

try:
    import resource
except ImportError:          # Windows
    resource = None

FRAMES_PER_HOUR = {'pal': 25 * 3600, 'ntsc': round(30000 / 1001 * 3600)}


# ---------------------------------------------------------------- machine

def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ''


def machine_info():
    info = {'os': platform.system(), 'os_version': platform.release(), 'arch': platform.machine(),
            'host': platform.node().split('.')[0], 'logical_cpus': os.cpu_count()}
    if sys.platform.startswith('linux'):
        with open('/proc/cpuinfo') as f:
            m = re.search(r'model name\s*:\s*(.+)', f.read())
        info['cpu'] = m.group(1).strip() if m else platform.processor()
        with open('/proc/meminfo') as f:
            info['ram_gb'] = round(int(re.search(r'MemTotal:\s+(\d+)', f.read()).group(1)) / 1048576)
    elif sys.platform == 'darwin':
        info['cpu'] = _run(['sysctl', '-n', 'machdep.cpu.brand_string'])
        info['ram_gb'] = round(int(_run(['sysctl', '-n', 'hw.memsize']) or 0) / 2**30)
    else:
        info['cpu'] = platform.processor()
    return info


def pick_cores(count):
    """Physical cores to pin one decode to, chosen the way the toolkit chooses; None if this
    platform cannot pin."""
    if not sys.platform.startswith('linux'):
        return None, None
    import cpu_affinity
    allocator = cpu_affinity.AffinityAllocator()
    if not allocator.available:
        return None, None
    cpus = allocator.allocate('benchmark', count)
    return (cpus, allocator) if cpus else (None, None)


# ---------------------------------------------------------------- processes

def process_table():
    """{pid: (ppid, rss_kb, args)} for every process (Unix)."""
    out = _run(['ps', '-axo', 'pid=,ppid=,rss=,args='])
    table = {}
    for line in out.splitlines():
        parts = line.split(None, 3)
        if len(parts) == 4 and parts[0].isdigit():
            table[int(parts[0])] = (int(parts[1]), int(parts[2]), parts[3])
    return table


def descendants(table, root):
    found, frontier = {root}, [root]
    while frontier:
        parent = frontier.pop()
        for pid, (ppid, _, _) in table.items():
            if ppid == parent and pid not in found:
                found.add(pid)
                frontier.append(pid)
    return found


DECODER_WORDS = re.compile(r'(tape-decode|vhs-decode|decode\.py vhs|ld-ldf-reader)')
# The helper that mounts a prebuilt AppImage carries the decoder's name but belongs to the run that started it
NOT_A_DECODE = re.compile(r'(squashfuse|fusermount|\.mount_|AppImage .*-o )')


def foreign_decoders(table, mine, marker=None):
    """Decode processes that are not ours (anything else decoding makes a result meaningless).
    `marker` is a string only our own decode has on its command line (its output path): a prebuilt
    AppImage leaves a process of its own outside our child's tree, and that one is ours too."""
    me = os.getpid()
    return sorted(pid for pid, (_, _, args) in table.items()
                  if pid not in mine and pid != me and DECODER_WORDS.search(args)
                  and not NOT_A_DECODE.search(args) and 'bench.py' not in args
                  and not (marker and marker in args))


# ---------------------------------------------------------------- variants

class Variant:
    def __init__(self, spec, kind, label, exe=None):
        self.spec, self.kind, self.label, self.exe = spec, kind, label, exe
        self.error = None


def parse_variant(spec, work):
    spec, _, label = spec.partition('#')           # "...#my label" names it in the table
    if spec.startswith('exe='):
        path, _, kind = spec[4:].rpartition(':')
        if kind not in ('tape-decode', 'vhs-decode') or not os.path.isfile(path):
            raise ValueError(f"{spec}: expected exe=PATH:tape-decode or exe=PATH:vhs-decode with an existing PATH")
        return Variant(spec, kind, label or f"{kind} ({path})", path)
    name, _, how = spec.partition('@')
    if name not in ('tape-decode', 'vhs-decode'):
        raise ValueError(f"unknown variant '{spec}'")
    if not how:
        return Variant(spec, name, label or f"{name} (installed)", shutil.which(name))
    return Variant(spec, name, label or f"{name} {how}")


def build(variant, work, log):
    """Make variant.exe using the toolkit's own scripts. Raises RuntimeError with the reason."""
    if variant.exe or '@' not in variant.spec:
        if not variant.exe:
            raise RuntimeError(f"{variant.kind} is not installed in this environment (run ./setup.sh)")
        return
    if os.name == 'nt':
        raise RuntimeError("building variants needs bash; only installed programs can be measured on Windows")
    name, _, how = variant.spec.partition('@')
    how, _, option = how.partition(':')
    folder = os.path.join(work, re.sub(r'[^A-Za-z0-9._-]', '_', variant.spec))
    prefix = os.path.join(folder, 'prefix')
    os.makedirs(os.path.join(prefix, 'bin'), exist_ok=True)
    scripts = os.path.join(ROOT, 'build-scripts')
    env = dict(os.environ)

    def sh(cmd):
        log(f"    $ {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        with open(os.path.join(folder, 'build.log'), 'a') as f:
            f.write(' '.join(cmd) + '\n' + result.stdout + result.stderr)
        if result.returncode != 0:
            tail = (result.stderr or result.stdout).strip().splitlines()[-3:]
            raise RuntimeError(f"build failed ({' '.join(tail)[:300]}); see {folder}/build.log")

    if name == 'tape-decode':
        script = os.path.join(scripts, 'install-tape-decode.sh')
        if how == 'release':
            sh(['bash', script, '--mode', 'easy', '--prefix', prefix, '--dest', os.path.join(folder, 'download')])
        elif how in ('native', 'generic'):
            cmd = ['bash', script, '--mode', 'performance', '--prefix', prefix, '--dest', os.path.join(folder, 'src')]
            if option:
                cmd += ['--version', option]
            if how == 'generic':
                cmd.append('--safe')
            sh(cmd)
        else:
            raise RuntimeError(f"unknown tape-decode build '{how}' (release, native or generic)")
        variant.exe = os.path.join(prefix, 'bin', 'tape-decode')
    else:
        if how == 'release':
            sh(['bash', os.path.join(scripts, 'install-vhs-decode-binary.sh'), '--prefix', prefix,
                '--dest', os.path.join(folder, 'download')])
            variant.exe = os.path.join(prefix, 'bin', 'vhs-decode')
        else:
            src = os.path.join(folder, 'src')
            shutil.rmtree(src, ignore_errors=True)
            os.makedirs(src)
            archive = subprocess.run(['git', '-C', os.path.join(ROOT, 'external', 'vhs-decode'), 'archive', how],
                                     capture_output=True)
            if archive.returncode != 0:
                raise RuntimeError(f"external/vhs-decode has no ref '{how}' (git fetch --tags there first)")
            subprocess.run(['tar', '-x', '-C', src], input=archive.stdout, check=True)
            env['SETUPTOOLS_SCM_PRETEND_VERSION'] = how.lstrip('v') if re.match(r'^v?\d', how) else '0.0.0'
            cmd = ['bash', os.path.join(scripts, 'build-vhs-decode.sh'), '--source', src,
                   '--venv', os.path.join(folder, 'venv')]
            if option == 'generic':
                cmd.append('--safe')
            sh(cmd)
            variant.exe = os.path.join(folder, 'venv', 'bin', 'vhs-decode')
    if not os.path.isfile(variant.exe):
        raise RuntimeError(f"the build did not produce {variant.exe}")


# ---------------------------------------------------------------- samples

def make_sample(source, seconds, start, out_dir, log):
    """Cut `seconds` of capture from a .ddd.flac. (A FLAC capture labels its rate 40000, so a real
    second is 1000 label seconds.)"""
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise RuntimeError("ffmpeg is needed to cut a sample (run ./setup.sh)")
    target = os.path.join(out_dir, f"sample_{int(seconds)}s.ddd.flac")
    log(f"  cutting {seconds:g} s of {os.path.basename(source)} from {start:g} s")
    # Re-encoded, not stream-copied: a copy keeps the original file's sample count in its header, and
    # tape-decode's release binary treats the mismatch as a read error.
    subprocess.run([ffmpeg, '-v', 'error', '-y', '-ss', str(start * 1000), '-t', str(seconds * 1000),
                    '-i', source, '-c:a', 'flac', '-compression_level', '8', target], check=True)
    return target


def resample(sample, rate_mhz, out_dir, log):
    """Make a lower-rate copy of a 40 MHz capture (what a 20 MS/s recorder would have written)."""
    ffmpeg = shutil.which('ffmpeg')
    target = os.path.join(out_dir, f"sample_{rate_mhz:g}msps.ddd.flac")
    log(f"  resampling to {rate_mhz:g} MS/s")
    subprocess.run([ffmpeg, '-v', 'error', '-y', '-i', sample, '-ar', str(round(rate_mhz * 1000)),
                    '-sample_fmt', 's16', '-c:a', 'flac', '-compression_level', '8', target], check=True)
    return target


def repeat_sample(sample, total_seconds, out_dir, log):
    """Make a long sample by repeating a short one. Good enough for
    measuring speed: the joins cost a moment of lost sync every repeat, nothing more."""
    import rf_formats
    length = rf_formats.capture_duration_seconds(sample)
    if not length:
        raise RuntimeError("cannot tell how long the sample is, so it cannot be repeated")
    copies = max(1, round(total_seconds / length))
    if copies == 1:
        return sample
    ffmpeg = shutil.which('ffmpeg')
    target = os.path.join(out_dir, f"sample_{round(copies * length)}s_repeated.ddd.flac")
    listing = os.path.join(out_dir, 'repeat.txt')
    with open(listing, 'w') as f:
        f.write(''.join(f"file '{sample}'\n" for _ in range(copies)))
    log(f"  repeating the {length:.0f} s sample {copies} times: {copies * length / 60:.1f} minutes")
    subprocess.run([ffmpeg, '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', listing,
                    '-c:a', 'flac', '-compression_level', '8', target], check=True)
    os.remove(listing)
    return target


def pack_lds(flac, out_path, log):
    """Write the sample as an old-style packed 10-bit .lds, so vhs-decode builds can be measured
    reading uncompressed input as well."""
    import numpy as np
    ffmpeg = shutil.which('ffmpeg')
    log("  writing an uncompressed .lds copy of the sample")
    proc = subprocess.Popen([ffmpeg, '-v', 'error', '-i', flac, '-f', 's16le', '-'], stdout=subprocess.PIPE)
    with open(out_path, 'wb') as f:
        leftover = b''
        while True:
            data = proc.stdout.read(1 << 24)
            if not data:
                break
            data = leftover + data
            usable = len(data) // 8 * 8          # 4 samples of 2 bytes
            leftover = data[usable:]
            s = np.frombuffer(data[:usable], dtype='<i2').astype(np.int32)
            v = ((s >> 6) + 512).astype(np.uint16).reshape(-1, 4)
            a, b, c, d = v[:, 0], v[:, 1], v[:, 2], v[:, 3]
            out = np.empty((len(v), 5), dtype=np.uint8)
            out[:, 0] = a >> 2
            out[:, 1] = ((a & 3) << 6) | (b >> 4)
            out[:, 2] = ((b & 15) << 4) | (c >> 6)
            out[:, 3] = ((c & 63) << 2) | (d >> 8)
            out[:, 4] = d & 255
            f.write(out.tobytes())
    proc.wait()
    return out_path


# ---------------------------------------------------------------- one run

def run_once(variant, sample, work, standard, cores, threads, rate_mhz, log):
    decoder = decoder_backends.select_decoder(variant.kind)
    out_dir = os.path.join(work, 'out')
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.join(out_dir, re.sub(r'[^A-Za-z0-9._-]', '_', variant.spec))
    for suffix in ('.tbc', '_chroma.tbc', '.tbc.json', '.log'):
        if os.path.exists(base + suffix):
            os.remove(base + suffix)
    problem = decoder.input_problem(sample)
    if problem:
        raise RuntimeError(problem)
    tokens, structural, problems = project_flags.decode_arguments(None, decoder.key)
    cmd, more = decoder.build_command(variant.exe, {'video_standard': standard, 'tape_speed': 'SP', 'sample_rate_mhz': rate_mhz},
                                      tokens, structural, sample, base, threads=threads)
    if problems + more:
        raise RuntimeError('; '.join(problems + more))

    cpus, allocator = pick_cores(cores) if cores else (None, None)
    preexec = None
    if cpus:
        import cpu_affinity
        preexec = cpu_affinity.make_preexec_fn(cpus)
    before = resource.getrusage(resource.RUSAGE_CHILDREN) if resource else None
    started = time.perf_counter()
    with open(base + '.stdout', 'w') as sink:
        proc = subprocess.Popen(cmd, stdout=sink, stderr=subprocess.STDOUT, preexec_fn=preexec)
    peak_kb, disturbed = 0, []
    while proc.poll() is None:
        table = process_table()
        mine = descendants(table, proc.pid)
        peak_kb = max(peak_kb, sum(table[p][1] for p in mine if p in table))
        for pid in foreign_decoders(table, mine, base):
            if pid not in disturbed:
                disturbed.append(pid)
        time.sleep(1.0)
    wall = time.perf_counter() - started
    if allocator:
        allocator.release('benchmark')
    cpu_s = None
    if resource:
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu_s = (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)

    if proc.returncode != 0:
        tail = open(base + '.stdout', errors='replace').read().strip().splitlines()[-2:]
        raise RuntimeError(f"exit code {proc.returncode}: {'; '.join(tail)[:300]}")
    try:
        with open(base + '.tbc.json') as f:
            frames = len(json.load(f)['fields']) // 2
    except (OSError, KeyError, ValueError):
        tail = re.sub(r'\x1b\[[0-9;]*m', '', open(base + '.stdout', errors='replace').read()).strip().splitlines()[-2:]
        raise RuntimeError("the decode finished but wrote no usable .tbc.json: " + '; '.join(tail)[:300])
    for suffix in ('.tbc', '_chroma.tbc'):
        if os.path.exists(base + suffix):
            os.remove(base + suffix)
    return {'wall_s': wall, 'cpu_s': cpu_s, 'peak_rss_mb': peak_kb / 1024, 'frames': frames,
            'fps': frames / wall, 'cores': cpus, 'disturbed_by': disturbed}


# ---------------------------------------------------------------- main

def summarise(results, standard, baseline):
    rows = []
    for spec, runs in results.items():
        good = [r for r in runs if 'fps' in r and not r.get('disturbed_by') and not r.get('warmup')]
        failed = [r for r in runs if 'error' in r]
        if not good:
            rows.append({'variant': spec, 'error': (failed[0]['error'] if failed else 'no clean runs')})
            continue
        fps = statistics.median(r['fps'] for r in good)
        rows.append({'variant': spec, 'fps': fps, 'min': min(r['fps'] for r in good),
                     'max': max(r['fps'] for r in good), 'runs': len(good),
                     'cpu_s': statistics.median(r['cpu_s'] for r in good) if good[0]['cpu_s'] is not None else None,
                     'rss_mb': max(r['peak_rss_mb'] for r in good),
                     'hour_min': FRAMES_PER_HOUR[standard] / fps / 60})
    base_fps = next((r['fps'] for r in rows if r['variant'] == baseline and 'fps' in r), None)
    for r in rows:
        if 'fps' in r and base_fps:
            r['vs_baseline'] = r['fps'] / base_fps
    return rows


def format_table(rows, labels, baseline):
    lines = ["| Build | Frames/s | Range | Runs | CPU s | Peak RAM | One hour of tape |"
             + (f" vs {baseline} |" if baseline else ""),
             "|---|---|---|---|---|---|---|" + ("---|" if baseline else "")]
    for r in rows:
        if 'error' in r:
            reason = re.sub(r'\x1b\[[0-9;]*m', '', r['error']).replace('|', '/')
            lines.append(f"| {labels[r['variant']]} | FAILED: {reason} | | | | | |" + (" |" if baseline else ""))
            continue
        hour = f"{r['hour_min']:.0f} min" if r['hour_min'] < 150 else f"{r['hour_min'] / 60:.1f} h"
        cpu = f"{r['cpu_s']:.0f}" if r['cpu_s'] is not None else "-"
        rel = f" {r['vs_baseline']:.2f}x |" if baseline and 'vs_baseline' in r else (" |" if baseline else "")
        lines.append(f"| {labels[r['variant']]} | {r['fps']:.1f} | {r['min']:.1f}-{r['max']:.1f} | {r['runs']} | "
                     f"{cpu} | {r['rss_mb']:.0f} MB | {hour} |{rel}")
    return '\n'.join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description="Benchmark decoder builds on this machine",
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__.split('Variants')[1])
    p.add_argument('--sample', required=True, help="a .ddd.flac capture to decode")
    p.add_argument('--seconds', type=float, help="cut this many seconds from the capture and use that (default: all of it)")
    p.add_argument('--start', type=float, default=5, help="where the cut starts, in seconds (default 5)")
    p.add_argument('--resample-to', type=float, metavar='MHZ',
                   help="decode a lower-rate copy of the sample (20 = what a 20 MS/s recorder writes)")
    p.add_argument('--repeat-to', type=float, metavar='SECONDS',
                   help="repeat the sample until it is about this long (600 = ten minutes). A boring capture repeated "
                        "gives a long run that measures speed without needing a long tape")
    p.add_argument('--variants', default='tape-decode,vhs-decode', help="what to measure (see below)")
    p.add_argument('--runs', type=int, default=3, help="timed runs per build (default 3), after one discarded warm-up")
    p.add_argument('--cores', type=int, default=4, help="cores to pin one decode to on Linux (default 4)")
    p.add_argument('--threads', type=int, default=3, help="the toolkit's decode thread setting (default 3: four cores)")
    p.add_argument('--standard', choices=('pal', 'ntsc'), default='pal')
    p.add_argument('--baseline', help="variant to compare the others with")
    p.add_argument('--lds', action='store_true', help="also run vhs-decode builds on an uncompressed .lds copy of the sample")
    p.add_argument('--work', default=os.path.join(HERE, 'work'), help="scratch folder (builds, outputs)")
    p.add_argument('--results', default=os.path.join(HERE, 'results'), help="where to write the results")
    p.add_argument('--keep-work', action='store_true', help="keep builds and logs afterwards")
    args = p.parse_args(argv)

    if os.name == 'nt':
        print("note: Windows is not tested; decodes run unpinned and there is no disturbance check")
    log = lambda m: print(m, flush=True)
    work = os.path.abspath(args.work)
    os.makedirs(work, exist_ok=True)
    machine = machine_info()
    log(f"{machine.get('host')}: {machine.get('cpu')}, {machine.get('logical_cpus')} threads, "
        f"{machine.get('ram_gb', '?')} GB, {machine['os']} {machine['arch']}")

    sample = os.path.abspath(args.sample)
    if not os.path.isfile(sample):
        sys.exit(f"sample not found: {sample}")
    if args.seconds:
        sample = make_sample(sample, args.seconds, args.start, work, log)
    if args.repeat_to:
        sample = repeat_sample(sample, args.repeat_to, work, log)
    rate_mhz = 40
    if args.resample_to:
        sample = resample(sample, args.resample_to, work, log)
        rate_mhz = args.resample_to
    lds_sample = pack_lds(sample, os.path.join(work, 'sample.lds'), log) if args.lds else None

    variants = []
    for spec in [s.strip() for s in args.variants.split(',') if s.strip()]:
        try:
            variants.append(parse_variant(spec, work))
        except ValueError as e:
            sys.exit(str(e))
    if any('@' in v.spec and not v.exe for v in variants) and os.environ.get('CONDA_DEFAULT_ENV') != 'ddd-capture-toolkit':
        sys.exit("building variants needs the toolkit's conda environment: run  conda activate ddd-capture-toolkit  first")
    runs_plan = []                 # (label key, variant, input file)
    for v in variants:
        log(f"preparing {v.label}")
        try:
            build(v, work, log)
        except RuntimeError as e:
            v.error = str(e)
            log(f"  FAILED: {v.error}")
            continue
        runs_plan.append((v.spec, v, sample))
        if lds_sample and v.kind == 'vhs-decode':
            runs_plan.append((v.spec + ' [.lds]', v, lds_sample))

    results = {key: [] for key, _, _ in runs_plan}
    labels = {v.spec: v.label for v in variants}
    for key, v, _ in runs_plan:
        labels.setdefault(key, v.label + (' on .lds' if key.endswith('[.lds]') else ''))
    for v in variants:
        if v.error:
            results[v.spec] = [{'error': v.error}]

    def attempt(key, v, infile, warmup):
        waited = 0
        while foreign_decoders(process_table(), set()) and waited < 120 and os.name != 'nt':
            if waited == 0:
                log("  another decode is running; waiting for it to finish (up to 2 minutes)")
            time.sleep(5)
            waited += 5
        try:
            r = run_once(v, infile, work, args.standard, args.cores, args.threads, rate_mhz, log)
        except RuntimeError as e:
            r = {'error': str(e)}
        r['warmup'] = warmup
        if r.get('disturbed_by'):
            r['note'] = f"another decode ran at the same time (pid {r['disturbed_by']}); not counted"
        results[key].append(r)
        shown = (f"{r['fps']:.2f} fps in {r['wall_s']:.1f}s" if 'fps' in r else f"FAILED: {r['error']}")
        log(f"  {labels[key]:<45} {'warm-up' if warmup else 'run':<8} {shown}" + (f"  [{r['note']}]" if r.get('note') else ''))

    log(f"\nwarm-up, then {args.runs} runs of each; sample {os.path.basename(sample)}")
    for key, v, infile in runs_plan:
        attempt(key, v, infile, True)
    for _ in range(args.runs):
        for key, v, infile in runs_plan:
            attempt(key, v, infile, False)

    rows = summarise(results, args.standard, args.baseline)
    table = format_table(rows, labels, args.baseline)
    log("\n" + table)

    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    out_dir = os.path.join(os.path.abspath(args.results), f"{machine.get('host')}-{stamp}")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'results.json'), 'w') as f:
        json.dump({'machine': machine, 'sample': os.path.basename(sample), 'rate_mhz': rate_mhz, 'standard': args.standard,
                   'cores': args.cores, 'threads': args.threads, 'labels': labels, 'runs': results, 'summary': rows},
                  f, indent=2)
    with open(os.path.join(out_dir, 'results.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['variant', 'warmup', 'wall_s', 'cpu_s', 'peak_rss_mb', 'frames', 'fps', 'disturbed', 'error'])
        for key, runs in results.items():
            for r in runs:
                w.writerow([key, r.get('warmup', ''), r.get('wall_s', ''), r.get('cpu_s', ''), r.get('peak_rss_mb', ''),
                            r.get('frames', ''), r.get('fps', ''), bool(r.get('disturbed_by')), r.get('error', '')])
    with open(os.path.join(out_dir, 'summary.md'), 'w') as f:
        f.write(f"# {machine.get('cpu')} ({machine['os']} {machine['arch']}, {machine.get('ram_gb', '?')} GB)\n\n"
                f"Sample: {os.path.basename(sample)} at {rate_mhz:g} MS/s, {args.standard.upper()}, {args.cores} cores"
                f"{'' if sys.platform.startswith('linux') else ' (unpinned on this platform)'}.\n\n{table}\n")
    log(f"\nresults written to {out_dir}")
    if not args.keep_work:
        shutil.rmtree(os.path.join(work, 'out'), ignore_errors=True)
    return 1 if any('error' in r for r in rows) else 0


if __name__ == '__main__':
    sys.exit(main())
