"""Module 4: Medication Safety & Clinical Interaction Engine (MSCIE).

Deterministic rules decide every alert and its severity (AGENTS.md 6.2); the knowledge base is the
CSV tables in services/knowledge/data (a demo knowledge base, every row citing its source). The
engine supports the physician's decision and never makes it: any medicine can be chosen, and a
high-risk alert can be overridden with a written justification, which is logged.
"""
