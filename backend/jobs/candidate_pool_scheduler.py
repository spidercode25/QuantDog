from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from config import get_settings
from infra.sqlalchemy import get_engine
from jobs.queue import enqueue_job, has_job_with_dedupe_key


def enqueue_candidate_pool_close_run(
    *,
    now_et: datetime | None = None,
    force: bool = False,
    trading_date_et: date | None = None,
) -> str | None:
    settings = get_settings()
    if not settings.candidate_pool_enabled:
        return None
    if settings.database_url is None:
        raise ValueError("DATABASE_URL not set")

    current_et = now_et or datetime.now(tz=ZoneInfo("America/New_York"))
    current_et = current_et.astimezone(ZoneInfo("America/New_York"))
    effective_trading_date = trading_date_et or current_et.date()
    close_time_et = _close_time_for_date(effective_trading_date)

    if not force:
        if current_et.weekday() >= 5:
            return None
        if is_us_market_holiday(effective_trading_date):
            return None
        if current_et.time() < close_time_et:
            return None

    trading_date_et_text = effective_trading_date.isoformat()
    engine = get_engine(settings.database_url)
    dedupe_key = f"candidate_pool_close_run:{trading_date_et_text}"
    if has_job_with_dedupe_key(
        engine,
        dedupe_key=dedupe_key,
        states=("queued", "running", "succeeded"),
    ):
        return None

    return enqueue_job(
        engine,
        kind="candidate_pool_close_run",
        payload={"trading_date_et": trading_date_et_text},
        dedupe_key=dedupe_key,
    )


def is_us_market_holiday(trading_date_et: date) -> bool:
    year = trading_date_et.year
    holidays = {
        _observed(date(year, 1, 1)),
        _nth_weekday_of_month(year, 1, 0, 3),
        _nth_weekday_of_month(year, 2, 0, 3),
        _good_friday(year),
        _last_weekday_of_month(year, 5, 0),
        _observed(date(year, 6, 19)),
        _observed(date(year, 7, 4)),
        _nth_weekday_of_month(year, 9, 0, 1),
        _nth_weekday_of_month(year, 11, 3, 4),
        _observed(date(year, 12, 25)),
    }
    return trading_date_et in holidays


def is_us_market_half_day(trading_date_et: date) -> bool:
    year = trading_date_et.year

    thanksgiving = _nth_weekday_of_month(year, 11, 3, 4)
    day_after_thanksgiving = thanksgiving + timedelta(days=1)

    christmas_eve = date(year, 12, 24)
    if christmas_eve.weekday() >= 5:
        christmas_eve_half_day = None
    else:
        christmas_eve_half_day = christmas_eve

    half_days = {day_after_thanksgiving}
    if christmas_eve_half_day is not None:
        half_days.add(christmas_eve_half_day)
    return trading_date_et in half_days


def _close_time_for_date(trading_date_et: date) -> "time":
    settings = get_settings()
    if is_us_market_half_day(trading_date_et):
        return time(13, 5)
    return settings.candidate_pool_close_time_et


def _observed(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def _nth_weekday_of_month(year: int, month: int, weekday: int, ordinal: int) -> date:
    current = date(year, month, 1)
    while current.weekday() != weekday:
        current += timedelta(days=1)
    current += timedelta(weeks=ordinal - 1)
    return current


def _last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    if month == 12:
        current = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        current = date(year, month + 1, 1) - timedelta(days=1)
    while current.weekday() != weekday:
        current -= timedelta(days=1)
    return current


def _good_friday(year: int) -> date:
    easter = _easter_sunday(year)
    return easter - timedelta(days=2)


def _easter_sunday(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)
