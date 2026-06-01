"""Offline + skip-gated evaluation harness for the per-file diagnostic agent.

Builds a real multi-format corpus, runs files through ``run_react_loop`` against
the configured provider, and scores convergence + citation round-trip. Used to
certify the agent on inputs that were not hand-picked for a demo.
"""
