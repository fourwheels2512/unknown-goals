"""The independent proof checker.

Every claim the engine derives carries a proof: the operator that produced
it, the claims it consumed, the rules it applied, the assumptions it made,
and the time constraints those inputs had to satisfy. This module
re-validates those proofs from a shipped ledger export, with no engine
code in the process: it reads the export's own claim list, its own rule
list, the kit's table of built-in rule identifiers and the kit's table of
proof operators, and it re-derives nothing.

A proof is valid when

  * it exists (a DERIVED claim without a proof is invalid),
  * it names an operator, and the operator is one the engine emits
    (`data/operators.json`),
  * every input claim it cites is present in the same episode's ledger,
  * every input claim it cites was on the ledger before the claim it
    supports (`ingested_at` no later),
  * every rule it applies is a rule the episode knew (built-in or
    learned and carried in the export), and
  * every time constraint it asserts holds on the cited claims' intervals.

A constraint is written `A.event_time <op> B.event_time [+/- n]`, where A
and B are claim identifiers and the comparison is satisfiable over the
claims' event-time intervals: `>=` compares the latest of A with the
earliest of B, `<=` the earliest of A with the latest of B.

Two things beyond provenance are checked, where the export records them.

**The commitment.** An episode that ends FOUND names the room it committed
to. The checker requires an observation of the object in that room --
status OBSERVED, confidence at the resolution bar or above, and made by
something other than the reasoner. A commitment the ledger does not
witness is an invalid episode. Exports written before these fields existed
carry no verdict; those episodes are counted as "commitment not
checkable" and the run still passes.

**The absence certificate.** An episode that ends NOT_FOUND carries one
certificate claim, and the checker re-derives its content rather than
reading it back: it recomputes, from the export's own entities, the rooms
the robot knew about; it recomputes, from the export's own claims, the
last report that placed the object anywhere; and it requires the
certificate to cite one late-enough empty-handed look per room and that
last placing report. The look has to be the robot's own: an observation
one of its actions returned, not a report and not a third party's sensor,
because a room the robot never entered is a room it did not cover. A
certificate covering some of the rooms, or resting on a second-hand tip or
on somebody else's camera, or ignoring a later sighting, fails.

A certificate may state one assumption that changes the rule it is read
under. An assumption line beginning `target static:` says the object cannot
move, and the ordering of looks is then re-derived per place: each covered
place's clearing look against the newest claim that placed the object at
THAT place, and each place the robot could not reach that something placed
the object at against the robot's own later look that found it empty, which
the certificate has to name (`refuted: <sighting> by <look>`). A claim that
places the object outside the places altogether -- carried by somebody, last
seen with somebody -- still has to be postdated by every clearing look,
because a carrier could have taken it anywhere. Without that line the rule
above applies unchanged, so a certificate cannot be read under the weaker
ordering without declaring the assumption in its own text.

What this certifies and what it does not: the checker replays provenance
and tests the two commitments above. It confirms that every conclusion the
engine committed to is traceable to evidence that was on the ledger, under
rules the episode declared, in an order time allows; that a find was
witnessed; and that a NOT-FOUND rests on a complete, current sweep. It
does not re-derive the belief numbers -- how much a hypothesis was worth is
the engine's arithmetic and no part of this file -- and it does not score
the outcome: whether a conclusion was *right* is the artifact's
hidden-truth grading, not the checker's.

  python -m unknown_goals.checker data/exports/battery_final.jsonl.gz
  python -m unknown_goals.checker data/exports/*.jsonl.gz --quiet

Exit status is non-zero if any proof, commitment or certificate fails.

Copyright (c) 2026 Kiran Nayudu. Apache-2.0."""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Iterator

DATA_DIR = Path(__file__).resolve().parent / "data"

