from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import text

from infra.sqlalchemy import get_engine

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


@dataclass(frozen=True, slots=True)
class CandidateSnapshot:
    snapshot_key: str  # format: YYYY-MM-DD_HH:MM:SS
    snapshot_time_et: datetime
    provider_asof_et: datetime
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CandidateMember:
    snapshot_key: str
    symbol: str
    rank: int
    rvol: float
    pct_change: float
    dollar_volume: float
    last_price: float
    inclusion_reason: str | None
    exclusion_reason: str | None
    created_at: datetime


class CandidatePoolRepository:
    def __init__(self, engine: Engine | None = None, database_url: str | None = None) -> None:
        if engine is not None:
            self._engine = engine
        elif database_url is not None:
            self._engine = get_engine(database_url)
        else:
            import os

            database_url = os.environ.get("DATABASE_URL")
            if not database_url:
                raise ValueError("Either engine or database_url must be provided")
            self._engine = get_engine(database_url)

    def snapshot_exists(self, snapshot_key: str) -> bool:
        with self._engine.connect() as conn:
            result = conn.execute(
                text("SELECT 1 FROM candidate_snapshots WHERE snapshot_key = :snapshot_key LIMIT 1"),
                {"snapshot_key": snapshot_key},
            )
            return result.fetchone() is not None

    def upsert_snapshot(
        self,
        snapshot_key: str,
        snapshot_time_et: datetime,
        provider_asof_et: datetime,
        members: list[CandidateMember],
    ) -> None:
        """Idempotently upsert a snapshot and its members."""
        with self._engine.connect() as conn:
            # Upsert snapshot
            conn.execute(
                text("""
                    INSERT INTO candidate_snapshots (snapshot_key, snapshot_time_et, provider_asof_et, created_at)
                    VALUES (:snapshot_key, :snapshot_time_et, :provider_asof_et, :created_at)
                    ON CONFLICT (snapshot_key) DO UPDATE SET
                        snapshot_time_et = EXCLUDED.snapshot_time_et,
                        provider_asof_et = EXCLUDED.provider_asof_et,
                        created_at = EXCLUDED.created_at
                """),
                {
                    "snapshot_key": snapshot_key,
                    "snapshot_time_et": snapshot_time_et,
                    "provider_asof_et": provider_asof_et,
                    "created_at": datetime.now(UTC),
                },
            )

            # Delete existing members for this snapshot (for idempotency)
            conn.execute(
                text("DELETE FROM candidate_members WHERE snapshot_key = :snapshot_key"),
                {"snapshot_key": snapshot_key},
            )

            # Insert members
            for member in members:
                conn.execute(
                    text("""
                        INSERT INTO candidate_members (
                            snapshot_key, symbol, rank, rvol, pct_change, dollar_volume,
                            last_price, inclusion_reason, exclusion_reason, created_at
                        )
                        VALUES (
                            :snapshot_key, :symbol, :rank, :rvol, :pct_change, :dollar_volume,
                            :last_price, :inclusion_reason, :exclusion_reason, :created_at
                        )
                    """),
                    {
                        "snapshot_key": snapshot_key,
                        "symbol": member.symbol,
                        "rank": member.rank,
                        "rvol": member.rvol,
                        "pct_change": member.pct_change,
                        "dollar_volume": member.dollar_volume,
                        "last_price": member.last_price,
                        "inclusion_reason": member.inclusion_reason,
                        "exclusion_reason": member.exclusion_reason,
                        "created_at": datetime.now(UTC),
                    },
                )

            conn.commit()

    def get_latest_snapshot(self) -> CandidateSnapshot | None:
        """Get the most recent successful snapshot."""
        with self._engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT snapshot_key, snapshot_time_et, provider_asof_et, created_at
                    FROM candidate_snapshots
                    ORDER BY snapshot_time_et DESC
                    LIMIT 1
                """)
            )
            row = result.fetchone()
            if row is None:
                return None

            # Convert string timestamps to datetime if needed
            snapshot_time_et = row[1] if isinstance(row[1], datetime) else datetime.fromisoformat(row[1])
            provider_asof_et = row[2] if isinstance(row[2], datetime) else datetime.fromisoformat(row[2])
            created_at = row[3] if isinstance(row[3], datetime) else datetime.fromisoformat(row[3])

            return CandidateSnapshot(
                snapshot_key=row[0],
                snapshot_time_et=snapshot_time_et,
                provider_asof_et=provider_asof_et,
                created_at=created_at,
            )

    def get_snapshot_members(self, snapshot_key: str) -> list[CandidateMember]:
        """Get all members for a given snapshot."""
        with self._engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT
                        snapshot_key, symbol, rank, rvol, pct_change, dollar_volume,
                        last_price, inclusion_reason, exclusion_reason, created_at
                    FROM candidate_members
                    WHERE snapshot_key = :snapshot_key
                    ORDER BY rank ASC
                """),
                {"snapshot_key": snapshot_key},
            )
            return [
                CandidateMember(
                    snapshot_key=row[0],
                    symbol=row[1],
                    rank=row[2],
                    rvol=row[3],
                    pct_change=row[4],
                    dollar_volume=row[5],
                    last_price=row[6],
                    inclusion_reason=row[7],
                    exclusion_reason=row[8],
                    created_at=row[9],
                )
                for row in result.fetchall()
            ]

    def prune_old_snapshots(self, keep_days: int = 30) -> int:
        """Delete snapshots older than keep_days and their members."""
        with self._engine.connect() as conn:
            cutoff = datetime.now(UTC) - timedelta(days=keep_days)
            result = conn.execute(
                text("""
                    DELETE FROM candidate_snapshots
                    WHERE created_at < :cutoff
                    RETURNING snapshot_key
                """),
                {"cutoff": cutoff},
            )
            deleted_count = len(result.fetchall())
            conn.commit()
            return deleted_count
