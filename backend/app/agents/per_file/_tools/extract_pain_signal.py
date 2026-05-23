from app.agents.per_file._state import WorkingState
from app.schemas import PainSignal, Source


def extract_pain_signal(ws: WorkingState, *, text: str, category: str, sources: list[Source]) -> dict:
    ps = PainSignal(text=text, category=category, sources=sources)
    ws.pain_signals.append(ps)
    return {"ok": True, "pain_signal_index": len(ws.pain_signals) - 1}
