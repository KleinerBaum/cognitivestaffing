"""Ensure inline prompts are sourced from the central registry."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterator, Sequence

PROMPT_KEYWORDS: Sequence[str] = (
    "You are",
    "Du bist",
    "Respond",
    "Antworte",
    "JSON",
    "Folge",
    "Return",
    "Call the function",
)

IGNORED_PARTS = {"tests", "prompts", "__pycache__"}
TARGET_DIRS = {
    "openai_utils",
    "llm",
    "pipelines",
    "generators",
    "sidebar",
    "question_logic",
}


def _iter_python_files(root: Path) -> Iterator[Path]:
    for path in root.rglob("*.py"):
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        if rel.parts[0] not in TARGET_DIRS:
            continue
        yield path


def _docstring_nodes(tree: ast.AST) -> set[ast.AST]:
    nodes: set[ast.AST] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                nodes.add(first.value)
    return nodes


def _joined_text(node: ast.JoinedStr) -> str:
    parts: list[str] = []
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            parts.append(value.value)
    return "".join(parts)


def _call_name(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Call):
        func = node.func
    else:
        return None
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _looks_like_prompt(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 60 and "\n" not in stripped:
        return False
    return any(keyword in stripped for keyword in PROMPT_KEYWORDS)


def test_no_inline_prompts_outside_registry() -> None:
    root = Path(__file__).resolve().parents[1]
    violations: list[str] = []
    for path in _iter_python_files(root):
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        doc_nodes = _docstring_nodes(tree)
        parent_map: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parent_map[child] = parent
        for node in ast.walk(tree):
            text: str | None = None
            lineno = getattr(node, "lineno", 1)
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node in doc_nodes:
                    continue
                parent_name = _call_name(parent_map.get(node))
                if parent_name in {"tr", "_tr"}:
                    continue
                text = node.value
            elif isinstance(node, ast.JoinedStr):
                text = _joined_text(node)
            if not text:
                continue
            if _looks_like_prompt(text):
                snippet = " ".join(text.split())[:120]
                violations.append(f"{path}:{lineno}: {snippet}")
    assert not violations, "Inline prompts must be stored in prompts/registry.yaml:\n" + "\n".join(violations)
