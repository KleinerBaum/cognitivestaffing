import base64
import json
import sys
import types
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import ingest.extractors as extractors
import llm.client as llm_client
import openai_utils
import question_logic
from constants.keys import StateKeys, UIKeys
from models.need_analysis import NeedAnalysisProfile
from openai_utils.extraction import ExtractionResult
import wizard
from ingest.reader import clean_structured_document


class StubUploadedFile(BytesIO):
    """Simple uploaded file stand-in with a name attribute."""

    def __init__(self, data: bytes, name: str) -> None:
        super().__init__(data)
        self.name = name
        self.type = "application/pdf"


@pytest.mark.parametrize(
    "lang, expected",
    [
        (
            "de",
            {
                "heading": "**Vorgeschlagene Fragen:**",
                "info": "Der Assistent hat Anschlussfragen, um fehlende Angaben zu ergänzen:",
                "question": "Wie lautet der Arbeitsort?",
                "suggestions": ["Berlin (Hybrid)", "Remote möglich"],
                "company": "Daten GmbH",
                "job_title": "Data Scientist (DE)",
                "city": "Berlin",
                "ocr_text": "Dies ist eine gescannte deutsche Stellenanzeige.",
            },
        ),
        (
            "en",
            {
                "heading": "**Suggested questions:**",
                "info": "The assistant has generated follow-up questions to help fill in missing info:",
                "question": "What is the primary work location?",
                "suggestions": ["Berlin", "Remote"],
                "company": "Insight Labs",
                "job_title": "Data Scientist (EN)",
                "city": "Munich",
                "ocr_text": "This is a scanned English job advertisement.",
            },
        ),
        (
            "mixed",
            {
                "heading": "**Suggested questions:**",
                "info": "The assistant has generated follow-up questions to help fill in missing info:",
                "question": "Where will the team work from?",
                "suggestions": ["Hybrid", "Fully remote"],
                "company": "Global Analytics",
                "job_title": "Data Scientist (Hybrid)",
                "city": "Zurich",
                "ocr_text": "Gemischter Text. Mixed language content for detection.",
            },
        ),
    ],
)
def test_wizard_handles_pdf_upload_with_followups(
    monkeypatch: pytest.MonkeyPatch, lang: str, expected: dict[str, Any]
) -> None:
    """Streamlit wizard should ingest a PDF upload and render localized follow-ups."""

    # Load the PDF fixture and keep bytes ready for the upload simulation.
    fixture_path = Path("tests/fixtures/job_ad_simple_en_pdf_base64.txt")
    pdf_bytes = base64.b64decode(fixture_path.read_text(encoding="utf-8").strip())

    # Patch the costly LLM helpers with deterministic outputs.
    base_profile = NeedAnalysisProfile().model_dump()
    base_profile["company"]["name"] = expected["company"]
    base_profile["position"]["job_title"] = expected["job_title"]
    base_profile["position"]["role_summary"] = f"Kurzbeschreibung {lang}"
    base_profile["location"]["primary_city"] = expected["city"]
    base_profile["compensation"]["salary_min"] = 60000
    base_profile["compensation"]["salary_max"] = 80000
    base_profile["compensation"]["currency"] = "EUR"
    base_profile["requirements"]["hard_skills_required"] = [f"Python ({lang})"]
    base_profile["requirements"]["soft_skills_required"] = [f"Teamwork ({lang})"]
    base_profile["meta"]["followups_answered"] = []
    profile_model = NeedAnalysisProfile.model_validate(base_profile)
    profile_payload = profile_model.model_dump(mode="json")

    def fake_extract_json(*_: Any, **__: Any) -> str:
        return json.dumps(profile_payload)

    monkeypatch.setattr(llm_client, "extract_json", fake_extract_json)
    monkeypatch.setattr(wizard, "extract_json", fake_extract_json)

    def fake_extract_with_function(*_: Any, **__: Any) -> ExtractionResult:
        return ExtractionResult(data=profile_payload, field_contexts={}, global_context=[])

    monkeypatch.setattr(openai_utils, "extract_with_function", fake_extract_with_function)

    followup_payload = {
        "questions": [
            {
                "field": "company.name",
                "question": expected["question"],
                "priority": "critical",
                "suggestions": list(expected["suggestions"]),
            }
        ]
    }

    monkeypatch.setattr(question_logic, "ask_followups", lambda *_, **__: followup_payload)
    monkeypatch.setattr(wizard, "ask_followups", lambda *_, **__: followup_payload)

    monkeypatch.setattr("wizard.apply_rules", lambda *_: {})
    monkeypatch.setattr("wizard.search_occupations", lambda *_, **__: [])
    monkeypatch.setattr("wizard.classify_occupation", lambda *_, **__: {})
    monkeypatch.setattr("wizard._refresh_esco_skills", lambda *_, **__: None)

    monkeypatch.setattr(
        openai_utils,
        "suggest_skills_for_role",
        lambda *_, **__: {
            "tools_and_technologies": ["Streamlit"],
            "hard_skills": [f"Python ({lang})"],
            "soft_skills": [f"Communication ({lang})"],
            "certificates": ["Azure"],
        },
    )
    monkeypatch.setattr(openai_utils, "suggest_benefits", lambda *_, **__: [f"Benefit {lang}"])
    monkeypatch.setattr(
        openai_utils,
        "suggest_onboarding_plans",
        lambda *_, **__: [f"Onboarding Schritt {idx + 1} ({lang})" for idx in range(5)],
    )

    # Prepare OCR stubs so that _extract_pdf walks the OCR branch.
    class _DummyPage:
        def extract_text(self) -> str:
            return ""

    class _DummyReader:
        def __init__(self, *_: Any, **__: Any) -> None:
            self.pages = [_DummyPage()]

    monkeypatch.setattr("pypdf.PdfReader", _DummyReader)

    ocr_text = expected["ocr_text"]

    pdf2image_stub = types.SimpleNamespace(convert_from_bytes=lambda *_, **__: [object()])
    pytesseract_stub = types.SimpleNamespace(image_to_string=lambda *_: ocr_text)
    monkeypatch.setitem(sys.modules, "pdf2image", pdf2image_stub)
    monkeypatch.setitem(sys.modules, "pytesseract", pytesseract_stub)

    original_extract_pdf = extractors._extract_pdf

    def fake_extract_text_from_file(upload: Any) -> Any:
        upload.seek(0)
        buffer = BytesIO(upload.read())
        return original_extract_pdf(buffer, getattr(upload, "name", "upload.pdf"))

    monkeypatch.setattr(extractors, "extract_text_from_file", fake_extract_text_from_file)

    # Spin up the Streamlit app via AppTest.
    app = AppTest.from_file("app.py")
    app.run(timeout=30)

    # Configure language before triggering the upload.
    app.session_state["lang"] = lang
    if lang in {"de", "en"}:
        app.session_state[UIKeys.LANG_SELECT] = lang
    else:
        app.session_state[UIKeys.LANG_SELECT] = "en"
    app.session_state["auto_reask"] = True

    # Simulate the file upload via session state and run the callback.
    uploaded_file = StubUploadedFile(pdf_bytes, name=f"fixture-{lang}.pdf")
    app.session_state[UIKeys.PROFILE_FILE_UPLOADER] = uploaded_file
    doc = clean_structured_document(extractors.extract_text_from_file(uploaded_file))
    app.session_state["__prefill_profile_text__"] = doc.text
    app.session_state["__prefill_profile_doc__"] = doc
    app.session_state[StateKeys.RAW_BLOCKS] = doc.blocks
    app.session_state[StateKeys.RAW_TEXT] = doc.text
    app.session_state["__run_extraction__"] = True

    # Run the app twice to allow reruns after extraction triggers.
    app.run(timeout=30)
    app.run(timeout=30)
    company_markdown = [md.value for md in app.markdown]
    company_button_labels = [btn.label for btn in app.button]

    app.session_state[StateKeys.STEP] = app.session_state[StateKeys.WIZARD_STEP_COUNT] - 1
    app.run(timeout=30)
    summary_markdown = [md.value for md in app.markdown]

    # Verify session state carries the extracted information and follow-ups.
    profile_state = app.session_state[StateKeys.PROFILE]
    assert profile_state["company"]["name"] == expected["company"]
    assert profile_state["position"]["job_title"] == expected["job_title"]
    assert app.session_state[StateKeys.RAW_TEXT].strip() == ocr_text

    followups_state = app.session_state[StateKeys.FOLLOWUPS]
    assert any(q.get("question") == expected["question"] for q in followups_state)
    target_followup = next(q for q in followups_state if q.get("question") == expected["question"])
    assert target_followup.get("suggestions") == expected["suggestions"]

    # Follow-up section and suggestion chips should render localized strings.
    assert any(expected["info"] in value for value in company_markdown)
    assert any(expected["question"] in value for value in company_markdown)
    for suggestion in expected["suggestions"]:
        assert suggestion in company_button_labels

    assert any(expected["heading"] in value for value in summary_markdown)
    assert any(expected["question"] in value for value in summary_markdown)
