#!/usr/bin/env python3
# pyright: reportAttributeAccessIssue=false
"""Client program for testing US stock analysis APIs.

Supports two modes:
- HTTP mode (default): call a running API service
- In-process mode: call Flask app test_client directly (no server required)
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ApiResult:
    ok: bool
    status: int
    body: dict[str, Any]
    error: str | None = None


class HttpApiClient:
    def __init__(self, base_url: str, timeout_seconds: float):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def post(self, path: str, payload: dict[str, Any]) -> ApiResult:
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return self._request(req)

    def get(self, path: str, query: dict[str, Any] | None = None) -> ApiResult:
        suffix = ""
        if query:
            suffix = "?" + urllib.parse.urlencode({k: str(v) for k, v in query.items()})
        req = urllib.request.Request(f"{self.base_url}{path}{suffix}", method="GET")
        return self._request(req)

    def _request(self, request: urllib.request.Request) -> ApiResult:
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as resp:
                raw = resp.read().decode("utf-8", "replace")
                body = json.loads(raw) if raw else {}
                return ApiResult(ok=200 <= resp.status < 300, status=resp.status, body=body)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            body = json.loads(raw) if raw else {}
            return ApiResult(ok=False, status=exc.code, body=body, error=f"HTTP {exc.code}")
        except Exception as exc:
            return ApiResult(ok=False, status=0, body={}, error=str(exc))


class InProcessApiClient:
    def __init__(self):
        from quantdog.api import create_app

        app = create_app()
        self.client = app.test_client()

    def post(self, path: str, payload: dict[str, Any]) -> ApiResult:
        resp = self.client.post(path, json=payload)
        return ApiResult(ok=200 <= resp.status_code < 300, status=resp.status_code, body=resp.get_json() or {})

    def get(self, path: str, query: dict[str, Any] | None = None) -> ApiResult:
        resp = self.client.get(path, query_string=query)
        return ApiResult(ok=200 <= resp.status_code < 300, status=resp.status_code, body=resp.get_json() or {})


def _print_section(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def _clip_list(value: list[Any], max_items: int) -> list[Any]:
    return value[: max(1, max_items)]


def _to_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _extract_item_score(item: dict[str, Any], *, kind: str) -> float | None:
    raw_value = item.get("raw")
    raw: dict[str, Any] = raw_value if isinstance(raw_value, dict) else {}
    ai_rating_value = raw.get("aiRating")
    ai_rating: dict[str, Any] = ai_rating_value if isinstance(ai_rating_value, dict) else {}

    for candidate in (
        item.get("score"),
        item.get("sentiment_score"),
        item.get("rank_score"),
        raw.get("score"),
        ai_rating.get("score"),
    ):
        score = _to_number(candidate)
        if score is not None:
            return score

    if kind == "twitter":
        likes = _to_number(item.get("likes")) or 0.0
        retweets = _to_number(item.get("retweets")) or 0.0
        replies = _to_number(item.get("replies")) or 0.0
        view_count = _to_number(item.get("view_count")) or 0.0
        return (likes * 1.0) + (retweets * 2.0) + (replies * 1.5) + (view_count / 1000.0)

    return None


def _high_score_threshold(scores: list[float], *, kind: str) -> float:
    max_score = max(scores)
    min_score = min(scores)
    if -1.0 <= min_score and max_score <= 1.0:
        base = 0.3 if kind == "news" else 0.2
    elif max_score <= 10.0:
        base = 6.0 if kind == "news" else 5.0
    else:
        base = 60.0 if kind == "news" else 40.0
    return max(base, max_score * 0.6)


def _filter_high_score_items(items: list[Any], *, kind: str, max_items: int) -> list[dict[str, Any]]:
    dict_items = [item for item in items if isinstance(item, dict)]
    if not dict_items:
        return []

    scored: list[tuple[dict[str, Any], float]] = []
    for item in dict_items:
        score = _extract_item_score(item, kind=kind)
        if score is not None:
            scored.append((item, score))

    if not scored:
        return []

    threshold = _high_score_threshold([score for _, score in scored], kind=kind)
    selected = [item for item, score in scored if score >= threshold]
    return _clip_list(selected, max_items)


def _data_of(result: ApiResult) -> dict[str, Any]:
    if not result.ok:
        return {}
    if not isinstance(result.body, dict):
        return {}
    payload = result.body.get("data")
    return payload if isinstance(payload, dict) else {}


def _filter_news_twitter_payload(value: Any, *, max_items: int) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item_value in value.items():
            if key == "news" and isinstance(item_value, list):
                out[key] = _filter_high_score_items(item_value, kind="news", max_items=max_items)
            elif key == "twitter" and isinstance(item_value, list):
                out[key] = _filter_high_score_items(item_value, kind="twitter", max_items=max_items)
            else:
                out[key] = _filter_news_twitter_payload(item_value, max_items=max_items)
        return out

    if isinstance(value, list):
        return [_filter_news_twitter_payload(item, max_items=max_items) for item in value]

    return value


def _short_text(value: Any, *, max_len: int = 80) -> str:
    text = str(value or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _short_text_keep_tail_parens(value: Any, *, max_len: int = 90) -> str:
    text = str(value or "").strip()
    if len(text) <= max_len:
        return text

    right = text.rfind(")")
    left = text.rfind("(", 0, right) if right != -1 else -1
    if left != -1 and right == len(text) - 1 and left < right:
        tail = text[left:]
        if len(tail) < max_len - 8:
            head_room = max_len - len(tail) - 1
            if head_room > 0:
                head = text[:head_room].rstrip()
                return f"{head}…{tail}"

    return _short_text(text, max_len=max_len)


def _fmt_number(value: Any, digits: int = 2) -> str:
    num = _to_number(value)
    if num is None:
        return "n/a"
    return f"{num:.{digits}f}"


def _build_final_advice(
    *,
    decision: str,
    confidence_value: Any,
    combined_score: Any,
    risk_regime: str,
) -> str:
    confidence_num = _to_number(confidence_value) or 0.0
    combined_num = _to_number(combined_score)

    if decision == "BUY" and confidence_num >= 70:
        return f"偏多，建议分批布局并设置止损；当前风控状态={risk_regime or 'unknown'}。"
    if decision == "SELL" and confidence_num >= 70:
        return f"偏空，建议控制仓位或等待回撤确认；当前风控状态={risk_regime or 'unknown'}。"
    if combined_num is not None and abs(combined_num) < 0.4:
        return "信号分歧较大，建议先观察，等待技术与情绪进一步共振。"
    return "中性偏谨慎，建议小仓位试错并严格执行风控。"


def _build_tweet(symbol: str, payloads: dict[str, dict[str, Any]]) -> str:
    strategy = payloads.get("strategy") or {}
    technical = payloads.get("technical") or {}
    intel = payloads.get("intel") or {}
    macro = payloads.get("macro") or {}

    technical_analysis_raw = technical.get("analysis")
    technical_analysis: dict[str, Any] = technical_analysis_raw if isinstance(technical_analysis_raw, dict) else {}

    decision = str(strategy.get("decision") or technical_analysis.get("decision") or "HOLD")
    confidence_value = strategy.get("confidence")
    if confidence_value is None:
        confidence_value = technical_analysis.get("confidence")
    raw_reasons = technical_analysis.get("reasons")
    reasons: list[str] = [str(item).strip() for item in raw_reasons if str(item).strip()] if isinstance(raw_reasons, list) else []

    macro_snapshot_raw = macro.get("snapshot")
    macro_snapshot: dict[str, Any] = macro_snapshot_raw if isinstance(macro_snapshot_raw, dict) else {}

    indicators_raw = technical.get("indicators")
    indicators: dict[str, Any] = indicators_raw if isinstance(indicators_raw, dict) else {}
    risk_filter_raw = strategy.get("risk_filter")
    risk_filter: dict[str, Any] = risk_filter_raw if isinstance(risk_filter_raw, dict) else {}
    confirmations_raw = strategy.get("confirmations")
    confirmations: dict[str, Any] = confirmations_raw if isinstance(confirmations_raw, dict) else {}
    risk_regime = str(risk_filter.get("regime") or "unknown")
    combined_score = strategy.get("combined_score")
    vix_value = risk_filter.get("vix")
    vix_rule = _short_text(risk_filter.get("rule"), max_len=120)
    c1_rollover = confirmations.get("c1_vix_rollover")
    confirm_true_count = confirmations.get("true_count")
    confirm_unknown_count = confirmations.get("unknown_count")

    news_raw = intel.get("news")
    twitter_raw = intel.get("twitter")
    news_items: list[Any] = news_raw if isinstance(news_raw, list) else []
    twitter_items: list[Any] = twitter_raw if isinstance(twitter_raw, list) else []
    top_news = _filter_high_score_items(news_items, kind="news", max_items=1)
    top_twitter = _filter_high_score_items(twitter_items, kind="twitter", max_items=1)

    news_headline = ""
    if top_news:
        headline = _short_text_keep_tail_parens(top_news[0].get("headline"), max_len=120)
        news_headline = headline if headline else ""

    twitter_snippet = ""
    if top_twitter:
        text = _short_text_keep_tail_parens(top_twitter[0].get("text"), max_len=120)
        twitter_snippet = text if text else ""

    advice = _build_final_advice(
        decision=decision,
        confidence_value=confidence_value,
        combined_score=combined_score,
        risk_regime=risk_regime,
    )

    tech_line = (
        f"技术指标: 决策={decision}, 置信度={confidence_value if confidence_value is not None else 'n/a'}, "
        f"score={_fmt_number(combined_score, 3)}, close={_fmt_number(indicators.get('latest_price') if indicators.get('latest_price') is not None else indicators.get('last_close'))}, "
        f"SMA20={_fmt_number(indicators.get('sma20'))}, SMA50={_fmt_number(indicators.get('sma50'))}, "
        f"RSI14={_fmt_number(indicators.get('rsi14'))}, MACD={_fmt_number(indicators.get('macd'), 3)}"
    )
    macro_snapshot_line = (
        "宏观数据: "
        f"TIPS10Y={_fmt_number(macro_snapshot.get('tips_10y'), 3)}, "
        f"US10Y={_fmt_number(macro_snapshot.get('yield_10y'), 3)}, "
        f"US2Y={_fmt_number(macro_snapshot.get('yield_2y'), 3)}, "
        f"10Y2Y={_fmt_number(macro_snapshot.get('yield_spread'), 3)}, "
        f"Fed={_fmt_number(macro_snapshot.get('fed_rate'), 3)}, "
        f"CPI={_fmt_number(macro_snapshot.get('cpi'), 3)}, "
        f"CoreCPI={_fmt_number(macro_snapshot.get('core_cpi'), 3)}, "
        f"DXY={_fmt_number(macro_snapshot.get('dxy'), 3)}, "
        f"BE10Y={_fmt_number(macro_snapshot.get('breakeven'), 3)}, "
        f"Cu/Au={_fmt_number(macro_snapshot.get('copper_gold_ratio'), 4)}"
    )
    vix_line = (
        f"VIX分析: vix={_fmt_number(vix_value, 3)}, regime={risk_regime}, "
        f"c1_vix_rollover={c1_rollover}, confirm_true={confirm_true_count}, "
        f"confirm_unknown={confirm_unknown_count}, 规则={vix_rule or 'n/a'}"
    )
    news_line = f"新闻: {news_headline or '无高分新闻'}"
    twitter_line = f"Twitter: {twitter_snippet or '无高分Twitter'}"
    advice_line = f"建议: {advice}"
    reasons_line = "技术依据: " + (
        "; ".join(_short_text(reason, max_len=56) for reason in reasons[:3])
        if reasons
        else "暂无"
    )

    return "\n".join(
        [
            f"【{symbol.upper()} 市场推文草稿】",
            tech_line,
            reasons_line,
            macro_snapshot_line,
            vix_line,
            news_line,
            twitter_line,
            advice_line,
            "#QuantDog #USStocks",
        ]
    )


def _format_data_for_output(data: Any, detail: str, max_items: int) -> Any:
    if detail == "full":
        return _filter_news_twitter_payload(data, max_items=max_items)
    if not isinstance(data, dict):
        return data

    out: dict[str, Any] = {}

    for key in [
        "symbol",
        "decision",
        "confidence",
        "combined_score",
        "sentiment",
        "sentiment_score",
        "macro_theme",
        "news_count",
        "twitter_count",
        "has_alert",
        "count",
        "latest_price",
    ]:
        if key in data:
            out[key] = data.get(key)

    if "risk_filter" in data and isinstance(data["risk_filter"], dict):
        rf = data["risk_filter"]
        out["risk_filter"] = {
            "vix": rf.get("vix"),
            "regime": rf.get("regime"),
            "cash_target_pct": rf.get("cash_target_pct"),
            "allow_high_beta": rf.get("allow_high_beta"),
            "index_dip_buy_zone": rf.get("index_dip_buy_zone"),
            "rule": rf.get("rule"),
        }

    if "confirmations" in data and isinstance(data["confirmations"], dict):
        c = data["confirmations"]
        out["confirmations"] = {
            "c1_vix_rollover": c.get("c1_vix_rollover"),
            "c2_tightening_chain_not_worsening": c.get("c2_tightening_chain_not_worsening"),
            "c3_xle_momo_ratio_not_expanding": c.get("c3_xle_momo_ratio_not_expanding"),
            "true_count": c.get("true_count"),
            "unknown_count": c.get("unknown_count"),
            "xle_qqq_ratio_now": c.get("xle_qqq_ratio_now"),
            "xle_qqq_ratio_prev": c.get("xle_qqq_ratio_prev"),
        }

    if "analysis" in data and isinstance(data["analysis"], dict):
        out["analysis"] = {
            "decision": data["analysis"].get("decision"),
            "confidence": data["analysis"].get("confidence"),
            "score": data["analysis"].get("score"),
            "reasons": _clip_list(data["analysis"].get("reasons") or [], max_items),
        }

    if "indicators" in data and isinstance(data["indicators"], dict):
        indicators = data["indicators"]
        out["indicators"] = {
            "latest_price": indicators.get("latest_price"),
            "last_close": indicators.get("last_close"),
            "sma20": indicators.get("sma20"),
            "sma50": indicators.get("sma50"),
            "rsi14": indicators.get("rsi14"),
            "macd": indicators.get("macd"),
            "macd_histogram": indicators.get("macd_histogram"),
            "recent_high": indicators.get("recent_high"),
            "recent_low": indicators.get("recent_low"),
        }

    if "keyword_hits" in data:
        out["keyword_hits"] = data.get("keyword_hits")

    if "news" in data and isinstance(data["news"], list):
        filtered_news = _filter_high_score_items(data["news"], kind="news", max_items=max_items)
        news_items = []
        for item in filtered_news:
            if isinstance(item, dict):
                news_items.append(
                    {
                        "headline": item.get("headline"),
                        "source": item.get("source"),
                        "published_at": item.get("published_at") or item.get("ts"),
                        "signal": item.get("signal"),
                        "score": _extract_item_score(item, kind="news"),
                        "url": item.get("url"),
                    }
                )
        out["news"] = news_items

    if "twitter" in data and isinstance(data["twitter"], list):
        filtered_twitter = _filter_high_score_items(data["twitter"], kind="twitter", max_items=max_items)
        tw_items = []
        for item in filtered_twitter:
            if isinstance(item, dict):
                tw_items.append(
                    {
                        "user": item.get("user"),
                        "text": item.get("text"),
                        "created_at": item.get("created_at"),
                        "likes": item.get("likes"),
                        "retweets": item.get("retweets"),
                        "url": item.get("url"),
                    }
                )
        out["twitter"] = tw_items

    if "snapshot" in data:
        snapshot_value = data.get("snapshot")
        out["snapshot"] = _filter_news_twitter_payload(snapshot_value, max_items=max_items)

    if detail == "summary":
        return out

    # standard detail: keep all important top-level fields if present
    for key in ["horizon", "bars_count", "inputs", "note", "alerts", "results"]:
        if key in data:
            value = data.get(key)
            if key in {"alerts", "results"} and isinstance(value, list):
                out[key] = _filter_news_twitter_payload(_clip_list(value, max_items), max_items=max_items)
            else:
                out[key] = value
    return out


def _print_result(label: str, result: ApiResult, detail: str, max_items: int) -> None:
    status = "OK" if result.ok else "FAIL"
    print(f"[{status}] {label} (status={result.status})")
    if result.ok:
        data = result.body.get("data") if isinstance(result.body, dict) else result.body
        formatted = _format_data_for_output(data, detail=detail, max_items=max_items)
        print(f"  data: {json.dumps(formatted, ensure_ascii=False)}")
    else:
        msg = result.error or "request failed"
        print(f"  error: {msg}")
        if isinstance(result.body, dict) and result.body:
            print(f"  body: {json.dumps(result.body, ensure_ascii=False)}")


def run_analysis(
    client,
    symbols: list[str],
    horizon: str,
    limit: int,
    detail: str,
    max_items: int,
) -> int:
    failures = 0
    _print_section("US Stock Analysis Client")
    print(f"symbols: {', '.join(symbols)}")
    print(f"horizon: {horizon}, limit: {limit}")

    for symbol in symbols:
        _print_section(f"Symbol {symbol}")

        technical = client.post("/api/v1/market/technical", {"symbol": symbol, "horizon": horizon})
        _print_result("technical", technical, detail, max_items)
        failures += 0 if technical.ok else 1
        technical_data = _data_of(technical)

        intel = client.post("/api/v1/market/intel", {"symbol": symbol, "limit": limit})
        _print_result("intel(news+twitter)", intel, detail, max_items)
        failures += 0 if intel.ok else 1
        intel_data = _data_of(intel)

        macro = client.post("/api/v1/market/macro", {"symbol": symbol, "limit": limit})
        _print_result("macro", macro, detail, max_items)
        failures += 0 if macro.ok else 1
        macro_data = _data_of(macro)

        strategy = client.post(f"/api/v1/stocks/{symbol}/strategy", {"horizon": horizon, "limit": limit})
        _print_result("strategy", strategy, detail, max_items)
        failures += 0 if strategy.ok else 1
        strategy_data = _data_of(strategy)

        monitor = client.get(f"/api/v1/stocks/{symbol}/monitor", {"horizon": horizon, "limit": limit})
        _print_result("monitor", monitor, detail, max_items)
        failures += 0 if monitor.ok else 1
        monitor_data = _data_of(monitor)

        tweet = _build_tweet(
            symbol,
            {
                "technical": technical_data,
                "intel": intel_data,
                "macro": macro_data,
                "strategy": strategy_data,
                "monitor": monitor_data,
            },
        )
        print("  tweet:")
        for line in tweet.splitlines():
            print(f"    {line}")

    _print_section("Batch Monitor")
    batch = client.post("/api/v1/stocks/monitor", {"symbols": symbols, "horizon": horizon, "limit": limit})
    _print_result("stocks/monitor(batch)", batch, detail, max_items)
    failures += 0 if batch.ok else 1

    print("\nDone.")
    return 1 if failures > 0 else 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="US stock analysis client for QuantDog API")
    parser.add_argument("--symbols", default="TSLA,AAPL,MSFT", help="Comma-separated US stock symbols")
    parser.add_argument("--horizon", default="1d", help="Analysis horizon, e.g. 1d/1w/1m")
    parser.add_argument("--limit", type=int, default=20, help="News/twitter item limit")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL for HTTP mode")
    parser.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout seconds")
    parser.add_argument(
        "--detail",
        default="summary",
        choices=["summary", "standard", "full"],
        help="Output detail level",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=5,
        help="Max news/twitter/list items to display for summary/standard",
    )
    parser.add_argument(
        "--inprocess",
        action="store_true",
        help="Use Flask test_client in-process (no external API server needed)",
    )
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    if not symbols:
        print("No symbols provided.", file=sys.stderr)
        return 2

    if args.inprocess:
        client = InProcessApiClient()
    else:
        client = HttpApiClient(args.base_url, timeout_seconds=args.timeout)

    return run_analysis(
        client,
        symbols,
        args.horizon,
        args.limit,
        detail=args.detail,
        max_items=args.max_items,
    )


if __name__ == "__main__":
    raise SystemExit(main())
