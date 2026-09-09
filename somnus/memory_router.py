"""Deterministic Hindsight routing with an auditable, idempotent ledger.

Normal Hermes Hindsight writes use one fixed bank. This module is the explicit
bridge for domain-scoped dual-write: classify, redact, retain, read back, then
invalidate the source. The default caller mode is dry-run.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

__all__ = ["BankRoute", "Fact", "HindsightClient", "MemoryRouter", "RouteDecision", "RouteLedger", "classify_fact", "fact_from_payload", "make_decisions", "redact_sensitive"]

SECRET_PATTERNS = (
    re.compile(r"(?i)(\b(?:api[_ -]?key|access[_ -]?token|auth(?:orization)?|password|passwd|secret|client[_ -]?secret|connection[_ -]?string)\b\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(\bbearer\s+)([^\s,;]+)"),
    re.compile(r"(?i)\b(?:postgres(?:ql)?|mysql|mssql|redis)://[^\s\"']+"),
)

@dataclass(frozen=True)
class BankRoute:
    bank_id: str
    reason: str
    confidence: str = "high"
    needs_review: bool = False

@dataclass(frozen=True)
class Fact:
    memory_id: str
    text: str
    fact_type: str = "world"
    state: str = "valid"
    context: str = ""
    document_id: str = ""
    occurred_at: str = ""
    raw: Mapping[str, Any] | None = None

@dataclass(frozen=True)
class RouteDecision:
    source_bank: str
    source_memory_id: str
    target: BankRoute
    content: str
    content_hash: str

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def redact_sensitive(value: str) -> str:
    text = str(value)
    for pattern in SECRET_PATTERNS:
        if pattern.groups >= 2:
            text = pattern.sub(lambda m: f"{m.group(1)}[REDACTED]", text)
        else:
            text = pattern.sub("[REDACTED_CONNECTION_STRING]", text)
    return text

def _stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def _keywords(text: str) -> set[str]:
    normalized = re.sub(r"[^a-z0-9à-ÿ]+", " ", text.casefold())
    return set(normalized.split())

def classify_fact(text: str, *, explicit_bank: str = "") -> BankRoute:
    """Classify with an allowlisted vocabulary; ambiguity is never guessed."""
    if explicit_bank:
        if explicit_bank not in {"agent-hermes", "repo-edp-helios", "ops-infra"}:
            return BankRoute(explicit_bank, "explicit bank", "low", True)
        return BankRoute(explicit_bank, "explicit bank")
    words = _keywords(text)
    helios = {"edp-helios", "helios", "github", "pull", "request", "pr", "commit", "branch", "ci", "frontend", "backend", "carteira", "excel", "planilha", "postergadas", "metas", "dashboard", "vite", "vitest", "pytest"}
    infra = {"docker", "container", "raspberry", "pi", "cloudflare", "tunnel", "network", "rede", "systemd", "sqlite", "hindsight", "somnus", "proxy", "zscaler", "hostinger", "digitalocean"}
    governance = {"hermes", "panteão", "governança", "governance", "perfil", "agent-hermes", "preferência", "preference", "identidade", "identity"}
    scores = {"repo-edp-helios": len(words & helios), "ops-infra": len(words & infra), "agent-hermes": len(words & governance)}
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    bank, best = ordered[0]
    second = ordered[1][1]
    if best == 0:
        return BankRoute("agent-hermes", "no domain signal", "low", True)
    if best == second:
        return BankRoute("agent-hermes", "ambiguous domain", "low", True)
    return BankRoute(bank, f"keyword score {best}", "high" if best >= second + 2 else "medium")

def fact_from_payload(raw: Mapping[str, Any]) -> Fact:
    metadata = raw.get("metadata") if isinstance(raw.get("metadata"), Mapping) else {}
    return Fact(
        memory_id=str(raw.get("id") or raw.get("memory_id") or ""),
        text=str(raw.get("text") or raw.get("content") or ""),
        fact_type=str(raw.get("fact_type") or raw.get("type") or "world"),
        state=str(raw.get("state") or "valid"),
        context=str(raw.get("context") or metadata.get("context") or ""),
        document_id=str(raw.get("document_id") or metadata.get("document_id") or ""),
        occurred_at=str(raw.get("occurred_at") or raw.get("timestamp") or ""),
        raw=raw,
    )

class HindsightTransport(Protocol):
    def request(self, method: str, path: str, *, query: Mapping[str, Any] | None = None, payload: Mapping[str, Any] | None = None) -> Any: ...

class HindsightClient:
    """Stdlib-only Hindsight HTTP client. Error bodies are never logged."""
    def __init__(self, base_url: str, api_key: str = "", timeout: float = 90.0) -> None:
        self.base_url, self.api_key, self.timeout = base_url.rstrip("/"), api_key, timeout
    def request(self, method: str, path: str, *, query: Mapping[str, Any] | None = None, payload: Mapping[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        if query:
            url += "?" + urlencode({k: v for k, v in query.items() if v is not None})
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        try:
            with urlopen(Request(url, data=body, headers=headers, method=method.upper()), timeout=self.timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            raise RuntimeError(f"Hindsight HTTP {exc.code} for {method} {path}") from exc
        except URLError as exc:
            raise RuntimeError(f"Hindsight unavailable for {method} {path}: {exc.reason}") from exc
        if not raw.strip():
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Hindsight returned non-JSON for {method} {path}") from exc
    def list_memories(self, bank_id: str, *, limit: int = 100, offset: int = 0) -> list[Fact]:
        payload = self.request("GET", f"/v1/default/banks/{bank_id}/memories/list", query={"limit": limit, "offset": offset})
        items = payload if isinstance(payload, list) else (payload.get("memories") or payload.get("items") or payload.get("data") or []) if isinstance(payload, Mapping) else []
        return [fact_from_payload(item) for item in items if isinstance(item, Mapping)]
    def retain_digest(self, bank_id: str, content: str, *, context: str, document_id: str, timestamp: str = "") -> Mapping[str, Any]:
        item = {"content": redact_sensitive(content), "context": redact_sensitive(context), "document_id": document_id}
        if timestamp:
            item["timestamp"] = timestamp
        result = self.request("POST", f"/v1/default/banks/{bank_id}/memories", payload={"async": False, "items": [item]})
        if not isinstance(result, Mapping) or result.get("success") is False:
            raise RuntimeError("Hindsight retain did not confirm success")
        return result
    def invalidate(self, bank_id: str, memory_id: str, *, reason: str) -> Mapping[str, Any]:
        result = self.request("PATCH", f"/v1/default/banks/{bank_id}/memories/{memory_id}", payload={"state": "invalidated", "reason": redact_sensitive(reason)})
        if isinstance(result, Mapping) and result.get("success") is False:
            raise RuntimeError("Hindsight invalidation was rejected")
        return result if isinstance(result, Mapping) else {}
    def stats(self, bank_id: str) -> Mapping[str, Any]:
        result = self.request("GET", f"/v1/default/banks/{bank_id}/stats")
        return result if isinstance(result, Mapping) else {}

class RouteLedger:
    """SQLite journal for idempotency and post-write verification."""
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS memory_routes (
      source_bank TEXT NOT NULL, source_memory_id TEXT NOT NULL, target_bank TEXT NOT NULL,
      content_hash TEXT NOT NULL, status TEXT NOT NULL, document_id TEXT NOT NULL,
      target_verified INTEGER NOT NULL DEFAULT 0, source_invalidated INTEGER NOT NULL DEFAULT 0,
      attempts INTEGER NOT NULL DEFAULT 0, reason TEXT NOT NULL DEFAULT '', last_error TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      PRIMARY KEY (source_bank, source_memory_id, target_bank, content_hash)
    );
    CREATE INDEX IF NOT EXISTS idx_memory_routes_status ON memory_routes(status);
    """
    def __init__(self, path: str | os.PathLike) -> None:
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL"); self.db.execute("PRAGMA busy_timeout=30000"); self.db.executescript(self.SCHEMA)
    def close(self) -> None: self.db.close()
    def get(self, decision: RouteDecision) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM memory_routes WHERE source_bank=? AND source_memory_id=? AND target_bank=? AND content_hash=?", (decision.source_bank, decision.source_memory_id, decision.target.bank_id, decision.content_hash)).fetchone()
    def begin(self, decision: RouteDecision) -> bool:
        now = _now(); self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.get(decision)
            if row and row["source_invalidated"]:
                self.db.execute("COMMIT"); return False
            if row:
                self.db.execute("UPDATE memory_routes SET status='pending', attempts=attempts+1, updated_at=?, last_error='' WHERE source_bank=? AND source_memory_id=? AND target_bank=? AND content_hash=?", (now, decision.source_bank, decision.source_memory_id, decision.target.bank_id, decision.content_hash))
            else:
                self.db.execute("INSERT INTO memory_routes (source_bank, source_memory_id, target_bank, content_hash, status, document_id, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)", (decision.source_bank, decision.source_memory_id, decision.target.bank_id, decision.content_hash, "pending", f"somnus-route-{decision.content_hash[:24]}", now, now))
            self.db.execute("COMMIT"); return True
        except Exception:
            self.db.execute("ROLLBACK"); raise
    def document_id(self, decision: RouteDecision) -> str:
        row = self.get(decision)
        if not row: raise RuntimeError("route is not registered in ledger")
        return str(row["document_id"])
    def set_document_id(self, decisions: Iterable[RouteDecision], document_id: str) -> None:
        for decision in decisions:
            self.db.execute("UPDATE memory_routes SET document_id=?, updated_at=? WHERE source_bank=? AND source_memory_id=? AND target_bank=? AND content_hash=?", (document_id, _now(), decision.source_bank, decision.source_memory_id, decision.target.bank_id, decision.content_hash))

    def needs_retain(self, decision: RouteDecision) -> bool:
        row = self.get(decision)
        return not row or not bool(row["target_verified"])

    def mark_verified(self, decision: RouteDecision) -> None:
        self.db.execute("UPDATE memory_routes SET status='verified', target_verified=1, updated_at=? WHERE source_bank=? AND source_memory_id=? AND target_bank=? AND content_hash=?", (_now(), decision.source_bank, decision.source_memory_id, decision.target.bank_id, decision.content_hash))
    def mark_invalidated(self, decision: RouteDecision) -> None:
        self.db.execute("UPDATE memory_routes SET status='complete', source_invalidated=1, updated_at=? WHERE source_bank=? AND source_memory_id=? AND target_bank=? AND content_hash=?", (_now(), decision.source_bank, decision.source_memory_id, decision.target.bank_id, decision.content_hash))
    def mark_error(self, decision: RouteDecision, error: str) -> None:
        self.db.execute("UPDATE memory_routes SET status='error', last_error=?, updated_at=? WHERE source_bank=? AND source_memory_id=? AND target_bank=? AND content_hash=? AND source_invalidated=0", (redact_sensitive(error)[:1000], _now(), decision.source_bank, decision.source_memory_id, decision.target.bank_id, decision.content_hash))

