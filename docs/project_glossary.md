# Project Glossary

Project-specific vocabulary for the redesigned ops diagnostic agent. Authoritative spec: [`superpowers/specs/2026-05-23-real-files-diagnostic-redesign-design.md`](superpowers/specs/2026-05-23-real-files-diagnostic-redesign-design.md).

## Agent Integrator Context

**AI-native business** — A business where AI is embedded into daily workflows. The goal is measurable ROI on lead handling, operations, and follow-up — not "we use ChatGPT."

**Fastest win** — The first workflow automation that has the best balance of high ROI, low effort, and manageable risk.

**Boring business** — A non-hype business with lots of manual workflow (insurance, property management, construction, law, local services, healthcare admin, staffing, finance ops). Strong AI opportunities because repetitive manual work is everywhere.

**Workflow leak** — A place where time, revenue, customer trust, or operational visibility is lost.

**Implementation blueprint** — The proposed system plan: steps, required systems, success metrics, risks — each entry citing source evidence.

## Insurance Agency Domain

**Producer** — Sells policies and manages revenue opportunities.

**CSR** — Customer Service Representative. Handles intake, document collection, follow-up.

**Declaration page** — Summary page from an existing insurance policy, requested when preparing a new quote.

**Commercial coverage** — Business insurance: general liability, workers comp, property, auto, professional liability.

**Quote package** — The collection of information and documents needed before a carrier or producer can prepare a quote.

**Renewal** — Updating and renewing an existing policy before it expires.

## Redesign-Specific Concepts

**Multi-agent system** — A system composed of multiple narrow-purpose LLM agents wired together so that one agent's typed output is the next agent's typed input. This project has nine agent roles: per-file agents (parallel, one per uploaded file), reviewer, synthesizer, five diagnostic-chain agents (`workflow_map`, `bottleneck_detect`, `roi_score`, `fastest_win_select`, `solution_blueprint`), and self-reviewer. The LangGraph parent workflow is the wiring diagram.

**Typed handoff** — Every agent's input and output is a Pydantic model. Agents never read each other's prompts or internals; they only see typed artifacts in `DiagnosticState`. This is what makes the pipeline testable agent-by-agent and traceable claim-by-claim.

**Per-file agent** — One LLM agent assigned to one uploaded file. Implemented as a **tool-routed ReAct loop** (see below) — reads the parsed file content, calls tools to retrieve and extract structured records, and emits a typed `FileSummary` with citations. Per-file agents are summarizers, not deciders — they never score opportunities or pick winners.

