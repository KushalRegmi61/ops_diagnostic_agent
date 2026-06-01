"""Idempotent builder for the multi-format eval corpus.

Generates two operationally-realistic files per parser family under ``files/``
and writes ``manifest.json`` describing the minimum each file must yield. The
content is plausible agency-ops data (lead intake, renewals, manual handoffs)
so convergence reflects real extraction, not toy text.
"""
import json
import mailbox
from pathlib import Path

import fitz
import openpyxl
import pandas as pd
from docx import Document

ROOT = Path(__file__).parent
FILES = ROOT / "files"


def _write_pdfs() -> None:
    """Two SOP-style PDFs with manual-touchpoint language."""
    for name, lines in {
        "intake_sop.pdf": [
            "Inbound Lead SOP",
            "Step 1: CSR collects contact info by phone.",
            "Step 2: CSR manually rekeys contact into Applied Epic.",
            "Step 3: Producer follows up within 24 hours (often slips to 3 days).",
        ],
        "renewal_sop.pdf": [
            "Renewal Processing SOP",
            "Step 1: Account manager pulls declarations page from carrier portal.",
            "Step 2: Quote is re-typed into the agency management system.",
            "Step 3: Renewal email sent; no automated reminder exists.",
        ],
    }.items():
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "\n".join(lines))
        doc.save(FILES / name)
        doc.close()


def _write_docx() -> None:
    """Two onboarding/handoff DOCX files."""
    for name, paras in {
        "onboarding_sop.docx": [
            "Client Onboarding SOP",
            "Step 1: Verify lead identity against submitted documents.",
            "Step 2: Open the client file in Applied Epic by hand.",
            "Step 3: CSR emails welcome packet; status tracked in a spreadsheet.",
        ],
        "claims_handoff.docx": [
            "Claims Handoff Procedure",
            "Step 1: First notice of loss received by phone.",
            "Step 2: CSR copies details into both the carrier site and the CRM.",
            "Step 3: Adjuster assignment is emailed manually with no SLA.",
        ],
    }.items():
        doc = Document()
        for p in paras:
            doc.add_paragraph(p)
        doc.save(FILES / name)


def _write_text_like() -> None:
    """md/txt/vtt/srt fixtures with explicit pain language."""
    (FILES / "producer_notes.md").write_text(
        "# Producer Notes\n\n"
        "Leads wait more than 24 hours before first response.\n"
        "CSR manually copies CRM notes into the renewal email.\n"
        "No dashboard shows which leads are stuck awaiting documents.\n"
    )
    (FILES / "standup_notes.md").write_text(
        "# Ops Standup\n\n"
        "Double-entry between HubSpot and Epic keeps causing errors.\n"
        "Renewal reminders are sent by memory, not by system.\n"
    )
    (FILES / "discovery_call.txt").write_text(
        "Discovery call summary.\n"
        "Client reports slow document collection from insureds.\n"
        "Producer follow-up is inconsistent and untracked.\n"
    )
    (FILES / "qbr_notes.txt").write_text(
        "QBR notes.\n"
        "Revenue leaks when renewals lapse without a reminder.\n"
        "Team re-keys the same data into three systems.\n"
    )
    (FILES / "intake_call.vtt").write_text(
        "WEBVTT\n\n"
        "00:00:01.000 --> 00:00:05.000\n"
        "Founder: our biggest issue is lead response time.\n\n"
        "00:00:06.000 --> 00:00:10.000\n"
        "CSR: we copy notes from email to HubSpot manually.\n\n"
        "00:00:11.000 --> 00:00:15.000\n"
        "Founder: nobody can see which leads are stuck.\n"
    )
    (FILES / "renewal_call.srt").write_text(
        "1\n00:00:01,000 --> 00:00:05,000\n"
        "AM: renewals slip because reminders are manual.\n\n"
        "2\n00:00:06,000 --> 00:00:10,000\n"
        "Owner: we lose accounts when a renewal is missed.\n"
    )


def _write_tabular() -> None:
    """csv/xlsx lead exports with stuck-stage rows."""
    pd.DataFrame(
        [
            {"name": "Acme Corp", "email": "ops@acme.com", "stage": "awaiting_docs", "days_in_stage": 12},
            {"name": "Beta LLC", "email": "hi@beta.com", "stage": "new", "days_in_stage": 1},
            {"name": "Gamma Inc", "email": "info@gamma.com", "stage": "awaiting_docs", "days_in_stage": 30},
        ]
    ).to_csv(FILES / "leads_pipeline.csv", index=False)
    pd.DataFrame(
        [
            {"account": "Delta Co", "owner": "unassigned", "renewal_in_days": 5, "reminded": "no"},
            {"account": "Echo Ltd", "owner": "J. Reyes", "renewal_in_days": 45, "reminded": "no"},
        ]
    ).to_csv(FILES / "renewals.csv", index=False)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Leads"
    ws.append(["name", "email", "stage", "days_in_stage"])
    ws.append(["Acme Corp", "ops@acme.com", "awaiting_docs", 12])
    ws.append(["Beta LLC", "hi@beta.com", "new", 1])
    wb.save(FILES / "leads_export.xlsx")

    wb2 = openpyxl.Workbook()
    ws2 = wb2.active
    ws2.title = "Renewals"
    ws2.append(["account", "owner", "renewal_in_days", "reminded"])
    ws2.append(["Delta Co", "unassigned", 5, "no"])
    wb2.save(FILES / "renewals_export.xlsx")


