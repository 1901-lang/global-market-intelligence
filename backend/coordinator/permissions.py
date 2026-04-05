"""Permissions and Policy Enforcement for Coordinator.

Handles permission checks, approval requirements, and policy-aware
execution for tool invocations.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from coordinator.models import SessionContext

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Permission Categories
# ---------------------------------------------------------------------------

# Read-only tools (available to all roles)
READONLY_TOOLS: Set[str] = {
    "market_data.fetch_assets",
    "market_data.fetch_macro_context",
    "signals.generate_signals",
    "signals.get_signal",
    "consensus.get_consensus",
    "alerts.get_recent",
    "briefs.get_latest",
    "analytics.generate_kpi",
    "analytics.check_anomalies",
    "market_intel.get_narrative",
    "market_intel.deep_dive",
    "support.chat",
    "support.onboard",
    "admin.get_briefing",
}

# Analyst tools (require analyst or admin role)
ANALYST_TOOLS: Set[str] = {
    "briefs.generate",
    "consensus.run_debate",
    "market_intel.generate_narrative",
    "alerts.mark_read",
    "admin.query",
}

# Admin-only tools
ADMIN_TOOLS: Set[str] = {
    "admin.add_asset",
    "admin.remove_asset",
    "admin.update_config",
    "admin.manage_users",
}

# Tools requiring explicit approval before execution
APPROVAL_REQUIRED_TOOLS: Set[str] = {
    "admin.remove_asset",
    "admin.update_config",
    "admin.manage_users",
}

# Rate-limited tools (calls per minute per user)
RATE_LIMITS: Dict[str, int] = {
    "consensus.run_debate": 10,
    "briefs.generate": 5,
    "market_intel.generate_narrative": 10,
    "market_intel.deep_dive": 20,
    "admin.query": 30,
}


class PermissionChecker:
    """Handles permission checks for tool invocations."""
    
    @staticmethod
    def can_use_tool(context: SessionContext, tool_name: str) -> bool:
        """Check if user can use a specific tool.
        
        Args:
            context: Session context with user info
            tool_name: The tool to check access for
        
        Returns:
            True if user has permission, False otherwise
        """
        # Admin can use everything
        if context.role == "admin":
            return True
        
        # Check readonly tools
        if tool_name in READONLY_TOOLS:
            return True
        
        # Check analyst tools
        if tool_name in ANALYST_TOOLS:
            return context.role in ("analyst", "admin")
        
        # Check admin tools
        if tool_name in ADMIN_TOOLS:
            return context.role == "admin"
        
        # Check explicit permissions
        if context.has_permission(tool_name):
            return True
        
        # Check wildcard permissions (e.g., "market_data.*")
        tool_prefix = tool_name.split(".")[0] + ".*"
        if context.has_permission(tool_prefix):
            return True
        
        # Default deny
        return False
    
    @staticmethod
    def requires_approval(tool_name: str) -> bool:
        """Check if a tool requires user approval before execution.
        
        Args:
            tool_name: The tool to check
        
        Returns:
            True if approval is required, False otherwise
        """
        return tool_name in APPROVAL_REQUIRED_TOOLS
    
    @staticmethod
    def get_available_tools(context: SessionContext, all_tools: List[str]) -> List[str]:
        """Filter tools based on user permissions.
        
        Args:
            context: Session context with user info
            all_tools: List of all available tools
        
        Returns:
            List of tools the user can access
        """
        return [
            tool for tool in all_tools
            if PermissionChecker.can_use_tool(context, tool)
        ]
    
    @staticmethod
    def get_rate_limit(tool_name: str) -> Optional[int]:
        """Get rate limit for a tool.
        
        Args:
            tool_name: The tool to check
        
        Returns:
            Calls per minute allowed, or None if unlimited
        """
        return RATE_LIMITS.get(tool_name)


class PolicyEnforcer:
    """Enforces execution policies for coordinator operations."""
    
    def __init__(self):
        self._rate_counters: Dict[str, Dict[str, int]] = {}  # user_id -> tool -> count
    
    def check_policy(
        self,
        context: SessionContext,
        tool_name: str,
        input_data: Optional[Dict[str, Any]] = None,
    ) -> PolicyCheckResult:
        """Check all policies for a tool invocation.
        
        Args:
            context: Session context
            tool_name: Tool being invoked
            input_data: Input parameters for the tool
        
        Returns:
            PolicyCheckResult with allowed status and any violations
        """
        violations = []
        
        # Check permission
        if not PermissionChecker.can_use_tool(context, tool_name):
            violations.append(f"No permission to use tool: {tool_name}")
        
        # Check rate limit
        rate_limit = PermissionChecker.get_rate_limit(tool_name)
        if rate_limit:
            user_tools = self._rate_counters.setdefault(context.user_id, {})
            current_count = user_tools.get(tool_name, 0)
            if current_count >= rate_limit:
                violations.append(f"Rate limit exceeded for {tool_name}: {rate_limit}/min")
        
        # Check input validation policies
        if input_data:
            input_violations = self._check_input_policies(tool_name, input_data)
            violations.extend(input_violations)
        
        return PolicyCheckResult(
            allowed=len(violations) == 0,
            requires_approval=PermissionChecker.requires_approval(tool_name),
            violations=violations,
        )
    
    def _check_input_policies(
        self,
        tool_name: str,
        input_data: Dict[str, Any],
    ) -> List[str]:
        """Check input data against policies."""
        violations = []
        
        # Check for potentially dangerous inputs
        for key, value in input_data.items():
            if isinstance(value, str):
                # Check for SQL-like patterns (basic prevention)
                dangerous_patterns = ["DROP", "DELETE", "UPDATE", "INSERT", "--", ";"]
                value_upper = value.upper()
                for pattern in dangerous_patterns:
                    if pattern in value_upper and key not in ("query", "message", "content"):
                        violations.append(f"Potentially dangerous input in {key}")
                        break
        
        return violations
    
    def record_invocation(self, user_id: str, tool_name: str) -> None:
        """Record a tool invocation for rate limiting."""
        user_tools = self._rate_counters.setdefault(user_id, {})
        user_tools[tool_name] = user_tools.get(tool_name, 0) + 1
    
    def reset_rate_counters(self) -> None:
        """Reset rate counters (call periodically, e.g., every minute)."""
        self._rate_counters.clear()


class PolicyCheckResult:
    """Result of a policy check."""
    
    def __init__(
        self,
        allowed: bool,
        requires_approval: bool = False,
        violations: Optional[List[str]] = None,
    ):
        self.allowed = allowed
        self.requires_approval = requires_approval
        self.violations = violations or []
    
    def __bool__(self) -> bool:
        return self.allowed


# Global policy enforcer instance
_policy_enforcer: Optional[PolicyEnforcer] = None


def get_policy_enforcer() -> PolicyEnforcer:
    """Get the global policy enforcer instance."""
    global _policy_enforcer
    if _policy_enforcer is None:
        _policy_enforcer = PolicyEnforcer()
    return _policy_enforcer


def check_tool_permission(context: SessionContext, tool_name: str) -> bool:
    """Convenience function to check tool permission."""
    return PermissionChecker.can_use_tool(context, tool_name)


def check_tool_policy(
    context: SessionContext,
    tool_name: str,
    input_data: Optional[Dict[str, Any]] = None,
) -> PolicyCheckResult:
    """Convenience function to check all policies for a tool."""
    return get_policy_enforcer().check_policy(context, tool_name, input_data)
