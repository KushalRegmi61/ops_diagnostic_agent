"""Prompt package for the diagnostic agent.

Each submodule owns the prompt string for one lead-graph node or per-file brief.
Prompts use ``str.format`` placeholders that the corresponding graph/agent fills
with JSON-serialised state (file summaries, intake bundle, opportunities, etc.)
just before calling ``LLMProvider.generate_json``.
"""
