"""Plan Generator for Coordinator.

Generates execution plans based on classification and available tools.
Creates structured step sequences with dependencies and completion criteria.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from coordinator.models import (
    Classification,
    ClassificationType,
    TaskStep,
    TaskPlan,
    SessionContext,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Plan Templates
# ---------------------------------------------------------------------------

# Predefined plans for common request types
PLAN_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    # Market data queries
    "get_prices": [
        {
            "description": "Fetch current asset prices",
            "tool": "market_data.fetch_assets",
            "input": {},
        },
    ],
    "get_macro": [
        {
            "description": "Fetch macro market context",
            "tool": "market_data.fetch_macro_context",
            "input": {},
        },
    ],
    "get_all_market_data": [
        {
            "description": "Fetch current asset prices",
            "tool": "market_data.fetch_assets",
            "input": {},
        },
        {
            "description": "Fetch macro market context",
            "tool": "market_data.fetch_macro_context",
            "input": {},
        },
    ],
    
    # Signal and consensus queries
    "get_signals": [
        {
            "description": "Fetch current asset prices",
            "tool": "market_data.fetch_assets",
            "input": {},
        },
        {
            "description": "Generate trading signals",
            "tool": "signals.generate_signals",
            "input": {},
        },
    ],
    "get_consensus": [
        {
            "description": "Get AI model consensus",
            "tool": "consensus.get_consensus",
            "input": {},
        },
    ],
    "full_analysis": [
        {
            "description": "Fetch current asset prices",
            "tool": "market_data.fetch_assets",
            "input": {},
        },
        {
            "description": "Fetch macro context",
            "tool": "market_data.fetch_macro_context",
            "input": {},
        },
        {
            "description": "Generate trading signals",
            "tool": "signals.generate_signals",
            "input": {},
        },
        {
            "description": "Get AI consensus",
            "tool": "consensus.get_consensus",
            "input": {},
        },
    ],
    
    # Brief and report queries
    "get_brief": [
        {
            "description": "Get latest market brief",
            "tool": "briefs.get_latest",
            "input": {},
        },
    ],
    "generate_brief": [
        {
            "description": "Fetch current market data",
            "tool": "market_data.fetch_assets",
            "input": {},
        },
        {
            "description": "Generate new market brief",
            "tool": "briefs.generate",
            "input": {},
        },
    ],
    
    # Analytics queries
    "get_kpi": [
        {
            "description": "Generate KPI report",
            "tool": "analytics.generate_kpi",
            "input": {},
        },
    ],
    "check_anomalies": [
        {
            "description": "Run anomaly detection",
            "tool": "analytics.check_anomalies",
            "input": {},
        },
    ],
    
    # Alert queries
    "get_alerts": [
        {
            "description": "Get recent alerts",
            "tool": "alerts.get_recent",
            "input": {},
        },
    ],
    
    # Market intelligence queries
    "get_narrative": [
        {
            "description": "Get latest market narrative",
            "tool": "market_intel.get_narrative",
            "input": {},
        },
    ],
    "deep_dive": [
        {
            "description": "Fetch asset price data",
            "tool": "market_data.fetch_assets",
            "input": {},
        },
        {
            "description": "Run deep dive analysis",
            "tool": "market_intel.deep_dive",
            "input": {},
        },
    ],
    
    # Admin queries
    "admin_status": [
        {
            "description": "Get admin briefing and system status",
            "tool": "admin.get_briefing",
            "input": {},
        },
    ],
    "admin_query": [
        {
            "description": "Execute admin query",
            "tool": "admin.query",
            "input": {},
        },
    ],
}

# Keyword to template mapping
KEYWORD_TEMPLATE_MAP: Dict[str, str] = {
    "price": "get_prices",
    "prices": "get_prices",
    "asset": "get_prices",
    "assets": "get_prices",
    "bitcoin": "get_prices",
    "btc": "get_prices",
    "ethereum": "get_prices",
    "eth": "get_prices",
    "gold": "get_prices",
    "oil": "get_prices",
    
    "macro": "get_macro",
    "vix": "get_macro",
    "usd index": "get_macro",
    "bond yield": "get_macro",
    
    "market data": "get_all_market_data",
    "all data": "get_all_market_data",
    "market overview": "get_all_market_data",
    
    "signal": "get_signals",
    "signals": "get_signals",
    "recommendation": "get_signals",
    
    "consensus": "get_consensus",
    "ai models": "get_consensus",
    "model output": "get_consensus",
    
    "full analysis": "full_analysis",
    "complete analysis": "full_analysis",
    "analyze all": "full_analysis",
    
    "brief": "get_brief",
    "briefing": "get_brief",
    "latest brief": "get_brief",
    "market brief": "get_brief",
    
    "generate brief": "generate_brief",
    "new brief": "generate_brief",
    "create brief": "generate_brief",
    
    "kpi": "get_kpi",
    "metrics": "get_kpi",
    "performance": "get_kpi",
    
    "anomaly": "check_anomalies",
    "anomalies": "check_anomalies",
    "unusual": "check_anomalies",
    
    "alert": "get_alerts",
    "alerts": "get_alerts",
    "notification": "get_alerts",
    
    "narrative": "get_narrative",
    "market narrative": "get_narrative",
    "commentary": "get_narrative",
    
    "deep dive": "deep_dive",
    "deep-dive": "deep_dive",
    "detailed analysis": "deep_dive",
    "analyze": "deep_dive",
    
    "status": "admin_status",
    "system status": "admin_status",
    "platform status": "admin_status",
    "agent status": "admin_status",
    
    "admin": "admin_query",
    "admin query": "admin_query",
}


def _find_template(message: str) -> Optional[str]:
    """Find the best matching template for the message."""
    message_lower = message.lower()
    
    # Check for exact keyword matches (longer matches first)
    sorted_keywords = sorted(KEYWORD_TEMPLATE_MAP.keys(), key=len, reverse=True)
    for keyword in sorted_keywords:
        if keyword in message_lower:
            return KEYWORD_TEMPLATE_MAP[keyword]
    
    return None


def _extract_asset_symbol(message: str) -> Optional[str]:
    """Extract asset symbol from message if present."""
    import re
    
    # Look for common asset symbols
    symbols = ["BTC", "ETH", "GOLD", "OIL", "SOL", "XRP", "ADA", "DOT", "LINK"]
    message_upper = message.upper()
    
    for symbol in symbols:
        if symbol in message_upper:
            return symbol
    
    # Look for "bitcoin", "ethereum" etc.
    name_to_symbol = {
        "bitcoin": "BTC",
        "ethereum": "ETH",
        "gold": "GOLD",
        "oil": "OIL",
        "crude": "OIL",
    }
    message_lower = message.lower()
    for name, symbol in name_to_symbol.items():
        if name in message_lower:
            return symbol
    
    return None


def _create_steps_from_template(
    template_name: str,
    available_tools: List[str],
    message: str,
) -> List[TaskStep]:
    """Create task steps from a template."""
    template = PLAN_TEMPLATES.get(template_name, [])
    steps = []
    
    for i, step_def in enumerate(template):
        tool = step_def.get("tool")
        
        # Only include if tool is available
        if tool and tool not in available_tools:
            logger.debug(f"Skipping step with unavailable tool: {tool}")
            continue
        
        # Process input parameters
        input_params = dict(step_def.get("input", {}))
        
        # Inject asset symbol if this is an asset-specific operation
        if "asset" in step_def.get("description", "").lower():
            symbol = _extract_asset_symbol(message)
            if symbol:
                input_params["symbol"] = symbol
        
        steps.append(TaskStep.create(
            description=step_def["description"],
            tool=tool,
            input=input_params if input_params else None,
            step_order=i,
        ))
    
    return steps


async def generate_plan(
    classification: Classification,
    user_message: str,
    available_tools: List[str],
    context: SessionContext,
    use_llm: bool = False,
) -> TaskPlan:
    """Generate an execution plan based on classification.
    
    Args:
        classification: The request classification
        user_message: The user's request message
        available_tools: List of tools available to the user
        context: Session context with user permissions
        use_llm: Whether to use LLM for complex planning
    
    Returns:
        TaskPlan with steps and completion criteria
    """
    # Conversational requests don't need a plan
    if classification.classification_type == ClassificationType.CONVERSATIONAL:
        return TaskPlan(
            objective="Respond to conversation",
            steps=[
                TaskStep.create(
                    description="Generate conversational response",
                    tool=None,  # Direct LLM response, no tool
                    step_order=0,
                )
            ],
            completion_condition="Response generated",
        )
    
    # Try to find a matching template
    template_name = _find_template(user_message)
    
    if template_name:
        steps = _create_steps_from_template(template_name, available_tools, user_message)
        if steps:
            return TaskPlan(
                objective=f"Execute {template_name.replace('_', ' ')} workflow",
                steps=steps,
                completion_condition="All steps completed successfully",
                estimated_duration_seconds=len(steps) * 5,
                requires_approval=classification.requires_approval,
                approval_reason="Transactional operation" if classification.requires_approval else None,
            )
    
    # Use suggested tools from classification
    if classification.suggested_tools:
        steps = []
        for i, tool in enumerate(classification.suggested_tools):
            if tool in available_tools:
                steps.append(TaskStep.create(
                    description=f"Execute {tool.replace('.', ' ').replace('_', ' ')}",
                    tool=tool,
                    step_order=i,
                ))
        
        if steps:
            return TaskPlan(
                objective=f"Execute {classification.classification_type.value} request",
                steps=steps,
                completion_condition="All steps completed",
                estimated_duration_seconds=len(steps) * 5,
                requires_approval=classification.requires_approval,
            )
    
    # Fallback: use LLM to generate plan
    if use_llm and classification.requires_planning:
        return await _llm_generate_plan(
            user_message,
            available_tools,
            classification,
        )
    
    # Default: single step with direct response
    return TaskPlan(
        objective="Process user request",
        steps=[
            TaskStep.create(
                description="Process request and generate response",
                tool=None,
                step_order=0,
            )
        ],
        completion_condition="Response generated",
    )


async def _llm_generate_plan(
    user_message: str,
    available_tools: List[str],
    classification: Classification,
) -> TaskPlan:
    """Use LLM to generate a complex plan."""
    from agents.llm import llm_chat
    import json
    
    tools_list = "\n".join(f"- {t}" for t in available_tools)
    
    system_prompt = f"""You are a task planner for a market intelligence platform.
