#!/usr/bin/env python3
"""
Thermal test: does this machine slow down under a long decode, when, and how long does it take to recover?

    python3 benchmark/thermal.py --exe PATH/tape-decode --sample Slice.ddd.flac --probe Short.ddd.flac

Built for fanless machines (a MacBook Air) but it works on any. It
  1. lets the machine sit idle and records that (the cool baseline),
  2. times a short decode (the probe) while cool,
  3. decodes the sample over and over, sampling the CPU clock, thermal state and decode speed every few seconds,
  4. stops a set time after it sees the machine slow down (or at the time limit if it never does),
  5. leaves the machine idle, repeating the probe now and then, until the probe is as fast as it was when cool.

What counts as slowing down: the decode speed, or the CPU clock, stays below 90% of its early value (minutes 2 to 5) for
two minutes. Thermal pressure other than Nominal is recorded when it first appears but is not counted as slowing.

Temperature: Apple silicon does not give a die temperature to a normal program. macOS reports a thermal
pressure level and the CPU clock instead, and that is what is recorded there ("sudo -n powermetrics" must work
without a password: run `sudo -v` first or allow powermetrics in sudoers). On Linux the hottest hwmon
sensor and the average CPU clock are recorded. A drop in the clock is the evidence of throttling.

Results go to <results>/thermal-<host>-<time>/: samples.csv (every sample), probes.csv, summary.md, thermal.json.
"""

import argparse
import csv
import datetime
import glob
import json
import os
import re
import statistics
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bench  # noqa: E402
import decoder_backends  # noqa: E402
import project_flags  # noqa: E402

SUFFIXES = ('.tbc', '_chroma.tbc', '.tbc.json')


# ---------------------------------------------------------------- sensors

