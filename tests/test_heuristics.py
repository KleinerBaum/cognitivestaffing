import importlib.util
import pathlib
from utils.json_parse import parse_extraction

spec = importlib.util.spec_from_file_location(
    "heuristics", pathlib.Path("ingest/heuristics.py")
)
heuristics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(heuristics)

guess_job_title = heuristics.guess_job_title
guess_company = heuristics.guess_company
guess_city = heuristics.guess_city


def test_guess_job_title_strip_gender() -> None:
    text = "Senior Data Scientist (m/w/d) – RAG, OpenAI & Recruiting Tech"
    assert guess_job_title(text) == "Senior Data Scientist"


def test_guess_company_brand() -> None:
    text = "Wir sind Vacalyser, ein Tech-Brand der Example GmbH"
    name, brand = guess_company(text)
    assert name == "Example GmbH"
    assert brand == "Vacalyser"


def test_guess_city_from_header() -> None:
    text = "Berlin | Hybrid | ab 01.10.2024"
    assert guess_city(text) == "Berlin"


def test_parse_extraction_city_alias() -> None:
    jd = parse_extraction('{"position": {"job_title": "Dev"}, "city": "Düsseldorf"}')
    assert jd.location.primary_city == "Düsseldorf"
