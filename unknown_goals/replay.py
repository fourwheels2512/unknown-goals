"""Walk one engine episode, decision by decision, against the evidence it
was made on.

The export carries, for every step the engine took: how many claims were on
the ledger when it chose, the hypotheses it was holding with their belief
and epistemic status, the action it chose and the rationale it gave, the
outcome, and the claims that outcome put on the ledger. This replays that
record in order, then prints the result against the episode's hidden ground
truth and the proof path of the last claim the engine derived, with the
kit's own checker verdict on it.

  python -m unknown_goals.replay data/exports/battery_final.jsonl.gz \
      --episode test=T2 seed=10007 level=6
  python -m unknown_goals.replay data/exports/budget_sweep.jsonl.gz --index 0
  python -m unknown_goals.replay data/exports/battery_final.jsonl.gz --list

Nothing here re-derives anything: the replayer reads what the engine
recorded and the checker re-validates the provenance of it.

Copyright (c) 2026 Kiran Nayudu. Apache-2.0."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from unknown_goals.checker import check_episode, episode_label, read_export

RULE = "-" * 72


def _match(episode: dict, wanted: dict[str, str]) -> bool:
    key = episode.get("episode_key", {})
    for k, v in wanted.items():
        if k not in key:
            return False
        if str(key[k]) != v:
            return False
    return True


def select(path: str | Path, wanted: dict[str, str],
           index: int | None) -> dict:
    episodes = list(read_export(path))
    if index is not None:
        if not -len(episodes) <= index < len(episodes):
            raise SystemExit(f"index {index} out of range "
                             f"({len(episodes)} episodes in {path})")
        return episodes[index]
    hits = [e for e in episodes if _match(e, wanted)]
    if not hits:
        if not episodes:
            raise SystemExit(f"{path} is empty")
        terms = " ".join(f"{k}={v}" for k, v in wanted.items())
        raise SystemExit(f"no episode in {path} matches {terms}\n"
                         f"keys present, e.g.: {episode_label(episodes[0])}")
    if len(hits) > 1:
        raise SystemExit(f"{len(hits)} episodes match; add key=value terms "
                         f"(first: {episode_label(hits[0])})")
    return hits[0]


def _claim_line(c: dict) -> str:
    eff = c.get("effective_status", c.get("status"))
    status = c["status"] if eff == c["status"] else f"{c['status']}->{eff}"
    t = (f"t={c['event_time_start']}"
         if c["event_time_start"] == c["event_time_end"]
         else f"t={c['event_time_start']}..{c['event_time_end']}")
    return (f"    {c['claim_id']:<22} {c['subject']} {c['predicate']} "
            f"{c['obj']}  conf={c['confidence']:.2f}  {status}  {t}  "
            f"src={c['source_id']}")


def replay(episode: dict, out=None, max_new_claims: int = 12) -> int:
    # resolved here, not in the signature: a default bound at import time
    # would write past anything that redirects stdout later
    out = out if out is not None else sys.stdout
    claims = episode.get("claims", [])
    by_id = {c["claim_id"]: c for c in claims}
    key = episode_label(episode)
    eng = episode.get("engine", {})

    print(RULE, file=out)
    print(f"episode {key}", file=out)
    print(f"artifact {episode.get('artifact')}", file=out)
    print(f"engine {eng.get('version')} config {eng.get('config_version')} "
          f"rules {eng.get('rules_version')}", file=out)
    print(f"{len(episode.get('entities', []))} entities, {len(claims)} claims, "
          f"{len(episode.get('rules', []))} rules known", file=out)
    print(RULE, file=out)

    decisions = episode.get("decisions", [])
    for d in decisions:
        n_before = d.get("claims_before", 0)
        print(f"\nstep {d.get('step')}  [{n_before} claims on the ledger]",
              file=out)
        hyps = d.get("hypotheses", [])
        if hyps:
            print("  hypotheses:", file=out)
            for h in hyps:
                where = h.get("candidate_location")
                extra = []
                if h.get("container"):
                    extra.append(f"in {h['container']}")
                if h.get("carrier"):
                    extra.append(f"with {h['carrier']}")
                tail = ("  (" + ", ".join(extra) + ")") if extra else ""
                print(f"    belief {h.get('belief', 0.0):.3f}  "
                      f"{h.get('status', ''):<14} {where}{tail}", file=out)
                if h.get("description"):
                    print(f"        {h['description']}", file=out)
        print(f"  action: {d.get('action_type')} {d.get('target')}", file=out)
        if d.get("rationale"):
            print(f"  because: {d['rationale']}", file=out)
        print(f"  outcome: {d.get('result')}", file=out)
        new_ids = d.get("new_claim_ids", [])
        if new_ids:
            print(f"  new evidence ({len(new_ids)} claims):", file=out)
            for cid in new_ids[:max_new_claims]:
                c = by_id.get(cid)
                print(_claim_line(c) if c else f"    {cid}  <not in export>",
                      file=out)
            if len(new_ids) > max_new_claims:
                print(f"    ... {len(new_ids) - max_new_claims} more", file=out)
        else:
            print("  new evidence: none", file=out)

    res = episode.get("result", {})
    print("\n" + RULE, file=out)
    verdict = ("CORRECT" if res.get("correct")
               else "WRONG" if res.get("success") else "NO COMMITMENT")
    print(f"result: {verdict}   goal {res.get('goal_status')}   "
          f"{res.get('steps_used')} steps", file=out)
    print(f"  committed to : {res.get('found_at')}", file=out)
    print(f"  ground truth : {res.get('ground_truth_location')}", file=out)

    derived = [c for c in claims if c.get("status") == "DERIVED"]
    valid, total, errors = check_episode(episode)
    print(f"\nproof audit: {valid}/{total} derived claims replay", file=out)
    for e in errors:
        print(f"  INVALID {e}", file=out)
    if derived:
        # the top derived claim: the one the engine was most confident of,
        # ties going to the one it derived last
        top = max(enumerate(derived), key=lambda p: (p[1]["confidence"], p[0]))[1]
        proof = top.get("proof") or {}
        print(f"\nproof path of {top['claim_id']} "
              f"({top['subject']} {top['predicate']} {top['obj']}, "
              f"conf {top['confidence']:.2f}):", file=out)
        print(f"  operator   : {proof.get('operator')}", file=out)
        for cid in proof.get("input_claims", []):
            c = by_id.get(cid)
            print(f"  input      : {cid}"
                  + (f"  {c['subject']} {c['predicate']} {c['obj']} "
                     f"({c['status']}, conf {c['confidence']:.2f})" if c
                     else "  <not in export>"), file=out)
        for rid in proof.get("rule_ids", []):
            desc = next((r.get("description", "") for r in episode.get("rules", [])
                         if r.get("rule_id") == rid), "")
            print(f"  rule       : {rid}" + (f"  {desc}" if desc else ""),
                  file=out)
        for a in proof.get("assumptions", []):
            print(f"  assumption : {a}", file=out)
        for t in proof.get("time_constraints", []):
            print(f"  constraint : {t}", file=out)
        faulted = any(e.startswith(top["claim_id"] + ":") for e in errors)
        print(f"  checker    : {'INVALID' if faulted else 'VALID'}", file=out)
    print(RULE, file=out)
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="unknown-goals-replay",
        description="Walk one engine episode against its evidence.")
    ap.add_argument("export", help="data/exports/<artifact>.jsonl.gz")
    ap.add_argument("--episode", nargs="*", default=[], metavar="key=value",
                    help="episode_key terms, e.g. test=T2 seed=10007 level=6")
    ap.add_argument("--index", type=int, default=None,
                    help="pick by position instead (0 is the first row)")
    ap.add_argument("--list", action="store_true",
                    help="list the episode keys in the file and stop")
    args = ap.parse_args(argv)

    if args.list:
        for i, ep in enumerate(read_export(args.export)):
            print(f"{i:5d}  {episode_label(ep)}")
        return 0
    wanted: dict[str, str] = {}
    for term in args.episode:
        if "=" not in term:
            ap.error(f"--episode takes key=value terms, got {term!r}")
        k, v = term.split("=", 1)
        wanted[k] = v
    if not wanted and args.index is None:
        ap.error("give --episode key=value ... or --index N or --list")
    return replay(select(args.export, wanted, args.index))


if __name__ == "__main__":
    raise SystemExit(main())
