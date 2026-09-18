"""Forgeries the checker has to reject.

A checker that only replays provenance can be satisfied by an export that
was written rather than run: cite claims that exist, name a rule, assert no
time constraint, and every proof "replays". These tests take two episodes
that are sound -- one that ends with the object found, one that ends with a
certificate that it is in none of the rooms the robot knows about -- and one
real episode out of a shipped export, and change one thing at a time. Each
change is something a forger would do, and each must be caught, by a message
that names the claim at fault.

The sound NOT-FOUND episode here is built from the specification of the
absence certificate, not from the engine's code: six rooms, one second-hand
tip that places the object before the sweep begins, six looks of the robot's
own that each found a room empty afterwards, and one certificate citing all
seven. A look of the robot's own is an observation one of its actions
returned, and carries the mark that says so; an OBSERVED absence without it
came from somewhere the robot was not, and does not clear a room.

Copyright (c) 2026 Kiran Nayudu. Apache-2.0."""

from __future__ import annotations

import json

import pytest
from conftest import GOOD_EPISODE, read_jsonl
from unknown_goals.checker import (
    check_certificate,
    check_commitment,
    check_episode,
    check_export,
    known_operators,
)

TARGET = "wrench_1"
ROOMS = ["bay_a", "bay_b", "bay_c", "bay_d", "bay_e", "bay_f"]
# bay_a is looked at first, bay_f last
ABSENCE_TIMES = {room: 10 + i for i, room in enumerate(ROOMS)}


def _claim(cid, subject, predicate, obj, t0, t1, status, source_id="test",
           conf=0.9, proof=None, provenance=None):
    return {"claim_id": cid, "subject": subject, "predicate": predicate,
            "obj": obj, "event_time_start": t0, "event_time_end": t1,
            "ingested_at": t1, "source_id": source_id, "confidence": conf,
            "status": status, "proof": proof,
            "provenance": provenance or {},
            "effective_status": status, "status_history": []}


def _entity(eid, etype, name):
    return {"entity_id": eid, "entity_type": etype, "name": name,
            "aliases": []}


def _not_found_episode() -> dict:
    absences = [
        _claim(f"a_{room}", TARGET, "ABSENT_FROM", room,
               ABSENCE_TIMES[room], ABSENCE_TIMES[room], "OBSERVED",
               source_id="robot_eyes", conf=0.97,
               provenance={"via_action": True})
        for room in ROOMS]
    tip = _claim("tip_1", TARGET, "LOCATED_AT", "bay_c", 5, 5, "REPORTED",
                 source_id="foreman", conf=0.6)
    certificate = _claim(
        "cert_1", TARGET, "ABSENT_FROM", "all_known_locations", 20, 20,
        "DERIVED", source_id="reasoner", conf=0.97,
        proof={"operator": "coverage_certificate",
               "input_claims": [f"a_{room}" for room in ROOMS] + ["tip_1"],
               "rule_ids": [],
               "assumptions": ["rooms: " + ",".join(ROOMS),
                               "absences observed by: robot_eyes"],
               "time_constraints": [f"a_{room}.event_time >= "
                                    f"tip_1.event_time" for room in ROOMS]},
        provenance={"certificate": True})
    return {
        "schema": "unknown-goals-ledger-export/1",
        "engine": {"version": "0.5.0", "config_version": "0.2.0",
                   "rules_version": "0.2.0"},
        "artifact": "data/artifacts/handwritten.json",
        "episode_key": {"test": "TN", "seed": 11, "level": 4},
        "entities": [_entity(TARGET, "TOOL", "wrench")]
                    + [_entity(room, "LOCATION", room.replace("_", " "))
                       for room in ROOMS],
        "claims": [tip] + absences + [certificate],
        "rules": [],
        "decisions": [],
        "result": {"success": False, "target": TARGET,
                   "verdict": "NOT_FOUND", "found_at": None,
                   "ground_truth_location": None, "correct": False,
                   "steps_used": 6, "goal_status": "NOT_FOUND"},
    }


