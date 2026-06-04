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
from app.agents.per_file._tools._citation import _EXCERPT_BY_TYPE
from app.schemas import ParsedFile


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
