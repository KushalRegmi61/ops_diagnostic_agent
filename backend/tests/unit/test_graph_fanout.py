"""Unit tests for the pure fan-out helpers: target selection and Send dispatch."""
from langgraph.types import Send

from app.graph import _compute_targets, dispatch_fanout
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


def test_dispatch_emits_one_send_per_target_initial():
    """Initial pass: one Send to per_file_one per file, carrying its FileRef + run_id."""
    refs = [_ref("f1"), _ref("f2")]
    state = {"run_id": "run_x", "files": refs, "summary_review": None}
    sends = dispatch_fanout(state)
    assert len(sends) == 2
    assert all(isinstance(s, Send) for s in sends)
    assert all(s.node == "per_file_one" for s in sends)
    assert {s.arg["file_ref"].file_id for s in sends} == {"f1", "f2"}
    assert all(s.arg["run_id"] == "run_x" for s in sends)


def test_dispatch_only_targets_revision_files_on_redo():
    """Redo pass: Sends only for files flagged by revision_requests."""
    review = SummaryReview(
        revision_requests=[RevisionRequest(file_id="f2", reason="weak_citation", detail="sparse")],
        notes="",
    )
    state = {"run_id": "run_x", "files": [_ref("f1"), _ref("f2")], "summary_review": review}
    sends = dispatch_fanout(state)
    assert len(sends) == 1
    assert sends[0].arg["file_ref"].file_id == "f2"
