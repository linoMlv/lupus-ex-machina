"""Everything that talks to a language model.

Kept out of ``engine/`` on purpose, and a test enforces it (D-001): the rules of
the game must stay playable and testable with no model, no network and no cost
(GL-2). What crosses the boundary is the agent protocol, nothing else.
"""