def _found_episode() -> dict:
    """The kit's sound episode, with the find witnessed and the verdict
    fields the newer exports carry."""
    episode = json.loads(json.dumps(GOOD_EPISODE))
    episode["episode_key"] = {"test": "TF", "seed": 12, "level": 2}
    episode["claims"].append(
        _claim("c4", "wrench_1", "LOCATED_AT", "bay_a", 14, 14, "OBSERVED",
               source_id="robot_eyes", conf=0.97))
    episode["result"]["target"] = "wrench_1"
    episode["result"]["verdict"] = "FOUND"
    return episode


@pytest.fixture
def found() -> dict:
    return _found_episode()


@pytest.fixture
def not_found() -> dict:
    return _not_found_episode()


def _certificate(episode: dict) -> dict:
    return next(c for c in episode["claims"]
                if (c.get("proof") or {}).get("operator")
                == "coverage_certificate")


def _confirming(episode: dict) -> dict:
    return next(c for c in episode["claims"] if c["claim_id"] == "c4")


# --------------------------------------------------------------------------
# the unmutated episodes pass
# --------------------------------------------------------------------------

def test_the_sound_found_episode_passes(found):
    valid, total, errors = check_episode(found)
    assert (valid, total) == (1, 1)
    assert errors == []
    assert check_commitment(found) == ("checked", [])
    assert check_certificate(found) == ("none", [])


def test_the_sound_not_found_episode_passes(not_found):
    valid, total, errors = check_episode(not_found)
    assert (valid, total) == (1, 1), errors
    assert errors == []
    assert check_commitment(not_found) == ("checked", [])
    assert check_certificate(not_found) == ("checked", [])


# --------------------------------------------------------------------------
# provenance forgeries
# --------------------------------------------------------------------------

def test_a_deleted_input_claim_is_caught(found):
    found["claims"] = [c for c in found["claims"] if c["claim_id"] != "c2"]
    valid, total, errors = check_episode(found)
    assert (valid, total) == (0, 1)
    assert "dangling input c2" in errors[0]
    assert errors[0].startswith("c3:")


def test_a_changed_rule_id_is_caught(found):
    found["claims"][2]["proof"]["rule_ids"] = ["rule_carrier_location_v2"]
    valid, total, errors = check_episode(found)
    assert (valid, total) == (0, 1)
    assert "unknown rule rule_carrier_location_v2" in errors[0]
    assert errors[0].startswith("c3:")


def test_an_operator_outside_the_table_is_caught(found):
    found["claims"][2]["proof"]["operator"] = "temporal_graph_traversal_v2"
    valid, total, errors = check_episode(found)
    assert (valid, total) == (0, 1)
    assert "unknown operator 'temporal_graph_traversal_v2'" in errors[0]
    assert errors[0].startswith("c3:")


def test_the_operator_table_covers_what_the_engine_emits():
    operators = known_operators()
    assert {"temporal_graph_traversal", "refuted_fallback_search",
            "weak_sighting_search", "coverage_certificate",
            "llm_proposal"} <= operators
    assert "temporal_graph_traversal_v2" not in operators


def test_an_input_ingested_after_its_conclusion_is_caught(found):
    # c1 is cited by c3; move it onto the ledger after c3 was derived
    found["claims"][0]["ingested_at"] = 99
    valid, total, errors = check_episode(found)
    assert (valid, total) == (0, 1)
    assert "input c1 reached the ledger at 99, after the claim it supports " \
           "at 12" in errors[0]
    assert errors[0].startswith("c3:")


# --------------------------------------------------------------------------
# commitment forgeries
# --------------------------------------------------------------------------

def test_a_commitment_to_a_room_nothing_witnessed_is_caught(found):
    found["result"]["found_at"] = "bay_b"
    status, errors = check_commitment(found)
    assert status == "failed"
    assert errors == ["committed to wrench_1 at bay_b with no observation of "
                      "it there: no OBSERVED LOCATED_AT(wrench_1, bay_b) on "
                      "this ledger"]


def test_a_confirmation_below_the_resolution_bar_is_caught(found):
    _confirming(found)["confidence"] = 0.8
    status, errors = check_commitment(found)
    assert status == "failed"
    assert len(errors) == 1
    assert errors[0].startswith("c4: cannot witness the commitment to "
                                "wrench_1 at bay_a")
    assert "confidence 0.8 is below the resolution bar 0.9" in errors[0]


