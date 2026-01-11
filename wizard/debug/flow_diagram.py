from __future__ import annotations

"""FLOW_DIAGRAM_GENERATOR: Mermaid flowchart generation for wizard navigation."""

from dataclasses import dataclass
import inspect
import ast
from typing import Iterable, Mapping, Protocol, Sequence

from wizard.navigation_types import StepNextResolver, WizardContext


class StepLike(Protocol):
    key: str
    label: tuple[str, str]
    next_step_id: StepNextResolver | None
    required_fields: tuple[str, ...]
    allow_skip: bool


@dataclass(frozen=True)
class BranchEdge:
    target: str
    label: str | None
    conditional: bool
    has_else: bool


@dataclass(frozen=True)
class MermaidEdge:
    source: str
    target: str
    label: str | None
    style: str


def build_mermaid_flowchart(
    router_or_config: Sequence[StepLike] | object,
    *,
    current_step_id: str | None = None,
) -> str:
    """Return a Mermaid flowchart for the wizard step configuration."""

    steps = _coerce_steps(router_or_config)
    step_map = {step.key: step for step in steps}
    node_ids = {step.key: _node_id(step.key) for step in steps}

    edges: list[MermaidEdge] = []
    for index, step in enumerate(steps):
        forward_edges = _resolve_forward_edges(step, steps, step_map)
        for forward_edge in forward_edges:
            edges.append(
                MermaidEdge(
                    source=node_ids[step.key],
                    target=node_ids.get(forward_edge.target, _node_id(forward_edge.target)),
                    label=forward_edge.label,
                    style="-->",
                )
            )

        if step.required_fields:
            guard_label = "Pflichtfelder fehlen / Missing required fields"
            edges.append(
                MermaidEdge(
                    source=node_ids[step.key],
                    target=node_ids[step.key],
                    label=guard_label,
                    style="-.->",
                )
            )

        if index > 0:
            previous_key = steps[index - 1].key
            edges.append(
                MermaidEdge(
                    source=node_ids[step.key],
                    target=node_ids[previous_key],
                    label=None,
                    style="-.->",
                )
            )

    lines = ["flowchart TD"]
    for step in steps:
        step_label = _format_label(step.label)
        node_label = f"{step_label}"
        if current_step_id and step.key == current_step_id:
            node_label = f"{step_label} (current)"
        lines.append(f'    {node_ids[step.key]}["{node_label}"]')

    for diagram_edge in edges:
        edge_label = _sanitize_label(diagram_edge.label)
        if edge_label:
            lines.append(f"    {diagram_edge.source} {diagram_edge.style}|{edge_label}| {diagram_edge.target}")
        else:
            lines.append(f"    {diagram_edge.source} {diagram_edge.style} {diagram_edge.target}")

    return "\n".join(lines)


def validate_router_graph(router_or_config: Sequence[StepLike] | object) -> list[str]:
    """Validate the wizard graph and return warnings."""

    steps = _coerce_steps(router_or_config)
    step_keys = [step.key for step in steps]
    step_map = {step.key: step for step in steps}
    warnings: list[str] = []

    forward_targets: dict[str, list[str]] = {}
    conditional_checks: dict[str, BranchEdge] = {}
    for step in steps:
        edges = _resolve_forward_edges(step, steps, step_map)
        forward_targets[step.key] = [edge.target for edge in edges if edge.target]
        for edge in edges:
            if edge.conditional:
                conditional_checks[step.key] = edge
            if edge.target and edge.target not in step_map:
                warnings.append(f"Step '{step.key}' links to unknown target '{edge.target}'.")

    for key, targets in forward_targets.items():
        if not targets and key != step_keys[-1]:
            warnings.append(f"Step '{key}' has no forward path.")

    for key, edge in conditional_checks.items():
        if edge.conditional and not edge.has_else:
            warnings.append(f"Step '{key}' has a conditional branch without an else path.")

    return warnings


