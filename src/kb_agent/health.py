from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from kb_agent.compile import compile_fast
from kb_agent.conflicts import detect_accepted_conflicts
from kb_agent.sources import load_source_index


@dataclass(frozen=True)
class HealthReport:
    status: str
    source_count: int
    finding_count: int
    graph_node_count: int
    graph_edge_count: int
    conflict_count: int


def _load_graph_counts(root: Path) -> tuple[int, int]:
    summary_path = root / ".kb" / "graph" / "summary.json"
    if not summary_path.is_file():
        return 0, 0

    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if not isinstance(summary, dict):
            return 0, 0
        node_count = summary.get("node_count", 0)
        edge_count = summary.get("edge_count", 0)
        if type(node_count) is not int or type(edge_count) is not int:
            return 0, 0
        return node_count, edge_count
    except json.JSONDecodeError:
        return 0, 0


def build_health_report(root: Path) -> HealthReport:
    compile_result = compile_fast(root)
    source_count = len(load_source_index(root))
    finding_count = len(compile_result.findings)
    graph_node_count, graph_edge_count = _load_graph_counts(root)
    conflict_count = len(detect_accepted_conflicts(root))
    status = "ok" if compile_result.passed else "warning"
    return HealthReport(
        status=status,
        source_count=source_count,
        finding_count=finding_count,
        graph_node_count=graph_node_count,
        graph_edge_count=graph_edge_count,
        conflict_count=conflict_count,
    )