def _write_mbox() -> None:
    """Two mbox files of inbound quote/renewal requests."""
    for name, subject, body in [
        ("quote_requests.mbox", "Need a quote", "We need a commercial liability quote ASAP. Please send the document list."),
        ("renewal_inbox.mbox", "Renewal coming up", "Our policy renews next month. Nobody has reached out yet."),
    ]:
        path = FILES / name
        if path.exists():
            path.unlink()
        mbox = mailbox.mbox(str(path))
        msg = mailbox.mboxMessage()
        msg["From"] = "lead@acme.com"
        msg["To"] = "csr@agency.com"
        msg["Subject"] = subject
        msg["Message-ID"] = f"<{name}@acme.com>"
        msg.set_payload(body)
        mbox.add(msg)
        mbox.close()


def _write_json() -> None:
    """Two CRM-style JSON exports with stuck contacts."""
    (FILES / "crm_contacts.json").write_text(json.dumps({
        "contacts": [
            {"id": "c1", "name": "Acme Corp", "last_touch_days": 12, "stage": "awaiting_docs"},
            {"id": "c2", "name": "Beta LLC", "last_touch_days": 1, "stage": "new"},
        ]
    }, indent=2))
    (FILES / "pipeline_export.json").write_text(json.dumps({
        "opportunities": [
            {"id": "o1", "account": "Delta Co", "owner": "unassigned", "stalled_days": 21},
            {"id": "o2", "account": "Echo Ltd", "owner": "J. Reyes", "stalled_days": 2},
        ]
    }, indent=2))


# (file, type, parser, min_workflows, min_pain_signals, min_lead_rows, min_citations, must_converge)
_MANIFEST: list[dict] = [
    {"file": "intake_sop.pdf", "type": "pdf", "min_workflows": 1, "min_pain_signals": 1, "min_lead_rows": 0, "min_citations": 1, "must_converge": True},
    {"file": "renewal_sop.pdf", "type": "pdf", "min_workflows": 1, "min_pain_signals": 0, "min_lead_rows": 0, "min_citations": 1, "must_converge": True},
    {"file": "onboarding_sop.docx", "type": "docx", "min_workflows": 1, "min_pain_signals": 0, "min_lead_rows": 0, "min_citations": 1, "must_converge": True},
    {"file": "claims_handoff.docx", "type": "docx", "min_workflows": 1, "min_pain_signals": 1, "min_lead_rows": 0, "min_citations": 1, "must_converge": True},
    {"file": "producer_notes.md", "type": "md", "min_workflows": 0, "min_pain_signals": 2, "min_lead_rows": 0, "min_citations": 1, "must_converge": True},
    {"file": "standup_notes.md", "type": "md", "min_workflows": 0, "min_pain_signals": 1, "min_lead_rows": 0, "min_citations": 1, "must_converge": True},
    {"file": "discovery_call.txt", "type": "txt", "min_workflows": 0, "min_pain_signals": 1, "min_lead_rows": 0, "min_citations": 1, "must_converge": True},
    {"file": "qbr_notes.txt", "type": "txt", "min_workflows": 0, "min_pain_signals": 1, "min_lead_rows": 0, "min_citations": 1, "must_converge": True},
    {"file": "intake_call.vtt", "type": "vtt", "min_workflows": 0, "min_pain_signals": 1, "min_lead_rows": 0, "min_citations": 1, "must_converge": True},
    {"file": "renewal_call.srt", "type": "srt", "min_workflows": 0, "min_pain_signals": 1, "min_lead_rows": 0, "min_citations": 1, "must_converge": True},
    {"file": "leads_pipeline.csv", "type": "csv", "min_workflows": 0, "min_pain_signals": 0, "min_lead_rows": 1, "min_citations": 1, "must_converge": True},
    {"file": "renewals.csv", "type": "csv", "min_workflows": 0, "min_pain_signals": 0, "min_lead_rows": 1, "min_citations": 1, "must_converge": True},
    {"file": "leads_export.xlsx", "type": "xlsx", "min_workflows": 0, "min_pain_signals": 0, "min_lead_rows": 1, "min_citations": 1, "must_converge": True},
    {"file": "renewals_export.xlsx", "type": "xlsx", "min_workflows": 0, "min_pain_signals": 0, "min_lead_rows": 1, "min_citations": 1, "must_converge": True},
    {"file": "quote_requests.mbox", "type": "mbox", "min_workflows": 0, "min_pain_signals": 1, "min_lead_rows": 0, "min_citations": 1, "must_converge": True},
    {"file": "renewal_inbox.mbox", "type": "mbox", "min_workflows": 0, "min_pain_signals": 1, "min_lead_rows": 0, "min_citations": 1, "must_converge": True},
    {"file": "crm_contacts.json", "type": "json", "min_workflows": 0, "min_pain_signals": 0, "min_lead_rows": 1, "min_citations": 1, "must_converge": True},
    {"file": "pipeline_export.json", "type": "json", "min_workflows": 0, "min_pain_signals": 0, "min_lead_rows": 1, "min_citations": 1, "must_converge": True},
]


def main() -> None:
    """Regenerate all corpus files and the manifest in place. Idempotent."""
    FILES.mkdir(parents=True, exist_ok=True)
    _write_pdfs()
    _write_docx()
    _write_text_like()
    _write_tabular()
    _write_mbox()
    _write_json()
    (ROOT / "manifest.json").write_text(json.dumps(_MANIFEST, indent=2))
    print(f"Corpus written to {FILES} ({len(_MANIFEST)} cases)")


if __name__ == "__main__":
    main()
