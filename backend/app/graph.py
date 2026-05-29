"""LangGraph parent workflow for the ops-diagnostic agent.

Wiring:
    per_file_setup
        → (Send fan-out) per_file_one … → per_file_join
            → review_summaries
                → (bounded redo) per_file_setup | synthesis
    → workflow_map → bottleneck_detect → roi_score → fastest_win_select
        → solution_blueprint
            → self_review_final
                → (bounded revision) solution_blueprint | END
"""
import time
from pathlib import Path
from typing import Callable

from langgraph.graph import END, StateGraph
from langgraph.types import Send

from app import _langgraph_pydantic_patch  # noqa: F401  (teach Redis serializer about Pydantic)
from app.parsers import parse as parsers_parse
from app.agents.lead import (
    bottleneck_detect,
    fastest_win_select,
    review_summaries,
    roi_score,
    self_review_final,
    solution_blueprint,
    synthesis,
    workflow_map,
)
from app.llm.base import LLMParseError, LLMProvider
from app.observability import node_span
from app.registry import get_agent_module
from app.schemas import ExtractionError, IntakeBundle, ParsedFile, RunContext, SummaryReview
from app.state import DiagnosticState
from app.structured_logging import get_logger


logger = get_logger(__name__)


def _compute_targets(state: DiagnosticState) -> tuple[set[str], str]:
    """Return (targeted file_ids, reason).

    On a redo pass (review has revision_requests) only the flagged files are
    targeted; otherwise every file in the run is targeted.
    """
    review = state.get("summary_review")
    if review and review.revision_requests:
        return {r.file_id for r in review.revision_requests}, "revision_requests"
    return {f.file_id for f in state["files"]}, "initial"


def dispatch_fanout(state: DiagnosticState) -> list[Send]:
    """Fan out one Send per targeted file to the per_file_one node.

    Each Send carries only what per_file_one needs: the run_id and the file's
    FileRef. The branch's return value is merged into the shared channel via
    the file_summaries / errors reducers.
    """
    targets, _ = _compute_targets(state)
    return [
        Send("per_file_one", {"run_id": state["run_id"], "file_ref": fref})
        for fref in state["files"]
        if fref.file_id in targets
    ]


