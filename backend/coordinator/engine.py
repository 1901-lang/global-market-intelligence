"""Coordinator Engine - Core orchestration runtime.

Implements the 6-phase lifecycle:
1. Ingest - Receive user message, session context, permissions, available tools
2. Classify - Categorize request type
3. Plan - Generate execution plan
4. Execute - Invoke tools via MCP adapters
5. Reflect - Decide next action
6. Synthesize - Produce final answer

This is the single entry point for all coordinator interactions.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from db import get_db
from security import sanitize_input

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

logger = logging.getLogger(__name__)


class CoordinatorEngine:
    """Main coordinator runtime engine.
    
    Orchestrates task execution through a structured lifecycle with durable state,
    explicit tool contracts, and policy-aware execution.
    """
    
    def __init__(
        self,
        classifier: Optional[Callable] = None,
        planner: Optional[Callable] = None,
        executor: Optional[Callable] = None,
        synthesizer: Optional[Callable] = None,
    ):
        """Initialize the coordinator engine with optional custom components."""
        self._classifier = classifier
        self._planner = planner
        self._executor = executor
        self._synthesizer = synthesizer
        self._tool_registry: Dict[str, Any] = {}
        self._event_handlers: List[Callable[[TaskEvent], None]] = []
    
    def register_tool_registry(self, registry: Dict[str, Any]) -> None:
        """Register the MCP tool registry."""
        self._tool_registry = registry
    
    def add_event_handler(self, handler: Callable[[TaskEvent], None]) -> None:
        """Add an event handler for task events."""
        self._event_handlers.append(handler)
    
    async def _emit_event(self, event: TaskEvent) -> None:
        """Emit a task event to all handlers."""
        await self._persist_event(event)
        for handler in self._event_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.warning(f"Event handler error: {e}")
    
    async def _persist_event(self, event: TaskEvent) -> None:
        """Persist event to database for audit trail."""
        try:
            async with get_db() as db:
                await db.execute(
                    """INSERT INTO task_events (task_id, event_type, payload_json, timestamp)
                       VALUES (?, ?, ?, ?)""",
                    (
                        event.task_id,
                        event.event_type.value,
                        json.dumps(event.payload) if event.payload else None,
                        event.timestamp or datetime.now(timezone.utc),
                    ),
                )
                await db.commit()
        except Exception as e:
            logger.warning(f"Failed to persist event: {e}")
    
    # -------------------------------------------------------------------------
    # Task State Persistence
    # -------------------------------------------------------------------------
    
    async def _save_task(self, task: TaskState) -> None:
        """Save task state to database."""
        task.updated_at = datetime.now(timezone.utc)
        try:
            async with get_db() as db:
                # Check if task exists
                existing = await db.fetchone(
                    "SELECT id FROM tasks WHERE id = ?", (task.task_id,)
                )
                if existing:
                    await db.execute(
                        """UPDATE tasks SET
                           session_id = ?, user_id = ?, goal = ?, status = ?,
                           classification = ?, updated_at = ?, completed_at = ?,
                           context_json = ?, result_json = ?, error_json = ?
                           WHERE id = ?""",
                        (
                            task.session_id,
                            task.user_id,
                            task.goal,
                            task.status.value,
                            task.classification.value if task.classification else None,
                            task.updated_at,
                            task.completed_at,
                            json.dumps(task.context) if task.context else None,
                            json.dumps(task.result) if task.result else None,
                            json.dumps(task.error) if task.error else None,
                            task.task_id,
                        ),
                    )
                else:
                    await db.execute(
                        """INSERT INTO tasks (id, session_id, user_id, goal, status,
                           classification, created_at, updated_at, completed_at,
                           context_json, result_json, error_json)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            task.task_id,
                            task.session_id,
                            task.user_id,
                            task.goal,
                            task.status.value,
                            task.classification.value if task.classification else None,
                            task.created_at,
                            task.updated_at,
                            task.completed_at,
                            json.dumps(task.context) if task.context else None,
                            json.dumps(task.result) if task.result else None,
                            json.dumps(task.error) if task.error else None,
                        ),
                    )
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to save task: {e}")
            raise
    
    async def _save_steps(self, task: TaskState) -> None:
        """Save all task steps to database."""
        try:
            async with get_db() as db:
                # Delete existing steps and re-insert (simpler than upsert)
                await db.execute(
                    "DELETE FROM task_steps WHERE task_id = ?", (task.task_id,)
                )
                for step in task.plan:
                    await db.execute(
                        """INSERT INTO task_steps (id, task_id, step_order, description,
                           tool, status, input_json, output_json, error, started_at,
                           completed_at, requires_approval)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            step.step_id,
                            task.task_id,
                            step.step_order,
                            step.description,
                            step.tool,
                            step.status.value,
                            json.dumps(step.input) if step.input else None,
                            json.dumps(step.output) if step.output else None,
                            step.error,
                            step.started_at,
                            step.completed_at,
                            1 if step.requires_approval else 0,
                        ),
                    )
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to save steps: {e}")
            raise
    
    async def _save_artifacts(self, task: TaskState) -> None:
        """Save task artifacts to database."""
        try:
            async with get_db() as db:
                for artifact in task.artifacts:
                    existing = await db.fetchone(
                        "SELECT id FROM task_artifacts WHERE id = ?",
                        (artifact.artifact_id,)
                    )
                    if not existing:
                        await db.execute(
                            """INSERT INTO task_artifacts (id, task_id, artifact_type,
                               name, url, metadata_json, created_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (
                                artifact.artifact_id,
                                task.task_id,
                                artifact.artifact_type,
                                artifact.name,
                                artifact.url,
                                json.dumps(artifact.metadata) if artifact.metadata else None,
                                artifact.created_at,
                            ),
                        )
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to save artifacts: {e}")
            raise
    
    async def load_task(self, task_id: str) -> Optional[TaskState]:
        """Load task state from database."""
        try:
            async with get_db() as db:
                row = await db.fetchone(
                    "SELECT * FROM tasks WHERE id = ?", (task_id,)
                )
                if not row:
                    return None
                
                # Load steps
                step_rows = await db.fetchall(
                    "SELECT * FROM task_steps WHERE task_id = ? ORDER BY step_order",
                    (task_id,)
                )
                
                # Load artifacts
                artifact_rows = await db.fetchall(
                    "SELECT * FROM task_artifacts WHERE task_id = ?", (task_id,)
                )
                
            # Build task state
            task = TaskState(
                task_id=row["id"],
                session_id=row["session_id"],
                user_id=row["user_id"],
                goal=row["goal"],
                status=TaskStatus(row["status"]),
                classification=ClassificationType(row["classification"]) if row.get("classification") else None,
                context=json.loads(row["context_json"]) if row.get("context_json") else None,
                result=json.loads(row["result_json"]) if row.get("result_json") else None,
                error=json.loads(row["error_json"]) if row.get("error_json") else None,
                created_at=row.get("created_at"),
                updated_at=row.get("updated_at"),
                completed_at=row.get("completed_at"),
            )
            
            # Add steps
            for sr in step_rows:
                task.plan.append(TaskStep(
                    step_id=sr["id"],
                    description=sr["description"],
                    tool=sr.get("tool"),
                    status=TaskStepStatus(sr["status"]),
                    input=json.loads(sr["input_json"]) if sr.get("input_json") else None,
                    output=json.loads(sr["output_json"]) if sr.get("output_json") else None,
                    error=sr.get("error"),
                    started_at=sr.get("started_at"),
                    completed_at=sr.get("completed_at"),
                    step_order=sr.get("step_order", 0),
                    requires_approval=bool(sr.get("requires_approval", 0)),
                ))
            
            # Add artifacts
            for ar in artifact_rows:
                task.artifacts.append(TaskArtifact(
                    artifact_id=ar["id"],
                    artifact_type=ar["artifact_type"],
                    name=ar["name"],
                    url=ar.get("url"),
                    metadata=json.loads(ar["metadata_json"]) if ar.get("metadata_json") else None,
                    created_at=ar.get("created_at"),
                ))
            
            return task
        except Exception as e:
            logger.error(f"Failed to load task: {e}")
            return None
    
    # -------------------------------------------------------------------------
    # Phase 1: Ingest
    # -------------------------------------------------------------------------
    
    async def ingest(
        self,
        session_context: SessionContext,
        user_message: str,
        prior_task_id: Optional[str] = None,
    ) -> IngestResult:
        """Phase 1: Ingest user message and build context.
        
        - Sanitize input
        - Load prior task state if resuming
        - Get available tools based on permissions
        """
        # Sanitize user input
        try:
            sanitized_message = sanitize_input(user_message)
        except ValueError as e:
            logger.warning(f"Input sanitization failed: {e}")
            sanitized_message = user_message  # Fallback, classifier will handle
        
        # Load prior state if resuming
        prior_state = None
        if prior_task_id:
            prior_state = await self.load_task(prior_task_id)
        
        # Get available tools based on user permissions
        available_tools = self._get_available_tools(session_context)
        
        return IngestResult(
            session_context=session_context,
            user_message=user_message,
            sanitized_message=sanitized_message,
            available_tools=available_tools,
            prior_state=prior_state,
        )
    
    def _get_available_tools(self, context: SessionContext) -> List[str]:
        """Get tools available to the user based on permissions."""
        all_tools = list(self._tool_registry.keys())
        
        # For now, return all tools. In production, filter by permissions.
        if context.role == "readonly":
            # Read-only users get limited tools
            return [t for t in all_tools if not t.startswith("admin.")]
        
        return all_tools
    
    # -------------------------------------------------------------------------
    # Phase 2: Classify
    # -------------------------------------------------------------------------
    
    async def classify(self, ingest_result: IngestResult) -> Classification:
        """Phase 2: Classify the request type.
        
        Uses rule-based classification first, falls back to LLM if needed.
        """
        if self._classifier:
            return await self._classifier(ingest_result)
        
        # Default rule-based classification
        return await self._default_classify(ingest_result)
    
    async def _default_classify(self, ingest_result: IngestResult) -> Classification:
        """Default rule-based classifier."""
        from coordinator.classifier import classify_request
        return await classify_request(
            ingest_result.sanitized_message,
            ingest_result.available_tools,
        )
    
    # -------------------------------------------------------------------------
    # Phase 3: Plan
    # -------------------------------------------------------------------------
    
    async def plan(
        self,
        classification: Classification,
        ingest_result: IngestResult,
    ) -> TaskPlan:
        """Phase 3: Generate execution plan.
        
        Creates a structured plan with steps, dependencies, and completion criteria.
        """
        if self._planner:
            return await self._planner(classification, ingest_result)
        
        # Default planning
        return await self._default_plan(classification, ingest_result)
    
    async def _default_plan(
        self,
        classification: Classification,
        ingest_result: IngestResult,
    ) -> TaskPlan:
        """Default planner based on classification."""
        from coordinator.planner import generate_plan
        return await generate_plan(
            classification=classification,
            user_message=ingest_result.sanitized_message,
            available_tools=ingest_result.available_tools,
            context=ingest_result.session_context,
        )
    
    # -------------------------------------------------------------------------
    # Phase 4: Execute
    # -------------------------------------------------------------------------
    
    async def execute_step(
        self,
        task: TaskState,
        step: TaskStep,
    ) -> StepResult:
        """Phase 4: Execute a single step.
        
        Invokes tools via MCP adapters and captures results.
        """
        if self._executor:
            return await self._executor(task, step)
        
        # Default execution
        return await self._default_execute_step(task, step)
    
    async def _default_execute_step(
        self,
        task: TaskState,
        step: TaskStep,
    ) -> StepResult:
        """Default step executor using MCP client."""
        from coordinator.executor import execute_step
        return await execute_step(
            task=task,
            step=step,
            tool_registry=self._tool_registry,
        )
    
    # -------------------------------------------------------------------------
    # Phase 5: Reflect
    # -------------------------------------------------------------------------
    
    async def reflect(
        self,
        task: TaskState,
        step_result: StepResult,
    ) -> ReflectionDecision:
        """Phase 5: Decide next action based on step result.
        
        Determines whether to continue, retry, request approval, or terminate.
        """
        # Check for failure
        if not step_result.success:
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                return ReflectionDecision(
                    action=ReflectionAction.RETRY,
                    reasoning=f"Step failed: {step_result.error}. Retrying ({task.retry_count}/{task.max_retries})",
                )
            else:
                return ReflectionDecision(
                    action=ReflectionAction.TERMINATE,
                    reasoning=f"Step failed after {task.max_retries} retries: {step_result.error}",
                )
        
        # Reset retry count on success
        task.retry_count = 0
        
        # Check if there are more steps
        next_index = task.current_step_index + 1
        if next_index < len(task.plan):
            next_step = task.plan[next_index]
            
            # Check if next step requires approval
            if next_step.requires_approval:
                return ReflectionDecision(
                    action=ReflectionAction.REQUEST_APPROVAL,
                    reasoning=f"Next step requires approval: {next_step.description}",
                    next_step_index=next_index,
                )
            
            return ReflectionDecision(
                action=ReflectionAction.CONTINUE,
                reasoning="Step completed successfully, proceeding to next step",
                next_step_index=next_index,
            )
        
        # All steps completed
        return ReflectionDecision(
            action=ReflectionAction.TERMINATE,
            reasoning="All steps completed successfully",
        )
    
    # -------------------------------------------------------------------------
    # Phase 6: Synthesize
    # -------------------------------------------------------------------------
    
    async def synthesize(self, task: TaskState) -> FinalResponse:
        """Phase 6: Produce final response.
        
        Combines step outputs into a coherent answer with artifacts and evidence.
        """
        if self._synthesizer:
            return await self._synthesizer(task)
        
        # Default synthesis
        return await self._default_synthesize(task)
    
    async def _default_synthesize(self, task: TaskState) -> FinalResponse:
        """Default synthesizer that combines step outputs."""
        from coordinator.synthesizer import synthesize_response
        return await synthesize_response(task)
    
    # -------------------------------------------------------------------------
    # Main Entry Point
    # -------------------------------------------------------------------------
    
    async def run(
        self,
        session_context: SessionContext,
        user_message: str,
        prior_task_id: Optional[str] = None,
    ) -> FinalResponse:
        """Main entry point for coordinator interactions.
        
        Executes the full 6-phase lifecycle and returns a final response.
        For streaming, use run_stream() instead.
        """
        # Phase 1: Ingest
        ingest_result = await self.ingest(
            session_context=session_context,
            user_message=user_message,
            prior_task_id=prior_task_id,
        )
        
        # Create or resume task
        if ingest_result.prior_state and ingest_result.prior_state.status == TaskStatus.AWAITING_APPROVAL:
            task = ingest_result.prior_state
        else:
            task = TaskState.create(
                session_id=session_context.session_id,
                user_id=session_context.user_id,
                goal=ingest_result.sanitized_message,
            )
        
        await self._save_task(task)
        await self._emit_event(TaskEvent.create(
            task.task_id,
            TaskEventType.TASK_CREATED,
            {"goal": task.goal},
        ))
        
        # Phase 2: Classify
        classification = await self.classify(ingest_result)
        task.classification = classification.classification_type
        task.update_status(TaskStatus.PLANNING)
        await self._save_task(task)
        
        await self._emit_event(TaskEvent.create(
            task.task_id,
            TaskEventType.TASK_CLASSIFIED,
            classification.to_dict(),
        ))
        
        # Phase 3: Plan
        plan = await self.plan(classification, ingest_result)
        task.plan = plan.steps
        task.update_status(TaskStatus.EXECUTING)
        await self._save_task(task)
        await self._save_steps(task)
        
        await self._emit_event(TaskEvent.create(
            task.task_id,
            TaskEventType.TASK_PLANNED,
            plan.to_dict(),
        ))
        
        # Check if plan requires approval before execution
        if plan.requires_approval:
            task.update_status(TaskStatus.AWAITING_APPROVAL)
            await self._save_task(task)
            await self._emit_event(TaskEvent.create(
                task.task_id,
                TaskEventType.TASK_AWAITING_APPROVAL,
                {"reason": plan.approval_reason},
            ))
            return FinalResponse(
                answer=f"This operation requires approval: {plan.approval_reason}",
                task_state=task,
            )
        
        # Phase 4 & 5: Execute steps with reflection
        while task.current_step_index < len(task.plan):
            step = task.plan[task.current_step_index]
            step.status = TaskStepStatus.RUNNING
            step.started_at = datetime.now(timezone.utc)
            await self._save_steps(task)
            
            await self._emit_event(TaskEvent.create(
                task.task_id,
                TaskEventType.STEP_STARTED,
                {"step_id": step.step_id, "description": step.description},
            ))
            
            # Execute step
            step_result = await self.execute_step(task, step)
            
            # Update step status
            if step_result.success:
                step.status = TaskStepStatus.COMPLETED
                step.output = step_result.output
            else:
                step.status = TaskStepStatus.FAILED
                step.error = step_result.error
            step.completed_at = datetime.now(timezone.utc)
            
            # Add any artifacts
            for artifact in step_result.artifacts:
                task.add_artifact(artifact)
            
            await self._save_steps(task)
            await self._save_artifacts(task)
            
            event_type = TaskEventType.STEP_COMPLETED if step_result.success else TaskEventType.STEP_FAILED
            await self._emit_event(TaskEvent.create(
                task.task_id,
                event_type,
                step_result.to_dict(),
            ))
            
            # Reflect on result
            decision = await self.reflect(task, step_result)
            
            if decision.action == ReflectionAction.TERMINATE:
                break
            elif decision.action == ReflectionAction.RETRY:
                # Don't advance step index
                task.update_status(TaskStatus.RETRYING)
                await self._save_task(task)
                continue
            elif decision.action == ReflectionAction.REQUEST_APPROVAL:
                task.update_status(TaskStatus.AWAITING_APPROVAL)
                await self._save_task(task)
                await self._emit_event(TaskEvent.create(
                    task.task_id,
                    TaskEventType.TASK_AWAITING_APPROVAL,
                    {"step_id": step.step_id, "reasoning": decision.reasoning},
                ))
                return FinalResponse(
                    answer=f"Approval required: {decision.reasoning}",
                    task_state=task,
                )
            elif decision.action == ReflectionAction.CONTINUE:
                task.current_step_index = decision.next_step_index or (task.current_step_index + 1)
        
        # Determine final status
        if task.has_failures():
            task.update_status(TaskStatus.PARTIAL_SUCCESS if task.get_completed_steps() else TaskStatus.FAILED)
        else:
            task.update_status(TaskStatus.COMPLETED)
        
        await self._save_task(task)
        
        # Phase 6: Synthesize
        response = await self.synthesize(task)
        response.task_state = task
        
        event_type = TaskEventType.TASK_COMPLETED if task.status == TaskStatus.COMPLETED else TaskEventType.TASK_FAILED
        await self._emit_event(TaskEvent.create(
            task.task_id,
            event_type,
            response.to_dict(),
        ))
        
        return response
    
    async def run_stream(
        self,
        session_context: SessionContext,
        user_message: str,
        prior_task_id: Optional[str] = None,
    ) -> AsyncGenerator[TaskEvent, None]:
        """Streaming entry point for coordinator interactions.
        
        Yields TaskEvents as they occur during execution.
        """
        events: List[TaskEvent] = []
        
        # Capture events as they're emitted
        async def capture_event(event: TaskEvent):
            events.append(event)
        
        self.add_event_handler(capture_event)
        
        try:
            # Run the coordinator
            response = await self.run(session_context, user_message, prior_task_id)
            
            # Yield all captured events
            for event in events:
                yield event
            
            # Yield final response as message chunk
            yield TaskEvent.create(
                response.task_state.task_id if response.task_state else "unknown",
                TaskEventType.MESSAGE_CHUNK,
                {"content": response.answer, "done": True},
            )
        finally:
            # Remove the event handler
            self._event_handlers.remove(capture_event)
    
    async def approve_task(self, task_id: str, approved: bool = True) -> Optional[TaskState]:
        """Approve or reject a pending task.
        
        If approved, the task will resume execution from the pending step.
        If rejected, the task will be marked as cancelled.
        """
        task = await self.load_task(task_id)
        if not task:
            return None
        
        if task.status != TaskStatus.AWAITING_APPROVAL:
            logger.warning(f"Task {task_id} is not awaiting approval")
            return task
        
        if approved:
            task.update_status(TaskStatus.EXECUTING)
            await self._emit_event(TaskEvent.create(
                task.task_id,
                TaskEventType.TASK_APPROVED,
                {"approved": True},
            ))
        else:
            task.update_status(TaskStatus.CANCELLED)
            await self._emit_event(TaskEvent.create(
                task.task_id,
                TaskEventType.TASK_CANCELLED,
                {"reason": "User rejected approval"},
            ))
        
        await self._save_task(task)
        return task
    
    async def cancel_task(self, task_id: str) -> Optional[TaskState]:
        """Cancel a running task."""
        task = await self.load_task(task_id)
        if not task:
            return None
        
        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            logger.warning(f"Task {task_id} is already in terminal state")
            return task
        
        task.update_status(TaskStatus.CANCELLED)
        await self._save_task(task)
        
        await self._emit_event(TaskEvent.create(
            task.task_id,
            TaskEventType.TASK_CANCELLED,
            {"reason": "User cancelled"},
        ))
        
        return task


# Singleton instance for easy access
_coordinator: Optional[CoordinatorEngine] = None


def get_coordinator() -> CoordinatorEngine:
    """Get the global coordinator instance."""
    global _coordinator
    if _coordinator is None:
        _coordinator = CoordinatorEngine()
    return _coordinator


def init_coordinator(
    tool_registry: Optional[Dict[str, Any]] = None,
    classifier: Optional[Callable] = None,
    planner: Optional[Callable] = None,
    executor: Optional[Callable] = None,
    synthesizer: Optional[Callable] = None,
) -> CoordinatorEngine:
    """Initialize the global coordinator with custom components."""
    global _coordinator
    _coordinator = CoordinatorEngine(
        classifier=classifier,
        planner=planner,
        executor=executor,
        synthesizer=synthesizer,
    )
    if tool_registry:
        _coordinator.register_tool_registry(tool_registry)
    return _coordinator
