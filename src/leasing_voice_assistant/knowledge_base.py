from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from leasing_voice_assistant.interfaces import KnowledgeSnippet

DEFAULT_KB_DIR = Path("data/kb")
DEFAULT_RETRIEVAL_LIMIT = 5
MAX_RETRIEVAL_LIMIT = 25
DEFAULT_SNIPPET_CHARS = 500

_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "do",
        "does",
        "for",
        "from",
        "how",
        "i",
        "in",
        "is",
        "it",
        "me",
        "of",
        "on",
        "or",
        "the",
        "there",
        "to",
        "what",
        "when",
        "with",
        "you",
    }
)


@dataclass(frozen=True)
class KnowledgeSection:
    source_id: str
    document_id: str
    title: str
    section_heading: str
    text: str
    path: str


class MarkdownKnowledgeRetriever:
    def __init__(
        self,
        sections: Sequence[KnowledgeSection],
        *,
        snippet_chars: int = DEFAULT_SNIPPET_CHARS,
    ) -> None:
        self.sections = tuple(sections)
        self.snippet_chars = max(snippet_chars, 80)

    @classmethod
    def from_directory(
        cls,
        kb_dir: Path | str = DEFAULT_KB_DIR,
        *,
        snippet_chars: int = DEFAULT_SNIPPET_CHARS,
    ) -> MarkdownKnowledgeRetriever:
        return cls(load_markdown_sections(Path(kb_dir)), snippet_chars=snippet_chars)

    def retrieve(
        self, query: str, *, limit: int = DEFAULT_RETRIEVAL_LIMIT
    ) -> Sequence[KnowledgeSnippet]:
        normalized_query = query.strip()
        normalized_limit = _normalize_limit(limit)
        if not normalized_query:
            return ()

        query_terms = _token_counts(normalized_query)
        if not query_terms:
            return ()

        scored = ((_score_section(section, query_terms), section) for section in self.sections)
        matches = sorted(
            ((score, section) for score, section in scored if score > 0),
            key=lambda item: (-item[0], item[1].source_id),
        )
        return tuple(
            KnowledgeSnippet(
                source_id=section.source_id,
                text=_bounded_snippet(section.text, self.snippet_chars),
                score=round(score, 4),
                title=section.title,
                section_heading=section.section_heading,
                metadata=(
                    ("document_id", section.document_id),
                    ("path", section.path),
                ),
            )
            for score, section in matches[:normalized_limit]
        )


def load_markdown_sections(kb_dir: Path) -> tuple[KnowledgeSection, ...]:
    if not kb_dir.exists():
        return ()

    sections: list[KnowledgeSection] = []
    for path in sorted(kb_dir.glob("*.md")):
        sections.extend(_parse_markdown_document(path))
    return tuple(sections)


def _parse_markdown_document(path: Path) -> tuple[KnowledgeSection, ...]:
    document_id = _slugify(path.stem)
    title = path.stem.replace("-", " ").title()
    current_heading = title
    current_lines: list[str] = []
    sections: list[KnowledgeSection] = []

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        heading_match = _HEADING_PATTERN.match(raw_line)
        if heading_match:
            level = len(heading_match.group(1))
            heading = heading_match.group(2).strip()
            if level == 1:
                title = heading
                if current_lines:
                    sections.append(
                        _section_from_lines(
                            document_id,
                            title,
                            current_heading,
                            current_lines,
                            path,
                        )
                    )
                    current_lines = []
                current_heading = heading
            else:
                if current_lines:
                    sections.append(
                        _section_from_lines(
                            document_id,
                            title,
                            current_heading,
                            current_lines,
                            path,
                        )
                    )
                current_heading = heading
                current_lines = []
            continue

        current_lines.append(raw_line)

    if current_lines:
        sections.append(
            _section_from_lines(document_id, title, current_heading, current_lines, path)
        )

    return tuple(section for section in sections if section.text)


def _section_from_lines(
    document_id: str,
    title: str,
    section_heading: str,
    lines: Sequence[str],
    path: Path,
) -> KnowledgeSection:
    text = _normalize_body(lines)
    return KnowledgeSection(
        source_id=f"{document_id}#{_slugify(section_heading)}",
        document_id=document_id,
        title=title,
        section_heading=section_heading,
        text=text,
        path=path.as_posix(),
    )


def _normalize_body(lines: Sequence[str]) -> str:
    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        current.append(stripped)
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs)


def _score_section(section: KnowledgeSection, query_terms: Counter[str]) -> float:
    text_terms = _token_counts(section.text)
    title_terms = _token_counts(section.title)
    heading_terms = _token_counts(section.section_heading)
    score = 0.0

    for term, query_count in query_terms.items():
        text_count = text_terms.get(term, 0)
        if text_count:
            score += min(text_count, query_count) * 1.0
        if term in heading_terms:
            score += 2.0
        if term in title_terms:
            score += 1.5

    coverage = sum(
        1
        for term in query_terms
        if term in text_terms or term in heading_terms or term in title_terms
    )
    if coverage:
        score += coverage / len(query_terms)
    return score


def _token_counts(text: str) -> Counter[str]:
    return Counter(_tokens(text))


def _tokens(text: str) -> Iterable[str]:
    for token in _TOKEN_PATTERN.findall(text.casefold()):
        if token not in _STOPWORDS and len(token) > 1:
            yield token


def _bounded_snippet(text: str, max_chars: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def _normalize_limit(limit: int) -> int:
    return min(max(limit, 1), MAX_RETRIEVAL_LIMIT)


def _slugify(value: str) -> str:
    tokens = _TOKEN_PATTERN.findall(value.casefold())
    return "-".join(tokens) or "section"
