import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
import smoke_gate as gate


class SmokeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        (self.repo / "tracked.txt").write_text("original\n")
        self.git("add", ".")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "baseline")
        self.plan = self.root / "plan.json"
        self.state = self.root / "receipts" / "pass.json"

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def set_plan(self, code="pass", timeout=10):
        self.plan.write_text(json.dumps({"version": 1, "checks": [
            {"id": "behavior", "argv": [sys.executable, "-c", code],
             "timeout_seconds": timeout}]}))

    def run_gate(self):
        return gate.verify(self.repo, self.plan, self.state)

    def test_missing_repository_never_passes(self):
        self.set_plan()
        result = gate.verify(self.root / "absent", self.plan, self.state)
        self.assertEqual("BLOCKED", result["status"])
        self.assertFalse(self.state.exists())

    def test_blocked_retry_really_executes_again(self):
        counter = self.root / "counter"
        code = ("from pathlib import Path; import sys; p=Path(" + repr(str(counter)) + "); "
                "p.write_text(p.read_text()+'x' if p.exists() else 'x'); sys.exit(3)")
        self.set_plan(code)
        self.assertEqual("BLOCKED", self.run_gate()["status"])
        self.assertEqual("BLOCKED", self.run_gate()["status"])
        self.assertEqual("xx", counter.read_text())
        self.assertFalse(self.state.exists())

    def test_pass_receipt_is_written_after_observed_effect(self):
        effect = self.root / "effect"
        self.set_plan("from pathlib import Path; Path(" + repr(str(effect)) + ").write_text('executed')")
        result = self.run_gate()
        self.assertEqual("executed", effect.read_text())
        self.assertEqual("PASS", result["status"])
        self.assertEqual(result, json.loads(self.state.read_text()))
        self.assertEqual(self.git("rev-parse", "HEAD"), result["identity"]["commit"])

    def test_failed_attempt_invalidates_previous_pass_receipt(self):
        self.set_plan()
        self.assertEqual("PASS", self.run_gate()["status"])
        self.set_plan("raise SystemExit(1)")
        self.assertEqual("FAIL", self.run_gate()["status"])
        self.assertFalse(self.state.exists())

    def test_missing_executable_is_blocked(self):
        self.plan.write_text(json.dumps({"version": 1, "checks": [{"id": "missing",
            "argv": [str(self.root / "not-installed")], "timeout_seconds": 1}]}))
        self.assertEqual("BLOCKED", self.run_gate()["status"])
        self.assertFalse(self.state.exists())

    def test_timeout_is_inconclusive(self):
        self.set_plan("import time; time.sleep(60)", timeout=0.03)
        self.assertEqual("INCONCLUSIVE", self.run_gate()["status"])
        self.assertFalse(self.state.exists())

    def test_source_modified_during_check_is_not_certified(self):
        self.set_plan("from pathlib import Path; Path('tracked.txt').write_text('changed')")
        self.assertEqual("INCONCLUSIVE", self.run_gate()["status"])
        self.assertEqual("changed", (self.repo / "tracked.txt").read_text())
        self.assertFalse(self.state.exists())

    def test_dirty_input_is_blocked_even_if_same_number_of_files(self):
        self.set_plan()
        (self.repo / "tracked.txt").write_text("another value\n")
        self.assertEqual("BLOCKED", self.run_gate()["status"])
        self.assertFalse(self.state.exists())

    def test_linked_git_worktree_is_supported(self):
        worktree = self.root / "linked"
        self.git("worktree", "add", "--detach", str(worktree), "HEAD")
        self.repo = worktree
        self.assertTrue((worktree / ".git").is_file())
        self.set_plan()
        self.assertEqual("PASS", self.run_gate()["status"])

    def test_empty_or_duplicate_check_plan_does_not_pass(self):
        self.plan.write_text('{"version":1,"checks":[]}')
        self.assertEqual("BLOCKED", self.run_gate()["status"])
        self.set_plan()
        plan = json.loads(self.plan.read_text())
        plan["checks"] *= 20
        self.plan.write_text(json.dumps(plan))
        self.assertEqual("BLOCKED", self.run_gate()["status"])
        self.assertFalse(self.state.exists())

    def test_concurrent_verification_does_not_claim_pass(self):
        self.set_plan()
        self.state.parent.mkdir()
        with (self.state.parent / (self.state.name + ".lock")).open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual("BLOCKED", self.run_gate()["status"])

    def test_raw_child_errors_and_inherited_secrets_are_not_emitted(self):
        self.set_plan("import sys; print('SYNTHETIC_NOT_A_KEY'); sys.exit(1)")
        p = subprocess.run([sys.executable, str(Path(gate.__file__)), "--repo", str(self.repo),
                            "--plan", str(self.plan), "--state", str(self.state)],
                           capture_output=True, text=True)
        self.assertEqual(1, p.returncode)
        self.assertNotIn("SYNTHETIC_NOT_A_KEY", p.stdout + p.stderr)
        self.set_plan("import os; assert 'HERMES_SYNTHETIC_SECRET' not in os.environ")
        p = subprocess.run([sys.executable, str(Path(gate.__file__)), "--repo", str(self.repo),
                            "--plan", str(self.plan), "--state", str(self.state)],
                           env={**os.environ, "HERMES_SYNTHETIC_SECRET": "SYNTHETIC_NOT_A_KEY"},
                           capture_output=True, text=True)
        self.assertEqual(0, p.returncode)


if __name__ == "__main__":
    unittest.main()
