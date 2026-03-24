# -*- coding: utf-8 -*-
"""
US Sector Stock Screening Module

Provides sector-based stock screening for daily watchlist generation.

Features:
- Top 10 US sectors with representative stocks
- Technical analysis filtering (baseline)
- AI research for final recommendations
"""

import yfinance as yf
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime, timedelta


# Top 10 US sector ETFs and their sectors
SECTOR_ETF_MAP = {
    "XLK": "Technology",
    "XLV": "Healthcare",
    "XLF": "Financial Services",
    "XLI": "Industrials",
    "XLB": "Materials",
    "XLRE": "Real Estate",
    "XLE": "Energy",
    "XLU": "Utilities",
    "XLP": "Consumer Staples",
    "XLY": "Consumer Discretionary",
}


@dataclass
class SectorStock:
    """Represents a stock in a sector."""
    symbol: str
    name: str
    sector: str
    weight: float  # Weight in sector ETF
    market_cap: float = 0.0


@dataclass
class ScreeningResult:
    """Result of screening a stock."""
    symbol: str
    sector: str
    technical_score: float
    technical_decision: str
    technical_confidence: int
    technical_reasons: List[str]
    ai_decision: Optional[str] = None
    ai_confidence: Optional[int] = None
    composite_score: float = 0.0


