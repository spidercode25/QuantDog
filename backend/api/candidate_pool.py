# pyright: reportMissingImports=false, reportAttributeAccessIssue=false

from __future__ import annotations

from flask import Blueprint, g

from api.envelope import error, success
from screening.candidate_pool_repository import CandidatePoolRepository

candidate_pool_bp = Blueprint("candidate_pool", __name__)


def get_db():
    """Get database connection from Flask app context."""
    if "db" not in g:
        from config import get_settings
        from infra.sqlalchemy import get_engine

        settings = get_settings()
        if settings.database_url is None:
            raise ValueError("DATABASE_URL not set")
        database_url = settings.database_url
        g.db = get_engine(database_url)
    return g.db


@candidate_pool_bp.teardown_request
def close_db(exception):
    """Close database connection at end of request."""
    db = g.pop("db", None)
    if db is not None:
        db.dispose()


@candidate_pool_bp.get("/api/v1/candidate-pools/latest")
def get_latest_candidate_pool():
    """Get the latest successful candidate snapshot."""
    db = get_db()
    repo = CandidatePoolRepository(engine=db)

    snapshot = repo.get_latest_snapshot()
    if snapshot is None:
        return error("No candidate snapshot found", error_type="not_found", detail="No candidate snapshot found in database", status_code=404)

    members = repo.get_snapshot_members(snapshot.snapshot_key)

    candidates = [
        {
            "symbol": member.symbol,
            "rank": member.rank,
            "rvol": member.rvol,
            "pct_change": member.pct_change,
            "dollar_volume": member.dollar_volume,
            "last_price": member.last_price,
        }
        for member in members
    ]

    return success(
        {
            "candidates": candidates,
        }
    )
