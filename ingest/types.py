"""Structured content helpers for ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List
import re


@dataclass(slots=True)
class ContentBlock:
    """Container describing a chunk of extracted content."""

    type: str
    """Semantic type of the block (paragraph, heading, list_item, table, ...)."""

    text: str
    """Primary text associated with the block."""

    level: int | None = None
    """Optional hierarchical level (e.g. heading depth or list indentation)."""

    metadata: dict[str, Any] | None = None
    """Additional metadata such as page numbers or table rows."""

    def render(self) -> str:
        """Return a normalized string representation for downstream joins."""

        if not self.text:
            return ""
        if self.type == "list_item":
            meta = self.metadata or {}
            marker = meta.get("marker", "-")
            ordered = bool(meta.get("ordered"))
            separator = ". " if ordered and not str(marker).endswith(".") else " "
            return f"{marker}{separator}{self.text}".strip()
        return self.text


@dataclass(slots=True)
class StructuredDocument:
    """Representation of extracted content with semantic blocks."""

    text: str
    blocks: list[ContentBlock]
    source: str | None = None
    raw_html: str | None = None

    def __bool__(self) -> bool:  # pragma: no cover - convenience
        return bool(self.text)

    def __str__(self) -> str:  # pragma: no cover - convenience
        return self.text

    @classmethod
    def from_blocks(
        cls,
        blocks: Iterable[ContentBlock],
        *,
        source: str | None = None,
        raw_html: str | None = None,
    ) -> "StructuredDocument":
        """Create a structured document from ``blocks``.

        Empty blocks are filtered and the resulting text is joined with blank
        lines to mimic the previous plain-text behaviour.
        """

        block_list = [block for block in blocks if block.text and block.text.strip()]
        text_parts = [block.render() for block in block_list if block.render().strip()]
        text = "\n\n".join(text_parts).strip()
        return cls(text=text, blocks=block_list, source=source, raw_html=raw_html)


_BULLET_RE = re.compile(r"^([*\u2022\-\u2013\u2023])\s+(.*)")
_ORDERED_RE = re.compile(r"^(\d+)[.)]\s+(.*)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)")


def _list_level_from_indent(line: str) -> int:
    """Return list nesting level based on indentation."""

    indent = len(line) - len(line.lstrip(" \t"))
    # Treat every two spaces (or a tab) as one additional level
    return max(indent // 2, 0)


def _flush_paragraph(buffer: List[str], blocks: List[ContentBlock]) -> None:
    if not buffer:
        return
    paragraph = "\n".join(buffer).strip()
    if paragraph:
        blocks.append(ContentBlock(type="paragraph", text=paragraph))
    buffer.clear()


def build_plain_text_document(
    text: str, *, source: str | None = None, raw_html: str | None = None
) -> StructuredDocument:
    """Convert raw ``text`` into a :class:`StructuredDocument`.

    Bullet points, ordered lists and Markdown headings are detected and mapped
    to dedicated block types so downstream consumers can preserve structure.
    """

    if not text:
        return StructuredDocument(text="", blocks=[], source=source, raw_html=raw_html)

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.splitlines()
    blocks: list[ContentBlock] = []
    buffer: list[str] = []

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            _flush_paragraph(buffer, blocks)
            continue
        heading_match = _HEADING_RE.match(stripped)
        if heading_match:
            _flush_paragraph(buffer, blocks)
            marker, content = heading_match.groups()
            blocks.append(
                ContentBlock(
                    type="heading",
                    text=content.strip(),
                    level=len(marker),
                    metadata={"marker": marker},
                )
            )
            continue
        bullet_match = _BULLET_RE.match(stripped)
        if bullet_match:
            _flush_paragraph(buffer, blocks)
            marker, content = bullet_match.groups()
            blocks.append(
                ContentBlock(
                    type="list_item",
                    text=content.strip(),
                    level=_list_level_from_indent(line),
                    metadata={"marker": marker, "ordered": False},
                )
            )
            continue
        ordered_match = _ORDERED_RE.match(stripped)
        if ordered_match:
            _flush_paragraph(buffer, blocks)
            marker, content = ordered_match.groups()
            blocks.append(
                ContentBlock(
                    type="list_item",
                    text=content.strip(),
                    level=_list_level_from_indent(line),
                    metadata={"marker": marker, "ordered": True},
                )
            )
            continue
        buffer.append(stripped)

    _flush_paragraph(buffer, blocks)

    return StructuredDocument.from_blocks(blocks, source=source, raw_html=raw_html)
