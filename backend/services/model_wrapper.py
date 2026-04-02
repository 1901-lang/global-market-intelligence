import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from models.schemas import BaseSignal, MarketContext, ModelOutput
from datetime import datetime

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Model identifiers — latest/most advanced versions for deep market analysis
OPENAI_MODEL = "gpt-5.4"          # OpenAI GPT-5.4
CLAUDE_MODEL = "claude-opus-4-6"  # Anthropic Claude Opus 4.6
GEMINI_MODEL = "gemini-3.1-pro"   # Google Gemini 3.1 Pro

SYSTEM_PROMPT = (
    "You are a quantitative market analyst AI. "
    "Analyze the provided market data and return a JSON object with EXACTLY these fields: "
    '{"signal": "BUY"|"SELL"|"HOLD", "confidence": <0.0-1.0>, "reasoning": [<list of short strings>]}. '
    "Be concise. Return ONLY valid JSON."
)


def _build_prompt(signal: BaseSignal, context: Optional[MarketContext]) -> str:
    parts = [
        f"Asset: {signal.asset}",
        f"Current signal (rule-based): {signal.signal}",
        f"Confidence: {signal.confidence:.2f}",
        f"24h price change: {signal.price_change:+.2f}%",
        f"Trend: {signal.trend}",
        f"Key drivers: {', '.join(signal.drivers or [])}",
    ]
    if context:
        if context.usd_index:
            parts.append(f"USD Index: {context.usd_index:.2f}")
        if context.bond_yield_10y:
            parts.append(f"10Y Bond Yield: {context.bond_yield_10y:.2f}%")
        if context.news_sentiment is not None:
            parts.append(f"News Sentiment: {context.news_sentiment:+.2f}")
        if context.vix:
            parts.append(f"VIX: {context.vix:.1f}")
    return "\n".join(parts)


def _build_debate_prompt(
    signal: BaseSignal,
    context: Optional[MarketContext],
    other_outputs: List[ModelOutput],
) -> str:
    base = _build_prompt(signal, context)
    other = "\n".join(
        f"- {o.model_name.upper()}: {o.signal} (confidence {o.confidence:.2f}) — {'; '.join(o.reasoning[:2])}"
        for o in other_outputs
    )
    return (
        f"{base}\n\n"
        f"Other AI models produced:\n{other}\n\n"
        "Re-evaluate your decision considering the above. "
        "Return updated JSON: {\"signal\": ..., \"confidence\": ..., \"reasoning\": [...]}"
    )


def _parse_model_response(raw: str) -> Dict[str, Any]:
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
    except Exception:
        pass
    return {"signal": "HOLD", "confidence": 0.5, "reasoning": ["Unable to parse response"]}


async def query_openai(
    prompt: str,
    model_name: str = OPENAI_MODEL,
) -> Dict[str, Any]:
    if not OPENAI_API_KEY:
        return _fallback_response("openai")
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        resp = await client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=300,
        )
        raw = resp.choices[0].message.content or ""
        return _parse_model_response(raw)
    except Exception as exc:
        logger.warning(f"OpenAI error: {exc}")
        return _fallback_response("openai")


async def query_claude(prompt: str) -> Dict[str, Any]:
    if not ANTHROPIC_API_KEY:
        return _fallback_response("claude")
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        message = await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text if message.content else ""
        return _parse_model_response(raw)
    except Exception as exc:
        logger.warning(f"Claude error: {exc}")
        return _fallback_response("claude")


async def query_gemini(prompt: str) -> Dict[str, Any]:
    if not GEMINI_API_KEY:
        return _fallback_response("gemini")
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(
            GEMINI_MODEL,
            system_instruction=SYSTEM_PROMPT,
        )
        full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"
        resp = await asyncio.to_thread(model.generate_content, full_prompt)
        raw = resp.text if hasattr(resp, "text") else ""
        return _parse_model_response(raw)
    except Exception as exc:
        logger.warning(f"Gemini error: {exc}")
        return _fallback_response("gemini")


def _fallback_response(model: str) -> Dict[str, Any]:
    logger.info(f"Using deterministic fallback for {model} (no API key or error).")
    return {
        "signal": "HOLD",
        "confidence": 0.5,
        "reasoning": [f"{model} API unavailable — holding position pending data"],
    }


def _to_model_output(asset: str, model_name: str, result: Dict) -> ModelOutput:
    signal = result.get("signal", "HOLD").upper()
    if signal not in ("BUY", "SELL", "HOLD"):
        signal = "HOLD"
    confidence = float(result.get("confidence", 0.5))
    confidence = max(0.0, min(1.0, confidence))
    reasoning = result.get("reasoning", [])
    if isinstance(reasoning, str):
        reasoning = [reasoning]
    return ModelOutput(
        asset=asset,
        model_name=model_name,
        signal=signal,
        confidence=confidence,
        reasoning=reasoning,
        raw_response=json.dumps(result),
        timestamp=datetime.utcnow(),
    )


async def query_all_models(
    signal: BaseSignal,
    context: Optional[MarketContext],
) -> List[ModelOutput]:
    prompt = _build_prompt(signal, context)
    openai_raw, claude_raw, gemini_raw = await asyncio.gather(
        query_openai(prompt),
        query_claude(prompt),
        query_gemini(prompt),
        return_exceptions=True,
    )
    outputs = []
    for model_name, raw in [("openai", openai_raw), ("claude", claude_raw), ("gemini", gemini_raw)]:
        if isinstance(raw, Exception):
            raw = _fallback_response(model_name)
        outputs.append(_to_model_output(signal.asset, model_name, raw))
    return outputs


async def debate_loop(
    signal: BaseSignal,
    context: Optional[MarketContext],
    initial_outputs: List[ModelOutput],
) -> List[ModelOutput]:
    refined = []
    tasks = []
    for output in initial_outputs:
        others = [o for o in initial_outputs if o.model_name != output.model_name]
        debate_prompt = _build_debate_prompt(signal, context, others)
        if output.model_name == "openai":
            tasks.append(query_openai(debate_prompt))
        elif output.model_name == "claude":
            tasks.append(query_claude(debate_prompt))
        else:
            tasks.append(query_gemini(debate_prompt))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for output, result in zip(initial_outputs, results):
        if isinstance(result, Exception):
            result = _fallback_response(output.model_name)
        refined.append(_to_model_output(signal.asset, output.model_name, result))
    return refined
