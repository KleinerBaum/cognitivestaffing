"""Graph and stage management tools for the wizard."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from agents import function_tool

StageKind = Literal["ingest", "extract", "qa", "validate", "enrich", "generate", "export", "utility"]


class StagePatch(BaseModel):
    name: Optional[str] = Field(None, description="New title for the stage.")
    description: Optional[str] = Field(None, description="Long description.")
    kind: Optional[StageKind] = None
    required_fields: Optional[List[str]] = None
    meta: Optional[Dict[str, Any]] = None


class GraphState(BaseModel):
    stages: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


@function_tool
def add_stage(
    name: str,
    description: str = "Stage in the journey",
    kind: str = "utility",
    required_fields: Optional[List[str]] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> str:
    """Create a wizard stage node and return {"stage_id": "..."}."""

    stage_id = f"stage_{name.lower().replace(' ', '_')}"
    return json.dumps(
        {
            "stage_id": stage_id,
            "name": name,
            "description": description,
            "kind": kind,
            "required_fields": required_fields or [],
            "meta": meta or {},
        }
    )


@function_tool
def update_stage(stage_id: str, patch: StagePatch) -> str:
    """Update a stage in place. Returns {"stage_id": "...", "updated": true}."""

    return json.dumps({"stage_id": stage_id, "updated": True, "patch": patch.model_dump()})


@function_tool
def remove_stage(stage_id: str) -> str:
    """Delete a stage and incident edges. Returns {"removed": true}."""

    return json.dumps({"removed": True, "stage_id": stage_id})


@function_tool
def connect_stages(from_stage_id: str, to_stage_id: str, edge_label: Optional[str] = None) -> str:
    """Connect two stages (DAG). Returns {"edge_id": "..."}."""

    edge_id = f"edge_{from_stage_id}_to_{to_stage_id}"
    return json.dumps({
        "edge_id": edge_id,
        "from": from_stage_id,
        "to": to_stage_id,
        "label": edge_label,
    })


@function_tool
def disconnect(edge_id: str) -> str:
    """Remove an edge. Returns {"removed": true}."""

    return json.dumps({"removed": True, "edge_id": edge_id})


@function_tool
def list_graph(vacancy_id: str) -> str:
    """Return the full graph JSON for a vacancy."""

    return json.dumps({"vacancy_id": vacancy_id, "graph": {"stages": [], "edges": []}})


@function_tool
def save_graph(vacancy_id: str, graph: GraphState) -> str:
    """Persist the graph layout + metadata. Returns {"saved": true}."""

    return json.dumps(
        {
            "vacancy_id": vacancy_id,
            "saved": True,
            "stages": graph.stages,
            "edges": graph.edges,
        }
    )


@function_tool
def load_graph(vacancy_id: str) -> str:
    """Load graph if present. Returns {"graph": {...}}."""

    return json.dumps({"vacancy_id": vacancy_id, "graph": {"stages": [], "edges": []}})


__all__ = [
    "StageKind",
    "GraphState",
    "StagePatch",
    "add_stage",
    "connect_stages",
    "disconnect",
    "list_graph",
    "load_graph",
    "remove_stage",
    "save_graph",
    "update_stage",
]
