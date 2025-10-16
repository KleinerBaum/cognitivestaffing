# agent_setup.py
from agents import Agent, FileSearchTool, WebSearchTool  # hosted tools
from wizard_tools import (
    add_stage,
    update_stage,
    remove_stage,
    connect_stages,
    disconnect,
    list_graph,
    save_graph,
    load_graph,
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
    run_stage,
    run_all,
    retry_stage,
    set_model,
    set_reasoning_effort,
    set_tool_choice,
    set_temperature,
    set_max_output_tokens,
    redact_pii,
    log_event,
    get_run,
)


def build_wizard_agent(vector_store_ids: list[str] | None = None) -> Agent:
    hosted = []
    if vector_store_ids:
        hosted.append(FileSearchTool(max_num_results=6, vector_store_ids=vector_store_ids))
    # Optionally allow browsing for salary benchmarks, etc.
    hosted.append(WebSearchTool())

    function_tools = [
        add_stage,
        update_stage,
        remove_stage,
        connect_stages,
        disconnect,
        list_graph,
        save_graph,
        load_graph,
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
        run_stage,
        run_all,
        retry_stage,
        set_model,
        set_reasoning_effort,
        set_tool_choice,
        set_temperature,
        set_max_output_tokens,
        redact_pii,
        log_event,
        get_run,
    ]

    return Agent(
        name="Recruitment Wizard",
        instructions=(
            "You are a recruitment workflow agent. "
            "Always keep the vacancy graph consistent (DAG). "
            "Prefer minimal reasoning for graph edits; raise effort for extraction/validation. "
            "Call the appropriate tool for each user intent; do not hallucinate fields."
        ),
        tools=hosted + function_tools,
        # Model config is specified when running; Agents SDK uses OpenAI Responses under the hood.
    )