def test_a_confirmation_the_reasoner_signed_itself_is_caught(found):
    _confirming(found)["source_id"] = "reasoner"
    status, errors = check_commitment(found)
    assert status == "failed"
    assert len(errors) == 1
    assert errors[0].startswith("c4: cannot witness the commitment to "
                                "wrench_1 at bay_a")
    assert "the reasoner is its own source" in errors[0]


def test_a_verdict_of_not_found_with_no_certificate_is_caught(not_found):
    not_found["claims"] = [c for c in not_found["claims"]
                           if c["claim_id"] != "cert_1"]
    status, errors = check_commitment(not_found)
    assert status == "failed"
    assert errors == ["verdict NOT_FOUND for wrench_1 with no absence "
                      "certificate on the ledger"]


def test_a_certificate_in_an_episode_that_found_the_object_is_caught(not_found):
    not_found["result"]["verdict"] = "FOUND"
    not_found["result"]["found_at"] = "bay_c"
    status, errors = check_commitment(not_found)
    assert status == "failed"
    assert any(e.startswith("cert_1: an absence certificate in an episode "
                            "whose verdict is FOUND") for e in errors), errors


def test_an_export_without_the_verdict_fields_is_counted_not_passed():
    status, errors = check_commitment(GOOD_EPISODE)
    assert (status, errors) == ("not checkable", [])


# --------------------------------------------------------------------------
# certificate forgeries
# --------------------------------------------------------------------------

def test_a_certificate_that_cites_five_of_six_rooms_is_caught(not_found):
    proof = _certificate(not_found)["proof"]
    proof["input_claims"] = [c for c in proof["input_claims"]
                             if c != "a_bay_f"]
    status, errors = check_certificate(not_found)
    assert status == "failed"
    assert errors == ["cert_1: cites nothing that found bay_f empty of "
                      "wrench_1"]


def test_a_certificate_that_also_shortens_its_own_room_list_is_caught(not_found):
    """The same forgery with the paperwork tidied: the certificate claims it
    only ever had to sweep five rooms. The rooms are recomputed from the
    export's own entities, so the sixth is still there."""
    proof = _certificate(not_found)["proof"]
    proof["input_claims"] = [c for c in proof["input_claims"]
                             if c != "a_bay_f"]
    proof["assumptions"][0] = "rooms: " + ",".join(ROOMS[:-1])
    status, errors = check_certificate(not_found)
    assert status == "failed"
    assert "cert_1: says it swept 5 of the 6 rooms it had to: leaves out " \
           "bay_f" in errors
    assert "cert_1: cites nothing that found bay_f empty of wrench_1" in errors


def test_a_certificate_resting_on_a_second_hand_absence_is_caught(not_found):
    """bay_f is cleared by a tip rather than by a look of the robot's own."""
    for claim in not_found["claims"]:
        if claim["claim_id"] == "a_bay_f":
            claim["status"] = "REPORTED"
            claim["source_id"] = "foreman"
    status, errors = check_certificate(not_found)
    assert status == "failed"
    assert errors == ["cert_1: nothing clears bay_f: a_bay_f is a REPORTED "
                      "absence from bay_f, and only a look of the robot's "
                      "own clears a room"]


def test_a_certificate_resting_on_a_third_partys_camera_is_caught(not_found):
    """bay_f is cleared by a fixed camera's report rather than by a look of
    the robot's own. Every provenance test passes -- the claim is there, it
    is OBSERVED, it is confident, it postdates the tip -- and the room is
    still not covered, because the robot was never in it."""
    for claim in not_found["claims"]:
        if claim["claim_id"] == "a_bay_f":
            claim["source_id"] = "ceiling_camera"
            claim["provenance"] = {}
    valid, total, proof_errors = check_episode(not_found)
    assert (valid, total) == (1, 1), proof_errors   # the provenance replays
    status, errors = check_certificate(not_found)
    assert status == "failed"
    assert errors == ["cert_1: nothing clears bay_f: a_bay_f is an absence "
                      "from bay_f that no action of the robot's returned, "
                      "and only a look of the robot's own clears a room"]


