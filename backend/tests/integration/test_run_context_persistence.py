"""Integration: Run.run_context_json round-trips through DB and into reconstructed state."""
import pytest

from app.database import Base, SessionLocal, engine
from app.graph import initial_state
from app.models import Run
from app.schemas import RunContext

try:
    from app.checkpointer import redis_healthcheck
except ImportError:  # pragma: no cover
    redis_healthcheck = None  # type: ignore


def setup_function(_):
    """Drop and recreate DB schema before each test."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


@pytest.mark.skipif(
    redis_healthcheck is None or not redis_healthcheck(),
    reason="Redis Stack with RedisJSON+RediSearch not available",
)
def test_run_context_persists_through_db_and_state():
    """Persist user_context on Run, reconstruct RunContext, place in state — round-trip.

    Validates:
    1. RunContext serializes to run_context_json on Run insert.
    2. run_context_json deserializes back to RunContext.
    3. initial_state() accepts the reconstructed RunContext and places it in state.
    4. State contains the original user_context string.
    """
    # Step 1: Create and persist a Run with RunContext.
    with SessionLocal() as db:
        ctx = RunContext(user_context="focus onboarding")
        db.add(Run(id="r_ctx_int", status="queued", run_context_json=ctx.model_dump_json()))
        db.commit()

    # Step 2: Read back from DB and deserialize.
    with SessionLocal() as db:
        run = db.get(Run, "r_ctx_int")
        assert run is not None
        assert run.run_context_json is not None
        restored = RunContext.model_validate_json(run.run_context_json)
        assert restored.user_context == "focus onboarding"

    # Step 3: Construct initial_state with the restored RunContext.
    state = initial_state("r_ctx_int", [], run_context=restored)

    # Step 4: Verify state contains the RunContext and its user_context.
    assert state["run_context"] == restored
    assert state["run_context"].user_context == "focus onboarding"