def _coerce_steps(router_or_config: Sequence[StepLike] | object) -> Sequence[StepLike]:
    if isinstance(router_or_config, Sequence):
        return router_or_config
    pages = getattr(router_or_config, "pages", None)
    if pages is None:
        raise TypeError("router_or_config must be a step sequence or expose .pages")
    return pages


def _resolve_forward_edges(
    step: StepLike,
    steps: Sequence[StepLike],
    step_map: Mapping[str, StepLike],
) -> list[BranchEdge]:
    if step.next_step_id is None:
        next_key = _default_next_key(step, steps)
        if not next_key:
            return []
        return [BranchEdge(target=next_key, label=None, conditional=False, has_else=True)]

    branch_edges = _extract_branch_edges(step.next_step_id)
    if branch_edges:
        return branch_edges

    context = WizardContext(schema={}, critical_fields=())
    try:
        resolved = step.next_step_id(context, {})
    except Exception:
        resolved = None
    if isinstance(resolved, str) and resolved:
        if resolved in step_map:
            return [
                BranchEdge(
                    target=resolved,
                    label=step.next_step_id.__name__,
                    conditional=False,
                    has_else=True,
                )
            ]
    return []


def _extract_branch_edges(resolver: StepNextResolver) -> list[BranchEdge]:
    """Best-effort AST parsing to detect conditional return paths."""

    try:
        source = inspect.getsource(resolver)
    except (OSError, TypeError):
        return []

    try:
        parsed = ast.parse(source)
    except SyntaxError:
        return []

    func_node = next(
        (node for node in parsed.body if isinstance(node, ast.FunctionDef)),
        None,
    )
    if func_node is None:
        return []

    return_node = _find_first_return(func_node.body)
    if return_node is None:
        return []

    if isinstance(return_node.value, ast.IfExp):
        condition = _source_segment(source, return_node.value.test) or "condition"
        true_value = _extract_string_constant(return_node.value.body)
        false_value = _extract_string_constant(return_node.value.orelse)
        edges: list[BranchEdge] = []
        if true_value:
            edges.append(
                BranchEdge(
                    target=true_value,
                    label=str(condition),
                    conditional=True,
                    has_else=bool(false_value),
                )
            )
        if false_value:
            edges.append(
                BranchEdge(
                    target=false_value,
                    label="else",
                    conditional=True,
                    has_else=True,
                )
            )
        return edges

    if isinstance(return_node.value, ast.Constant) and isinstance(return_node.value.value, str):
        return [
            BranchEdge(
                target=return_node.value.value,
                label=None,
                conditional=False,
                has_else=True,
            )
        ]

    if isinstance(return_node.value, ast.Call):
        return []

    return []


def _find_first_return(nodes: Iterable[ast.stmt]) -> ast.Return | None:
    for node in nodes:
        if isinstance(node, ast.Return):
            return node
        if isinstance(node, ast.If):
            return_node = _find_first_return(node.body)
            if return_node:
                return return_node
            return_node = _find_first_return(node.orelse)
            if return_node:
                return return_node
    return None


def _extract_string_constant(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _source_segment(source: str, node: ast.AST) -> str | None:
    try:
        segment = ast.get_source_segment(source, node)
    except AttributeError:
        segment = None
    if not segment:
        return None
    return " ".join(segment.split())


def _default_next_key(step: StepLike, steps: Sequence[StepLike]) -> str | None:
    index = next((i for i, candidate in enumerate(steps) if candidate.key == step.key), None)
    if index is None or index + 1 >= len(steps):
        return None
    return steps[index + 1].key


def _format_label(label_pair: tuple[str, str]) -> str:
    if label_pair[0] == label_pair[1]:
        return label_pair[0]
    return f"{label_pair[0]} / {label_pair[1]}"


def _sanitize_label(label: str | None) -> str | None:
    if not label:
        return None
    sanitized = label.replace("|", "/").replace("\n", " ")
    return sanitized


def _node_id(key: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in key)
    return f"step_{safe}"
