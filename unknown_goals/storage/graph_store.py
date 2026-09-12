"""Temporal belief graph: a NetworkX view over ledger claims.

The graph is a VIEW — the ledger stays canonical. Only claims whose effective
status is trusted evidence (OBSERVED/REPORTED/DERIVED) become edges; rejected,
superseded, and contradicted claims are excluded, and hypotheses never enter.

The view is maintained INCREMENTALLY (view-maintenance follow-up, step one):
`refresh()` integrates only the claims and status events appended since the
last refresh, using two watermarks — a cursor into the append-only claim
cache and the status_events autoincrement id. `rebuild()` remains the
from-scratch path; tests/test_ivm_equivalence.py holds refresh() to being
indistinguishable from it after every reasoning step.
"""

from __future__ import annotations

import networkx as nx

from unknown_goals.core.enums import EpistemicStatus, Predicate
from unknown_goals.models.records import Claim
from unknown_goals.storage.ledger import Ledger

TRUSTED = {EpistemicStatus.OBSERVED, EpistemicStatus.REPORTED, EpistemicStatus.DERIVED}


class BeliefGraph:
    def __init__(self, ledger: Ledger) -> None:
        self.ledger = ledger
        self.graph = nx.MultiDiGraph()
        self._claim_cursor = 0
        self._status_seq = 0
        self._entity_rev = -1        # force the first entity sync
        self._entity_ids: set[str] = set()
        self.rebuild()

    def rebuild(self) -> None:
        g = nx.MultiDiGraph()
        self._entity_ids = set()
        for entity in self.ledger.entities():
            g.add_node(entity.entity_id, entity_type=entity.entity_type.value,
                       name=entity.name)
            self._entity_ids.add(entity.entity_id)
        # one bulk status lookup for the whole ledger instead of a SQL round
        # trip per claim
        statuses = self.ledger.effective_statuses()
        for claim in self.ledger.claims():
            if statuses.get(claim.claim_id, claim.status) not in TRUSTED:
                continue
            self._add_edge(g, claim)
        self.graph = g
        self._claim_cursor = self.ledger.claim_count()
        self._status_seq = self.ledger.status_event_seq()
        self._entity_rev = self.ledger.entity_rev()

    def refresh(self) -> None:
        """Integrate what changed since the last rebuild/refresh — O(changes),
        not O(lifetime ledger). End state is identical to rebuild()."""
        if self._entity_rev != self.ledger.entity_rev():
            for entity in self.ledger.entities():
                self.graph.add_node(entity.entity_id,
                                    entity_type=entity.entity_type.value,
                                    name=entity.name)
                self._entity_ids.add(entity.entity_id)
            self._entity_rev = self.ledger.entity_rev()

        new_claims = self.ledger.claims_appended_since(self._claim_cursor)
        for claim in new_claims:
            # any status event for a claim this new is also newer than the
            # status watermark, so the event pass below corrects the edge
            if claim.status in TRUSTED:
                self._add_edge(self.graph, claim)
        self._claim_cursor += len(new_claims)

        for event_id, claim_id, new_status in \
                self.ledger.status_events_since(self._status_seq):
            self._status_seq = event_id
            claim = self.ledger.get_claim(claim_id)
            if claim is None:      # cannot happen (ledger enforces existence)
                continue
            has_edge = self.graph.has_edge(claim.subject, claim.obj, key=claim_id)
            if new_status in TRUSTED and not has_edge:
                self._add_edge(self.graph, claim)
            elif new_status not in TRUSTED and has_edge:
                self.graph.remove_edge(claim.subject, claim.obj, key=claim_id)
                # a non-entity endpoint exists only while an edge references
                # it — exactly what a from-scratch rebuild would produce
                for node in (claim.subject, claim.obj):
                    if node not in self._entity_ids and node in self.graph \
                            and self.graph.degree(node) == 0:
                        self.graph.remove_node(node)

    @staticmethod
    def _add_edge(g: nx.MultiDiGraph, claim: Claim) -> None:
        g.add_edge(
            claim.subject, claim.obj, key=claim.claim_id,
            predicate=claim.predicate.value,
            t_start=claim.event_time_start, t_end=claim.event_time_end,
            confidence=claim.confidence, source=claim.source_id,
        )

    def edges_from(self, subject: str, predicate: Predicate | None = None) -> list[Claim]:
        out: list[Claim] = []
        if subject not in self.graph:
            return out
        for _, _, key in sorted(self.graph.out_edges(subject, keys=True),
                                key=lambda t: t[2]):
            claim = self.ledger.get_claim(key)
            if claim and (predicate is None or claim.predicate == predicate):
                out.append(claim)
        return out

    def edges_to(self, obj: str, predicate: Predicate | None = None) -> list[Claim]:
        out: list[Claim] = []
        if obj not in self.graph:
            return out
        for _, _, key in sorted(self.graph.in_edges(obj, keys=True),
                                key=lambda t: t[2]):
            claim = self.ledger.get_claim(key)
            if claim and (predicate is None or claim.predicate == predicate):
                out.append(claim)
        return out
