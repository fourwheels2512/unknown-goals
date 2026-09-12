"""Deterministic warehouse world: hidden ground truth the robot never sees.

The world advances by applying scripted GroundEvents. Object positions resolve
through carrier/container chains. The evaluator compares the robot's answers
against this truth; the robot mind itself only ever receives sensor claims."""

from __future__ import annotations

from pydantic import BaseModel, Field

from unknown_goals.core.enums import EntityType
from unknown_goals.models.records import Entity


class GroundEvent(BaseModel):
    t: int
    kind: str            # MOVE | PICKUP | DROP | LOAD | UNLOAD
    actor: str           # person/container/robot doing it
    obj: str | None = None
    dest: str | None = None


class WorldSpec(BaseModel):
    scenario_id: str
    level: int = 1
    seed: int = 0
    locations: dict[str, tuple[int, int]]            # location -> grid cell
    entities: list[Entity]
    initial_positions: dict[str, str]                # entity -> location
    can_carry: list[tuple[str, str]] = Field(default_factory=list)
    events: list[GroundEvent] = Field(default_factory=list)
    # observations that sensors missed live; revealed only by REPLAY_CAMERA,
    # each tagged with provenance["location"]
    hidden_observations: list = Field(default_factory=list)
    target: str = ""
    horizon: int = 60
    truth_note: str = ""     # which causal branch actually happened (evaluator only)


class World:
    def __init__(self, spec: WorldSpec) -> None:
        self.spec = spec
        self.t = 0
        self.positions: dict[str, str] = dict(spec.initial_positions)
        self.held_by: dict[str, str] = {}      # object -> person carrying it
        self.inside: dict[str, str] = {}       # object -> container
        self.truth_log: list[GroundEvent] = []
        self._pending = sorted(spec.events, key=lambda e: (e.t, e.actor, e.kind))

    # -- dynamics -----------------------------------------------------------
    def advance_to(self, t: int) -> list[GroundEvent]:
        applied: list[GroundEvent] = []
        while self._pending and self._pending[0].t <= t:
            ev = self._pending.pop(0)
            self._apply(ev)
            applied.append(ev)
        self.t = max(self.t, t)
        return applied

    def _apply(self, ev: GroundEvent) -> None:
        if ev.kind == "MOVE" and ev.dest:
            self.positions[ev.actor] = ev.dest
        elif ev.kind == "PICKUP" and ev.obj:
            self.held_by[ev.obj] = ev.actor
            self.inside.pop(ev.obj, None)
        elif ev.kind == "DROP" and ev.obj:
            self.held_by.pop(ev.obj, None)
            self.positions[ev.obj] = self.positions.get(ev.actor, "unknown")
        elif ev.kind == "LOAD" and ev.obj and ev.dest:   # dest = container
            self.held_by.pop(ev.obj, None)
            self.inside[ev.obj] = ev.dest
        elif ev.kind == "UNLOAD" and ev.obj:
            container = self.inside.pop(ev.obj, None)
            if container:
                self.positions[ev.obj] = self.positions.get(container, "unknown")
        self.truth_log.append(ev)

    # -- truth queries (evaluator only) -------------------------------------
    def true_location(self, entity: str) -> str:
        if entity in self.held_by:
            return self.true_location(self.held_by[entity])
        if entity in self.inside:
            return self.true_location(self.inside[entity])
        return self.positions.get(entity, "unknown")

    def true_container(self, entity: str) -> str | None:
        return self.inside.get(entity)

    # -- geometry ------------------------------------------------------------
    def distance(self, loc_a: str, loc_b: str) -> int:
        ax, ay = self.spec.locations[loc_a]
        bx, by = self.spec.locations[loc_b]
        return abs(ax - bx) + abs(ay - by)

    def entities_of_type(self, etype: EntityType) -> list[str]:
        return sorted(e.entity_id for e in self.spec.entities if e.entity_type == etype)

    def entities_of_type_at(self, location: str) -> list[str]:
        """Containers currently sitting at a location (visible on inspection)."""
        return sorted(
            e.entity_id for e in self.spec.entities
            if e.entity_type == EntityType.CONTAINER
            and self.true_location(e.entity_id) == location)

    def spec_hidden_observations(self) -> list:
        return self.spec.hidden_observations
