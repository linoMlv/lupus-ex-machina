"""Deterministic game engine.

This package owns the whole game state, the legality of every action and the
end conditions. It never calls a language model: agents hand it *intents*, it
validates them and produces a new state (D-001). A full game must be playable by
scripted agents, which is what makes the rules testable at no cost (GL-2).
"""
