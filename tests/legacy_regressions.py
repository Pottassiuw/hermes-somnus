"""Eight RED acceptance regressions against the supplied Somnus snapshot.

Usage: python tests/legacy_regressions.py --source /path/to/extracted/bundle
Expected: seven failures and one BLOCKED integration test. No real credentials,
provider calls or host mutations.
The old runtime's external interactions are represented by instrumented fixtures;
assertions inspect their effects, not the cycle's self-reported status.
"""
import argparse
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

parser = argparse.ArgumentParser()
parser.add_argument("--source", required=True, type=Path)
args, remaining = parser.parse_known_args()
SOURCE = args.source.resolve()
sys.path.insert(0, str(SOURCE))
from somnus import bench, config, daemon, guards, hooks, state, triage
from somnus.memory_router import Fact, MemoryRouter, RouteLedger


class SettledDefects(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_01_command_substring_cannot_grant_host_write(self):
        identity = self.root / "authority"
        identity.write_text("before")
        cfg = config.SomnusConfig(home=str(self.root / "state"))
        marker = cfg.home_path / "sessions" / "test.dream"
        marker.parent.mkdir(parents=True)
        marker.write_text("1")
        command = "printf changed > " + shlex.quote(str(identity)) + " # somnus-sandbox.sh"
        verdict = hooks.make_pre_tool_call(cfg)("terminal", {"command": command}, task_id="test")
        if verdict is None:  # Actual meaning of None: host terminal proceeds.
            subprocess.run(["bash", "-c", command], check=True)
        self.assertEqual("before", identity.read_text())

    def test_02_rollback_restores_identity_and_removes_new_files(self):
        identity = self.root / "core.md"
        identity.write_text("before")
        cfg = config.SomnusConfig(enabled=True, home=str(self.root / "cycle"))
        cfg.identity.manifest_paths = [str(identity)]
        staging = cfg.home_path / "staging"
        staging.mkdir(parents=True)
        (staging / "old").write_text("original")
        class Tamper:
            def recent_turns(self):
                identity.write_text("changed")
                (staging / "added").write_text("unexpected")
                return []
            def memory_region(self): return []
        store = state.Store(cfg.db_path)
        self.addCleanup(store.close)
        daemon.dream_cycle(cfg, Tamper(), host=guards.FakeHost(), store=store, now_hour=3)
        self.assertEqual(("before", False), (identity.read_text(), (staging / "added").exists()))

    def test_03_no_source_lost_without_exact_preservation(self):
        originals = {str(i): "helios frontend " + chr(65+i)*6500 for i in range(3)}
        class MemoryService:
            def __init__(self): self.source = dict(originals); self.target = ""; self.doc = ""
            def retain_digest(self, bank, content, *, context, document_id):
                self.target, self.doc = content, document_id
            def list_memories(self, bank, **kwargs):
                return [Fact("target", "unrelated text", document_id=self.doc)]
            def invalidate(self, bank, memory_id, **kwargs): self.source.pop(memory_id)
        service = MemoryService()
        ledger = RouteLedger(self.root / "ledger.db")
        self.addCleanup(ledger.close)
        MemoryRouter(service, ledger, apply=True, max_batch=5).route(
            "agent-hermes", [Fact(k, v) for k, v in originals.items()])
        self.assertTrue(all(k in service.source or v in service.target for k, v in originals.items()))

    def test_04_raw_credential_does_not_enter_model_argument(self):
        captured = []
        secret = "SYNTHETIC_NEVER_A_REAL_CREDENTIAL"
        triage.extract([triage.Turn("s", 1, "2026-09-09T00:00:00Z", "tool",
            content=json.dumps({"api_key": secret}), ok=False)],
            lambda prompt: captured.append(prompt) or "{}")
        self.assertTrue(captured)
        self.assertNotIn(secret, captured[0])

    def test_05_exhausted_budget_prevents_build_side_effect(self):
        cfg = config.SomnusConfig(enabled=True, home=str(self.root / "budget"))
        cfg.budget.max_llm_calls = 0
        calls = []
        record = triage.FailureRecord("sig", "trigger", "error", "consequence")
        class Runtime:
            def recent_turns(self): return []
            def memory_region(self): return []
            def baseline_reproduces(self, h): return True
            def build_candidate(self, h): calls.append("paid_build_request"); return object()
            def gate_a(self, c): return False, "fixture ends after paid request"
        store = state.Store(cfg.db_path)
        self.addCleanup(store.close)
        # An already established failure removes incidental triage-model traffic.
        with patch.object(triage, "extract", return_value=[record]):
            daemon.dream_cycle(cfg, Runtime(), host=guards.FakeHost(), store=store, now_hour=3)
        self.assertEqual([], calls)

    def test_06_blocked_smoke_cannot_become_pass_on_retry(self):
        repo = self.root / "repo"
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test", "-c",
            "user.email=test@example.invalid", "commit", "--allow-empty", "-qm", "baseline"], check=True)
        subprocess.run(["git", "-C", str(repo), "update-ref", "refs/remotes/origin/develop", "HEAD"], check=True)
        scripts = self.root / "scripts"
        scripts.mkdir()
        for name in ["helios-smoke-gated.sh", "helios-smoke.sh", "helios-precheck.sh"]:
            shutil.copyfile(SOURCE / "scripts" / name, scripts / name)
            (scripts / name).chmod(0o700)
        import os
        env = {**os.environ, "HERMES_HOME": str(self.root / "home"), "HELIOS_REPO": str(repo),
            "HELIOS_PRECHECK_STATE": str(self.root / "fingerprint"),
            "SOMNUS_REPORT_DIR": str(self.root / "reports"), "HELIOS_BASE_URL": "",
            "HELIOS_PYTHON": str(self.root / "python-not-installed")}
        outcomes = [subprocess.run(["bash", str(scripts / "helios-smoke-gated.sh")],
            env=env, capture_output=True).returncode for _ in range(2)]
        self.assertEqual([3, 3], outcomes)

    def test_07_duplicate_case_does_not_supply_twenty_independent_results(self):
        cfg = config.SomnusConfig(enabled=True, home=str(self.root / "duplicates"))
        delivered = self.root / "staged-candidate"
        record = triage.FailureRecord("sig", "trigger", "error", "consequence")
        class Runtime:
            def recent_turns(self): return []
            def memory_region(self): return []
            def baseline_reproduces(self, h): return True
            def build_candidate(self, h): return object()
            def gate_a(self, c): return True, "fixture"
            def run_fixtures(self, side, c):
                passed = side == "candidate"
                return [bench.CaseResult("only-one", "hold", passed, float(passed))] * 20
            def stage(self, *unused):
                delivered.write_text("published by the real daemon stage path")
                return str(delivered)
        store = state.Store(cfg.db_path)
        self.addCleanup(store.close)
        with patch.object(triage, "extract", return_value=[record]):
            daemon.dream_cycle(cfg, Runtime(), host=guards.FakeHost(), store=store, now_hour=3)
        self.assertFalse(delivered.exists())

    def test_08_module_exit_is_not_an_implemented_production_delivery(self):
        self.skipTest("BLOCKED: no production Runtime/entrypoint to exercise; run acceptance.py canary against the installed stock harness")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0], *remaining])
