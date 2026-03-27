from __future__ import annotations

from flask import Blueprint

from api.envelope import error, success
from screening.candidate_pool_repository import CandidatePoolRepository

candidate_pool_bp = Blueprint("candidate_pool", __name__)


@candidate_pool_bp.get("/api/v1/candidate-pools/latest")
def get_latest_candidate_pool():
    """Get the latest successful candidate snapshot."""
    repo = CandidatePoolRepository()

    repo = CandidatePoolRepository()

    snapshot = repo.get_latest_snapshot()
    if snapshot is None:
        return error("No candidate snapshot found", error_type="not_found", status_code=404)

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
            "snapshot_time": snapshot.snapshot_time_et.strftime("%H:%M:%S"),
            "timezone": "America/New_York",
            "count": len(candidates),
            "candidates": candidates,
        }
    )
