from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kb_agent.compile import compile_fast
from kb_agent.sources import load_source_index


@dataclass(frozen=True)
class HealthReport:
    status: str
    source_count: int
    finding_count: int


def build_health_report(root: Path) -> HealthReport:
    compile_result = compile_fast(root)
    source_count = len(load_source_index(root))
    finding_count = len(compile_result.findings)
    status = "ok" if compile_result.passed else "warning"
    return HealthReport(
        status=status,
        source_count=source_count,
        finding_count=finding_count,
    )
