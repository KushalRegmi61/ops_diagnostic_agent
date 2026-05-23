# Resume Concept Map

This document maps each technical concept Kushal claims in the [Agent Integrator AI Engineer resume](../agent_integrator_ai_engineer_2026-05-20/kushal_regmi_ai_engineer_resume.pdf) to where it is exercised in this project. The goal: anyone reading the resume and then opening this codebase can verify the claim, not just take it on faith.

Several claims are **honestly carried by CareGene / Sambodhan / Veritas evidence in the resume itself** — those tools (DynamoDB, Kafka, PKG/knowledge-graphs, ONNX/vLLM, W&B, gRPC) were the right choice there but would be force-fit here. They're marked as such below rather than retrofitted.

**Scope note:** v1 of this project is a local demo. Deployment, CI/CD pipelines, and broader production-hardening (k8s, EC2, GitHub Actions, circuit breakers, audit ledgers, S3 backend) are out of scope here and stay honestly carried by the CareGene resume evidence.

## Mapping Table

| Resume claim | Project surface area | Status |
|---|---|---|
| **LangGraph** | Parent workflow + per-file fan-out + bounded review/revision loops in `backend/app/graph.py`. | v1 (Plan 2) |
| **StateGraph** | `DiagnosticState` TypedDict carrying typed handoffs between nine agent roles. | v1 (Plan 2) |
| **ReAct** | Per-file agents implemented as tool-routed ReAct agents — think → call tool → observe → continue. The lead reviewer's redo decision is also ReAct-shaped (think → act on summaries → observe gaps → revise). | v1 (Plan 2) |
| **Tool routing** | Per-file agents call a fixed toolbelt: `search_text`, `extract_workflow`, `extract_pain_signal`, `extract_lead_row`, `cite_locator`. Tool calls are dispatched by an explicit router, not free-form. | v1 (Plan 2) |
| **RAG / retrieval** | Per-file agents perform localized retrieval within a single file via `search_text` (deterministic substring + token-overlap scoring over `ParsedSegment` list). Cross-file vector RAG is deferred to v2 §16. | v1 (light) + v2 (hybrid vector retrieval) |
| **Human-in-the-loop** | The reviewer agent's `revision_requests` are renderable in the UI as a human-approvable diff before the redo cycle triggers. An `auto-approve` mode skips the gate for non-interactive runs. Full approval-gated outbound actions remain v2. | v1 (UI gate) + v2 (outbound actions) |
| **Guardrails** | (1) Pydantic schema validation on every LLM output. (2) Citation existence + reachability post-check (deterministic). (3) Bounded review/revision loops (1 cycle each). (4) JSON-mode enforcement on every provider. | v1 |
| **LLM Evaluation (DeepEval / Ragas / G-Eval)** | Not used here — v1 measures the pipeline end-to-end via Langfuse traces (every node, every LLM call, every tool call, every redo/revision decision). An offline eval harness is honestly carried by CareGene LLM/RAG evaluation infrastructure on the resume. | resume-carried |
| **Python / FastAPI / REST APIs / AsyncIO** | FastAPI handlers, async LLM provider clients (`httpx.AsyncClient`). | v1 (Plan 1) |
| **gRPC** | Not used here — honestly carried by CareGene PKG/EHR ingestion evidence. Adding gRPC here would be force-fit. | resume-carried |
| **Next.js / React / TypeScript / Admin Dashboards** | Upload view, run-progress dashboard, blueprint view with citation side panel, eval-report panel. | v1 (Plan 3) |
| **PostgreSQL** | `runs`, `files`, `file_summaries`, `intake_bundles`, `blueprints`, `evaluations` tables. SQLite as local fallback. | v1 |
| **DynamoDB** | Not used here — Postgres is the right relational choice for this data shape. Honestly carried by CareGene episode/event-storage evidence. | resume-carried |
| **Kafka** | Not used here — eventing is overkill for a single-process pipeline. Honestly carried by CareGene PKG-to-clinical-core eventing evidence. | resume-carried |
| **Valkey/Redis** | **Required** as the LangGraph checkpointer (`langgraph-checkpoint-redis`). Keyed by `run_id`. Drives the bounded redo and revision loops; the backend refuses to start if Redis is unreachable. | v1 (Plan 2) |
| **Vector DBs / Knowledge Graphs** | Deferred to v2 §16 (company knowledge source + RAG hybrid). v1 uses in-file localized retrieval, which is the right scope for an evidence-first diagnostic. | v2 |
| **S3 / AWS / Kubernetes / GitHub Actions CI/CD / EC2** | Out of scope for the v1 demo. Honestly carried by CareGene infrastructure and deployment evidence. | resume-carried |
| **Docker / docker-compose** | `backend/Dockerfile`, `frontend/Dockerfile`, root `docker-compose.yml` orchestrating backend + frontend + Postgres + Redis + Ollama. `make demo` builds and starts the whole stack with one command. | v1 (Plan 1 + Plan 3) |
| **ONNX / vLLM** | Not used — this project orchestrates LLMs, it doesn't serve them. Honestly carried by CareGene MLOps + projects context. | resume-carried |
| **Langfuse** | **The single measurement layer in v1.** One nested trace per run; every node, every LLM call, every tool call, every redo/revision decision instrumented. Per spec §10. | v1 (Plan 2) |
| **Transformer fundamentals** | Honestly carried by GPT-2-from-scratch project on the resume. | resume-carried |

## What this project deliberately is NOT

To stay honest and demo-focused:

- **Not a model trainer.** No ONNX, vLLM, or fine-tuning.
- **Not a multi-service distributed system.** No Kafka, DynamoDB, or PKG-style knowledge graph.
- **Not a clinical/healthcare system.** No PHI handling, FHIR ingestion, per-user encryption.
- **Not a deployment story.** No k8s, EC2, or CI/CD pipelines. Local Docker demo only.

The trade is intentional: each project on the CV gets to be specifically excellent at one thing. This project is specifically excellent at **multi-agent diagnostic reasoning over real ops files, with citations, evals, and proper LangGraph + Redis + Langfuse plumbing — runnable end-to-end with one `make demo`.**

## How to use this map

In the meeting, this map is the "show your work" bridge between the resume and the codebase. If Shaun asks "your resume says ReAct — where in this project?", the answer is: `backend/app/agents/per_file/*.py` plus the reviewer redo loop in `backend/app/agents/lead/review_summaries.py`, both implemented as ReAct loops.
