import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.schema import VacalyserJD, ALL_FIELDS  # noqa: E402
from questions.missing import missing_fields  # noqa: E402


def test_missing_fields_order():
    jd = VacalyserJD(job_title="dev")
    expected = [f for f in ALL_FIELDS if f not in {"schema_version", "job_title"}]
    assert missing_fields(jd) == expected