class SectorProvider:
    """Provides sector and stock information."""

    def __init__(self, top_stocks_per_sector: int = 10):
        self.top_stocks_per_sector = top_stocks_per_sector

    def get_sector_stocks(self, sectors: Optional[List[str]] = None) -> List[SectorStock]:
        """
        Get top stocks for each sector.

        Args:
            sectors: List of sector names to fetch. If None, fetch all top 10 sectors.

        Returns:
            List of SectorStock objects
        """
        if sectors is None:
            # Use all top 10 sectors
            sectors = list(SECTOR_ETF_MAP.values())

        all_stocks = []

        for etf_ticker, sector_name in SECTOR_ETF_MAP.items():
            if sector_name not in sectors:
                continue

            print(f"  Fetching top {self.top_stocks_per_sector} stocks for {sector_name} ({etf_ticker})...")

            try:
                # Get sector ETF info to parse holdings
                etf = yf.Ticker(etf_ticker)
                info = etf.info

                # Method 1: Try to use .holdings (yfinance feature)
                # Note: yfinance doesn't directly provide holdings for all ETFs
                # We'll use a predefined list of top stocks per sector

                # For now, use predefined representative stocks
                sector_data = self._get_sector_representatives(sector_name)

                for symbol, name, weight in sector_data:
                    stock = SectorStock(
                        symbol=symbol,
                        name=name,
                        sector=sector_name,
                        weight=weight,
                    )
                    all_stocks.append(stock)

                print(f"    Loaded {len(sector_data)} stocks for {sector_name}")

            except Exception as e:
                print(f"    Warning: Failed to fetch {etf_ticker}: {e}")
                continue

        return all_stocks

    def _get_sector_representatives(self, sector_name: str) -> List[tuple]:
        """
        Get representative stocks for a sector.

        Returns list of (symbol, name, weight) tuples.

        Note: In production, this should fetch from reliable data sources.
        For now, using well-known top stocks per sector.
        """
        # Predefined top stocks per sector (symbol, name, weight)
        sector_mappings = {
            "Technology": [
                ("AAPL", "Apple Inc.", 0.15),
                ("MSFT", "Microsoft Corporation", 0.14),
                ("NVDA", "NVIDIA Corporation", 0.13),
                ("GOOGL", "Alphabet Inc.", 0.08),
                ("META", "Meta Platforms Inc.", 0.07),
                ("TSLA", "Tesla Inc.", 0.06),
                ("AMD", "Advanced Micro Devices", 0.05),
                ("INTC", "Intel Corporation", 0.04),
                ("CSCO", "Cisco Systems Inc.", 0.04),
                ("ORCL", "Oracle Corporation", 0.04),
            ],
            "Healthcare": [
                ("JNJ", "Johnson & Johnson", 0.12),
                ("UNH", "UnitedHealth Group", 0.11),
                ("PFE", "Pfizer Inc.", 0.08),
                ("ABBV", "AbbVie Inc.", 0.07),
                ("TMO", "Thermo Fisher Scientific", 0.06),
                ("MRK", "Merck & Co. Inc.", 0.06),
                ("ABT", "Abbott Laboratories", 0.05),
                ("LLY", "Eli Lilly and Company", 0.05),
                ("DHR", "Danaher Corporation", 0.05),
                ("BMY", "Bristol-Myers Squibb", 0.04),
            ],
            "Financial Services": [
                ("BRK.B", "Berkshire Hathaway Inc.", 0.14),
                ("JPM", "JPMorgan Chase & Co.", 0.13),
                ("V", "Visa Inc.", 0.10),
                ("MA", "Mastercard Incorporated", 0.08),
                ("BAC", "Bank of America Corporation", 0.07),
                ("WFC", "Wells Fargo & Company", 0.06),
                ("GS", "Goldman Sachs Group Inc.", 0.05),
                ("MS", "Morgan Stanley", 0.05),
                ("SCHW", "Charles Schwab Corporation", 0.04),
                ("BLK", "BlackRock Inc.", 0.04),
            ],
            "Industrials": [
                ("GE", "General Electric Company", 0.10),
                ("CAT", "Caterpillar Inc.", 0.08),
                ("HON", "Honeywell International Inc.", 0.07),
                ("DE", "Deere & Company", 0.06),
                ("UPS", "United Parcel Service Inc.", 0.05),
                ("BA", "Boeing Company", 0.05),
                ("RTX", "Raytheon Technologies Corporation", 0.05),
                ("LMT", "Lockheed Martin Corporation", 0.04),
                ("EMR", "Emerson Electric Co.", 0.04),
                ("MMM", "3M Company", 0.04),
            ],
            "Materials": [
                ("LIN", "Linde plc", 0.15),
                ("APD", "Air Products and Chemicals Inc.", 0.10),
                ("DOW", "Dow Inc.", 0.09),
                ("SHW", "Sherwin-Williams Company", 0.08),
                ("NEM", "Newmont Corporation", 0.07),
                ("FCX", "Freeport-McMoRan Inc.", 0.06),
                ("PPG", "PPG Industries Inc.", 0.05),
                ("DD", "DuPont de Nemours Inc.", 0.05),
                ("ALB", "Albemarle Corporation", 0.04),
                ("VMC", "Vulcan Materials Company", 0.04),
            ],
            "Real Estate": [
                ("PLD", "Prologis Inc.", 0.10),
                ("AMT", "American Tower Corporation", 0.09),
                ("CCI", "Crown Castle International Corp.", 0.07),
                ("EQIX", "Equinix Inc.", 0.06),
                ("SPG", "Simon Property Group Inc.", 0.05),
                ("PSA", "Public Storage", 0.05),
                ("WELL", "Welltower Inc.", 0.04),
                ("O", "Realty Income Corporation", 0.04),
                ("DLR", "Digital Realty Trust Inc.", 0.04),
                ("CBRE", "CBRE Group Inc.", 0.03),
            ],
            "Energy": [
                ("XOM", "Exxon Mobil Corporation", 0.12),
                ("CVX", "Chevron Corporation", 0.11),
                ("COP", "ConocoPhillips", 0.08),
                ("EOG", "EOG Resources Inc.", 0.06),
                ("SLB", "Schlumberger Limited", 0.06),
                ("PSX", "Phillips 66", 0.04),
                ("MPC", "Marathon Petroleum Corporation", 0.05),
                ("PSX", "Phillips 66", 0.04),
                ("VLO", "Valero Energy Corporation", 0.04),
                ("OXY", "Occidental Petroleum Corporation", 0.03),
            ],
            "Utilities": [
                ("NEE", "NextEra Energy Inc.", 0.12),
                ("D", "Dominion Energy Inc.", 0.07),
                ("DUK", "Duke Energy Corporation", 0.07),
                ("SO", "Southern Company", 0.06),
                ("AEP", "American Electric Power Company", 0.05),
                ("EXC", "Exelon Corporation", 0.05),
                ("SRE", "Sempra Energy", 0.04),
                ("WEC", "WEC Energy Group Inc.", 0.04),
                ("ED", "Consolidated Edison Inc.", 0.03),
                ("XEL", "Xcel Energy Inc.", 0.03),
            ],
            "Consumer Staples": [
                ("PG", "Procter & Gamble Company", 0.13),
                ("KO", "Coca-Cola Company", 0.10),
                ("PEP", "PepsiCo Inc.", 0.09),
                ("WMT", "Walmart Inc.", 0.08),
                ("COST", "Costco Wholesale Corporation", 0.06),
                ("PM", "Philip Morris International Inc.", 0.05),
                ("MO", "Altria Group Inc.", 0.04),
                ("CL", "Colgate-Palmolive Company", 0.04),
                ("KMB", "Kimberly-Clark Corporation", 0.03),
                ("GIS", "General Mills Inc.", 0.03),
            ],
            "Consumer Discretionary": [
                ("AMZN", "Amazon.com Inc.", 0.15),
                ("TSLA", "Tesla Inc.", 0.10),
                ("HD", "Home Depot Inc.", 0.08),
                ("MCD", "McDonald's Corporation", 0.07),
                ("NKE", "Nike Inc.", 0.06),
                ("SBUX", "Starbucks Corporation", 0.05),
                ("LOW", "Lowe's Companies Inc.", 0.04),
                ("TJX", "TJX Companies Inc.", 0.04),
                ("BKNG", "Booking Holdings Inc.", 0.03),
                ("ETSY", "Etsy Inc.", 0.02),
            ],
        }

        return sector_mappings.get(sector_name, [])


