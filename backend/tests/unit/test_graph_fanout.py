"""Unit tests for the pure fan-out helpers: target selection and Send dispatch."""
from app.graph import _compute_targets
from app.schemas import FileRef, RevisionRequest, SummaryReview


def _ref(fid: str) -> FileRef:
    """Minimal FileRef for fan-out tests."""
    return FileRef(
        file_id=fid,
        file_name=f"{fid}.txt",
        blob_path=f"/tmp/{fid}.txt",
        mime_type="text/plain",
        parser_status="ok",
    )


def test_compute_targets_initial_is_all_files():
    """With no review, every file is a target and the reason is 'initial'."""
    state = {"files": [_ref("f1"), _ref("f2")], "summary_review": None}
    targets, reason = _compute_targets(state)
    assert targets == {"f1", "f2"}
    assert reason == "initial"


def test_compute_targets_redo_is_revision_requests_only():
    """With revision requests, only flagged file_ids are targets and reason is 'revision_requests'."""
    review = SummaryReview(
        revision_requests=[
            RevisionRequest(file_id="f2", reason="weak_citation", detail="sources too sparse")
        ],
        notes="",
    )
    state = {"files": [_ref("f1"), _ref("f2")], "summary_review": review}
    targets, reason = _compute_targets(state)
    assert targets == {"f2"}
    assert reason == "revision_requests"
