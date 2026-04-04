from datetime import datetime, timezone
from typing import List, Optional
from models.schemas import AssetPrice, MarketContext, BaseSignal


PRICE_CHANGE_THRESHOLD = 1.0  # percent
HIGH_CONFIDENCE_BASE = 0.55
SIGNAL_BOOST = 0.05


def _trend(change: float) -> str:
    if change > 2.0:
        return "strong_up"
    if change > 0.5:
        return "up"
    if change < -2.0:
        return "strong_down"
    if change < -0.5:
        return "down"
    return "neutral"


def _sentiment_signal(sentiment: float) -> str:
    if sentiment > 0.1:
        return "BUY"
    if sentiment < -0.1:
        return "SELL"
    return "HOLD"


def generate_signal(
    asset: AssetPrice,
    context: Optional[MarketContext],
) -> BaseSignal:
    drivers: List[str] = []
    confidence = HIGH_CONFIDENCE_BASE
    signal_votes = {"BUY": 0, "SELL": 0, "HOLD": 0}

    # Price momentum
    chg = asset.change_24h or 0.0
    trend = _trend(chg)

    if abs(chg) >= PRICE_CHANGE_THRESHOLD:
        if chg > 0:
            signal_votes["BUY"] += 2
            confidence += SIGNAL_BOOST
            drivers.append(f"Price up {chg:.2f}% in 24h")
        else:
            signal_votes["SELL"] += 2
            confidence += SIGNAL_BOOST
            drivers.append(f"Price down {abs(chg):.2f}% in 24h")
    else:
        signal_votes["HOLD"] += 1
        drivers.append("Price stable (<1% change)")

    if context:
        # USD index influence (inverse for commodities/crypto)
        if context.usd_index is not None:
            if context.usd_index > 105:
                signal_votes["SELL"] += 1
                drivers.append(f"Strong USD (index {context.usd_index:.1f}) — headwind")
            elif context.usd_index < 102:
                signal_votes["BUY"] += 1
                drivers.append(f"Weak USD (index {context.usd_index:.1f}) — tailwind")

        # Bond yields
        if context.bond_yield_10y is not None:
            if context.bond_yield_10y > 4.5:
                signal_votes["SELL"] += 1
                confidence -= 0.03
                drivers.append(f"High 10Y yield ({context.bond_yield_10y:.2f}%) — risk-off")
            elif context.bond_yield_10y < 3.5:
                signal_votes["BUY"] += 1
                confidence += 0.03
                drivers.append(f"Low 10Y yield ({context.bond_yield_10y:.2f}%) — risk-on")

        # News sentiment
        if context.news_sentiment is not None:
            sent_sig = _sentiment_signal(context.news_sentiment)
            label = f"{context.news_sentiment:+.2f}"
            signal_votes[sent_sig] += 1
            drivers.append(f"News sentiment {label}")
            if abs(context.news_sentiment) > 0.3:
                confidence += 0.04

        # On-chain (crypto only)
        if asset.asset_type == "crypto" and context.on_chain_activity is not None:
            if context.on_chain_activity > 0.7:
                signal_votes["BUY"] += 1
                drivers.append("High on-chain activity")
            elif context.on_chain_activity < 0.3:
                signal_votes["SELL"] += 1
                drivers.append("Low on-chain activity")

        # VIX (volatility)
        if context.vix is not None:
            if context.vix > 25:
                signal_votes["SELL"] += 1
                confidence -= 0.05
                drivers.append(f"High volatility (VIX {context.vix:.1f})")
            elif context.vix < 15:
                signal_votes["BUY"] += 1
                confidence += 0.02
                drivers.append(f"Low volatility (VIX {context.vix:.1f})")

    # Final vote — BUY wins ties over HOLD, HOLD wins over SELL
    signal_priority = {"BUY": 2, "HOLD": 1, "SELL": 0}

    def _vote_key(k: str) -> tuple:
        return (signal_votes[k], signal_priority.get(k, 0))

    final_signal = max(signal_votes, key=_vote_key)
    if signal_votes[final_signal] == 0:
        final_signal = "HOLD"

    confidence = round(max(0.10, min(0.95, confidence)), 4)

    return BaseSignal(
        asset=asset.symbol,
        signal=final_signal,
        confidence=confidence,
        price_change=chg,
        trend=trend,
        drivers=drivers[:5],
        timestamp=datetime.now(timezone.utc),
    )


def generate_all_signals(
    assets: List[AssetPrice],
    context: Optional[MarketContext],
) -> List[BaseSignal]:
    return [generate_signal(a, context) for a in assets]