def test_the_robots_own_later_look_at_that_room_clears_it(not_found):
    """The same room, with the robot's own look added after the camera's
    report: the certificate cites both and the room is covered."""
    camera = _claim("cam_bay_f", TARGET, "ABSENT_FROM", "bay_f", 13, 13,
                    "OBSERVED", source_id="ceiling_camera", conf=0.99)
    not_found["claims"].insert(1, camera)
    _certificate(not_found)["proof"]["input_claims"].append("cam_bay_f")
    status, errors = check_certificate(not_found)
    assert (status, errors) == ("checked", [])


def test_a_later_tip_the_certificate_ignores_is_caught(not_found):
    """A tip places the object after two of the rooms were swept, and the
    forged certificate simply does not mention it: neither in what it cites
    nor in the constraints it asserts. The checker recomputes the last claim
    that placed the object, so leaving it out changes nothing."""
    not_found["claims"].insert(
        1, _claim("tip_2", TARGET, "LOCATED_AT", "bay_e", 12, 12, "REPORTED",
                  source_id="foreman", conf=0.6))
    valid, total, proof_errors = check_episode(not_found)
    assert (valid, total) == (1, 1), proof_errors   # the provenance replays
    status, errors = check_certificate(not_found)
    assert status == "failed"
    assert "cert_1: does not cite tip_2, the last report that placed " \
           "wrench_1 (LOCATED_AT bay_e, ending at 12)" in errors
    assert "cert_1: nothing clears bay_a: a_bay_a found bay_a empty at 10, " \
           "before tip_2 placed wrench_1 at 12" in errors
    assert "cert_1: nothing clears bay_b: a_bay_b found bay_b empty at 11, " \
           "before tip_2 placed wrench_1 at 12" in errors
    # the rooms swept at or after the tip are untouched
    stale = sorted(e.split("nothing clears ")[1].split(":")[0]
                   for e in errors if "nothing clears " in e)
    assert stale == ["bay_a", "bay_b"], errors


def test_a_forged_time_constraint_does_not_save_a_stale_sweep(not_found):
    """The same forgery with the constraint list rewritten to point at the
    old tip, which the sweep does satisfy. The recomputation ignores what
    the proof asserts about itself."""
    not_found["claims"].insert(
        1, _claim("tip_2", TARGET, "LOCATED_AT", "bay_e", 12, 12, "REPORTED",
                  source_id="foreman", conf=0.6))
    proof = _certificate(not_found)["proof"]
    proof["input_claims"] = [f"a_{room}" for room in ROOMS] + ["tip_1"]
    proof["time_constraints"] = [f"a_{room}.event_time >= tip_1.event_time"
                                 for room in ROOMS]
    valid, total, _ = check_episode(not_found)
    assert (valid, total) == (1, 1)
    status, errors = check_certificate(not_found)
    assert status == "failed"
    assert any("does not cite tip_2" in e for e in errors), errors


def test_two_certificates_in_one_episode_are_caught(not_found):
    second = json.loads(json.dumps(_certificate(not_found)))
    second["claim_id"] = "cert_2"
    not_found["claims"].append(second)
    status, errors = check_certificate(not_found)
    assert status == "failed"
    assert errors[0] == ("cert_1, cert_2: 2 absence certificates in one "
                         "episode; an episode ends once, so it certifies once")


def test_a_certificate_over_a_room_the_episode_does_not_know_is_caught(not_found):
    proof = _certificate(not_found)["proof"]
    proof["assumptions"].append("excluded: bay_z")
    status, errors = check_certificate(not_found)
    assert status == "failed"
    assert "cert_1: excludes bay_z, which this episode does not know as " \
           "rooms" in errors


