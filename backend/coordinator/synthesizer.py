"""Response Synthesizer for Coordinator.

Combines step outputs into a coherent final response with
artifacts, evidence, and execution summary.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from coordinator.models import (
    TaskState,
    TaskStatus,
    TaskStep,
    TaskStepStatus,
    TaskArtifact,
    FinalResponse,
)

logger = logging.getLogger(__name__)


async def synthesize_response(task: TaskState) -> FinalResponse:
    """Synthesize a final response from task execution.
    
    Combines outputs from all completed steps into a coherent answer.
    
    Args:
        task: The completed/failed task state
    
    Returns:
        FinalResponse with answer, artifacts, evidence, and summary
    """
    completed_steps = task.get_completed_steps()
    failed_steps = task.get_failed_steps()
    
    # Collect all outputs
    outputs: List[Any] = []
    evidence: List[str] = []
    
    for step in completed_steps:
        if step.output is not None:
            outputs.append({
                "step": step.description,
                "tool": step.tool,
                "output": step.output,
            })
            
            # Extract evidence from output
            evidence_item = _extract_evidence(step)
            if evidence_item:
                evidence.append(evidence_item)
    
    # Build step summary
    step_summary = _build_step_summary(task.plan)
    
    # Collect unresolved issues
    unresolved = []
    for step in failed_steps:
        unresolved.append(f"Failed: {step.description} - {step.error}")
    
    # Generate answer
    if task.status == TaskStatus.COMPLETED:
        answer = await _generate_success_answer(task, outputs)
    elif task.status == TaskStatus.PARTIAL_SUCCESS:
        answer = await _generate_partial_answer(task, outputs, unresolved)
    elif task.status == TaskStatus.AWAITING_APPROVAL:
        answer = _generate_approval_message(task)
    else:
        answer = await _generate_failure_answer(task, unresolved)
    
    return FinalResponse(
        answer=answer,
        artifacts=task.artifacts,
        evidence=evidence,
        step_summary=step_summary,
        unresolved_issues=unresolved,
        task_state=task,
    )


def _extract_evidence(step: TaskStep) -> Optional[str]:
    """Extract evidence citation from step output."""
    if not step.output:
        return None
    
    output = step.output
    
    # Handle different output formats
    if isinstance(output, str):
        # Truncate long strings
        if len(output) > 200:
            return f"[{step.tool or 'response'}]: {output[:200]}..."
        return f"[{step.tool or 'response'}]: {output}"
    
    if isinstance(output, dict):
        # Extract key fields
        if "content" in output:
            return f"[{step.tool}]: {str(output['content'])[:200]}..."
        if "data" in output:
            data = output["data"]
            if isinstance(data, list) and len(data) > 0:
                return f"[{step.tool}]: Retrieved {len(data)} items"
            return f"[{step.tool}]: {str(data)[:200]}..."
    
    if isinstance(output, list):
        return f"[{step.tool}]: Retrieved {len(output)} items"
    
    return f"[{step.tool}]: Data retrieved"


def _build_step_summary(steps: List[TaskStep]) -> List[Dict[str, Any]]:
    """Build a summary of all steps and their status."""
    summary = []
    
    for step in steps:
        duration = None
        if step.started_at and step.completed_at:
            duration = (step.completed_at - step.started_at).total_seconds()
        
        summary.append({
            "step_id": step.step_id,
            "description": step.description,
            "tool": step.tool,
            "status": step.status.value,
            "duration_seconds": duration,
            "has_output": step.output is not None,
            "error": step.error,
        })
    
    return summary


async def _generate_success_answer(
    task: TaskState,
    outputs: List[Dict[str, Any]],
) -> str:
    """Generate answer for successful task completion."""
    # If single output with direct text, return it
    if len(outputs) == 1:
        output = outputs[0]["output"]
        if isinstance(output, str):
            return output
    
    # For multiple outputs or complex data, use LLM to synthesize
    return await _llm_synthesize(task.goal, outputs, success=True)


async def _generate_partial_answer(
    task: TaskState,
    outputs: List[Dict[str, Any]],
    unresolved: List[str],
) -> str:
    """Generate answer for partially successful task."""
    base_answer = await _llm_synthesize(task.goal, outputs, success=True)
    
    issues_text = "\n".join(f"- {issue}" for issue in unresolved)
    
    return f"""{base_answer}

