"""Action executor: performs approved actions against the simulated world and
reports what ACTUALLY happened. Success is declared only after outcome sensing
confirms the postcondition — never because the action was attempted."""

from __future__ import annotations

from unknown_goals.core.config import EngineConfig
from unknown_goals.core.enums import ActionResult, ActionType, EpistemicStatus, Predicate
from unknown_goals.models.records import ActionSpec, Claim
from unknown_goals.simulation.world import World
from unknown_goals.storage.ledger import Ledger


class ExecutionReport:
    def __init__(self) -> None:
        self.result: ActionResult = ActionResult.SUCCESS
        self.new_claims: list[Claim] = []
        self.time_spent: int = 1
        self.robot_location: str | None = None


class Executor:
    def __init__(self, world: World, ledger: Ledger, config: EngineConfig,
                 robot_id: str = "robot_1") -> None:
        self.world = world
        self.ledger = ledger
        self.config = config
        self.robot_id = robot_id
        self.robot_location = world.positions.get(robot_id, "storage")

    def _observe(self, report: ExecutionReport, subj: str, pred: Predicate,
                 obj: str, t: int, conf: float, source: str) -> None:
        # confidence is bounded by definition; a sensor rate drawn from a
        # corrupt/tampered config (e.g. scan_tp_rate > 1) is clamped here so
        # the observation degrades gracefully instead of crashing Claim()
        conf = min(max(conf, 0.0), 1.0)
        claim = Claim(subject=subj, predicate=pred, obj=obj,
                      event_time_start=t, event_time_end=t, ingested_at=t,
                      source_id=source, confidence=conf,
                      status=EpistemicStatus.OBSERVED,
                      provenance={"via_action": True, "source_event": f"act_{source}_{t}_{subj}_{obj}"})
        self.ledger.append_claim(claim)
        report.new_claims.append(claim)

    def execute(self, action: ActionSpec, target_entity: str, now: int) -> ExecutionReport:
        report = ExecutionReport()
        cfg = self.config.planner
        kind = action.action_type

        if kind in (ActionType.INSPECT_LOCATION, ActionType.MOVE_TO):
            if action.target not in self.world.spec.locations:
                report.result = ActionResult.INVALID
                return report
            travel = self.world.distance(self.robot_location, action.target)
            report.time_spent = 1 + travel
            self.robot_location = action.target
            self.world.positions[self.robot_id] = action.target
            # postcondition: pose verified against world truth
            if self.world.positions[self.robot_id] != action.target:
                report.result = ActionResult.FAILED
                return report
            report.robot_location = self.robot_location
            if kind == ActionType.MOVE_TO:
                return report
            t = now + report.time_spent
            true_loc = self.world.true_location(target_entity)
            in_container = self.world.true_container(target_entity)
            if true_loc == action.target and in_container is None:
                self._observe(report, target_entity, Predicate.LOCATED_AT,
                              action.target, t, cfg.inspect_tp_rate, "robot_eyes")
            else:
                self._observe(report, target_entity, Predicate.ABSENT_FROM,
                              action.target, t, 0.95, "robot_eyes")
            # containers present are visible even when their contents are not
            for container in self.world.entities_of_type_at(action.target):
                self._observe(report, container, Predicate.LOCATED_AT,
                              action.target, t, 0.96, "robot_eyes")
            return report

        if kind == ActionType.SCAN_CONTAINER:
            container = action.target
            if self.ledger.get_entity(container) is None:
                report.result = ActionResult.INVALID
                return report
            container_loc = self.world.true_location(container)
            travel = self.world.distance(self.robot_location, container_loc)
            report.time_spent = 1 + travel
            self.robot_location = container_loc
            self.world.positions[self.robot_id] = container_loc
            report.robot_location = self.robot_location
            t = now + report.time_spent
            # a scan reports EVERYTHING inside — an RFID reader sees every tag,
            # not just the one you hoped for; unknown contents get registered
            contents = sorted(obj for obj, box in self.world.inside.items()
                              if box == container)
            for obj in contents:
                if self.ledger.get_entity(obj) is None:
                    from unknown_goals.core.enums import EntityType
                    from unknown_goals.models.records import Entity
                    self.ledger.add_entity(Entity(
                        entity_id=obj, entity_type=EntityType.TOOL, name=obj))
                self._observe(report, obj, Predicate.INSIDE,
                              container, t, cfg.scan_tp_rate, "rfid_scanner")
                self._observe(report, obj, Predicate.LOCATED_AT,
                              container_loc, t, cfg.scan_tp_rate, "rfid_scanner")
            if target_entity not in contents:
                self._observe(report, target_entity, Predicate.ABSENT_FROM,
                              container, t, cfg.scan_tp_rate, "rfid_scanner")
            return report

        if kind == ActionType.REPLAY_CAMERA:
            t = now + 1
            revealed = [c for c in self.world.spec_hidden_observations()
                        if c.provenance.get("location") == action.target]
            for hidden in revealed:
                claim = hidden.model_copy(update={"ingested_at": t})
                try:
                    self.ledger.append_claim(claim)
                    report.new_claims.append(claim)
                except Exception:
                    pass  # already revealed on an earlier replay
            return report

        if kind == ActionType.QUERY_MEMORY:
            return report  # deliberately yields nothing new

        if kind == ActionType.PICK_UP:
            obj = action.target
            obj_loc = self.world.true_location(obj)
            if self.ledger.get_entity(obj) is None:
                report.result = ActionResult.INVALID
                return report
            travel = self.world.distance(self.robot_location, obj_loc) \
                if obj_loc in self.world.spec.locations else 0
            report.time_spent = 1 + travel
            if obj_loc in self.world.spec.locations:
                self.robot_location = obj_loc
                self.world.positions[self.robot_id] = obj_loc
                report.robot_location = obj_loc
            t = now + report.time_spent
            container = self.world.true_container(obj)
            if container is not None:
                self.world.inside.pop(obj, None)   # open it, take the item
            self.world.held_by[obj] = self.robot_id
            # postcondition verified against world truth, then observed
            if self.world.held_by.get(obj) != self.robot_id:
                report.result = ActionResult.FAILED
                return report
            self._observe(report, obj, Predicate.CARRIED_BY,
                          self.robot_id, t, 0.99, "robot_gripper")
            return report

        if kind == ActionType.PLACE:
            obj = action.target
            if self.world.held_by.get(obj) != self.robot_id:
                report.result = ActionResult.INVALID
                return report
            self.world.held_by.pop(obj, None)
            self.world.positions[obj] = self.robot_location
            t = now + 1
            if self.world.true_location(obj) != self.robot_location:
                report.result = ActionResult.FAILED
                return report
            self._observe(report, obj, Predicate.LOCATED_AT,
                          self.robot_location, t, 0.99, "robot_gripper")
            return report

        report.result = ActionResult.INVALID
        return report
