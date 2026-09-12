"""Seeded scenario generator: training ground, benchmark factory, curriculum.

Emits two strictly separated layers per scenario:
  - hidden truth  (WorldSpec events — evaluator only)
  - observable evidence (noisy Claims — all the robot mind ever sees)

Difficulty levels:
  L1 direct observation, 1 hop            L4 + distractors/decoys/stale claims
  L2 person carrier bridge, 2 hops        L5 + contradictions, occlusion,
  L3 person + cart chain, 3-4 hops             wrong-branch recovery
  L6 GASLIGHT: an adversary deliberately plants false evidence — confident fake
     sightings, staged twin-object decoys, contradictory reports — while the
     true causal chain hides in normal noise. Tests whether provenance,
     contradiction detection, and verify-then-debunk survive deception.
"""

from __future__ import annotations

from unknown_goals.core.enums import EntityType, EpistemicStatus, Predicate
from unknown_goals.core.seeds import SeedManager
from unknown_goals.models.records import Claim, Entity
from unknown_goals.simulation.scenarios import STANDARD_LOCATIONS
from unknown_goals.simulation.world import GroundEvent, WorldSpec

PEOPLE_POOL = ["iris", "marco", "dana", "felix"]
CARTS = ["cart_1", "cart_2"]
TOOL_POOL = ["wrench_12", "wrench_18", "hammer_3", "hammer_9", "driver_5",
             "spanner_7", "drill_2", "saw_4", "clamp_6", "torch_8",
             "plier_3", "chisel_5", "level_6", "tape_4", "file_8"]


class _ClaimFactory:
    def __init__(self, scenario_id: str) -> None:
        self.scenario_id = scenario_id
        self.n = 0

    def make(self, subj: str, pred: Predicate, obj: str, t: int, conf: float,
             source: str, ingest_delay: int = 1, **prov) -> Claim:
        self.n += 1
        cid = f"c_{self.scenario_id}_{self.n:03d}"
        return Claim(claim_id=cid, subject=subj, predicate=pred, obj=obj,
                     event_time_start=t, event_time_end=t,
                     ingested_at=t + ingest_delay, source_id=source,
                     confidence=round(conf, 3), status=EpistemicStatus.OBSERVED,
                     provenance={"source_event": cid, **prov})


