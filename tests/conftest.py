"""Shared fixtures for the kit's tests.

Copyright (c) 2026 Kiran Nayudu. Apache-2.0."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

KIT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def kit() -> Path:
    return KIT


@pytest.fixture(scope="session")
def exports(kit: Path) -> list[Path]:
    d = kit / "data" / "exports"
    if not d.is_dir():
        return []
    return sorted(d.glob("*.jsonl.gz")) + sorted(d.glob("*.jsonl"))


def read_jsonl(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


# A two-episode export written by hand: the first episode's derived claim
# has a sound proof, the second's cites a claim that is not on the ledger
# and asserts a constraint that the cited times do not satisfy. The checker
# has to accept exactly one of them.
def _claim(cid, subject, predicate, obj, t0, t1, status, proof=None,
           conf=0.9):
    return {"claim_id": cid, "subject": subject, "predicate": predicate,
            "obj": obj, "event_time_start": t0, "event_time_end": t1,
            "ingested_at": t1, "source_id": "test", "confidence": conf,
            "status": status, "proof": proof, "provenance": {},
            "effective_status": status, "status_history": []}


GOOD_EPISODE = {
    "schema": "unknown-goals-ledger-export/1",
    "engine": {"version": "0.5.0", "config_version": "0.2.0",
               "rules_version": "0.2.0"},
    "artifact": "data/artifacts/handwritten.json",
    "episode_key": {"test": "TG", "seed": 1, "level": 2},
    "entities": [{"entity_id": "wrench_1", "entity_type": "TOOL",
                  "name": "wrench", "aliases": []},
                 {"entity_id": "bay_a", "entity_type": "LOCATION",
                  "name": "bay A", "aliases": []}],
    "claims": [
        _claim("c1", "wrench_1", "LAST_SEEN_WITH", "sam", 10, 10, "OBSERVED"),
        _claim("c2", "sam", "ENTERED", "bay_a", 12, 12, "OBSERVED"),
        _claim("c3", "wrench_1", "CANDIDATE_LOCATION", "bay_a", 12, 12,
               "DERIVED",
               {"operator": "temporal_graph_traversal",
                "input_claims": ["c1", "c2"],
                "rule_ids": ["rule_carrier_location_v1"],
                "assumptions": ["the carrier kept the object"],
                "time_constraints": ["c2.event_time >= c1.event_time"]}),
    ],
    "rules": [{"rule_id": "rule_carrier_location_v1",
               "description": "An object last associated with a carrier may "
                              "be at the carrier's later location.",
               "status": "VALIDATED", "version": "1"}],
    "decisions": [
        {"step": 0, "action_type": "INSPECT_LOCATION", "target": "bay_a",
         "rationale": "the only candidate the evidence supports",
         "result": "SUCCESS", "new_claim_ids": [], "claims_before": 3,
         "hypotheses": [{"hypothesis_id": "h1",
                         "description": "the wrench is in bay A",
                         "candidate_location": "bay_a", "container": None,
                         "carrier": "sam", "status": "HYPOTHESIZED",
                         "belief": 0.81}]},
    ],
    "result": {"success": True, "found_at": "bay_a",
               "ground_truth_location": "bay_a", "correct": True,
               "steps_used": 1, "goal_status": "ACHIEVED"},
}

BROKEN_EPISODE = json.loads(json.dumps(GOOD_EPISODE))
BROKEN_EPISODE["episode_key"] = {"test": "TB", "seed": 2, "level": 2}
BROKEN_EPISODE["claims"][2]["proof"] = {
    "operator": "temporal_graph_traversal",
    "input_claims": ["c1", "c99"],                  # c99 is not on the ledger
    "rule_ids": ["rule_that_does_not_exist"],       # nor is this rule known
    "assumptions": [],
    "time_constraints": ["c1.event_time >= c2.event_time"],  # 10 >= 12, false
}


@pytest.fixture
def tiny_export(tmp_path: Path) -> Path:
    path = tmp_path / "handwritten.jsonl"
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(GOOD_EPISODE) + "\n")
        fh.write(json.dumps(BROKEN_EPISODE) + "\n")
    return path
