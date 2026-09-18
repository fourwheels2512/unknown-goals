"""The engine's module name is not in the kit's code.

The gate that keeps the withheld computation out of the kit is
`scripts/export_kit.py` in the engine repository: it holds the withheld
terms in clear and scans the whole build before anything is published.
The kit itself carries no form of that list. The first release shipped
the terms as SHA-256 digests for a self-test here; the digests were
recovered by hashing the kit's own prose, so they withheld nothing, and
the file and the self-test are gone. What this file still checks is the
one thing the kit can check about itself without a list: that no kit code
names the engine's module, except the two files whose purpose is to show
it is absent.

Copyright (c) 2026 Kiran Nayudu. Apache-2.0."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

TEXT_SUFFIXES = {".py", ".md", ".toml", ".txt", ".json", ".srv", ".action",
                 ".msg", ".xml", ".cfg", ".yaml", ".yml", ""}

ENGINE_MODULE = re.compile(r"\brobot_mind\b")


def _files(kit: Path, dirs, files) -> list[Path]:
    out: list[Path] = []
    for d in dirs:
        root = kit / d
        if root.is_dir():
            out += [p for p in sorted(root.rglob("*"))
                    if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES
                    and "__pycache__" not in p.parts]
    out += [kit / f for f in files if (kit / f).is_file()]
    return out


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""


def test_the_kit_ships_no_list_of_withheld_names(kit: Path):
    """Neither in clear nor as digests: the first release's hash file was
    reversible from the kit's own vocabulary."""
    data = kit / "unknown_goals" / "data"
    assert not (data / "leak_hashes.json").exists(), \
        "the withheld-name digest file is back in the kit"
    for path in sorted(data.glob("*.json")):
        text = _read(path).lower()
        assert "withheld" not in text and "leak" not in text, \
            f"{path.name} describes a withheld-name list"


# Two files name the engine's module on purpose, in order to establish that
# it is ABSENT: the parity test imports it and skips when it is missing, and
# the verifier reports whether it is importable so a clean-room run is
# visible in the output. Nothing else in the kit may name it.
NAMES_THE_ENGINE_ON_PURPOSE = {
    "tests/test_generator_parity.py",
    "unknown_goals/verify.py",
}


def test_the_engine_module_name_is_not_in_the_kit_code(kit: Path):
    """`robot_mind_msgs` is the ROS 2 interface package and keeps its name;
    the engine's own module name must not appear in any kit code."""
    bad: list[str] = []
    for path in _files(kit, ["unknown_goals", "baselines", "tests"],
                       ["pyproject.toml"]):
        rel = path.relative_to(kit).as_posix()
        if rel in NAMES_THE_ENGINE_ON_PURPOSE:
            continue
        for i, line in enumerate(_read(path).splitlines(), 1):
            if ENGINE_MODULE.search(line):
                bad.append(f"{rel}:{i}: {line.strip()}")
    assert not bad, "the engine's module name is in kit code:\n" + "\n".join(bad)


def test_the_files_that_name_the_engine_only_try_to_import_it(kit: Path):
    """The exemption above is narrow: each of those two files may name the
    engine only in an import that is expected to fail."""
    for rel in sorted(NAMES_THE_ENGINE_ON_PURPOSE):
        path = kit / rel
        if not path.exists():
            continue
        for i, line in enumerate(_read(path).splitlines(), 1):
            if not ENGINE_MODULE.search(line):
                continue
            assert "import" in line or line.strip().startswith("#") \
                or '"' in line or "'" in line, \
                f"{rel}:{i} names the engine outside an import: {line.strip()}"


def test_the_belief_breakdown_is_not_in_the_records_model(kit: Path):
    """Every number the engine displays has a breakdown behind it. The
    breakdown is the belief arithmetic, and it is not in this release."""
    records = kit / "unknown_goals" / "models" / "records.py"
    if not records.exists():
        pytest.skip("records.py not in this tree")
    text = _read(records)
    for banned in ("BeliefBreakdown", "breakdown", "path_confidence",
                   "contradiction_penalty", "normalization_denominator",
                   "raw_score", "age_weights"):
        assert banned not in text, f"{banned!r} is in records.py"
