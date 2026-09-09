"""Deterministic static checks used by the Argus cron gate."""
from __future__ import annotations

import ast
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Finding:
    kind: str
    path: str
    line: int
    detail: str
    severity: str = "warning"

    def to_dict(self) -> dict:
        return asdict(self)


_SECRET_ASSIGNMENT = re.compile(r"(?i)\b(?:api[_-]?key|token|password|secret|connection[_ -]?string)\b\s*[:=]")


def _scope_duplicates(nodes: list[ast.AST], path: Path, findings: list[Finding], scope: str) -> None:
    names: dict[str, list[int]] = {}
    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.setdefault(node.name, []).append(node.lineno)
    for name, lines in names.items():
        if len(lines) > 1:
            findings.append(Finding("duplicate_function", str(path), lines[0], f"{scope}:{name} at lines {','.join(map(str, lines))}"))


def audit_python_file(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [Finding("syntax_error", str(path), exc.lineno or 0, "Python parsing failed", "error")]
    _scope_duplicates(tree.body, path, findings, "module")
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            _scope_duplicates(list(node.body), path, findings, getattr(node, "name", "scope"))
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                findings.append(Finding("bare_except", str(path), node.lineno, "bare except masks the error", "error"))
            elif isinstance(node.type, ast.Name) and node.type.id == "Exception":
                findings.append(Finding("broad_except", str(path), node.lineno, "except Exception requires justification"))
    for number, line in enumerate(source.splitlines(), 1):
        if _SECRET_ASSIGNMENT.search(line) and "os.environ" not in line and "getenv" not in line and "[REDACTED]" not in line:
            findings.append(Finding("possible_secret_assignment", str(path), number, "credential-like assignment; value omitted", "error"))
    return findings


def audit_tree(root: str | Path) -> dict:
    base = Path(root).expanduser().resolve()
    findings: list[Finding] = []
    files = 0
    for path in sorted(base.rglob("*.py")):
        if any(part in {".git", ".venv", "node_modules", "__pycache__"} for part in path.parts):
            continue
        files += 1
        findings.extend(audit_python_file(path))
    errors = sum(item.severity == "error" for item in findings)
    return {
        "root": str(base),
        "files_scanned": files,
        "finding_count": len(findings),
        "error_count": errors,
        "findings": [item.to_dict() for item in findings],
        "status": "fail" if errors else ("warn" if findings else "ok"),
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=None)
    args = parser.parse_args()
    root = args.root or __import__("os").environ.get("HELIOS_REPO", ".")
    result = audit_tree(root)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if result["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
