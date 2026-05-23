"""search_text tool: token-overlap + substring search over a ParsedFile.

Cheap deterministic retrieval the ReAct agent uses to locate candidate
segments before calling ``read_segment`` for full text.
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
    """Token-overlap + substring scoring over a single ParsedFile.

    Returns the top_k hits as dicts: {segment_index, score, text, locator}.
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
