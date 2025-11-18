"""LangChain-based output parser helpers for structured extraction."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any

try:  # pragma: no cover - dependency differences
    from langchain.output_parsers import (
        PydanticOutputParser,
        ResponseSchema,
        StructuredOutputParser,
    )
except ImportError:  # pragma: no cover - langchain>=1.0 moved these classes
    from langchain_core.output_parsers import (  # type: ignore[import-not-found]
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
                (
                    "Embed only the NeedAnalysisProfile JSON object without commentary. "
                    "Always express process.interview_stages as an integer (count of stages) or null."
                ),
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

    @staticmethod
    def _has_interview_stage_error(validation_error: ValidationError) -> bool:
        """Return ``True`` when ``process.interview_stages`` caused validation issues."""

        for error in validation_error.errors():
            location = tuple(error.get("loc", ()))
            if location == ("process", "interview_stages"):
                return True
        return False

    @staticmethod
    def _coerce_stage_list(payload: MutableMapping[str, Any]) -> bool:
        """Convert ``process.interview_stages`` lists to integers when present."""

        process = payload.get("process")
        if not isinstance(process, MutableMapping):
            return False

        stages = process.get("interview_stages")
        if isinstance(stages, Sequence) and not isinstance(stages, (str, bytes, bytearray)):
            normalize_interview_stages_field(payload)
            return not isinstance(process.get("interview_stages"), Sequence)
        return False

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
            if (
                canonical_data is not None
                and self._has_interview_stage_error(validation_error)
                and self._coerce_stage_list(canonical_data)
            ):
                try:
                    fallback_model = NeedAnalysisProfile.model_validate(canonical_data)
                except ValidationError as fallback_error:
                    validation_error = fallback_error
                else:
                    logger.info(
                        "NeedAnalysis payload normalized after interview_stages list fallback."
                    )
                    return fallback_model, canonical_data
                data = canonical_data
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
