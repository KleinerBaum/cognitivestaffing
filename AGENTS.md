Cognitive Staffing – Agent Guide (CS_AGENT/1.1)
How to work

Programming language & style: Use Python ≥ 3.11 and follow PEP 8 conventions. Include type hints in all new code.

Directories & keys: Keep to the established structure:

UI components: components/, pages/

Core domain logic: core/

LLM integration: llm/ (OpenAI Responses API + tools)

NLP utilities: nlp/

RAG (retrieval): ingest/ (OpenAI vector store files)

Misc utilities: utils/

Schema propagation (CS_SCHEMA_PROPAGATE): When adding or changing any schema field, update it everywhere – the Pydantic model, business logic, UI, and export templates must remain in sync. Document any mapping or migration changes and add tests covering them.

UI binding rules:

Always retrieve widget default values via wizard._logic.get_value("<path>"). The profile in st.session_state[StateKeys.PROFILE] is the single source of truth (it already contains all schema defaults).

Use canonical schema paths (e.g. "company.name", "location.primary_city") as widget keys. Use the widget helpers from wizard.wizard (which wrap components.widget_factory) to ensure _update_profile keeps the sidebar, summary, and exports in sync.

Secrets: Never hardcode API keys or secrets. Access keys via environment variables (os.getenv("OPENAI_API_KEY")) or Streamlit secrets (st.secrets["openai"]).

Commands to run (CI checks)

Make sure these checks pass locally (they run in CI for every PR):

Format & Lint: ruff format && ruff check – auto-format the code and ensure lint rules pass.

Type checking: mypy --config-file pyproject.toml – static typing (no new type errors).

Tests: pytest -q – all tests must pass (in CI, use -m "not integration" if internet access is off).

App smoke test: streamlit run app.py – manually verify the wizard flow, summary page, JSON/Markdown exports, ESCO skill mapping, and the Boolean search builder in the UI.

Pre-commit hooks: pre-commit run --all-files – run all configured linters and formatters (ruff, black, etc.) on the codebase.

Branching & PR guidelines

Branch naming: Use feature branches with the prefix feat/<short-description> (e.g. feat/add-salary-field).

Pull requests: Merge via the dev branch. Open PRs against dev, which will be merge-trained into main (no direct commits to main).

Release notes: Every PR should include a summary of changes (for Changelog or release notes).

Documentation: Update the README and docs/CHANGELOG.md for any user-facing or developer-impacting changes.

Internationalization: Provide new UI text or prompts in both English and German (update translation constants or files accordingly).

Screenshots: If the UI changes, update any relevant screenshots under images/ in the repository.

API & tools integration

OpenAI usage: Use the OpenAI Responses API with available tools (e.g. WebSearchTool, FileSearchTool) and always request structured outputs (validated via Pydantic models or JSON schema). The default model is gpt-4.1-mini for cost-efficiency and speed. If the user selects “genau” (precise mode), switch to a higher reasoning model (e.g. o4-mini or o3) based on the REASONING_EFFORT setting.

Quick vs Precise toggle: The wizard settings expose a bilingual quick/precise selector. Respect the stored mode by routing quick requests to gpt-4.1-mini with low reasoning effort and precise requests to the configured reasoning tier (o4-mini/o3) with higher verbosity. Keep cache keys (for extraction reuse or salary lookups) mode-aware so switching modes invalidates stale responses.

Responses vs. Chat completions: USE_RESPONSES_API is on by default and must stay in sync with USE_CLASSIC_API. Clearing the Responses flag (or setting USE_CLASSIC_API=1) forces all calls through the legacy Chat Completions API. Suggestion helpers should preserve the retry cascade: Responses → Chat → curated static copy when outages persist.

RESPONSES_ALLOW_TOOLS (default 0) controls whether Responses calls can send tool/function payloads. Leave it disabled unless the tenant is allowlisted for tool-enabled Responses; otherwise force a fallback to the Chat client whenever tools are required. The debug panel and config.set_api_mode() helper must keep USE_RESPONSES_API, USE_CLASSIC_API, RESPONSES_ALLOW_TOOLS, and the bilingual logging switch aligned.

Missing API key guard: When OPENAI_API_KEY is absent, keep AI-triggering widgets disabled and surface the bilingual lock hint (no background calls).

Model configuration: The API base URL can be changed for the EU region – use OPENAI_API_BASE_URL="https://eu.api.openai.com/v1" if needed. Always respect configured timeouts for OpenAI API calls and implement retries with exponential backoff on failure.

Agents SDK: If you modify agent logic or tool wiring, update agent_setup.py accordingly. Only allowed tools are enabled in the cloud environment (currently WebSearchTool and FileSearchTool).

RAG (vector store): If VECTOR_STORE_ID is set, enable retrieval-augmented generation by querying the corresponding OpenAI vector store for context. If not set, the agents should proceed without vector retrieval.

ESCO API: Only use read-only GET requests to the ESCO API (https://ec.europa.eu/esco/api). Cache ESCO responses with st.cache_data (set an appropriate TTL) to avoid redundant external calls.

Security & access policies

Internet access: By default, the Codex agent runs with internet access disabled (except during initial setup for dependency installation). Enable internet for the agent only when necessary, and restrict it to specific allowlisted domains and safe HTTP methods (GET/HEAD/OPTIONS, unless a test requires POST).

Logging: Avoid logging any sensitive data. Do not log API keys or personally identifiable information (PII) in application logs or error messages.

Secrets management: Load all secret keys (e.g. OPENAI_API_KEY) from environment variables or st.secrets. Never commit secrets to the repo or hardcode them in code.

What to output

When the Codex agent produces a solution or code change, its response should include:

The git diff and a list of files changed.

Any commands run (especially those that failed) and their outputs or error messages.

Reproduction steps for verifying the change or bug, along with the expected vs. actual outcomes.

Instructions for how to roll back the changes if applicable (e.g. how to revert a commit).

For large or complex tasks, break the solution into smaller, incremental PRs rather than one big change.

Working with the Codex agent

To get the best results when instructing the Codex coding agent (for example, via ChatGPT or an IDE integration):

Be specific with references: Mention exact file paths, function or class names, or use greppable identifiers when referring to code. This helps the agent quickly locate relevant code.

Provide reproduction details: If reporting a bug or requesting a fix, include clear steps to reproduce the issue, the commands or inputs used, and what happened. This context helps the agent understand the problem.

State expected vs. actual behavior: Clearly describe what you expected the code to do, and what it did instead. This makes it easier for the agent to pinpoint the discrepancy.

Split big tasks: For large implementations, ask the agent to tackle the work in smaller, reviewable chunks or separate PRs. This ensures easier review and testing.

Include logs and errors: When debugging, paste the full error messages or stack traces. Full logs give the agent more context than summaries.

Ask open-ended questions: Besides direct fixes, you can ask the agent for refactoring suggestions, help to identify potential bugs, ideas to improve performance, to brainstorm a solution approach, or even to draft documentation. Leverage the agent’s capabilities for these exploratory tasks as well.

Flag selection: The RecruitingWizard schema is always active; when toggling Responses vs. Chat clients, ensure both flags remain in sync.
