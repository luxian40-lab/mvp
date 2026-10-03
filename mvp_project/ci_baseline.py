"""Nodeids del baseline de fallos. Solo esos se marcan xfail en CI."""
from __future__ import annotations

from pathlib import Path

REASON = "baseline 56929af7"


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def baseline_path() -> Path:
    return repo_root() / "scripts" / "baseline_failures_before.txt"


def dotted_to_nodeid(dotted: str) -> str:
    """core.tests_x.Class.test_y → core/tests_x.py::Class::test_y."""
    parts = dotted.strip().split(".")
    i = 0
    while i < len(parts) and not (
        parts[i][:1].isupper() or parts[i].startswith("test_")
    ):
        i += 1
    mod = "/".join(parts[:i]) + ".py"
    rest = "::".join(parts[i:])
    return f"{mod}::{rest}" if rest else mod


def parse_baseline_lines(text: str) -> set[str]:
    nodeids: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("FAILED "):
            nodeids.add(line[len("FAILED ") :].strip().replace("\\", "/"))
            continue
        if line.startswith("FAIL:") and "(" in line and line.endswith(")"):
            dotted = line[line.rfind("(") + 1 : -1].strip()
            nodeids.add(dotted_to_nodeid(dotted))
    return nodeids


def baseline_nodeids(path: Path | None = None) -> set[str]:
    target = path or baseline_path()
    if not target.is_file():
        return set()
    return parse_baseline_lines(target.read_text(encoding="utf-8"))