**Note:** Some steps could not be completed:
{issues_text}"""


async def _generate_failure_answer(
    task: TaskState,
    unresolved: List[str],
) -> str:
    """Generate answer for failed task."""
    issues_text = "\n".join(f"- {issue}" for issue in unresolved)
    
    return f"""I was unable to complete your request: "{task.goal}"

The following issues occurred:
{issues_text}

Please try again or rephrase your request. If the problem persists, contact support."""


def _generate_approval_message(task: TaskState) -> str:
    """Generate message for task awaiting approval."""
    return f"""This operation requires approval before it can proceed.

**Request:** {task.goal}
**Task ID:** {task.task_id}

Please approve or reject this action to continue."""


async def _llm_synthesize(
    goal: str,
    outputs: List[Dict[str, Any]],
    success: bool,
) -> str:
    """Use LLM to synthesize a coherent response from multiple outputs."""
    from agents.llm import llm_chat
    
    # Format outputs for LLM
    output_text = ""
    for i, out in enumerate(outputs, 1):
        output_str = _format_output(out["output"])
        output_text += f"\n{i}. [{out['tool'] or 'response'}] {out['step']}:\n{output_str}\n"
    
    system_prompt = """You are an AI assistant for an institutional market intelligence platform.
Synthesize the collected data and outputs into a clear, professional response.
Be concise and actionable. Use markdown formatting where helpful.
Do not repeat raw data; summarize and highlight key insights."""
    
    prompt = f"""User goal: {goal}

Collected outputs:{output_text}

Synthesize a cohesive response addressing the user's goal. 
Highlight key findings and actionable insights."""
    
    response = await llm_chat(
        system_prompt,
        prompt,
        max_tokens=800,
        fallback=_fallback_synthesis(outputs),
    )
    
    return response


def _format_output(output: Any) -> str:
    """Format output for inclusion in synthesis prompt."""
    if isinstance(output, str):
        return output[:1000] if len(output) > 1000 else output
    
    if isinstance(output, dict):
        # Pretty print dict but limit size
        formatted = json.dumps(output, indent=2, default=str)
        return formatted[:1000] if len(formatted) > 1000 else formatted
    
    if isinstance(output, list):
        # Summarize list
        if len(output) == 0:
            return "Empty list"
        if len(output) <= 3:
            return json.dumps(output, indent=2, default=str)[:500]
        return f"List with {len(output)} items. First few: {json.dumps(output[:3], indent=2, default=str)[:500]}"
    
    return str(output)[:500]


def _fallback_synthesis(outputs: List[Dict[str, Any]]) -> str:
    """Fallback synthesis when LLM is unavailable."""
    if not outputs:
        return "No data was retrieved."
    
    parts = ["Here's what I found:\n"]
    
    for out in outputs:
        tool = out.get("tool", "response")
        output = out.get("output")
        
        if isinstance(output, str):
            parts.append(f"**{tool}:** {output[:300]}{'...' if len(output) > 300 else ''}\n")
        elif isinstance(output, dict):
            if "content" in output:
                parts.append(f"**{tool}:** {output['content'][:300]}\n")
            else:
                parts.append(f"**{tool}:** Data retrieved\n")
        elif isinstance(output, list):
            parts.append(f"**{tool}:** {len(output)} items retrieved\n")
        else:
            parts.append(f"**{tool}:** Data retrieved\n")
    
    return "".join(parts)


def create_artifact_from_output(
    step: TaskStep,
    output: Any,
    artifact_type: str = "data",
) -> Optional[TaskArtifact]:
    """Create an artifact from step output if appropriate."""
    if output is None:
        return None
    
    # Determine artifact type and name
    name = step.description
    
    if isinstance(output, str) and len(output) > 500:
        # Long text becomes a report artifact
        return TaskArtifact.create(
            artifact_type="report",
            name=name,
            metadata={"length": len(output), "preview": output[:200]},
        )
    
    if isinstance(output, dict):
        if "content" in output:
            return TaskArtifact.create(
                artifact_type="report",
                name=name,
                metadata={"preview": str(output.get("content", ""))[:200]},
            )
        if "data" in output and isinstance(output["data"], list):
            return TaskArtifact.create(
                artifact_type="data",
                name=name,
                metadata={"count": len(output["data"])},
            )
    
    if isinstance(output, list) and len(output) > 5:
        return TaskArtifact.create(
            artifact_type="data",
            name=name,
            metadata={"count": len(output)},
        )
    
    return None
