"""Evidence entities for Need Analysis V2."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


EvidenceSource = Literal["user", "llm", "heuristic", "import"]


class EvidenceItem(BaseModel):
    """Traceable evidence for a field value."""

    model_config = ConfigDict(extra="forbid")

    field_path: str
    value: Any = None
    source: EvidenceSource = "import"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    excerpt: str = ""
