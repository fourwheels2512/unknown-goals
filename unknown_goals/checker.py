"""The independent proof checker.

Every claim the engine derives carries a proof: the operator that produced
it, the claims it consumed, the rules it applied, the assumptions it made,
and the time constraints those inputs had to satisfy. This module
re-validates those proofs from a shipped ledger export, with no engine
code in the process: it reads the export's own claim list, its own rule
list, and the kit's table of built-in rule identifiers, and it re-derives
nothing.

A proof is valid when

  * it exists (a DERIVED claim without a proof is invalid),
  * it names an operator,
  * every input claim it cites is present in the same episode's ledger,
  * every rule it applies is a rule the episode knew (built-in or
    learned and carried in the export), and
  * every time constraint it asserts holds on the cited claims' intervals.

A constraint is written `A.event_time <op> B.event_time [+/- n]`, where A
and B are claim identifiers and the comparison is satisfiable over the
claims' event-time intervals: `>=` compares the latest of A with the
earliest of B, `<=` the earliest of A with the latest of B.

What this certifies and what it does not: the checker replays provenance.
It confirms that every conclusion the engine committed to is traceable to
evidence that was on the ledger, under rules the episode declared, in an
order time allows. It does not re-derive the conclusions, and it does not
score them: whether a conclusion was *right* is the artifact's hidden-truth
grading, not the checker's.

  python -m unknown_goals.checker data/exports/battery_final.jsonl.gz
  python -m unknown_goals.checker data/exports/*.jsonl.gz --quiet

Exit status is non-zero if any proof fails.

Copyright (c) 2026 Kiran Nayudu. Apache-2.0."""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from pathlib import Path
from typing import Iterator

DATA_DIR = Path(__file__).resolve().parent / "data"

# The grammar of a proof's time constraint. Ported unchanged from the
# engine's own proof checker so a kit verdict and an engine verdict cannot
# differ by interpretation.
_CONSTRAINT = re.compile(
    r"^(\S+)\.event_time\s*(<=|>=)\s*(\S+)\.event_time(?:\s*([+-])\s*(\d+))?$")

SCHEMA = "unknown-goals-ledger-export/1"


def builtin_rule_ids() -> set[str]:
    """Identifiers of the engine's hand-written rules.

    The kit ships each rule's id, description, status and version. A rule's
    measured reliability is part of the engine and is not in this table;
    the checker never needs it, because a proof cites a rule by identity."""
    path = DATA_DIR / "builtin_rules.json"
    rules = json.loads(path.read_text(encoding="utf-8"))
    return {r["rule_id"] for r in rules}


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
                if cid not in claims:
                    problems.append(f"dangling input {cid}")
            for rid in proof.get("rule_ids", []):
                if rid not in known_rules:
                    problems.append(f"unknown rule {rid}")
            for expr in proof.get("time_constraints", []):
                if not _constraint_holds(claims, expr):
                    problems.append(f"violated constraint {expr!r}")
            if not proof.get("operator"):
                problems.append("missing operator")
        if problems:
            errors.append(f"{claim['claim_id']}: {'; '.join(problems)}")
        else:
            valid += 1
    return valid, total, errors


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
    for ep in read_export(path):
        if ep.get("schema") != SCHEMA:
            raise ValueError(f"{path}: unexpected schema {ep.get('schema')!r}, "
                             f"expected {SCHEMA!r}")
        artifact = artifact or ep.get("artifact")
        v, t, errs = check_episode(ep)
        valid += v
        total += t
        errors += [f"[{episode_label(ep)}] {e}" for e in errs]
        episodes.append({"key": episode_label(ep), "valid": v, "total": t})
    return {"export": str(path), "artifact": artifact,
            "episodes": episodes, "n_episodes": len(episodes),
            "valid": valid, "total": total,
            "rate": (valid / total) if total else 1.0,
            "errors": errors}


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
