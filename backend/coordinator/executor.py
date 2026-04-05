"""Step Executor for Coordinator.

Executes individual task steps by invoking tools via the MCP adapter layer.
Handles tool invocation, result validation, and error handling.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from coordinator.models import (
    TaskState,
    TaskStep,
    TaskStepStatus,
    TaskArtifact,
    StepResult,
)

logger = logging.getLogger(__name__)


async def execute_step(
    task: TaskState,
    step: TaskStep,
    tool_registry: Dict[str, Any],
) -> StepResult:
    """Execute a single task step.
    
    If the step has a tool, invoke it via the MCP adapter.
    If no tool, generate a direct response using the LLM.
    
    Args:
        task: The current task state
        step: The step to execute
        tool_registry: Registry of available MCP tools/adapters
    
    Returns:
        StepResult with success status, output, and any artifacts
    """
    start_time = time.time()
    
    try:
        if step.tool:
            # Execute via MCP tool
            result = await _execute_tool(step, tool_registry, task)
        else:
            # Direct LLM response (no tool)
            result = await _execute_direct(task, step)
        
        duration_ms = int((time.time() - start_time) * 1000)
        return StepResult(
            step=step,
            success=True,
            output=result.get("data"),
            artifacts=result.get("artifacts", []),
            duration_ms=duration_ms,
        )
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Step execution failed: {e}")
        return StepResult(
            step=step,
            success=False,
            error=str(e),
            duration_ms=duration_ms,
        )


async def _execute_tool(
    step: TaskStep,
    tool_registry: Dict[str, Any],
    task: TaskState,
) -> Dict[str, Any]:
    """Execute a step via MCP tool invocation."""
    tool_name = step.tool
    
    if not tool_name:
        raise ValueError("Step has no tool specified")
    
    # Get the tool adapter
    adapter = tool_registry.get(tool_name)
    if not adapter:
        # Try to find adapter by prefix (e.g., "market_data" from "market_data.fetch_assets")
        parts = tool_name.split(".")
        if len(parts) >= 2:
            adapter_name = parts[0]
            method_name = ".".join(parts[1:])
            adapter = tool_registry.get(adapter_name)
            if adapter and hasattr(adapter, "invoke"):
                # Call adapter's invoke method
                result = await adapter.invoke(method_name, step.input or {}, task)
                return _normalize_result(result)
        
        raise ValueError(f"Unknown tool: {tool_name}")
    
    # Check if adapter has invoke method
    if hasattr(adapter, "invoke"):
        result = await adapter.invoke(tool_name, step.input or {}, task)
        return _normalize_result(result)
    
    # Check if adapter is callable
    if callable(adapter):
        result = await adapter(step.input or {})
        return _normalize_result(result)
    
    raise ValueError(f"Tool {tool_name} is not invocable")


def _normalize_result(result: Any) -> Dict[str, Any]:
    """Normalize tool result to standard format."""
    if isinstance(result, dict):
        return {
            "data": result.get("data", result),
            "artifacts": result.get("artifacts", []),
        }
    return {"data": result, "artifacts": []}


async def _execute_direct(task: TaskState, step: TaskStep) -> Dict[str, Any]:
    """Execute a step that doesn't require a tool (direct LLM response)."""
    from agents.llm import llm_chat
    
    # Build context from task
    context_parts = [f"User goal: {task.goal}"]
    
    # Add any prior step outputs
    for prior_step in task.get_completed_steps():
        if prior_step.output:
            output_summary = str(prior_step.output)[:500]  # Limit for context
            context_parts.append(f"Step '{prior_step.description}' output: {output_summary}")
    
    context = "\n".join(context_parts)
    
    system_prompt = """You are an AI assistant for a market intelligence platform.
Generate a helpful, concise response based on the user's goal and available context.
Use institutional market terminology when appropriate.
Be direct and actionable."""
    
    response = await llm_chat(
        system_prompt,
        f"Context:\n{context}\n\nGenerate a response for step: {step.description}",
        max_tokens=500,
        fallback="Unable to generate response. Please try again.",
    )
    
    return {"data": response, "artifacts": []}


class ToolInvocationError(Exception):
    """Error during tool invocation."""
    pass


class ToolNotFoundError(Exception):
    """Tool not found in registry."""
    pass


class ToolValidationError(Exception):
    """Tool input/output validation error."""
    pass


async def validate_tool_input(
    tool_name: str,
    input_data: Dict[str, Any],
    tool_registry: Dict[str, Any],
) -> bool:
    """Validate tool input against schema.
    
    Returns True if valid, raises ToolValidationError if invalid.
    """
    adapter = tool_registry.get(tool_name)
    if not adapter:
        # Try prefix lookup
        parts = tool_name.split(".")
        if len(parts) >= 2:
            adapter = tool_registry.get(parts[0])
    
    if not adapter:
        raise ToolNotFoundError(f"Tool not found: {tool_name}")
    
    # Check if adapter has validation method
    if hasattr(adapter, "validate_input"):
        try:
            return adapter.validate_input(tool_name, input_data)
        except Exception as e:
            raise ToolValidationError(f"Input validation failed: {e}")
    
    # No validation available, assume valid
    return True


async def validate_tool_output(
    tool_name: str,
    output_data: Any,
    tool_registry: Dict[str, Any],
) -> bool:
    """Validate tool output against expected schema.
    
    Returns True if valid, raises ToolValidationError if invalid.
    """
    adapter = tool_registry.get(tool_name)
    if not adapter:
        parts = tool_name.split(".")
        if len(parts) >= 2:
            adapter = tool_registry.get(parts[0])
    
    if not adapter:
        raise ToolNotFoundError(f"Tool not found: {tool_name}")
    
    if hasattr(adapter, "validate_output"):
        try:
            return adapter.validate_output(tool_name, output_data)
        except Exception as e:
            raise ToolValidationError(f"Output validation failed: {e}")
    
    return True


async def execute_with_retry(
    task: TaskState,
    step: TaskStep,
    tool_registry: Dict[str, Any],
    max_retries: int = 3,
    retry_delay_seconds: float = 1.0,
) -> StepResult:
    """Execute a step with automatic retry on failure.
    
    Uses exponential backoff between retries.
    """
    last_error = None
    
    for attempt in range(max_retries):
        result = await execute_step(task, step, tool_registry)
        
        if result.success:
            return result
        
        last_error = result.error
        
        # Don't retry on validation errors
        if "validation" in str(last_error).lower():
            break
        
        # Exponential backoff
        if attempt < max_retries - 1:
            delay = retry_delay_seconds * (2 ** attempt)
            logger.info(f"Retrying step after {delay}s (attempt {attempt + 2}/{max_retries})")
            await asyncio.sleep(delay)
    
    return StepResult(
        step=step,
        success=False,
        error=f"Failed after {max_retries} attempts: {last_error}",
    )
