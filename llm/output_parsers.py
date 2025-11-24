"""LangChain-based output parser helpers for structured extraction."""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from functools import lru_cache
from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any

from langchain.output_parsers import (
    PydanticOutputParser,
    ResponseSchema,
    StructuredOutputParser,
)
from langchain.schema import OutputParserException
from pydantic import ValidationError

from core.schema import canonicalize_profile_payload
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
        errors: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.raw_text = raw_text
        self.data = data
        self.original = original
        self.errors: Sequence[Mapping[str, Any]] | None = errors


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
                        "Return null for unknown primitive values and empty arrays when no entries are available. "
                        "Do not omit any required fields; include empty strings or empty objects when information is missing."
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

        if isinstance(payload, Mapping):
            target = dict(payload)
        else:
            return None
        return canonicalize_profile_payload(target)

    @staticmethod
    def _has_text(value: Any) -> bool:
        return isinstance(value, str) and value.strip() != ""

    @classmethod
    def _sequence_has_text(cls, value: Any) -> bool:
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return any(cls._has_text(item) for item in value)
        return False

    @classmethod
    def _collect_missing_sections(cls, profile: NeedAnalysisProfile) -> list[str]:
        missing: list[str] = []
        if not cls._sequence_has_text(profile.responsibilities.items):
            missing.append("responsibilities.items")
        if not cls._has_text(profile.company.culture):
            missing.append("company.culture")
        process_overview_values = (
            profile.process.recruitment_timeline,
            profile.process.process_notes,
            profile.process.application_instructions,
        )
        has_hiring_steps = cls._sequence_has_text(profile.process.hiring_process) or cls._has_text(
            profile.process.hiring_process
        )
        if not any(cls._has_text(value) for value in process_overview_values) and not has_hiring_steps:
            missing.append("process.overview")
        return missing

    @staticmethod
    def _has_interview_stage_error(validation_error: Exception) -> bool:
        """Return ``True`` when ``process.interview_stages`` caused validation issues."""

        error_iterator: Sequence[Mapping[str, Any]] | None = None
        if isinstance(validation_error, ValidationError):
            error_iterator = validation_error.errors()
        elif hasattr(validation_error, "errors"):
            maybe_errors = getattr(validation_error, "errors")
            if callable(maybe_errors):  # pragma: no cover - defensive
                try:
                    error_iterator = maybe_errors()
                except Exception:
                    error_iterator = None
        if not error_iterator:
            return False

        for error in error_iterator:
            raw_location = error.get("loc", ())
            if not isinstance(raw_location, (list, tuple)):
                continue
            location = tuple(raw_location)
            if len(location) >= 2 and tuple(location[:2]) == ("process", "interview_stages"):
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

    @staticmethod
    def _format_error_location(location: Sequence[Any]) -> str:
        """Return dotted label for ``location`` entries."""

        if not location:
            return ""
        formatted: list[str] = []
        for part in location:
            if isinstance(part, int):
                if not formatted:
                    formatted.append(f"[{part}]")
                else:
                    formatted[-1] = f"{formatted[-1]}[{part}]"
                continue
            formatted.append(str(part))
        return ".".join(formatted)

    @staticmethod
    def _remove_location_value(target: Any, location: Sequence[Any]) -> bool:
        """Drop the value pointed to by ``location`` inside ``target``."""

        cursor: Any = target
        for index, part in enumerate(location):
            is_last = index == len(location) - 1
            if is_last:
                if isinstance(part, int) and isinstance(cursor, list):
                    if 0 <= part < len(cursor):
                        del cursor[part]
                        return True
                    return False
                if isinstance(part, str) and isinstance(cursor, MutableMapping):
                    if part in cursor:
                        cursor.pop(part)
                        return True
                    return False
                return False
            if isinstance(part, int):
                if isinstance(cursor, list) and 0 <= part < len(cursor):
                    cursor = cursor[part]
                else:
                    return False
            else:
                if isinstance(cursor, MutableMapping) and part in cursor:
                    cursor = cursor[part]
                else:
                    return False
        return False

    @classmethod
    def _prune_invalid_fields(
        cls,
        payload: MutableMapping[str, Any],
        errors: Sequence[Mapping[str, Any]] | None,
    ) -> list[str]:
        """Remove invalid paths referenced in ``errors`` from ``payload``."""

        removed: list[str] = []
        if not errors:
            return removed
        seen: set[str] = set()
        for entry in errors:
            loc = entry.get("loc")
            if not isinstance(loc, (list, tuple)) or not loc:
                continue
            label = cls._format_error_location(loc)
            if not label:
                label = "<root>"
            if label in seen:
                continue
            if cls._remove_location_value(payload, loc):
                removed.append(label)
                seen.add(label)
        return removed

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
        except (ValidationError, OutputParserException) as validation_error:
            canonical_data = self._canonicalize_payload(data)
            error_details: Sequence[Mapping[str, Any]] | None = None
            if isinstance(validation_error, ValidationError):
                error_details = validation_error.errors()
            elif hasattr(validation_error, "errors"):
                maybe_errors = getattr(validation_error, "errors")
                if callable(maybe_errors):  # pragma: no cover - defensive
                    try:
                        error_details = list(maybe_errors())
                    except Exception:
                        error_details = None
            canonical_validation_error: ValidationError | None = None
            if canonical_data is not None:
                try:
                    fallback_model = NeedAnalysisProfile.model_validate(canonical_data)
                except ValidationError as canonical_error:
                    canonical_validation_error = canonical_error
                else:
                    logger.info("NeedAnalysis payload validated after schema canonicalization.")
                    return fallback_model, canonical_data
            if canonical_validation_error is not None:
                validation_error = canonical_validation_error
                error_details = canonical_validation_error.errors()
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
                    logger.info("NeedAnalysis payload normalized after interview_stages list fallback.")
                    return fallback_model, canonical_data
                data = canonical_data
            repaired_payload: Mapping[str, Any] | None = None
            if canonical_data is not None:
                repaired_payload = repair_profile_payload(
                    canonical_data,
                    errors=error_details,
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
            if canonical_data is not None and error_details:
                trimmed_data = deepcopy(canonical_data)
                removed_paths = self._prune_invalid_fields(trimmed_data, error_details)
                if removed_paths:
                    try:
                        trimmed_model = NeedAnalysisProfile.model_validate(trimmed_data)
                    except ValidationError as trimmed_error:
                        logger.debug(
                            "Validation failed after removing invalid fields: %s",
                            trimmed_error,
                        )
                    else:
                        logger.warning(
                            "NeedAnalysis payload removed invalid fields to preserve data: %s",
                            ", ".join(removed_paths),
                        )
                        return trimmed_model, trimmed_data
            raise NeedAnalysisParserError(
                "Structured extraction failed Pydantic validation.",
                raw_text=candidate,
                data=canonical_data or (data if isinstance(data, dict) else None),
                original=validation_error,
                errors=error_details,
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

        missing_sections = self._collect_missing_sections(model)
        if missing_sections:
            error_locations = []
            for section in missing_sections:
                loc = tuple(part for part in section.split(".") if part)
                error_locations.append({"loc": loc or (section,), "msg": "missing"})
            raise NeedAnalysisParserError(
                "Structured extraction is missing critical sections.",
                raw_text=candidate,
                data=data if isinstance(data, dict) else None,
                errors=error_locations,
            )

        return model, data


@lru_cache(maxsize=1)
def get_need_analysis_output_parser() -> NeedAnalysisOutputParser:
    """Return the singleton NeedAnalysis output parser."""

    return NeedAnalysisOutputParser()
