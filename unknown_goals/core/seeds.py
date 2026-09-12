"""Deterministic randomness. One integer seed reproduces everything.

Every consumer gets a NAMED substream derived via SHA-256 (never Python's
salted hash()), so adding a new consumer never shifts an existing one."""

import hashlib
import random


def substream(seed: int, name: str) -> random.Random:
    digest = hashlib.sha256(f"{seed}:{name}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


class SeedManager:
    def __init__(self, seed: int) -> None:
        self.seed = seed

    def stream(self, name: str) -> random.Random:
        return substream(self.seed, name)