# The grammar of a proof's time constraint. Ported unchanged from the
# engine's own proof checker so a kit verdict and an engine verdict cannot
# differ by interpretation.
_CONSTRAINT = re.compile(
    r"^(\S+)\.event_time\s*(<=|>=)\s*(\S+)\.event_time(?:\s*([+-])\s*(\d+))?$")

SCHEMA = "unknown-goals-ledger-export/1"

# --- the absence certificate's fixed vocabulary ----------------------------
# A claim that says the object is in none of the rooms the robot knows
# about. The predicate and the object below are the certificate's shape;
# the operator is how a proof announces itself as one.
CERTIFICATE_OPERATOR = "coverage_certificate"
CERTIFICATE_PREDICATE = "ABSENT_FROM"
CERTIFICATE_OBJECT = "all_known_locations"
ABSENCE_PREDICATE = "ABSENT_FROM"

# A claim that puts the object somewhere. The certificate has to be no
# older than the last of these, whoever made it: a second-hand tip that
# arrives late still means the sweep has to be redone.
PLACING_PREDICATES = ("LOCATED_AT", "NEAR", "CARRIED_BY", "LAST_SEEN_WITH",
                      "INSIDE")
# The placing predicates that name a PLACE. The other two name a person or
# a thing, and place the object wherever that carrier has since gone, so
# they say something about every place at once.
ROOM_PLACING_PREDICATES = ("LOCATED_AT", "INSIDE", "NEAR")
PLACING_STATUSES = ("OBSERVED", "REPORTED")

# A certificate may state one assumption that changes the rule it is read
# under: an assumption line beginning `target static:` says the object
# cannot move, and then the ordering of looks is re-derived PER PLACE
# instead of across places. Without the line the rule below is unchanged.
# The prefix is what is matched; the sentence is what a reader of the proof
# sees, and it is the same text the engine writes.
STATIC_TARGET_PREFIX = "target static:"
STATIC_TARGET_ASSUMPTION = (
    "target static: the target does not move, so each place is cleared by "
    "its own newest look against the newest claim that placed the target at "
    "that place, and a claim about one place does not stale another's look")
_REFUTED = re.compile(r"^refuted:\s*(\S+)\s+by\s+(\S+)\s*$")

# The confidence at which the robot treats a look as having settled the
# question. Public: it is the resolution bar the paper reports, not a
# weight of the belief arithmetic.
RESOLUTION_BAR = 0.9

VERDICTS = ("FOUND", "NOT_FOUND", "UNDECIDED")

_ROOMS_PREFIX = "rooms:"
_EXCLUDED_PREFIX = "excluded:"


@lru_cache(maxsize=1)
def builtin_rule_ids() -> frozenset[str]:
    """Identifiers of the engine's hand-written rules.

    The kit ships each rule's id, description, status and version. A rule's
    measured reliability is part of the engine and is not in this table;
    the checker never needs it, because a proof cites a rule by identity."""
    path = DATA_DIR / "builtin_rules.json"
    rules = json.loads(path.read_text(encoding="utf-8"))
    return frozenset(r["rule_id"] for r in rules)


@lru_cache(maxsize=1)
def known_operators() -> frozenset[str]:
    """Every operator name a proof may carry (`data/operators.json`).

    A proof step names the operator that produced it. An export that names
    a step outside this table is describing something the engine does not
    do, so the proof is rejected rather than replayed."""
    path = DATA_DIR / "operators.json"
    table = json.loads(path.read_text(encoding="utf-8"))
    return frozenset(row["operator"] for row in table["operators"])


def read_export(path: str | Path) -> Iterator[dict]:
    """One episode per line, in the artifact's own row order."""
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as fh:  # type: ignore[operator]
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: not JSON: {exc}") from exc


def _interval(claim: dict) -> tuple[int, int]:
    return int(claim["event_time_start"]), int(claim["event_time_end"])


