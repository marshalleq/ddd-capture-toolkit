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

    Lifecycle:
      cpus = allocator.allocate(job_id, cores_wanted)
      # ... launch subprocess with sched_setaffinity(0, set(cpus)) ...
      # eventually:
      allocator.release(job_id)

    Multiple concurrent jobs are intentionally placed on DIFFERENT L3
    groups when possible — that's the win on Zen X3D where cross-CCD
    L3 misses dominate the per-decode fps regression. When all groups
    are occupied the allocator gives partial allocations (shared L3)
    rather than refusing; jobs still benefit from "no cross-CCD
    migration" even when L3 isn't dedicated.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._groups = discover_topology()
        self._assignments: Dict[str, List[int]] = {}

    @property
    def available(self) -> bool:
        """True if we discovered any topology (i.e. Linux with /sys)."""
        return bool(self._groups)

    def total_physical_cores(self) -> int:
        return sum(len(g.physical_cores) for g in self._groups)

    def allocate(self, job_id: str, cores_wanted: int) -> Optional[List[int]]:
        """Reserve up to `cores_wanted` physical cores for `job_id`.

        Returns the assigned CPU numbers, or None if pinning isn't
        possible (no topology discovered, or no cores free at all).
        Callers should treat a None return as "run unpinned".
        """
        if cores_wanted <= 0:
            return None
        with self._lock:
            if not self._groups:
                return None

            def free_cores(g: L3Group) -> List[int]:
                return [c for c in g.physical_cores if c not in g.allocated]

            # Prefer the LEAST-occupied group that can fit the full ask;
            # falls back to the least-occupied group with any free cores.
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
                # Every physical core is taken — no pinning, let the
                # scheduler do its thing.
                return None

            group.allocated.update(chosen)
            self._assignments[job_id] = list(chosen)
            return list(chosen)

    def release(self, job_id: str) -> None:
        """Return this job's allocation to the pool. Idempotent."""
        with self._lock:
            cores = self._assignments.pop(job_id, None)
            if not cores:
                return
            cores_set = set(cores)
            for g in self._groups:
                g.allocated -= cores_set

    def describe(self) -> str:
        """Human-readable topology snapshot for logging."""
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
                    f"in use=[{','.join(map(str, used))}]; "
                    f"free=[{','.join(map(str, free))}]"
                )
            return '\n'.join(lines)


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
