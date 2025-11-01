"""LangChain-based output parser helpers for structured extraction."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from langchain.output_parsers import (
    PydanticOutputParser,
    ResponseSchema,
    StructuredOutputParser,
)
from langchain.schema import OutputParserException

from models.need_analysis import NeedAnalysisProfile


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

        try:
            parsed = self._pydantic_parser.parse(candidate)
        except Exception as err:  # pragma: no cover - LangChain wraps ValidationError
            raise NeedAnalysisParserError(
                "Structured extraction failed Pydantic validation.",
                raw_text=candidate,
                data=data,
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

