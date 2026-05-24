"""Tool for deterministic retrieval over a parsed file's segments.

The LLM cannot see a large file all at once. Parsers first convert the file
into ``ParsedFile.segments``; then the ReAct agent calls ``search_text`` with
queries such as "manual follow-up", "missing owner", or "lead response delay".

This tool scans every segment in the parsed file and ranks matches using a
simple lexical score: word-token overlap plus exact substring presence. It
returns candidate segments with their ``segment_index``, preview text, score,
and locator. The agent normally follows a good hit with ``read_segment`` to see
the full text before extracting anything.

This is intentionally cheap and deterministic. It is not semantic search and
does not require embeddings, so it is fast and testable but may miss evidence
that uses very different wording from the query.
"""
import re

from app.schemas import ParsedFile


def _tokenize(s: str) -> set[str]:
    """Lowercased word-token set built by splitting on non-word characters."""
    return {t.lower() for t in re.split(r"\W+", s) if t}


def _score(segment_text: str, query: str) -> float:
    """Combine token overlap (70%) with substring presence (30%) into a 0..1 score."""
    seg_tokens = _tokenize(segment_text)
    q_tokens = _tokenize(query)
    if not q_tokens:
        return 0.0
    overlap = len(seg_tokens & q_tokens) / len(q_tokens)
    substring = 1.0 if query.lower() in segment_text.lower() else 0.0
    return overlap * 0.7 + substring * 0.3


def search_text(parsed: ParsedFile, *, query: str, top_k: int = 3) -> list[dict]:
    """Return the top matching segments for ``query``.

    Each hit has ``segment_index`` for follow-up reads, ``score`` for ranking,
    ``text`` for quick inspection, and ``locator`` for later citation.
    """
    scored = [
        {
            "segment_index": i,
            "score": _score(seg.text, query),
            "text": seg.text,
            "locator": seg.locator,
        }
        for i, seg in enumerate(parsed.segments)
    ]
    scored.sort(key=lambda h: h["score"], reverse=True)
    return scored[:top_k]
