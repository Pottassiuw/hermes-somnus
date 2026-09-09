"""
somnus.guards — the veto layer.

Every trigger in Somnus is a disjunction; every guard is a conjunction. A dream
cycle runs only when SOME trigger fires and ALL guards pass.

Guards are pure functions over an injectable HostReader so they are testable
without a Raspberry Pi, and so the same code can run in CI.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

__all__ = ["HostReader", "LinuxHost", "FakeHost", "GuardResult", "evaluate", "triggers_fired"]


class HostReader(Protocol):
    def load1(self) -> float: ...
    def temp_c(self) -> float: ...
    def free_mem_mb(self) -> int: ...
    def free_disk_pct(self, path: str) -> float: ...


class LinuxHost:
    """Reads /proc and /sys. Degrades gracefully where a file is absent."""

    def load1(self) -> float:
        try:
            return float(Path("/proc/loadavg").read_text().split()[0])
        except Exception:
            return 0.0

    def temp_c(self) -> float:
        for zone in ("/sys/class/thermal/thermal_zone0/temp",):
            try:
                return int(Path(zone).read_text().strip()) / 1000.0
            except Exception:
                continue
        return 0.0  # unknown temperature must not block; the health probe alerts instead

    def free_mem_mb(self) -> int:
        try:
            for line in Path("/proc/meminfo").read_text().splitlines():
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) // 1024
        except Exception:
            pass
        return 1 << 30

    def free_disk_pct(self, path: str) -> float:
        try:
            st = os.statvfs(path)
            return 100.0 * st.f_bavail / st.f_blocks if st.f_blocks else 100.0
        except Exception:
            return 100.0


@dataclass
class FakeHost:
    """Injectable host for tests."""
    _load1: float = 0.1
    _temp_c: float = 45.0
    _free_mem_mb: int = 4096
    _free_disk_pct: float = 60.0

    def load1(self) -> float: return self._load1
    def temp_c(self) -> float: return self._temp_c
    def free_mem_mb(self) -> int: return self._free_mem_mb
    def free_disk_pct(self, path: str) -> float: return self._free_disk_pct


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    failures: tuple[str, ...] = ()
    observations: dict = field(default_factory=dict)

    def reason(self) -> str:
        return "ok" if self.ok else "; ".join(self.failures)


def evaluate(
    cfg,
    host: HostReader,
    *,
    idle_minutes: float,
    spend_today_usd: float,
    lock_free: bool,
    health_ok: bool,
    somnus_home: str | os.PathLike = ".",
) -> GuardResult:
    """
    Conjunction of every guard. Returns the full failure list rather than
    short-circuiting, because the morning digest should say *everything* that
    was wrong, not just the first thing.
    """
    g = cfg.guards
    obs = {
        "load1": host.load1(),
        "temp_c": host.temp_c(),
        "free_mem_mb": host.free_mem_mb(),
        "free_disk_pct": host.free_disk_pct(str(somnus_home)),
        "idle_minutes": idle_minutes,
        "spend_today_usd": spend_today_usd,
        "lock_free": lock_free,
        "health_ok": health_ok,
    }
    fails: list[str] = []

    if obs["load1"] > g.max_load1:
        fails.append(f"load1={obs['load1']:.2f}>{g.max_load1}")
    if obs["temp_c"] > g.max_temp_c:
        fails.append(f"temp={obs['temp_c']:.0f}C>{g.max_temp_c}")
    if obs["free_mem_mb"] < g.min_free_mem_mb:
        fails.append(f"free_mem={obs['free_mem_mb']}MB<{g.min_free_mem_mb}")
    if obs["free_disk_pct"] < g.min_free_disk_pct:
        fails.append(f"free_disk={obs['free_disk_pct']:.1f}%<{g.min_free_disk_pct}")
    if idle_minutes < cfg.triggers.quiet_minutes:
        fails.append(f"user_active_{idle_minutes:.0f}m_ago<{cfg.triggers.quiet_minutes}")
    if spend_today_usd >= cfg.budget.daily_cap_usd:
        fails.append(f"budget_exhausted={spend_today_usd:.2f}>={cfg.budget.daily_cap_usd}")
    if not lock_free:
        fails.append("lock_held")
    if not health_ok:
        fails.append("health_probe_red")

    return GuardResult(ok=not fails, failures=tuple(fails), observations=obs)


def triggers_fired(
    cfg,
    *,
    hour: int,
    idle_minutes: float,
    backlog_turns: int,
    open_failure_signatures: int,
    novelty_fraction: float = 0.0,
    compression_pending: bool = False,
) -> tuple[str, ...]:
    """
    Disjunction of triggers. Returns every trigger that fired, for the digest.

    Note that the scheduled window still requires `min_idle_minutes` — a cron
    time that fires while you are working is not a dream, it is an interruption.
    """
    t = cfg.triggers
    fired: list[str] = []

    if hour == t.scheduled_hour and idle_minutes >= t.min_idle_minutes:
        fired.append("scheduled_window")
    if backlog_turns >= t.episodic_backlog_turns:
        fired.append(f"episodic_backlog={backlog_turns}")
    if open_failure_signatures >= t.open_failure_threshold:
        fired.append(f"open_failures={open_failure_signatures}")
    if novelty_fraction >= t.novelty_fraction:
        fired.append(f"novelty={novelty_fraction:.2f}")
    if compression_pending and t.on_session_compress:
        fired.append("post_compaction")

    return tuple(fired)
