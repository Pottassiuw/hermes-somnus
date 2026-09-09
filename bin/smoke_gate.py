#!/usr/bin/env python3
"""Ordinary verifier; NOT a sandbox or a permission boundary.

Run outside the candidate UID/namespace with a protected plan and state directory.
Only stdout's structured result is safe to hand back to a model. Raw child output
is discarded. PASS certifies the listed commands, never completeness of coverage.
No previous PASS is reused: the caller decides whether there is new work.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time

CODES = {"PASS": 0, "FAIL": 1, "BLOCKED": 3, "INCONCLUSIVE": 4}
ENV = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LC_ALL": "C", "LANG": "C",
       "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
       "GIT_TERMINAL_PROMPT": "0"}


class Unavailable(Exception):
    pass


def git(repo: Path, *args: str) -> str:
    try:
        p = subprocess.run(["git", "--no-optional-locks", "-C", str(repo),
                            "-c", "core.hooksPath=/dev/null", *args],
                           env=ENV, stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise Unavailable from None
    if p.returncode:
        raise Unavailable
    return p.stdout.decode("utf-8", errors="strict").strip()


def identity(repo: Path) -> dict:
    if not repo.is_dir() or git(repo, "rev-parse", "--is-inside-work-tree") != "true":
        raise Unavailable
    if Path(git(repo, "rev-parse", "--show-toplevel")).resolve() != repo.resolve():
        raise Unavailable
    if git(repo, "status", "--porcelain=v1", "--untracked-files=all"):
        raise Unavailable
    return {"commit": git(repo, "rev-parse", "--verify", "HEAD"),
            "tree": git(repo, "rev-parse", "--verify", "HEAD^{tree}")}


def sync_directory(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_pass(path: Path, value: dict) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                         dir=path.parent, delete=False) as f:
            temporary = Path(f.name)
            json.dump(value, f, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def command_outcome(argv: list[str], repo: Path, timeout: float) -> tuple[str, int | None]:
    try:
        p = subprocess.Popen(argv, cwd=repo, env=ENV, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
    except OSError:
        return "BLOCKED", None
    try:
        code = p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        p.wait()
        return "INCONCLUSIVE", None
    return ({0: "PASS", 1: "FAIL", 3: "BLOCKED", 4: "INCONCLUSIVE",
             126: "BLOCKED", 127: "BLOCKED"}.get(code, "INCONCLUSIVE"), code)


def validate_plan(plan: dict) -> list[dict]:
    if set(plan) != {"version", "checks"} or plan["version"] != 1:
        raise ValueError
    checks = plan["checks"]
    if not isinstance(checks, list) or not checks:
        raise ValueError
    seen = set()
    for check in checks:
        if set(check) != {"id", "argv", "timeout_seconds"}:
            raise ValueError
        name, argv, timeout = check["id"], check["argv"], check["timeout_seconds"]
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", name):
            raise ValueError
        if name in seen:
            raise ValueError
        seen.add(name)
        if not isinstance(argv, list) or not argv or any(not isinstance(a, str) or not a or "\0" in a for a in argv):
            raise ValueError
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 1800:
            raise ValueError
    return checks


def verify(repo: Path, plan_path: Path, state_path: Path) -> dict:
    result = {"status": "BLOCKED", "reason": "precondition", "checks": []}
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        with (state_path.parent / (state_path.name + ".lock")).open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                result["reason"] = "another_verification_is_running"
                return result
            state_path.unlink(missing_ok=True)
            sync_directory(state_path.parent)
            raw_plan = plan_path.read_bytes()
            checks = validate_plan(json.loads(raw_plan))
            before = identity(repo)
            fingerprint_input = {**before,
                "plan_sha256": hashlib.sha256(raw_plan).hexdigest(),
                "gate_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
            result["identity"] = fingerprint_input
            result["fingerprint"] = hashlib.sha256(json.dumps(fingerprint_input, sort_keys=True).encode()).hexdigest()
            for check in checks:
                status, code = command_outcome(check["argv"], repo, check["timeout_seconds"])
                result["checks"].append({"id": check["id"], "status": status, "exit_code": code})
                if status != "PASS":
                    result.update(status=status, reason="check_did_not_pass")
                    return result
            try:
                after = identity(repo)
            except Unavailable:
                after = None
            if before != after:
                result.update(status="INCONCLUSIVE", reason="candidate_changed_during_verification")
                return result
            result.update(status="PASS", reason="listed_checks_passed", finished_ns=time.time_ns())
            try:
                write_pass(state_path, result)
            except OSError:
                state_path.unlink(missing_ok=True)
                result.update(status="BLOCKED", reason="receipt_not_persisted")
            return result
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, Unavailable):
        result.update(status="BLOCKED", reason="precondition_or_environment_unavailable")
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    args = parser.parse_args()
    result = verify(args.repo, args.plan, args.state)
    print(json.dumps(result, sort_keys=True))
    return CODES[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
