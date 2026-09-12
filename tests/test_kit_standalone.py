"""The kit stands on its own: it imports, it runs a scenario end to end
under the episode contract, and none of it needs the engine.

Copyright (c) 2026 Kiran Nayudu. Apache-2.0."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from baselines.scripted_baselines import (
    action_menu,
    run_filter_episode,
    run_scripted_episode,
)
from unknown_goals.core.config import DEFAULT_CONFIG
from unknown_goals.simulation.generator import generate


def test_the_shipped_configuration_is_the_paper_s():
    assert DEFAULT_CONFIG.budget.max_actions == 8
    assert DEFAULT_CONFIG.budget.max_time_steps == 60
    assert DEFAULT_CONFIG.planner.inspect_tp_rate == 0.97
    assert DEFAULT_CONFIG.planner.scan_tp_rate == 0.98
    assert DEFAULT_CONFIG.config_version == "0.2.0"
    assert DEFAULT_CONFIG.rules_version == "0.2.0"


def test_a_generated_world_is_a_deterministic_function_of_the_seed():
    a_spec, a_evidence = generate(20000, 5)
    b_spec, b_evidence = generate(20000, 5)
    assert a_spec.model_dump(mode="json") == b_spec.model_dump(mode="json")
    assert [c.model_dump(mode="json") for c in a_evidence] == \
        [c.model_dump(mode="json") for c in b_evidence]
    c_spec, _ = generate(20001, 5)
    assert c_spec.model_dump(mode="json") != a_spec.model_dump(mode="json")


@pytest.mark.parametrize("policy", ["sweep", "random", "lastseen"])
def test_a_scripted_policy_finishes_an_episode(policy: str):
    spec, evidence = generate(20000, 4)
    row = run_scripted_episode(spec, evidence, policy, 20000)
    assert row["steps"] <= DEFAULT_CONFIG.budget.max_actions
    assert set(row) == {"seed", "truth", "ground_truth", "success",
                        "found_at", "correct", "steps"}
    assert row["correct"] == bool(row["success"]
                                  and row["found_at"] == row["ground_truth"])


def test_the_filter_baseline_finishes_an_episode():
    spec, evidence = generate(20000, 4)
    row = run_filter_episode(spec, evidence, 20000)
    assert row["steps"] <= DEFAULT_CONFIG.budget.max_actions


def test_the_action_menu_is_every_place_a_policy_could_look():
    spec, _ = generate(20000, 4)
    menu = action_menu(spec)
    assert menu
    assert len({(a.action_type, a.target) for a in menu}) == len(menu)


def test_the_exact_belief_planner_matches_its_shipped_rows(kit: Path):
    """Six budgets x twelve seeds x five levels is the shipped sweep; one
    cell of it here keeps the test fast and still exercises the exact DP."""
    from baselines.belief_planner import run_planner_episode

    shipped = kit / "data" / "artifacts" / "belief_planner_sweep_12.json"
    if not shipped.exists():
        pytest.skip("belief_planner_sweep_12.json not in this tree")
    data = json.loads(shipped.read_text(encoding="utf-8"))
    budget = str(data["budgets"][-1])
    want = [r for r in data["results"][budget]["episodes"]
            if r["level"] == 5][:4]
    assert want, "no level-5 rows in the shipped planner sweep"

    config = DEFAULT_CONFIG.model_copy(deep=True)
    config.budget.max_actions = int(budget)
    for row in want:
        spec, evidence = generate(row["seed"], 5)
        got = run_planner_episode(spec, evidence, row["seed"], config=config)
        assert got["correct"] == row["correct"], row
        assert got["steps"] == row["steps"], row
        assert got["found_at"] == row["found_at"], row


def test_the_checker_and_the_replayer_have_console_entry_points():
    from unknown_goals import checker, replay, verify
    for module in (checker, replay, verify):
        assert callable(module.main)
