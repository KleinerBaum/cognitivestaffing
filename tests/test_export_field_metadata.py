from exports.models import apply_field_metadata_to_payload


def test_apply_field_metadata_marks_unconfirmed_heuristics() -> None:
    payload = {
        "company": {"name": "Acme"},
        "meta": {
            "field_metadata": {
                "company.name": {
                    "source": "heuristic",
                    "confidence": 0.4,
                    "confirmed": False,
                }
            }
        },
    }

    marked = apply_field_metadata_to_payload(payload, mark_unconfirmed=True, exclude_unconfirmed=False)

    assert marked["company"]["name"].endswith("[UNCONFIRMED_ESTIMATE]")


def test_apply_field_metadata_excludes_unconfirmed_heuristics() -> None:
    payload = {
        "company": {"name": "Acme"},
        "meta": {
            "field_metadata": {
                "company.name": {
                    "source": "heuristic",
                    "confidence": 0.4,
                    "confirmed": False,
                }
            }
        },
    }

    cleaned = apply_field_metadata_to_payload(payload, mark_unconfirmed=False, exclude_unconfirmed=True)

    assert cleaned["company"]["name"] is None
