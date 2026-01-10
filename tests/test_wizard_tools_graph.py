from __future__ import annotations

import json

from wizard_tools.experimental import graph


def test_add_stage_generates_canonical_identifier() -> None:
    payload = json.loads(
        graph.add_stage(
            name="Talent Review",
            description="Review hiring funnel",
            kind="qa",
            required_fields=["position.job_title"],
            meta={"owner": "talent"},
        )
    )

    assert payload["stage_id"] == "stage_talent_review"
    assert payload["name"] == "Talent Review"
    assert payload["required_fields"] == ["position.job_title"]
    assert payload["meta"] == {"owner": "talent"}


def test_update_stage_serialises_patch() -> None:
    patch = graph.StagePatch(description="Updated", required_fields=["company.name"])
    payload = json.loads(graph.update_stage("stage_candidate_screening", patch))

    assert payload["stage_id"] == "stage_candidate_screening"
    assert payload["updated"] is True
    assert payload["patch"]["description"] == "Updated"
    assert payload["patch"]["required_fields"] == ["company.name"]
    assert payload["patch"]["name"] is None


def test_graph_serialisation_helpers_return_expected_payloads() -> None:
    graph_state = graph.GraphState(stages=[{"id": "stage_a"}], edges=[{"id": "edge_ab"}])

    saved = json.loads(graph.save_graph("vacancy-1", graph_state))
    assert saved["vacancy_id"] == "vacancy-1"
    assert saved["saved"] is True
    assert saved["stages"] == [{"id": "stage_a"}]
    assert saved["edges"] == [{"id": "edge_ab"}]

    listing = json.loads(graph.list_graph("vacancy-1"))
    assert listing["vacancy_id"] == "vacancy-1"
    assert listing["graph"] == {"stages": [], "edges": []}

    edge = json.loads(graph.connect_stages("stage_a", "stage_b", edge_label="Next"))
    assert edge["edge_id"] == "edge_stage_a_to_stage_b"
    assert edge["label"] == "Next"

    removed = json.loads(graph.disconnect(edge["edge_id"]))
    assert removed == {"removed": True, "edge_id": "edge_stage_a_to_stage_b"}


def test_load_graph_returns_empty_structure() -> None:
    payload = json.loads(graph.load_graph("vacancy-empty"))

    assert payload == {"vacancy_id": "vacancy-empty", "graph": {"stages": [], "edges": []}}
