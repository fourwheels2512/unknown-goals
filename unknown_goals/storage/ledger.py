"""Append-only evidence ledger backed by SQLite.
Copyright (c) 2026 Kiran Nayudu.

Invariants enforced here:
- Claims are never updated or deleted. There is no UPDATE path at all.
- Status changes append StatusEvent rows; a claim's effective status is the
  latest event, with full history preserved.
- Both clocks are stored: event_time (world) and ingested_at (system).

Nothing is fetched or delivered until what was found is verified here.
"""

from __future__ import annotations

import json
import sqlite3
from bisect import insort

from unknown_goals.core.enums import EntityType, EpistemicStatus, Predicate
from unknown_goals.models.records import Claim, Entity, EpisodeRecord, Proof, Rule


def _claim_order(c: Claim) -> tuple[int, str]:
    """The ledger's canonical read order: ORDER BY ingested_at, claim_id."""
    return (c.ingested_at, c.claim_id)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS entities (
    entity_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    name TEXT NOT NULL,
    aliases TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    obj TEXT NOT NULL,
    event_time_start INTEGER NOT NULL,
    event_time_end INTEGER NOT NULL,
    ingested_at INTEGER NOT NULL,
    source_id TEXT NOT NULL,
    confidence REAL NOT NULL,
    status TEXT NOT NULL,
    proof TEXT,
    provenance TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS status_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT NOT NULL,
    new_status TEXT NOT NULL,
    reason TEXT NOT NULL,
    ingested_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS rules (
    rule_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS episodes (
    episode_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_claims_subject ON claims(subject);
CREATE INDEX IF NOT EXISTS idx_claims_pred ON claims(predicate);
CREATE INDEX IF NOT EXISTS idx_status_claim ON status_events(claim_id, id);
"""


class Ledger:
    def __init__(self, path: str = ":memory:") -> None:
        self.conn = sqlite3.connect(path)
        self.conn.executescript(_SCHEMA)
        self.conn.commit()
        # Claims are append-only and never mutated after ingestion, so their
        # deserialized form is cached in memory: reads serve from the cache
        # instead of re-parsing every row from SQLite on each call. This is
        # what lets a long-lived, memory-heavy mind reason at a steady speed
        # rather than slowing as its ledger grows (the hot reasoning loop
        # calls claims()/get_claim() hundreds of times per decision). The DB
        # remains the durable source of truth; the cache is rebuilt from it
        # whenever a ledger is opened (including crash recovery).
        self._claim_cache: list[Claim] = []      # append order (cursor views)
        self._claim_by_id: dict[str, Claim] = {}
        # Secondary indexes over the cache, maintained on append (incremental
        # view maintenance, step one): filtered claims() calls — the hot
        # reasoning loop issues hundreds per decision — walk only the claims
        # that can match instead of the whole lifetime ledger. Step two: every
        # index (and the all-claims view) is kept in the canonical read order
        # at insertion, so claims() never sorts — a filtered read is one
        # ordered walk over the narrowest matching index.
        self._sorted: list[Claim] = []
        self._by_subject: dict[str, list[Claim]] = {}
        self._by_predicate: dict[Predicate, list[Claim]] = {}
        self._by_obj: dict[str, list[Claim]] = {}
        # "What do we know about THIS object under THIS predicate" is by far the
        # commonest question the reasoner asks (every hypothesis hop, every
        # absence check). Answering it from the single-column indexes means
        # walking one whole column to keep a handful of rows, so it gets its own
        # composite index and the answer becomes a direct lookup.
        self._by_subj_pred: dict[tuple[str, Predicate], list[Claim]] = {}
        # Entities are tiny, immutable once registered (INSERT OR IGNORE), and
        # read hundreds of thousands of times per simulated day by the drives
        # and the reasoner; they are cached like claims (the table stays the
        # durable truth and the cache is rebuilt from it on open).
        self._entities: dict[str, Entity] = {}
        # bumped on add_entity so views can skip entity resync when unchanged
        self._entity_rev: int = 0
        # Effective status of every claim (latest status event wins, else the
        # claim's base status), maintained on append — hot paths that classify
        # the ledger every step stop re-scanning two SQL tables. The tables
        # remain the durable truth; this map is rebuilt from them on open.
        self._effective: dict[str, EpistemicStatus] = {}
        self._load_claim_cache()

    def _load_claim_cache(self) -> None:
        self._claim_cache = [
            self._row_to_claim(r)
            for r in self.conn.execute(
                "SELECT * FROM claims ORDER BY ingested_at, claim_id")
        ]
        self._claim_by_id = {c.claim_id: c for c in self._claim_cache}
        self._sorted = []
        self._by_subject, self._by_predicate, self._by_obj = {}, {}, {}
        self._by_subj_pred = {}
        for c in self._claim_cache:
            self._index_claim(c)
        self._entities = {
            r[0]: Entity(entity_id=r[0], entity_type=EntityType(r[1]), name=r[2],
                         aliases=json.loads(r[3]))
            for r in self.conn.execute(
                "SELECT entity_id, entity_type, name, aliases FROM entities")
        }
        self._effective = {c.claim_id: c.status for c in self._claim_cache}
        for cid, new_status in self.conn.execute(
            "SELECT claim_id, new_status FROM status_events WHERE id IN "
            "(SELECT MAX(id) FROM status_events GROUP BY claim_id)"
        ):
            self._effective[cid] = EpistemicStatus(new_status)

    def _index_claim(self, claim: Claim) -> None:
        # insertion keeps each list in canonical order; the common case (a
        # newer ingestion) lands at the end in O(log n)
        insort(self._sorted, claim, key=_claim_order)
        insort(self._by_subject.setdefault(claim.subject, []), claim, key=_claim_order)
        insort(self._by_predicate.setdefault(claim.predicate, []), claim, key=_claim_order)
        insort(self._by_obj.setdefault(claim.obj, []), claim, key=_claim_order)
        insort(self._by_subj_pred.setdefault((claim.subject, claim.predicate), []),
               claim, key=_claim_order)

    # -- entities -----------------------------------------------------------
    def add_entity(self, entity: Entity) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO entities VALUES (?,?,?,?)",
            (entity.entity_id, entity.entity_type.value, entity.name,
             json.dumps(entity.aliases)),
        )
        self.conn.commit()
        # OR IGNORE semantics: the first registration of an id stands
        if entity.entity_id not in self._entities:
            self._entities[entity.entity_id] = entity.model_copy(deep=True)
        self._entity_rev += 1

    def get_entity(self, entity_id: str) -> Entity | None:
        # served from the cache; same row the SELECT would return
        return self._entities.get(entity_id)

    def entities(self) -> list[Entity]:
        # same result and ordering as SELECT ... ORDER BY entity_id
        return [self._entities[k] for k in sorted(self._entities)]

    # -- claims (append-only) ----------------------------------------------
    def append_claim(self, claim: Claim) -> str:
        """Append a claim. Raises on ontology violation or duplicate id.
        There is deliberately no update_claim method."""
        subj = self.get_entity(claim.subject)
        obje = self.get_entity(claim.obj)
        if subj is not None and obje is not None:
            if not claim.validate_against_ontology(subj.entity_type, obje.entity_type):
                raise ValueError(
                    f"ontology violation: {subj.entity_type} "
                    f"-{claim.predicate}-> {obje.entity_type}"
                )
        if claim.status == EpistemicStatus.DERIVED and claim.proof is None:
            raise ValueError("DERIVED claims must carry a proof")
        self.conn.execute(
            "INSERT INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (claim.claim_id, claim.subject, claim.predicate.value, claim.obj,
             claim.event_time_start, claim.event_time_end, claim.ingested_at,
             claim.source_id, claim.confidence, claim.status.value,
             claim.proof.model_dump_json() if claim.proof else None,
             json.dumps(claim.provenance, sort_keys=True)),
        )
        self.conn.commit()
        self._claim_cache.append(claim)
        self._claim_by_id[claim.claim_id] = claim
        self._index_claim(claim)
        self._effective[claim.claim_id] = claim.status
        return claim.claim_id

    def _row_to_claim(self, r: tuple) -> Claim:
        return Claim(
            claim_id=r[0], subject=r[1], predicate=Predicate(r[2]), obj=r[3],
            event_time_start=r[4], event_time_end=r[5], ingested_at=r[6],
            source_id=r[7], confidence=r[8], status=EpistemicStatus(r[9]),
            proof=Proof.model_validate_json(r[10]) if r[10] else None,
            provenance=json.loads(r[11]),
        )

    def get_claim(self, claim_id: str) -> Claim | None:
        return self._claim_by_id.get(claim_id)

    def claims(
        self,
        subject: str | None = None,
        predicate: Predicate | None = None,
        obj: str | None = None,
    ) -> list[Claim]:
        # served from the in-memory cache (append-only, never mutated); same
        # result and ordering as the SQL query it replaces:
        # WHERE [filters] ORDER BY ingested_at, claim_id
        # A filtered call walks the narrowest matching index, not the whole
        # lifetime cache — required for per-decision cost that does not grow
        # with everything the mind has ever seen. Every index is already in
        # canonical order (maintained at insertion), so no sort happens here.
        pools: list[list[Claim]] = []
        if subject is not None and predicate is not None:
            # the composite index answers this exactly; it is a subset of both
            # single-column pools, so it is never the wider choice
            pools.append(self._by_subj_pred.get((subject, predicate), []))
        elif subject is not None:
            pools.append(self._by_subject.get(subject, []))
        elif predicate is not None:
            pools.append(self._by_predicate.get(predicate, []))
        if obj is not None:
            pools.append(self._by_obj.get(obj, []))
        candidates = min(pools, key=len) if pools else self._sorted
        if obj is None or (subject is None and predicate is None):
            # the chosen pool is keyed on exactly the filters asked for, so
            # every candidate already matches and the per-row re-test is dead
            # work. Only a mixed query (obj AND subject/predicate) can land on
            # a pool that covers just part of the filter and must be re-tested.
            return list(candidates)
        return [
            c for c in candidates
            if (subject is None or c.subject == subject)
            and (predicate is None or c.predicate == predicate)
            and (obj is None or c.obj == obj)
        ]

    def latest_claim_about(
        self,
        obj: str,
        source_ids: tuple[str, ...] | frozenset[str] | None = None,
        statuses: set[EpistemicStatus] | frozenset[EpistemicStatus] | None = None,
    ) -> Claim | None:
        """The newest claim with this obj, in canonical order, optionally
        restricted to source ids and to effective statuses. None if none match.

        The obj index is already in canonical (ingested_at, claim_id) order, so
        the last matching entry IS the newest: this walks that index backwards
        and stops at the first match instead of scanning the whole lifetime of
        the ledger to take a max. Callers that want "how long ago did we last
        see room X" pay for room X's history, never for everything the mind has
        ever recorded.
        """
        for c in reversed(self._by_obj.get(obj, [])):
            if source_ids is not None and c.source_id not in source_ids:
                continue
            if statuses is not None and self._effective[c.claim_id] not in statuses:
                continue
            return c
        return None

    def claim_count(self) -> int:
        return len(self._claim_cache)

    def claims_appended_since(self, index: int) -> list[Claim]:
        """Claims appended after the first `index` ones, in append order.
        The cache is append-only, so an integer cursor is a stable watermark."""
        return self._claim_cache[index:]

    def entity_rev(self) -> int:
        return self._entity_rev

    # -- status transitions (append-only) ----------------------------------
    def append_status_event(self, claim_id: str, new_status: EpistemicStatus,
                            reason: str, ingested_at: int) -> None:
        if self.get_claim(claim_id) is None:
            raise ValueError(f"unknown claim {claim_id}")
        self.conn.execute(
            "INSERT INTO status_events (claim_id, new_status, reason, ingested_at) "
            "VALUES (?,?,?,?)",
            (claim_id, new_status.value, reason, ingested_at),
        )
        self.conn.commit()
        self._effective[claim_id] = new_status

    def effective_status(self, claim_id: str) -> EpistemicStatus:
        if claim_id not in self._claim_by_id:
            raise ValueError(f"unknown claim {claim_id}")
        return self._effective[claim_id]

    def effective_statuses(self) -> dict[str, EpistemicStatus]:
        """Effective status of EVERY claim, served from the append-maintained
        map instead of re-scanning two SQL tables per call. Same semantics:
        the latest status event wins, else the claim's base status. Returns a
        copy so callers cannot corrupt the view."""
        return dict(self._effective)

    def status_event_seq(self) -> int:
        """Highest status-event id so far (0 when none) — a watermark for
        views that integrate status changes incrementally."""
        row = self.conn.execute(
            "SELECT COALESCE(MAX(id), 0) FROM status_events").fetchone()
        return int(row[0])

    def status_events_since(self, after_id: int) -> list[tuple[int, str, EpistemicStatus]]:
        """(id, claim_id, new_status) for every status event with id > after_id,
        in append order."""
        rows = self.conn.execute(
            "SELECT id, claim_id, new_status FROM status_events "
            "WHERE id > ? ORDER BY id",
            (after_id,),
        ).fetchall()
        return [(r[0], r[1], EpistemicStatus(r[2])) for r in rows]

    def status_history(self, claim_id: str) -> list[tuple[EpistemicStatus, str, int]]:
        rows = self.conn.execute(
            "SELECT new_status, reason, ingested_at FROM status_events "
            "WHERE claim_id=? ORDER BY id",
            (claim_id,),
        ).fetchall()
        return [(EpistemicStatus(r[0]), r[1], r[2]) for r in rows]

    # -- rules & episodes ---------------------------------------------------
    def upsert_rule(self, rule: Rule) -> None:
        """Rules are versioned artifacts, not evidence; replacement is allowed
        and each version's metrics live in the payload."""
        self.conn.execute(
            "INSERT OR REPLACE INTO rules VALUES (?,?)",
            (rule.rule_id, rule.model_dump_json()),
        )
        self.conn.commit()

    def get_rule(self, rule_id: str) -> Rule | None:
        row = self.conn.execute(
            "SELECT payload FROM rules WHERE rule_id=?", (rule_id,)
        ).fetchone()
        return Rule.model_validate_json(row[0]) if row else None

    def rules(self) -> list[Rule]:
        rows = self.conn.execute("SELECT payload FROM rules ORDER BY rule_id").fetchall()
        return [Rule.model_validate_json(r[0]) for r in rows]

    def store_episode(self, episode: EpisodeRecord) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO episodes VALUES (?,?)",
            (episode.episode_id, episode.model_dump_json()),
        )
        self.conn.commit()

    def episodes(self) -> list[EpisodeRecord]:
        rows = self.conn.execute("SELECT payload FROM episodes ORDER BY episode_id").fetchall()
        return [EpisodeRecord.model_validate_json(r[0]) for r in rows]
