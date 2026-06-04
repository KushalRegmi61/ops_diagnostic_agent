"""Shared citation validation for the per-file extract_* tools.

Owns the parser-``excerpt()`` dispatch table and ``_validate_sources``, which
round-trips each proposed Source locator through its parser and partitions the
sources into kept (resolves to non-empty text) and dropped. The extract_* tools
call this at the commit point so no Source is ever saved that cannot round-trip.
"""
from app.parsers import csv as _p_csv
from app.parsers import docx as _p_docx
from app.parsers import json as _p_json
from app.parsers import mbox as _p_mbox
from app.parsers import md as _p_md
from app.parsers import pdf as _p_pdf
from app.parsers import srt as _p_srt
from app.parsers import txt as _p_txt
from app.parsers import vtt as _p_vtt
from app.parsers import xlsx as _p_xlsx
from app.schemas import ParsedFile

_EXCERPT_BY_TYPE = {
    "pdf": _p_pdf, "docx": _p_docx, "md": _p_md, "txt": _p_txt,
    "transcript_vtt": _p_vtt, "transcript_srt": _p_srt,
    "csv": _p_csv, "xlsx": _p_xlsx, "mbox": _p_mbox, "json": _p_json,
}


def _locator_of(source) -> dict | None:
    """Extract a plain-dict locator from a source dict or pydantic Source."""
    loc = source.get("locator") if isinstance(source, dict) else getattr(source, "locator", None)
    if loc is None:
        return None
    return loc if isinstance(loc, dict) else loc.model_dump(mode="json")


def _validate_sources(parsed: ParsedFile, sources: list) -> tuple[list, list]:
    """Partition ``sources`` into (kept, dropped) by round-tripping each locator.

    A source is kept iff its parser's ``excerpt()`` returns non-empty text without
    raising ``(KeyError, ValueError)``. Order is preserved within each partition.
    """
    module = _EXCERPT_BY_TYPE.get(parsed.type)
    kept: list = []
    dropped: list = []
    for src in sources:
        locator = _locator_of(src)
        ok = False
        if module is not None and locator is not None:
            try:
                ok = bool(module.excerpt(parsed, locator))
            except (KeyError, ValueError):
                ok = False
        (kept if ok else dropped).append(src)
    return kept, dropped
