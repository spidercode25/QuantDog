# Market data providers for QuantDog

from __future__ import annotations

import logging
from datetime import datetime, timezone
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
    
    def fetch_bars_1d(self, symbol: str, start_date: str, end_date: str, adjusted: bool = True) -> list[dict[str, Any]]:
        """Fetch daily bars using yfinance."""
        logger.info("Fetching bars for %s from %s to %s (adjusted=%s)", symbol, start_date, end_date, adjusted)
        
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date, auto_adjust=adjusted)
            
            if df.empty:
                logger.warning("No data returned for %s", symbol)
                return []
            
            bars = []
            for idx, row in df.iterrows():
                # idx is pandas Timestamp
                bar_date = idx.date()
                ts_utc = int(idx.timestamp())
                
                bar = {
                    "symbol": symbol.upper(),
                    "bar_date": bar_date.isoformat(),
                    "ts_utc": ts_utc,
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]),
                    "adjusted": adjusted,
                    "source": "yfinance"
                }
                bars.append(bar)
            
            logger.info("Fetched %d bars for %s", len(bars), symbol)
            return bars
            
        except Exception as e:
            logger.error("Failed to fetch bars for %s: %s", symbol, e)
            raise


def get_provider() -> MarketDataProvider:
    """Get the configured market data provider."""
    # TODO: Add support for Finnhub and other providers
    return YFinanceProvider()
