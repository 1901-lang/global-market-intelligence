"""SSE Streaming for Coordinator.

Handles Server-Sent Events streaming for real-time task progress updates.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

from coordinator.models import TaskEvent, TaskEventType

logger = logging.getLogger(__name__)


class SSEFormatter:
    """Formats events for Server-Sent Events protocol."""
    
    @staticmethod
    def format_event(
        event_type: str,
        data: Any,
        event_id: Optional[str] = None,
    ) -> str:
        """Format a single SSE event.
        
        Args:
            event_type: The event type name
            data: The event data (will be JSON serialized)
            event_id: Optional event ID for client tracking
        
        Returns:
            SSE-formatted string
        """
        lines = []
        
        if event_id:
            lines.append(f"id: {event_id}")
        
        lines.append(f"event: {event_type}")
        
        # Serialize data
        if isinstance(data, str):
            data_str = data
        else:
            data_str = json.dumps(data, default=str)
        
        # SSE requires data lines to not contain newlines
        # Split multi-line data into multiple data: lines
        for line in data_str.split("\n"):
            lines.append(f"data: {line}")
        
        # End with double newline
        return "\n".join(lines) + "\n\n"
    
    @staticmethod
    def format_task_event(event: TaskEvent) -> str:
        """Format a TaskEvent for SSE.
        
        Args:
            event: The task event to format
        
        Returns:
            SSE-formatted string
        """
        return SSEFormatter.format_event(
            event_type=event.event_type.value,
            data={
                "task_id": event.task_id,
                "payload": event.payload,
                "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            },
            event_id=str(event.event_id) if event.event_id else None,
        )
    
    @staticmethod
    def format_heartbeat() -> str:
        """Format a heartbeat/keepalive event."""
        return ": heartbeat\n\n"
    
    @staticmethod
    def format_error(error: str, task_id: Optional[str] = None) -> str:
        """Format an error event."""
        return SSEFormatter.format_event(
            event_type="error",
            data={
                "task_id": task_id,
                "error": error,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )


class EventBroadcaster:
    """Manages broadcasting events to multiple SSE connections."""
    
    def __init__(self):
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}  # task_id -> queues
        self._global_subscribers: List[asyncio.Queue] = []
    
    async def subscribe(
        self,
        task_id: Optional[str] = None,
    ) -> asyncio.Queue:
        """Subscribe to events.
        
        Args:
            task_id: If provided, only receive events for this task.
                    If None, receive all events.
        
        Returns:
            Queue that will receive events
        """
        queue: asyncio.Queue = asyncio.Queue()
        
        if task_id:
            if task_id not in self._subscribers:
                self._subscribers[task_id] = []
            self._subscribers[task_id].append(queue)
        else:
            self._global_subscribers.append(queue)
        
        return queue
    
    async def unsubscribe(
        self,
        queue: asyncio.Queue,
        task_id: Optional[str] = None,
    ) -> None:
        """Unsubscribe from events.
        
        Args:
            queue: The queue to remove
            task_id: The task ID that was subscribed to
        """
        if task_id and task_id in self._subscribers:
            try:
                self._subscribers[task_id].remove(queue)
                if not self._subscribers[task_id]:
                    del self._subscribers[task_id]
            except ValueError:
                pass
        else:
            try:
                self._global_subscribers.remove(queue)
            except ValueError:
                pass
    
    async def broadcast(self, event: TaskEvent) -> None:
        """Broadcast an event to all relevant subscribers.
        
        Args:
            event: The event to broadcast
        """
        # Send to task-specific subscribers
        if event.task_id in self._subscribers:
            for queue in self._subscribers[event.task_id]:
                try:
                    await queue.put(event)
                except Exception as e:
                    logger.warning(f"Failed to queue event: {e}")
        
        # Send to global subscribers
        for queue in self._global_subscribers:
            try:
                await queue.put(event)
            except Exception as e:
                logger.warning(f"Failed to queue global event: {e}")


# Global broadcaster instance
_broadcaster: Optional[EventBroadcaster] = None


def get_broadcaster() -> EventBroadcaster:
    """Get the global event broadcaster."""
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = EventBroadcaster()
    return _broadcaster


async def stream_task_events(
    task_id: str,
    timeout_seconds: float = 300,
    heartbeat_interval: float = 15,
) -> AsyncGenerator[str, None]:
    """Stream SSE events for a specific task.
    
    Args:
        task_id: The task to stream events for
        timeout_seconds: Maximum time to stream
        heartbeat_interval: Seconds between heartbeat messages
    
    Yields:
        SSE-formatted strings
    """
    broadcaster = get_broadcaster()
    queue = await broadcaster.subscribe(task_id)
    
    try:
        start_time = asyncio.get_event_loop().time()
        last_heartbeat = start_time
        
        while True:
            current_time = asyncio.get_event_loop().time()
            
            # Check timeout
            if current_time - start_time > timeout_seconds:
                yield SSEFormatter.format_event(
                    "timeout",
                    {"message": "Stream timeout reached"},
                )
                break
            
            # Send heartbeat if needed
            if current_time - last_heartbeat > heartbeat_interval:
                yield SSEFormatter.format_heartbeat()
                last_heartbeat = current_time
            
            try:
                # Wait for event with short timeout for heartbeat
                event = await asyncio.wait_for(
                    queue.get(),
                    timeout=heartbeat_interval,
                )
                
                yield SSEFormatter.format_task_event(event)
                
                # Check for terminal events
                if event.event_type in (
                    TaskEventType.TASK_COMPLETED,
                    TaskEventType.TASK_FAILED,
                    TaskEventType.TASK_CANCELLED,
                ):
                    break
                    
            except asyncio.TimeoutError:
                # Send heartbeat and continue
                yield SSEFormatter.format_heartbeat()
                last_heartbeat = asyncio.get_event_loop().time()
    
    finally:
        await broadcaster.unsubscribe(queue, task_id)


async def stream_coordinator_run(
    coordinator,
    session_context,
    user_message: str,
    prior_task_id: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """Stream events from a coordinator run.
    
    This is a convenience wrapper that sets up event broadcasting
    and yields SSE-formatted events as the coordinator executes.
    
    Args:
        coordinator: The CoordinatorEngine instance
        session_context: The session context
        user_message: The user's message
        prior_task_id: Optional prior task ID for resumption
    
    Yields:
        SSE-formatted strings
    """
    broadcaster = get_broadcaster()
    
    # Create a queue for this run
    task_queue: asyncio.Queue = asyncio.Queue()
    
    # Add handler to capture events
    async def capture_and_broadcast(event: TaskEvent):
        await broadcaster.broadcast(event)
        await task_queue.put(event)
    
    coordinator.add_event_handler(capture_and_broadcast)
    
    try:
        # Start coordinator run in background
        run_task = asyncio.create_task(
            coordinator.run(session_context, user_message, prior_task_id)
        )
        
        # Stream events as they come in
        while not run_task.done():
            try:
                event = await asyncio.wait_for(task_queue.get(), timeout=15)
                yield SSEFormatter.format_task_event(event)
                
                # Check for terminal events
                if event.event_type in (
                    TaskEventType.TASK_COMPLETED,
                    TaskEventType.TASK_FAILED,
                    TaskEventType.TASK_CANCELLED,
                    TaskEventType.TASK_AWAITING_APPROVAL,
                ):
                    break
            except asyncio.TimeoutError:
                yield SSEFormatter.format_heartbeat()
        
        # Get the result
        result = await run_task
        
        # Yield final response
        yield SSEFormatter.format_event(
            "response",
            {
                "answer": result.answer,
                "artifacts": [a.to_dict() for a in result.artifacts],
                "task_id": result.task_state.task_id if result.task_state else None,
            },
        )
    
    except Exception as e:
        logger.error(f"Streaming error: {e}")
        yield SSEFormatter.format_error(str(e))
    
    finally:
        # Clean up handler
        try:
            coordinator._event_handlers.remove(capture_and_broadcast)
        except ValueError:
            pass
