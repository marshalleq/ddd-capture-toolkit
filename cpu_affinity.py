"""CPU affinity / pinning for compute-heavy jobs.

Multi-decode workloads on modern CPUs (AMD Zen with separate CCDs, Intel
Hybrid with P/E cores, multi-socket NUMA) lose significant per-decode fps
when the kernel scheduler bounces a job's worker processes across L3
caches. The kernel doesn't know that a vhs-decode is a tight cluster
of related processes that should stay co-located.

This module discovers the L3 grouping from /sys and hands out core
slots to jobs at start-time. Each job's subprocess is pinned via
sched_setaffinity (via preexec_fn at subprocess.Popen time) so its
worker children inherit the affinity on fork.

Linux-only. discover_topology() returns [] elsewhere; AffinityAllocator
then becomes a no-op (allocate returns None, caller runs unpinned).

The allocator prefers:
  1. An EMPTY L3 group (best cache isolation between decodes).
  2. The LEAST-occupied group when no empty group fits.
  3. Partial allocation from any group if the full ask doesn't fit.
  4. None — caller runs unpinned.

So on a 9950X3D (two L3 instances), the first concurrent decode lands
on CCD 0 (the V-Cache CCD), the second on CCD 1, the third shares
CCD 0 with the first, and so on.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class L3Group:
    """One L3 cache instance — typically one CCD on AMD, one die on Intel.

    cpus: every logical CPU that shares this L3, including SMT siblings.
    physical_cores: one logical CPU per physical core, picked deterministically
        (the lowest CPU id in each SMT sibling set). These are the ones we
        hand out; SMT siblings are deliberately NOT allocated, so a pinned
        job runs only on physical cores, not on logical SMT threads where
        two processes would contend for execution units.
    smt_siblings: physical_cpu -> [other CPUs sharing this physical core].
        Not allocated, but recorded for diagnostics.
    allocated: subset of physical_cores currently held by some job.
    """
    cpus: Set[int]
    physical_cores: List[int]
    smt_siblings: Dict[int, List[int]]
    allocated: Set[int] = field(default_factory=set)


def _read_cpu_list(path: str) -> List[int]:
    """Parse a kernel cpu-list ('0-7,16-23') from a /sys file."""
    try:
        with open(path) as f:
            text = f.read().strip()
    except OSError:
        return []
    cpus: List[int] = []
    for part in text.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            a, b = part.split('-')
            try:
                cpus.extend(range(int(a), int(b) + 1))
            except ValueError:
                continue
        else:
            try:
                cpus.append(int(part))
            except ValueError:
                continue
    return cpus


def discover_topology() -> List[L3Group]:
    """Parse /sys to build the L3 groups.

    Returns one L3Group per L3 instance, sorted by lowest CPU number
    (so on Zen, CCD 0 comes first). Empty list on non-Linux or if /sys
    doesn't expose the topology we expect.
    """
    if not os.path.isdir('/sys/devices/system/cpu'):
        return []

    online = _read_cpu_list('/sys/devices/system/cpu/online')
    if not online:
        return []

    # Per-cpu: which CPUs share its L3, which are its SMT siblings.
    l3_shared: Dict[int, frozenset] = {}
    smt_siblings_raw: Dict[int, Set[int]] = {}
    for cpu in online:
        l3_path = f'/sys/devices/system/cpu/cpu{cpu}/cache/index3/shared_cpu_list'
        smt_path = f'/sys/devices/system/cpu/cpu{cpu}/topology/thread_siblings_list'
        l3 = frozenset(_read_cpu_list(l3_path)) if os.path.exists(l3_path) else frozenset({cpu})
        smt = set(_read_cpu_list(smt_path)) if os.path.exists(smt_path) else {cpu}
        l3_shared[cpu] = l3
        smt_siblings_raw[cpu] = smt

    # Group CPUs by their L3 set (same set => same L3 instance).
    groups_raw: Dict[frozenset, Set[int]] = {}
    for cpu, l3 in l3_shared.items():
        groups_raw.setdefault(l3, set()).add(cpu)

    result: List[L3Group] = []
    for l3_set, cpus in groups_raw.items():
        # Choose one logical CPU per physical core: the lowest-numbered
        # member of each SMT sibling set.
        seen_smt: Set[int] = set()
        physical: List[int] = []
        smt_map: Dict[int, List[int]] = {}
        for cpu in sorted(cpus):
            if cpu in seen_smt:
                continue
            siblings = smt_siblings_raw.get(cpu, {cpu})
            seen_smt.update(siblings)
            physical.append(cpu)
            smt_map[cpu] = sorted(s for s in siblings if s != cpu)
        if physical:
            result.append(L3Group(
                cpus=set(cpus),
                physical_cores=physical,
                smt_siblings=smt_map,
            ))

    result.sort(key=lambda g: min(g.physical_cores) if g.physical_cores else 0)
    return result


class AffinityAllocator:
    """Thread-safe allocator that hands out physical-core slots to jobs.

    Two allocation types:

      DECODE (allocate_decode) — reserves specific physical cores for the
        job. Used by vhs-decode. Pins the subprocess to that exact set so
        no other decode can grab those cores. When a decode is allocated
        or released, all registered NON-DECODE jobs are re-affined so
        their allowed set never overlaps with running decodes.

      NON-DECODE (reserve_non_decode_set + register_non_decode_pid) —
        gives the job an initial pin set of "all physical cores NOT
        currently held by decodes". The set is then dynamically narrowed
        if a decode starts later, and widened when a decode releases.
        Used by lds-compress, tbc-export, audio-align, final-mux.

    Lifecycle (decode):
      cpus = allocator.allocate_decode(job_id, cores_wanted)
      # launch subprocess with sched_setaffinity(0, set(cpus)) via preexec
      ...
      allocator.release(job_id)

    Lifecycle (non-decode):
      allowed = allocator.reserve_non_decode_set(job_id)
      # launch subprocess with sched_setaffinity(0, set(allowed)) via preexec
      allocator.register_non_decode_pid(job_id, process.pid)
      ...
      allocator.release(job_id)

    Decodes are intentionally placed on DIFFERENT L3 groups when possible
    — the cache-locality win on Zen X3D. When all physical cores are
    occupied by decodes, non-decodes fall back to the full physical-core
    set (they share with decodes, unavoidable at saturation).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._groups = discover_topology()
        # Unified per-job allocation table:
        # {job_id: {'type': 'decode'|'non_decode', 'cores': [int], 'pid': int|None}}
        self._allocations: Dict[str, Dict] = {}

    @property
    def available(self) -> bool:
        """True if we discovered any topology (i.e. Linux with /sys)."""
        return bool(self._groups)

    def total_physical_cores(self) -> int:
        return sum(len(g.physical_cores) for g in self._groups)

    def allocate_decode(self, job_id: str, cores_wanted: int) -> Optional[List[int]]:
        """Reserve up to `cores_wanted` physical cores for a decode job.

        Returns the assigned CPU numbers, or None if pinning isn't possible
        (no topology discovered, or no cores free at all). Callers should
        treat a None return as 'run unpinned'.

        Side effect: any registered non-decode jobs are re-affined so their
        allowed set excludes the newly-pinned cores.
        """
        if cores_wanted <= 0:
            return None
        with self._lock:
            if not self._groups:
                return None
            allocated = self._allocate_decode_locked(cores_wanted)
            if allocated is None:
                return None
            self._allocations[job_id] = {
                'type': 'decode',
                'cores': allocated,
                'pid': None,
            }
            self._reaffine_non_decodes_locked()
            return list(allocated)

    # Backwards-compatible alias for the old single-purpose method.
    def allocate(self, job_id: str, cores_wanted: int) -> Optional[List[int]]:
        return self.allocate_decode(job_id, cores_wanted)

    def reserve_non_decode_set(self, job_id: str) -> Optional[List[int]]:
        """Compute the initial pinning set for a non-decode CPU-heavy job.

        Returns 'all physical cores NOT currently held by decodes', or
        None if no topology is available. Caller should pass this to
        subprocess.Popen via preexec_fn and then call
        register_non_decode_pid once the process has spawned so future
        decode start/release can re-affine this job.

        If decodes currently saturate all physical cores, the returned
        set falls back to ALL physical cores (the non-decode will share;
        unavoidable at saturation).
        """
        with self._lock:
            if not self._groups:
                return None
            allowed = self._non_decode_allowed_locked()
            self._allocations[job_id] = {
                'type': 'non_decode',
                'cores': list(allowed),
                'pid': None,
            }
            return list(allowed)

    def register_non_decode_pid(self, job_id: str, pid: int) -> None:
        """Attach a PID to a non-decode allocation so it can be re-affined
        when decode allocations change. No-op if the job_id isn't a
        currently-registered non-decode."""
        with self._lock:
            info = self._allocations.get(job_id)
            if info and info.get('type') == 'non_decode':
                info['pid'] = pid

    def release(self, job_id: str) -> None:
        """Release this job's allocation. Idempotent.

        If the released job was a decode, registered non-decodes are
        re-affined — their allowed set grows back to include the freed
        cores.
        """
        with self._lock:
            info = self._allocations.pop(job_id, None)
            if info is None:
                return
            if info.get('type') == 'decode':
                cores_set = set(info.get('cores', []))
                for g in self._groups:
                    g.allocated -= cores_set
                self._reaffine_non_decodes_locked()

    def describe(self) -> str:
        """Human-readable topology + allocation snapshot for logging."""
        with self._lock:
            if not self._groups:
                return "(no L3-group topology available — pinning disabled)"
            lines = [
                f"{len(self._groups)} L3 group(s), "
                f"{self.total_physical_cores()} physical cores total:"
            ]
            for i, g in enumerate(self._groups):
                free = sorted(set(g.physical_cores) - g.allocated)
                used = sorted(g.allocated)
                lines.append(
                    f"  L3 group {i}: physical={g.physical_cores}; "
                    f"decode-held=[{','.join(map(str, used))}]; "
                    f"free=[{','.join(map(str, free))}]"
                )
            non_decodes = [
                (jid, info) for jid, info in self._allocations.items()
                if info.get('type') == 'non_decode'
            ]
            if non_decodes:
                lines.append(f"  Non-decode pins ({len(non_decodes)}):")
                for jid, info in non_decodes:
                    pid = info.get('pid', '?')
                    cores = info.get('cores', [])
                    lines.append(f"    {jid} (pid {pid}): {cores}")
            return '\n'.join(lines)

    # ----- Internals (callers hold _lock) -----

    def _allocate_decode_locked(self, cores_wanted: int) -> Optional[List[int]]:
        """Pick cores for a decode, preferring an empty / least-occupied
        L3 group. Returns the chosen list (also updates group.allocated)
        or None if no cores are free."""
        def free_cores(g: L3Group) -> List[int]:
            return [c for c in g.physical_cores if c not in g.allocated]

        full_candidates = []
        partial_candidates = []
        for g in self._groups:
            free = free_cores(g)
            if len(free) >= cores_wanted:
                full_candidates.append((g, free))
            elif free:
                partial_candidates.append((g, free))

        if full_candidates:
            full_candidates.sort(key=lambda gf: len(gf[0].allocated))
            group, free = full_candidates[0]
            chosen = free[:cores_wanted]
        elif partial_candidates:
            partial_candidates.sort(key=lambda gf: -len(gf[1]))
            group, free = partial_candidates[0]
            chosen = free  # take everything available in the best group
        else:
            return None

        group.allocated.update(chosen)
        return list(chosen)

    def _all_physical_cores_locked(self) -> Set[int]:
        s: Set[int] = set()
        for g in self._groups:
            s.update(g.physical_cores)
        return s

    def _decode_cores_locked(self) -> Set[int]:
        s: Set[int] = set()
        for info in self._allocations.values():
            if info.get('type') == 'decode':
                s.update(info.get('cores', []))
        return s

    def _non_decode_allowed_locked(self) -> List[int]:
        """All physical cores not currently held by decodes. Falls back
        to all physical cores when decodes saturate everything."""
        all_phys = self._all_physical_cores_locked()
        decode_set = self._decode_cores_locked()
        allowed = sorted(all_phys - decode_set)
        if not allowed:
            allowed = sorted(all_phys)
        return allowed

    def _reaffine_non_decodes_locked(self) -> None:
        """Push the current allowed set to every registered non-decode PID
        via os.sched_setaffinity. Lost PIDs (process died) are skipped
        silently; release() will clean their entry up."""
        new_allowed = self._non_decode_allowed_locked()
        new_set = set(new_allowed)
        for info in self._allocations.values():
            if info.get('type') != 'non_decode':
                continue
            pid = info.get('pid')
            if not pid:
                continue
            try:
                os.sched_setaffinity(pid, new_set)
                info['cores'] = list(new_allowed)
            except (OSError, ProcessLookupError):
                # Process gone; leave entry, release() will pop it.
                pass


def make_preexec_fn(cpus):
    """Return a subprocess preexec_fn that pins the child to `cpus`.

    Safe to call with cpus=None / empty (returns None, caller passes that
    straight to subprocess.Popen which then doesn't run a preexec hook).
    Linux-only: uses os.sched_setaffinity which doesn't exist on macOS;
    callers should only invoke this on platforms where the allocator
    actually returned cores.
    """
    if not cpus:
        return None
    cpu_set = set(int(c) for c in cpus)

    def _preexec():
        try:
            os.sched_setaffinity(0, cpu_set)
        except (OSError, AttributeError):
            # Best-effort — if pinning fails for any reason, run unpinned.
            pass

    return _preexec
