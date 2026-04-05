"""Request Classifier for Coordinator.

Classifies user requests into categories to determine the appropriate
execution path. Uses rule-based classification with LLM fallback.
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

from coordinator.models import (
    Classification,
    ClassificationType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword patterns for rule-based classification
# ---------------------------------------------------------------------------

CONVERSATIONAL_PATTERNS = [
    r"^(hi|hello|hey|good\s*(morning|afternoon|evening))[\s!.,]*$",
    r"^(thanks|thank\s*you|thx)[\s!.,]*$",
    r"^(bye|goodbye|see\s*you)[\s!.,]*$",
    r"^(ok|okay|got\s*it|understood)[\s!.,]*$",
]

INFORMATIONAL_PATTERNS = [
    r"\b(what\s+is|what's|whats)\b",
    r"\b(show\s+me|get\s+me|fetch|retrieve)\b",
    r"\b(current\s+price|price\s+of)\b",
    r"\b(latest\s+brief|market\s+data|consensus)\b",
    r"\b(how\s+many|list\s+all|what\s+are)\b",
]

ANALYTICAL_PATTERNS = [
    r"\b(analyze|analyse|analysis)\b",
    r"\b(compare|comparison|versus|vs\.?)\b",
    r"\b(why\s+is|why\s+did|explain\s+why)\b",
    r"\b(trend|pattern|correlation)\b",
    r"\b(deep\s*dive|research|investigate)\b",
    r"\b(forecast|predict|outlook)\b",
    r"\b(sentiment|momentum|volatility)\b",
]

OPERATIONAL_PATTERNS = [
    r"\b(system\s+status|platform\s+health|agent\s+status)\b",
    r"\b(kpi|metrics|performance\s+report)\b",
    r"\b(briefing|admin\s+report|operational)\b",
    r"\b(check\s+anomal|anomaly\s+detection)\b",
]

TRANSACTIONAL_PATTERNS = [
    r"\b(add\s+asset|remove\s+asset|delete)\b",
    r"\b(create\s+alert|set\s+alert|configure)\b",
    r"\b(update\s+settings|change\s+config)\b",
    r"\b(execute|run\s+job|trigger)\b",
]

MULTI_STEP_PATTERNS = [
    r"\b(and\s+then|after\s+that|followed\s+by)\b",
    r"\b(first.*then|step\s+\d+)\b",
    r"\b(generate.*and.*send|analyze.*and.*report)\b",
    r"\b(workflow|pipeline|sequence)\b",
]

# ---------------------------------------------------------------------------
# Tool suggestions based on keywords
# ---------------------------------------------------------------------------

TOOL_SUGGESTIONS = {
    # Market data tools
    "price": ["market_data.fetch_assets"],
    "prices": ["market_data.fetch_assets"],
    "asset": ["market_data.fetch_assets"],
    "assets": ["market_data.fetch_assets"],
    "bitcoin": ["market_data.fetch_assets"],
    "btc": ["market_data.fetch_assets"],
    "ethereum": ["market_data.fetch_assets"],
    "eth": ["market_data.fetch_assets"],
    "gold": ["market_data.fetch_assets"],
    "oil": ["market_data.fetch_assets"],
    "macro": ["market_data.fetch_macro_context"],
    "context": ["market_data.fetch_macro_context"],
    "vix": ["market_data.fetch_macro_context"],
    "usd": ["market_data.fetch_macro_context"],
    
    # Signal tools
    "signal": ["signals.generate_signals"],
    "signals": ["signals.generate_signals"],
    "recommendation": ["signals.generate_signals"],
    
    # Consensus tools
    "consensus": ["consensus.get_consensus"],
    "ai": ["consensus.get_consensus", "consensus.run_debate"],
    "models": ["consensus.get_consensus"],
    "debate": ["consensus.run_debate"],
    
    # Alert tools
    "alert": ["alerts.get_recent", "alerts.create"],
    "alerts": ["alerts.get_recent"],
    "notification": ["alerts.get_recent"],
    
    # Brief tools
    "brief": ["briefs.get_latest", "briefs.generate"],
    "briefing": ["briefs.get_latest", "briefs.generate"],
    "report": ["briefs.generate"],
    
    # Analytics tools
    "kpi": ["analytics.generate_kpi"],
    "analytics": ["analytics.generate_kpi"],
    "anomaly": ["analytics.check_anomalies"],
    "metrics": ["analytics.generate_kpi"],
    
    # Market intel tools
    "narrative": ["market_intel.get_narrative"],
    "analysis": ["market_intel.deep_dive"],
    "deep dive": ["market_intel.deep_dive"],
    "deep-dive": ["market_intel.deep_dive"],
    
    # Support tools
    "help": ["support.chat"],
    "support": ["support.chat"],
    "onboard": ["support.onboard"],
    
    # Admin tools
    "status": ["admin.get_briefing", "admin.query"],
    "admin": ["admin.query"],
    "system": ["admin.get_briefing"],
}


def _match_patterns(text: str, patterns: List[str]) -> bool:
    """Check if text matches any of the patterns."""
    text_lower = text.lower().strip()
    for pattern in patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True
    return False


def _extract_suggested_tools(text: str, available_tools: List[str]) -> List[str]:
    """Extract suggested tools based on keywords in the text."""
    text_lower = text.lower()
    suggestions = set()
    
    for keyword, tools in TOOL_SUGGESTIONS.items():
        if keyword in text_lower:
            for tool in tools:
                if tool in available_tools:
                    suggestions.add(tool)
    
    return list(suggestions)


async def classify_request(
    message: str,
    available_tools: List[str],
    use_llm_fallback: bool = False,
) -> Classification:
    """Classify a user request into an execution category.
    
    Uses rule-based classification first, then LLM if needed.
    
    Args:
        message: The user's request message
        available_tools: List of tools available to the user
        use_llm_fallback: Whether to use LLM for uncertain classifications
    
    Returns:
        Classification with type, confidence, and suggested tools
    """
    message_lower = message.lower().strip()
    
    # Short messages are likely conversational
    if len(message_lower) < 10:
        if _match_patterns(message, CONVERSATIONAL_PATTERNS):
            return Classification(
                classification_type=ClassificationType.CONVERSATIONAL,
                confidence=0.95,
                reasoning="Short message matching conversational pattern",
                requires_planning=False,
            )
    
    # Check for multi-step patterns first (highest priority)
    if _match_patterns(message, MULTI_STEP_PATTERNS):
        suggested_tools = _extract_suggested_tools(message, available_tools)
        return Classification(
            classification_type=ClassificationType.MULTI_STEP,
            confidence=0.85,
            reasoning="Message contains multi-step workflow indicators",
            suggested_tools=suggested_tools,
            requires_planning=True,
        )
    
    # Check for transactional patterns (requires approval)
    if _match_patterns(message, TRANSACTIONAL_PATTERNS):
        suggested_tools = _extract_suggested_tools(message, available_tools)
        return Classification(
            classification_type=ClassificationType.TRANSACTIONAL,
            confidence=0.90,
            reasoning="Message indicates a transactional operation",
            suggested_tools=suggested_tools,
            requires_planning=True,
            requires_approval=True,
        )
    
    # Check for operational patterns
    if _match_patterns(message, OPERATIONAL_PATTERNS):
        suggested_tools = _extract_suggested_tools(message, available_tools)
        return Classification(
            classification_type=ClassificationType.OPERATIONAL,
            confidence=0.85,
            reasoning="Message requests operational or admin information",
            suggested_tools=suggested_tools,
            requires_planning=False,
        )
    
    # Check for analytical patterns
    if _match_patterns(message, ANALYTICAL_PATTERNS):
        suggested_tools = _extract_suggested_tools(message, available_tools)
        return Classification(
            classification_type=ClassificationType.ANALYTICAL,
            confidence=0.85,
            reasoning="Message requests analysis or insights",
            suggested_tools=suggested_tools,
            requires_planning=len(suggested_tools) > 1,
        )
    
    # Check for informational patterns
    if _match_patterns(message, INFORMATIONAL_PATTERNS):
        suggested_tools = _extract_suggested_tools(message, available_tools)
        return Classification(
            classification_type=ClassificationType.INFORMATIONAL,
            confidence=0.85,
            reasoning="Message requests information or data",
            suggested_tools=suggested_tools,
            requires_planning=False,
        )
    
    # Check for conversational patterns
    if _match_patterns(message, CONVERSATIONAL_PATTERNS):
        return Classification(
            classification_type=ClassificationType.CONVERSATIONAL,
            confidence=0.90,
            reasoning="Message matches conversational pattern",
            requires_planning=False,
        )
    
    # Fallback: try to extract tools and classify based on that
    suggested_tools = _extract_suggested_tools(message, available_tools)
    
    if suggested_tools:
        # If we can match tools, assume informational unless complex
        classification_type = ClassificationType.INFORMATIONAL
        requires_planning = False
        
        if len(suggested_tools) > 2:
            classification_type = ClassificationType.MULTI_STEP
            requires_planning = True
        elif any("deep_dive" in t or "analyze" in t for t in suggested_tools):
            classification_type = ClassificationType.ANALYTICAL
            requires_planning = True
        
        return Classification(
            classification_type=classification_type,
            confidence=0.70,
            reasoning="Classified based on tool keyword matching",
            suggested_tools=suggested_tools,
            requires_planning=requires_planning,
        )
    
    # Use LLM fallback if enabled
    if use_llm_fallback:
        return await _llm_classify(message, available_tools)
    
    # Default to informational with low confidence
    return Classification(
        classification_type=ClassificationType.INFORMATIONAL,
        confidence=0.50,
        reasoning="Default classification - no strong pattern match",
        requires_planning=False,
    )


async def _llm_classify(message: str, available_tools: List[str]) -> Classification:
    """Use LLM for classification when rules are uncertain."""
    from agents.llm import llm_chat
    
    tools_list = ", ".join(available_tools[:20])  # Limit for context
    
    system_prompt = """You are a request classifier for a market intelligence platform.
