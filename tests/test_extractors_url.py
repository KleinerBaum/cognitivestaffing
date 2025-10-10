import sys
import types
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from ingest.extractors import extract_text_from_url


STEPSTONE_FIXTURE = """
<html>
  <body>
    <header>
      <nav>
        <ul>
          <li>For candidates</li>
          <li>Career advice</li>
        </ul>
      </nav>
    </header>
    <div data-at="job-ad-container">
      <nav>Breadcrumbs</nav>
      <main>
        <article>
          <h1>Senior Data Engineer (f/m/d)</h1>
          <section>
            <h2>Your mission</h2>
            <p>Build reliable data pipelines and analytics tooling.</p>
            <ul>
              <li>Design ETL jobs for production workloads.</li>
              <li>Collaborate with platform teams.</li>
            </ul>
            <h2>Your profile</h2>
            <p>Python expert with experience in orchestration frameworks.</p>
          </section>
        </article>
      </main>
    </div>
    <footer>
      <p>StepStone GmbH · All rights reserved</p>
    </footer>
  </body>
</html>
"""

RHEINBAHN_BOILERPLATE_FIXTURE = """
<html>
  <body>
    <header>
      <nav>
        <ul>
          <li>Startseite</li>
          <li>Unternehmen</li>
          <li>Karriere</li>
        </ul>
      </nav>
    </header>
    <main>
      <section class="hero">
        <h1>Digitalisierung bei der Rheinbahn</h1>
        <p>Gemeinsam gestalten wir Mobilität.</p>
      </section>
      <section class="boilerplate">
        <p>Willkommen auf unserem Karriereportal.</p>
      </section>
      <footer>
        <ul>
          <li>Impressum</li>
          <li>Datenschutz</li>
          <li>Kontakt</li>
        </ul>
      </footer>
    </main>
  </body>
</html>
"""

RHEINBAHN_FIXTURE_PATH = (
    PROJECT_ROOT / "tests" / "fixtures" / "html" / "rheinbahn_produktentwickler.html"
)


def test_extract_text_from_url_success(monkeypatch: pytest.MonkeyPatch) -> None:
    html = (
        "<html><body>"
        "<p>Hello URL paragraph with additional context for testing.</p>"
        "<p>" + "A" * 210 + "</p>"
        "</body></html>"
    )

    class Resp:
        status_code = 200
        text = html

        def raise_for_status(self) -> None:  # pragma: no cover - stub
            return None

    def fake_get(_url: str, timeout: float, headers: dict | None = None) -> Resp:
        return Resp()

    fake_traf = types.SimpleNamespace(
        extract=lambda *_args, **_kwargs: "Recovered fallback text"
    )

    monkeypatch.setattr("ingest.extractors.requests.get", fake_get)
    monkeypatch.setitem(sys.modules, "trafilatura", fake_traf)

    doc = extract_text_from_url("http://example.com")
    assert "Hello URL paragraph" in doc.text
    assert len(doc.text) > 200
    assert doc.blocks and doc.blocks[0].type == "paragraph"


def test_extract_text_from_url_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import requests
    from requests import Response

    def fake_get(
        _url: str, timeout: float, headers: dict | None = None
    ) -> Response:  # pragma: no cover - stub
        resp = Response()
        resp.status_code = 404
        resp._content = b""

        def raise_for_status() -> None:
            raise requests.HTTPError(response=resp)

        resp.raise_for_status = raise_for_status  # type: ignore[method-assign]
        return resp

    monkeypatch.setattr("ingest.extractors.requests.get", fake_get)
    monkeypatch.setitem(sys.modules, "trafilatura", None)

    with pytest.raises(ValueError) as err:
        extract_text_from_url("http://example.com")
    assert "status 404" in str(err.value)


def test_stepstone_like_content_extraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Resp:
        status_code = 200
        text = STEPSTONE_FIXTURE

        def raise_for_status(self) -> None:  # pragma: no cover - stub
            return None

    def fake_get(_url: str, timeout: float, headers: dict | None = None) -> Resp:
        return Resp()

    monkeypatch.setattr("ingest.extractors.requests.get", fake_get)
    monkeypatch.setitem(sys.modules, "trafilatura", None)

    doc = extract_text_from_url("https://www.stepstone.de/jobs/awesome-role")

    text = doc.text
    assert "Senior Data Engineer" in text
    assert "Design ETL jobs" in text
    assert "For candidates" not in text
    assert "Breadcrumbs" not in text


def test_rheinbahn_boilerplate_triggers_trafilatura_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Resp:
        status_code = 200
        text = RHEINBAHN_BOILERPLATE_FIXTURE

        def raise_for_status(self) -> None:  # pragma: no cover - stub
            return None

    def fake_get(_url: str, timeout: float, headers: dict | None = None) -> Resp:
        return Resp()

    recovered = (
        "Produktentwickler Digitalisierung\n\n"
        "Darauf kannst du dich freuen: Moderne Arbeitswelten im Herzen von Düsseldorf.\n\n"
        "Du gestaltest die digitale Zukunft im Verkehrsnetz und setzt innovative Services für unsere Fahrgäste um."
    )

    monkeypatch.setattr("ingest.extractors.requests.get", fake_get)
    fake_traf = types.SimpleNamespace(
        extract=lambda *_args, **_kwargs: recovered,
    )
    monkeypatch.setitem(sys.modules, "trafilatura", fake_traf)

    doc = extract_text_from_url(
        "https://karriere.rheinbahn.de/job/duesseldorf-produktentwickler-boilerplate"
    )

    assert "Produktentwickler Digitalisierung" in doc.text
    assert "Darauf kannst du dich freuen" in doc.text
    assert len(doc.text) > len("Startseite Unternehmen Karriere")


def test_rheinbahn_content_extraction(monkeypatch: pytest.MonkeyPatch) -> None:
    html = RHEINBAHN_FIXTURE_PATH.read_text(encoding="utf-8")

    class Resp:
        status_code = 200
        text = html

        def raise_for_status(self) -> None:  # pragma: no cover - stub
            return None

    def fake_get(_url: str, timeout: float, headers: dict | None = None) -> Resp:
        return Resp()

    monkeypatch.setattr("ingest.extractors.requests.get", fake_get)
    monkeypatch.setitem(sys.modules, "trafilatura", None)

    doc = extract_text_from_url(
        "https://karriere.rheinbahn.de/job/duesseldorf-produktentwickler"
    )

    text = doc.text
    assert "Darauf kannst du dich freuen" in text
    assert "gestaltest du die digitale Zukunft" in text
    assert "Du entwickelst digitale Services" in text
    assert "Startseite" not in text
    assert "Impressum" not in text
