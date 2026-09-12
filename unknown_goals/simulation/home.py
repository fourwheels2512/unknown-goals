"""The Coffee Ladder's home world: an unfamiliar house, not a warehouse.

Different topology, different entities, different movers (roommates, a
dishwasher, a tote bag) — a transfer test: the engine's reasoning must work
here with zero home-specific code, or the warehouse results were overfitting.

Each coffee item gets an INDEPENDENT fate sampled from realistic house
entropy: stayed put / roommate relocated it / sealed in the dishwasher /
riding in a tote bag that changed rooms. Evidence: stale sightings, partial
carrier chains, occasional missing absences — the usual honest noise.
"""

from __future__ import annotations

from unknown_goals.core.enums import EntityType, EpistemicStatus, Predicate
from unknown_goals.core.seeds import SeedManager
from unknown_goals.models.records import Claim, Entity
from unknown_goals.simulation.world import GroundEvent, WorldSpec

HOME_LOCATIONS: dict[str, tuple[int, int]] = {
    "kitchen": (0, 0), "pantry": (1, 0), "living_room": (2, 0),
    "hallway": (0, 1), "office": (1, 1), "bedroom": (2, 1),
}

COFFEE_ITEMS = ["mug_9", "grounds_jar", "filter_pack", "kettle_2"]
DISTRACTORS = ["keys_3", "book_7", "charger_1", "remote_4", "plant_6"]
ROOMMATES = ["sam", "ana", "leo"]


class _CF:
    def __init__(self, scenario_id: str) -> None:
        self.scenario_id = scenario_id
        self.n = 0

    def make(self, subj: str, pred: Predicate, obj: str, t: int, conf: float,
             source: str, **prov) -> Claim:
        self.n += 1
        cid = f"c_{self.scenario_id}_{self.n:03d}"
        return Claim(claim_id=cid, subject=subj, predicate=pred, obj=obj,
                     event_time_start=t, event_time_end=t, ingested_at=t + 1,
                     source_id=source, confidence=round(conf, 3),
                     status=EpistemicStatus.OBSERVED,
                     provenance={"source_event": cid, **prov})


