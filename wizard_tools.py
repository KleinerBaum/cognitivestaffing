# wizard_tools.py
from __future__ import annotations

import json
from typing import Any, Literal, Optional, List, Dict
from pydantic import BaseModel, Field

# Agents SDK
from agents import function_tool

# ---------- Shared types ----------

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

# ---------- A) Graph & Stage Management ----------

@function_tool
def add_stage(
    name: str,
    description: str = "Stage in the journey",
    kind: StageKind = "utility",
    required_fields: Optional[List[str]] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Create a wizard stage node and return {"stage_id": "..."}.
    Args:
      name: Human-readable title.
      description: What happens in this step.
      kind: Category that drives defaults (ingest/extract/qa/validate/enrich/generate/export/utility).
      required_fields: Schema fields this step must fill.
      meta: Arbitrary step configuration (e.g., model, effort).
    """
    # TODO: Persist to your store and return real id
    return json.dumps({"stage_id": f"stage_{name.lower().replace(' ','_')}"})

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
    """
    Connect two stages (DAG). Returns {"edge_id": "..."}.
    Args:
      from_stage_id: Source node id.
      to_stage_id: Target node id.
      edge_label: Optional label (e.g., "on_success").
    """
    return json.dumps({"edge_id": f"edge_{from_stage_id}_to_{to_stage_id}"})

@function_tool
def disconnect(edge_id: str) -> str:
    """Remove an edge. Returns {"removed": true}."""
    return json.dumps({"removed": True, "edge_id": edge_id})

@function_tool
def list_graph(vacancy_id: str) -> str:
    """Return the full graph JSON for a vacancy."""
    # TODO: Load from storage
    return json.dumps({"vacancy_id": vacancy_id, "graph": {"stages": [], "edges": []}})

@function_tool
def save_graph(vacancy_id: str, graph: GraphState) -> str:
    """Persist the graph layout + metadata. Returns {"saved": true}."""
    return json.dumps({"vacancy_id": vacancy_id, "saved": True})

@function_tool
def load_graph(vacancy_id: str) -> str:
    """Load graph if present. Returns {"graph": {...}}."""
    return json.dumps({"vacancy_id": vacancy_id, "graph": {"stages": [], "edges": []}})

# ---------- B) Vacancy Data Operations ----------

@function_tool
def upload_jobad(
    source_url: Optional[str] = None,
    file_id: Optional[str] = None,
    text: Optional[str] = None,
) -> str:
    """
    Normalize a job ad into text + metadata. One of source_url, file_id or text must be provided.
    Returns: {"text": "...", "metadata": {...}}
    """
    norm_text = text or f"// fetched from {source_url or file_id}"
    return json.dumps({"text": norm_text, "metadata": {"source_url": source_url, "file_id": file_id}})

class ExtractionConfig(BaseModel):
    schema_version: str = "v1"
    language: Optional[str] = None
    strict_json: bool = True

@function_tool
def extract_vacancy_fields(text: str, config: ExtractionConfig) -> str:
    """
    Run structured extraction to the vacancy schema.
    Returns: {"profile": {...}, "confidence": 0..1}
    """
    # TODO: call Responses API with JSON schema for deterministic fields
    return json.dumps({"profile": {"title": "Software Engineer"}, "confidence": 0.83})

@function_tool
def detect_gaps(profile_json: Dict[str, Any]) -> str:
    """Return list of missing/ambiguous fields. {"gaps":[{"field":"benefits", "reason":"missing"}]}"""
    # TODO: compute from schema
    return json.dumps({"gaps": [{"field": "benefits", "reason": "missing"}]})

@function_tool
def generate_followups(profile_json: Dict[str, Any], role_context: Optional[str] = None) -> str:
    """Produce prioritized follow-up Qs for SMEs. Returns {"questions":[...]}"""
    return json.dumps({"questions": ["What are the core benefits?", "Travel requirements?"]})

@function_tool
def ingest_answers(qa_pairs: List[Dict[str, str]], profile_json: Dict[str, Any]) -> str:
    """Merge SME answers into the profile. Returns {"profile": {...}}"""
    profile_json["answers"] = qa_pairs
    return json.dumps({"profile": profile_json})

class ValidationConfig(BaseModel):
    jurisdiction: Optional[str] = None
    constraints: Optional[Dict[str, Any]] = None

@function_tool
def validate_profile(profile_json: Dict[str, Any], config: ValidationConfig) -> str:
    """Validate profile (comp bands, location, legal). Returns {"ok": bool, "issues":[...] }"""
    return json.dumps({"ok": True, "issues": []})

@function_tool
def map_esco_skills(profile_json: Dict[str, Any]) -> str:
    """Map skills to ESCO taxonomy with levels. Returns {"skills":[...]}"""
    return json.dumps({"skills": [{"name": "Python", "level": "advanced"}]})

@function_tool
def market_salary_enrich(profile_json: Dict[str, Any], region: str) -> str:
    """Attach market salary ranges + rationale. Returns {"salary":{"min":...,"max":...}}"""
    return json.dumps({"salary": {"min": 60000, "max": 90000, "currency": "EUR", "region": region}})

@function_tool
def generate_jd(profile_json: Dict[str, Any], tone: str = "professional", lang: str = "en") -> str:
    """Generate Job Description variants. Returns {"drafts":[{"kind":"short","text":"..."}, ...]}"""
    return json.dumps({"drafts": [{"kind": "short", "text": "JD short..."}, {"kind": "long", "text": "JD long..."}]})

@function_tool
def export_profile(profile_json: Dict[str, Any], format: Literal["json","csv","docx"]="json") -> str:
    """Export the profile in a given format. Returns {"file_url": "..."}"""
    return json.dumps({"file_url": f"https://files/export/profile.{format}"})

# ---------- C) RAG / Knowledge ----------

@function_tool
def index_documents(files: List[str]) -> str:
    """Add files to vector store for File Search. Returns {"indexed": n}"""
    return json.dumps({"indexed": len(files)})

@function_tool
def semantic_search(query: str, k: int = 5) -> str:
    """Search vector store. Returns {"passages":[{"text":"...","source":"..."}]}"""
    return json.dumps({"passages": [{"text": "…", "source": "doc1.pdf"}]})

@function_tool
def attach_context(stage_id: str, passages: List[Dict[str, str]]) -> str:
    """Associate retrieved passages with a stage. Returns {"attached": true}"""
    return json.dumps({"attached": True, "stage_id": stage_id})

# ---------- D) Execution Control & Reasoning ----------

@function_tool
def run_stage(stage_id: str, inputs: Optional[Dict[str, Any]] = None) -> str:
    """
    Execute the stage’s domain op. Returns {"stage_id": "...", "outputs": {...}, "reasoning_summary": "..."}.
    The Agent should set reasoning effort & model via per-stage meta.
    """
    return json.dumps({"stage_id": stage_id, "outputs": {"ok": True}, "reasoning_summary": "Executed."})

@function_tool
def run_all(vacancy_id: str) -> str:
    """Run all stages topologically. Returns {"vacancy_id":"...", "completed": true}"""
    return json.dumps({"vacancy_id": vacancy_id, "completed": True})

@function_tool
def retry_stage(stage_id: str, strategy: Literal["same_inputs","regenerate","raise_effort"]="regenerate") -> str:
    """Retry a failed or low-confidence stage. Returns {"retried": true}"""
    return json.dumps({"stage_id": stage_id, "retried": True, "strategy": strategy})

@function_tool
def set_model(stage_id: Optional[str], model: Literal["gpt-5-nano","gpt-5-mini"]) -> str:
    """Set model for a stage or globally if stage_id is None. Returns {"ok": true}"""
    return json.dumps({"ok": True, "stage_id": stage_id, "model": model})

@function_tool
def set_reasoning_effort(stage_id: Optional[str], level: Literal["minimal","medium","high"]="minimal") -> str:
    """Set GPT-5 reasoning effort for a stage or globally. Returns {"ok": true}"""
    return json.dumps({"ok": True, "stage_id": stage_id, "level": level})

@function_tool
def set_tool_choice(stage_id: Optional[str], mode: Literal["auto","none","force"]= "auto", function_name: Optional[str]=None) -> str:
    """Control tool selection. If mode=='force', provide function_name. Returns {"ok": true}"""
    return json.dumps({"ok": True, "stage_id": stage_id, "mode": mode, "function_name": function_name})

@function_tool
def set_temperature(stage_id: Optional[str], value: float = 0.2) -> str:
    """Set sampling temperature (0..2)."""
    return json.dumps({"ok": True, "stage_id": stage_id, "temperature": value})

@function_tool
def set_max_output_tokens(stage_id: Optional[str], value: int = 2048) -> str:
    """Cap output tokens for a stage/global."""
    return json.dumps({"ok": True, "stage_id": stage_id, "max_output_tokens": value})

# ---------- E) Safety / PII / Logging ----------

@function_tool
def redact_pii(text: str) -> str:
    """Mask PII before persistence. Returns {"redacted":"..."}"""
    return json.dumps({"redacted": text})

@function_tool
def log_event(vacancy_id: str, stage_id: Optional[str], kind: str, payload: Dict[str, Any]) -> str:
    """Telemetry audit event."""
    return json.dumps({"logged": True})

@function_tool
def get_run(run_id: str) -> str:
    """Fetch a run’s tool calls + outputs for replay. Returns {"run": {...}}"""
    return json.dumps({"run": {"id": run_id, "items": []}})
