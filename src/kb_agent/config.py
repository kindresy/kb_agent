from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class KBConfig:
    domain: str
    title: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "title": self.title,
            "source_policy": {"ai_can_modify_sources": False},
            "citation_policy": {"require_citation_for_claim": True},
            "conflict_policy": {"require_user_review": True},
        }


def default_config(domain: str) -> KBConfig:
    return KBConfig(domain=domain, title=f"{domain} Knowledge Base")


def write_config(root: Path, config: KBConfig) -> None:
    path = root / "kb.yaml"
    path.write_text(
        yaml.safe_dump(config.to_dict(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def load_config(root: Path) -> dict[str, Any]:
    path = root / "kb.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"missing kb.yaml at {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"invalid kb.yaml at {path}")
    return data
