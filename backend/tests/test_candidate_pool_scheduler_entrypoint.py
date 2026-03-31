from __future__ import annotations

from unittest.mock import patch


def test_run_candidate_pool_scheduler_once(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("LOG_DIR", ".")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setenv("TELEGRAM_GROUP_ID", "-1001234567890")
    monkeypatch.setenv("LONGBRIDGE_APP_KEY", "key")
    monkeypatch.setenv("LONGBRIDGE_APP_SECRET", "secret")
    monkeypatch.setenv("LONGBRIDGE_ACCESS_TOKEN", "token")
    monkeypatch.setattr("sys.argv", ["run_candidate_pool_scheduler.py", "--once"])

    from run_candidate_pool_scheduler import main

    with patch("run_candidate_pool_scheduler.configure_logging"), patch(
        "run_candidate_pool_scheduler.enqueue_candidate_pool_close_run"
    ) as mock_enqueue:
        result = main()

    assert result == 0
    mock_enqueue.assert_called_once_with(force=False, trading_date_et=None)


def test_run_candidate_pool_scheduler_once_force(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("LOG_DIR", ".")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setenv("TELEGRAM_GROUP_ID", "-1001234567890")
    monkeypatch.setenv("LONGBRIDGE_APP_KEY", "key")
    monkeypatch.setenv("LONGBRIDGE_APP_SECRET", "secret")
    monkeypatch.setenv("LONGBRIDGE_ACCESS_TOKEN", "token")
    monkeypatch.setattr("sys.argv", ["run_candidate_pool_scheduler.py", "--once", "--force"])

    from run_candidate_pool_scheduler import main

    with patch("run_candidate_pool_scheduler.configure_logging"), patch(
        "run_candidate_pool_scheduler.enqueue_candidate_pool_close_run"
    ) as mock_enqueue:
        result = main()

    assert result == 0
    mock_enqueue.assert_called_once_with(force=True, trading_date_et=None)


def test_run_candidate_pool_scheduler_once_force_with_trading_date(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("LOG_DIR", ".")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setenv("TELEGRAM_GROUP_ID", "-1001234567890")
    monkeypatch.setenv("LONGBRIDGE_APP_KEY", "key")
    monkeypatch.setenv("LONGBRIDGE_APP_SECRET", "secret")
    monkeypatch.setenv("LONGBRIDGE_ACCESS_TOKEN", "token")
    monkeypatch.setattr(
        "sys.argv",
        ["run_candidate_pool_scheduler.py", "--once", "--force", "--trading-date-et", "2026-03-30"],
    )

    from run_candidate_pool_scheduler import main

    with patch("run_candidate_pool_scheduler.configure_logging"), patch(
        "run_candidate_pool_scheduler.enqueue_candidate_pool_close_run"
    ) as mock_enqueue:
        result = main()

    assert result == 0
    called_kwargs = mock_enqueue.call_args.kwargs
    assert called_kwargs["force"] is True
    assert str(called_kwargs["trading_date_et"]) == "2026-03-30"