def _constraint_holds(claims: dict[str, dict], expr: str) -> bool:
    m = _CONSTRAINT.match(expr.strip())
    if not m:
        return False
    a_id, op, b_id, sign, offset = m.groups()
    a, b = claims.get(a_id), claims.get(b_id)
    if a is None or b is None:
        return False
    delta = int(offset or 0) * (-1 if sign == "-" else 1)
    a_start, a_end = _interval(a)
    b_start, b_end = _interval(b)
    if op == ">=":       # satisfiable on intervals: latest of a vs earliest of b
        return a_end >= b_start + delta
    return a_start <= b_end + delta


def check_episode(episode: dict) -> tuple[int, int, list[str]]:
    """Returns (valid, total, error descriptions) over the episode's
    DERIVED claims.

    The engine's checker tests `claim.status` -- the status the claim was
    ingested with -- not the status it ended the episode in. A claim that
    was derived and later contradicted still has to carry a sound proof of
    how it was derived, so this tests `status` too, and `effective_status`
    is reported by the replayer rather than used here."""
    claims = {c["claim_id"]: c for c in episode.get("claims", [])}
    known_rules = builtin_rule_ids() | {
        r["rule_id"] for r in episode.get("rules", [])}
    operators = known_operators()
    valid = total = 0
    errors: list[str] = []
    for claim in episode.get("claims", []):
        if claim.get("status") != "DERIVED":
            continue
        total += 1
        problems: list[str] = []
        proof = claim.get("proof")
        if proof is None:
            problems.append("missing proof")
        else:
            for cid in proof.get("input_claims", []):
                source = claims.get(cid)
                if source is None:
                    problems.append(f"dangling input {cid}")
                    continue
                theirs, ours = source.get("ingested_at"), claim.get("ingested_at")
                if theirs is not None and ours is not None and theirs > ours:
                    problems.append(
                        f"input {cid} reached the ledger at {theirs}, after "
                        f"the claim it supports at {ours}")
            for rid in proof.get("rule_ids", []):
                if rid not in known_rules:
                    problems.append(f"unknown rule {rid}")
            for expr in proof.get("time_constraints", []):
                if not _constraint_holds(claims, expr):
                    problems.append(f"violated constraint {expr!r}")
            operator = proof.get("operator")
            if not operator:
                problems.append("missing operator")
            elif operator not in operators:
                problems.append(f"unknown operator {operator!r}")
        if problems:
            errors.append(f"{claim['claim_id']}: {'; '.join(problems)}")
        else:
            valid += 1
    return valid, total, errors


# --------------------------------------------------------------- commitment

def _claims_of(episode: dict) -> list[dict]:
    return list(episode.get("claims", []))


def certificate_claims(episode: dict) -> list[dict]:
    """Every claim in the episode whose proof announces an absence
    certificate."""
    out = []
    for claim in _claims_of(episode):
        proof = claim.get("proof") or {}
        if proof.get("operator") == CERTIFICATE_OPERATOR:
            out.append(claim)
    return out


