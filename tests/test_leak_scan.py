"""The kit does not carry anything the release withholds.

The authoritative gate is `scripts/export_kit.py` in the engine
repository, which holds the withheld terms in clear and scans the whole
build before it finishes. This test is the kit's own self-check: it keeps a
later edit of the kit from reintroducing one of those terms, and it keeps
the engine's module name out of the kit's code.

Copyright (c) 2026 Kiran Nayudu. Apache-2.0."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from conftest import identifier_hits, leak_hashes, phrase_hits

# The kit's own source and documents. The ledger exports have their own
# contract test (test_exports.py), which checks the data's shape as well as
# its words.
SOURCE_DIRS = ["unknown_goals", "baselines", "tests", "ros2"]
SOURCE_FILES = ["pyproject.toml", "README.md", "LICENSE", "LICENSE-DATA",
                "LICENSE-DEMO"]
DOC_DIRS = ["docs"]
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


def test_the_hash_list_shipped():
    h = leak_hashes()
    assert h["words"], "no withheld identifiers to check against"
    assert h["fields"], "no withheld configuration fields to check against"
    assert h["phrases"], "no withheld phrases to check against"
    assert h["phrase_max_words"] >= 1
    assert all(len(d) == 64 for d in h["words"] + h["fields"] + h["phrases"])


def test_no_withheld_identifier_in_the_kit_source(kit: Path):
    h = leak_hashes()
    words, fields = set(h["words"]), set(h["fields"])
    bad: list[str] = []
    for path in _files(kit, SOURCE_DIRS, SOURCE_FILES):
        hits = identifier_hits(_read(path), words, fields)
        bad += [f"{path.relative_to(kit).as_posix()}: {h}" for h in sorted(hits)]
    assert not bad, "withheld identifiers in the kit source:\n" + "\n".join(bad)


def test_no_withheld_phrase_in_the_kit_source_or_documents(kit: Path):
    h = leak_hashes()
    phrases, n = set(h["phrases"]), int(h["phrase_max_words"])
    bad: list[str] = []
    for path in _files(kit, SOURCE_DIRS + DOC_DIRS, SOURCE_FILES):
        hits = phrase_hits(_read(path), phrases, n)
        bad += [f"{path.relative_to(kit).as_posix()}: {x!r}"
                for x in sorted(hits)]
    assert not bad, "withheld phrases in the kit:\n" + "\n".join(bad)


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