def generate_home(seed: int) -> tuple[WorldSpec, list[Claim], list[str]]:
    """Returns (spec, observable evidence, coffee item targets)."""
    sm = SeedManager(seed)
    r_world = sm.stream("home_world")
    r_truth = sm.stream("home_truth")
    r_noise = sm.stream("home_noise")
    sid = f"home_{seed}"
    cf = _CF(sid)
    locations = sorted(HOME_LOCATIONS)
    people = sorted(r_world.sample(ROOMMATES, r_world.randint(2, 3)))

    entities = (
        [Entity(entity_id=i, entity_type=EntityType.TOOL, name=i)
         for i in COFFEE_ITEMS + DISTRACTORS]
        + [Entity(entity_id="coffee_machine", entity_type=EntityType.TOOL,
                  name="coffee_machine")]
        + [Entity(entity_id=p, entity_type=EntityType.PERSON, name=p) for p in people]
        + [Entity(entity_id="dishwasher", entity_type=EntityType.CONTAINER,
                  name="dishwasher"),
           Entity(entity_id="tote_bag", entity_type=EntityType.CONTAINER,
                  name="tote_bag"),
           Entity(entity_id="robot_1", entity_type=EntityType.ROBOT, name="robot_1")]
        + [Entity(entity_id=loc, entity_type=EntityType.LOCATION, name=loc)
           for loc in locations])

    positions: dict[str, str] = {"coffee_machine": "kitchen",
                                 "dishwasher": "kitchen",
                                 "robot_1": "hallway"}
    home_spots = {"mug_9": "kitchen", "grounds_jar": "pantry",
                  "filter_pack": "pantry", "kettle_2": "kitchen"}
    for item in COFFEE_ITEMS:
        positions[item] = home_spots[item]
    for dtr in DISTRACTORS:
        positions[dtr] = r_world.choice(locations)
    for p in people:
        positions[p] = r_world.choice(locations)
    positions["tote_bag"] = r_world.choice(["hallway", "living_room", "bedroom"])

    events: list[GroundEvent] = []
    evidence: list[Claim] = []

    def conf(lo, hi):
        return r_noise.uniform(lo, hi)

    # household knowledge: what can carry what
    for carrier in ["dishwasher", "tote_bag"] + people:
        for item in COFFEE_ITEMS:
            if carrier == "dishwasher" and item in ("grounds_jar", "filter_pack"):
                continue    # nobody dishwashes coffee grounds
            evidence.append(cf.make(carrier, Predicate.CAN_CARRY, item, 0,
                                    0.99, "house_knowledge"))

    # the coffee machine is where coffee machines live
    evidence.append(cf.make("coffee_machine", Predicate.LOCATED_AT, "kitchen",
                            0, conf(0.9, 0.98), "house_camera"))

    tote_moved = False
    tote_now = ""
    t_clock = 1
    for item in COFFEE_ITEMS:
        origin = positions[item]
        evidence.append(cf.make(item, Predicate.LOCATED_AT, origin, 0,
                                conf(0.8, 0.95), "house_camera"))
        fate = r_truth.random()
        t0 = t_clock
        t_clock += 3
        if fate < 0.42:
            continue                                  # stayed put
        if fate < 0.72:
            # a roommate relocated it
            mover = r_world.choice(people)
            dest = r_world.choice([loc for loc in locations if loc != origin])
            events += [GroundEvent(t=t0, kind="PICKUP", actor=mover, obj=item),
                       GroundEvent(t=t0 + 1, kind="MOVE", actor=mover, dest=dest),
                       GroundEvent(t=t0 + 2, kind="DROP", actor=mover, obj=item)]
            evidence.append(cf.make(item, Predicate.NEAR, mover, t0,
                                    conf(0.7, 0.9), "house_camera"))
            evidence.append(cf.make(mover, Predicate.ENTERED, dest, t0 + 1,
                                    conf(0.85, 0.97), "door_sensor"))
            if r_noise.random() < 0.75:
                evidence.append(cf.make(item, Predicate.ABSENT_FROM, origin,
                                        t0 + 2, conf(0.8, 0.94), "house_camera"))
        elif fate < 0.88 and item in ("mug_9", "kettle_2"):
            # sealed in the dishwasher (invisible to inspection; needs a scan)
            loader = r_world.choice(people)
            events += [GroundEvent(t=t0, kind="PICKUP", actor=loader, obj=item),
                       GroundEvent(t=t0 + 1, kind="MOVE", actor=loader, dest="kitchen"),
                       GroundEvent(t=t0 + 2, kind="LOAD", actor=loader, obj=item,
                                   dest="dishwasher")]
            evidence.append(cf.make(item, Predicate.NEAR, loader, t0,
                                    conf(0.65, 0.88), "house_camera"))
            evidence.append(cf.make(loader, Predicate.ENTERED, "kitchen", t0 + 1,
                                    conf(0.85, 0.97), "door_sensor"))
            if r_noise.random() < 0.7:
                evidence.append(cf.make(item, Predicate.ABSENT_FROM, origin,
                                        t0 + 2, conf(0.8, 0.94), "house_camera"))
        else:
            # left in the tote bag, which later changes rooms
            carrier = r_world.choice(people)
            tote_from = tote_now if tote_moved else positions["tote_bag"]
            tote_to = r_world.choice([loc for loc in locations if loc != tote_from])
            events += [GroundEvent(t=t0, kind="PICKUP", actor=carrier, obj=item),
                       GroundEvent(t=t0 + 1, kind="MOVE", actor=carrier, dest=tote_from),
                       GroundEvent(t=t0 + 2, kind="LOAD", actor=carrier, obj=item,
                                   dest="tote_bag")]
            evidence.append(cf.make(item, Predicate.NEAR, carrier, t0,
                                    conf(0.65, 0.9), "house_camera"))
            evidence.append(cf.make(carrier, Predicate.ENTERED, tote_from, t0 + 1,
                                    conf(0.85, 0.97), "door_sensor"))
            if r_noise.random() < 0.7:
                evidence.append(cf.make(item, Predicate.ABSENT_FROM, origin,
                                        t0 + 2, conf(0.8, 0.94), "house_camera"))
            if not tote_moved:
                tmove = t_clock
                events += [GroundEvent(t=tmove, kind="MOVE", actor="tote_bag",
                                       dest=tote_to)]
                evidence.append(cf.make("tote_bag", Predicate.EXITED, tote_from,
                                        tmove, conf(0.85, 0.96), "door_sensor"))
                evidence.append(cf.make("tote_bag", Predicate.MOVED_TO, tote_to,
                                        tmove, conf(0.85, 0.96), "door_sensor"))
                tote_moved = True
                tote_now = tote_to
                t_clock += 2

    # background house noise: roommates and distractors move around
    for _ in range(r_world.randint(3, 5)):
        who = r_world.choice(people)
        evidence.append(cf.make(who, Predicate.ENTERED,
                                r_world.choice(locations),
                                r_world.randint(1, t_clock), conf(0.8, 0.97),
                                "door_sensor"))
    for dtr in r_world.sample(DISTRACTORS, 3):
        evidence.append(cf.make(dtr, Predicate.LOCATED_AT, positions[dtr],
                                r_world.randint(0, t_clock), conf(0.7, 0.95),
                                "house_camera"))

    spec = WorldSpec(
        scenario_id=sid, level=2, seed=seed, locations=HOME_LOCATIONS,
        entities=entities, initial_positions=positions,
        can_carry=[(c, i) for c in ["dishwasher", "tote_bag"] + people
                   for i in COFFEE_ITEMS],
        events=sorted(events, key=lambda e: (e.t, e.actor, e.kind)),
        target=COFFEE_ITEMS[0], horizon=60,
        truth_note="home")
    evidence.sort(key=lambda c: (c.ingested_at, c.claim_id))
    return spec, evidence, list(COFFEE_ITEMS)
