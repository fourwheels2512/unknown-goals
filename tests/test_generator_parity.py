"""The kit's scenario generator is the engine's scenario generator.

The whole benchmark rests on this: the paper's seeds have to name the same
worlds here that they name inside the engine, or every baseline in this kit
is measured on a different problem. The check is exact -- the full
serialised world specification and the full briefing evidence, for every
seed 1..20 at every level 1..6 -- and it runs only where both packages are
importable, which is the engine's own development environment.

    pytest tests/test_generator_parity.py        # from the engine checkout

Everywhere else it skips, because the engine is not distributed.

Copyright (c) 2026 Kiran Nayudu. Apache-2.0."""

from __future__ import annotations

import pytest

from unknown_goals.simulation.generator import generate as kit_generate

engine = pytest.importorskip(
    "robot_mind.simulation.generator",
    reason="the engine is not importable here, which is the normal case")
engine_generate = engine.generate

SEEDS = range(1, 21)
LEVELS = range(1, 7)


@pytest.mark.parametrize("level", LEVELS)
def test_the_same_seed_makes_the_same_world(level: int):
    for seed in SEEDS:
        kit_spec, kit_evidence = kit_generate(seed, level)
        eng_spec, eng_evidence = engine_generate(seed, level)
        assert kit_spec.model_dump(mode="json") == \
            eng_spec.model_dump(mode="json"), f"seed {seed} level {level}: world"
        assert [c.model_dump(mode="json") for c in kit_evidence] == \
            [c.model_dump(mode="json") for c in eng_evidence], \
            f"seed {seed} level {level}: briefing evidence"


def test_the_random_substreams_are_derived_identically():
    from robot_mind.core.seeds import substream as engine_substream

    from unknown_goals.core.seeds import substream as kit_substream
    for seed in (0, 1, 42, 20000, 10007):
        for name in ("layout", "events", "evidence", "noise", "decoys"):
            kit_rng, engine_rng = kit_substream(seed, name), \
                engine_substream(seed, name)
            a = [kit_rng.random() for _ in range(5)]
            b = [engine_rng.random() for _ in range(5)]
            assert a == b, f"substream {name!r} at seed {seed}"