def check_commitment(episode: dict) -> tuple[str, list[str]]:
    """What the episode committed to, tested against its own ledger.

    Returns one of "checked", "not checkable" or "failed", and the reasons
    where it failed. "not checkable" is what an export written before the
    verdict fields existed returns; it is not a failure, and the count is
    reported so nobody mistakes an unchecked episode for a checked one."""
    result = episode.get("result") or {}
    target, verdict = result.get("target"), result.get("verdict")
    if target is None or verdict is None:
        return "not checkable", []

    errors: list[str] = []
    found_at = result.get("found_at")
    certificates = certificate_claims(episode)

    if verdict not in VERDICTS:
        errors.append(f"verdict '{verdict}' is not one of {list(VERDICTS)}")

    if verdict == "FOUND":
        if not found_at:
            errors.append("verdict FOUND, but the episode names no room")
        else:
            witnesses = [c for c in _claims_of(episode)
                         if c.get("subject") == target
                         and c.get("predicate") == "LOCATED_AT"
                         and c.get("obj") == found_at
                         and c.get("status") == "OBSERVED"]
            if not witnesses:
                errors.append(
                    f"committed to {target} at {found_at} with no observation "
                    f"of it there: no OBSERVED LOCATED_AT({target}, "
                    f"{found_at}) on this ledger")
            elif not any(w.get("confidence", 0) >= RESOLUTION_BAR
                         and w.get("source_id") != "reasoner"
                         for w in witnesses):
                for w in witnesses:
                    why = []
                    if w.get("confidence", 0) < RESOLUTION_BAR:
                        why.append(f"confidence {w.get('confidence')} is "
                                   f"below the resolution bar {RESOLUTION_BAR}")
                    if w.get("source_id") == "reasoner":
                        why.append("the reasoner is its own source, so it "
                                   "witnesses nothing")
                    errors.append(
                        f"{w['claim_id']}: cannot witness the commitment to "
                        f"{target} at {found_at}: {'; '.join(why)}")
    elif found_at:
        errors.append(f"verdict {verdict}, but the episode names {found_at} "
                      f"as the room it found {target} in")

    if verdict == "NOT_FOUND" and not certificates:
        errors.append(f"verdict NOT_FOUND for {target} with no absence "
                      f"certificate on the ledger")
    if certificates and verdict != "NOT_FOUND":
        errors.append(f"{certificates[0]['claim_id']}: an absence certificate "
                      f"in an episode whose verdict is {verdict}")

    return ("failed" if errors else "checked"), errors


# -------------------------------------------------------------- certificate

def _assumption_list(assumptions: list[str], prefix: str) -> list[str] | None:
    """The comma-separated list an assumption line carries, or None when no
    line starts with `prefix`."""
    for line in assumptions:
        text = str(line).strip()
        if text.lower().startswith(prefix):
            body = text[len(prefix):].strip()
            return [part.strip() for part in body.split(",") if part.strip()]
    return None


def latest_placing_claim(claims: list[dict], target: str) -> dict | None:
    """The last report that put `target` anywhere, recomputed from the
    export's own claims.

    Observed and reported claims count; a derived, hypothesised, predicted
    or simulated one does not, because the certificate is about what was
    seen or said, not about what was worked out."""
    placing = [c for c in claims
               if c.get("subject") == target
               and c.get("status") in PLACING_STATUSES
               and c.get("predicate") in PLACING_PREDICATES]
    if not placing:
        return None
    return max(placing, key=lambda c: (int(c["event_time_end"]),
                                       str(c["claim_id"])))


def static_target_assumed(assumptions: list[str]) -> bool:
    """Does this certificate declare that its object cannot move?"""
    return any(str(a).strip().lower().startswith(STATIC_TARGET_PREFIX)
               for a in assumptions)


def refuted_pairs(assumptions: list[str]) -> dict[str, str]:
    """The `refuted: <placing> by <absence>` lines, as placing -> absence."""
    out: dict[str, str] = {}
    for line in assumptions:
        m = _REFUTED.match(str(line).strip())
        if m:
            out[m.group(1)] = m.group(2)
    return out


def placing_claims_by_place(claims: list[dict], target: str,
                            known: set[str]) -> tuple[dict, dict | None]:
    """The newest claim that placed `target` at each place the episode
    knows, and the newest claim that placed it somewhere that is not one of
    them (carried by somebody, last seen with somebody, or inside something
    this episode does not know as a place).

    Recomputed from the export's own claims, ordered exactly as
    `latest_placing_claim` orders them, so a certificate that reads the
    ordering per place can be checked against the claims rather than
    believed."""
    at_place: dict[str, dict] = {}
    elsewhere = None

    def key(claim: dict) -> tuple:
        return (int(claim["event_time_end"]), str(claim["claim_id"]))

    for c in claims:
        if c.get("subject") != target \
                or c.get("status") not in PLACING_STATUSES \
                or c.get("predicate") not in PLACING_PREDICATES:
            continue
        if c.get("predicate") in ROOM_PLACING_PREDICATES \
                and c.get("obj") in known:
            current = at_place.get(str(c.get("obj")))
            if current is None or key(c) > key(current):
                at_place[str(c.get("obj"))] = c
        elif elsewhere is None or key(c) > key(elsewhere):
            elsewhere = c
    return at_place, elsewhere


