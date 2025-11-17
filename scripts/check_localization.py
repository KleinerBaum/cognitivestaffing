"""Scan UI sources for untranslated English strings."""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Iterable, Mapping, Sequence, cast

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import i18n as _i18n
except Exception:  # pragma: no cover - fallback for import-time issues
    I18N_STR: dict[str, dict[str, str]] = {"en": {}}
else:  # pragma: no cover - executed in normal environments
    imported = cast(Mapping[str, Mapping[str, str]], getattr(_i18n, "STR", {"en": {}}))
    I18N_STR = {lang: dict(values) for lang, values in imported.items()}


DEFAULT_DIRECTORIES: tuple[str, ...] = (
    "sidebar",
    "pages",
    "components",
    "wizard",
    "ui_views",
)


@dataclass(frozen=True)
class LocalizationOffense:
    """Represents a string literal that is missing localisation wrappers."""

    file: Path
    line: int
    value: str
    reason: str


class _LocalizationVisitor(ast.NodeVisitor):
    """Collect offending string literals inside a Python AST."""

    def __init__(
        self,
        file_path: Path,
        parents: dict[ast.AST, ast.AST | None],
        known_translations: set[str],
    ) -> None:
        self.file_path = file_path
        self.parents = parents
        self.known_translations = known_translations
        self.offenses: list[LocalizationOffense] = []

    def visit_Constant(self, node: ast.Constant) -> None:  # noqa: N802 - ast API
        if isinstance(node.value, str):
            # JoinedStr nodes handle their own constant children.
            if not isinstance(self.parents.get(node), ast.JoinedStr):
                self._maybe_report(node, node.value)
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:  # noqa: N802 - ast API
        literal = "".join(
            part.value for part in node.values if isinstance(part, ast.Constant) and isinstance(part.value, str)
        )
        if literal:
            self._maybe_report(node, literal)
        self.generic_visit(node)

    # Helper predicates -------------------------------------------------

    def _maybe_report(self, node: ast.AST, text: str) -> None:
        if not _looks_english(text):
            return
        if self._is_docstring(node):
            return
        if self._is_within_tr_call(node):
            return
        if self._is_bilingual_tuple(node):
            return
        if text.strip() in self.known_translations:
            return
        reason = "String literal is not wrapped in tr() or registered in i18n.STR"
        self.offenses.append(
            LocalizationOffense(
                file=self.file_path,
                line=getattr(node, "lineno", 0) or 0,
                value=text.strip(),
                reason=reason,
            )
        )

    def _is_docstring(self, node: ast.AST) -> bool:
        parent = self.parents.get(node)
        if not isinstance(parent, ast.Expr):
            return False
        grandparent = self.parents.get(parent)
        if not isinstance(grandparent, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            return False
        body = getattr(grandparent, "body", [])
        return bool(body) and body[0] is parent

    def _is_within_tr_call(self, node: ast.AST) -> bool:
        current: ast.AST | None = node
        while current is not None and current in self.parents:
            parent = self.parents[current]
            if isinstance(parent, ast.Call):
                func = parent.func
                if isinstance(func, ast.Name) and func.id == "tr":
                    return True
                if isinstance(func, ast.Attribute) and func.attr == "tr":
                    return True
            current = parent
        return False

    def _is_bilingual_tuple(self, node: ast.AST) -> bool:
        parent = self.parents.get(node)
        if not isinstance(parent, ast.Tuple):
            return False
        elements = parent.elts
        if len(elements) != 2:
            return False
        return all(_is_string_like(element) for element in elements)


def _is_string_like(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return True
    if isinstance(node, ast.JoinedStr):
        return any(isinstance(part, ast.Constant) and isinstance(part.value, str) for part in node.values)
    return False


def _looks_english(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 3:
        return False
    if not any(ch.isalpha() for ch in stripped):
        return False
    if any(ch in "äöüÄÖÜß" for ch in stripped):
        return False
    if " " not in stripped and not any(ch.isupper() for ch in stripped):
        return False
    if stripped.isupper() and len(stripped) <= 4:
        return False
    return True


def _build_parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST | None]:
    parents: dict[ast.AST, ast.AST | None] = {tree: None}
    stack = [tree]
    while stack:
        node = stack.pop()
        for child in ast.iter_child_nodes(node):
            parents[child] = node
            stack.append(child)
    return parents


def load_known_translations() -> set[str]:
    """Return a set of English translation strings from :mod:`i18n`."""

    english_entries = I18N_STR.get("en", {})
    return {value.strip() for value in english_entries.values()}


def scan_file(path: Path, known_translations: set[str] | None = None) -> list[LocalizationOffense]:
    """Scan a Python source file for hard-coded English strings."""

    known = known_translations or load_known_translations()
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    parents = _build_parent_map(tree)
    visitor = _LocalizationVisitor(path, parents, known)
    visitor.visit(tree)
    return visitor.offenses


def scan_paths(paths: Iterable[Path], known_translations: set[str] | None = None) -> list[LocalizationOffense]:
    """Scan every Python file under ``paths`` for localisation issues."""

    offenses: list[LocalizationOffense] = []
    known = known_translations or load_known_translations()
    for target in paths:
        if target.is_file() and target.suffix == ".py":
            offenses.extend(scan_file(target, known))
            continue
        if not target.is_dir():
            continue
        for source_file in sorted(target.rglob("*.py")):
            if source_file.is_file():
                offenses.extend(scan_file(source_file, known))
    return offenses


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        default=DEFAULT_DIRECTORIES,
        help="Directories or files to scan (defaults to UI modules).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    targets = [PROJECT_ROOT / path for path in args.paths]
    offenses = scan_paths(targets)
    if offenses:
        print("Localization scan found untranslated strings:")
        for offense in offenses:
            rel = offense.file.relative_to(PROJECT_ROOT)
            print(f"- {rel}:{offense.line} – {offense.reason}: {offense.value}")
        return 1
    print("Localization scan passed – no offending strings detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
