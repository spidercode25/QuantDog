from __future__ import annotations

from datetime import date, datetime


def build_candidate_pool_close_message(
    *,
    trading_date_et: date,
    snapshot_time_et: datetime,
    candidates: list[dict],
) -> str:
    date_label = trading_date_et.isoformat()
    snapshot_label = snapshot_time_et.strftime("%Y-%m-%d %H:%M:%S ET")

    if not candidates:
        return (
            f"Daily stock selection for {date_label}\n"
            f"Snapshot: {snapshot_label}\n"
            "Universe: curated Longbridge-backed v1 watchlist\n"
            "No candidates passed the 1%-5% gain and RVOL filters."
        )

    lines = [
        f"Daily stock selection for {date_label}",
        f"Snapshot: {snapshot_label}",
        "Universe: curated Longbridge-backed v1 watchlist",
        f"Candidates: {len(candidates)}",
    ]

    for candidate in candidates:
        lines.append(
            "#{rank} {symbol} | gain {pct_change:.2f}% | RVOL {rvol:.2f}x | price ${last_price:.2f}".format(
                rank=candidate["rank"],
                symbol=candidate["symbol"],
                pct_change=candidate["pct_change"],
                rvol=candidate["rvol"],
                last_price=candidate["last_price"],
            )
        )

    return "\n".join(lines)
