from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, ClassVar

import httpx
from sqlalchemy import text

from quantdog.analysis.indicators import calculate_indicators
from quantdog.analysis.baseline import generate_baseline_analysis
from quantdog.config import Settings
from quantdog.infra.providers import get_provider
from quantdog.infra.providers.news import resolve_news_provider
from quantdog.infra.providers.twitter import resolve_twitter_provider
from quantdog.infra.sqlalchemy import get_engine
from quantdog.research.news_cache import fetch_recent_news


@dataclass(slots=True)
class MarketIntelService:
    settings: Settings
    _macro_snapshot_cache: ClassVar[dict[str, Any] | None] = None
    _macro_snapshot_cache_date: ClassVar[str | None] = None

    def _get_fred_latest(self, series_id: str) -> float | None:
        params: dict[str, Any] = {
            "series_id": series_id,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 1,
        }
        if self.settings.fred_api_key:
            params["api_key"] = self.settings.fred_api_key

        url = f"{self.settings.fred_base_url.rstrip('/')}/series/observations"
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            payload = resp.json()

        observations = payload.get("observations") if isinstance(payload, dict) else None
        if not isinstance(observations, list) or not observations:
            return None

        row = observations[0]
        if not isinstance(row, dict):
            return None

        raw = row.get("value")
        if isinstance(raw, (int, float)):
            return float(raw)
        if isinstance(raw, str):
            if raw == "." or raw.strip() == "":
                return None
            try:
                return float(raw)
            except ValueError:
                return None
        return None

    @staticmethod
    def _empty_macro_snapshot() -> dict[str, Any]:
        ids = {
            "tips_10y": None,
            "yield_10y": None,
            "yield_2y": None,
            "yield_spread": None,
            "cpi": None,
            "core_cpi": None,
            "fed_rate": None,
            "dxy": None,
            "breakeven": None,
            "copper_gold_ratio": None,
        }
        return ids

    def _has_today_db_bar(self, symbol: str) -> bool:
        if self.settings.database_url is None:
            return False

        engine = get_engine(self.settings.database_url)
        today = date.today().isoformat()
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT 1
                    FROM bars_1d
                    WHERE symbol = :symbol
                      AND adjusted = true
                      AND bar_date = :bar_date
                    LIMIT 1
                    """
                ),
                {"symbol": symbol.upper(), "bar_date": today},
            ).fetchone()
        return row is not None

    def _get_macro_snapshot(self, symbol: str) -> dict[str, Any]:
        ids = {
            "tips_10y": "DFII10",
            "yield_10y": "DGS10",
            "yield_2y": "DGS2",
            "yield_spread": "T10Y2Y",
            "cpi": "CPIAUCSL",
            "core_cpi": "CPILFESL",
            "fed_rate": "FEDFUNDS",
            "dxy": "DTWEXBGS",
            "breakeven": "T10YIE",
        }

        today = date.today().isoformat()
        cache = MarketIntelService._macro_snapshot_cache
        cache_date = MarketIntelService._macro_snapshot_cache_date

        if cache_date == today and cache is not None:
            return dict(cache)

        if self._has_today_db_bar(symbol):
            if cache is not None:
                return dict(cache)
            return self._empty_macro_snapshot()

        if not self.settings.fred_api_key:
            return self._empty_macro_snapshot()

        result: dict[str, Any] = {}
        for key, sid in ids.items():
            try:
                result[key] = self._get_fred_latest(sid)
            except Exception:
                result[key] = None

        try:
            copper = self._get_fred_latest("PCOPPUSDM")
            gold = self._get_fred_latest("GOLDAMGBD228NLBM")
            if copper is None or gold is None or gold == 0:
                result["copper_gold_ratio"] = None
            else:
                result["copper_gold_ratio"] = round((copper * 14.5833) / float(gold), 4)
        except Exception:
            result["copper_gold_ratio"] = None

        MarketIntelService._macro_snapshot_cache = dict(result)
        MarketIntelService._macro_snapshot_cache_date = today

        return result

    @staticmethod
    def _macro_theme_from_snapshot(snapshot: dict[str, Any]) -> str:
        yield_spread = snapshot.get("yield_spread")
        fed_rate = snapshot.get("fed_rate")
        cpi = snapshot.get("cpi")
        core_cpi = snapshot.get("core_cpi")
        breakeven = snapshot.get("breakeven")
        dxy = snapshot.get("dxy")

        if isinstance(yield_spread, (int, float)) and yield_spread < 0:
            return "growth"
        if isinstance(fed_rate, (int, float)) and isinstance(cpi, (int, float)) and fed_rate > cpi:
            return "rates"
        if isinstance(core_cpi, (int, float)) and core_cpi >= 3.5:
            return "inflation"
        if isinstance(breakeven, (int, float)) and breakeven >= 2.5:
            return "inflation"
        if isinstance(dxy, (int, float)) and dxy >= 125:
            return "liquidity"
        return "none"

    def _fetch_live_recent_bars(self, symbol: str, *, minimum_bars: int = 50) -> list[dict[str, Any]]:
        try:
            provider = get_provider()
            today = date.today()
            lookback_days = max(120, minimum_bars * 3)
            start_date = (today - timedelta(days=lookback_days)).isoformat()
            end_date = (today + timedelta(days=1)).isoformat()
            fetched = provider.fetch_bars_1d(symbol, start_date, end_date, adjusted=True)
        except Exception:
            return []

        if not fetched:
            return []

        normalized: list[dict[str, Any]] = []
        for item in fetched:
            if not isinstance(item, dict):
                continue
            date_text = str(item.get("bar_date") or "").strip()
            close = item.get("close")
            if not date_text or close is None:
                continue
            normalized.append(
                {
                    "symbol": symbol.upper(),
                    "bar_date": date_text,
                    "ts_utc": item.get("ts_utc"),
                    "open": float(item.get("open") or close),
                    "high": float(item.get("high") or close),
                    "low": float(item.get("low") or close),
                    "close": float(close),
                    "volume": item.get("volume"),
                    "adjusted": True,
                    "source": f"{item.get('source') or 'provider'}_realtime",
                }
            )

        if not normalized:
            return []

        normalized.sort(key=lambda b: str(b.get("bar_date") or ""))
        if len(normalized) <= minimum_bars:
            return normalized
        return normalized[-minimum_bars:]

    @staticmethod
    def _merge_bars_by_date(base_bars: list[dict[str, Any]], incoming_bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not incoming_bars:
            return base_bars

        by_date: dict[str, dict[str, Any]] = {}
        for bar in base_bars:
            date_text = str(bar.get("bar_date") or "")
            if date_text:
                by_date[date_text] = dict(bar)

        for bar in incoming_bars:
            date_text = str(bar.get("bar_date") or "")
            if date_text:
                by_date[date_text] = dict(bar)

        merged = list(by_date.values())
        merged.sort(key=lambda b: str(b.get("bar_date") or ""))
        return merged

    @staticmethod
    def _has_current_day_bar(bars: list[dict[str, Any]]) -> bool:
        today = date.today().isoformat()
        for bar in bars:
            if str(bar.get("bar_date") or "") == today:
                return True
        return False

    def _fetch_recent_closes(self, symbol: str, *, limit: int = 5) -> list[float]:
        if self.settings.database_url is None:
            return []
        engine = get_engine(self.settings.database_url)
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT close
                    FROM bars_1d
                    WHERE symbol = :symbol AND adjusted = true
                    ORDER BY bar_date DESC
                    LIMIT :limit
                    """
                ),
                {"symbol": symbol, "limit": max(1, min(limit, 200))},
            )
            rows = result.fetchall()
        return [float(row[0]) for row in rows if row and row[0] is not None]

    def _fetch_live_close_fallback(self, symbol: str) -> float | None:
        """Fallback to market data provider when DB bars are unavailable."""
        try:
            provider = get_provider()
            end_date = date.today()
            start_date = end_date - timedelta(days=14)
            bars = provider.fetch_bars_1d(
                symbol,
                start_date.isoformat(),
                end_date.isoformat(),
                adjusted=True,
            )
            if not bars:
                return None
            latest = bars[-1]
            close = latest.get("close")
            return float(close) if close is not None else None
        except Exception:
            return None

    def _get_latest_available_close(self, candidates: list[str]) -> tuple[str | None, float | None]:
        for candidate in candidates:
            closes = self._fetch_recent_closes(candidate, limit=1)
            if closes:
                return candidate, closes[0]
            live_close = self._fetch_live_close_fallback(candidate)
            if live_close is not None:
                return candidate, live_close
        return None, None

    def _build_vix_risk_filter(self) -> dict[str, Any]:
        symbol, vix_value = self._get_latest_available_close(["^VIX", "VIX"])

        if vix_value is None:
            return {
                "vix_symbol": None,
                "vix": None,
                "regime": "unknown",
                "cash_target_pct": None,
                "rule": "VIX unavailable; skip regime gating",
                "allow_high_beta": False,
                "index_dip_buy_zone": False,
            }

        if vix_value < 17:
            regime = "risk_on"
            cash_target = 10
            rule = "VIX<17: allow high-beta longs"
            allow_high_beta = True
            index_dip_buy_zone = False
        elif vix_value < 27:
            regime = "neutral_caution"
            cash_target = 30
            rule = "17<=VIX<27: keep ~30% cash"
            allow_high_beta = False
            index_dip_buy_zone = False
        elif vix_value <= 46:
            regime = "high_vol_observe"
            cash_target = 55
            rule = "27<=VIX<=46: observe macro, cautious dip-buy"
            allow_high_beta = False
            index_dip_buy_zone = False
        else:
            regime = "panic_zone"
            cash_target = 30
            rule = "VIX>46: index dip-buy relatively safer, still staged"
            allow_high_beta = False
            index_dip_buy_zone = True

        return {
            "vix_symbol": symbol,
            "vix": round(vix_value, 3),
            "regime": regime,
            "cash_target_pct": cash_target,
            "rule": rule,
            "allow_high_beta": allow_high_beta,
            "index_dip_buy_zone": index_dip_buy_zone,
        }

    def _cross_asset_confirmations(self) -> dict[str, Any]:
        # C1: VIX topping/down-break (proxy: 2-day decline after recent spike)
        _, vix_latest = self._get_latest_available_close(["^VIX", "VIX"])
        vix_recent = self._fetch_recent_closes("^VIX", limit=3)
        if not vix_recent:
            vix_recent = self._fetch_recent_closes("VIX", limit=3)
        c1 = None
        if len(vix_recent) >= 3:
            # rows are DESC, so [0] newest
            c1 = (vix_recent[0] < vix_recent[1]) and (vix_recent[1] >= vix_recent[2])

        # C2: Oil tightening chain risk not escalating (proxy with CL=F + DXY if available)
        oil_recent = self._fetch_recent_closes("CL=F", limit=2)
        dxy_recent = self._fetch_recent_closes("DX-Y.NYB", limit=2)
        if not dxy_recent:
            dxy_recent = self._fetch_recent_closes("DXY", limit=2)
        c2 = None
        if len(oil_recent) >= 2 and len(dxy_recent) >= 2:
            oil_up = oil_recent[0] > oil_recent[1]
            dxy_up = dxy_recent[0] > dxy_recent[1]
            c2 = not (oil_up and dxy_up)

        # C3: XLE / momentum-strength ratio not expanding (proxy XLE/QQQ)
        xle_recent = self._fetch_recent_closes("XLE", limit=2)
        qqq_recent = self._fetch_recent_closes("QQQ", limit=2)
        c3 = None
        ratio_now = None
        ratio_prev = None
        if len(xle_recent) >= 2 and len(qqq_recent) >= 2 and qqq_recent[0] > 0 and qqq_recent[1] > 0:
            ratio_now = xle_recent[0] / qqq_recent[0]
            ratio_prev = xle_recent[1] / qqq_recent[1]
            c3 = ratio_now <= ratio_prev

        confirmations = [flag for flag in [c1, c2, c3] if flag is True]
        unknowns = [flag for flag in [c1, c2, c3] if flag is None]
        return {
            "c1_vix_rollover": c1,
            "c2_tightening_chain_not_worsening": c2,
            "c3_xle_momo_ratio_not_expanding": c3,
            "xle_qqq_ratio_now": round(ratio_now, 6) if ratio_now is not None else None,
            "xle_qqq_ratio_prev": round(ratio_prev, 6) if ratio_prev is not None else None,
            "true_count": len(confirmations),
            "unknown_count": len(unknowns),
            "as_of_utc": datetime.now(timezone.utc).isoformat(),
            "vix_latest": vix_latest,
        }

    def get_technical_analysis(self, symbol: str, *, horizon: str = "1d") -> dict[str, Any]:
        if self.settings.database_url is None:
            raise ValueError("DATABASE_URL not set")

        sym = symbol.strip().upper()
        engine = get_engine(self.settings.database_url)
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT symbol, bar_date, ts_utc, open, high, low, close, volume, adjusted, source
                    FROM bars_1d
                    WHERE symbol = :symbol AND adjusted = true
                    ORDER BY bar_date DESC
                    LIMIT 100
                    """
                ),
                {"symbol": sym},
            )
            rows = result.fetchall()

        bars = [
            {
                "symbol": row[0],
                "bar_date": str(row[1]),
                "ts_utc": row[2],
                "open": float(row[3]),
                "high": float(row[4]),
                "low": float(row[5]),
                "close": float(row[6]),
                "volume": row[7],
                "adjusted": row[8],
                "source": row[9],
            }
            for row in reversed(rows)
        ]

        if not bars or not self._has_current_day_bar(bars):
            live_recent = self._fetch_live_recent_bars(sym, minimum_bars=50)
            bars = self._merge_bars_by_date(bars, live_recent)

        if not bars:
            raise ValueError(f"No bars found for {sym}. Ingest data first.")

        indicators = calculate_indicators(bars)
        latest_close = bars[-1].get("close")
        if latest_close is not None:
            indicators["latest_price"] = float(latest_close)
        baseline = generate_baseline_analysis(sym, indicators)
        return {
            "symbol": sym,
            "horizon": horizon,
            "bars_count": len(bars),
            "latest_price": indicators.get("latest_price"),
            "indicators": indicators,
            "analysis": baseline,
        }

    def get_news_twitter_analysis(self, symbol: str, *, limit: int = 20) -> dict[str, Any]:
        sym = symbol.strip().upper()
        news_items: list[dict[str, Any]] = []
        twitter_items: list[dict[str, Any]] = []
        source_status: dict[str, Any] = {
            "news_cache": "not_checked",
            "news_provider": "not_checked",
            "twitter_provider": "not_checked",
        }

        if self.settings.database_url:
            try:
                news_items = fetch_recent_news(
                    self.settings.database_url,
                    sym,
                    limit=min(limit, self.settings.news_limit),
                    max_age_hours=self.settings.news_cache_max_age_hours,
                )
                source_status["news_cache"] = "hit" if news_items else "miss"
            except Exception:
                news_items = []
                source_status["news_cache"] = "error"
        else:
            source_status["news_cache"] = "disabled_no_database"

        if not news_items:
            news_resolution = resolve_news_provider(self.settings)
            source_status["news_provider"] = news_resolution.reason
            if news_resolution.provider is not None:
                try:
                    news_items = news_resolution.provider.fetch_news(sym, limit=min(limit, self.settings.news_limit))
                    source_status["news_provider"] = "ok"
                except Exception:
                    news_items = []
                    source_status["news_provider"] = "error"
        else:
            source_status["news_provider"] = "skipped_due_to_cache"

        twitter_resolution = resolve_twitter_provider(self.settings)
        source_status["twitter_provider"] = twitter_resolution.reason
        if twitter_resolution.provider is not None:
            try:
                twitter_items = twitter_resolution.provider.search_symbol(
                    sym,
                    limit=min(limit, self.settings.twitter_limit),
                )
                source_status["twitter_provider"] = "ok"
            except Exception:
                twitter_items = []
                source_status["twitter_provider"] = "error"

        sentiment_score = self._score_sentiment(news_items, twitter_items)
        sentiment = "neutral"
        if sentiment_score > 0.15:
            sentiment = "bullish"
        elif sentiment_score < -0.15:
            sentiment = "bearish"

        return {
            "symbol": sym,
            "news_count": len(news_items),
            "twitter_count": len(twitter_items),
            "sentiment": sentiment,
            "sentiment_score": round(sentiment_score, 3),
            "source_status": source_status,
            "news": news_items[: min(10, len(news_items))],
            "twitter": twitter_items[: min(10, len(twitter_items))],
        }

    def get_macro_analysis(self, symbol: str, *, limit: int = 20) -> dict[str, Any]:
        intel = self.get_news_twitter_analysis(symbol, limit=limit)
        snapshot = self._get_macro_snapshot(symbol)
        top_theme = self._macro_theme_from_snapshot(snapshot)
        return {
            "macro_theme": top_theme,
            "snapshot": snapshot,
            "market_sentiment": intel["sentiment"],
            "market_sentiment_score": intel["sentiment_score"],
            "note": "Macro analysis uses FRED snapshot data.",
        }

    def get_strategy(self, symbol: str, *, horizon: str = "1d", limit: int = 20) -> dict[str, Any]:
        technical = self.get_technical_analysis(symbol, horizon=horizon)
        intel = self.get_news_twitter_analysis(symbol, limit=limit)
        macro = self.get_macro_analysis(symbol, limit=limit)

        tech_score = float(technical["analysis"].get("score") or 0.0)
        sentiment_score = float(intel["sentiment_score"])
        combined_score = (tech_score * 0.7) + (sentiment_score * 0.6)

        decision = "HOLD"
        if combined_score >= 0.5:
            decision = "BUY"
        elif combined_score <= -0.5:
            decision = "SELL"

        confidence = min(95, max(5, int(abs(combined_score) * 100)))

        risk_filter = self._build_vix_risk_filter()
        confirmations = self._cross_asset_confirmations()

        regime = risk_filter.get("regime")
        if regime == "neutral_caution":
            # keep more cash, require stronger score to BUY
            if decision == "BUY" and combined_score < 0.9:
                decision = "HOLD"
            confidence = max(5, min(confidence, 70))
        elif regime == "high_vol_observe":
            # only allow dip buy if 2/3 conditions true
            if decision == "BUY" and confirmations["true_count"] < 2:
                decision = "HOLD"
            confidence = max(5, min(confidence, 60))
        elif regime == "panic_zone":
            # prefer index dip-buy, cap single-stock aggression
            if decision == "BUY" and confirmations["c1_vix_rollover"] is not True:
                decision = "HOLD"
            confidence = max(5, min(confidence, 65))

        return {
            "symbol": symbol.upper(),
            "decision": decision,
            "confidence": confidence,
            "combined_score": round(combined_score, 3),
            "inputs": {
                "technical_decision": technical["analysis"].get("decision"),
                "technical_score": tech_score,
                "sentiment": intel["sentiment"],
                "sentiment_score": sentiment_score,
                "macro_theme": macro["macro_theme"],
            },
            "risk_filter": risk_filter,
            "confirmations": confirmations,
            "note": "Strategy is deterministic and combines technical + sentiment weights.",
        }

    def get_monitoring(self, symbols: list[str], *, horizon: str = "1d", limit: int = 20) -> dict[str, Any]:
        normalized = [s.strip().upper() for s in symbols if s.strip()]
        results = []
        alerts = []
        for symbol in normalized:
            try:
                strategy = self.get_strategy(symbol, horizon=horizon, limit=limit)
                results.append(strategy)
                if strategy["decision"] != "HOLD" or strategy["confidence"] >= 70:
                    alerts.append(
                        {
                            "symbol": symbol,
                            "decision": strategy["decision"],
                            "confidence": strategy["confidence"],
                            "combined_score": strategy["combined_score"],
                        }
                    )
            except Exception as exc:
                results.append({"symbol": symbol, "error": str(exc)})

        return {
            "count": len(normalized),
            "alerts": alerts,
            "results": results,
        }

    @staticmethod
    def _score_sentiment(news_items: list[dict[str, Any]], twitter_items: list[dict[str, Any]]) -> float:
        score = 0.0

        for item in news_items:
            signal = str(item.get("signal") or "").lower()
            if signal in {"long", "bullish", "positive"}:
                score += 0.2
            elif signal in {"short", "bearish", "negative"}:
                score -= 0.2

        positive_words = {"beat", "growth", "launch", "approval", "strong", "bull"}
        negative_words = {"miss", "cut", "downgrade", "lawsuit", "recall", "bear"}
        for item in twitter_items:
            txt = str(item.get("text") or "").lower()
            if any(w in txt for w in positive_words):
                score += 0.05
            if any(w in txt for w in negative_words):
                score -= 0.05

        count = max(1, len(news_items) + len(twitter_items))
        return max(-1.0, min(1.0, score / count * 5.0))