Classify the user's request into one of these categories:
- CONVERSATIONAL: Greetings, acknowledgments, small talk
- INFORMATIONAL: Direct questions, data lookups
- ANALYTICAL: Analysis requests, comparisons, insights
- OPERATIONAL: System status, admin queries
- TRANSACTIONAL: Config changes, asset management (requires approval)
- MULTI_STEP: Complex workflows requiring multiple steps

Respond with JSON: {"type": "CATEGORY", "confidence": 0.0-1.0, "reasoning": "...", "suggested_tools": [...]}
Available tools: """ + tools_list
    
    try:
        response = await llm_chat(
            system_prompt,
            f"Classify this request: {message}",
            max_tokens=200,
            temperature=0.1,
        )
        
        import json
        # Extract JSON from response
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(response[start:end])
            return Classification(
                classification_type=ClassificationType(data.get("type", "informational").lower()),
                confidence=float(data.get("confidence", 0.7)),
                reasoning=data.get("reasoning", "LLM classification"),
                suggested_tools=[t for t in data.get("suggested_tools", []) if t in available_tools],
                requires_planning=data.get("type", "").lower() in ("multi_step", "analytical"),
                requires_approval=data.get("type", "").lower() == "transactional",
            )
    except Exception as e:
        logger.warning(f"LLM classification failed: {e}")
    
    # Fallback
    return Classification(
        classification_type=ClassificationType.INFORMATIONAL,
        confidence=0.50,
        reasoning="LLM classification failed, using fallback",
    )
