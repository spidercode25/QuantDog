# Market data providers for QuantDog

from __future__ import annotations

import logging
from datetime import date
from typing import Any


logger = logging.getLogger("infra.providers")


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


class LongbridgeProvider(MarketDataProvider):
    """Longbridge market data provider."""

    def __init__(self):
        """Initialize Longbridge provider with credentials from environment."""
        try:
            from longbridge.openapi import (
                AdjustType,
                Config,
                QuoteContext,
            )  # type: ignore[import-not-found]

            config = Config.from_apikey_env()
            self.ctx = QuoteContext(config)
            self._AdjustType = AdjustType
        except Exception as e:
            logger.error("Failed to initialize Longbridge provider: %s", e)
            self.ctx = None
            self._AdjustType = None

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """Convert yfinance-style symbol to Longbridge format.

        Args:
            symbol: Stock symbol in yfinance format (e.g., "AAPL", "700.HK")

        Returns:
            Longbridge-formatted symbol (e.g., "AAPL.US", "700.HK")
        """
        symbol = symbol.upper().strip()

        # If already in Longbridge format (has market suffix), return as-is
        if "." in symbol:
            return symbol

        # Default to US market for plain symbols
        return f"{symbol}.US"

    @staticmethod
    def _parse_date(date_str: str) -> date:
        """Parse date string in YYYY-MM-DD format."""
        parts = date_str.split("-")
        if len(parts) != 3:
            raise ValueError(f"Invalid date format: {date_str}")
        return date(int(parts[0]), int(parts[1]), int(parts[2]))

    def fetch_bars_1d(self, symbol: str, start_date: str, end_date: str, adjusted: bool = True) -> list[dict[str, Any]]:
        """Fetch daily bars using Longbridge.

        Args:
            symbol: Stock symbol (e.g., "AAPL", "700.HK")
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            adjusted: Whether to use adjusted prices

        Returns:
            List of bars with keys: symbol, bar_date, ts_utc, open, high, low, close, volume, adjusted, source
        """
        if self.ctx is None:
            logger.error("Longbridge context not initialized, check credentials")
            return []

        logger.info("Fetching bars for %s from %s to %s (adjusted=%s)", symbol, start_date, end_date, adjusted)

        try:
            # Convert to Longbridge symbol format
            lb_symbol = self._normalize_symbol(symbol)

            # Parse dates - Longbridge API expects datetime.date objects
            start_dt = self._parse_date(start_date)
            end_dt = self._parse_date(end_date)

            # Determine adjust type
            if self._AdjustType is None:
                logger.error("Longbridge AdjustType not available")
                return []
            adjust_type = self._AdjustType.ForwardAdjust if adjusted else self._AdjustType.NoAdjust

            # Fetch historical candlesticks by date range
            # Longbridge expects datetime.date objects for start/end parameters
            from longbridge.openapi import Period as LongbridgePeriod

            resp = self.ctx.history_candlesticks_by_date(
                symbol=lb_symbol,
                period=LongbridgePeriod.Day,
                adjust_type=adjust_type,
                start=start_dt,
                end=end_dt,
            )

            # Handle different response formats
            candles = None
            if hasattr(resp, 'candlesticks'):  # type: ignore[attr-defined]
                candles = resp.candlesticks  # type: ignore[attr-defined]
            elif isinstance(resp, list):
                candles = resp

            if not candles:
                logger.warning("No data returned for %s", symbol)
                return []

            # Convert to expected format
            bars = []
            for candle in candles:

                # Handle timestamp - could be datetime object or int/float
                timestamp = candle.timestamp
                from datetime import datetime
                if isinstance(timestamp, (int, float)):
                    # Assume milliseconds
                    ts = timestamp / 1000
                    dt = datetime.fromtimestamp(ts)
                elif isinstance(timestamp, datetime):
                    dt = timestamp
                    ts = dt.timestamp()
                else:
                    logger.warning("Unexpected timestamp type: %s", type(timestamp))
                    continue

                bar_date = dt.strftime("%Y-%m-%d")

                # Price fields are Decimal or string, convert to float
                close_v = float(candle.close) if candle.close else None
                open_v = float(candle.open) if candle.open else None
                high_v = float(candle.high) if candle.high else None
                low_v = float(candle.low) if candle.low else None
                volume_v = int(candle.volume) if candle.volume else 0

                if close_v is None:
                    continue

                bar = {
                    "symbol": symbol.upper(),
                    "bar_date": bar_date,
                    "ts_utc": int(ts),
                    "open": open_v if open_v is not None else close_v,
                    "high": high_v if high_v is not None else close_v,
                    "low": low_v if low_v is not None else close_v,
                    "close": close_v,
                    "volume": volume_v,
                    "adjusted": adjusted,
                    "source": "longbridge",
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
    return LongbridgeProvider()
