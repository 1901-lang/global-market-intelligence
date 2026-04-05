"""Task State Models for Coordinator Runtime.

Defines the core data structures for durable task state management.
These models are persisted in PostgreSQL/SQLite and used throughout
the coordinator lifecycle.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TaskStatus(str, Enum):
    """Task lifecycle status."""
    QUEUED = "queued"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    RETRYING = "retrying"
    PARTIAL_SUCCESS = "partial_success"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStepStatus(str, Enum):
    """Individual step status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ClassificationType(str, Enum):
    """Request classification categories."""
    CONVERSATIONAL = "conversational"       # Greeting, acknowledgment, small talk
    INFORMATIONAL = "informational"         # Direct question, lookup
    ANALYTICAL = "analytical"               # Analysis, comparison, insight generation
    OPERATIONAL = "operational"             # System status, admin query
    TRANSACTIONAL = "transactional"         # Risky action requiring approval
    MULTI_STEP = "multi_step"               # Complex workflow requiring planning


class TaskEventType(str, Enum):
    """Task event types for streaming and audit."""
    TASK_CREATED = "task.created"
    TASK_CLASSIFIED = "task.classified"
    TASK_PLANNED = "task.planned"
    STEP_STARTED = "step.started"
    STEP_COMPLETED = "step.completed"
    STEP_FAILED = "step.failed"
    TASK_AWAITING_APPROVAL = "task.awaiting_approval"
    TASK_APPROVED = "task.approved"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"
    MESSAGE_CHUNK = "message.chunk"
    TOOL_INVOKED = "tool.invoked"
    TOOL_RESULT = "tool.result"


class ReflectionAction(str, Enum):
    """Actions the coordinator can take after step execution."""
    CONTINUE = "continue"           # Proceed to next step
    RETRY = "retry"                 # Retry current step
    SWITCH_STRATEGY = "switch"      # Change approach
    REQUEST_APPROVAL = "approval"   # Need user approval
    ASK_USER = "ask_user"           # Need clarification
    TERMINATE = "terminate"         # Task complete or unrecoverable


# ---------------------------------------------------------------------------
# Core Task Models
# ---------------------------------------------------------------------------

