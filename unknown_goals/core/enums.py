"""Canonical enums: the closed vocabularies every module communicates in."""

from enum import StrEnum


class EpistemicStatus(StrEnum):
    """How a claim relates to reality. A hypothesis can NEVER become OBSERVED
    by scoring high; only a new observation carries OBSERVED status."""

    OBSERVED = "OBSERVED"            # directly sensed
    REPORTED = "REPORTED"            # supplied by a non-authoritative source
    DERIVED = "DERIVED"              # produced by deterministic inference, with proof
    HYPOTHESIZED = "HYPOTHESIZED"    # candidate explanation, not yet validated
    PREDICTED = "PREDICTED"          # expected future state
    SIMULATED = "SIMULATED"          # imagined rollout, never a real event
    VALIDATED_RULE = "VALIDATED_RULE"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    CONTRADICTED = "CONTRADICTED"


class EntityType(StrEnum):
    PERSON = "PERSON"
    ROBOT = "ROBOT"
    OBJECT = "OBJECT"
    TOOL = "TOOL"
    CONTAINER = "CONTAINER"
    LOCATION = "LOCATION"
    VEHICLE = "VEHICLE"
    SENSOR = "SENSOR"
    TASK = "TASK"


class Predicate(StrEnum):
    """Relation vocabulary. Argument types are declared in ONTOLOGY."""

    LOCATED_AT = "LOCATED_AT"
    NEAR = "NEAR"
    INSIDE = "INSIDE"
    CARRIED_BY = "CARRIED_BY"
    LAST_SEEN_WITH = "LAST_SEEN_WITH"
    MOVED_TO = "MOVED_TO"
    ENTERED = "ENTERED"
    EXITED = "EXITED"
    ABSENT_FROM = "ABSENT_FROM"
    CAN_CARRY = "CAN_CARRY"
    SAME_AS = "SAME_AS"
    CANDIDATE_LOCATION = "CANDIDATE_LOCATION"


class GoalType(StrEnum):
    LOCATE = "LOCATE"
    INSPECT = "INSPECT"
    DELIVER = "DELIVER"
    VERIFY = "VERIFY"
    DIAGNOSE = "DIAGNOSE"
    LEARN_PATTERN = "LEARN_PATTERN"


class GoalStatus(StrEnum):
    ACTIVE = "ACTIVE"
    IN_PROGRESS = "IN_PROGRESS"
    ACHIEVED = "ACHIEVED"
    FAILED_BUDGET = "FAILED_BUDGET"
    ABORTED = "ABORTED"


class ActionType(StrEnum):
    INSPECT_LOCATION = "INSPECT_LOCATION"
    SCAN_CONTAINER = "SCAN_CONTAINER"
    SCAN_OBJECT = "SCAN_OBJECT"
    REPLAY_CAMERA = "REPLAY_CAMERA"
    QUERY_MEMORY = "QUERY_MEMORY"
    MOVE_TO = "MOVE_TO"
    PICK_UP = "PICK_UP"
    PLACE = "PLACE"
    WAIT = "WAIT"


class DiagnosisKind(StrEnum):
    """Typed self-diagnosis vocabulary (the four-way taxonomy from the
    Recuris line of work, mapped to this engine's surfaces): what kind of
    thing broke, so repair can be scoped to the implicated machinery."""

    OVERCONFIDENT_BELIEF = "OVERCONFIDENT_BELIEF"   # bad state: beliefs high, world disagrees
    SEARCH_EXHAUSTION = "SEARCH_EXHAUSTION"         # missing skill: budgets die while still confused
    FRUITLESS_ACTIONS = "FRUITLESS_ACTIONS"         # bad checker: sensor-yield expectations wrong
    STALE_PATROL = "STALE_PATROL"                   # bad timing: staleness model mispredicts yield
    RULE_MISCALIBRATED = "RULE_MISCALIBRATED"       # bad checker: rule reliability vs reality


class StepKind(StrEnum):
    """Plan-step vocabulary (component #12: plans as data)."""

    FIND = "FIND"                # locate an entity via the reasoning engine
    COLLECT = "COLLECT"          # gather entities to a destination (verified)
    DO = "DO"                    # a domain operation with declared preconditions


class StepState(StrEnum):
    PENDING = "PENDING"
    DORMANT = "DORMANT"          # a fallback branch, inert until activated
    DONE = "DONE"
    FAILED = "FAILED"


