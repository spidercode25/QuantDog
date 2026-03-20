# Market data providers for QuantDog

from __future__ import annotations

import logging
from typing import Any

import yfinance as yf  # type: ignore[import-not-found]


logger = logging.getLogger("quantdog.infra.providers")


class MarketDataProvider:
    """Abstract data provider."""
    
    def fetch_bars_1d(self, symbol: str, start_date: str, end_date: str, adjusted: bool = True) -> list[dict[str, Any]]:
        """Fetch daily bars for a symbol.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL")
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            adjusted: Whether to use adjusted prices
            
        Returns:
            List of bars with keys: symbol, bar_date, ts_utc, open, high, low, close, volume, adjusted, source
        """
        raise NotImplementedError


class YFinanceProvider(MarketDataProvider):
    """YFinance market data provider."""

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            num = float(value)
        except (TypeError, ValueError):
            return None
        if num != num:  # NaN check
            return None
        return num

    @staticmethod
    def _to_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            num = int(float(value))
        except (TypeError, ValueError):
            return None
        return num

    @staticmethod
    def _series_value(row: Any, key: str) -> Any:
        try:
            if key in row:
                return row[key]
            lower = key.lower()
            if lower in row:
                return row[lower]
        except Exception:
            return None
        return None
    
    def fetch_bars_1d(self, symbol: str, start_date: str, end_date: str, adjusted: bool = True) -> list[dict[str, Any]]:
        """Fetch daily bars using yfinance."""
        logger.info("Fetching bars for %s from %s to %s (adjusted=%s)", symbol, start_date, end_date, adjusted)

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date, auto_adjust=adjusted)

            if df is None or df.empty:
                logger.warning("No data returned for %s", symbol)
                return []

            bars = []
            for idx, row in df.iterrows():
                date_text = str(idx).strip()
                bar_date_text = date_text[:10]
                if len(bar_date_text) != 10 or "-" not in bar_date_text:
                    continue

                open_v = self._to_float(self._series_value(row, "Open"))
                high_v = self._to_float(self._series_value(row, "High"))
                low_v = self._to_float(self._series_value(row, "Low"))
                close_v = self._to_float(self._series_value(row, "Close"))
                volume_v = self._to_int(self._series_value(row, "Volume"))

                if close_v is None:
                    continue
                bar = {
                    "symbol": symbol.upper(),
                    "bar_date": bar_date_text,
                    "ts_utc": None,
                    "open": open_v if open_v is not None else close_v,
                    "high": high_v if high_v is not None else close_v,
                    "low": low_v if low_v is not None else close_v,
                    "close": close_v,
                    "volume": volume_v if volume_v is not None else 0,
                    "adjusted": adjusted,
                    "source": "yfinance",
                }
                bars.append(bar)

            logger.info("Fetched %d bars for %s", len(bars), symbol)
            return bars

        except Exception as e:
            logger.error("Failed to fetch bars for %s: %s", symbol, e)
            return []


def get_provider() -> MarketDataProvider:
    """Get the configured market data provider."""
    # TODO: Add support for Finnhub and other providers
    return YFinanceProvider()
