"""The ledger exports keep their contract.

Every line is one engine episode. The schema is fixed, the proof of every
derived claim re-validates, and the fields the release withholds are not
there: no belief breakdown, no planner arithmetic, no entropy, and no
reliability attached to a built-in rule.

Copyright (c) 2026 Kiran Nayudu. Apache-2.0."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import read_jsonl
from unknown_goals.checker import SCHEMA, builtin_rule_ids, check_episode

TOP_LEVEL = ["schema", "engine", "artifact", "episode_key", "entities",
             "claims", "rules", "decisions", "result"]

# The belief arithmetic's origin story, and the planner's numbers. None of
# it ships: the paper withholds how support, contradiction, age and rule
# reliability combine, and the demonstration build prints none of it either.
FORBIDDEN_KEYS = {
    "breakdown", "prior", "path_confidence", "contradiction_penalty",
    "age_weights", "raw_score", "normalization_denominator", "final_belief",
    "expected_information_gain", "expected_success_prob", "cost", "risk",
    "value", "entropy_before", "entropy_after",
}

# A provenance key naming one of these is a window, an anchor or a gate of
# the withheld machinery and must have been removed before shipping.
FORBIDDEN_PROVENANCE_SUBSTRINGS = ("window", "anchor", "decay", "half",
                                   "floor", "gate")


def _keys(obj, out: set[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.add(k)
            _keys(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _keys(v, out)


def test_there_are_exports(exports):
    assert exports, ("data/exports/ is empty: the kit cannot re-validate any "
                     "proof without the ledger exports")


def test_every_line_has_the_schema_and_its_fields(exports):
    if not exports:
        pytest.skip("no exports in this tree")
    for path in exports:
        for i, ep in enumerate(read_jsonl(path), 1):
            assert ep.get("schema") == SCHEMA, f"{path.name}:{i}"
            assert list(ep) == TOP_LEVEL, f"{path.name}:{i}: {list(ep)}"
            assert ep["episode_key"], f"{path.name}:{i}: empty episode key"
            assert str(ep["artifact"]).startswith("data/artifacts/"), \
                f"{path.name}:{i}: {ep['artifact']}"
            assert set(ep["result"]) >= {
                "success", "found_at", "ground_truth_location", "correct",
                "steps_used", "goal_status"}, f"{path.name}:{i}"


def test_no_withheld_field_is_exported(exports):
    if not exports:
        pytest.skip("no exports in this tree")
    for path in exports:
        seen: set[str] = set()
        for ep in read_jsonl(path):
            _keys(ep, seen)
        leaked = sorted(seen & FORBIDDEN_KEYS)
        assert not leaked, f"{path.name} exports withheld fields: {leaked}"


def test_no_provenance_key_names_a_withheld_mechanism(exports):
    if not exports:
        pytest.skip("no exports in this tree")
    for path in exports:
        bad: set[str] = set()
        for ep in read_jsonl(path):
            for claim in ep["claims"]:
                for k in (claim.get("provenance") or {}):
                    low = k.lower()
                    if any(s in low for s in FORBIDDEN_PROVENANCE_SUBSTRINGS):
                        bad.add(k)
        assert not bad, f"{path.name} provenance keys: {sorted(bad)}"


def test_builtin_rules_ship_without_their_reliability(exports):
    if not exports:
        pytest.skip("no exports in this tree")
    builtin = builtin_rule_ids()
    for path in exports:
        for i, ep in enumerate(read_jsonl(path), 1):
            for rule in ep["rules"]:
                if rule["rule_id"] in builtin:
                    assert "reliability" not in rule, (
                        f"{path.name}:{i}: built-in rule "
                        f"{rule['rule_id']} carries a reliability")


def test_every_proof_in_every_export_replays(exports):
    if not exports:
        pytest.skip("no exports in this tree")
    for path in exports:
        valid = total = 0
        errors: list[str] = []
        for ep in read_jsonl(path):
            v, t, errs = check_episode(ep)
            valid += v
            total += t
            errors += errs
        assert not errors, (f"{path.name}: {len(errors)} invalid proofs, "
                            f"first: {errors[0]}")
        assert valid == total


def test_the_export_names_an_artifact_that_ships(exports, kit: Path):
    if not exports:
        pytest.skip("no exports in this tree")
    for path in exports:
        first = next(read_jsonl(path), None)
        assert first is not None, f"{path.name} is empty"
        artifact = kit / first["artifact"]
        assert artifact.exists(), (f"{path.name} names {first['artifact']}, "
                                   f"which is not in the kit")