@dataclass
class TaskStep:
    """A single step in a task execution plan."""
    step_id: str
    description: str
    tool: Optional[str] = None
    status: TaskStepStatus = TaskStepStatus.PENDING
    input: Optional[Dict[str, Any]] = None
    output: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    step_order: int = 0
    requires_approval: bool = False
    
    @classmethod
    def create(
        cls,
        description: str,
        tool: Optional[str] = None,
        input: Optional[Dict[str, Any]] = None,
        step_order: int = 0,
        requires_approval: bool = False,
    ) -> TaskStep:
        """Create a new task step with generated ID."""
        return cls(
            step_id=str(uuid.uuid4()),
            description=description,
            tool=tool,
            input=input,
            step_order=step_order,
            requires_approval=requires_approval,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "step_id": self.step_id,
            "description": self.description,
            "tool": self.tool,
            "status": self.status.value,
            "input": self.input,
            "output": self.output,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "step_order": self.step_order,
            "requires_approval": self.requires_approval,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TaskStep:
        """Deserialize from dictionary."""
        return cls(
            step_id=data["step_id"],
            description=data["description"],
            tool=data.get("tool"),
            status=TaskStepStatus(data.get("status", "pending")),
            input=data.get("input"),
            output=data.get("output"),
            error=data.get("error"),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            step_order=data.get("step_order", 0),
            requires_approval=data.get("requires_approval", False),
        )


@dataclass
class TaskArtifact:
    """An artifact produced by task execution."""
    artifact_id: str
    artifact_type: str  # report, brief, chart, data, alert
    name: str
    url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    
    @classmethod
    def create(
        cls,
        artifact_type: str,
        name: str,
        url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TaskArtifact:
        """Create a new artifact with generated ID."""
        return cls(
            artifact_id=str(uuid.uuid4()),
            artifact_type=artifact_type,
            name=name,
            url=url,
            metadata=metadata,
            created_at=datetime.now(timezone.utc),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "name": self.name,
            "url": self.url,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TaskArtifact:
        """Deserialize from dictionary."""
        return cls(
            artifact_id=data["artifact_id"],
            artifact_type=data["artifact_type"],
            name=data["name"],
            url=data.get("url"),
            metadata=data.get("metadata"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
        )


@dataclass
class TaskEvent:
    """An event in the task execution lifecycle."""
    event_id: Optional[int] = None
    task_id: str = ""
    event_type: TaskEventType = TaskEventType.TASK_CREATED
    payload: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None
    
    @classmethod
    def create(
        cls,
        task_id: str,
        event_type: TaskEventType,
        payload: Optional[Dict[str, Any]] = None,
    ) -> TaskEvent:
        """Create a new task event."""
        return cls(
            task_id=task_id,
            event_type=event_type,
            payload=payload,
            timestamp=datetime.now(timezone.utc),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "event_id": self.event_id,
            "task_id": self.task_id,
            "event_type": self.event_type.value,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
    
    def to_sse(self) -> str:
        """Format as Server-Sent Event."""
        data = json.dumps({
            "event": self.event_type.value,
            "task_id": self.task_id,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        })
        return f"event: {self.event_type.value}\ndata: {data}\n\n"


@dataclass
class TaskState:
    """Complete task state for durable persistence."""
    task_id: str
    session_id: str
    user_id: str
    goal: str
    status: TaskStatus = TaskStatus.QUEUED
    classification: Optional[ClassificationType] = None
    plan: List[TaskStep] = field(default_factory=list)
    artifacts: List[TaskArtifact] = field(default_factory=list)
    context: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # In-memory tracking (not persisted)
    current_step_index: int = 0
    retry_count: int = 0
    max_retries: int = 3
    
    @classmethod
    def create(
        cls,
        session_id: str,
        user_id: str,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> TaskState:
        """Create a new task with generated ID."""
        now = datetime.now(timezone.utc)
        return cls(
            task_id=str(uuid.uuid4()),
            session_id=session_id,
            user_id=user_id,
            goal=goal,
            context=context or {},
            created_at=now,
            updated_at=now,
        )
    
    def get_current_step(self) -> Optional[TaskStep]:
        """Get the current step being executed."""
        if 0 <= self.current_step_index < len(self.plan):
            return self.plan[self.current_step_index]
        return None
    
    def get_pending_steps(self) -> List[TaskStep]:
        """Get all pending steps."""
        return [s for s in self.plan if s.status == TaskStepStatus.PENDING]
    
    def get_completed_steps(self) -> List[TaskStep]:
        """Get all completed steps."""
        return [s for s in self.plan if s.status == TaskStepStatus.COMPLETED]
    
    def get_failed_steps(self) -> List[TaskStep]:
        """Get all failed steps."""
        return [s for s in self.plan if s.status == TaskStepStatus.FAILED]
    
    def all_steps_completed(self) -> bool:
        """Check if all steps are completed or skipped."""
        if not self.plan:
            return True
        return all(
            s.status in (TaskStepStatus.COMPLETED, TaskStepStatus.SKIPPED)
            for s in self.plan
        )
    
    def has_failures(self) -> bool:
        """Check if any step failed."""
        return any(s.status == TaskStepStatus.FAILED for s in self.plan)
    
    def add_artifact(self, artifact: TaskArtifact) -> None:
        """Add an artifact to the task."""
        self.artifacts.append(artifact)
        self.updated_at = datetime.now(timezone.utc)
    
    def update_status(self, status: TaskStatus) -> None:
        """Update task status and timestamp."""
        self.status = status
        self.updated_at = datetime.now(timezone.utc)
        if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            self.completed_at = self.updated_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for database storage."""
        return {
            "task_id": self.task_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "goal": self.goal,
            "status": self.status.value,
            "classification": self.classification.value if self.classification else None,
            "plan": [s.to_dict() for s in self.plan],
            "artifacts": [a.to_dict() for a in self.artifacts],
            "context": self.context,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TaskState:
        """Deserialize from dictionary."""
        task = cls(
            task_id=data["task_id"],
            session_id=data["session_id"],
            user_id=data["user_id"],
            goal=data["goal"],
            status=TaskStatus(data.get("status", "queued")),
            classification=ClassificationType(data["classification"]) if data.get("classification") else None,
            plan=[TaskStep.from_dict(s) for s in data.get("plan", [])],
            artifacts=[TaskArtifact.from_dict(a) for a in data.get("artifacts", [])],
            context=data.get("context"),
            result=data.get("result"),
            error=data.get("error"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
        )
        return task


# ---------------------------------------------------------------------------
# Coordinator Phase Models
# ---------------------------------------------------------------------------

@dataclass
class SessionContext:
    """Session context for coordinator requests."""
    session_id: str
    user_id: str
    username: str
    role: str  # admin, analyst, readonly
    permissions: List[str] = field(default_factory=list)
    preferences: Optional[Dict[str, Any]] = None
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        if self.role == "admin":
            return True
        return permission in self.permissions
    
    def can_approve(self) -> bool:
        """Check if user can approve transactional operations."""
        return self.role in ("admin", "analyst")


@dataclass
class IngestResult:
    """Result of the Ingest phase."""
    session_context: SessionContext
    user_message: str
    sanitized_message: str
    available_tools: List[str]
    prior_state: Optional[TaskState] = None
    conversation_history: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class Classification:
    """Result of the Classify phase."""
    classification_type: ClassificationType
    confidence: float
    reasoning: str
    suggested_tools: List[str] = field(default_factory=list)
    requires_planning: bool = False
    requires_approval: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "type": self.classification_type.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "suggested_tools": self.suggested_tools,
            "requires_planning": self.requires_planning,
            "requires_approval": self.requires_approval,
        }


@dataclass
class TaskPlan:
    """Result of the Plan phase."""
    objective: str
    steps: List[TaskStep]
    completion_condition: str
    estimated_duration_seconds: Optional[int] = None
    requires_approval: bool = False
    approval_reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "objective": self.objective,
            "steps": [s.to_dict() for s in self.steps],
            "completion_condition": self.completion_condition,
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "requires_approval": self.requires_approval,
            "approval_reason": self.approval_reason,
        }


@dataclass
class StepResult:
    """Result of executing a single step."""
    step: TaskStep
    success: bool
    output: Optional[Any] = None
    error: Optional[str] = None
    artifacts: List[TaskArtifact] = field(default_factory=list)
    duration_ms: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "step_id": self.step.step_id,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "artifacts": [a.to_dict() for a in self.artifacts],
            "duration_ms": self.duration_ms,
        }


@dataclass
class ReflectionDecision:
    """Result of the Reflect phase."""
    action: ReflectionAction
    reasoning: str
    next_step_index: Optional[int] = None
    retry_strategy: Optional[str] = None
    user_question: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "action": self.action.value,
            "reasoning": self.reasoning,
            "next_step_index": self.next_step_index,
            "retry_strategy": self.retry_strategy,
            "user_question": self.user_question,
        }


@dataclass
class FinalResponse:
    """Result of the Synthesize phase."""
    answer: str
    artifacts: List[TaskArtifact] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    step_summary: List[Dict[str, Any]] = field(default_factory=list)
    unresolved_issues: List[str] = field(default_factory=list)
    task_state: Optional[TaskState] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "answer": self.answer,
            "artifacts": [a.to_dict() for a in self.artifacts],
            "evidence": self.evidence,
            "step_summary": self.step_summary,
            "unresolved_issues": self.unresolved_issues,
            "task_id": self.task_state.task_id if self.task_state else None,
        }
