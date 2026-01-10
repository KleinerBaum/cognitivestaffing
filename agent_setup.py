# agent_setup.py
from __future__ import annotations

import os

from agents import Agent, FileSearchTool, WebSearchTool  # hosted tools
from prompts import prompt_registry
from wizard_tools import (
    attach_context,
    detect_gaps,
    export_profile,
    extract_vacancy_fields,
    generate_followups,
    generate_jd,
    get_run,
    index_documents,
    ingest_answers,
    log_event,
    map_esco_skills,
    market_salary_enrich,
    redact_pii,
    semantic_search,
    upload_jobad,
    validate_profile,
)


def _graph_tools_enabled() -> bool:
    return os.getenv("ENABLE_AGENT_GRAPH", "").lower() in {"1", "true", "yes", "on"}


def _experimental_graph_tools() -> list[object]:
    if not _graph_tools_enabled():
        return []

    from wizard_tools.experimental import execution, graph

    return [
        graph.add_stage,
        graph.update_stage,
        graph.remove_stage,
        graph.connect_stages,
        graph.disconnect,
        graph.list_graph,
        graph.save_graph,
        graph.load_graph,
        execution.run_stage,
        execution.run_all,
        execution.retry_stage,
        execution.set_model,
        execution.set_reasoning_effort,
        execution.set_tool_choice,
        execution.set_temperature,
        execution.set_max_output_tokens,
    ]


def build_wizard_agent(vector_store_ids: list[str] | None = None) -> Agent:
    hosted = []
    if vector_store_ids:
        hosted.append(FileSearchTool(max_num_results=6, vector_store_ids=vector_store_ids))
    # Optionally allow browsing for salary benchmarks, etc.
    hosted.append(WebSearchTool())

    function_tools: list[object] = [
        upload_jobad,
        extract_vacancy_fields,
        detect_gaps,
        generate_followups,
        ingest_answers,
        validate_profile,
        map_esco_skills,
        market_salary_enrich,
        generate_jd,
        export_profile,
        index_documents,
        semantic_search,
        attach_context,
        redact_pii,
        log_event,
        get_run,
    ]
    function_tools.extend(_experimental_graph_tools())

    return Agent(
        name="Recruitment Wizard",
        instructions=prompt_registry.get("agent.workflow.instructions"),
        tools=hosted + function_tools,
        # Model config is specified when running; Agents SDK uses OpenAI Responses under the hood.
    )
