"""Tool for deterministic BM25 retrieval over a parsed file's segments.

The LLM cannot see a large file all at once. Parsers first convert the file
into ``ParsedFile.segments``; then the ReAct agent calls ``search_text`` with
queries such as "manual follow-up", "missing owner", or "lead response delay".

This tool adapts the app's canonical ``ParsedSegment`` objects into LangChain
``Document`` objects only for retrieval, ranks them with LangChain's in-memory
``BM25Retriever``, then converts the hits back into the existing tool result
shape. The agent normally follows a good hit with ``read_segment`` to see the
full text before extracting anything.

BM25 is lexical, deterministic, and embedding-free. It is stronger than raw
token overlap for exact-term retrieval because rare query terms matter more,
but it is still not semantic search.
"""
import re

from langchain_community.retrievers.bm25 import BM25Retriever
from langchain_core.documents import Document

from app.schemas import ParsedFile


def _preprocess(s: str) -> list[str]:
    """Lowercased word-token list used by BM25 and display scoring."""
    return [t.lower() for t in re.split(r"\W+", s) if t]


def _documents_from_parsed(parsed: ParsedFile) -> list[Document]:
    """Adapt ParsedSegments into LangChain Documents without changing the app schema."""
    return [
        Document(
            page_content=seg.text,
            metadata={
                "segment_index": i,
                "locator": seg.locator,
                "file_id": parsed.file_id,
                "file_name": parsed.file_name,
                "file_type": parsed.type,
            },
        )
        for i, seg in enumerate(parsed.segments)
    ]


def _score(segment_text: str, query: str) -> float:
    """Return a 0..1 display/debug score; BM25 controls result order."""
    seg_tokens = set(_preprocess(segment_text))
    q_tokens = set(_preprocess(query))
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
    if top_k <= 0 or not parsed.segments:
        return []

    query_tokens = _preprocess(query)
    documents = _documents_from_parsed(parsed)
    if not query_tokens:
        return [
            {
                "segment_index": doc.metadata["segment_index"],
                "score": 0.0,
                "text": doc.page_content,
                "locator": doc.metadata["locator"],
            }
            for doc in documents[:top_k]
        ]

    retriever = BM25Retriever.from_documents(
        documents,
        k=top_k,
        preprocess_func=_preprocess,
    )
    hits = retriever.invoke(query)
    return [
        {
            "segment_index": doc.metadata["segment_index"],
            "score": _score(doc.page_content, query),
            "text": doc.page_content,
            "locator": doc.metadata["locator"],
        }
        for doc in hits
    ]
