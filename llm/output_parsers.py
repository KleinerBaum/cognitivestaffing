"""LangChain-based output parser helpers for structured extraction."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any, Mapping

try:  # pragma: no cover - dependency differences
    from langchain.output_parsers import (
        PydanticOutputParser,
        ResponseSchema,
        StructuredOutputParser,
    )
except ImportError:  # pragma: no cover - langchain>=1.0 moved these classes
    from langchain_core.output_parsers import (  # type: ignore[no-redef]
        PydanticOutputParser,
        ResponseSchema,
        StructuredOutputParser,
    )
from langchain.schema import OutputParserException
from pydantic import ValidationError

from llm.json_repair import repair_profile_payload
from llm.profile_normalization import normalize_interview_stages_field
from models.need_analysis import NeedAnalysisProfile

logger = logging.getLogger(__name__)


class NeedAnalysisParserError(ValueError):
    """Raised when the NeedAnalysis parser cannot coerce a payload."""

    def __init__(
        self,
        message: str,
        *,
        raw_text: str,
        data: dict[str, Any] | None,
        original: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.raw_text = raw_text
        self.data = data
        self.original = original


class NeedAnalysisOutputParser:
    """Combine LangChain structured parsers for NeedAnalysis payloads."""

    def __init__(self) -> None:
        self._pydantic_parser = PydanticOutputParser(pydantic_object=NeedAnalysisProfile)
        self._structured_parser = StructuredOutputParser.from_response_schemas(
            [
                ResponseSchema(
                    name="profile",
                    description=(
                        "JSON object that strictly matches the NeedAnalysisProfile schema. "
                        "Return null for unknown primitive values and empty arrays when no entries are available."
                    ),
                )
            ]
        )

    @property
    def format_instructions(self) -> str:
        """Return combined formatting instructions for prompts."""

        return "\n\n".join(
            (
                "Use the following structured output format.",
                self._structured_parser.get_format_instructions(),
                "Embed only the NeedAnalysisProfile JSON object without commentary.",
                self._pydantic_parser.get_format_instructions(),
            )
        )

    @staticmethod
    def _canonicalize_payload(payload: Any) -> dict[str, Any] | None:
        """Return a canonical dict payload when ``payload`` is mapping-like."""

        if isinstance(payload, dict):
            target: dict[str, Any] = payload
        elif isinstance(payload, Mapping):
            target = dict(payload)
        else:
            return None
        normalize_interview_stages_field(target)
        return target

    def parse(self, text: str) -> tuple[NeedAnalysisProfile, dict[str, Any]]:
        """Parse ``text`` and return the Pydantic model along with the raw dict."""

        candidate = text
        try:
            structured = self._structured_parser.parse(text)
        except OutputParserException:
            structured = None
        if structured and isinstance(structured, dict) and "profile" in structured:
            payload = structured["profile"]
            if isinstance(payload, str):
                candidate = payload
            else:
                candidate = json.dumps(payload)

        try:
            data = json.loads(candidate)
        except json.JSONDecodeError as err:
            raise NeedAnalysisParserError(
                "Structured extraction did not return valid JSON.",
                raw_text=candidate,
                data=None,
                original=err,
            ) from err

        if isinstance(data, dict):
            normalize_interview_stages_field(data)
            candidate = json.dumps(data)

        try:
            parsed = self._pydantic_parser.parse(candidate)
        except ValidationError as validation_error:
            canonical_data = self._canonicalize_payload(data)
            repaired_payload: Mapping[str, Any] | None = None
            if canonical_data is not None:
                repaired_payload = repair_profile_payload(
                    canonical_data,
                    errors=validation_error.errors(),
                )
            if repaired_payload:
                repaired_data = self._canonicalize_payload(dict(repaired_payload))
                if repaired_data is None:
                    repaired_data = dict(repaired_payload)
                    normalize_interview_stages_field(repaired_data)
                try:
                    repaired_model = NeedAnalysisProfile.model_validate(repaired_data)
                except ValidationError as repaired_error:
                    repaired_raw = json.dumps(repaired_data)
                    raise NeedAnalysisParserError(
                        "Repaired NeedAnalysis payload failed validation.",
                        raw_text=repaired_raw,
                        data=repaired_data,
                        original=repaired_error,
                    ) from repaired_error
                logger.info("NeedAnalysis payload repaired after validation failure.")
                return repaired_model, repaired_data
            raise NeedAnalysisParserError(
                "Structured extraction failed Pydantic validation.",
                raw_text=candidate,
                data=canonical_data or (data if isinstance(data, dict) else None),
                original=validation_error,
            ) from validation_error
        except Exception as err:  # pragma: no cover - LangChain wraps other exceptions
            raise NeedAnalysisParserError(
                "Structured extraction failed due to an unexpected error.",
                raw_text=candidate,
                data=data if isinstance(data, dict) else None,
                original=err,
            ) from err

        if isinstance(parsed, NeedAnalysisProfile):
            model = parsed
        elif isinstance(parsed, dict):  # pragma: no cover - safety net
            model = NeedAnalysisProfile.model_validate(parsed)
        else:  # pragma: no cover - defensive
            model = NeedAnalysisProfile.model_validate(json.loads(parsed.model_dump_json()))

        return model, data


@lru_cache(maxsize=1)
def get_need_analysis_output_parser() -> NeedAnalysisOutputParser:
    """Return the singleton NeedAnalysis output parser."""

    return NeedAnalysisOutputParser()
