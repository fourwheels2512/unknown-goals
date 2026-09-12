"""The Woz Test house: a procedurally generated, genuinely unfamiliar home.

The engine receives NOTHING up front — no map, no entity list, no evidence.
Items sit wherever the household left them (no event trail, no witnesses).
All knowledge must arrive through the robot's own passive perception: standing
in a room reveals its visible contents and its doorways, nothing more. Items
inside containers are invisible until the container is scanned.

Levels:
  W1  every coffee item is in the starting room (binding + collection + brew)
  W2  items scattered across the house (demands exploration)
  W3  + a decoy second mug (ambiguity) and one item sealed in a cabinet
"""

from __future__ import annotations

from unknown_goals.core.enums import EntityType
from unknown_goals.core.seeds import SeedManager
from unknown_goals.models.records import Entity
from unknown_goals.simulation.world import World, WorldSpec

ROOM_POOL = ["kitchen", "pantry", "den", "living_room", "bedroom", "office",
             "hallway", "sunroom", "garage", "laundry"]

# recipe classes -> the instance-id prefix a vision system would report
RECIPE_CLASSES = ["mug", "grounds", "filter", "kettle", "machine"]
INSTANCE_STYLES = {
    "mug": ["mug_red", "mug_blue", "mug_green"],
    "grounds": ["grounds_tin", "grounds_bag"],
    "filter": ["filter_box", "filter_pack"],
    "kettle": ["kettle_steel", "kettle_glass"],
    "machine": ["machine_drip", "machine_press"],
}
CLUTTER = ["lamp_1", "book_2", "vase_3", "cable_4", "shoe_5", "plant_6"]


def generate_wozhome(seed: int, level: int) -> tuple[WorldSpec, str, dict]:
    """Returns (full-truth spec, starting room, meta). NO evidence is emitted:
    the robot must earn every claim through its own sensors."""
    assert level in (1, 2, 3)
    sm = SeedManager(seed)
    rw = sm.stream(f"woz_world_{level}")

    n_rooms = rw.randint(5, 7)
    rooms = sorted(rw.sample(ROOM_POOL, n_rooms))
    # a real house is CONNECTED: resample cell layouts (same seeded stream)
    # until every room is reachable through doorways
    all_cells = [(x, y) for x in range(4) for y in range(2)]
    while True:
        cells = rw.sample(all_cells, n_rooms)
        cellset = set(cells)
        seen = {cells[0]}
        frontier = [cells[0]]
        while frontier:
            cx, cy = frontier.pop()
            for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                if (nx, ny) in cellset and (nx, ny) not in seen:
                    seen.add((nx, ny))
                    frontier.append((nx, ny))
        if len(seen) == n_rooms:
            break
    locations = dict(zip(rooms, cells, strict=False))
    start = rw.choice(rooms)

    items: dict[str, str] = {}          # instance id -> class
    for cls in RECIPE_CLASSES:
        inst = rw.choice(INSTANCE_STYLES[cls])
        items[inst] = cls
    decoy = None
    if level >= 3:
        used_mug = next(i for i, c in items.items() if c == "mug")
        decoy = rw.choice([m for m in INSTANCE_STYLES["mug"] if m != used_mug])
        items[decoy] = "mug"

    positions: dict[str, str] = {"robot_1": start}
    for inst in items:
        positions[inst] = start if level == 1 else rw.choice(rooms)
    for junk in rw.sample(CLUTTER, 4):
        positions[junk] = rw.choice(rooms)

    entities = (
        [Entity(entity_id=i, entity_type=EntityType.TOOL, name=i) for i in items]
        + [Entity(entity_id=j, entity_type=EntityType.OBJECT, name=j)
           for j in CLUTTER if j in positions]
        + [Entity(entity_id="robot_1", entity_type=EntityType.ROBOT, name="robot_1")]
        + [Entity(entity_id=r, entity_type=EntityType.LOCATION, name=r)
           for r in rooms])

    sealed: dict[str, str] = {}
    if level >= 3:
        cab_room = rw.choice(rooms)
        entities.append(Entity(entity_id="cabinet_1",
                               entity_type=EntityType.CONTAINER, name="cabinet_1"))
        positions["cabinet_1"] = cab_room
        sealable = [i for i, c in items.items()
                    if c in ("grounds", "filter") ]
        hidden = rw.choice(sealable)
        positions[hidden] = cab_room
        sealed[hidden] = "cabinet_1"

    spec = WorldSpec(
        scenario_id=f"woz_l{level}_{seed}", level=level, seed=seed,
        locations=locations, entities=entities, initial_positions=positions,
        events=[], target=next(i for i, c in items.items() if c == "mug"),
        horizon=200, truth_note=f"woz_w{level}")
    meta = {"items": items, "start": start, "decoy": decoy, "sealed": sealed,
            "brew_room": positions[next(i for i, c in items.items()
                                        if c == "machine")]}
    return spec, start, meta


def build_truth_world(spec: WorldSpec, sealed: dict[str, str]) -> World:
    world = World(spec)
    for item, container in sealed.items():
        world.inside[item] = container
    return world


def adjacent_rooms(spec: WorldSpec, room: str) -> list[str]:
    x, y = spec.locations[room]
    out = []
    for other, (ox, oy) in spec.locations.items():
        if abs(ox - x) + abs(oy - y) == 1:
            out.append(other)
    return sorted(out)


def visible_in_room(world: World, room: str) -> tuple[list[str], list[str]]:
    """(visible items, containers present). Container CONTENTS stay hidden."""
    items, containers = [], []
    for e in world.spec.entities:
        if e.entity_type == EntityType.ROBOT or e.entity_type == EntityType.LOCATION:
            continue
        if world.true_container(e.entity_id) is not None:
            continue                      # sealed away, invisible
        if world.true_location(e.entity_id) != room:
            continue
        if e.entity_type == EntityType.CONTAINER:
            containers.append(e.entity_id)
        else:
            items.append(e.entity_id)
    return sorted(items), sorted(containers)
