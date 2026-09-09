#!/usr/bin/env python3
"""Deployment acceptance, run by the operator outside the executor.

Missing prerequisites exit 3 (BLOCKED); no simulated deployment PASS.
All canaries are synthetic. Namespace mode requires a disposable labelled lab.
Budget mode only POSTs after the provider reports an exhausted finite key cap.
No returned error body, key, or subprocess stderr is printed.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import uuid


class Blocked(Exception):
    pass


def run(argv, *, timeout=30, data=None):
    try:
        return subprocess.run(argv, input=data, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise Blocked from None


def namespace(target):
    if not shutil.which("docker") or not shutil.which("ssh"):
        raise Blocked
    p = run(["docker", "inspect", "hermes-author"])
    if p.returncode:
        raise Blocked
    actual = json.loads(p.stdout)[0]
    if actual["Config"].get("Labels", {}).get("hermes.acceptance") != "true":
        raise Blocked
    assert actual["HostConfig"]["NetworkMode"] == "none"
    assert actual["HostConfig"]["ReadonlyRootfs"] is True
    assert actual["HostConfig"].get("Privileged") is False
    assert "ALL" in [c.upper() for c in actual["HostConfig"].get("CapDrop", [])]
    assert not actual["HostConfig"].get("CapAdd")
    assert any(s in ("no-new-privileges", "no-new-privileges=true")
               for s in actual["HostConfig"].get("SecurityOpt", []))
    assert actual["HostConfig"].get("PidMode") != "host"
    assert actual["HostConfig"].get("IpcMode") != "host"
    mounts = actual.get("Mounts", [])
    assert {m["Destination"] for m in mounts} <= {"/work", "/tmp"}
    assert any(m["Destination"] == "/work" and m["RW"] for m in mounts)
    # The fixed authorized-key command must be tested through SSH, not docker exec.
    command = r'''python3 - <<'PY'
from pathlib import Path
import os, socket
assert os.getuid() == 65532
for path in ['/var/run/docker.sock','/run/docker.sock','/run/credentials',
             '/etc/hermes/authority.json','/root/.ssh','/srv/hermes/receipts']:
    assert not Path(path).exists(), path
assert set(os.listdir('/sys/class/net')) == {'lo'}
try:
    os.setuid(0)
except PermissionError:
    pass
else:
    raise AssertionError('became root')
try:
    Path('/authority-attempt').write_text('changed')
except OSError:
    pass
else:
    raise AssertionError('wrote outside work')
Path('/work/acceptance-added').write_text('candidate-only')
PY
# somnus-sandbox.sh
'''
    p = run(["ssh", "-T", "-o", "BatchMode=yes", target, command])
    assert p.returncode == 0
    # Independent reader checks the actual artifact, not the shell's exit alone.
    host_work = Path(next(m["Source"] for m in mounts if m["Destination"] == "/work"))
    assert (host_work / "acceptance-added").read_text() == "candidate-only"
    return {"namespace": "PASS", "limit": "disposable lab only; no provider or production restore proved"}


def budget(key_file, model):
    if not key_file.is_file() or key_file.stat().st_mode & 0o077:
        raise Blocked
    key = key_file.read_text().strip()
    if not key:
        raise Blocked
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    def key_state():
        try:
            req = urllib.request.Request("https://openrouter.ai/api/v1/key", headers=headers)
            with urllib.request.urlopen(req, timeout=20) as response:
                data = json.load(response)["data"]
            return data
        except (OSError, ValueError, KeyError):
            raise Blocked from None
    before = key_state()
    for field in ("limit", "limit_remaining", "usage"):
        value = before.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise Blocked
    if before.get("limit") is None or before.get("limit_remaining") is None or before["limit_remaining"] > 0:
        raise Blocked
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": "Reply OK."}],
                       "max_tokens": 1}).encode()
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            response.read(1)
        raise AssertionError("exhausted cap accepted a request")
    except urllib.error.HTTPError as exc:
        assert exc.code == 402, "provider did not demonstrate a credit-limit rejection"
    except OSError:
        raise Blocked from None
    after = key_state()
    if not isinstance(after.get("usage"), (int, float)):
        raise Blocked
    assert after.get("usage") == before.get("usage")
    return {"provider_cap": "PASS", "limit": "direct exhausted-key request only; reconcile delayed usage and the real harness separately"}


def canary(target, artifact):
    if not shutil.which("hermes") or not shutil.which("ssh") or not artifact.parent.is_dir():
        raise Blocked
    # The caller must have provisioned the protected SSH profile; no local fallback.
    if os.environ.get("TERMINAL_SSH_HOST") is None or os.environ.get("TERMINAL_SSH_USER") is None:
        raise Blocked
    namespace(target)
    backend = run(["hermes", "config", "get", "terminal.backend"])
    if backend.returncode or backend.stdout.strip().strip(b'"\'') != b"ssh":
        raise Blocked
    nonce = uuid.uuid4().hex  # Not a credential.
    content = "HERMES_ACCEPTANCE_" + nonce
    prompt = ("Use the terminal tool to write exactly this text, with no newline, to "
              "/work/acceptance-delivery.txt: " + content + ". Do not perform any other task.")
    # Feed plain text through stdin; neither shell interpolation nor a new Runtime.
    p = run(["hermes", "chat", "--toolsets", "terminal", "--query-file", "-"],
            timeout=180, data=prompt.encode())
    if p.returncode:
        raise Blocked
    # artifact is the independently known bind-mounted /work path, not a path
    # or hash returned by the model. The operator supplies it from docker inspect.
    assert artifact.read_text() == content
    return {"real_harness_artifact": "PASS", "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            "limit": "generation only; publication and recovery are separate acceptance tests"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("namespace")
    p.add_argument("--ssh-target", required=True)
    p = sub.add_parser("budget")
    p.add_argument("--key-file", type=Path, required=True)
    p.add_argument("--model", required=True)
    p = sub.add_parser("canary")
    p.add_argument("--artifact", type=Path, required=True)
    p.add_argument("--ssh-target", required=True)
    args = parser.parse_args()
    try:
        if args.mode == "namespace": result = namespace(args.ssh_target)
        elif args.mode == "budget": result = budget(args.key_file, args.model)
        else: result = canary(args.ssh_target, args.artifact)
        print(json.dumps({"status": "PASS", "observations": result}, sort_keys=True))
        return 0
    except Blocked:
        print('{"status":"BLOCKED","reason":"deployment_prerequisite_or_service_unavailable"}')
        return 3
    except (AssertionError, OSError, ValueError, KeyError, IndexError):
        print('{"status":"FAIL","reason":"observable_property_not_satisfied"}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
