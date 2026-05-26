from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    type: str
    title: str
    path: str
    original_path: str
    hash: str
    status: str = "accepted"


TYPE_BY_SUFFIX = {
    ".pdf": "spec",
    ".md": "manual",
    ".markdown": "manual",
    ".txt": "manual",
    ".html": "webpage",
    ".htm": "webpage",
    ".c": "code",
    ".h": "code",
    ".py": "code",
    ".rs": "code",
    ".go": "code",
    ".log": "log",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
}

DESTINATION_BY_TYPE = {
    "spec": "sources/specs",
    "manual": "sources/manuals",
    "webpage": "sources/webpages",
    "code": "sources/code",
    "log": "sources/logs",
    "image": "sources/images",
    "unknown": "sources/unknown",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def detect_type(path: Path) -> str:
    return TYPE_BY_SUFFIX.get(path.suffix.lower(), "unknown")


def source_id_for(path: Path) -> str:
    source_id = re.sub(r"[^a-z0-9]+", "_", path.stem.lower()).strip("_")
    return source_id or "source"


def iter_input_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(candidate for candidate in path.rglob("*") if candidate.is_file())
    raise FileNotFoundError(f"input path does not exist: {path}")


def load_source_index(root: Path) -> list[SourceRecord]:
    index_path = root / ".kb" / "source_index.jsonl"
    if not index_path.is_file():
        return []

    records = []
    for line in index_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(SourceRecord(**json.loads(line)))
    return records


def write_source_index(root: Path, records: list[SourceRecord]) -> None:
    index_path = root / ".kb" / "source_index.jsonl"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(asdict(record), ensure_ascii=False, sort_keys=True)
        for record in records
    ]
    index_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def unique_destination(destination: Path) -> Path:
    if not destination.exists():
        return destination

    for counter in range(2, 10_000):
        candidate = destination.with_name(
            f"{destination.stem}_{counter}{destination.suffix}"
        )
        if not candidate.exists():
            return candidate

    raise ValueError(f"could not find unique destination for {destination}")


def unique_source_id(source_id: str, existing_ids: set[str]) -> str:
    if source_id not in existing_ids:
        return source_id

    for counter in range(2, 10_000):
        candidate = f"{source_id}_{counter}"
        if candidate not in existing_ids:
            return candidate

    raise ValueError(f"could not find unique source_id for {source_id}")


def ingest_path(root: Path, input_path: Path) -> list[SourceRecord]:
    records = load_source_index(root)
    new_records = []
    existing_ids = {record.source_id for record in records}

    for source_path in iter_input_files(input_path):
        source_type = detect_type(source_path)
        destination_dir = root / DESTINATION_BY_TYPE[source_type]
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = unique_destination(destination_dir / source_path.name)
        shutil.copy2(source_path, destination)
        source_id = unique_source_id(source_id_for(destination), existing_ids)
        existing_ids.add(source_id)

        record = SourceRecord(
            source_id=source_id,
            type=source_type,
            title=source_path.stem,
            path=destination.relative_to(root).as_posix(),
            original_path=str(source_path),
            hash=sha256_file(destination),
        )
        new_records.append(record)

    write_source_index(root, records + new_records)
    return new_records
