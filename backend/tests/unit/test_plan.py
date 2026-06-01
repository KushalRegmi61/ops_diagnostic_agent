"""Tier-1 tests for plan-first generation (default checklist on failure)."""
from app.agents.per_file._plan import DEFAULT_PLAN, PlanChecklist, make_plan
from app.schemas import ParsedFile, ParsedSegment


def _parsed():
    return ParsedFile(
        file_id="f1", file_name="x.txt", type="txt",
        segments=[ParsedSegment(text="hello", locator={"type": "text", "line_start": 1, "line_end": 1})],
    )


class _GoodProvider:
    def generate_json(self, *, prompt_name, prompt, schema, **kw):
        return {"items": ["find workflows", "find pain signals", "cite + extract", "finalize"]}, object()


class _BrokenProvider:
    def generate_json(self, *, prompt_name, prompt, schema, **kw):
        raise RuntimeError("model unavailable")


def test_make_plan_returns_model_items_on_success():
    plan = make_plan(_GoodProvider(), _parsed())
    assert plan == ["find workflows", "find pain signals", "cite + extract", "finalize"]


def test_make_plan_falls_back_to_default_on_failure():
    plan = make_plan(_BrokenProvider(), _parsed())
    assert plan == DEFAULT_PLAN


def test_plan_checklist_clamps_to_two_to_four_items():
    pc = PlanChecklist(items=["a", "b", "c", "d", "e", "f"])
    assert 2 <= len(pc.items) <= 4
