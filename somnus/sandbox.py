"""
somnus.sandbox — three nested isolation layers.

  Layer 3  host            (never written to by a dream)
  Layer 2  git worktree    (bounds repository damage; gives you the diff free)
  Layer 1  ephemeral container (bounds runtime damage)

Autonomy is preserved *inside* the box: the agent may write files, run tests,
install packages, try ten approaches. It simply cannot escape and cannot promote.
That is the entire trick (§2.4.4).
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence

__all__ = ["SandboxError", "docker_argv", "worktree_add", "worktree_remove", "session", "reap"]


class SandboxError(RuntimeError):
    pass


@dataclass(frozen=True)
class SandboxSpec:
    hypothesis_id: str
    worktree: Path
    fixtures_dev: Path
    image: str = "python:3.11-slim"
    network: str = "none"
    memory_mb: int = 512
    cpus: float = 1.0
    pids_limit: int = 256
    read_only_rootfs: bool = True
    timeout_s: int = 900


def docker_argv(spec: SandboxSpec, command: Sequence[str]) -> list[str]:
    """
    Build the `docker run` argv.

    Split out as a pure function so the isolation policy is unit-testable
    without a Docker daemon — the adversarial test in Phase 3 of the roadmap
    asserts against exactly this list.

    Note what is NOT mounted: fixtures/{hold,guard,regress}. That absence is
    IR-2's first and cheapest layer.
    """
    argv: list[str] = [
        "docker", "run", "--rm",
        "--name", f"somnus-{spec.hypothesis_id}",
        "--network", spec.network if spec.network != "llm_only" else "somnus-egress",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--pids-limit", str(spec.pids_limit),
        "--memory", f"{spec.memory_mb}m",
        "--memory-swap", f"{spec.memory_mb}m",
        "--cpus", str(spec.cpus),
        "--user", f"{os.getuid()}:{os.getgid()}",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=128m",
        "-v", f"{spec.worktree}:/work:rw",
        "-v", f"{spec.fixtures_dev}:/fixtures/dev:ro",
        "-w", "/work",
        "-e", "HOME=/tmp",
    ]
    if spec.read_only_rootfs:
        argv.insert(3, "--read-only")
    argv.append(spec.image)
    argv += ["timeout", str(spec.timeout_s), *command]
    return argv


def run(spec: SandboxSpec, command: Sequence[str]) -> subprocess.CompletedProcess:
    argv = docker_argv(spec, command)
    return subprocess.run(argv, capture_output=True, text=True,
                          timeout=spec.timeout_s + 30, check=False)


# --------------------------------------------------------------------------- #
# Worktrees
# --------------------------------------------------------------------------- #

def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, check=False)


def worktree_add(repo: str | os.PathLike, root: str | os.PathLike,
                 hypothesis_id: str, base: str = "HEAD") -> Path:
    repo, root = Path(os.path.expanduser(str(repo))), Path(os.path.expanduser(str(root)))
    wt = root / f"dream-{hypothesis_id}"
    if wt.exists():
        return wt
    root.mkdir(parents=True, exist_ok=True)
    res = _git(repo, "worktree", "add", "-b", f"somnus/dream-{hypothesis_id}", str(wt), base)
    if res.returncode != 0:
        raise SandboxError(f"git worktree add failed: {res.stderr.strip()}")
    return wt


def worktree_remove(repo: str | os.PathLike, wt: str | os.PathLike,
                    delete_branch: bool = True) -> None:
    repo, wt = Path(os.path.expanduser(str(repo))), Path(os.path.expanduser(str(wt)))
    _git(repo, "worktree", "remove", "--force", str(wt))
    if wt.exists():
        shutil.rmtree(wt, ignore_errors=True)
    if delete_branch:
        _git(repo, "branch", "-D", f"somnus/{wt.name}")


def diff(repo: str | os.PathLike, wt: str | os.PathLike) -> str:
    """The candidate's full diff, for the evidence bundle in the PR body."""
    res = _git(Path(os.path.expanduser(str(wt))), "diff", "HEAD")
    return res.stdout


@contextmanager
def session(cfg, hypothesis_id: str) -> Iterator[SandboxSpec]:
    """
    Create worktree + session marker, yield the spec, and always tear down.

    The marker file is what `hooks.pre_tool_call` keys on to decide that the
    permission ceiling applies. Its removal in `finally` is the reason the
    ceiling cannot leak into the user's next interactive session.
    """
    wt = worktree_add(cfg.promote.repo, cfg.worktrees_path, hypothesis_id)
    markers = cfg.home_path / "sessions"
    markers.mkdir(parents=True, exist_ok=True)
    marker = markers / f"{hypothesis_id}.dream"
    marker.write_text("1", encoding="utf-8")

    spec = SandboxSpec(
        hypothesis_id=hypothesis_id,
        worktree=wt,
        fixtures_dev=cfg.fixtures_path / "dev",
        image=cfg.sandbox.image,
        network=cfg.sandbox.network,
        memory_mb=cfg.sandbox.memory_mb,
        cpus=cfg.sandbox.cpus,
        pids_limit=cfg.sandbox.pids_limit,
        read_only_rootfs=cfg.sandbox.read_only_rootfs,
        timeout_s=cfg.sandbox.timeout_s,
    )
    try:
        yield spec
    finally:
        marker.unlink(missing_ok=True)
        subprocess.run(["docker", "kill", f"somnus-{hypothesis_id}"],
                       capture_output=True, check=False)


def reap(cfg) -> list[str]:
    """
    Remove stale worktrees and branches. Called in the orchestrator's `finally`
    and again by a weekly cron, because an aborted night leaves debris.
    """
    removed: list[str] = []
    root = cfg.worktrees_path
    if not root.exists():
        return removed
    for wt in sorted(p for p in root.iterdir() if p.is_dir()):
        try:
            worktree_remove(cfg.promote.repo, wt)
            removed.append(wt.name)
        except Exception:
            shutil.rmtree(wt, ignore_errors=True)
            removed.append(wt.name)
    return removed
