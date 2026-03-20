from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True, slots=True)
class TwelveDataProvider:
    base_url: str
    api_key: str
    interval: str = "1day"
    timeout_seconds: float = 12.0

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        merged = dict(params)
        merged["apikey"] = self.api_key

        with httpx.Client(timeout=self.timeout_seconds) as client:
            resp = client.get(f"{self.base_url.rstrip('/')}{path}", params=merged)
            resp.raise_for_status()
            data = resp.json()

        if isinstance(data, dict) and data.get("status") == "error":
            message = data.get("message") or data.get("code") or "twelvedata error"
            raise ValueError(str(message))
        if not isinstance(data, dict):
            raise ValueError("Unexpected TwelveData response format")
        return data

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _latest_value(payload: dict[str, Any], field: str) -> float | None:
        values = payload.get("values")
        if not isinstance(values, list) or not values:
            return None

        head = values[0]
        if not isinstance(head, dict):
            return None

        raw = head.get(field)
        if raw is None:
            return None

        return TwelveDataProvider._to_float(raw)

    @staticmethod
    def _latest_time(payload: dict[str, Any]) -> str | None:
        values = payload.get("values")
        if not isinstance(values, list) or not values:
            return None

        head = values[0]
        if not isinstance(head, dict):
            return None

        dt = head.get("datetime")
        if dt is None:
            return None
        text = str(dt).strip()
        return text or None

    def fetch_technical_indicators(self, symbol: str) -> dict[str, Any]:
        sym = symbol.strip().upper()

        base_params = {
            "symbol": sym,
            "interval": self.interval,
            "series_type": "close",
            "outputsize": 1,
        }

        sma20_payload = self._get("/sma", {**base_params, "time_period": 20})
        sma50_payload = self._get("/sma", {**base_params, "time_period": 50})
        rsi14_payload = self._get("/rsi", {**base_params, "time_period": 14})
        macd_payload = self._get(
            "/macd",
            {
                **base_params,
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
            },
        )

        macd_values = macd_payload.get("values")
        macd_value = None
        macd_signal = None
        macd_hist = None
        if isinstance(macd_values, list) and macd_values and isinstance(macd_values[0], dict):
            top = macd_values[0]
            macd_value = self._to_float(top.get("macd"))
            macd_signal = self._to_float(top.get("macd_signal"))
            macd_hist = self._to_float(top.get("macd_hist"))

        as_of = (
            self._latest_time(sma20_payload)
            or self._latest_time(sma50_payload)
            or self._latest_time(rsi14_payload)
            or self._latest_time(macd_payload)
        )

        return {
            "symbol": sym,
            "source": "twelvedata",
            "as_of": as_of,
            "sma20": self._latest_value(sma20_payload, "sma"),
            "sma50": self._latest_value(sma50_payload, "sma"),
            "rsi14": self._latest_value(rsi14_payload, "rsi"),
            "macd": macd_value,
            "macd_signal": macd_signal,
            "macd_histogram": macd_hist,
        }
