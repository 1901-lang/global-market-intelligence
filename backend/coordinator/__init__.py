"""Coordinator Runtime Engine - MCP-capable orchestration platform.

This module provides the core orchestration layer for the Global Market Intelligence
platform. It implements a structured execution engine with durable task state,
explicit tool contracts, and policy-aware execution.

The coordinator follows a 6-phase lifecycle:
1. Ingest - Receive user message, session context, permissions, available tools
2. Classify - Categorize request type (conversational, informational, analytical, etc.)
3. Plan - Generate execution plan with subtasks and dependencies
4. Execute - Invoke tools via MCP-compatible adapters, checkpoint state
5. Reflect - Decide to continue, retry, switch strategy, or request approval
6. Synthesize - Produce final answer with evidence, artifacts, and summary

Key principles:
- Reuse existing business logic via MCP adapters (no rewrites)
- Coordinator-first orchestration (single entry point)
- Explicit tool contracts (MCP Tool schema)
- Explicit task state (durable in PostgreSQL, not chat history)
- Deterministic control logic where possible
- Policy-aware execution (approval for risky operations)
- Strong observability (structured logging, task events, audit trail)
"""

from coordinator.models import (
    TaskStatus,
    TaskState,
    TaskStep,
    TaskStepStatus,
    TaskArtifact,
    TaskEvent,
    TaskEventType,
    Classification,
    ClassificationType,
    IngestResult,
    TaskPlan,
    StepResult,
    ReflectionDecision,
    ReflectionAction,
    FinalResponse,
    SessionContext,
)
from coordinator.engine import CoordinatorEngine

__all__ = [
    # Models
    "TaskStatus",
    "TaskState",
    "TaskStep",
    "TaskStepStatus",
    "TaskArtifact",
    "TaskEvent",
    "TaskEventType",
    "Classification",
    "ClassificationType",
    "IngestResult",
    "TaskPlan",
    "StepResult",
    "ReflectionDecision",
    "ReflectionAction",
    "FinalResponse",
    "SessionContext",
    # Engine
    "CoordinatorEngine",
]