def test_an_exclusion_is_taken_at_its_word_and_then_enforced(not_found):
    """Excluding a room as unreachable is the one thing the export cannot
    settle, so the checker takes the exclusion at its word -- and then holds
    the certificate to the room list that exclusion implies. This is the
    residual gap: a forger who declares a room unreachable is believed about
    that room, and about nothing else."""
    proof = _certificate(not_found)["proof"]
    proof["input_claims"] = [c for c in proof["input_claims"]
                             if c != "a_bay_f"]
    proof["assumptions"][0] = "rooms: " + ",".join(ROOMS[:-1])
    proof["assumptions"].append("excluded: bay_f")
    status, errors = check_certificate(not_found)
    assert (status, errors) == ("checked", [])


# --------------------------------------------------------------------------
# the same forgeries on a real episode out of a shipped export
# --------------------------------------------------------------------------

def _real_episode(exports) -> dict:
    for path in exports:
        for episode in read_jsonl(path):
            derived = [c for c in episode["claims"]
                       if c["status"] == "DERIVED"
                       and (c.get("proof") or {}).get("input_claims")]
            if len(derived) >= 3:
                return episode
    pytest.skip("no shipped export carries an episode with three derived "
                "claims that cite evidence")


@pytest.fixture
def real(exports) -> dict:
    if not exports:
        pytest.skip("no exports in this tree")
    return _real_episode(exports)


def _first_derived(episode: dict) -> dict:
    return next(c for c in episode["claims"]
                if c["status"] == "DERIVED"
                and (c.get("proof") or {}).get("input_claims"))


def test_a_real_episode_replays(real):
    valid, total, errors = check_episode(real)
    assert errors == []
    assert valid == total > 0


def test_a_real_episode_with_an_input_deleted_is_caught(real):
    claim = _first_derived(real)
    cited = claim["proof"]["input_claims"][0]
    real["claims"] = [c for c in real["claims"] if c["claim_id"] != cited]
    valid, total, errors = check_episode(real)
    assert valid < total
    assert any(e.startswith(f"{claim['claim_id']}:")
               and f"dangling input {cited}" in e for e in errors), errors


def test_a_real_episode_with_a_renamed_operator_is_caught(real):
    claim = _first_derived(real)
    claim["proof"]["operator"] = "hand_of_the_author"
    valid, total, errors = check_episode(real)
    assert valid == total - 1
    assert [e for e in errors
            if e == f"{claim['claim_id']}: unknown operator "
                    f"'hand_of_the_author'"], errors


def test_a_real_episode_with_a_renamed_rule_is_caught(real):
    claim = _first_derived(real)
    claim["proof"]["rule_ids"] = ["rule_invented_for_this_export"]
    valid, total, errors = check_episode(real)
    assert valid == total - 1
    assert [e for e in errors
            if e == f"{claim['claim_id']}: unknown rule "
                    f"rule_invented_for_this_export"], errors


def test_a_real_episode_with_an_input_ingested_too_late_is_caught(real):
    claim = _first_derived(real)
    cited = claim["proof"]["input_claims"][0]
    late = claim["ingested_at"] + 1000
    for c in real["claims"]:
        if c["claim_id"] == cited:
            c["ingested_at"] = late
    valid, total, errors = check_episode(real)
    assert valid < total
    assert any(f"input {cited} reached the ledger at {late}, after the claim "
               f"it supports at {claim['ingested_at']}" in e
               for e in errors), errors


# --------------------------------------------------------------------------
# the summary counts
# --------------------------------------------------------------------------

def test_check_export_counts_commitments_and_certificates(tmp_path):
    path = tmp_path / "forgery.jsonl"
    bad = _found_episode()
    bad["episode_key"] = {"test": "TX", "seed": 13, "level": 2}
    _confirming(bad)["confidence"] = 0.8
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for episode in (_found_episode(), _not_found_episode(), bad,
                        GOOD_EPISODE):
            fh.write(json.dumps(episode) + "\n")
    summary = check_export(path)
    assert summary["n_episodes"] == 4
    assert summary["commitments_checked"] == 2
    assert summary["commitments_failed"] == 1
    assert summary["commitments_not_checkable"] == 1
    assert summary["certificates_checked"] == 1
    assert summary["certificates_failed"] == 0
    assert len(summary["errors"]) == 1
    assert summary["errors"][0].startswith(
        "[test=TX seed=13 level=2] commitment: c4:")