def check_certificate(episode: dict) -> tuple[str, list[str]]:
    """Re-derive an absence certificate from the export it sits in.

    Returns "none" when the episode carries no certificate, otherwise
    "checked" or "failed" with the reasons. Nothing here reads the
    certificate's own account of itself except the list of rooms it
    excluded as unreachable, which the export cannot settle either way,
    and the assumption it declares about its object -- static or not --
    which decides which ordering rule the rest is checked against: every
    other part is recomputed and compared."""
    certificates = certificate_claims(episode)
    if not certificates:
        return "none", []

    claims = _claims_of(episode)
    by_id = {c["claim_id"]: c for c in claims}
    errors: list[str] = []
    if len(certificates) > 1:
        errors.append(
            f"{', '.join(c['claim_id'] for c in certificates)}: "
            f"{len(certificates)} absence certificates in one episode; an "
            f"episode ends once, so it certifies once")

    cert = certificates[0]
    cid = cert["claim_id"]
    target = cert.get("subject")
    stated_target = (episode.get("result") or {}).get("target")
    if stated_target is not None and stated_target != target:
        errors.append(f"{cid}: certifies the absence of {target}, but the "
                      f"episode was looking for {stated_target}")
    if cert.get("status") != "DERIVED":
        errors.append(f"{cid}: an absence certificate is a derived claim; "
                      f"this one is {cert.get('status')}")
    if cert.get("predicate") != CERTIFICATE_PREDICATE:
        errors.append(f"{cid}: predicate '{cert.get('predicate')}', expected "
                      f"'{CERTIFICATE_PREDICATE}'")
    if cert.get("obj") != CERTIFICATE_OBJECT:
        errors.append(f"{cid}: object '{cert.get('obj')}', expected "
                      f"'{CERTIFICATE_OBJECT}'")

    proof = cert.get("proof") or {}
    cited_ids = list(proof.get("input_claims") or [])
    cited = [by_id[x] for x in cited_ids if x in by_id]
    assumptions = [str(a) for a in (proof.get("assumptions") or [])]

    # the rooms: recomputed from the export's own entities, less the ones
    # the certificate says it could not reach
    known_rooms = {e["entity_id"] for e in episode.get("entities", [])
                   if e.get("entity_type") == "LOCATION"}
    excluded = set(_assumption_list(assumptions, _EXCLUDED_PREFIX) or [])
    stray = sorted(excluded - known_rooms)
    if stray:
        errors.append(f"{cid}: excludes {', '.join(stray)}, which this "
                      f"episode does not know as rooms")
    covered = known_rooms - excluded
    if not covered:
        errors.append(f"{cid}: certifies a sweep of no rooms at all")

    declared = _assumption_list(assumptions, _ROOMS_PREFIX)
    if declared is None:
        errors.append(f"{cid}: does not say which rooms it swept")
    elif set(declared) != covered:
        short = sorted(covered - set(declared))
        extra = sorted(set(declared) - covered)
        parts = []
        if short:
            parts.append(f"leaves out {', '.join(short)}")
        if extra:
            parts.append(f"names {', '.join(extra)}, which are not rooms of "
                         f"this episode")
        errors.append(f"{cid}: says it swept {len(declared)} of the "
                      f"{len(covered)} rooms it had to: {'; '.join(parts)}")

    # the last thing that placed the object, recomputed -- or, under the
    # static assumption, the last thing that placed it at each place and
    # the last thing that placed it outside the places altogether
    static = static_target_assumed(assumptions)
    placing = latest_placing_claim(claims, target) if target else None
    at_place: dict[str, dict] = {}
    elsewhere = None
    refuted_by: dict[str, str] = {}
    if static:
        if target:
            at_place, elsewhere = placing_claims_by_place(claims, target,
                                                          known_rooms)
        refuted_by = refuted_pairs(assumptions)
        for room in sorted(covered):
            p = at_place.get(room)
            if p is not None and p["claim_id"] not in cited_ids:
                errors.append(
                    f"{cid}: does not cite {p['claim_id']}, the last report "
                    f"that placed {target} at {room}")
        if elsewhere is not None and elsewhere["claim_id"] not in cited_ids:
            errors.append(
                f"{cid}: does not cite {elsewhere['claim_id']}, the last "
                f"report that placed {target} ({elsewhere.get('predicate')} "
                f"{elsewhere.get('obj')}, ending at "
                f"{elsewhere.get('event_time_end')})")
    elif placing is not None and placing["claim_id"] not in cited_ids:
        errors.append(
            f"{cid}: does not cite {placing['claim_id']}, the last report "
            f"that placed {target} ({placing.get('predicate')} "
            f"{placing.get('obj')}, ending at {placing.get('event_time_end')})")

    # one observed, late-enough empty-handed look per room
    absences: dict[str, list[dict]] = {}
    for c in cited:
        if c.get("predicate") != ABSENCE_PREDICATE:
            continue
        if c.get("subject") != target:
            errors.append(f"{cid}: cites {c['claim_id']}, an absence of "
                          f"{c.get('subject')} and not of {target}")
            continue
        absences.setdefault(str(c.get("obj")), []).append(c)

    # a certificate under the static assumption may also cite the looks that
    # closed an open lead at a place it could not reach; every other absence
    # has to be at a place it says it covered
    allowed = covered | excluded if static else covered
    for room in sorted(set(absences) - allowed):
        errors.append(f"{cid}: cites an absence from {room}, which is not "
                      f"one of the rooms it covers")

    for room in sorted(covered):
        candidates = absences.get(room, [])
        if not candidates:
            errors.append(f"{cid}: cites nothing that found {room} empty of "
                          f"{target}")
            continue
        # what this room's clearing look has to postdate: under the static
        # assumption the newest claim that placed the object AT THIS ROOM
        # and any claim that placed it outside the rooms altogether;
        # otherwise the newest claim that placed it anywhere
        against = [at_place.get(room), elsewhere] if static else [placing]
        reasons: list[str] = []
        cleared = False
        for a in candidates:
            if a.get("status") != "OBSERVED":
                reasons.append(f"{a['claim_id']} is a {a.get('status')} "
                               f"absence from {room}, and only a look of the "
                               f"robot's own clears a room")
                continue
            if not (a.get("provenance") or {}).get("via_action"):
                reasons.append(f"{a['claim_id']} is an absence from {room} "
                               f"that no action of the robot's returned, and "
                               f"only a look of the robot's own clears a room")
                continue
            stale = next((p for p in against if p is not None
                          and int(a["event_time_end"])
                          < int(p["event_time_start"])), None)
            if stale is not None:
                reasons.append(
                    f"{a['claim_id']} found {room} empty at "
                    f"{a['event_time_end']}, before {stale['claim_id']} "
                    f"placed {target} at {stale['event_time_start']}")
                continue
            cleared = True
            break
        if not cleared:
            errors.append(f"{cid}: nothing clears {room}: {'; '.join(reasons)}")

    # a place the robot could not reach that something placed the object at
    # is an open lead unless one of the robot's own later looks found it
    # empty, and the certificate has to name that pair
    if static:
        for room in sorted(excluded):
            p = at_place.get(room)
            if p is None:
                continue
            look = by_id.get(refuted_by.get(p["claim_id"], ""))
            if not (look is not None
                    and look["claim_id"] in cited_ids
                    and look.get("subject") == target
                    and look.get("predicate") == ABSENCE_PREDICATE
                    and str(look.get("obj")) == room
                    and look.get("status") == "OBSERVED"
                    and (look.get("provenance") or {}).get("via_action")
                    and int(look["event_time_end"])
                    >= int(p["event_time_start"])):
                errors.append(
                    f"{cid}: {room} is excluded but {p['claim_id']} placed "
                    f"{target} there and nothing of the robot's own later "
                    f"found it empty")

    return ("failed" if errors else "checked"), errors


