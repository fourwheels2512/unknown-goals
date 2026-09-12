"""The configuration the benchmark kit needs, and nothing else.

The engine's own configuration carries the tuned constants of the belief
arithmetic, the planner, the drives, the bandit and the induction
lifecycle. Those are withheld from this release (see the paper's
"Reproducibility and data availability"). What the kit's baselines and the
executor actually read is here, and every value in this file is stated in
the paper:

  * the action budget, 8 actions, and the 60-step time cap;
  * the sensor model the executor and the exact belief-space planner both
    use: an inspection finds a visible object with probability 0.97, an
    RFID scan finds a contained object with probability 0.98.

`SensorConfig` is reached as `config.planner` so that the baselines and the
executor read exactly the same attribute names they read inside the engine;
nothing else of the engine's planner is in this file.

`config_version` and `rules_version` are the strings the committed
artifacts record, so a regenerated artifact compares equal to the shipped
one field for field.

Copyright (c) 2026 Kiran Nayudu. Apache-2.0."""

from __future__ import annotations

from pydantic import BaseModel

CONFIG_VERSION = "0.2.0"
RULES_VERSION = "0.2.0"


class SensorConfig(BaseModel):
    """The executor's true sensor model (paper, episode contract)."""

    inspect_tp_rate: float = 0.97     # inspection finds a visible object
    scan_tp_rate: float = 0.98        # RFID scan finds a contained object


class BudgetConfig(BaseModel):
    max_actions: int = 8
    max_time_steps: int = 60


class EngineConfig(BaseModel):
    config_version: str = CONFIG_VERSION
    rules_version: str = RULES_VERSION
    planner: SensorConfig = SensorConfig()
    budget: BudgetConfig = BudgetConfig()


DEFAULT_CONFIG = EngineConfig()
