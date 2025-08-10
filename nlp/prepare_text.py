"""Text preparation helpers."""

from __future__ import annotations


def truncate_smart(text: str, max_chars: int) -> str:
    """Truncate text preserving bullet and paragraph boundaries.

    The function collects full paragraphs separated by blank lines. Bullet lists
    inside a paragraph are cut only at line boundaries so the last bullet is
    kept whole.
    """

    if not text or len(text) <= max_chars:
        return text.strip()

    result_parts: list[str] = []
    total = 0
    paragraphs = text.split("\n\n")
    for para in paragraphs:
        seg = para
        separator = 2 if result_parts else 0
        needed = len(seg) + separator
        if total + needed > max_chars:
            if para.lstrip().startswith("-"):
                lines = para.splitlines()
                kept: list[str] = []
                for line in lines:
                    line_sep = 1 if (result_parts or kept) else 0
                    line_len = len(line) + line_sep
                    if total + line_len > max_chars:
                        break
                    kept.append(line)
                    total += line_len
                if kept:
                    result_parts.append("\n".join(kept))
            break
        else:
            result_parts.append(seg)
            total += needed
    return "\n\n".join(result_parts).strip()
