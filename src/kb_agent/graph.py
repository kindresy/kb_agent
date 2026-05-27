from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from kb_agent.jsonl import read_jsonl, write_jsonl
from kb_agent.markdown import extract_kb_source_refs
from kb_agent.sources import load_source_index


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    type: str
    label: str
    ref: str


@dataclass(frozen=True)
class GraphEdge:
    from_: str
    to: str
    type: str
    evidence: str

    def to_record(self) -> dict[str, str]:
        return {
            "from": self.from_,
            "to": self.to,
            "type": self.type,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class GraphExport:
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    report_path: str


def _claim_paths(root: Path) -> list[Path]:
    claims_root = root / ".kb" / "claims"
    return sorted(claims_root.rglob("*.jsonl")) if claims_root.is_dir() else []


def _topic_paths(root: Path) -> list[Path]:
    topics_root = root / ".kb" / "topics"
    return sorted(topics_root.rglob("*.jsonl")) if topics_root.is_dir() else []


def _chunk_paths(root: Path) -> list[Path]:
    chunks_root = root / ".kb" / "chunks"
    return sorted(chunks_root.rglob("*.jsonl")) if chunks_root.is_dir() else []


def _note_paths(root: Path) -> list[Path]:
    notes_root = root / "notes"
    return sorted(notes_root.rglob("*.md")) if notes_root.is_dir() else []


def _edge_key(edge: GraphEdge) -> tuple[str, str, str, str]:
    return (edge.from_, edge.to, edge.type, edge.evidence)


def _sorted_unique_edges(edges: list[GraphEdge]) -> list[GraphEdge]:
    return sorted({_edge_key(edge): edge for edge in edges}.values(), key=_edge_key)


def _tokens(text: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return tuple(re.findall(r"[a-z0-9]+", normalized))


def _topic_terms(topic: dict) -> set[tuple[str, ...]]:
    topic_id = str(topic.get("topic_id", ""))
    values = [
        topic_id,
        topic_id.removeprefix("topic.").replace("_", " "),
        str(topic.get("name", "")),
    ]
    values.extend(str(alias) for alias in topic.get("aliases") or [])
    return {tokens for value in values if (tokens := _tokens(value))}


def _contains_token_phrase(tokens: tuple[str, ...], phrase: tuple[str, ...]) -> bool:
    if len(phrase) > len(tokens):
        return False
    return any(
        tokens[index : index + len(phrase)] == phrase
        for index in range(len(tokens) - len(phrase) + 1)
    )


def build_graph(root: Path) -> tuple[list[GraphNode], list[GraphEdge]]:
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    topic_match_terms: dict[str, set[tuple[str, ...]]] = {}

    for source in load_source_index(root):
        nodes[f"source:{source.source_id}"] = GraphNode(
            node_id=f"source:{source.source_id}",
            type="source",
            label=source.title,
            ref=source.path,
        )

    for path in _topic_paths(root):
        relative = path.relative_to(root).as_posix()
        for topic in read_jsonl(path):
            topic_id = str(topic.get("topic_id", ""))
            if not topic_id:
                continue
            topic_match_terms[topic_id] = _topic_terms(topic)
            nodes[f"topic:{topic_id}"] = GraphNode(
                node_id=f"topic:{topic_id}",
                type="topic",
                label=str(topic.get("name", topic_id)),
                ref=relative,
            )
            source_id = str(topic.get("source_id", ""))
            if source_id:
                edges.append(
                    GraphEdge(
                        from_=f"topic:{topic_id}",
                        to=f"source:{source_id}",
                        type="topic_from_source",
                        evidence="source_id",
                    )
                )

    for path in _chunk_paths(root):
        relative = path.relative_to(root).as_posix()
        for chunk in read_jsonl(path):
            chunk_id = str(chunk.get("chunk_id", ""))
            if not chunk_id:
                continue
            nodes[f"chunk:{chunk_id}"] = GraphNode(
                node_id=f"chunk:{chunk_id}",
                type="chunk",
                label=chunk_id,
                ref=relative,
            )
            topic_id = str(chunk.get("topic_id", ""))
            source_id = str(chunk.get("source_id", ""))
            if topic_id:
                edges.append(
                    GraphEdge(
                        from_=f"chunk:{chunk_id}",
                        to=f"topic:{topic_id}",
                        type="chunk_supports_topic",
                        evidence="topic_id",
                    )
                )
            if source_id:
                edges.append(
                    GraphEdge(
                        from_=f"chunk:{chunk_id}",
                        to=f"source:{source_id}",
                        type="chunk_from_source",
                        evidence="source_id",
                    )
                )

    for path in _claim_paths(root):
        relative = path.relative_to(root).as_posix()
        for claim in read_jsonl(path):
            claim_id = str(claim.get("claim_id", ""))
            if not claim_id:
                continue
            nodes[f"claim:{claim_id}"] = GraphNode(
                node_id=f"claim:{claim_id}",
                type="claim",
                label=str(claim.get("claim", claim_id)),
                ref=relative,
            )
            topic_id = str(claim.get("topic_id", ""))
            if topic_id:
                edges.append(
                    GraphEdge(
                        from_=f"claim:{claim_id}",
                        to=f"topic:{topic_id}",
                        type="claim_about_topic",
                        evidence="topic_id",
                    )
                )
            for citation in claim.get("citations") or []:
                citation_text = str(citation)
                for source_id in extract_kb_source_refs(citation_text):
                    edges.append(
                        GraphEdge(
                            from_=f"claim:{claim_id}",
                            to=f"source:{source_id}",
                            type="claim_cites_source",
                            evidence=citation_text,
                        )
                    )

    for note in _note_paths(root):
        relative = note.relative_to(root).as_posix()
        text = note.read_text(encoding="utf-8", errors="replace")
        node_id = f"note:{relative}"
        nodes[node_id] = GraphNode(
            node_id=node_id,
            type="note",
            label=relative,
            ref=relative,
        )
        for source_id in extract_kb_source_refs(text):
            edges.append(
                GraphEdge(
                    from_=node_id,
                    to=f"source:{source_id}",
                    type="note_mentions_source",
                    evidence=source_id,
                )
            )
        note_tokens = _tokens(text)
        for topic_id, terms in topic_match_terms.items():
            if any(_contains_token_phrase(note_tokens, term) for term in terms):
                edges.append(
                    GraphEdge(
                        from_=node_id,
                        to=f"topic:{topic_id}",
                        type="note_mentions_topic",
                        evidence=topic_id,
                    )
                )

    return sorted(nodes.values(), key=lambda node: node.node_id), _sorted_unique_edges(
        edges
    )


def export_graph(root: Path) -> GraphExport:
    nodes, edges = build_graph(root)
    graph_root = root / ".kb" / "graph"
    write_jsonl(graph_root / "nodes.jsonl", [asdict(node) for node in nodes])
    write_jsonl(graph_root / "edges.jsonl", [edge.to_record() for edge in edges])

    node_counts = Counter(node.type for node in nodes)
    edge_counts = Counter(edge.type for edge in edges)
    summary = {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "node_counts": dict(sorted(node_counts.items())),
        "edge_counts": dict(sorted(edge_counts.items())),
    }
    (graph_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report_path = root / "reports" / "graph" / "graph_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    source_coverage = _source_coverage(nodes, edges)
    claim_citation_coverage = _claim_citation_coverage(nodes, edges)
    report_path.write_text(
        "\n".join(
            [
                "# Graph Report",
                "",
                f"- Nodes: {len(nodes)}",
                f"- Edges: {len(edges)}",
                "",
                "## Node Types",
                "",
                *_count_lines(node_counts),
                "",
                "## Edge Types",
                "",
                *_count_lines(edge_counts),
                "",
                "## Source Coverage",
                "",
                f"- Total sources: {source_coverage['total_sources']}",
                f"- Linked sources: {source_coverage['linked_sources']}",
                f"- Unlinked sources: {source_coverage['unlinked_sources']}",
                "",
                "## Claim Citation Coverage",
                "",
                f"- Total claims: {claim_citation_coverage['total_claims']}",
                f"- Cited claims: {claim_citation_coverage['cited_claims']}",
                f"- Uncited claims: {claim_citation_coverage['uncited_claims']}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return GraphExport(
        nodes=nodes,
        edges=edges,
        report_path=report_path.relative_to(root).as_posix(),
    )


def _count_lines(counts: Counter[str]) -> list[str]:
    if not counts:
        return ["- none"]
    return [f"- {name}: {count}" for name, count in sorted(counts.items())]


def _source_coverage(
    nodes: list[GraphNode], edges: list[GraphEdge]
) -> dict[str, int]:
    source_node_ids = {node.node_id for node in nodes if node.type == "source"}
    linked_source_ids = {
        edge.to
        for edge in edges
        if edge.to in source_node_ids and edge.from_ != edge.to
    }
    return {
        "total_sources": len(source_node_ids),
        "linked_sources": len(linked_source_ids),
        "unlinked_sources": len(source_node_ids - linked_source_ids),
    }


def _claim_citation_coverage(
    nodes: list[GraphNode], edges: list[GraphEdge]
) -> dict[str, int]:
    claim_node_ids = {node.node_id for node in nodes if node.type == "claim"}
    cited_claim_ids = {
        edge.from_
        for edge in edges
        if edge.type == "claim_cites_source" and edge.from_ in claim_node_ids
    }
    return {
        "total_claims": len(claim_node_ids),
        "cited_claims": len(cited_claim_ids),
        "uncited_claims": len(claim_node_ids - cited_claim_ids),
    }
