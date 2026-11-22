"""Module 6: on-demand home visits for non-emergency problems.

Pure rules live here (no database, no network): the state machine (states.py), distance and coordinate checks
(geo.py), the emergency gate (gate.py), doctor ranking (matching.py) and the offer window (offers.py). Rules
decide who is offered a request; nothing here diagnoses. The suitability table, the checklist and the ranking
weights are a demo knowledge base (services/knowledge/data/home_visit_*.csv), not clinically reviewed.
"""
