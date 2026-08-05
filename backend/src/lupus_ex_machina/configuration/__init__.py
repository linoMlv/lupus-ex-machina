"""Everything a game can be set to, in one schema (D-068).

This package holds the configuration the user edits and the front end derives
its form from. It imports the engine — the rules a game is played by are the
engine's own types — and the engine never imports it back: a rule must be
readable without knowing which model sits in which seat.
"""
