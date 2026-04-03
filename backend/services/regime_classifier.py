"""Deterministic rule-based market regime classifier.

Consumes MarketContext (DXY, 10Y yield, VIX, sentiment) and asset behaviour
to return a MarketRegime label and rationale. No LLM required — this is the
ground-truth analytical layer that feeds the research agent.

Regime labels
-------------
risk_on            : Low volatility, positive sentiment, risk assets bid
risk_off           : High volatility, negative sentiment, safe-haven demand
inflationary       : Rising yields, strong commodity prices, DXY divergence
disinflationary    : Falling yields, softening commodities, easing pressure
dollar_strength    : DXY elevated/rising, pressure on hard assets and EM
dollar_weakness    : DXY depressed/falling, tailwind for commodities and crypto
volatility_stress  : VIX spike, cross-asset correlation breakdown
liquidity_supportive: Low rates, low vol, supportive credit conditions
mixed_transition   : Conflicting signals across macro indicators
"""

from __future__ import annotations

from typing import Optional, Tuple
from models.schemas import MarketContext, MarketRegime
from datetime import datetime


# Thresholds (tunable)
VIX_STRESS = 25.0
VIX_LOW = 15.0
DXY_STRONG = 104.0
DXY_WEAK = 100.0
YIELD_HIGH = 4.5
YIELD_LOW = 3.5
SENTIMENT_POSITIVE = 0.1
SENTIMENT_NEGATIVE = -0.1


def classify_regime(context: Optional[MarketContext]) -> MarketRegime:
    """Classify the current market regime from macro context data.

    Returns a MarketRegime with a label, rationale, contributing factors,
    and a confidence score reflecting how clearly the data supports the label.
    """
    if context is None:
        return MarketRegime(
            label="mixed_transition",
            rationale="Market context data unavailable — defaulting to mixed/transition regime.",
            contributing_factors=["no_macro_data"],
            confidence=0.3,
            timestamp=datetime.utcnow(),
        )

    factors: list[str] = []
    signals: dict[str, str] = {}

    vix = context.vix
    dxy = context.usd_index
    yield_10y = context.bond_yield_10y
    sentiment = context.news_sentiment

    # VIX signals
    if vix is not None:
        if vix >= VIX_STRESS:
            signals["vix"] = "stress"
            factors.append(f"VIX elevated at {vix:.1f} (≥{VIX_STRESS})")
        elif vix <= VIX_LOW:
            signals["vix"] = "calm"
            factors.append(f"VIX suppressed at {vix:.1f} (≤{VIX_LOW})")
        else:
            signals["vix"] = "neutral"

    # DXY signals
    if dxy is not None:
        if dxy >= DXY_STRONG:
            signals["dxy"] = "strong"
            factors.append(f"DXY strong at {dxy:.2f} (≥{DXY_STRONG})")
        elif dxy <= DXY_WEAK:
            signals["dxy"] = "weak"
            factors.append(f"DXY weak at {dxy:.2f} (≤{DXY_WEAK})")
        else:
            signals["dxy"] = "neutral"

    # Yield signals
    if yield_10y is not None:
        if yield_10y >= YIELD_HIGH:
            signals["yield"] = "high"
            factors.append(f"10Y yield elevated at {yield_10y:.2f}% (≥{YIELD_HIGH}%)")
        elif yield_10y <= YIELD_LOW:
            signals["yield"] = "low"
            factors.append(f"10Y yield suppressed at {yield_10y:.2f}% (≤{YIELD_LOW}%)")
        else:
            signals["yield"] = "neutral"

    # Sentiment signals
    if sentiment is not None:
        if sentiment >= SENTIMENT_POSITIVE:
            signals["sentiment"] = "positive"
            factors.append(f"News sentiment positive at {sentiment:+.2f}")
        elif sentiment <= SENTIMENT_NEGATIVE:
            signals["sentiment"] = "negative"
            factors.append(f"News sentiment negative at {sentiment:+.2f}")
        else:
            signals["sentiment"] = "neutral"

    label, rationale, confidence = _resolve_regime(signals, factors)

    return MarketRegime(
        label=label,
        rationale=rationale,
        contributing_factors=factors,
        confidence=confidence,
        timestamp=datetime.utcnow(),
    )


def _resolve_regime(
    signals: dict[str, str],
    factors: list[str],
) -> Tuple[str, str, float]:
    """Map signal combination to a regime label using priority rules."""

    vix = signals.get("vix", "neutral")
    dxy = signals.get("dxy", "neutral")
    yld = signals.get("yield", "neutral")
    snt = signals.get("sentiment", "neutral")

    # Priority 1: Volatility stress overrides everything
    if vix == "stress":
        return (
            "volatility_stress",
            "VIX elevated above stress threshold — cross-asset correlation risk elevated, "
            "safe-haven demand likely. Risk-taking activity expected to compress.",
            0.85,
        )

    # Priority 2: Dollar extremes
    if dxy == "strong" and yld == "high":
        return (
            "inflationary",
            "Dollar strength combined with rising yields suggests persistent inflationary pressure "
            "and Fed tightening bias. Hard assets face headwinds from real-rate pressure.",
            0.80,
        )

    if dxy == "weak" and snt == "positive":
        return (
            "risk_on",
            "Dollar weakness with positive risk sentiment is a classic risk-on configuration. "
            "Expect commodity and crypto outperformance, EM relief.",
            0.78,
        )

    if dxy == "strong" and snt == "negative":
        return (
            "risk_off",
            "Strong dollar with negative sentiment signals defensive positioning. "
            "Capital flows moving toward safety — USD, Treasuries, gold.",
            0.78,
        )

    if dxy == "weak" and yld == "low":
        return (
            "liquidity_supportive",
            "Weak dollar with suppressed yields reflects accommodative financial conditions. "
            "Supportive for risk assets and duration.",
            0.75,
        )

    if dxy == "strong":
        return (
            "dollar_strength",
            "USD index above key threshold — applying headwinds to commodity prices, "
            "crypto, and non-dollar assets. Monitor for real-rate drivers.",
            0.72,
        )

    if dxy == "weak":
        return (
            "dollar_weakness",
            "USD index below key support — tailwind for hard assets and crypto. "
            "Monitor for dollar carry unwind and commodity re-pricing.",
            0.72,
        )

    # Priority 3: Yield extremes without DXY signal
    if yld == "high":
        return (
            "inflationary",
            "Elevated 10Y yields signal persistent inflation expectations or fiscal risk premium. "
            "Rate-sensitive assets under pressure.",
            0.70,
        )

    if yld == "low":
        return (
            "disinflationary",
            "Suppressed 10Y yields indicate falling inflation expectations or growth concerns. "
            "Duration tailwind; risk assets may be range-bound.",
            0.68,
        )

    # Priority 4: Pure sentiment
    if vix == "calm" and snt == "positive":
        return (
            "risk_on",
            "Low volatility and positive sentiment — classic risk-on environment. "
            "Momentum strategies and risk assets favoured.",
            0.70,
        )

    if snt == "negative":
        return (
            "risk_off",
            "Negative sentiment with no strong macro offset — defensive posture warranted. "
            "Monitor for sentiment-driven selling.",
            0.62,
        )

    # Default: mixed
    return (
        "mixed_transition",
        "Macro signals are conflicting or insufficient for a clear regime classification. "
        "Treat as transitional — reduce regime-dependent positioning confidence.",
        0.45,
    )