def episode_label(episode: dict) -> str:
    key = episode.get("episode_key", {})
    return " ".join(f"{k}={v}" for k, v in key.items()) or "<no key>"


def check_export(path: str | Path) -> dict:
    """Checks one export file. Returns a summary dict; never raises on an
    invalid proof (the caller decides what an invalid proof means)."""
    episodes: list[dict] = []
    valid = total = 0
    errors: list[str] = []
    artifact = None
    counts = {"commitments_checked": 0, "commitments_not_checkable": 0,
              "commitments_failed": 0,
              "certificates_checked": 0, "certificates_failed": 0}
    for ep in read_export(path):
        if ep.get("schema") != SCHEMA:
            raise ValueError(f"{path}: unexpected schema {ep.get('schema')!r}, "
                             f"expected {SCHEMA!r}")
        artifact = artifact or ep.get("artifact")
        label = episode_label(ep)
        v, t, errs = check_episode(ep)
        valid += v
        total += t
        errors += [f"[{label}] {e}" for e in errs]

        commitment, cerrs = check_commitment(ep)
        counts["commitments_" + commitment.replace(" ", "_")] += 1
        errors += [f"[{label}] commitment: {e}" for e in cerrs]

        certificate, kerrs = check_certificate(ep)
        if certificate != "none":
            counts["certificates_" + certificate] += 1
        errors += [f"[{label}] certificate: {e}" for e in kerrs]

        episodes.append({"key": label, "valid": v, "total": t,
                         "commitment": commitment, "certificate": certificate})
    return {"export": str(path), "artifact": artifact,
            "episodes": episodes, "n_episodes": len(episodes),
            "valid": valid, "total": total,
            "rate": (valid / total) if total else 1.0,
            "errors": errors, **counts}


