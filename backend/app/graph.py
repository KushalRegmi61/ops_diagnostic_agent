"""LangGraph parent workflow for the ops-diagnostic agent.

Wiring:
    per_file_fanout
        → review_summaries
            → (bounded redo) per_file_fanout | synthesis
    → workflow_map → bottleneck_detect → roi_score → fastest_win_select
        → solution_blueprint
            → self_review_final
                → (bounded revision) solution_blueprint | END
"""
import time
from typing import Callable

from langgraph.graph import END, StateGraph

from app import _langgraph_pydantic_patch  # noqa: F401  (teach Redis serializer about Pydantic)
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
from app.llm.base import LLMProvider
from app.observability import node_span
from app.registry import get_agent_module
from app.schemas import IntakeBundle, ParsedFile
from app.state import DiagnosticState
from app.structured_logging import get_logger


logger = get_logger(__name__)


def build_graph(
    *,
    provider: LLMProvider,
    parsed_files: dict[str, ParsedFile],
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
    def per_file_fanout(state: DiagnosticState) -> dict:
        """Run each file's per-file ReAct agent; on redo, only re-runs files flagged by review."""
        node_started = time.perf_counter()
        review = state.get("summary_review")
        if review and review.revision_requests:
            targets = {r.file_id for r in review.revision_requests}
            reason = "revision_requests"
        else:
            targets = {f.file_id for f in state["files"]}
            reason = "initial"

        out = dict(state.get("file_summaries", {}) or {})
        logger.info(
            "graph.node.started",
            node="per_file_fanout",
            target_count=len(targets),
            targets=sorted(targets),
            reason=reason,
        )
        emit(
            "graph_node_started",
            f"Running per-file agents for {len(targets)} files",
            "per_file",
            node="per_file_fanout",
            target_count=len(targets),
            reason=reason,
        )
        with node_span("per_file_fanout", input={"targets": sorted(targets)}):
            for file_ref in state["files"]:
                if file_ref.file_id not in targets:
                    logger.info("graph.per_file.skipped", file_id=file_ref.file_id, reason="not_targeted")
                    continue
                parsed = parsed_files.get(file_ref.file_id)
                if parsed is None:
                    logger.warning("graph.per_file.skipped", file_id=file_ref.file_id, reason="not_parsed")
                    continue
                agent = get_agent_module(parsed.type)
                if agent is None:
                    logger.warning(
                        "graph.per_file.skipped",
                        file_id=file_ref.file_id,
                        file_type=parsed.type,
                        reason="no_agent",
                    )
                    continue
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
                    summary = agent.run(
                        provider=provider,
                        parsed=parsed,
                        on_tool_call=on_tool_call,
                        run_id=state["run_id"],
                        trace_name=f"per_file:{file_ref.file_id}",
                    )
                out[file_ref.file_id] = summary
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
        elapsed_ms = round((time.perf_counter() - node_started) * 1000)
        logger.info(
            "graph.node.completed",
            node="per_file_fanout",
            output_count=len(out),
            elapsed_ms=elapsed_ms,
        )
        emit(
            "graph_node_completed",
            f"Per-file analysis completed for {len(out)} files",
            "per_file",
            node="per_file_fanout",
            output_count=len(out),
            elapsed_ms=elapsed_ms,
        )
        return {"file_summaries": out}

    def review_node(state: DiagnosticState) -> dict:
        """Run review_summaries over the per-file outputs and capture any revision requests."""
        started = time.perf_counter()
        logger.info("graph.node.started", node="review_summaries", file_summary_count=len(state["file_summaries"]))
        emit("graph_node_started", "Reviewing file summaries", "review", node="review_summaries")
        with node_span("review_summaries"):
            rev = review_summaries.run(provider=provider, file_summaries=state["file_summaries"])
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
            bundle = synthesis.run(provider=provider, file_summaries=state["file_summaries"])
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
        assert isinstance(b, IntakeBundle)
        started = time.perf_counter()
        logger.info("graph.node.started", node="workflow_map", bundle_workflow_count=len(b.workflows))
        emit("graph_node_started", "Mapping workflows", "diagnose", node="workflow_map")
        with node_span("workflow_map"):
            wfs = workflow_map.run(provider=provider, bundle=b)
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
        assert isinstance(b, IntakeBundle)
        started = time.perf_counter()
        logger.info(
            "graph.node.started",
            node="bottleneck_detect",
            workflow_count=len(state["workflows"]),
            pain_signal_count=len(b.pain_signals),
        )
        emit("graph_node_started", "Detecting bottlenecks", "diagnose", node="bottleneck_detect")
        with node_span("bottleneck_detect"):
            bns = bottleneck_detect.run(provider=provider, bundle=b, workflows=state["workflows"])
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
        assert isinstance(b, IntakeBundle)
        started = time.perf_counter()
        logger.info("graph.node.started", node="roi_score", bottleneck_count=len(state["bottlenecks"]))
        emit("graph_node_started", "Scoring automation opportunities", "score", node="roi_score")
        with node_span("roi_score"):
            ops = roi_score.run(provider=provider, bundle=b, bottlenecks=state["bottlenecks"])
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
            sel = fastest_win_select.run(provider=provider, opportunities=state["opportunities"])
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
            logger.warning("graph.node.skipped", node="solution_blueprint", reason="no_selected_opportunity")
            emit(
                "graph_node_skipped",
                "No selected opportunity; skipping blueprint",
                "blueprint",
                "warning",
                node="solution_blueprint",
                reason="no_selected_opportunity",
            )
            return {"blueprint": None}
        b = state["bundle"]
        assert isinstance(b, IntakeBundle)
        idx = state["opportunities"].index(sel)
        fr = state.get("final_review")
        detail = fr.detail if (fr and not _final_review_ok(fr)) else None
        started = time.perf_counter()
        logger.info("graph.node.started", node="solution_blueprint", selected_index=idx, revision=bool(detail))
        emit("graph_node_started", "Generating solution blueprint", "blueprint", node="solution_blueprint", revision=bool(detail))
        with node_span("solution_blueprint", input={"selected_index": idx, "revision": bool(detail)}):
            bp = solution_blueprint.run(
                provider=provider, bundle=b, selected=sel,
                selected_index=idx, revision_detail=detail,
            )
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
            logger.warning("graph.node.skipped", node="self_review_final", reason="no_blueprint")
            emit(
                "graph_node_skipped",
                "No blueprint to review",
                "review_final",
                "warning",
                node="self_review_final",
                reason="no_blueprint",
            )
            return {"final_review": None}
        sel = state["selected"]
        b = state["bundle"]
        assert sel is not None and isinstance(b, IntakeBundle)
        started = time.perf_counter()
        logger.info(
            "graph.node.started",
            node="self_review_final",
            revised_once=state.get("revision_count", 0) > 0,
        )
        emit("graph_node_started", "Reviewing blueprint citations", "review_final", node="self_review_final")
        with node_span("self_review_final"):
            fr = self_review_final.run(
                provider=provider, blueprint=bp, bundle=b, selected=sel,
                opportunities=state["opportunities"],
                file_summaries=state["file_summaries"],
                parsed_files=parsed_files,
                revised_once=state.get("revision_count", 0) > 0,
            )
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
    g.add_node("per_file_fanout", per_file_fanout)
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

    g.set_entry_point("per_file_fanout")
    g.add_edge("per_file_fanout", "review_summaries")
    g.add_conditional_edges(
        "review_summaries", redo_router,
        {"redo": "redo_inc", "advance": "synthesis"},
    )
    g.add_edge("redo_inc", "per_file_fanout")
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


def initial_state(run_id: str, files) -> DiagnosticState:
    """Construct a starting DiagnosticState for a new run."""
    return {
        "run_id": run_id,
        "files": list(files),
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
