"""Tool for validating that a proposed source locator is real and reachable.

The per-file agent must attach citations to workflows, pain signals, and lead
rows. A citation uses a ``Source`` object, and the most important part of that
Source is the ``locator``: page/span for PDFs, paragraph index for DOCX, row
index for tables, JSON pointer for JSON, and so on.

Before the model uses a locator as evidence, it should call ``cite_locator``.
This tool dispatches to the matching parser's ``excerpt()`` function and checks
whether the locator can be resolved back to non-empty source text. That keeps
fabricated or malformed citations out of the FileSummary before later review
stages run.
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
    """Return ``{text, valid}`` after round-tripping ``locator`` through the parser.

    On the valid path also adds a ``next_step`` hint urging the model to
    immediately call ``extract_workflow`` / ``extract_pain_signal`` /
    ``extract_lead_row`` to commit the finding rather than stalling after cite.
    """
    module = _EXCERPT_BY_TYPE.get(parsed.type)
    if module is None:
        return {"text": "", "valid": False}
    try:
        text = module.excerpt(parsed, locator)
        return {
            "text": text,
            "valid": True,
            "next_step": (
                "Citation valid. It is NOT a finding yet — call extract_workflow / "
                "extract_pain_signal / extract_lead_row with this source to commit it."
            ),
        }
    except (KeyError, ValueError):
        return {"text": "", "valid": False}
