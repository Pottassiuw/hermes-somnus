"""
somnus.daemon — the orchestrator.

One night = one call to `dream_cycle`. Every phase is budgeted; every invariant
violation aborts and rolls back; nothing is promoted without a verdict.

The LLM and the fixture runner are injected (`Runtime`) so the whole cycle can
be exercised end-to-end in tests with fakes — which is the only way you will
ever trust it enough to let it run unattended.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Protocol, Sequence

from . import bench as _bench
from . import config as _config
from . import consolidate as _consolidate
from . import guards as _guards
from . import ideate as _ideate
from . import state as _state
from . import triage as _triage

__all__ = ["Abort", "Budget", "Runtime", "PhaseReport", "CycleReport", "dream_cycle"]


class Abort(RuntimeError):
    """Any invariant or budget violation. Always followed by rollback."""


# --------------------------------------------------------------------------- #
# Budget (IR-5)
# --------------------------------------------------------------------------- #

@dataclass
class Budget:
    wall_deadline: float
    llm_calls_left: int
    usd_left: float
    llm_calls_used: int = 0
    usd_used: float = 0.0

    @classmethod
    def start(cls, cfg: _config.SomnusConfig, now: float | None = None) -> "Budget":
        now = now if now is not None else time.time()
        return cls(
            wall_deadline=now + cfg.budget.max_wall_minutes * 60,
            llm_calls_left=cfg.budget.max_llm_calls,
            usd_left=cfg.budget.daily_cap_usd,
        )

    def spend(self, calls: int = 0, usd: float = 0.0, *, now: float | None = None) -> None:
        now = now if now is not None else time.time()
        if now > self.wall_deadline:
            raise Abort("wall_clock_exceeded")
        self.llm_calls_left -= calls
        self.usd_left -= usd
        self.llm_calls_used += calls
        self.usd_used += usd
        if self.llm_calls_left < 0:
            raise Abort("llm_call_budget_exceeded")
        if self.usd_left < 0:
            raise Abort("usd_budget_exceeded")


# --------------------------------------------------------------------------- #
# Injected runtime
# --------------------------------------------------------------------------- #

class Runtime(Protocol):
    """Everything the cycle needs from the outside world."""

    def llm(self, prompt: str, *, tier: str = "aux") -> str: ...
    def recent_turns(self) -> Sequence[_triage.Turn]: ...
    def memory_region(self) -> Sequence[_consolidate.MemoryEntry]: ...
    def trajectory_excerpts(self) -> str: ...
    def fixture_scores(self, variant: str) -> float: ...
    def baseline_reproduces(self, hypothesis) -> bool: ...
    def build_candidate(self, hypothesis) -> object: ...
    def gate_a(self, candidate) -> tuple[bool, str]: ...
    def run_fixtures(self, side: str, candidate) -> Sequence[_bench.CaseResult]: ...
    def stage(self, hypothesis, candidate, verdict) -> str: ...


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #

@dataclass
class PhaseReport:
    name: str
    ok: bool
    detail: str = ""
    items: int = 0


@dataclass
class CycleReport:
    run_id: str = ""
    status: str = "unknown"
    reason: str = ""
    triggers: tuple[str, ...] = ()
    phases: list[PhaseReport] = field(default_factory=list)
    failures_found: int = 0
    batches_accepted: int = 0
    batches_rejected: int = 0
    hypotheses_queued: int = 0
    accepted: list[dict] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)
    tokens_saved: int = 0
    llm_calls: int = 0
    usd: float = 0.0

    def add(self, name: str, ok: bool, detail: str = "", items: int = 0) -> None:
        self.phases.append(PhaseReport(name, ok, detail, items))


# --------------------------------------------------------------------------- #
# The cycle
# --------------------------------------------------------------------------- #

def dream_cycle(
    cfg: _config.SomnusConfig,
    rt: Runtime,
    *,
    host: _guards.HostReader | None = None,
    store: _state.Store | None = None,
    now_hour: int | None = None,
) -> CycleReport:
    report = CycleReport()
    if not cfg.enabled:
        report.status = "disabled"
        return report

    host = host or _guards.LinuxHost()
    store = store or _state.Store(cfg.db_path)
    ledger = _state.Ledger(cfg.ledger_path)

    # ---- trigger + guards ------------------------------------------------- #
    hour = now_hour if now_hour is not None else time.localtime().tm_hour
    idle = store.idle_minutes()
    fired = _guards.triggers_fired(
        cfg,
        hour=hour,
        idle_minutes=idle,
        backlog_turns=store.unconsolidated_turns(),
        open_failure_signatures=store.open_failure_signatures(),
    )
    report.triggers = fired
    if not fired:
        report.status, report.reason = "skipped", "no_trigger"
        return report

    gr = _guards.evaluate(
        cfg, host,
        idle_minutes=idle,
        spend_today_usd=store.spend_today(),
        lock_free=not cfg.lock_path.exists(),
        health_ok=True,
        somnus_home=cfg.home_path,
    )
    if not gr.ok:
        report.status, report.reason = "skipped", gr.reason()
        return report

    identity_before = _state.identity_hash(cfg.identity.manifest_paths)
    fixture_hash = _bench.fixture_tree_hash(cfg.fixtures_path)
    report.run_id = store.begin_run(",".join(fired), identity_before)
    budget = Budget.start(cfg)
    snapshot_path = None

    try:
        with _state.flock(cfg.lock_path):
            snapshot_path = _state.snapshot(
                cfg.home_path / "staging", cfg.snapshots_path, reason="pre-dream"
            )

            # ---- PHASE 1 · TRIAGE ---------------------------------------- #
            records = _triage.extract(
                rt.recent_turns(), lambda p: _spend(budget, rt, p, "aux")
            )
            for rec in records:
                store.upsert_failure(rec.to_dict())
            report.failures_found = len(records)
            report.add("triage", True, f"{len(records)} failure signatures", len(records))
            _bench.verify_fixture_manifest(cfg.fixtures_path, fixture_hash)

            # ---- PHASE 2 · CONSOLIDATE ----------------------------------- #
            region = list(rt.memory_region())
            if region:
                try:
                    batch = _consolidate.build_batch(
                        region,
                        rt.trajectory_excerpts(),
                        lambda p: _spend(budget, rt, p, "main"),
                        identity_before=identity_before,
                    )
                    ok, why = _consolidate.utility_ok(
                        batch,
                        score_with=rt.fixture_scores("with_region"),
                        score_without=rt.fixture_scores("without_region"),
                        score_replacement=rt.fixture_scores("replacement"),
                    )
                    if ok:
                        report.batches_accepted += 1
                        report.tokens_saved += max(0, batch.tokens_before - batch.tokens_after)
                        ledger.append("somnus", "consolidate", batch.id,
                                      evidence={"why": why, **batch.to_dict()["size_delta"]})
                    else:
                        report.batches_rejected += 1
                        ledger.append("somnus", "reject", batch.id, evidence={"why": why})
                    report.add("consolidate", ok, why, len(batch.replacement_set))
                except _consolidate.SchemaRejection as exc:
                    report.batches_rejected += 1
                    report.add("consolidate", False, str(exc))
            else:
                report.add("consolidate", True, "no region selected", 0)

            _state.assert_identity(identity_before, cfg.identity.manifest_paths)

            # ---- PHASE 3 · IDEATE ---------------------------------------- #
            hypotheses = [
                _ideate.from_failure(r.to_dict(), target_path=f"skills/{r.task_class or 'general'}")
                for r in records if r.status == "open"
            ]
            hypotheses = _ideate.rank(hypotheses, cfg.ideate_top_k)
            report.hypotheses_queued = len(hypotheses)
            for h in hypotheses:
                store.enqueue_hypothesis(h.to_dict(), report.run_id)
            report.add("ideate", True, f"{len(hypotheses)} ranked hypotheses", len(hypotheses))

            # ---- PHASE 4-5 · BUILD + BENCH ------------------------------- #
            for h in hypotheses:
                if not rt.baseline_reproduces(h):
                    store.settle_hypothesis(h.id, "rejected", "unfalsifiable_fixture")
                    report.rejected.append({"id": h.id, "reason": "unfalsifiable_fixture"})
                    continue

                candidate = rt.build_candidate(h)
                ok, why = rt.gate_a(candidate)
                if not ok:
                    store.settle_hypothesis(h.id, "rejected", f"gate_a:{why}")
                    report.rejected.append({"id": h.id, "reason": f"gate_a:{why}"})
                    continue

                base_results = rt.run_fixtures("baseline", candidate)
                cand_results = rt.run_fixtures("candidate", candidate)
                verdict = _bench.adjudicate(
                    base_results, cand_results,
                    min_effect=cfg.bench.min_effect,
                    alpha=cfg.bench.alpha,
                    min_pairs=cfg.bench.min_pairs,
                )
                store.settle_hypothesis(
                    h.id, "accepted" if verdict.accept else "rejected",
                    verdict.reason, verdict.to_json(),
                )
                if verdict.accept:
                    ref = rt.stage(h, candidate, verdict)
                    ledger.append("somnus", "stage", h.id,
                                  evidence={"ref": ref, "verdict": verdict.reason})
                    report.accepted.append({"id": h.id, "ref": ref,
                                            "effect": verdict.effect,
                                            "p": verdict.p_mcnemar})
                else:
                    report.rejected.append({"id": h.id, "reason": verdict.reason})

                _bench.verify_fixture_manifest(cfg.fixtures_path, fixture_hash)

            report.add("bench", True,
                       f"{len(report.accepted)} accepted / {len(report.rejected)} rejected",
                       len(report.accepted))

            # ---- close out ------------------------------------------------ #
            _state.assert_identity(identity_before, cfg.identity.manifest_paths)
            report.status = "ok"

    except (Abort, _state.IdentityDrift, RuntimeError) as exc:
        report.status, report.reason = "aborted", str(exc)
        report.add("abort", False, str(exc))
        if snapshot_path is not None:
            try:
                _state.restore(snapshot_path, cfg.home_path)
            except Exception as restore_exc:  # pragma: no cover
                report.add("rollback", False, str(restore_exc))
            else:
                report.add("rollback", True, str(snapshot_path))
    finally:
        report.llm_calls = budget.llm_calls_used
        report.usd = budget.usd_used
        if report.run_id:
            store.finish_run(
                report.run_id, report.status, report.reason,
                _state.identity_hash(cfg.identity.manifest_paths),
                budget.usd_used, budget.llm_calls_used,
            )
        _state.prune_snapshots(cfg.snapshots_path, keep=5)

    return report


def _spend(budget: Budget, rt: Runtime, prompt: str, tier: str) -> str:
    """Every LLM call goes through the budget. There is no other path."""
    budget.spend(calls=1, usd=0.01 if tier == "aux" else 0.05)
    return rt.llm(prompt, tier=tier)
