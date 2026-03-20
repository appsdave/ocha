"""Execution-plan computation for parallel multi-agent pipelines.

Determines which workers can run concurrently without risking merge
conflicts, based on their declared file-ownership patterns.

The orchestrator calls :func:`compute_execution_plan` before advancing
the pipeline.  It returns an ordered list of *execution groups* — each
group contains workers whose owned directories are disjoint and can
therefore safely run in parallel.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Sequence

from .file_lock import _patterns_overlap
from .state import WorkerSession, WorkerStatus


class ConcurrencyPolicy(StrEnum):
    """How aggressively to parallelise workers."""

    SEQUENTIAL = "sequential"   # One worker at a time (safest)
    AUTO = "auto"               # Parallel when scopes are disjoint
    FORCE_PARALLEL = "parallel" # All workers in one group (risky)


@dataclass(slots=True, frozen=True)
class ExecutionGroup:
    """A set of workers that can run concurrently."""

    workers: tuple[WorkerSession, ...]

    @property
    def session_ids(self) -> list[str]:
        return [w.session_id for w in self.workers]

    def __len__(self) -> int:
        return len(self.workers)


def _scopes_conflict(a: WorkerSession, b: WorkerSession) -> bool:
    """Return True if two workers' owned directories overlap."""
    for pat_a in _owned_patterns(a):
        for pat_b in _owned_patterns(b):
            if _patterns_overlap(pat_a, pat_b):
                return True
    return False


def _owned_patterns(worker: WorkerSession) -> list[str]:
    """Extract the owned patterns list from a worker.

    The ``owned_directory`` field is a single string (e.g. ``"app/"``).
    We wrap it in a list for uniform handling.
    """
    od = worker.owned_directory
    if not od:
        return []
    return [od]


def compute_execution_plan(
    workers: Sequence[WorkerSession],
    policy: ConcurrencyPolicy = ConcurrencyPolicy.AUTO,
) -> list[ExecutionGroup]:
    """Partition *workers* into ordered execution groups.

    Parameters
    ----------
    workers:
        The queued workers to schedule.  Only workers with status
        ``QUEUED`` are considered; others are silently skipped.
    policy:
        Controls parallelism strategy.

    Returns
    -------
    list[ExecutionGroup]
        Groups in execution order.  The orchestrator should launch all
        workers in group 0 first, wait for them to finish, then launch
        group 1, and so on.

    Algorithm (``AUTO`` policy)
    ---------------------------
    Greedy first-fit: iterate workers in pipeline order.  For each
    worker, try to add it to the current group.  If it conflicts with
    any worker already in the group, start a new group.

    This preserves the original pipeline ordering while maximising
    parallelism for non-overlapping scopes.
    """
    queued = [w for w in workers if w.status == WorkerStatus.QUEUED]
    if not queued:
        return []

    if policy == ConcurrencyPolicy.SEQUENTIAL:
        return [ExecutionGroup(workers=(w,)) for w in queued]

    if policy == ConcurrencyPolicy.FORCE_PARALLEL:
        return [ExecutionGroup(workers=tuple(queued))]

    # AUTO — greedy first-fit grouping
    groups: list[list[WorkerSession]] = []
    for worker in queued:
        placed = False
        for group in groups:
            if not any(_scopes_conflict(worker, existing) for existing in group):
                group.append(worker)
                placed = True
                break
        if not placed:
            groups.append([worker])

    return [ExecutionGroup(workers=tuple(g)) for g in groups]
