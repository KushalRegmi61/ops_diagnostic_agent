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
from typing import Callable

from langgraph.graph import END, StateGraph

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
from app.agents.per_file import (
    docx as a_docx,
    json as a_json,
    markdown as a_markdown,
    mbox as a_mbox,
    pdf as a_pdf,
    table as a_table,
    transcript as a_transcript,
)
from app.llm.base import LLMProvider
from app.schemas import IntakeBundle, ParsedFile
from app.state import DiagnosticState

# FileType -> per-file agent module.
_PER_FILE_AGENTS = {
    "pdf": a_pdf,
    "docx": a_docx,
    "md": a_markdown,
    "txt": a_markdown,
    "transcript_vtt": a_transcript,
    "transcript_srt": a_transcript,
    "csv": a_table,
    "xlsx": a_table,
    "mbox": a_mbox,
    "json": a_json,
}


def build_graph(
    *,
    provider: LLMProvider,
    parsed_files: dict[str, ParsedFile],
    redo_cap: int = 1,
    revision_cap: int = 1,
    checkpointer=None,
    on_tool_call: Callable | None = None,
):
    """Build and compile the diagnostic workflow.

    parsed_files is keyed by file_id and held in a closure (not in state) because
    ParsedFile segments are bulky and re-parsable from disk.
    """

    # --- Nodes ---
    def per_file_fanout(state: DiagnosticState) -> dict:
        # If redoing, restrict to file_ids in summary_review.revision_requests.
        review = state.get("summary_review")
        if review and review.revision_requests:
            targets = {r.file_id for r in review.revision_requests}
        else:
            targets = {f.file_id for f in state["files"]}

        out = dict(state.get("file_summaries", {}) or {})
        for file_ref in state["files"]:
            if file_ref.file_id not in targets:
                continue
            parsed = parsed_files.get(file_ref.file_id)
            if parsed is None:
                continue
            agent = _PER_FILE_AGENTS.get(parsed.type)
            if agent is None:
                continue
            summary = agent.run(provider=provider, parsed=parsed, on_tool_call=on_tool_call)
            out[file_ref.file_id] = summary
        return {"file_summaries": out}

    def review_node(state: DiagnosticState) -> dict:
        rev = review_summaries.run(provider=provider, file_summaries=state["file_summaries"])
        return {"summary_review": rev}

    def redo_router(state: DiagnosticState) -> str:
        rev = state.get("summary_review")
        if rev and rev.revision_requests and state.get("redo_count", 0) < redo_cap:
            return "redo"
        return "advance"

    def redo_inc(state: DiagnosticState) -> dict:
        return {"redo_count": state.get("redo_count", 0) + 1}

    def synthesis_node(state: DiagnosticState) -> dict:
        bundle = synthesis.run(provider=provider, file_summaries=state["file_summaries"])
        return {"bundle": bundle}

    def workflow_map_node(state: DiagnosticState) -> dict:
        b = state["bundle"]
        assert isinstance(b, IntakeBundle)
        wfs = workflow_map.run(provider=provider, bundle=b)
        return {"workflows": wfs}

    def bottleneck_detect_node(state: DiagnosticState) -> dict:
        b = state["bundle"]
        assert isinstance(b, IntakeBundle)
        bns = bottleneck_detect.run(provider=provider, bundle=b, workflows=state["workflows"])
        return {"bottlenecks": bns}

    def roi_score_node(state: DiagnosticState) -> dict:
        b = state["bundle"]
        assert isinstance(b, IntakeBundle)
        ops = roi_score.run(provider=provider, bundle=b, bottlenecks=state["bottlenecks"])
        return {"opportunities": ops}

    def fastest_win_select_node(state: DiagnosticState) -> dict:
        sel = fastest_win_select.run(provider=provider, opportunities=state["opportunities"])
        return {"selected": sel}

    def solution_blueprint_node(state: DiagnosticState) -> dict:
        sel = state["selected"]
        if sel is None:
            return {"blueprint": None}
        b = state["bundle"]
        assert isinstance(b, IntakeBundle)
        idx = state["opportunities"].index(sel)
        fr = state.get("final_review")
        detail = fr.detail if (fr and not _final_review_ok(fr)) else None
        bp = solution_blueprint.run(
            provider=provider, bundle=b, selected=sel,
            selected_index=idx, revision_detail=detail,
        )
        return {"blueprint": bp}

    def self_review_node(state: DiagnosticState) -> dict:
        bp = state["blueprint"]
        if bp is None:
            return {"final_review": None}
        sel = state["selected"]
        b = state["bundle"]
        assert sel is not None and isinstance(b, IntakeBundle)
        fr = self_review_final.run(
            provider=provider, blueprint=bp, bundle=b, selected=sel,
            opportunities=state["opportunities"],
            file_summaries=state["file_summaries"],
            parsed_files=parsed_files,
            revised_once=state.get("revision_count", 0) > 0,
        )
        return {"final_review": fr}

    def revise_router(state: DiagnosticState) -> str:
        fr = state.get("final_review")
        if fr is None or _final_review_ok(fr):
            return "end"
        if state.get("revision_count", 0) >= revision_cap:
            return "end"
        return "revise"

    def revise_inc(state: DiagnosticState) -> dict:
        return {"revision_count": state.get("revision_count", 0) + 1}

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