def make_decisions(source_bank: str, facts: Iterable[Fact]) -> list[RouteDecision]:
    decisions = []
    for fact in facts:
        if not fact.memory_id or not fact.text or fact.state != "valid" or fact.fact_type == "observation":
            continue
        content = redact_sensitive(fact.text).strip(); target = classify_fact(content)
        if target.needs_review or target.bank_id == source_bank: continue
        decisions.append(RouteDecision(source_bank, fact.memory_id, target, content, _stable_hash(f"{target.bank_id}\0{content}")))
    return decisions

def digest(decisions: Iterable[RouteDecision], *, max_chars: int = 12000) -> str:
    grouped: dict[str, list[str]] = {}
    for item in decisions: grouped.setdefault(item.target.bank_id, []).append(item.content)
    blocks = []
    for bank_id in sorted(grouped):
        unique = list(dict.fromkeys(grouped[bank_id])); blocks.append(f"Domain: {bank_id}\n" + "\n".join(f"- {text}" for text in unique))
    return "\n\n".join(blocks)[:max_chars]

class MemoryRouter:
    def __init__(self, client: HindsightClient, ledger: RouteLedger, *, apply: bool = False, max_batch: int = 25) -> None:
        if not 1 <= max_batch <= 50:
            raise ValueError("max_batch must be between 1 and 50")
        self.client, self.ledger, self.apply, self.max_batch = client, ledger, apply, max_batch
    def route(self, source_bank: str, facts: Iterable[Fact]) -> dict[str, Any]:
        decisions = make_decisions(source_bank, facts)
        report = {"source_bank": source_bank, "dry_run": not self.apply, "planned": len(decisions), "verified": 0, "invalidated": 0, "skipped": 0, "errors": [], "banks": sorted({d.target.bank_id for d in decisions})}
        grouped: dict[str, list[RouteDecision]] = {}
        for decision in decisions: grouped.setdefault(decision.target.bank_id, []).append(decision)
        report["batch_size"] = self.max_batch
        for target_bank, batch in grouped.items():
            if not self.apply: continue
            for start in range(0, len(batch), self.max_batch):
                chunk = batch[start:start + self.max_batch]
                plan = [d for d in chunk if self.ledger.begin(d)]
                if not plan:
                    report["skipped"] += len(chunk)
                    continue
                first = plan[0]; document_id = self.ledger.document_id(first)
                self.ledger.set_document_id(plan, document_id)
                try:
                    if any(self.ledger.needs_retain(decision) for decision in plan):
                        self.client.retain_digest(target_bank, digest(plan), context=f"Somnus routed synthesis from {source_bank} to {target_bank}", document_id=document_id)
                    target_facts = self.client.list_memories(target_bank, limit=500)
                    if not any(f.document_id == document_id or document_id in f.text for f in target_facts):
                        raise RuntimeError("target read-back did not expose the routed document")
                    for decision in plan:
                        self.ledger.mark_verified(decision)
                        self.client.invalidate(source_bank, decision.source_memory_id, reason=f"verified dual-write to {target_bank}; Somnus ledger retained")
                        self.ledger.mark_invalidated(decision); report["verified"] += 1; report["invalidated"] += 1
                except Exception as exc:
                    safe = redact_sensitive(str(exc))
                    for decision in plan: self.ledger.mark_error(decision, safe)
                    report["errors"].append({"bank": target_bank, "error": safe, "batch_start": start})
        return report

def env_client() -> HindsightClient:
    return HindsightClient(os.environ.get("HINDSIGHT_API_URL") or os.environ.get("HINDSIGHT_URL") or "http://127.0.0.1:8888", os.environ.get("HINDSIGHT_API_KEY", ""), float(os.environ.get("HINDSIGHT_TIMEOUT_S", "90")))