class SectorScreeningService:
    """Screens stocks across sectors using technical and AI analysis."""

    def __init__(
        self,
        sector_provider: SectorProvider,
        min_technical_confidence: int = 60,
        max_stocks_per_sector: int = 3,
        show_all_signals: bool = False,
        min_score: float | None = None,
    ):
        self.sector_provider = sector_provider
        self.min_technical_confidence = min_technical_confidence
        self.max_stocks_per_sector = max_stocks_per_sector
        self.show_all_signals = show_all_signals
        self.min_score = min_score

    def generate_watchlist(self, enable_ai_research: bool = False) -> Dict[str, List[ScreeningResult]]:
        """
        Generate daily watchlist by screening stocks across sectors.

        Args:
            enable_ai_research: If True, run AI research on top technical candidates

        Returns:
            Dictionary mapping sector names to list of screening results
        """
        print()
        print("=" * 80)
        print("Generating Sector-Based Watchlist")
        print("=" * 80)
        print()

        # Step 1: Get sector stocks
        print("[1/4] Fetching sector stocks...")
        all_stocks = self.sector_provider.get_sector_stocks()
        print(f"  Total stocks to screen: {len(all_stocks)}")
        print()

        # Group by sector
        sector_stocks: Dict[str, List[SectorStock]] = {}
        for stock in all_stocks:
            if stock.sector not in sector_stocks:
                sector_stocks[stock.sector] = []
            sector_stocks[stock.sector].append(stock)

        # Step 2: Technical analysis screening
        print("[2/4] Running technical analysis on all stocks...")
        watchlist: Dict[str, List[ScreeningResult]] = {}

        for sector, stocks in sector_stocks.items():
            print(f"  Screening {sector} ({len(stocks)} stocks)...")
            results = self._screen_sector(stocks)
            watchlist[sector] = results

        print()

        # Step 3: AI research on top candidates (if enabled)
        if enable_ai_research:
            print("[3/4] Running AI research on top technical candidates...")
            for sector, results in watchlist.items():
                top_results = results[:self.max_stocks_per_sector]
                for result in top_results:
                    self._run_ai_research(result)
            print()

        # Step 4: Rank by composite score
        print("[4/4] Ranking and finalizing watchlist...")
        for sector, results in watchlist.items():
            watchlist[sector] = self._rank_results(results)[:self.max_stocks_per_sector]

        print()
        return watchlist

    def _screen_sector(self, stocks: List[SectorStock]) -> List[ScreeningResult]:
        """Screen stocks in a sector using technical analysis."""
        from api.analysis import generate_baseline_analysis
        from analysis.indicators import calculate_indicators
        from infra.providers import get_provider
        from datetime import timedelta

        provider = get_provider()
        results = []

        # Get date range - last 90 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        for stock in stocks:
            try:
                # Fetch OHLCV data
                bars = provider.fetch_bars_1d(stock.symbol, start_str, end_str, adjusted=True)

                if not bars or len(bars) < 20:
                    continue

                # Calculate technical indicators
                indicators = calculate_indicators(bars)

                # Generate baseline analysis
                analysis = generate_baseline_analysis(stock.symbol, indicators)

                # Filter by confidence OR by BUY/SELL decision if all_signals mode
                # OR by score if min_score is specified
                should_include = False
                if analysis["confidence"] >= self.min_technical_confidence:
                    should_include = True
                elif self.show_all_signals and analysis["decision"] != "HOLD":
                    should_include = True
                elif self.min_score is not None and analysis["score"] >= self.min_score:
                    should_include = True

                if not should_include:
                    continue

                result = ScreeningResult(
                    symbol=stock.symbol,
                    sector=stock.sector,
                    technical_score=analysis["score"],
                    technical_decision=analysis["decision"],
                    technical_confidence=analysis["confidence"],
                    technical_reasons=analysis["reasons"],
                )
                results.append(result)

            except Exception as e:
                # Skip stocks that fail analysis
                continue

        # Sort by technical score
        results.sort(key=lambda x: x.technical_score, reverse=True)
        return results

    def _run_ai_research(self, result: ScreeningResult) -> None:
        """Run AI research on a screening result."""
        from research.orchestrator import ResearchOrchestrator
        from research.llm_client import MultiProviderLLMClient
        from config import get_settings
        from analysis.indicators import calculate_indicators
        from infra.providers import get_provider
        from research.models import RunContext, Horizon
        from datetime import datetime, timedelta

        try:
            # Fetch data for AI analysis
            provider = get_provider()
            end_date = datetime.now()
            start_date = end_date - timedelta(days=180)
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")

            bars = provider.fetch_bars_1d(result.symbol, start_str, end_str, adjusted=True)

            if not bars or len(bars) < 50:
                return

            indicators = calculate_indicators(bars)

            # Build context
            current_price = bars[-1]["close"]
            min_price = min(b["close"] for b in bars)
            max_price = max(b["close"] for b in bars)

            bars_summary = {
                "symbol": result.symbol,
                "current_price": f"${current_price:.2f}",
                "range": f"${min_price:.2f} - ${max_price:.2f}",
                "bars_count": len(bars),
                "date_range": f"{start_str} to {end_str}",
            }

            context = RunContext(
                symbol=result.symbol,
                as_of=datetime.now().strftime("%Y-%m-%d"),
                horizon=Horizon.ONE_WEEK,
                language="en",
                bars_summary=bars_summary,
                indicators=indicators,
                fundamentals={"note": "Real-time fundamental analysis not available in CLI mode"},
                news=[],
                sentiment_context={"note": "Real-time sentiment analysis not available in CLI mode"},
            )

            # Run AI research
            settings = get_settings()

            if not settings.database_url:
                print(f"    Warning: DATABASE_URL not configured, skipping AI research for {result.symbol}")
                return

            llm_client = MultiProviderLLMClient()
            orchestrator = ResearchOrchestrator(
                database_url=settings.database_url,
                llm_client=llm_client,
                per_agent_timeout=30.0,
                max_wall_time=120.0,
            )

            research_result = orchestrator.run_research(
                symbol=result.symbol,
                horizon=Horizon.ONE_WEEK,
            )

            # Update result with AI findings
            result.ai_decision = research_result.get("final_decision")
            result.ai_confidence = research_result.get("final_confidence", 0)

            if not result.ai_decision or result.ai_confidence is None:
                result.ai_decision = "HOLD"
                result.ai_confidence = 50

            # Calculate composite score (60% technical + 40% AI)
            technical_normalized = result.technical_score / 2.0  # Range -1 to 1 normalized to -0.5 to 0.5
            ai_normalized = (result.ai_confidence / 100.0) - 0.5  # Range 0-100 to -0.5 to 0.5

            if result.ai_decision == "BUY":
                ai_normalized = abs(ai_normalized)
            elif result.ai_decision == "SELL":
                ai_normalized = -abs(ai_normalized)
            else:  # HOLD
                ai_normalized = 0

            result.composite_score = 0.6 * technical_normalized + 0.4 * ai_normalized

        except Exception as e:
            # Skip AI research on error
            print(f"    Warning: AI research failed for {result.symbol}: {e}")

    def _rank_results(self, results: List[ScreeningResult]) -> List[ScreeningResult]:
        """Rank results by composite score."""
        results.sort(key=lambda x: x.composite_score, reverse=True)
        return results


def display_watchlist(watchlist: Dict[str, List[ScreeningResult]]) -> None:
    """Display the watchlist in a readable format."""
    print()
    print("=" * 80)
    print("DAILY WATCHLIST RECOMMENDATIONS")
    print("=" * 80)
    print()

    for sector, results in watchlist.items():
        if not results:
            continue

        print(f"--- {sector.upper()} ---")
        print()

        for i, result in enumerate(results, 1):
            print(f"[{i}] {result.symbol}")
            print(f"    Technical: {result.technical_decision} ({result.technical_confidence}%)")
            print(f"    Score: {result.technical_score:.2f}")
            print(f"    Reasons: {'; '.join(result.technical_reasons[:2])}")

            if result.ai_decision:
                print(f"    AI: {result.ai_decision} ({result.ai_confidence}%)")
                print(f"    Composite: {result.composite_score:.2f}")

            print()

    print("=" * 80)
    print(f"HIGH CONFIDENCE BUY SIGNALS: {sum(1 for r in [item for results in watchlist.values() for item in results] if r.technical_decision == 'BUY' and r.technical_confidence >= 70)}")
    print("=" * 80)
