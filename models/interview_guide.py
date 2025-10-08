"""Pydantic models representing interview guide outputs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class InterviewGuideQuestion(BaseModel):
    """Single question with guidance for the interview panel."""

    model_config = ConfigDict(extra="ignore")

    question: str = Field(default="", description="Question wording for the interviewer to ask.")
    focus: str = Field(default="", description="Key capability or topic the question targets.")
    evaluation: str = Field(
        default="",
        description="Guidance on what good answers look like or how to score responses.",
    )

    def trimmed(self) -> "InterviewGuideQuestion":
        """Return a copy with leading/trailing whitespace removed."""

        return self.model_copy(
            update={
                "question": self.question.strip(),
                "focus": self.focus.strip(),
                "evaluation": self.evaluation.strip(),
            }
        )


class InterviewGuideFocusArea(BaseModel):
    """Focus sections to highlight capabilities or themes."""

    model_config = ConfigDict(extra="ignore")

    label: str = Field(default="", description="Heading for the focus area.")
    items: list[str] = Field(default_factory=list, description="Bullet items belonging to the area.")

    def trimmed(self) -> "InterviewGuideFocusArea":
        """Return a copy with whitespace removed and empty entries filtered out."""

        cleaned_items = [item.strip() for item in self.items if str(item).strip()]
        return self.model_copy(
            update={
                "label": self.label.strip(),
                "items": cleaned_items,
            }
        )


class InterviewGuideMetadata(BaseModel):
    """Context information used to render the guide."""

    model_config = ConfigDict(extra="ignore")

    language: str = Field(default="de", description="Locale code (e.g. 'de' or 'en').")
    heading: str = Field(default="", description="Display heading for the guide document.")
    job_title: str = Field(default="", description="Job title or role name.")
    audience: str = Field(default="", description="Audience short code or identifier.")
    audience_label: str | None = Field(
        default=None, description="Localised label describing the interview audience."
    )
    tone: str = Field(default="", description="Tone descriptor supplied by the user or model.")
    tone_label: str | None = Field(
        default=None, description="Optional localised label to render the tone heading."
    )
    culture_note: str | None = Field(
        default=None,
        description="Optional description of the company culture to remind the panel.",
    )

    def normalised_language(self) -> str:
        """Return a simplified language identifier ('de' or 'en')."""

        lang = (self.language or "de").lower()
        return "de" if lang.startswith("de") else "en"


class InterviewGuide(BaseModel):
    """Structured representation of an interview guide."""

    model_config = ConfigDict(extra="ignore")

    metadata: InterviewGuideMetadata
    questions: list[InterviewGuideQuestion] = Field(default_factory=list)
    focus_areas: list[InterviewGuideFocusArea] = Field(default_factory=list)
    evaluation_notes: list[str] = Field(
        default_factory=list,
        description="General guidance for the panel when assessing answers.",
    )
    markdown: str | None = Field(
        default=None,
        description="Optional Markdown representation provided by the model.",
    )

    def _labels(self) -> tuple[str, str, str, str, str]:
        """Return translated labels for document sections."""

        lang = self.metadata.normalised_language()
        if lang == "de":
            return (
                "Interviewleitfaden",
                "Zielgruppe",
                "Tonfall",
                "Unternehmenskultur",
                "Fragen & Bewertungsleitfaden",
            )
        return (
            "Interview Guide",
            "Intended audience",
            "Tone",
            "Company culture",
            "Questions & evaluation guide",
        )

    def _focus_heading(self) -> str:
        return "Fokusbereiche" if self.metadata.normalised_language() == "de" else "Focus areas"

    def _question_labels(self) -> tuple[str, str]:
        if self.metadata.normalised_language() == "de":
            return "Fokus", "Bewertungshinweise"
        return "Focus", "Evaluation guidance"

    def _evaluation_heading(self) -> str:
        return (
            "Bewertungsschwerpunkte"
            if self.metadata.normalised_language() == "de"
            else "Evaluation notes"
        )

    def render_markdown(self) -> str:
        """Render a Markdown document from the structured content."""

        heading_label, audience_label, tone_label, culture_label, questions_heading = self._labels()
        focus_heading = self._focus_heading()
        focus_label, evaluation_label = self._question_labels()
        evaluation_heading = self._evaluation_heading()

        metadata = self.metadata
        trimmed_focus = [area.trimmed() for area in self.focus_areas if area]
        trimmed_questions = [question.trimmed() for question in self.questions if question]
        trimmed_notes = [note.strip() for note in self.evaluation_notes if str(note).strip()]

        heading_text = metadata.heading.strip()
        if not heading_text:
            job_title = metadata.job_title.strip()
            if metadata.normalised_language() == "de":
                heading_text = f"{heading_label} – {job_title or 'diese Position'}"
            else:
                heading_text = f"{heading_label} – {job_title or 'this role'}"

        lines: list[str] = [heading_text, ""]

        audience_text = (metadata.audience_label or metadata.audience or "").strip()
        if audience_text:
            lines.append(f"**{audience_label}:** {audience_text}")

        tone_text = (metadata.tone_label or metadata.tone or "").strip()
        if tone_text:
            lines.append(f"**{tone_label}:** {tone_text}")

        culture_text = (metadata.culture_note or "").strip()
        if culture_text:
            lines.append(f"**{culture_label}:** {culture_text}")

        if trimmed_notes:
            lines.append("")
            lines.append(f"## {evaluation_heading}")
            for note in trimmed_notes:
                lines.append(f"- {note}")

        if trimmed_focus:
            lines.append("")
            lines.append(f"## {focus_heading}")
            for area in trimmed_focus:
                label = area.label.strip()
                items = [item.strip() for item in area.items if item.strip()]
                if not (label or items):
                    continue
                if label and items:
                    lines.append(f"- **{label}:** {', '.join(items)}")
                elif label:
                    lines.append(f"- {label}")
                elif items:
                    lines.append(f"- {', '.join(items)}")

        if trimmed_questions:
            lines.append("")
            lines.append(f"## {questions_heading}")
            for idx, question in enumerate(trimmed_questions, start=1):
                question_text = question.question or ""
                focus_text = question.focus or ""
                evaluation_text = question.evaluation or ""
                lines.append("")
                lines.append(f"### {idx}. {question_text}")
                if focus_text:
                    lines.append(f"- **{focus_label}:** {focus_text}")
                if evaluation_text:
                    lines.append(f"- **{evaluation_label}:** {evaluation_text}")

        return "\n".join(lines).strip()

    def final_markdown(self) -> str:
        """Return the provided Markdown or a rendered version."""

        provided = (self.markdown or "").strip()
        if provided:
            return provided
        return self.render_markdown()

    def ensure_markdown(self) -> "InterviewGuide":
        """Return a copy with Markdown populated."""

        return self.model_copy(update={"markdown": self.final_markdown()})
