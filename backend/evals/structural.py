"""Offline structural probe for the per-file failure diagnostic.

Parses a file's segments and reports segment count, char-size distribution, and
BM25 liveness over a few generic probe queries — catching parser pathologies
(one mega-segment, dead retrieval, shredded tiny rows) without invoking an LLM.
"""
import statistics

from pydantic import BaseModel

from app.agents.per_file._tools.search_text import search_text
from app.schemas import ParsedFile

_PROBE_QUERIES = [
    "process steps workflow",
    "delay error manual handoff",
    "name email status owner",
]
_TINY_SEGMENT_CHARS = 20


class StructuralProbe(BaseModel):
    """Structural health of one parsed file, independent of the agent."""

    segment_count: int
    seg_chars_min: int
    seg_chars_median: int
    seg_chars_max: int
    bm25_nonempty_rate: float
    flags: list[str]


def probe_structure(parsed: ParsedFile, queries: list[str] | None = None) -> StructuralProbe:
    """Probe segment shape and BM25 liveness; derive parser-pathology flags."""
    queries = queries or _PROBE_QUERIES
    sizes = [len(seg.text) for seg in parsed.segments]
    if not sizes:
        return StructuralProbe(
            segment_count=0, seg_chars_min=0, seg_chars_median=0,
            seg_chars_max=0, bm25_nonempty_rate=0.0, flags=["no_segments"],
        )
    nonempty = sum(1 for q in queries if search_text(parsed, query=q, top_k=3))
    rate = nonempty / len(queries)
    median = int(statistics.median(sizes))
    flags: list[str] = []
    if len(sizes) == 1:
        flags.append("single_segment")
    if rate == 0.0:
        flags.append("bm25_dead")
    if median < _TINY_SEGMENT_CHARS:
        flags.append("tiny_segments")
    return StructuralProbe(
        segment_count=len(sizes),
        seg_chars_min=min(sizes),
        seg_chars_median=median,
        seg_chars_max=max(sizes),
        bm25_nonempty_rate=rate,
        flags=flags,
    )
