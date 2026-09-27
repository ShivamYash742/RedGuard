"""
RedGuard Controlled Execution Environment (CEE)
=================================================

Deterministic synthetic resources for Mode B agent runs (§5.1 of
MULTI_AGENT_LAB_PLAN.md): `files`, `web`, `db`, `kv`.

**Accuracy statement:** the CEE is a *research fixture*, not a security
sandbox. It provides controlled synthetic resources so runs are reproducible
and attacks stay inside the fixture. It makes no isolation guarantee and must
never be described as one.

Determinism rules:
  - `search_web` matches a normalized query key, falling back to a sorted
    scan over declared keys (never live search, never dict-iteration-order
    dependent in an unstated way).
  - `query_db` accepts only query names declared in the fixture, with
    optional equality filters on `params` — never arbitrary SQL.
  - Any unmatched lookup returns `NO_RESULTS` rather than raising, so an
    agent probing for something absent produces a recordable event, not a
    crash.

This module is stdlib-only and does not import `trace` or `topology` — it
has no notion of agents, authorization, or events. That is `tools.py`'s job.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

#: Sentinel returned for any unmatched resource lookup. A plain string (not
#: an exception, not None) so it round-trips through JSON in trace events
#: and evidence bundles unchanged.
NO_RESULTS = "NO_RESULTS"


def _normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", query.strip().lower())


class ControlledExecutionEnvironment:
    """Holds the four resource maps for one run and mediates deterministic
    reads/writes to them. Construct via `from_fixture` / `from_dict`.
    """

    def __init__(
        self,
        files: Optional[Dict[str, str]] = None,
        web: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        db: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        kv: Optional[Dict[str, Any]] = None,
        fixture_id: str = "unnamed",
    ):
        self.fixture_id = fixture_id
        self.files: Dict[str, str] = dict(files or {})
        self.web: Dict[str, List[Dict[str, Any]]] = dict(web or {})
        self.db: Dict[str, List[Dict[str, Any]]] = dict(db or {})
        self.kv: Dict[str, Any] = dict(kv or {})

    # ── construction ──────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ControlledExecutionEnvironment":
        return cls(
            files=data.get("files"),
            web=data.get("web"),
            db=data.get("db"),
            kv=data.get("kv"),
            fixture_id=data.get("fixture_id", "unnamed"),
        )

    @classmethod
    def from_fixture(cls, path: Path) -> "ControlledExecutionEnvironment":
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    # ── reads ──────────────────────────────────────────────────────────

    def read_file(self, path: str) -> str:
        return self.files.get(path, NO_RESULTS)

    def search_web(self, query: str) -> Any:
        key = _normalize_query(query)
        if key in self.web:
            return self.web[key]
        # Explicit ordered fallback: sorted declared keys, substring match
        # either direction. Deterministic regardless of fixture authoring order.
        for declared_key in sorted(self.web):
            if declared_key in key or key in declared_key:
                return self.web[declared_key]
        return NO_RESULTS

    def query_db(self, name: str, params: Optional[Dict[str, Any]] = None) -> Any:
        if name not in self.db:
            return NO_RESULTS
        rows = self.db[name]
        if not params:
            return rows
        if not isinstance(rows, list):
            # A free-text "table" cannot be filtered. Returning it whole beats
            # the old behaviour — iterating the string's characters and
            # crashing into a tool_error that hid the content from the agent.
            return rows
        return [
            row for row in rows
            if isinstance(row, dict) and all(row.get(k) == v for k, v in params.items())
        ] or NO_RESULTS

    def get_kv(self, key: str) -> Any:
        return self.kv.get(key, NO_RESULTS)

    def set_kv(self, key: str, value: Any) -> None:
        self.kv[key] = value

    # ── injection ──────────────────────────────────────────────────────

    def plant_artifact(self, channel: str, location: str, content: Any, mode: str = "replace") -> None:
        """Insert adversarial content into a resource before the run starts.

        `channel` selects the resource map; `location` is the key within it
        (a file path, a web query key, a db table name, or a kv key).

        `mode="append"` adds `content` as one more row (db) or search result
        (web) instead of replacing the whole list. Replacing a table with a
        string changed its shape between the clean and attack runs, and any
        `db_query` with a filter then crashed on it — the attack never
        reached the agent in exactly the cases titled "poisoned row".
        """
        if mode == "append":
            if channel not in ("db", "web"):
                raise ValueError(f"append planting is only defined for db and web, not {channel!r}")
            target = self.db if channel == "db" else self.web
            key = location if channel == "db" else _normalize_query(location)
            existing = target.get(key, [])
            if not isinstance(existing, list):
                raise ValueError(f"cannot append to non-list {channel} entry {location!r}")
            target[key] = [*existing, content]
            return
        if mode != "replace":
            raise ValueError(f"Unknown plant mode {mode!r}")
        if channel == "files":
            self.files[location] = content
        elif channel == "web":
            self.web[_normalize_query(location)] = content
        elif channel == "db":
            self.db[location] = content
        elif channel == "kv":
            self.kv[location] = content
        else:
            raise ValueError(f"Unknown CEE channel '{channel}'")

    # ── snapshot / restore ────────────────────────────────────────────

    def snapshot(self) -> Dict[str, Any]:
        return copy.deepcopy(
            {"files": self.files, "web": self.web, "db": self.db, "kv": self.kv}
        )

    def restore(self, snapshot: Dict[str, Any]) -> None:
        self.files = copy.deepcopy(snapshot["files"])
        self.web = copy.deepcopy(snapshot["web"])
        self.db = copy.deepcopy(snapshot["db"])
        self.kv = copy.deepcopy(snapshot["kv"])

    def to_json(self) -> Dict[str, Any]:
        data = self.snapshot()
        data["fixture_id"] = self.fixture_id
        return data


#: Short alias used throughout the rest of core/lab/.
CEE = ControlledExecutionEnvironment
