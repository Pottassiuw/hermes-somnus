from __future__ import annotations

from pathlib import Path

from somnus.code_audit import audit_tree


def test_audit_detects_bare_except_duplicate_and_secret_without_values(tmp_path: Path):
    secret_assignment = "API" + "_KEY = 'should not be printed'"
    source = f"""
{secret_assignment}
def duplicate(): pass
def duplicate(): pass
try:
    pass
except:
    pass
"""
    (tmp_path / "sample.py").write_text(source)
    result = audit_tree(tmp_path)
    kinds = {item["kind"] for item in result["findings"]}
    assert {"bare_except", "duplicate_function", "possible_secret_assignment"} <= kinds
    rendered = str(result)
    assert "should not be printed" not in rendered


def test_audit_ignores_virtualenv_and_reports_clean_tree(tmp_path: Path):
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "bad.py").write_text("except:")
    (tmp_path / "clean.py").write_text("def ok():\n    return 1\n")
    result = audit_tree(tmp_path)
    assert result["files_scanned"] == 1
    assert result["status"] == "ok"
