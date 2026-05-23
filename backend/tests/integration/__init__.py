"""Integration tests.

Touch real systems: Ollama (LLM), Redis Stack (LangGraph checkpointer + module
healthcheck), the production SQLite engine, and on-disk parser fixtures. Tests
are gated by ``_ollama_up`` / ``redis_healthcheck()`` skipif markers when their
dependency is not reachable.
"""
