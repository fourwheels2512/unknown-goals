"""Fixed scenarios, starting with the canonical wrench_12 case."""

from unknown_goals.core.enums import EntityType, EpistemicStatus, Predicate
from unknown_goals.models.records import Claim, Entity
from unknown_goals.simulation.world import GroundEvent, World, WorldSpec

STANDARD_LOCATIONS: dict[str, tuple[int, int]] = {
    "storage": (0, 0), "bay_1": (1, 0), "bay_2": (2, 0),
    "workbench_7": (0, 1), "bay_3": (1, 1), "bay_4": (2, 1),
}


def _entity(eid: str, etype: EntityType) -> Entity:
    return Entity(entity_id=eid, entity_type=etype, name=eid)


def wrench_scenario() -> tuple[WorldSpec, list[Claim]]:
    """The canonical case: wrench_12 → Iris → Bay 4 → cart_2 → Bay 2.
    Returns the hidden-truth spec plus the observable evidence stream."""
    entities = [
        _entity("wrench_12", EntityType.TOOL),
        _entity("wrench_18", EntityType.TOOL),
        _entity("iris", EntityType.PERSON),
        _entity("robot_1", EntityType.ROBOT),
        _entity("cart_2", EntityType.CONTAINER),
    ] + [_entity(loc, EntityType.LOCATION) for loc in STANDARD_LOCATIONS]

    spec = WorldSpec(
        scenario_id="wrench_canonical", level=3, seed=0,
        locations=STANDARD_LOCATIONS, entities=entities,
        initial_positions={
            "wrench_12": "workbench_7", "wrench_18": "storage",
            "iris": "workbench_7", "robot_1": "storage", "cart_2": "bay_4",
        },
        can_carry=[("cart_2", "wrench_12"), ("cart_2", "wrench_18"),
                   ("iris", "wrench_12"), ("iris", "wrench_18")],
        events=[
            GroundEvent(t=2, kind="PICKUP", actor="iris", obj="wrench_12"),
            GroundEvent(t=5, kind="MOVE", actor="iris", dest="bay_4"),
            GroundEvent(t=8, kind="LOAD", actor="iris", obj="wrench_12", dest="cart_2"),
            GroundEvent(t=9, kind="MOVE", actor="cart_2", dest="bay_2"),
        ],
        target="wrench_12", horizon=60,
    )

    def obs(cid: str, subj: str, pred: Predicate, obj: str, t: int,
            conf: float, source: str) -> Claim:
        return Claim(claim_id=cid, subject=subj, predicate=pred, obj=obj,
                     event_time_start=t, event_time_end=t, ingested_at=t + 1,
                     source_id=source, confidence=conf,
                     status=EpistemicStatus.OBSERVED,
                     provenance={"source_event": cid})

    evidence = [
        obs("c_anchor", "wrench_12", Predicate.LOCATED_AT, "workbench_7", 0, 0.93, "camera_3"),
        obs("c_near", "wrench_12", Predicate.NEAR, "iris", 2, 0.83, "camera_3"),
        obs("c_badge", "iris", Predicate.ENTERED, "bay_4", 5, 0.98, "badge_reader"),
        obs("c_absent", "wrench_12", Predicate.ABSENT_FROM, "workbench_7", 7, 0.92, "camera_3"),
        obs("c_can", "cart_2", Predicate.CAN_CARRY, "wrench_12", 0, 0.99, "registry"),
        obs("c_exit", "cart_2", Predicate.EXITED, "bay_4", 9, 0.95, "cart_tracker"),
        obs("c_dest", "cart_2", Predicate.MOVED_TO, "bay_2", 9, 0.95, "cart_tracker"),
    ]
    return spec, evidence


def blind_scenario() -> tuple[WorldSpec, list[Claim]]:
    """Gate 5 fixture: the wrench is missing and there is NO evidence at all."""
    spec, _ = wrench_scenario()
    spec = spec.model_copy(update={"scenario_id": "wrench_blind"})
    return spec, []


def build_world(spec: WorldSpec) -> World:
    world = World(spec)
    world.advance_to(10)   # scripted history has already happened
    return world