def generate(seed: int, level: int) -> tuple[WorldSpec, list[Claim]]:
    # external input (CLI, adapters) reaches here; validate with a real
    # error rather than an assert, which `python -O` would strip entirely.
    if not 1 <= level <= 6:
        raise ValueError(f"level must be an integer 1..6, got {level!r}")
    sm = SeedManager(seed)
    r_world = sm.stream(f"world_l{level}")
    r_truth = sm.stream(f"truth_l{level}")
    r_noise = sm.stream(f"noise_l{level}")
    scenario_id = f"wh_l{level}_{seed}"
    cf = _ClaimFactory(scenario_id)

    locations = sorted(STANDARD_LOCATIONS)
    people = sorted(r_world.sample(PEOPLE_POOL, r_world.randint(2, 4)))
    n_tools = r_world.randint(8, min(15, len(TOOL_POOL)))
    tools = sorted(r_world.sample(TOOL_POOL, n_tools))
    target = r_world.choice(tools)

    entities = (
        [Entity(entity_id=t, entity_type=EntityType.TOOL, name=t) for t in tools]
        + [Entity(entity_id=p, entity_type=EntityType.PERSON, name=p) for p in people]
        + [Entity(entity_id=c, entity_type=EntityType.CONTAINER, name=c) for c in CARTS]
        + [Entity(entity_id="robot_1", entity_type=EntityType.ROBOT, name="robot_1")]
        + [Entity(entity_id=loc, entity_type=EntityType.LOCATION, name=loc)
           for loc in locations])

    positions: dict[str, str] = {t: r_world.choice(locations) for t in tools}
    for p in people:
        positions[p] = r_world.choice(locations)
    for c in CARTS:
        positions[c] = r_world.choice(locations)
    positions["robot_1"] = "storage"

    loc0 = positions[target]
    carrier = r_world.choice(people)
    positions[carrier] = loc0
    cart = r_world.choice(CARTS)
    dest_b = r_world.choice([loc for loc in locations if loc != loc0])
    dest_c = r_world.choice([loc for loc in locations if loc not in (loc0, dest_b)])

    events: list[GroundEvent] = []
    evidence: list[Claim] = []
    hidden: list[Claim] = []
    spec_kwargs: dict = {}

    def conf(lo: float, hi: float) -> float:
        return r_noise.uniform(lo, hi)

    # registry knowledge: carts can carry every tool (cheap, always available)
    for c in CARTS:
        for t in tools:
            evidence.append(cf.make(c, Predicate.CAN_CARRY, t, 0, 0.99, "registry"))

    # anchor observation of the target
    anchor_conf = conf(0.85, 0.97)
    evidence.append(cf.make(target, Predicate.LOCATED_AT, loc0, 0, anchor_conf, "camera"))

    if level == 1:
        truth_note = "stay"
    else:
        # a person becomes associated with the target and leaves
        events.append(GroundEvent(t=2, kind="PICKUP", actor=carrier, obj=target))
        events.append(GroundEvent(t=5, kind="MOVE", actor=carrier, dest=dest_b))
        near_conf = conf(0.75, 0.92)
        evidence.append(cf.make(target, Predicate.NEAR, carrier, 2, near_conf, "camera"))
        evidence.append(cf.make(carrier, Predicate.ENTERED, dest_b, 5,
                                conf(0.93, 0.99), "badge_reader"))
        if r_noise.random() < 0.85:  # absence sometimes goes unobserved
            evidence.append(cf.make(target, Predicate.ABSENT_FROM, loc0, 7,
                                    conf(0.85, 0.96), "camera"))

        if level == 2:
            events.append(GroundEvent(t=7, kind="DROP", actor=carrier, obj=target))
            truth_note = "carrier"
        else:
            # cart chain: does the cart actually take it?
            positions[cart] = dest_b
            branch = r_truth.random()
            if branch < 0.72:
                events.append(GroundEvent(t=8, kind="LOAD", actor=carrier,
                                          obj=target, dest=cart))
                events.append(GroundEvent(t=9, kind="MOVE", actor=cart, dest=dest_c))
                truth_note = "transport"
            elif branch < 0.92:
                # person keeps it; the cart leaves anyway (empty — misleading)
                events.append(GroundEvent(t=9, kind="MOVE", actor=cart, dest=dest_c))
                truth_note = "carrier_kept"
            else:
                # object never left: the absence report was wrong (occlusion)
                events = [e for e in events if e.obj != target and e.kind != "PICKUP"]
                events.append(GroundEvent(t=9, kind="MOVE", actor=cart, dest=dest_c))
                truth_note = "occluded"
                hidden.append(cf.make(target, Predicate.LOCATED_AT, loc0, 8,
                                      0.88, "camera_replay", location=loc0))
            evidence.append(cf.make(cart, Predicate.EXITED, dest_b, 9,
                                    conf(0.88, 0.98), "cart_tracker"))
            evidence.append(cf.make(cart, Predicate.MOVED_TO, dest_c, 9,
                                    conf(0.88, 0.98), "cart_tracker"))

    if level >= 4:
        # distractors: unrelated people and tools move around and get observed
        for _ in range(r_world.randint(2, 4)):
            other = r_world.choice([p for p in people if p != carrier])
            where = r_world.choice(locations)
            evidence.append(cf.make(other, Predicate.ENTERED, where,
                                    r_world.randint(1, 9), conf(0.80, 0.98),
                                    "badge_reader"))
        for _ in range(r_world.randint(2, 4)):
            tool = r_world.choice([t for t in tools if t != target])
            evidence.append(cf.make(tool, Predicate.LOCATED_AT, positions[tool],
                                    r_world.randint(1, 8), conf(0.70, 0.95), "camera"))
        if r_noise.random() < 0.30 and len(people) > 1:
            # decoy association: someone else was near the target too
            decoy = r_world.choice([p for p in people if p != carrier])
            evidence.append(cf.make(target, Predicate.NEAR, decoy, 1,
                                    conf(0.55, 0.75), "camera"))

    if level == 5 and r_noise.random() < 0.5:
        # a plainly false sighting that contradicts better evidence
        wrong = r_world.choice([loc for loc in locations if loc != loc0])
        evidence.append(cf.make(target, Predicate.LOCATED_AT, wrong,
                                r_world.randint(8, 10), conf(0.45, 0.62),
                                "camera_flaky"))

    if level >= 6:
        # THE GASLIGHTER: a deliberate misinformation campaign. The liar knows
        # where the object really ended up and steers AWAY from it.
        true_final = dest_c if truth_note == "transport" else (
            dest_b if truth_note in ("carrier", "carrier_kept") else loc0)
        adversary = r_world.choice([p for p in people if p != carrier])
        wrong = r_world.choice([loc for loc in locations
                                if loc not in (loc0, true_final)])
        wrong2 = r_world.choice([loc for loc in locations
                                 if loc not in (loc0, true_final, wrong)])
        # 1) a CONFIDENT fake sighting, late enough to look fresh
        evidence.append(cf.make(target, Predicate.LOCATED_AT, wrong,
                                r_world.randint(9, 10), conf(0.70, 0.85),
                                "anonymous_tip", planted=True))
        # 2) a contradictory second report — liars overreach; the same object
        #    "seen" in two places close enough in time to conflict
        if r_noise.random() < 0.6:
            evidence.append(cf.make(target, Predicate.LOCATED_AT, wrong2,
                                    r_world.randint(9, 10), conf(0.55, 0.70),
                                    "anonymous_tip", planted=True))
        # 3) a staged decoy: a same-type twin moved near the fake location and
        #    "associated" with an innocent bystander
        twins = [t for t in tools if t != target
                 and t.split("_")[0] == target.split("_")[0]]
        if twins:
            twin = r_world.choice(twins)
            evidence.append(cf.make(twin, Predicate.LOCATED_AT, wrong,
                                    r_world.randint(8, 9), conf(0.80, 0.93),
                                    "camera", planted=True))
            evidence.append(cf.make(target, Predicate.NEAR, adversary,
                                    r_world.randint(1, 3), conf(0.50, 0.68),
                                    "anonymous_tip", planted=True))
        # 4) sometimes, a false absence report at the object's REAL location
        if r_noise.random() < 0.35:
            true_area = dest_c if truth_note == "transport" else (
                dest_b if truth_note in ("carrier", "carrier_kept") else loc0)
            evidence.append(cf.make(target, Predicate.ABSENT_FROM, true_area,
                                    r_world.randint(9, 10), conf(0.55, 0.72),
                                    "anonymous_tip", planted=True))

    spec = WorldSpec(
        scenario_id=scenario_id, level=level, seed=seed,
        locations=STANDARD_LOCATIONS, entities=entities,
        initial_positions=positions,
        can_carry=[(c, t) for c in CARTS for t in tools],
        events=sorted(events, key=lambda e: (e.t, e.actor, e.kind)),
        hidden_observations=hidden, target=target, horizon=60,
        truth_note=truth_note, **spec_kwargs)
    evidence.sort(key=lambda c: (c.ingested_at, c.claim_id))
    return spec, evidence
