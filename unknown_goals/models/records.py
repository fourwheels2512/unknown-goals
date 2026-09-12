"""Canonical typed records. Every subsystem communicates through these,
never through free-form text."""

from __future__ import annotations

import itertools
import uuid
from contextlib import contextmanager

from pydantic import BaseModel, Field, field_validator

from unknown_goals.core.enums import (
    ONTOLOGY,
    ActionResult,
    ActionType,
    EntityType,
    EpistemicStatus,
    GoalStatus,
    GoalType,
    Predicate,
    RuleStatus,
)

# Timestamps are persisted as SQLite INTEGER (signed 64-bit). A record whose
# clocks fall outside that range cannot be stored, so it is refused at the
# typed boundary with a clean validation error instead of crashing the
# storage layer with an opaque OverflowError.
INT64_MIN = -(2**63)
INT64_MAX = 2**63 - 1

_DETERMINISTIC_SCOPES: list[tuple[str, itertools.count]] = []


def new_id(prefix: str) -> str:
    if _DETERMINISTIC_SCOPES:
        scope, counter = _DETERMINISTIC_SCOPES[-1]
        return f"{prefix}_{scope}_{next(counter):05d}"
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@contextmanager
def deterministic_ids(scope: str):
    """Inside this context, generated ids are a deterministic sequence —
    two runs of the same scenario produce byte-identical records."""
    _DETERMINISTIC_SCOPES.append((scope, itertools.count(1)))
    try:
        yield
    finally:
        _DETERMINISTIC_SCOPES.pop()


class Entity(BaseModel):
    entity_id: str
    entity_type: EntityType
    name: str
    aliases: list[str] = Field(default_factory=list)


class Proof(BaseModel):
    """A machine-checkable dependency record — the proof IS the reasoning."""

    operator: str                                    # e.g. temporal_graph_traversal
    input_claims: list[str] = Field(default_factory=list)
    rule_ids: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    time_constraints: list[str] = Field(default_factory=list)


class Claim(BaseModel):
    """One atomic fact. Append-only: a Claim is never mutated after ingestion;
    status changes are recorded as separate StatusEvents in the ledger."""

    claim_id: str = Field(default_factory=lambda: new_id("c"))
    subject: str
    predicate: Predicate
    obj: str                      # object entity id, or value for scalar claims
    event_time_start: int = Field(ge=INT64_MIN, le=INT64_MAX)  # world minutes since episode start
    event_time_end: int = Field(ge=INT64_MIN, le=INT64_MAX)
    ingested_at: int = Field(ge=INT64_MIN, le=INT64_MAX)       # when the SYSTEM learned it (two-clock rule)
    source_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    status: EpistemicStatus
    proof: Proof | None = None    # required for DERIVED claims
    provenance: dict = Field(default_factory=dict)

    @field_validator("event_time_end")
    @classmethod
    def end_after_start(cls, v: int, info) -> int:
        start = info.data.get("event_time_start")
        if start is not None and v < start:
            raise ValueError("event_time_end must be >= event_time_start")
        return v

    def validate_against_ontology(self, subject_type: EntityType, object_type: EntityType) -> bool:
        subj_ok, obj_ok = ONTOLOGY[self.predicate]
        return subject_type in subj_ok and object_type in obj_ok


class Hypothesis(BaseModel):
    hypothesis_id: str = Field(default_factory=lambda: new_id("h"))
    description: str
    target_entity: str
    candidate_location: str       # location or container entity id
    container: str | None = None  # set when a container transport chain applies
    carrier: str | None = None    # set when a mobile carrier chain applies
    status: EpistemicStatus = EpistemicStatus.HYPOTHESIZED
    supporting_claims: list[str] = Field(default_factory=list)
    contradicting_claims: list[str] = Field(default_factory=list)
    proof: Proof | None = None
    belief: float = 0.0


class Goal(BaseModel):
    goal_id: str = Field(default_factory=lambda: new_id("g"))
    goal_type: GoalType
    target_entity: str
    status: GoalStatus = GoalStatus.ACTIVE
    max_actions: int = 8
    missing_variables: list[str] = Field(default_factory=list)


class ActionSpec(BaseModel):
    action_id: str = Field(default_factory=lambda: new_id("a"))
    action_type: ActionType
    target: str
    expected_information_gain: float = 0.0
    expected_success_prob: float = 0.0
    cost: float = 0.0
    risk: float = 0.0
    value: float = 0.0            # planner's combined score (EIG + success) / cost
    rationale: str = ""


class Outcome(BaseModel):
    action_id: str
    result: ActionResult
    new_claim_ids: list[str] = Field(default_factory=list)
    entropy_before: float = 0.0
    entropy_after: float = 0.0
    reward: float = 0.0


class Rule(BaseModel):
    """A reasoning or strategy rule with measured reliability and lifecycle."""

    rule_id: str
    description: str
    reliability: float = Field(ge=0.0, le=1.0)
    status: RuleStatus = RuleStatus.VALIDATED
    support_count: int = 0
    precision: float = 0.0
    recall: float = 0.0
    scope: dict = Field(default_factory=dict)
    version: str = "1"


class EpisodeRecord(BaseModel):
    episode_id: str = Field(default_factory=lambda: new_id("ep"))
    scenario_id: str
    seed: int
    level: int
    goal: Goal
    actions: list[ActionSpec] = Field(default_factory=list)
    outcomes: list[Outcome] = Field(default_factory=list)
    hypotheses_final: list[Hypothesis] = Field(default_factory=list)
    success: bool = False
    found_at: str | None = None
    ground_truth_location: str | None = None
    total_reward: float = 0.0
    steps_used: int = 0
    policy_version: str = "baseline"