Generate an execution plan for the user's request.

Available tools:
{tools_list}

Output JSON format:
{{
  "objective": "Brief description of the goal",
  "steps": [
    {{"description": "Step 1 description", "tool": "tool.name", "input": {{}}}},
    {{"description": "Step 2 description", "tool": "tool.name", "input": {{}}}}
  ],
  "completion_condition": "How to know when task is complete"
}}

Only use tools from the available list. Keep plans concise (1-5 steps).
"""
    
    try:
        response = await llm_chat(
            system_prompt,
            f"Create a plan for: {user_message}",
            max_tokens=400,
            temperature=0.2,
        )
        
        # Extract JSON from response
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(response[start:end])
            
            steps = []
            for i, step_data in enumerate(data.get("steps", [])):
                tool = step_data.get("tool")
                if tool and tool not in available_tools:
                    continue  # Skip unavailable tools
                
                steps.append(TaskStep.create(
                    description=step_data.get("description", f"Step {i+1}"),
                    tool=tool,
                    input=step_data.get("input"),
                    step_order=i,
                ))
            
            if steps:
                return TaskPlan(
                    objective=data.get("objective", "Execute user request"),
                    steps=steps,
                    completion_condition=data.get("completion_condition", "All steps completed"),
                    requires_approval=classification.requires_approval,
                )
    except Exception as e:
        logger.warning(f"LLM plan generation failed: {e}")
    
    # Fallback
    return TaskPlan(
        objective="Process user request",
        steps=[
            TaskStep.create(
                description="Generate response",
                tool=None,
                step_order=0,
            )
        ],
        completion_condition="Response generated",
    )
