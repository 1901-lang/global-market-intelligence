"""Session Management for Coordinator.

Manages coordinator sessions linking authenticated users to 
persistent session contexts and conversation history.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from db import get_db
from coordinator.models import SessionContext

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages coordinator sessions."""
    
    @staticmethod
    async def create_session(
        user_id: str,
        username: str,
        role: str,
        permissions: Optional[List[str]] = None,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> SessionContext:
        """Create a new coordinator session.
        
        Args:
            user_id: The user's ID
            username: The user's username
            role: The user's role (admin, analyst, readonly)
            permissions: Optional list of specific permissions
            preferences: Optional user preferences
        
        Returns:
            SessionContext for the new session
        """
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        # Build context JSON
        context_data = {
            "username": username,
            "role": role,
            "permissions": permissions or [],
            "preferences": preferences or {},
        }
        
        try:
            async with get_db() as db:
                await db.execute(
                    """INSERT INTO coordinator_sessions 
                       (id, user_id, created_at, last_activity_at, context_json, is_active)
                       VALUES (?, ?, ?, ?, ?, 1)""",
                    (session_id, user_id, now, now, json.dumps(context_data)),
                )
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise
        
        return SessionContext(
            session_id=session_id,
            user_id=user_id,
            username=username,
            role=role,
            permissions=permissions or [],
            preferences=preferences,
        )
    
    @staticmethod
    async def get_session(session_id: str) -> Optional[SessionContext]:
        """Retrieve an existing session.
        
        Args:
            session_id: The session ID to retrieve
        
        Returns:
            SessionContext if found and active, None otherwise
        """
        try:
            async with get_db() as db:
                row = await db.fetchone(
                    "SELECT * FROM coordinator_sessions WHERE id = ? AND is_active = 1",
                    (session_id,),
                )
                if not row:
                    return None
                
                context_data = json.loads(row.get("context_json") or "{}")
                
                return SessionContext(
                    session_id=row["id"],
                    user_id=row["user_id"],
                    username=context_data.get("username", "unknown"),
                    role=context_data.get("role", "readonly"),
                    permissions=context_data.get("permissions", []),
                    preferences=context_data.get("preferences"),
                )
        except Exception as e:
            logger.error(f"Failed to get session: {e}")
            return None
    
    @staticmethod
    async def update_activity(session_id: str) -> None:
        """Update the last activity timestamp for a session."""
        try:
            async with get_db() as db:
                await db.execute(
                    "UPDATE coordinator_sessions SET last_activity_at = ? WHERE id = ?",
                    (datetime.now(timezone.utc), session_id),
                )
                await db.commit()
        except Exception as e:
            logger.warning(f"Failed to update session activity: {e}")
    
    @staticmethod
    async def end_session(session_id: str) -> None:
        """End/deactivate a session."""
        try:
            async with get_db() as db:
                await db.execute(
                    "UPDATE coordinator_sessions SET is_active = 0 WHERE id = ?",
                    (session_id,),
                )
                await db.commit()
        except Exception as e:
            logger.warning(f"Failed to end session: {e}")
    
    @staticmethod
    async def get_user_sessions(user_id: str, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all sessions for a user.
        
        Args:
            user_id: The user's ID
            active_only: If True, only return active sessions
        
        Returns:
            List of session info dictionaries
        """
        try:
            query = "SELECT * FROM coordinator_sessions WHERE user_id = ?"
            if active_only:
                query += " AND is_active = 1"
            query += " ORDER BY last_activity_at DESC"
            
            async with get_db() as db:
                rows = await db.fetchall(query, (user_id,))
                
            return [
                {
                    "session_id": row["id"],
                    "user_id": row["user_id"],
                    "created_at": row.get("created_at"),
                    "last_activity_at": row.get("last_activity_at"),
                    "is_active": bool(row.get("is_active")),
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to get user sessions: {e}")
            return []
    
    @staticmethod
    async def cleanup_stale_sessions(max_age_hours: int = 24) -> int:
        """Cleanup sessions that haven't been active in max_age_hours.
        
        Args:
            max_age_hours: Sessions older than this are marked inactive
        
        Returns:
            Number of sessions cleaned up
        """
        try:
            async with get_db() as db:
                # Mark old sessions as inactive
                result = await db.execute(
                    f"""UPDATE coordinator_sessions 
                       SET is_active = 0 
                       WHERE is_active = 1 
                       AND last_activity_at < datetime('now', '-{max_age_hours} hours')""",
                    (),
                )
                await db.commit()
                return 0  # SQLite doesn't return rowcount easily
        except Exception as e:
            logger.error(f"Failed to cleanup sessions: {e}")
            return 0


async def create_session_from_user(user: Dict[str, Any]) -> SessionContext:
    """Create a session from an authenticated user dict.
    
    Commonly used when processing API requests with authenticated users.
    
    Args:
        user: User dictionary from auth system
    
    Returns:
        SessionContext for the user
    """
    return await SessionManager.create_session(
        user_id=str(user.get("id", user.get("user_id", "unknown"))),
        username=user.get("username", "unknown"),
        role=user.get("role", "readonly"),
        permissions=user.get("permissions", []),
        preferences=user.get("preferences"),
    )


async def get_or_create_session(
    session_id: Optional[str],
    user: Dict[str, Any],
) -> SessionContext:
    """Get existing session or create new one.
    
    Args:
        session_id: Optional existing session ID
        user: User dictionary from auth system
    
    Returns:
        SessionContext (existing or new)
    """
    if session_id:
        existing = await SessionManager.get_session(session_id)
        if existing:
            await SessionManager.update_activity(session_id)
            return existing
    
    # Create new session
    return await create_session_from_user(user)
