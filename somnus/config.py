"""
somnus.config — typed configuration loaded from ~/.hermes/config.yaml.

Defaults here are the ones argued for in the compendium. They are conservative
on purpose: it is much easier to loosen a threshold after a month of clean runs
than to explain a night that rewrote forty skills.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any

try:  # pyyaml ships with Hermes; degrade to defaults if it is somehow absent
    import yaml
except Exception:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


@dataclass
class Triggers:
    scheduled_hour: int = 3
    schedule: str = "0 3 * * *"
    min_idle_minutes: int = 90
    quiet_minutes: int = 60
    episodic_backlog_turns: int = 200
    open_failure_threshold: int = 3
    novelty_fraction: float = 0.4
    on_session_compress: bool = True


@dataclass
class Guards:
    max_load1: float = 2.0
    max_temp_c: float = 70.0
    min_free_mem_mb: int = 700
    min_free_disk_pct: float = 15.0


@dataclass
class Budget:
    daily_cap_usd: float = 5.0
    monthly_cap_usd: float = 80.0
    max_wall_minutes: int = 120
    max_llm_calls: int = 255


@dataclass
class PhaseBudget:
    wall_minutes: int = 15
    llm_calls: int = 20
    model: str = "aux"          # aux | main


@dataclass
class Phases:
    triage: PhaseBudget = field(default_factory=lambda: PhaseBudget(15, 20, "aux"))
    # NEVER a tiny model for consolidation: up to 30% format errors -> silent
    # long-term memory corruption (arXiv:2602.19320).
    consolidate: PhaseBudget = field(default_factory=lambda: PhaseBudget(25, 60, "main"))
    ideate: PhaseBudget = field(default_factory=lambda: PhaseBudget(10, 20, "main"))
    build: PhaseBudget = field(default_factory=lambda: PhaseBudget(40, 120, "main"))
    bench: PhaseBudget = field(default_factory=lambda: PhaseBudget(20, 30, "aux"))


@dataclass
class Bench:
    min_pairs: int = 20
    repeats: int = 3
    alpha: float = 0.01
    min_effect: float = 0.02
    require_replication: bool = True
    guard_regression_policy: str = "hard_reject"


@dataclass
class Sandbox:
    backend: str = "docker"
    image: str = "python:3.11-slim"
    network: str = "none"           # none | llm_only | allowlist
    memory_mb: int = 512
    cpus: float = 1.0
    pids_limit: int = 256
    read_only_rootfs: bool = True
    timeout_s: int = 900


@dataclass
class MemoryCfg:
    provider: str = "hindsight"
    shadow_bank_suffix: str = "-shadow"
    region_max_entries: int = 40
    min_pair_distance: float = 0.55   # cross-domain ideation must pair DISTANT regions
    promote_to_memory_md: str = "staged"   # staged | never
    max_description_similarity: float = 0.85


@dataclass
class Routing:
    source_bank: str = "agent-hermes"
    apply: bool = False
    page_size: int = 100
    max_pages: int = 20
    require_readback: bool = True
    invalidate_source: bool = True


@dataclass
class Reflect:
    enabled: bool = False
    schedule: str = "0 4 * * 1"
    bank: str = "repo-edp-helios"
    budget: str = "low"
    max_tokens: int = 1200
    include_facts: bool = True
    include_tool_calls: bool = False
    exclude_mental_models: bool = True


@dataclass
class Maintenance:
    enabled: bool = False
    schedule: str = "0 3 * * *"
    vacuum: bool = False
    volatile_retention_days: int = 7


@dataclass
class Identity:
    manifest_paths: list[str] = field(default_factory=lambda: [
        "~/.hermes/skills/.bundled_manifest",
        "~/.hermes/skills/.hub/lock.json",
        "~/.hermes/prompts/core.md",
    ])
    on_mismatch: str = "abort_and_rollback"


@dataclass
class Promote:
    mode: str = "pr"                # pr | staging
    repo: str = "~/.hermes/hermes-agent"
    branch_prefix: str = "somnus/"
    canary_sessions: int = 10
    auto_revert_on_guard_trip: bool = True


@dataclass
class Report:
    deliver: str = "local"
    include_rejected: bool = True


@dataclass
class SomnusConfig:
    enabled: bool = False           # opt-in, like the upstream Dreaming proposal
    home: str = "~/.hermes/somnus"
    ideate_top_k: int = 5
    triggers: Triggers = field(default_factory=Triggers)
    guards: Guards = field(default_factory=Guards)
    budget: Budget = field(default_factory=Budget)
    phases: Phases = field(default_factory=Phases)
    bench: Bench = field(default_factory=Bench)
    sandbox: Sandbox = field(default_factory=Sandbox)
    memory: MemoryCfg = field(default_factory=MemoryCfg)
    routing: Routing = field(default_factory=Routing)
    reflect: Reflect = field(default_factory=Reflect)
    maintenance: Maintenance = field(default_factory=Maintenance)
    identity: Identity = field(default_factory=Identity)
    promote: Promote = field(default_factory=Promote)
    report: Report = field(default_factory=Report)

    # -- derived paths ---------------------------------------------------- #

    @property
    def home_path(self) -> Path:
        return Path(os.path.expanduser(self.home))

    @property
    def db_path(self) -> Path:
        return self.home_path / "somnus.db"

    @property
    def ledger_path(self) -> Path:
        return self.home_path / "ledger.jsonl"

    @property
    def lock_path(self) -> Path:
        return self.home_path / "dream.lock"

    @property
    def fixtures_path(self) -> Path:
        return self.home_path / "fixtures"

    @property
    def worktrees_path(self) -> Path:
        return self.home_path / "worktrees"

    @property
    def snapshots_path(self) -> Path:
        return self.home_path / "snapshots"


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #

def _coerce(cls, data: Any):
    """
    Recursively build a dataclass from a plain dict, ignoring unknown keys.

    Field *types* arrive as strings under `from __future__ import annotations`,
    so nested dataclasses are detected from the instantiated default rather than
    from the annotation. Unknown keys are ignored so a newer config.yaml never
    crashes an older plugin.
    """
    if not is_dataclass(cls) or not isinstance(data, dict):
        return data
    obj = cls()
    known = {f.name for f in fields(cls)}
    for key, value in data.items():
        if key not in known:
            continue
        current = getattr(obj, key)
        if is_dataclass(current) and isinstance(value, dict):
            setattr(obj, key, _coerce(type(current), value))
        else:
            setattr(obj, key, value)
    return obj


def load(path: str | os.PathLike | None = None) -> SomnusConfig:
    """
    Load the `somnus:` block from a Hermes config.yaml.

    Missing file, missing block, or missing pyyaml all yield defaults with
    `enabled=False` — Somnus never turns itself on by accident.
    """
    p = Path(os.path.expanduser(str(path or "~/.hermes/config.yaml")))
    if yaml is None or not p.exists():
        return SomnusConfig()
    try:
        doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return SomnusConfig()
    block = doc.get("somnus") or {}
    if not isinstance(block, dict):
        return SomnusConfig()
    return _coerce(SomnusConfig, block)