def build_graph(
    *,
    provider: LLMProvider,
    parsed_files: dict[str, ParsedFile],
    run_context: RunContext | None = None,
    redo_cap: int = 1,
    revision_cap: int = 1,
    checkpointer=None,
    on_tool_call: Callable | None = None,
    on_event: Callable | None = None,
):
    """Build and compile the diagnostic workflow.

    parsed_files is keyed by file_id and held in a closure (not in state) because
    ParsedFile segments are bulky and re-parsable from disk.
    """

    def emit(type: str, message: str, stage: str, level: str = "info", **data) -> None:
        if on_event is not None:
            on_event(type=type, message=message, stage=stage, level=level, data=data)

    # --- Nodes (each wrapped in a Langfuse span via node_span) ---
    def per_file_setup(state: DiagnosticState) -> dict:
        """Entry node: emit the per-file phase start. Sends are dispatched by the conditional edge."""
        targets, reason = _compute_targets(state)
        logger.info(
            "graph.node.started",
            node="per_file_setup",
            target_count=len(targets),
            targets=sorted(targets),
            reason=reason,
        )
        emit(
            "graph_node_started",
            f"Running per-file agents for {len(targets)} files",
            "per_file",
            node="per_file_fanout",  # keep event contract stable for the frontend
            target_count=len(targets),
            reason=reason,
        )
        return {}

    def per_file_one(state: dict) -> dict:
        """Run one file's ReAct agent. Receives {run_id, file_ref} via Send.

        Returns {"file_summaries": {file_id: summary}} on success, or
        {"errors": [ExtractionError]} on parse failure. A skip (rehydrate
        failure / no agent) returns {} so siblings are unaffected.
        """
        file_ref = state["file_ref"]
        run_id = state["run_id"]
        parsed = parsed_files.get(file_ref.file_id)
        if parsed is None:
            try:
                parsed = parsers_parse(
                    file_id=file_ref.file_id,
                    file_name=file_ref.file_name,
                    path=Path(file_ref.blob_path),
                    mime_type=file_ref.mime_type,
                )
                parsed_files[file_ref.file_id] = parsed
                logger.info(
                    "graph.per_file.rehydrated",
                    file_id=file_ref.file_id,
                    file_type=parsed.type,
                    segment_count=len(parsed.segments),
                )
            except Exception as exc:
                logger.warning(
                    "graph.per_file.skipped",
                    file_id=file_ref.file_id,
                    reason="rehydrate_failed",
                    error=str(exc),
                )
                return {}
        agent = get_agent_module(parsed.type)
        if agent is None:
            logger.warning(
                "graph.per_file.skipped",
                file_id=file_ref.file_id,
                file_type=parsed.type,
                reason="no_agent",
            )
            return {}
        file_started = time.perf_counter()
        logger.info(
            "graph.per_file.started",
            file_id=file_ref.file_id,
            file_name=file_ref.file_name,
            file_type=parsed.type,
            segment_count=len(parsed.segments),
        )
        emit(
            "graph_per_file_started",
            f"Agent started for {file_ref.file_name}",
            "per_file",
            file_id=file_ref.file_id,
            file_name=file_ref.file_name,
            file_type=parsed.type,
            segment_count=len(parsed.segments),
        )
        with node_span(f"per_file:{file_ref.file_id}", input={"type": parsed.type}):
            try:
                summary = agent.run(
                    provider=provider,
                    parsed=parsed,
                    on_tool_call=on_tool_call,
                    run_id=run_id,
                    trace_name=f"per_file:{file_ref.file_id}",
                    user_context=(
                        run_context.user_context
                        if (run_context and run_context.has_steering())
                        else None
                    ),
                )
            except LLMParseError as err:
                logger.error(
                    "graph.per_file.failed",
                    file_id=file_ref.file_id,
                    stage=err.stage,
                    error=err.message,
                )
                emit(
                    "graph_per_file_failed",
                    f"Per-file agent failed for {file_ref.file_name}: parsed_json=False",
                    "per_file",
                    "error",
                    file_id=file_ref.file_id,
                    file_name=file_ref.file_name,
                    error_stage=err.stage,
                )
                return {"errors": [ExtractionError(
                    file_id=err.file_id or file_ref.file_id,
                    stage=err.stage,
                    message=err.message,
                )]}
        elapsed_ms = round((time.perf_counter() - file_started) * 1000)
        logger.info(
            "graph.per_file.completed",
            file_id=file_ref.file_id,
            workflow_count=len(summary.key_workflows),
            pain_signal_count=len(summary.key_pain_signals),
            lead_row_count=len(summary.lead_rows),
            open_question_count=len(summary.open_questions),
            elapsed_ms=elapsed_ms,
        )
        emit(
            "graph_per_file_completed",
            f"Agent completed {file_ref.file_name}",
            "per_file",
            file_id=file_ref.file_id,
            file_name=file_ref.file_name,
            workflow_count=len(summary.key_workflows),
            pain_signal_count=len(summary.key_pain_signals),
            lead_row_count=len(summary.lead_rows),
            open_question_count=len(summary.open_questions),
            elapsed_ms=elapsed_ms,
        )
        return {"file_summaries": {file_ref.file_id: summary}}

    def per_file_join(state: DiagnosticState) -> dict:
        """Fan-in marker after all per-file branches complete; emits the aggregate completed event."""
        out = state.get("file_summaries", {}) or {}
        logger.info("graph.node.completed", node="per_file_fanout", output_count=len(out))
        emit(
            "graph_node_completed",
            f"Per-file analysis completed for {len(out)} files",
            "per_file",
            node="per_file_fanout",
            output_count=len(out),
        )
        return {}

    def review_node(state: DiagnosticState) -> dict:
        """Run review_summaries over the per-file outputs and capture any revision requests."""
        started = time.perf_counter()
        logger.info("graph.node.started", node="review_summaries", file_summary_count=len(state["file_summaries"]))
        emit("graph_node_started", "Reviewing file summaries", "review", node="review_summaries")
        with node_span("review_summaries"):
            try:
                rev = review_summaries.run(provider=provider, file_summaries=state["file_summaries"])
            except LLMParseError as err:
                logger.error("graph.node.failed", node="review_summaries", stage=err.stage, error=err.message)
                emit("graph_node_failed", "Review summaries failed: parsed_json=False", "review", "error",
                     node="review_summaries", error_stage=err.stage)
                return {"summary_review": SummaryReview(revision_requests=[], notes="(review_summaries LLM parse failed)"), "errors": [ExtractionError(file_id=err.file_id, stage=err.stage, message=err.message)]}
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        logger.info(
            "graph.node.completed",
            node="review_summaries",
            revision_request_count=len(rev.revision_requests),
            elapsed_ms=elapsed_ms,
        )
        emit(
            "graph_node_completed",
            "Summary review completed",
            "review",
            node="review_summaries",
            revision_request_count=len(rev.revision_requests),
            elapsed_ms=elapsed_ms,
        )
        return {"summary_review": rev}

    def redo_router(state: DiagnosticState) -> str:
        """Decide whether to redo per-file extraction (capped by redo_cap) or advance to synthesis."""
        rev = state.get("summary_review")
        if rev and rev.revision_requests and state.get("redo_count", 0) < redo_cap:
            logger.info(
                "graph.router.decision",
                router="redo_router",
                decision="redo",
                redo_count=state.get("redo_count", 0),
                redo_cap=redo_cap,
                revision_request_count=len(rev.revision_requests),
            )
            emit("graph_router_decision", "Reviewer requested a focused redo", "review", router="redo_router", decision="redo")
            return "redo"
        logger.info(
            "graph.router.decision",
            router="redo_router",
            decision="advance",
            redo_count=state.get("redo_count", 0),
            redo_cap=redo_cap,
            revision_request_count=len(rev.revision_requests) if rev else 0,
        )
        emit("graph_router_decision", "Advancing to synthesis", "review", router="redo_router", decision="advance")
        return "advance"

    def redo_inc(state: DiagnosticState) -> dict:
        """Increment the redo counter — bounds the per-file redo loop."""
        redo_count = state.get("redo_count", 0) + 1
        logger.info("graph.counter.incremented", counter="redo_count", value=redo_count)
        emit("graph_counter_incremented", f"Redo pass {redo_count}", "review", counter="redo_count", value=redo_count)
        return {"redo_count": redo_count}

    def synthesis_node(state: DiagnosticState) -> dict:
        """Synthesize per-file summaries into a cross-file IntakeBundle."""
        started = time.perf_counter()
        logger.info("graph.node.started", node="synthesis", file_summary_count=len(state["file_summaries"]))
        emit("graph_node_started", "Synthesizing cross-file intake bundle", "synthesis", node="synthesis")
        with node_span("synthesis"):
            try:
                bundle = synthesis.run(provider=provider, file_summaries=state["file_summaries"], run_context=run_context)
            except LLMParseError as err:
                logger.error("graph.node.failed", node="synthesis", stage=err.stage, error=err.message)
                emit("graph_node_failed", "Synthesis failed: parsed_json=False", "synthesis", "error",
                     node="synthesis", error_stage=err.stage)
                empty = IntakeBundle(
                    workflows=[], pain_signals=[], lead_rows=[],
                    contradictions=[], file_index=[], extraction_errors=[],
                )
                return {"bundle": empty, "errors": [ExtractionError(file_id=err.file_id, stage=err.stage, message=err.message)]}
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        logger.info(
            "graph.node.completed",
            node="synthesis",
            workflow_count=len(bundle.workflows),
            pain_signal_count=len(bundle.pain_signals),
            lead_row_count=len(bundle.lead_rows),
            elapsed_ms=elapsed_ms,
        )
        emit(
            "graph_node_completed",
            "Synthesis completed",
            "synthesis",
            node="synthesis",
            workflow_count=len(bundle.workflows),
            pain_signal_count=len(bundle.pain_signals),
            lead_row_count=len(bundle.lead_rows),
            elapsed_ms=elapsed_ms,
        )
        return {"bundle": bundle}

    def workflow_map_node(state: DiagnosticState) -> dict:
        """Map the bundle into structured WorkflowRecords."""
        b = state["bundle"]
        if not isinstance(b, IntakeBundle):
            err = ExtractionError(
                file_id="",
                stage="workflow_map",
                message="bundle is None at node entry — upstream synthesis failed",
            )
            logger.error("graph.node.failed", node="workflow_map", reason="missing_bundle")
            emit("graph_node_failed", "workflow_map skipped: missing bundle", "diagnose", "error",
                 node="workflow_map", reason="missing_bundle")
            return {"workflows": [], "errors": [err]}
        started = time.perf_counter()
        logger.info("graph.node.started", node="workflow_map", bundle_workflow_count=len(b.workflows))
        emit("graph_node_started", "Mapping workflows", "diagnose", node="workflow_map")
        with node_span("workflow_map"):
            try:
                wfs = workflow_map.run(provider=provider, bundle=b)
            except LLMParseError as err:
                logger.error("graph.node.failed", node="workflow_map", stage=err.stage, error=err.message)
                emit("graph_node_failed", "Workflow map failed: parsed_json=False", "diagnose", "error",
                     node="workflow_map", error_stage=err.stage)
                return {"workflows": [], "errors": [ExtractionError(file_id=err.file_id, stage=err.stage, message=err.message)]}
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        logger.info(
            "graph.node.completed",
            node="workflow_map",
            workflow_count=len(wfs),
            elapsed_ms=elapsed_ms,
        )
        emit(
            "graph_node_completed",
            "Workflow map completed",
            "diagnose",
            node="workflow_map",
            workflow_count=len(wfs),
            elapsed_ms=elapsed_ms,
        )
        return {"workflows": wfs}

    def bottleneck_detect_node(state: DiagnosticState) -> dict:
        """Detect Bottlenecks inside the mapped workflows using the bundle's pain signals."""
        b = state["bundle"]
        if not isinstance(b, IntakeBundle):
            err = ExtractionError(
                file_id="",
                stage="bottleneck_detect",
                message="bundle is None at node entry — upstream synthesis failed",
            )
            logger.error("graph.node.failed", node="bottleneck_detect", reason="missing_bundle")
            emit("graph_node_failed", "bottleneck_detect skipped: missing bundle", "diagnose", "error",
                 node="bottleneck_detect", reason="missing_bundle")
            return {"bottlenecks": [], "errors": [err]}
        started = time.perf_counter()
        logger.info(
            "graph.node.started",
            node="bottleneck_detect",
            workflow_count=len(state["workflows"]),
            pain_signal_count=len(b.pain_signals),
        )
        emit("graph_node_started", "Detecting bottlenecks", "diagnose", node="bottleneck_detect")
        with node_span("bottleneck_detect"):
            try:
                bns = bottleneck_detect.run(provider=provider, bundle=b, workflows=state["workflows"], run_context=run_context)
            except LLMParseError as err:
                logger.error("graph.node.failed", node="bottleneck_detect", stage=err.stage, error=err.message)
                emit("graph_node_failed", "Bottleneck detection failed: parsed_json=False", "diagnose", "error",
                     node="bottleneck_detect", error_stage=err.stage)
                return {"bottlenecks": [], "errors": [ExtractionError(file_id=err.file_id, stage=err.stage, message=err.message)]}
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        logger.info(
            "graph.node.completed",
            node="bottleneck_detect",
            bottleneck_count=len(bns),
            elapsed_ms=elapsed_ms,
        )
        emit(
            "graph_node_completed",
            "Bottleneck detection completed",
            "diagnose",
            node="bottleneck_detect",
            bottleneck_count=len(bns),
            elapsed_ms=elapsed_ms,
        )
        return {"bottlenecks": bns}

    def roi_score_node(state: DiagnosticState) -> dict:
        """Score each bottleneck as an automation Opportunity (pain, ROI, effort, risk)."""
        b = state["bundle"]
        if not isinstance(b, IntakeBundle):
            err = ExtractionError(
                file_id="",
                stage="roi_score",
                message="bundle is None at node entry — upstream synthesis failed",
            )
            logger.error("graph.node.failed", node="roi_score", reason="missing_bundle")
            emit("graph_node_failed", "roi_score skipped: missing bundle", "score", "error",
                 node="roi_score", reason="missing_bundle")
            return {"opportunities": [], "errors": [err]}
        started = time.perf_counter()
        logger.info("graph.node.started", node="roi_score", bottleneck_count=len(state["bottlenecks"]))
        emit("graph_node_started", "Scoring automation opportunities", "score", node="roi_score")
        with node_span("roi_score"):
            try:
                ops = roi_score.run(provider=provider, bundle=b, bottlenecks=state["bottlenecks"])
            except LLMParseError as err:
                logger.error("graph.node.failed", node="roi_score", stage=err.stage, error=err.message)
                emit("graph_node_failed", "ROI scoring failed: parsed_json=False", "score", "error",
                     node="roi_score", error_stage=err.stage)
                return {"opportunities": [], "errors": [ExtractionError(file_id=err.file_id, stage=err.stage, message=err.message)]}
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        logger.info(
            "graph.node.completed",
            node="roi_score",
            opportunity_count=len(ops),
            elapsed_ms=elapsed_ms,
        )
        emit(
            "graph_node_completed",
            "ROI scoring completed",
            "score",
            node="roi_score",
            opportunity_count=len(ops),
            elapsed_ms=elapsed_ms,
        )
        return {"opportunities": ops}

    def fastest_win_select_node(state: DiagnosticState) -> dict:
        """Pick the single fastest-win Opportunity from the scored list."""
        started = time.perf_counter()
        logger.info("graph.node.started", node="fastest_win_select", opportunity_count=len(state["opportunities"]))
        emit("graph_node_started", "Selecting fastest win", "select", node="fastest_win_select")
        with node_span("fastest_win_select"):
            try:
                sel = fastest_win_select.run(provider=provider, opportunities=state["opportunities"], run_context=run_context)
            except LLMParseError as err:
                logger.error("graph.node.failed", node="fastest_win_select", stage=err.stage, error=err.message)
                emit("graph_node_failed", "Fastest win selection failed: parsed_json=False", "select", "error",
                     node="fastest_win_select", error_stage=err.stage)
                return {"selected": None, "errors": [ExtractionError(file_id=err.file_id, stage=err.stage, message=err.message)]}
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        logger.info(
            "graph.node.completed",
            node="fastest_win_select",
            selected=sel is not None,
            elapsed_ms=elapsed_ms,
        )
        emit(
            "graph_node_completed",
            "Fastest win selected",
            "select",
            node="fastest_win_select",
            selected=sel is not None,
            elapsed_ms=elapsed_ms,
        )
        return {"selected": sel}

    def solution_blueprint_node(state: DiagnosticState) -> dict:
        """Produce the cited Blueprint; on a revision pass, feeds final_review.detail back in."""
        sel = state["selected"]
        if sel is None:
            err = ExtractionError(
                file_id="",
                stage="solution_blueprint",
                message="no opportunity selected; cannot build blueprint",
            )
            logger.warning("graph.node.skipped", node="solution_blueprint", reason="no_selected_opportunity")
            emit(
                "graph_node_skipped",
                "No selected opportunity; skipping blueprint",
                "blueprint",
                "warning",
                node="solution_blueprint",
                reason="no_selected_opportunity",
            )
            return {"blueprint": None, "errors": [err]}
        b = state["bundle"]
        if not isinstance(b, IntakeBundle):
            err = ExtractionError(
                file_id="",
                stage="solution_blueprint",
                message="bundle is None at node entry — upstream synthesis failed",
            )
            logger.error("graph.node.failed", node="solution_blueprint", reason="missing_bundle")
            emit("graph_node_failed", "solution_blueprint skipped: missing bundle", "blueprint", "error",
                 node="solution_blueprint", reason="missing_bundle")
            return {"blueprint": None, "errors": [err]}
        idx = state["opportunities"].index(sel)
        fr = state.get("final_review")
        detail = fr.detail if (fr and not _final_review_ok(fr)) else None
        started = time.perf_counter()
        logger.info("graph.node.started", node="solution_blueprint", selected_index=idx, revision=bool(detail))
        emit("graph_node_started", "Generating solution blueprint", "blueprint", node="solution_blueprint", revision=bool(detail))
        with node_span("solution_blueprint", input={"selected_index": idx, "revision": bool(detail)}):
            try:
                bp = solution_blueprint.run(
                    provider=provider, bundle=b, selected=sel,
                    selected_index=idx, revision_detail=detail,
                    run_context=run_context,
                )
            except LLMParseError as err:
                logger.error("graph.node.failed", node="solution_blueprint", stage=err.stage, error=err.message)
                emit("graph_node_failed", "Solution blueprint failed: parsed_json=False", "blueprint", "error",
                     node="solution_blueprint", error_stage=err.stage)
                return {"blueprint": None, "errors": [ExtractionError(file_id=err.file_id, stage=err.stage, message=err.message)]}
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        logger.info(
            "graph.node.completed",
            node="solution_blueprint",
            has_blueprint=bp is not None,
            step_count=len(bp.steps) if bp is not None else 0,
            elapsed_ms=elapsed_ms,
        )
        emit(
            "graph_node_completed",
            "Blueprint generated",
            "blueprint",
            node="solution_blueprint",
            has_blueprint=bp is not None,
            step_count=len(bp.steps) if bp is not None else 0,
            elapsed_ms=elapsed_ms,
        )
        return {"blueprint": bp}

    def self_review_node(state: DiagnosticState) -> dict:
        """Run self_review_final — deterministic citation existence/reachability gates plus LLM consistency check."""
        bp = state["blueprint"]
        if bp is None:
            err = ExtractionError(
                file_id="",
                stage="self_review_final",
                message="no blueprint produced; cannot self-review",
            )
            logger.warning("graph.node.skipped", node="self_review_final", reason="no_blueprint")
            emit(
                "graph_node_skipped",
                "No blueprint to review",
                "review_final",
                "warning",
                node="self_review_final",
                reason="no_blueprint",
            )
            return {"final_review": None, "errors": [err]}
        sel = state["selected"]
        b = state["bundle"]
        if not isinstance(b, IntakeBundle):
            err = ExtractionError(
                file_id="",
                stage="self_review_final",
                message="bundle is None at node entry — upstream synthesis failed",
            )
            logger.error("graph.node.failed", node="self_review_final", reason="missing_bundle")
            emit("graph_node_failed", "self_review_final skipped: missing bundle", "review_final", "error",
                 node="self_review_final", reason="missing_bundle")
            return {"final_review": None, "errors": [err]}
        if sel is None:
            err = ExtractionError(
                file_id="",
                stage="self_review_final",
                message="selected opportunity is None at node entry — upstream selection failed",
            )
            logger.error("graph.node.failed", node="self_review_final", reason="missing_selected")
            emit("graph_node_failed", "self_review_final skipped: missing selected opportunity", "review_final", "error",
                 node="self_review_final", reason="missing_selected")
            return {"final_review": None, "errors": [err]}
        started = time.perf_counter()
        logger.info(
            "graph.node.started",
            node="self_review_final",
            revised_once=state.get("revision_count", 0) > 0,
        )
        emit("graph_node_started", "Reviewing blueprint citations", "review_final", node="self_review_final")
        with node_span("self_review_final"):
            try:
                fr = self_review_final.run(
                    provider=provider, blueprint=bp, bundle=b, selected=sel,
                    opportunities=state["opportunities"],
                    file_summaries=state["file_summaries"],
                    parsed_files=parsed_files,
                    revised_once=state.get("revision_count", 0) > 0,
                    run_context=run_context,
                )
            except LLMParseError as err:
                logger.error("graph.node.failed", node="self_review_final", stage=err.stage, error=err.message)
                emit("graph_node_failed", "Self-review failed: parsed_json=False", "review_final", "error",
                     node="self_review_final", error_stage=err.stage)
                return {"final_review": None, "errors": [ExtractionError(file_id=err.file_id, stage=err.stage, message=err.message)]}
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        logger.info(
            "graph.node.completed",
            node="self_review_final",
            citation_existence_ok=fr.citation_existence_ok,
            citation_reachability_ok=fr.citation_reachability_ok,
            no_silent_drops_ok=fr.no_silent_drops_ok,
            internal_consistency_ok=fr.internal_consistency_ok,
            elapsed_ms=elapsed_ms,
        )
        emit(
            "graph_node_completed",
            "Final self-review completed",
            "review_final",
            node="self_review_final",
            citation_existence_ok=fr.citation_existence_ok,
            citation_reachability_ok=fr.citation_reachability_ok,
            no_silent_drops_ok=fr.no_silent_drops_ok,
            internal_consistency_ok=fr.internal_consistency_ok,
            elapsed_ms=elapsed_ms,
        )
        return {"final_review": fr}

    def revise_router(state: DiagnosticState) -> str:
        """Decide whether to revise the Blueprint (capped by revision_cap) or end the run."""
        fr = state.get("final_review")
        if fr is None or _final_review_ok(fr):
            logger.info(
                "graph.router.decision",
                router="revise_router",
                decision="end",
                revision_count=state.get("revision_count", 0),
                revision_cap=revision_cap,
                final_review_ok=fr is not None and _final_review_ok(fr),
            )
            emit("graph_router_decision", "Final review accepted", "review_final", router="revise_router", decision="end")
            return "end"
        if state.get("revision_count", 0) >= revision_cap:
            logger.info(
                "graph.router.decision",
                router="revise_router",
                decision="end",
                revision_count=state.get("revision_count", 0),
                revision_cap=revision_cap,
                final_review_ok=False,
            )
            emit("graph_router_decision", "Revision cap reached", "review_final", "warning", router="revise_router", decision="end")
            return "end"
        logger.info(
            "graph.router.decision",
            router="revise_router",
            decision="revise",
            revision_count=state.get("revision_count", 0),
            revision_cap=revision_cap,
        )
        emit("graph_router_decision", "Revising blueprint after review", "review_final", router="revise_router", decision="revise")
        return "revise"

    def revise_inc(state: DiagnosticState) -> dict:
        """Increment the revision counter — bounds the Blueprint revision loop."""
        revision_count = state.get("revision_count", 0) + 1
        logger.info("graph.counter.incremented", counter="revision_count", value=revision_count)
        emit("graph_counter_incremented", f"Blueprint revision pass {revision_count}", "review_final", counter="revision_count", value=revision_count)
        return {"revision_count": revision_count}

    # --- Graph wiring ---
    g = StateGraph(DiagnosticState)
    g.add_node("per_file_setup", per_file_setup)
    g.add_node("per_file_one", per_file_one)
    g.add_node("per_file_join", per_file_join)
    g.add_node("review_summaries", review_node)
    g.add_node("redo_inc", redo_inc)
    g.add_node("synthesis", synthesis_node)
    g.add_node("workflow_map", workflow_map_node)
    g.add_node("bottleneck_detect", bottleneck_detect_node)
    g.add_node("roi_score", roi_score_node)
    g.add_node("fastest_win_select", fastest_win_select_node)
    g.add_node("solution_blueprint", solution_blueprint_node)
    g.add_node("self_review_final", self_review_node)
    g.add_node("revise_inc", revise_inc)

    g.set_entry_point("per_file_setup")
    g.add_conditional_edges("per_file_setup", dispatch_fanout, ["per_file_one"])
    g.add_edge("per_file_one", "per_file_join")
    g.add_edge("per_file_join", "review_summaries")
    g.add_conditional_edges(
        "review_summaries", redo_router,
        {"redo": "redo_inc", "advance": "synthesis"},
    )
    g.add_edge("redo_inc", "per_file_setup")
    g.add_edge("synthesis", "workflow_map")
    g.add_edge("workflow_map", "bottleneck_detect")
    g.add_edge("bottleneck_detect", "roi_score")
    g.add_edge("roi_score", "fastest_win_select")
    g.add_edge("fastest_win_select", "solution_blueprint")
    g.add_edge("solution_blueprint", "self_review_final")
    g.add_conditional_edges(
        "self_review_final", revise_router,
        {"revise": "revise_inc", "end": END},
    )
    g.add_edge("revise_inc", "solution_blueprint")

    return g.compile(checkpointer=checkpointer)


def _final_review_ok(fr) -> bool:
    """True only when all four FinalReview gate flags are green."""
    return (
        fr.citation_existence_ok
        and fr.citation_reachability_ok
        and fr.no_silent_drops_ok
        and fr.internal_consistency_ok
    )


def initial_state(run_id: str, files, run_context: RunContext | None = None) -> DiagnosticState:
    """Construct a starting DiagnosticState for a new run.

    ``run_context`` is closure-captured by ``build_graph`` for runtime reads.
    Storing it in state is for checkpoint-reload symmetry only — no node mutates it.
    """
    return {
        "run_id": run_id,
        "files": list(files),
        "run_context": run_context,
        "file_summaries": {},
        "summary_review": None,
        "redo_count": 0,
        "bundle": None,
        "workflows": [],
        "bottlenecks": [],
        "opportunities": [],
        "selected": None,
        "blueprint": None,
        "final_review": None,
        "revision_count": 0,
        "errors": [],
    }