def summary_line(summary: dict) -> str:
    """The commitment and certificate counts, for a printed report."""
    return (f"commitments {summary['commitments_checked']} checked, "
            f"{summary['commitments_failed']} failed, "
            f"{summary['commitments_not_checkable']} not checkable; "
            f"certificates {summary['certificates_checked']} checked, "
            f"{summary['certificates_failed']} failed")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="unknown-goals-check",
        description="Re-validate every proof path in a ledger export.")
    ap.add_argument("exports", nargs="+", help="data/exports/*.jsonl.gz")
    ap.add_argument("--quiet", action="store_true",
                    help="artifact totals only, no per-episode lines")
    ap.add_argument("--expect-proofs", type=float, default=None,
                    help="fail unless the proof-validity rate equals this "
                         "exactly (the artifact's own `proofs` field)")
    args = ap.parse_args(argv)

    bad = 0
    for spec in args.exports:
        summary = check_export(spec)
        if not args.quiet:
            for ep in summary["episodes"]:
                print(f"  {ep['key']:<48} proofs {ep['valid']}/{ep['total']}")
        rate = summary["rate"]
        print(f"{Path(spec).name}: {summary['n_episodes']} episodes, "
              f"proofs {summary['valid']}/{summary['total']} "
              f"= {rate:.6f}"
              + (f"   [{summary['artifact']}]" if summary["artifact"] else ""))
        print(f"  {summary_line(summary)}")
        for err in summary["errors"]:
            print(f"  INVALID {err}", file=sys.stderr)
            bad += 1
        if args.expect_proofs is not None and rate != args.expect_proofs:
            print(f"  MISMATCH: artifact records proofs="
                  f"{args.expect_proofs}, checker computes {rate}",
                  file=sys.stderr)
            bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
