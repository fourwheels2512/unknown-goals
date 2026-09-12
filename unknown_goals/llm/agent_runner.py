"""LLM-as-agent episode runner for the head-to-head experiment.

FAIRNESS CONTRACT — the LLM gets exactly what the engine gets:
  - the identical observable evidence stream (rendered as plain text)
  - the identical action menu, simulator, sensors, and 8-action budget
  - the identical success rule: a fresh high-confidence observation confirms
  - graded against the identical hidden ground truth
One re-prompt is allowed on an unparseable reply (formatting != reasoning);
a second failure consumes the step as an invalid action.
"""

from __future__ import annotations

import json
import re

from unknown_goals.core.config import DEFAULT_CONFIG, EngineConfig
from unknown_goals.core.enums import ActionResult, ActionType, EntityType, Predicate
from unknown_goals.execution.executor import Executor
from unknown_goals.llm.ollama_client import OllamaClient
from unknown_goals.models.records import ActionSpec, Claim
from unknown_goals.simulation.world import World, WorldSpec
from unknown_goals.storage.ledger import Ledger

SYSTEM_PROMPT = """You are a warehouse robot searching for a missing object.
You receive sensor evidence (with confidence scores) and choose ONE action per turn.

Available actions:
- inspect_location(<location>): go look; reveals the object if visible there (not inside a cart)
- scan_container(<cart>): RFID scan; reveals whether the object is inside that cart
- replay_camera(<location>): re-examine past footage at a location for missed detections

Think briefly, then reply with ONLY a JSON object on the last line:
{"action": "inspect_location" | "scan_container" | "replay_camera", "target": "<name>"}"""

# The "strong" scaffold coaches the model in exactly the investigative strategy
# the engine uses, so the published comparison is against a well-prompted agent,
# not a strawman. (ReAct-style: enumerate hypotheses, pick the discriminating test.)
SYSTEM_PROMPT_STRONG = """You are a warehouse robot detective searching for a missing object.
You receive timestamped sensor evidence (with confidence scores) and choose ONE action per turn.

Available actions:
- inspect_location(<location>): go look; reveals the object if visible there (NOT if it is inside a cart)
- scan_container(<cart>): RFID scan; reveals whether the object is inside that cart
- replay_camera(<location>): re-examine past footage at a location for missed detections

Investigate like a detective. Before each action:
1. List the competing explanations, and keep ALL of them alive until evidence rules them out. Always consider at least:
   - a cart that left the area carried the object to its destination
   - the person last near the object STILL HAS IT at their current location (carts often leave empty!)
   - the object never actually moved (an absence report can be a missed detection)
   - a sensor misidentified the object
2. Weigh each explanation against ALL the evidence, noting confidence scores and time order.
3. Choose the action that best discriminates between the leading explanations.
4. NEVER repeat an action that already came up empty; when a check fails, shift belief to the next explanation and test THAT.

Think step by step, then reply with a JSON object on the LAST line:
{"action": "inspect_location" | "scan_container" | "replay_camera", "target": "<name>"}"""

_JSON_RE = re.compile(r"\{[^{}]*\}")

_ACTION_MAP = {
    "inspect_location": ActionType.INSPECT_LOCATION,
    "scan_container": ActionType.SCAN_CONTAINER,
    "replay_camera": ActionType.REPLAY_CAMERA,
}


def render_evidence(evidence: list[Claim]) -> str:
    lines = []
    for c in sorted(evidence, key=lambda c: (c.event_time_start, c.claim_id)):
        lines.append(f"t={c.event_time_start:>2} {c.source_id}: {c.subject} "
                     f"{c.predicate.value} {c.obj} (confidence {c.confidence:.2f})")
    return "\n".join(lines)


def _parse(reply: str) -> tuple[ActionType, str] | None:
    for match in reversed(_JSON_RE.findall(reply)):
        try:
            obj = json.loads(match)
        except json.JSONDecodeError:
            continue
        action = _ACTION_MAP.get(str(obj.get("action", "")).strip().lower())
        target = str(obj.get("target", "")).strip()
        if action and target:
            return action, target
    return None


