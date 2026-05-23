"""cite_locator tool: enforce the citation round-trip invariant per Source.

A locator is only valid if the matching parser's ``excerpt()`` returns
non-empty text for it. This tool is what keeps fabricated locators out of
the FileSummary before the lead's ``self_review_final`` ever runs.
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


def cite_locator(parsed: ParsedFile, *, locator: dict) -> dict:
    """Validate a locator by roundtripping it through the parser's excerpt(). Returns {text, valid}."""
    module = _EXCERPT_BY_TYPE.get(parsed.type)
    if module is None:
        return {"text": "", "valid": False}
    try:
        text = module.excerpt(parsed, locator)
        return {"text": text, "valid": True}
    except (KeyError, ValueError):
        return {"text": "", "valid": False}
