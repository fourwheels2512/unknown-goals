"""The baselines the engine is measured against.

Every policy here runs under the identical episode contract: the same
generated scenario, the same executor and sensor model, the same action
budget, the same success rule (a LOCATED_AT claim about the target at
confidence >= 0.9), and the same hidden-truth grading.

  scripted_baselines   sweep, random, last-seen, and a plain Bayesian filter
  belief_planner       the exact finite-horizon belief-space (POMDP) planner
  budget_sweep         all of them across action budgets 2..8
  head_to_head         an LLM agent on the same scenarios

Copyright (c) 2026 Kiran Nayudu. Apache-2.0."""
