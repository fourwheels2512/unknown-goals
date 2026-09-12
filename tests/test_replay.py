"""The replayer walks an episode and prints what the decision rested on.

Copyright (c) 2026 Kiran Nayudu. Apache-2.0."""

from __future__ import annotations

import io

import pytest
from conftest import GOOD_EPISODE

from unknown_goals.replay import main, replay, select


def test_replay_prints_every_part_of_the_decision():
    out = io.StringIO()
    assert replay(GOOD_EPISODE, out=out) == 0
    text = out.getvalue()
    assert "episode test=TG seed=1 level=2" in text
    assert "step 0" in text
    assert "[3 claims on the ledger]" in text
    assert "INSPECT_LOCATION bay_a" in text
    assert "the only candidate the evidence supports" in text
    assert "belief 0.810" in text
    assert "result: CORRECT" in text
    assert "ground truth : bay_a" in text
    assert "proof audit: 1/1" in text
    assert "rule_carrier_location_v1" in text
    assert "c2.event_time >= c1.event_time" in text
    assert "checker    : VALID" in text


def test_replay_reports_an_invalid_proof(tiny_export):
    out = io.StringIO()
    episode = select(tiny_export, {"test": "TB"}, None)
    assert replay(episode, out=out) == 1
    assert "INVALID" in out.getvalue()


def test_select_by_key_and_by_index(tiny_export):
    assert select(tiny_export, {"test": "TG"}, None)["episode_key"]["seed"] == 1
    assert select(tiny_export, {}, 1)["episode_key"]["seed"] == 2
    with pytest.raises(SystemExit):
        select(tiny_export, {"test": "nope"}, None)
    with pytest.raises(SystemExit):
        select(tiny_export, {}, 99)


def test_cli_lists_episodes(tiny_export, capsys):
    assert main([str(tiny_export), "--list"]) == 0
    listed = capsys.readouterr().out
    assert "test=TG seed=1 level=2" in listed
    assert "test=TB seed=2 level=2" in listed


def test_cli_replays_one_episode(tiny_export, capsys):
    assert main([str(tiny_export), "--episode", "test=TG"]) == 0
    assert "result: CORRECT" in capsys.readouterr().out
