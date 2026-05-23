"""Unit tests: fast, deterministic, in-process.

No external services. Tests here may use stub providers that return canned
Pydantic models, but never a mock LLM — small LLM-dependent behavior belongs in
``tests/integration``.
"""
