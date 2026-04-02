import os
import json
import logging
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from db import get_db
from models.schemas import Brief, ConsensusResult, AssetPrice, MarketContext

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Use the same flagship model for brief generation to match analysis quality
BRIEF_OPENAI_MODEL = "gpt-5.4"


def _build_brief_prompt(
    assets: List[AssetPrice],
    signals: List[ConsensusResult],
    context: Optional[MarketContext],
) -> str:
    asset_lines = "\n".join(
        f"- {a.symbol}: ${a.price:,.2f} ({a.change_24h:+.2f}%)"
        for a in assets
    )
    signal_lines = "\n".join(
        f"- {s.asset}: {s.final_signal} (confidence {s.confidence:.0%}, {s.agreement_level} agreement)"
        for s in signals
    )
    ctx_lines = ""
    if context:
        parts = []
        if context.usd_index:
            parts.append(f"USD Index: {context.usd_index:.2f}")
        if context.bond_yield_10y:
            parts.append(f"10Y Yield: {context.bond_yield_10y:.2f}%")
        if context.news_sentiment is not None:
            parts.append(f"News Sentiment: {context.news_sentiment:+.2f}")
        if context.vix:
            parts.append(f"VIX: {context.vix:.1f}")
        ctx_lines = "Market Context: " + ", ".join(parts)

    today = date.today().strftime("%B %d, %Y")
    return (
        f"Generate a concise daily market intelligence brief for {today}.\n\n"
        f"Asset Prices:\n{asset_lines}\n\n"
        f"AI Consensus Signals:\n{signal_lines}\n\n"
        f"{ctx_lines}\n\n"
        "Include:\n"
        "1. One-paragraph executive summary\n"
        "2. Key signals to watch\n"
        "3. Top 3 risk factors\n"
        "Keep it professional, data-driven, under 300 words."
    )


async def generate_brief(
    assets: List[AssetPrice],
    signals: List[ConsensusResult],
    context: Optional[MarketContext],
) -> Brief:
    today_str = date.today().isoformat()
    content = ""
    key_signals = [
        {"asset": s.asset, "signal": s.final_signal, "confidence": s.confidence}
        for s in signals
    ]
    risks = [
        "API key not configured — brief generated from mock data",
        "Market conditions subject to rapid change",
        "Model consensus may not reflect intraday volatility",
    ]

    if OPENAI_API_KEY:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=OPENAI_API_KEY)
            prompt = _build_brief_prompt(assets, signals, context)
            resp = await client.chat.completions.create(
                model=BRIEF_OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a senior market analyst writing a daily intelligence brief."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=600,
            )
            content = resp.choices[0].message.content or ""
        except Exception as exc:
            logger.warning(f"Brief generation failed: {exc}")

    if not content:
        signal_summary = ", ".join(
            f"{s.asset}:{s.final_signal}" for s in signals
        )
        asset_summary = " | ".join(
            f"{a.symbol} ${a.price:,.0f} ({a.change_24h:+.1f}%)" for a in assets
        )
        content = (
            f"**Daily Market Brief — {date.today().strftime('%B %d, %Y')}**\n\n"
            f"Markets are showing mixed signals today. Current prices: {asset_summary}. "
            f"AI consensus signals: {signal_summary}. "
            f"Monitor key macro factors including USD strength, bond yields, and news sentiment "
            f"for directional confirmation. This brief was generated without live AI API access."
        )

    brief = Brief(
        content=content,
        key_signals=key_signals,
        risks=risks,
        date=today_str,
        timestamp=datetime.utcnow(),
    )
    await _save_brief(brief)
    return brief


async def _save_brief(brief: Brief):
    try:
        async with get_db() as db:
            await db.execute(
                """
                INSERT INTO briefs (content, key_signals, risks, date, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    brief.content,
                    json.dumps(brief.key_signals),
                    json.dumps(brief.risks),
                    brief.date,
                    datetime.utcnow(),
                ),
            )
            await db.commit()
    except Exception as exc:
        logger.warning(f"_save_brief failed: {exc}")


async def get_latest_brief() -> Optional[Brief]:
    try:
        async with get_db() as db:
            row = await db.fetchone(
                "SELECT * FROM briefs ORDER BY timestamp DESC LIMIT 1"
            )
        if not row:
            return None
        return Brief(
            id=row["id"],
            content=row["content"],
            key_signals=json.loads(row["key_signals"] or "[]"),
            risks=json.loads(row["risks"] or "[]"),
            date=row["date"],
            timestamp=row["timestamp"],
        )
    except Exception as exc:
        logger.warning(f"get_latest_brief failed: {exc}")
        return None