**ReAct (Reason + Act)** — An agent loop where the LLM alternates between thinking (reasoning over current state), acting (calling a tool), and observing (reading the tool's result), capped at a small iteration budget. Used here by per-file agents and (loosely) by the reviewer agent's redo decision.

**Tool routing** — Calls from the LLM to a fixed set of typed tools, dispatched by an explicit router (not free-form). The router enforces one tool call per iteration, typed argument validation, and iteration caps. Per-file agents in this project route over: `search_text`, `read_segment`, `extract_workflow`, `extract_pain_signal`, `extract_lead_row`, `cite_locator`, `finalize_summary`.

**Tool** — A deterministic function the LLM can invoke through the router. In this project, tools have no LLM inside them (they parse, score, or validate). `cite_locator` is the only path that produces a `Source` — every citation roundtrips through the parser.

**In-file retrieval (light RAG)** — `search_text` performs token-overlap + substring scoring localized to a single file (the file the per-file agent owns). v1 has no cross-file vector store; that's the v2 hybrid retrieval extension (spec §16.2).

**Human-in-the-loop checkpoint** — The UI gate between the reviewer agent's `SummaryReview` and the redo cycle. Operator can Approve / Edit / Skip the proposed revision requests. `auto_approve=true` skips the gate for `make demo` and headless runs.

**Lead-role agents** — The five-stage lead reasoning chain: reviewer (input gate) → synthesizer → diagnostic-chain agents → self-reviewer (output gate). Each is its own LangGraph node with its own prompt and output schema.

**FileSummary** — Typed output from one per-file agent: one-paragraph summary, key workflows, pain signals, lead rows (tables only), open questions, agent notes. Every extracted record carries `sources`.

**Source** — A typed citation: `{ file_id, file_name, type, locator }`. Attached to every extracted record.

**Locator** — File-type-specific pointer back to a precise place in a source file. PDF: `{ page, span_start, span_end }`. Transcript: `{ line_start, line_end, ts_start, ts_end }`. CSV: `{ row_index }`. MBOX: `{ message_id, header_or_body }`. JSON: `{ pointer }` (RFC 6901).

**IntakeBundle** — The lead agent's reconciled view across all files: workflows, pain signals, lead rows, contradictions, file index, extraction errors.

**Contradiction** — When two files disagree on a fact, both claims are preserved with both citations rather than silently merged.

**SummaryReview** — The lead agent's input gate. Emits `revision_requests` flagging missing info, contradictions, weak citations, or ignored open questions. Triggers up to one redo cycle of flagged per-file agents.

**FinalReview** — The lead agent's output gate. Audits citation existence, citation reachability, no silent drops, internal consistency. Up to one revision pass.

**Citation reachability** — A deterministic post-check: every cited locator must resolve to a real position in the parsed file. Catches LLM hallucinations.

## Agentic AI Concepts

**Agent** — A system that reasons over a task, calls tools, maintains state, and produces actions. Here: per-file agents summarize; the lead agent reasons.

**Graph** — A structured flow of nodes. This project uses LangGraph so the workflow is explicit and traceable.

**Node** — One step inside the graph. Examples: `fan_out_files`, `review_summaries`, `cross_file_synthesis`, `roi_score`, `self_review_final`.

**State** — The shared data object passed between nodes. `DiagnosticState` is the TypedDict for this project.

**Fan-out / fan-in** — A LangGraph pattern where one node spawns several parallel children, then a downstream node synchronizes them. Used for per-file agents.

**Bounded loop** — A graph edge that allows retrying a node at most a fixed number of times. Here: one redo cycle for review, one revision for self-review.

**Checkpointer** — A LangGraph component that persists `DiagnosticState` at every node boundary so the graph can resume from any prior state. This project uses a **Redis-backed checkpointer** (`langgraph-checkpoint-redis`). Required in v1 because the reviewer redo loop, self-review revision loop, and per-file failure retries all depend on cheap, correct resume between agent handoffs. Checkpoint identity is `(run_id)`. Configured by `REDIS_URL`, `LANGGRAPH_CHECKPOINTER=redis`, `LANGGRAPH_CHECKPOINT_NAMESPACE=ops_diagnostic`.

## LLM Concepts

**LLM provider** — The backend service used for model calls. Supported: `ollama`, `openai`, `groq`, `openai_compatible`. **No mock provider** in this project.

**Ollama** — Local LLM provider running on your machine. Default for CI and dev with `temperature=0`.

**OpenAI / Groq / OpenAI-compatible** — Hosted providers. Used for higher-quality demo runs.

**Per-node provider override** — Optional env var `LLM_PROVIDER_FOR_<NODE>` that lets a specific node target a different provider (e.g. lead agent on hosted, per-file agents on local). Off by default.

**Strict JSON output** — The model must return machine-readable JSON matching a Pydantic schema. The provider layer enforces a one-retry parse.

**Provider metadata** — Per-call record sent to Langfuse: provider, model, prompt_name, token estimate, parsed_json status, retry_count, latency_ms.

## Observability Concepts

**Langfuse** — LLM observability tool. Stores nested traces, spans, and generation metadata.

**Trace** — The full record of one run. One run = one nested trace.

**Span** — One timed operation inside a trace: a graph node, an LLM call, a parse step.

**Generation** — An LLM-specific trace event recording prompt, model, response metadata, tokens, parsing status.

**Trace storage** — Sent directly to Langfuse. No local trace persistence.

## Backend Concepts

**FastAPI** — Python web framework for API endpoints.

**Pydantic schema** — Typed request/response model.

**SQLAlchemy model** — Database storage model. Tables: `runs`, `files`, `file_summaries`, `intake_bundles`, `blueprints`.

**Service layer** — Coordinates blob storage, database, graph execution, and trace wiring. Routes stay thin; services do the work.

**Parser** — Deterministic file-type-specific reader that turns a raw file into anchored content. No LLM calls.

## Frontend Concepts

**Upload view** — Drag-and-drop interface with per-file parse-status indicator.

**Run Progress view** — Live view of per-file-agent completion, review pass/fail, revision triggers, diagnostic chain progress.

**Blueprint view** — Final output. Every claim has a clickable citation.

**Citation panel** — Side panel that renders the source file at a cited locator (PDF page, transcript line + timestamp, CSV row, MBOX message body).

## v2 Concepts (deferred)

**Company knowledge source** — Per-company memory of past blueprints, outcomes, success patterns, company-specific facts. Consulted during synthesis and updated after every run.

**Continuous learning loop** — Outcome capture + pattern mining + prompt augmentation. Makes the agent get better the more it works with a given company.

**Multimodal inputs** — Audio (transcribed via ASR), images (vision-capable per-file agent), with locator payloads extended to `{ ts_start, ts_end, speaker }` for audio and `{ image_id, bbox }` for images.
