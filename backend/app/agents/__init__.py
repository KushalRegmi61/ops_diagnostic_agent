"""Agent layer for the Ops Diagnostic Agent.

Hosts the two agent families that produce the diagnostic Blueprint:
``lead/`` - eight single-shot ``generate_json`` nodes that drive the parent
LangGraph workflow (review, synthesis, the five-node diagnostic chain, and
self-review); and ``per_file/`` - seven thin ReAct wrappers that summarize one
uploaded file each via tool calls bounded by ``PER_FILE_ITERATION_CAP``.
"""
