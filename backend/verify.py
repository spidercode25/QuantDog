from infra.providers import get_provider
from analysis.indicators import calculate_indicators
from analysis.baseline import generate_baseline_analysis

print('=== QuantDog Migration Verification ===')
print()

provider = get_provider()
bars = provider.fetch_bars_1d('700.HK', '2026-01-01', '2026-03-24', adjusted=True)

if bars:
    print(f'[OK] Fetched {len(bars)} bars from Longbridge')
    print(f'Latest close: ${bars[-1]["close"]:.2f}')
    print()

    indicators = calculate_indicators(bars)
    print(f'[OK] Indicators calculated:')
    print(f'  SMA20: ${indicators["sma20"]:.2f}')
    print(f'  RSI14: {indicators["rsi14"]:.2f}')
    print()

    analysis = generate_baseline_analysis('700.HK', indicators)
    print(f'[OK] Analysis:')
    print(f'  Decision: {analysis["decision"]}')
    print(f'  Confidence: {analysis["confidence"]}%')
    print(f'  Score: {analysis["score"]:.2f}')
    print()
    print('[SUCCESS] Migration verified - all core functions working')
else:
    print('[ERROR] Failed to fetch data')
