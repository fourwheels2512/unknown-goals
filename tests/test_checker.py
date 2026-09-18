"""The proof checker accepts a sound proof and rejects an unsound one, for
the reason it is unsound.

Copyright (c) 2026 Kiran Nayudu. Apache-2.0."""

from __future__ import annotations

import json

from conftest import BROKEN_EPISODE, GOOD_EPISODE
from unknown_goals.checker import (
    builtin_rule_ids,
    check_certificate,
    check_commitment,
    check_episode,
    check_export,
    known_operators,
    main,
    summary_line,
)


def test_builtin_rule_table_ships_without_reliabilities():
    from pathlib import Path

    import unknown_goals
    rows = json.loads(
        (Path(unknown_goals.__file__).parent / "data" / "builtin_rules.json")
        .read_text(encoding="utf-8"))
    assert rows, "the built-in rule table is empty"
    for row in rows:
        assert set(row) == {"rule_id", "description", "status", "version"}
    assert builtin_rule_ids() == {r["rule_id"] for r in rows}


def test_sound_proof_is_accepted():
    valid, total, errors = check_episode(GOOD_EPISODE)
    assert (valid, total) == (1, 1)
    assert errors == []


def test_unsound_proof_is_rejected_for_every_reason():
    valid, total, errors = check_episode(BROKEN_EPISODE)
    assert (valid, total) == (0, 1)
    assert len(errors) == 1
    why = errors[0]
    assert "dangling input c99" in why
    assert "unknown rule rule_that_does_not_exist" in why
    assert "violated constraint" in why


def test_a_derived_claim_with_no_proof_is_rejected():
    episode = json.loads(json.dumps(GOOD_EPISODE))
    episode["claims"][2]["proof"] = None
    valid, total, errors = check_episode(episode)
    assert (valid, total) == (0, 1)
    assert "missing proof" in errors[0]


def test_a_proof_with_no_operator_is_rejected():
    episode = json.loads(json.dumps(GOOD_EPISODE))
    episode["claims"][2]["proof"]["operator"] = ""
    valid, total, errors = check_episode(episode)
    assert (valid, total) == (0, 1)
    assert "missing operator" in errors[0]


def test_only_derived_claims_are_checked():
    episode = json.loads(json.dumps(GOOD_EPISODE))
    episode["claims"][2]["status"] = "OBSERVED"
    valid, total, errors = check_episode(episode)
    assert (valid, total) == (0, 0)
    assert errors == []


def test_a_derived_claim_later_contradicted_is_still_checked():
    """The engine's own checker tests the status the claim was ingested
    with, not the status it ended in; the kit does the same, so a claim
    that was derived and then refuted still has to carry a sound proof."""
    episode = json.loads(json.dumps(GOOD_EPISODE))
    episode["claims"][2]["effective_status"] = "CONTRADICTED"
    valid, total, _ = check_episode(episode)
    assert (valid, total) == (1, 1)


def test_the_operator_table_ships_with_a_description_for_each_operator():
    from pathlib import Path

    import unknown_goals
    table = json.loads(
        (Path(unknown_goals.__file__).parent / "data" / "operators.json")
        .read_text(encoding="utf-8"))
    assert table["schema"] == "unknown-goals-proof-operators/1"
    rows = table["operators"]
    assert rows, "the operator table is empty"
    for row in rows:
        assert set(row) == {"operator", "description"}
        assert row["description"].strip()
    assert known_operators() == {r["operator"] for r in rows}
    assert len(known_operators()) == len(rows), "a duplicated operator name"


def test_an_operator_the_engine_does_not_emit_is_rejected():
    episode = json.loads(json.dumps(GOOD_EPISODE))
    episode["claims"][2]["proof"]["operator"] = "vibes"
    valid, total, errors = check_episode(episode)
    assert (valid, total) == (0, 1)
    assert "unknown operator 'vibes'" in errors[0]


def test_an_input_that_reached_the_ledger_last_is_rejected():
    episode = json.loads(json.dumps(GOOD_EPISODE))
    episode["claims"][1]["ingested_at"] = 40
    valid, total, errors = check_episode(episode)
    assert (valid, total) == (0, 1)
    assert "input c2 reached the ledger at 40, after the claim it supports " \
           "at 12" in errors[0]


def test_an_episode_with_no_verdict_fields_is_not_silently_passed():
    """Every export shipped with this kit predates the verdict fields. The
    checker says so rather than counting those episodes as checked."""
    assert check_commitment(GOOD_EPISODE) == ("not checkable", [])
    assert check_certificate(GOOD_EPISODE) == ("none", [])


def test_check_export_reads_a_file_and_totals_it(tiny_export):
    summary = check_export(tiny_export)
    assert summary["n_episodes"] == 2
    assert (summary["valid"], summary["total"]) == (1, 2)
    assert summary["rate"] == 0.5
    assert len(summary["errors"]) == 1
    assert "test=TB" in summary["errors"][0]
    assert summary["commitments_not_checkable"] == 2
    assert summary["commitments_checked"] == summary["commitments_failed"] == 0
    assert summary["certificates_checked"] == summary["certificates_failed"] == 0
    assert summary_line(summary) == (
        "commitments 0 checked, 0 failed, 2 not checkable; "
        "certificates 0 checked, 0 failed")


def test_cli_exits_non_zero_on_an_invalid_proof(tiny_export, capsys):
    assert main([str(tiny_export)]) == 1
    out = capsys.readouterr()
    assert "proofs 1/2" in out.out


def test_cli_exits_non_zero_when_the_expected_fraction_differs(tiny_export):
    assert main([str(tiny_export), "--expect-proofs", "1.0"]) == 1
