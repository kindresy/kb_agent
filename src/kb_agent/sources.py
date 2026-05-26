from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import unquote

from kb_agent.markdown import extract_markdown_links


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    type: str
    title: str
    path: str
    original_path: str
    hash: str
    status: str = "accepted"
    kind: str = "file"
    package_path: str | None = None
    assets: list[str] | None = None


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


def is_markdown(path: Path) -> bool:
    return path.suffix.lower() in {".md", ".markdown"}


def markdown_assets_dir(path: Path) -> Path:
    return path.with_name(f"{path.stem}.assets")


def named_markdown_asset_dirs(path: Path) -> list[Path]:
    return [
        path.with_name(f"{path.stem}.assets"),
        path.with_name(f"{path.stem}-assets"),
        path.with_name(f"{path.stem}_assets"),
    ]


def linked_markdown_asset_dirs(path: Path) -> list[Path]:
    if not path.is_file():
        return []

    parent = path.parent
    dirs: list[Path] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for link in extract_markdown_links(text):
        link_path = Path(unquote(link))
        if not link_path.parts:
            continue
        first_part = link_path.parts[0]
        if first_part in {".", ".."}:
            continue
        candidate = parent / first_part
        if candidate.is_dir() and is_relative_to(candidate, parent):
            dirs.append(candidate)
    return dirs


def linked_markdown_asset_aliases(path: Path) -> list[tuple[Path, Path]]:
    if not path.is_file():
        return []

    parent = path.parent
    aliases: list[tuple[Path, Path]] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for link in extract_markdown_links(text):
        link_path = Path(unquote(link))
        if len(link_path.parts) < 2 or link_path.parts[0] in {".", ".."}:
            continue
        if (parent / link_path).exists():
            continue
        for assets_dir in named_markdown_asset_dirs(path):
            candidate = assets_dir.joinpath(*link_path.parts[1:])
            if candidate.is_file() and is_relative_to(candidate, assets_dir):
                aliases.append((candidate, link_path))
                break
    return aliases


def markdown_asset_dirs(path: Path) -> list[Path]:
    dirs = [
        candidate
        for candidate in named_markdown_asset_dirs(path) + linked_markdown_asset_dirs(path)
        if candidate.is_dir()
    ]
    unique_dirs: dict[Path, Path] = {}
    for directory in dirs:
        unique_dirs[directory.resolve()] = directory
    return sorted(unique_dirs.values())


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


def allocate_package_destination(
    root: Path, source_id: str, existing_ids: set[str]
) -> tuple[str, Path]:
    destination_parent = root / DESTINATION_BY_TYPE["manual"]
    for counter in range(1, 10_000):
        candidate_id = source_id if counter == 1 else f"{source_id}_{counter}"
        destination = destination_parent / candidate_id
        if candidate_id not in existing_ids and not destination.exists():
            return candidate_id, destination
    raise ValueError(f"could not find unique package destination for {source_id}")


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def package_assets(markdown_path: Path) -> list[Path]:
    return sorted(
        path
        for assets_dir in markdown_asset_dirs(markdown_path)
        for path in assets_dir.rglob("*")
        if path.is_file()
    )


def ingest_markdown_package(
    root: Path, markdown_path: Path, existing_ids: set[str]
) -> SourceRecord:
    source_id, package_dir = allocate_package_destination(
        root, source_id_for(markdown_path), existing_ids
    )
    package_dir.mkdir(parents=True, exist_ok=True)

    destination_markdown = package_dir / markdown_path.name
    shutil.copy2(markdown_path, destination_markdown)

    assets: list[str] = []
    for assets_dir in markdown_asset_dirs(markdown_path):
        destination_assets_dir = package_dir / assets_dir.name
        shutil.copytree(assets_dir, destination_assets_dir)
        assets.extend(
            path.relative_to(root).as_posix()
            for path in sorted(destination_assets_dir.rglob("*"))
            if path.is_file()
        )
    for source_file, relative_link in linked_markdown_asset_aliases(markdown_path):
        destination_alias = package_dir / relative_link
        destination_alias.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, destination_alias)
        assets.append(destination_alias.relative_to(root).as_posix())

    return SourceRecord(
        source_id=source_id,
        type="manual",
        title=markdown_path.stem,
        path=destination_markdown.relative_to(root).as_posix(),
        original_path=str(markdown_path),
        hash=sha256_file(destination_markdown),
        kind="package",
        package_path=package_dir.relative_to(root).as_posix(),
        assets=assets,
    )


def ingest_path(root: Path, input_path: Path) -> list[SourceRecord]:
    records = load_source_index(root)
    new_records = []
    existing_ids = {record.source_id for record in records}
    existing_hashes = {record.hash for record in records}
    input_files = iter_input_files(input_path)
    package_markdown_files = [
        source_path
        for source_path in input_files
        if is_markdown(source_path) and markdown_asset_dirs(source_path)
    ]
    package_asset_dirs = [
        assets_dir
        for markdown_path in package_markdown_files
        for assets_dir in markdown_asset_dirs(markdown_path)
    ]

    for markdown_path in package_markdown_files:
        source_hash = sha256_file(markdown_path)
        if source_hash in existing_hashes:
            continue
        record = ingest_markdown_package(root, markdown_path, existing_ids)
        existing_ids.add(record.source_id)
        existing_hashes.add(record.hash)
        new_records.append(record)

    for source_path in input_files:
        if source_path in package_markdown_files:
            continue
        if any(is_relative_to(source_path, asset_dir) for asset_dir in package_asset_dirs):
            continue
        source_hash = sha256_file(source_path)
        if source_hash in existing_hashes:
            continue
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
            hash=source_hash,
        )
        existing_hashes.add(record.hash)
        new_records.append(record)

    write_source_index(root, records + new_records)
    return new_records