class LLMEpisodeResult:
    def __init__(self) -> None:
        self.success = False
        self.found_at: str | None = None
        self.steps_used = 0
        self.invalid_actions = 0
        self.parse_failures = 0
        self.actions: list[str] = []
        self.ground_truth: str | None = None
        self.transcript: list[dict] = []   # per-step: thought, action, outcomes, robot

    @property
    def correct(self) -> bool:
        return self.success and self.found_at == self.ground_truth


def run_llm_episode(spec: WorldSpec, evidence: list[Claim],
                    client: OllamaClient,
                    config: EngineConfig = DEFAULT_CONFIG,
                    scaffold: str = "basic") -> LLMEpisodeResult:
    system_prompt = SYSTEM_PROMPT_STRONG if scaffold == "strong" else SYSTEM_PROMPT
    result = LLMEpisodeResult()
    ledger = Ledger()
    for entity in spec.entities:
        ledger.add_entity(entity)
    world = World(spec)
    start = max((e.t for e in spec.events), default=0) + 1
    world.advance_to(start)
    now = max([start] + [c.ingested_at for c in evidence])
    for claim in evidence:
        ledger.append_claim(claim)
    executor = Executor(world, ledger, config)
    result.ground_truth = world.true_location(spec.target)

    locations = sorted(e.entity_id for e in spec.entities
                       if e.entity_type == EntityType.LOCATION)
    containers = sorted(e.entity_id for e in spec.entities
                        if e.entity_type == EntityType.CONTAINER)

    goal_text = (f"GOAL: locate {spec.target}.\n"
                 f"Locations: {', '.join(locations)}. Carts: {', '.join(containers)}.\n\n"
                 f"EVIDENCE:\n{render_evidence(evidence)}\n")
    history: list[str] = []

    for step in range(config.budget.max_actions):
        user = goal_text
        if history:
            user += "\nYOUR ACTIONS SO FAR:\n" + "\n".join(history)
        user += f"\nChoose action {step + 1} of {config.budget.max_actions}."

        parsed = None
        reply = ""
        for attempt in range(2):
            reply = client.chat(system_prompt, user if attempt == 0 else
                                user + "\n\nYour previous reply was not valid JSON. "
                                       "Reply with ONLY the JSON object.")
            parsed = _parse(reply)
            if parsed:
                break
            result.parse_failures += 1

        thought = _JSON_RE.sub("", reply).strip()[:600]
        result.steps_used = step + 1
        if parsed is None:
            result.invalid_actions += 1
            history.append(f"step {step + 1}: (unparseable reply) -> wasted")
            result.transcript.append({"thought": thought, "action": None,
                                      "outcomes": [], "robot": None})
            continue

        action_type, target = parsed
        action = ActionSpec(action_type=action_type, target=target)
        report = executor.execute(action, spec.target, now)
        now += report.time_spent
        result.actions.append(f"{action_type.value}({target})")

        if report.result == ActionResult.INVALID:
            result.invalid_actions += 1
            history.append(f"step {step + 1}: {action_type.value}({target}) -> INVALID target")
            result.transcript.append({
                "thought": thought,
                "action": {"type": action_type.value, "target": target},
                "outcomes": ["INVALID target"], "robot": executor.robot_location})
            continue

        outcomes = []
        for c in report.new_claims:
            outcomes.append(f"{c.subject} {c.predicate.value} {c.obj} "
                            f"(confidence {c.confidence:.2f})")
            if (c.subject == spec.target and c.predicate == Predicate.LOCATED_AT
                    and c.confidence >= 0.9):
                result.success = True
                result.found_at = c.obj
        history.append(f"step {step + 1}: {action_type.value}({target}) -> "
                       + ("; ".join(outcomes) if outcomes else "no new information"))
        result.transcript.append({
            "thought": thought,
            "action": {"type": action_type.value, "target": target},
            "outcomes": outcomes,
            "robot": executor.robot_location})
        if result.success:
            break

    return result
