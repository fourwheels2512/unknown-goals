"""Unknown Goals benchmark kit.

The scenario generator, the executor and episode contract, every scripted
and belief-space baseline, the independent proof checker, the decision
replayer, and the one-command verifier for the numbers the paper reports.

The reasoning engine itself is not in this package. The kit checks the
engine's committed work: it re-validates every proof path in the shipped
ledger exports with no engine code, and it regenerates every baseline the
engine is compared against.

Copyright (c) 2026 Kiran Nayudu. Apache-2.0."""

__version__ = "0.5.0"
