"""One command that checks this kit against the paper.

    python -m unknown_goals.verify            # everything
    python -m unknown_goals.verify --quick    # skips the 100-seed suites

It does two things.

**It regenerates the baselines.** Every number the engine is compared
against in the paper's warehouse tables comes from a script in
`baselines/`, driven by integer seeds, with no engine in the loop. This
runs those scripts here and compares what comes out with the JSON
committed in `data/artifacts/`, field by field, ignoring only the timing
and machine fields a second run cannot reproduce. A baseline that does not
come back identical is a failure, and the failure is the kit's, never the
artifact's: the artifacts are the record of what was measured.

**It re-validates the proofs, and the commitments.** For every ledger
export in `data/exports/`, the kit's own checker replays the provenance of
every claim the engine derived, with no engine code. Where the summary
artifact records a proof-validity fraction of its own, the checker's
fraction has to equal it exactly. Beside the proofs it tests what each
episode committed to: a find has to be witnessed by an observation of the
object in the room named, and a NOT-FOUND has to carry an absence
certificate whose content the checker re-derives from the export. Episodes
exported before those fields existed are counted as "not checkable" rather
than passed in silence.

The engine arm of the budget sweep is not recomputed: those rows are the
engine's measured output and are read from the shipped artifact (see
`baselines/README.md`). Everything else in the table below runs here.

Exit status is non-zero if anything differs.

Copyright (c) 2026 Kiran Nayudu. Apache-2.0."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
import tempfile
import time
from pathlib import Path

from unknown_goals.checker import check_export, read_export, summary_line

# ---------------------------------------------------------------- comparison

# Verbatim from scripts/reproduce.py in the engine repository (Kiran Nayudu,
# 2026), so that the kit and the engine call two runs equal for exactly the
# same reasons: results compare, clocks and machine identity do not.
VOLATILE = {"elapsed_s", "timestamp", "wall_s", "seconds", "elapsed",
            "date", "machine", "system_load_during_pass", "load_avg_start",
            "load_avg_end", "tag", "cpu_count"}


def strip(x):
    """Drop timing/machine fields so two runs compare on results only."""
    if isinstance(x, dict):
        return {k: strip(v) for k, v in x.items() if k not in VOLATILE}
    if isinstance(x, list):
        return [strip(v) for v in x]
    return x


def first_difference(a, b, path: str = "") -> str | None:
    """Where two stripped structures first disagree, in dotted notation."""
    if type(a) is not type(b) and not (isinstance(a, (int, float))
                                       and isinstance(b, (int, float))):
        return f"{path or '<root>'}: {type(a).__name__} vs {type(b).__name__}"
    if isinstance(a, dict):
        for k in a:
            if k not in b:
                return f"{path}.{k}: only in the regenerated file"
        for k in b:
            if k not in a:
                return f"{path}.{k}: only in the shipped artifact"
        for k in a:
            d = first_difference(a[k], b[k], f"{path}.{k}")
            if d:
                return d
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: {len(a)} rows vs {len(b)} rows"
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_difference(x, y, f"{path}[{i}]")
            if d:
                return d
        return None
    if a != b:
        return f"{path or '<root>'}: {a!r} vs {b!r}"
    return None


@contextlib.contextmanager
def chdir(path: Path):
    old = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


def kit_root(start: Path | None = None) -> Path:
    """The kit tree: the nearest directory at or above `start` that holds
    `data/artifacts`."""
    here = (start or Path.cwd()).resolve()
    for cand in [here, *here.parents]:
        if (cand / "data" / "artifacts").is_dir():
            return cand
    # installed, run from elsewhere: fall back to the package's own parent
    pkg_parent = Path(__file__).resolve().parent.parent
    if (pkg_parent / "data" / "artifacts").is_dir():
        return pkg_parent
    raise SystemExit(
        "cannot find the kit tree (a directory containing data/artifacts). "
        "Run this from the kit checkout, or pass --kit-root DIR.")


# ------------------------------------------------------------------ baselines

def _run_module(entry, argv: list[str], cwd: Path, verbose: bool) -> None:
    """Run a baseline's own `main()` exactly as its command line would.

    The baselines parse `sys.argv`, so the invocation is spelled there and
    nothing about the script is changed to make it callable from here."""
    buf = io.StringIO()
    saved = sys.argv
    sys.argv = [entry.__module__, *argv]
    try:
        with chdir(cwd):
            if verbose:
                entry()
            else:
                with contextlib.redirect_stdout(buf):
                    entry()
    finally:
        sys.argv = saved


def regenerate(name: str, shipped: Path, entry, argv, cwd: Path,
               produced: Path, verbose: bool) -> dict:
    t0 = time.time()
    row = {"suite": name, "artifact": shipped.name}
    if not shipped.exists():
        row["status"] = "shipped artifact absent"
        row["ok"] = False
        return row
    try:
        _run_module(entry, argv, cwd, verbose)
    except Exception as exc:                       # noqa: BLE001
        row["status"] = f"baseline raised {type(exc).__name__}: {exc}"
        row["ok"] = False
        row["seconds"] = round(time.time() - t0, 1)
        return row
    if not produced.exists():
        row["status"] = "baseline produced no file"
        row["ok"] = False
        row["seconds"] = round(time.time() - t0, 1)
        return row
    got = strip(json.loads(produced.read_text(encoding="utf-8")))
    want = strip(json.loads(shipped.read_text(encoding="utf-8")))
    diff = first_difference(got, want)
    row["ok"] = diff is None
    row["status"] = "IDENTICAL" if diff is None else f"DIFFERS at {diff}"
    row["seconds"] = round(time.time() - t0, 1)
    return row


def baseline_rows(root: Path, quick: bool, verbose: bool) -> list[dict]:
    from baselines import belief_planner, budget_sweep, scripted_baselines

    art = root / "data" / "artifacts"
    rows: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="unknown-goals-verify-") as td:
        tmp = Path(td)
        (tmp / "data" / "artifacts").mkdir(parents=True, exist_ok=True)

        rows.append(regenerate(
            "scripted baselines (12 seeds x L2-6)",
            art / "scripted_baselines_warehouse.json",
            scripted_baselines.main, [], tmp,
            tmp / "data" / "artifacts" / "scripted_baselines_warehouse.json",
            verbose))

        out = tmp / "belief_planner_sweep_12.json"
        rows.append(regenerate(
            "exact belief-space planner (12 seeds)",
            art / "belief_planner_sweep_12.json",
            belief_planner.main, ["--seeds", "12", "--out", str(out)], tmp,
            out, verbose))

        out = tmp / "budget_sweep.json"
        rows.append(regenerate(
            "budget sweep, scripted arms (12 seeds)",
            art / "budget_sweep.json",
            budget_sweep.main, ["--out", str(out)], tmp, out, verbose))

        if not quick:
            shipped = art / "belief_planner_sweep.json"
            if shipped.exists():
                out = tmp / "belief_planner_sweep.json"
                rows.append(regenerate(
                    "exact belief-space planner (100 seeds)", shipped,
                    belief_planner.main,
                    ["--seeds", "100", "--out", str(out)], tmp, out, verbose))
            shipped = art / "budget_sweep_100.json"
            if shipped.exists():
                out = tmp / "budget_sweep_100.json"
                rows.append(regenerate(
                    "budget sweep, scripted arms (100 seeds)", shipped,
                    budget_sweep.main,
                    ["--seeds", "100", "--out", str(out)], tmp, out, verbose))
    return rows


# -------------------------------------------------------------------- proofs

def _proof_fractions(obj, path: tuple[str, ...] = ()) -> list[tuple[tuple, float]]:
    """Every `proofs` fraction an artifact records, with where it sits."""
    found: list[tuple[tuple, float]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "proofs" and isinstance(v, (int, float)):
                found.append((path, float(v)))
            else:
                found += _proof_fractions(v, path + (str(k),))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found += _proof_fractions(v, path + (str(i),))
    return found


def _group_for(episodes: list[dict], owner: str) -> list[dict]:
    """The export rows a `proofs` fraction covers.

    An artifact records its proof fraction under the name of the suite that
    produced it (`T1_warehouse`), and the export rows carry that suite in
    their episode key (`test=T1`). A row belongs to the fraction when one of
    its key values is that name or the name's first underscore-separated
    part."""
    head = owner.split("_")[0]
    out = []
    for ep in episodes:
        vals = {str(v) for v in ep.get("episode_key", {}).values()}
        if owner in vals or head in vals:
            out.append(ep)
    return out


def regeneration_verdicts(exports_dir: Path) -> dict[str, str]:
    """What `data/exports/INDEX.json` records about each artifact: whether
    the shipped build still reproduces it from the recorded command.

    An artifact marked DIFFERS is a historical record -- what was measured
    when the paper's table was written -- and the export is the current
    build's rerun of the same command. Its proof-validity fraction is
    therefore not expected to equal the artifact's, and the equality is
    asserted only where the two agree in the first place."""
    index = exports_dir / "INDEX.json"
    if not index.exists():
        return {}
    try:
        data = json.loads(index.read_text(encoding="utf-8"))
    except Exception:                              # noqa: BLE001
        return {}
    return {f["file"]: f.get("regeneration", "?") for f in data.get("files", [])}


def export_rows(root: Path, exports_dir: Path) -> list[dict]:
    rows: list[dict] = []
    verdicts = regeneration_verdicts(exports_dir)
    files = sorted(exports_dir.glob("*.jsonl.gz")) + \
        sorted(exports_dir.glob("*.jsonl"))
    if not files:
        return [{"suite": "ledger exports", "artifact": str(exports_dir),
                 "status": "no export files found", "ok": False}]
    for f in files:
        t0 = time.time()
        try:
            summary = check_export(f)
        except Exception as exc:                   # noqa: BLE001
            rows.append({"suite": f"proofs: {f.name}", "artifact": f.name,
                         "status": f"unreadable: {type(exc).__name__}: {exc}",
                         "ok": False})
            continue
        ok = not summary["errors"]
        status = (f"{summary['valid']}/{summary['total']} proofs replay "
                  f"over {summary['n_episodes']} episodes")
        if summary["errors"]:
            status = (f"{len(summary['errors'])} INVALID; first: "
                      f"{summary['errors'][0]}")
        rows.append({"suite": f"proofs: {f.name}", "artifact": summary["artifact"]
                     or f.name, "status": status, "ok": ok,
                     "seconds": round(time.time() - t0, 1)})
        # what the episodes committed to, beside how they got there
        rows.append({"suite": f"commitments: {f.name}",
                     "artifact": summary["artifact"] or f.name,
                     "status": summary_line(summary),
                     "ok": (summary["commitments_failed"] == 0
                            and summary["certificates_failed"] == 0)})

        # the artifact's own `proofs` fraction, where it records one
        art_rel = summary["artifact"]
        art_path = (root / art_rel) if art_rel else None
        if not art_path or not art_path.exists():
            continue
        try:
            artifact = json.loads(art_path.read_text(encoding="utf-8"))
        except Exception:                          # noqa: BLE001
            continue
        fractions = _proof_fractions(artifact)
        if not fractions:
            continue
        verdict = verdicts.get(f.name, "IDENTICAL")
        if verdict != "IDENTICAL":
            rows.append({"suite": f"proofs fraction: {f.name}",
                         "artifact": art_rel, "ok": True,
                         "status": f"not compared: the artifact does not "
                                   f"regenerate on this build ({verdict}); "
                                   f"it is the historical record and the "
                                   f"export is this build"})
            continue
        episodes = list(read_export(f))
        for path, want in fractions:
            owner = path[-1] if path else art_path.stem
            group = episodes if len(fractions) == 1 else _group_for(episodes, owner)
            label = ".".join(path) or art_path.stem
            if not group:
                rows.append({"suite": f"proofs fraction: {label}",
                             "artifact": art_rel,
                             "status": "no export rows match this suite",
                             "ok": False})
                continue
            valid = total = 0
            from unknown_goals.checker import check_episode
            for ep in group:
                v, t, _ = check_episode(ep)
                valid += v
                total += t
            got = (valid / total) if total else 1.0
            same = got == want
            rows.append({"suite": f"proofs fraction: {label}",
                         "artifact": art_rel,
                         "status": (f"artifact {want} == checker {got}" if same
                                    else f"artifact {want} != checker {got} "
                                         f"({valid}/{total} over "
                                         f"{len(group)} episodes)"),
                         "ok": same})
    return rows


# ---------------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="unknown-goals-verify",
        description="Regenerate every baseline and re-validate every proof.")
    ap.add_argument("--quick", action="store_true",
                    help="skip the 100-seed planner and budget suites")
    ap.add_argument("--kit-root", default=None,
                    help="the kit checkout (default: found from the cwd)")
    ap.add_argument("--exports", default=None,
                    help="directory of ledger exports (default: "
                         "<kit-root>/data/exports)")
    ap.add_argument("--skip-baselines", action="store_true")
    ap.add_argument("--skip-exports", action="store_true")
    ap.add_argument("--verbose", action="store_true",
                    help="let the baselines print their own progress")
    args = ap.parse_args(argv)

    root = Path(args.kit_root).resolve() if args.kit_root else kit_root()
    exports_dir = Path(args.exports).resolve() if args.exports \
        else root / "data" / "exports"
    print(f"kit    {root}")
    print(f"python {sys.version.split()[0]}")
    try:
        import robot_mind  # noqa: F401
        print("engine IMPORTABLE in this environment -- the kit's own result "
              "is still computed only from the kit, but a clean check runs "
              "where the engine is absent.")
    except ImportError:
        print("engine not importable (as it should be)")
    print()

    rows: list[dict] = []
    if not args.skip_baselines:
        rows += baseline_rows(root, args.quick, args.verbose)
    if not args.skip_exports:
        rows += export_rows(root, exports_dir)

    width = max([len(r["suite"]) for r in rows] + [20])
    print(f"| {'check'.ljust(width)} | {'result':<8} | detail")
    print(f"|{'-' * (width + 2)}|{'-' * 10}|{'-' * 40}")
    for r in rows:
        mark = "pass" if r.get("ok") else "FAIL"
        secs = f" [{r['seconds']}s]" if r.get("seconds") is not None else ""
        print(f"| {r['suite'].ljust(width)} | {mark:<8} | {r['status']}{secs}")
    failed = [r for r in rows if not r.get("ok")]
    print()
    if failed:
        print(f"{len(failed)} of {len(rows)} checks FAILED.")
        return 1
    print(f"all {len(rows)} checks pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
