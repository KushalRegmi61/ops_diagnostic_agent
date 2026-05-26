"""The single file-type registry covers every parser mime and every excerpt type."""
import importlib

from app.parsers import _EXCERPT_ROUTES, _MIME_ROUTES  # type: ignore[attr-defined]
from app.registry import AGENT_BY_FILE_TYPE


def test_every_parser_file_type_has_an_agent() -> None:
    missing = sorted(set(_EXCERPT_ROUTES.keys()) - set(AGENT_BY_FILE_TYPE.keys()))
    assert missing == [], f"file types without a per-file agent: {missing}"


def test_every_agent_module_exposes_run() -> None:
    for file_type, module_name in AGENT_BY_FILE_TYPE.items():
        mod = importlib.import_module(f"app.agents.per_file.{module_name}")
        assert callable(getattr(mod, "run", None)), f"{module_name} missing run()"


def test_parser_and_excerpt_modules_agree() -> None:
    parser_modules = set(_MIME_ROUTES.values())
    excerpt_modules = set(_EXCERPT_ROUTES.values())
    assert parser_modules == excerpt_modules, (
        f"parser/excerpt module mismatch: only in parsers={parser_modules - excerpt_modules}, "
        f"only in excerpt={excerpt_modules - parser_modules}"
    )
