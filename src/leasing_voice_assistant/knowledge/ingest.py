"""Markdown ingestion for the local knowledge base."""

import re
from pathlib import Path

from leasing_voice_assistant.knowledge.models import KnowledgeChunk, KnowledgeMetadata

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
DEFAULT_KNOWLEDGE_ROOT = Path(__file__).resolve().parents[3] / "data" / "knowledge"


def ingest_knowledge_base(root: Path | str = DEFAULT_KNOWLEDGE_ROOT) -> list[KnowledgeChunk]:
    """Read local markdown files into stable section-level chunks."""
    root_path = Path(root)
    if not root_path.exists():
        return []

    chunks: list[KnowledgeChunk] = []
    for source_path in sorted(root_path.rglob("*.md")):
        chunks.extend(_ingest_markdown_file(source_path, root_path))
    return chunks


def _ingest_markdown_file(source_path: Path, root_path: Path) -> list[KnowledgeChunk]:
    relative_path = source_path.relative_to(root_path).as_posix()
    property_identifier = _property_identifier(source_path, root_path)
    title = source_path.stem.replace("-", " ").title()
    current_section = title
    current_lines: list[str] = []
    chunks: list[KnowledgeChunk] = []

    for line in source_path.read_text(encoding="utf-8").splitlines():
        heading = HEADING_PATTERN.match(line)
        if heading is None:
            current_lines.append(line)
            continue

        level = len(heading.group(1))
        heading_text = heading.group(2).strip()
        if level == 1:
            title = heading_text
            current_section = heading_text
            current_lines = []
            continue

        _append_chunk(
            chunks,
            source_path=relative_path,
            document_title=title,
            section=current_section,
            property_identifier=property_identifier,
            lines=current_lines,
        )
        current_section = heading_text
        current_lines = []

    _append_chunk(
        chunks,
        source_path=relative_path,
        document_title=title,
        section=current_section,
        property_identifier=property_identifier,
        lines=current_lines,
    )
    return chunks


def _append_chunk(
    chunks: list[KnowledgeChunk],
    *,
    source_path: str,
    document_title: str,
    section: str,
    property_identifier: str | None,
    lines: list[str],
) -> None:
    text = "\n".join(line.strip() for line in lines).strip()
    if not text:
        return

    chunk_id = f"{source_path}#{_slugify(section)}"
    chunks.append(
        KnowledgeChunk(
            text=text,
            metadata=KnowledgeMetadata(
                source_path=source_path,
                document_title=document_title,
                section=section,
                chunk_id=chunk_id,
                property_identifier=property_identifier,
            ),
        )
    )


def _property_identifier(source_path: Path, root_path: Path) -> str | None:
    relative = source_path.relative_to(root_path)
    if len(relative.parts) >= 2 and relative.parts[0] == "properties":
        return source_path.stem
    return None


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "section"