class MacSensors:
    """powermetrics, streaming: CPU clock, CPU power and thermal pressure, one block per interval."""

    def __init__(self, interval_s):
        self.latest, self.lock = {}, threading.Lock()
        self.proc = subprocess.Popen(['sudo', '-n', 'powermetrics', '--samplers', 'thermal,cpu_power',
                                      '-i', str(int(interval_s * 1000))],
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        deadline = time.time() + interval_s + 15
        while not self.latest and time.time() < deadline and self.proc.poll() is None:
            time.sleep(0.5)
        if not self.latest:
            self.close()
            raise RuntimeError("could not read powermetrics. It needs `sudo -n powermetrics` to work without a password "
                               "(run `sudo -v` in the same terminal first, or allow it in sudoers)")

    def _read(self):
        block = {}
        for line in self.proc.stdout:
            if line.startswith('*** Sampled system activity'):
                if block:
                    with self.lock:
                        self.latest = dict(block)
                block = {}
            m = re.match(r'(P\d*-Cluster) HW active frequency:\s+(\d+) MHz', line)
            if m:
                block.setdefault('p_mhz', []).append(int(m.group(2)))
            m = re.match(r'(E\d*-Cluster) HW active frequency:\s+(\d+) MHz', line)
            if m:
                block.setdefault('e_mhz', []).append(int(m.group(2)))
            m = re.match(r'CPU Power:\s+(\d+) mW', line)
            if m:
                block['cpu_mw'] = int(m.group(1))
            m = re.match(r'Current pressure level:\s+(\w+)', line)
            if m:
                block['pressure'] = m.group(1)

    def read(self):
        with self.lock:
            b = dict(self.latest)
        mean = lambda v: round(sum(v) / len(v)) if v else ''
        return {'p_mhz': mean(b.get('p_mhz')), 'e_mhz': mean(b.get('e_mhz')),
                'cpu_mw': b.get('cpu_mw', ''), 'pressure': b.get('pressure', ''), 'temp_c': ''}

    def close(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()


class LinuxSensors:
    def __init__(self, interval_s):
        self.temps = [p for p in glob.glob('/sys/class/hwmon/hwmon*/temp*_input')]
        self.freqs = glob.glob('/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq')
        if not self.freqs and not self.temps:
            raise RuntimeError("this machine exposes no CPU clock or temperature under /sys")

    @staticmethod
    def _num(path):
        try:
            with open(path) as f:
                return int(f.read())
        except (OSError, ValueError):
            return None

    def read(self):
        freqs = [v for v in (self._num(p) for p in self.freqs) if v]
        temps = [v for v in (self._num(p) for p in self.temps) if v]
        return {'p_mhz': round(sum(freqs) / len(freqs) / 1000) if freqs else '', 'e_mhz': '', 'cpu_mw': '',
                'pressure': '', 'temp_c': round(max(temps) / 1000, 1) if temps else ''}

    def close(self):
        pass


def open_sensors(interval_s):
    if sys.platform == 'darwin':
        return MacSensors(interval_s)
    if sys.platform.startswith('linux'):
        return LinuxSensors(interval_s)
    raise RuntimeError("the thermal test runs on macOS and Linux")


# ---------------------------------------------------------------- decoding

class Decoding:
    """One tape-decode process on a sample, started the way the toolkit starts it."""

    def __init__(self, exe, sample, base, threads, standard='pal'):
        self.base = base
        for suffix in SUFFIXES:
            if os.path.exists(base + suffix):
                os.remove(base + suffix)
        decoder = decoder_backends.select_decoder('tape-decode')
        problem = decoder.input_problem(sample)
        if problem:
            raise RuntimeError(problem)
        import rf_formats
        rate_hz = rf_formats.capture_sample_rate_hz(sample)
        if not rate_hz:
            raise RuntimeError(f"{sample} does not say what sample rate it was recorded at")
        tokens, structural, problems = project_flags.decode_arguments(None, decoder.key)
        cmd, more = decoder.build_command(exe, {'video_standard': standard, 'tape_speed': 'SP',
                                                'sample_rate_mhz': rate_hz / 1e6}, tokens, structural, sample, base,
                                          threads=threads)
        if problems + more:
            raise RuntimeError('; '.join(problems + more))
        self.sink = open(base + '.stdout', 'w')
        self.started = time.time()
        self.proc = subprocess.Popen(cmd, stdout=self.sink, stderr=subprocess.STDOUT)

    def progress(self):
        """(frames done, seconds the decoder says it has been running), from its last progress line."""
        try:
            with open(self.base + '.stdout', 'rb') as f:
                f.seek(0, os.SEEK_END)
                f.seek(max(0, f.tell() - 4096))
                text = f.read().decode(errors='replace')
        except OSError:
            return None
        found = None
        for m in re.finditer(r'Decoded (\d+) fields so far in ([\d.]+)s', text):
            found = (int(m.group(1)) // 2, float(m.group(2)))
        return found

    def running(self):
        return self.proc.poll() is None

    def stop(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(30)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.sink.close()

    def clean(self):
        for suffix in SUFFIXES:
            if os.path.exists(self.base + suffix):
                os.remove(self.base + suffix)


def probe(exe, sample, work, threads, log):
    """Time one short decode to the end. Returns frames per second."""
    d = Decoding(exe, sample, os.path.join(work, 'probe'), threads)
    d.proc.wait()
    wall = time.time() - d.started
    d.sink.close()
    try:
        frames = bench.count_frames(d.base + '.tbc.json', d.base + '.stdout')
    finally:
        d.clean()
    return frames / wall


# ---------------------------------------------------------------- the test

def main(argv=None):
    p = argparse.ArgumentParser(description="Find out whether, when and how far a machine slows down under a long decode",
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument('--exe', required=True, help="the tape-decode program to run")
    p.add_argument('--sample', required=True, help="a ten minute .ddd.flac capture (it is decoded again and again)")
    p.add_argument('--probe', required=True, help="a short (30 to 60 second) .ddd.flac capture used to time the machine")
    p.add_argument('--threads', type=int, default=3, help="decode threads (default 3, as the benchmark uses for four cores)")
    p.add_argument('--interval', type=float, default=10, help="seconds between samples (default 10)")
    p.add_argument('--idle-minutes', type=float, default=10, help="minutes idle before the test starts (default 10)")
    p.add_argument('--past-minutes', type=float, default=20, help="minutes to keep going after slowing is seen (default 20)")
    p.add_argument('--max-minutes', type=float, default=120, help="stop after this long even if nothing slowed (default 120)")
    p.add_argument('--cooldown-minutes', type=float, default=60, help="longest recovery wait (default 60)")
    p.add_argument('--probe-every', type=float, default=5, help="minutes between probes while recovering (default 5)")
    p.add_argument('--work', default=os.path.join(HERE, 'work'))
    p.add_argument('--results', default=os.path.join(HERE, 'results'))
    p.add_argument('--submitter')
    args = p.parse_args(argv)

    log = lambda m: print(time.strftime('%H:%M:%S ') + m, flush=True)
    work = os.path.abspath(args.work)
    os.makedirs(work, exist_ok=True)
    machine = bench.machine_info(args.submitter)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    out_dir = os.path.join(os.path.abspath(args.results), f"thermal-{machine['host']}-{stamp}")
    os.makedirs(out_dir)
    sensors = open_sensors(args.interval)
    log(f"{machine['host']}: {machine['cpu']}, sensors {type(sensors).__name__}")

    rows, probes, state = [], [], {'phase': 'idle', 't0': time.time()}
    sample_file = open(os.path.join(out_dir, 'samples.csv'), 'w', newline='')
    writer = csv.writer(sample_file)
    writer.writerow(['minute', 'phase', 'p_mhz', 'e_mhz', 'cpu_mw', 'pressure', 'temp_c', 'fps', 'load1'])

    def tick(fps=''):
        s = sensors.read()
        row = {'minute': round((time.time() - state['t0']) / 60, 2), 'phase': state['phase'], **s, 'fps': fps,
               'load1': round(os.getloadavg()[0], 2)}
        rows.append(row)
        writer.writerow([row[k] for k in ('minute', 'phase', 'p_mhz', 'e_mhz', 'cpu_mw', 'pressure', 'temp_c', 'fps', 'load1')])
        sample_file.flush()
        return row

    def do_probe(label):
        fps = probe(args.exe, args.probe, work, args.threads, log)
        entry = {'minute': round((time.time() - state['t0']) / 60, 2), 'label': label, 'fps': round(fps, 2)}
        probes.append(entry)
        log(f"probe ({label}): {fps:.2f} fps")
        return fps

    result = {'machine': machine, 'args': vars(args)}
    try:
        # 1. cool baseline
        log(f"idle for {args.idle_minutes:g} minutes (leave the machine alone)")
        end = time.time() + args.idle_minutes * 60
        while time.time() < end:
            tick()
            time.sleep(args.interval)
        idle = [r for r in rows if r['phase'] == 'idle']
        result['baseline'] = {'idle_minutes': args.idle_minutes, 'load1_at_start': idle[0]['load1'] if idle else None,
                              'load1_at_end': rows[-1]['load1'], 'p_mhz_idle': rows[-1]['p_mhz'],
                              'pressure': rows[-1]['pressure'], 'temp_c': rows[-1]['temp_c']}
        state['phase'] = 'probe-cold'
        cold = do_probe('cool')
        result['baseline']['probe_fps'] = round(cold, 2)

        # 2. load until it slows, then a while longer
        state['phase'] = 'load'
        load_start = time.time()
        recent, early, onset, evidence = [], [], None, None
        d = Decoding(args.exe, args.sample, os.path.join(work, 'loop'), args.threads)
        last, runs_done, clocks, first_pressure = None, 0, [], None
        log("decoding the sample over and over")
        while True:
            time.sleep(args.interval)
            if not d.running():
                d.sink.close()
                d.clean()
                runs_done += 1
                d = Decoding(args.exe, args.sample, os.path.join(work, 'loop'), args.threads)
                last = None
                tick('')
                continue
            now = time.time()
            current = d.progress()
            fps = ''
            if current and last and current[1] > last[1]:
                fps = round((current[0] - last[0]) / (current[1] - last[1]), 2)
            if current:
                last = current
            row = tick(fps)
            minute = (now - load_start) / 60
            if first_pressure is None and row['pressure'] not in ('', 'Nominal'):
                first_pressure = round(minute, 1)
                result['first_pressure_change'] = {'minute_in_load': first_pressure, 'level': row['pressure']}
                log(f"thermal pressure {row['pressure']} at {first_pressure} minutes (reported, not counted as slowing)")
            if fps != '':
                recent.append(fps)
                recent = recent[-int(max(1, 60 / args.interval)):]
                if 2 <= minute <= 5:
                    early.append(statistics.mean(recent))
            if row['p_mhz'] != '' and 2 <= minute <= 5:
                clocks.append(row['p_mhz'])
            if onset is None and minute > 5 and early:
                reference = statistics.median(early)
                window = max(1, int(120 / args.interval))
                last_rows = [r for r in rows[-window:] if r['phase'] == 'load']
                low = [r['fps'] for r in last_rows if r['fps'] != '']
                slow_clock = [r['p_mhz'] for r in last_rows if r['p_mhz'] != '']
                if len(low) >= window * 0.8 and statistics.mean(low) < 0.9 * reference:
                    onset, evidence = now - 120, f"decode speed under 90% of {reference:.1f} fps for two minutes"
                elif clocks and len(slow_clock) >= window * 0.8 and statistics.mean(slow_clock) < 0.9 * statistics.median(clocks):
                    onset, evidence = now - 120, f"CPU clock under 90% of {statistics.median(clocks):.0f} MHz for two minutes"
                if onset:
                    result['onset_minute_in_load'] = round((onset - load_start) / 60, 1)
                    result['onset_evidence'] = evidence
                    result['reference_fps'] = round(reference, 2)
                    log(f"slowing seen at {result['onset_minute_in_load']} minutes: {evidence}")
            if onset and now - onset >= (args.past_minutes + 2) * 60:
                log(f"{args.past_minutes:g} minutes past the onset: stopping the load")
                break
            if minute >= args.max_minutes:
                log("time limit reached")
                break
        result['load_minutes'] = round((time.time() - load_start) / 60, 1)
        result['sample_runs_completed'] = runs_done
        d.stop()
        d.clean()
        hot_probe_start = time.time()

        # 3. recovery
        state['phase'] = 'probe-hot'
        hot = do_probe('straight after the load')
        result['hot_probe_fps'] = round(hot, 2)
        state['phase'] = 'recover'
        cool_end = time.time() + args.cooldown_minutes * 60
        next_probe = time.time() + args.probe_every * 60
        recovered = None
        while time.time() < cool_end and recovered is None:
            tick()
            time.sleep(args.interval)
            if time.time() >= next_probe:
                state['phase'] = 'probe-recover'
                fps = do_probe(f"{(time.time() - hot_probe_start) / 60:.0f} min after the load")
                state['phase'] = 'recover'
                if fps >= 0.95 * cold:
                    recovered = (time.time() - hot_probe_start) / 60
                next_probe = time.time() + args.probe_every * 60
        result['recovery_minutes'] = round(recovered, 1) if recovered else None
        log(f"recovered after {recovered:.0f} minutes" if recovered else "did not recover within the limit")
    finally:
        sensors.close()
        sample_file.close()
        result['probes'] = probes
        with open(os.path.join(out_dir, 'thermal.json'), 'w') as f:
            json.dump(result, f, indent=2, default=str)
        with open(os.path.join(out_dir, 'probes.csv'), 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['minute', 'label', 'fps'])
            for e in probes:
                w.writerow([e['minute'], e['label'], e['fps']])
        write_summary(out_dir, result, rows)
    log(f"results written to {out_dir}")
    return 0


def write_summary(out_dir, r, rows):
    m = r['machine']
    lines = [f"# Thermal test: {m['cpu']} ({m.get('os_name') or m['os']}, {m.get('ram_gb', '?')} GB)", '',
             f"Run on {m['when']} by {m['submitted_by']} with toolkit {m['toolkit']['version']}.", '']
    b = r.get('baseline')
    if b:
        lines += [f"**Cool baseline.** Idle for {b['idle_minutes']:g} minutes first (load average {b['load1_at_start']} "
                  f"falling to {b['load1_at_end']}); thermal pressure {b['pressure'] or 'not reported'}"
                  f"{', hottest sensor ' + str(b['temp_c']) + ' C' if b['temp_c'] != '' else ''}; the short probe decoded at "
                  f"{b.get('probe_fps', '?')} fps.", '']
    if 'onset_minute_in_load' in r:
        lines += [f"**Slowing began {r['onset_minute_in_load']} minutes into the load** ({r['onset_evidence']}); "
                  f"the early speed was {r['reference_fps']} fps. The load ran {r['load_minutes']} minutes in all.", '']
    elif 'load_minutes' in r:
        lines += [f"**No slowing seen** in {r['load_minutes']} minutes of load.", '']
    if 'first_pressure_change' in r:
        lines += [f"macOS first reported thermal pressure {r['first_pressure_change']['level']} "
                  f"{r['first_pressure_change']['minute_in_load']} minutes into the load.", '']
    if 'hot_probe_fps' in r:
        lines += [f"Straight after the load the probe ran at {r['hot_probe_fps']} fps. "
                  + (f"It was back to within 5% of the cool figure after {r['recovery_minutes']} minutes idle."
                     if r.get('recovery_minutes') else "It had not recovered when the wait ended."), '']
    load = [x for x in rows if x['phase'] == 'load']
    if load:
        lines += ['| Minutes into load | Decode fps | CPU clock (MHz) | Thermal pressure |', '|---|---|---|---|']
        start = load[0]['minute']
        for k in range(int((load[-1]['minute'] - start) // 5) + 1):
            blk = [x for x in load if k * 5 <= x['minute'] - start < k * 5 + 5]
            fps = [x['fps'] for x in blk if x['fps'] != '']
            mhz = [x['p_mhz'] for x in blk if x['p_mhz'] != '']
            press = sorted({x['pressure'] for x in blk if x['pressure']})
            lines.append(f"| {k * 5} to {k * 5 + 5} | {statistics.mean(fps):.1f} | "
                         f"{round(statistics.mean(mhz)) if mhz else '-'} | {', '.join(press) or '-'} |" if fps else
                         f"| {k * 5} to {k * 5 + 5} | - | - | - |")
        lines.append('')
    lines += ['| Minute | Probe | fps |', '|---|---|---|'] + [f"| {e['minute']} | {e['label']} | {e['fps']} |" for e in r.get('probes', [])]
    with open(os.path.join(out_dir, 'summary.md'), 'w') as f:
        f.write('\n'.join(lines) + '\n')


if __name__ == '__main__':
    sys.exit(main())
