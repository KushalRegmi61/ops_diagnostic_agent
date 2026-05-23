"""Per-file ReAct agents.

Each module under this package (``pdf``, ``docx``, ``markdown``, ``transcript``,
``table``, ``mbox``, ``json``) is a thin wrapper that picks a file-family
``_SUFFIX`` and delegates to ``_react_loop.run_react_loop``. The loop drives a
think -> act -> observe cycle bounded by ``PER_FILE_ITERATION_CAP``, using the
tool set in ``_tools/`` and the typed dispatcher in ``_router.py``. The loop
terminates by calling ``finalize_summary``, which produces a FileSummary
consumed by the lead's ``review_summaries`` and ``synthesis`` nodes.
"""