class ActionResult(StrEnum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    INVALID = "INVALID"


class RuleStatus(StrEnum):
    CANDIDATE = "CANDIDATE"
    PROVISIONAL = "PROVISIONAL"
    VALIDATED = "VALIDATED"
    DEPRECATED = "DEPRECATED"
    REJECTED = "REJECTED"


class FailureCategory(StrEnum):
    """Benchmark failure taxonomy."""

    WRONG_LOCATION_RANKED_FIRST = "WRONG_LOCATION_RANKED_FIRST"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    NO_HYPOTHESIS_GENERATED = "NO_HYPOTHESIS_GENERATED"
    INVALID_ACTION = "INVALID_ACTION"
    IDENTITY_CONFUSION = "IDENTITY_CONFUSION"
    PROOF_INVALID = "PROOF_INVALID"


# Ontology: allowed (subject_type, predicate, object_type) triples.
# Invalid chains are rejected at ingestion.
ONTOLOGY: dict[Predicate, tuple[frozenset[EntityType], frozenset[EntityType]]] = {
    Predicate.LOCATED_AT: (
        frozenset({EntityType.PERSON, EntityType.ROBOT, EntityType.OBJECT, EntityType.TOOL,
                   EntityType.CONTAINER, EntityType.VEHICLE}),
        frozenset({EntityType.LOCATION}),
    ),
    Predicate.NEAR: (
        frozenset({EntityType.PERSON, EntityType.ROBOT, EntityType.OBJECT, EntityType.TOOL,
                   EntityType.CONTAINER, EntityType.VEHICLE}),
        frozenset({EntityType.PERSON, EntityType.ROBOT, EntityType.OBJECT, EntityType.TOOL,
                   EntityType.CONTAINER, EntityType.VEHICLE}),
    ),
    Predicate.INSIDE: (
        frozenset({EntityType.OBJECT, EntityType.TOOL}),
        frozenset({EntityType.CONTAINER, EntityType.VEHICLE, EntityType.LOCATION}),
    ),
    Predicate.CARRIED_BY: (
        frozenset({EntityType.OBJECT, EntityType.TOOL}),
        frozenset({EntityType.PERSON, EntityType.ROBOT, EntityType.VEHICLE, EntityType.CONTAINER}),
    ),
    Predicate.LAST_SEEN_WITH: (
        frozenset({EntityType.OBJECT, EntityType.TOOL}),
        frozenset({EntityType.PERSON, EntityType.ROBOT, EntityType.CONTAINER, EntityType.VEHICLE}),
    ),
    Predicate.MOVED_TO: (
        frozenset({EntityType.PERSON, EntityType.ROBOT, EntityType.CONTAINER, EntityType.VEHICLE}),
        frozenset({EntityType.LOCATION}),
    ),
    Predicate.ENTERED: (
        frozenset({EntityType.PERSON, EntityType.ROBOT, EntityType.CONTAINER, EntityType.VEHICLE}),
        frozenset({EntityType.LOCATION}),
    ),
    Predicate.EXITED: (
        frozenset({EntityType.PERSON, EntityType.ROBOT, EntityType.CONTAINER, EntityType.VEHICLE}),
        frozenset({EntityType.LOCATION}),
    ),
    Predicate.ABSENT_FROM: (
        frozenset({EntityType.PERSON, EntityType.OBJECT, EntityType.TOOL, EntityType.CONTAINER}),
        frozenset({EntityType.LOCATION, EntityType.CONTAINER}),
    ),
    Predicate.CAN_CARRY: (
        frozenset({EntityType.PERSON, EntityType.ROBOT, EntityType.CONTAINER, EntityType.VEHICLE}),
        frozenset({EntityType.OBJECT, EntityType.TOOL}),
    ),
    Predicate.SAME_AS: (
        frozenset(EntityType),
        frozenset(EntityType),
    ),
    Predicate.CANDIDATE_LOCATION: (
        # anything that can be LOCATED_AT somewhere can be a LOCATE target;
        # restricting candidates to OBJECT/TOOL made locating a cart crash at
        # the ontology boundary (temporal probe finding, 2026-08-31)
        frozenset({EntityType.PERSON, EntityType.ROBOT, EntityType.OBJECT, EntityType.TOOL,
                   EntityType.CONTAINER, EntityType.VEHICLE}),
        frozenset({EntityType.LOCATION, EntityType.CONTAINER}),
    ),
}
