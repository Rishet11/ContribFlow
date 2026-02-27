"""
Supervisor Agent

Centralized orchestration node that decides which agent runs next.
"""

from graph.state import ContribFlowState

AGENT_ORDER = ["issue_finder", "repo_analyst", "domain_context", "contrib_planner"]


def _next_step_after(step: str) -> str | None:
    if step not in AGENT_ORDER:
        return None
    idx = AGENT_ORDER.index(step)
    if idx + 1 >= len(AGENT_ORDER):
        return None
    return AGENT_ORDER[idx + 1]


def supervisor_node(state: ContribFlowState) -> dict:
    """
    Decide and validate the next graph step.

    Reads: current_step, next_step, target_step, error
    Writes: current_step, next_step, error
    """
    if state.get("error"):
        return {"current_step": "supervisor", "next_step": None}

    next_step = state.get("next_step")
    target_step = state.get("target_step")
    current_step = state.get("current_step")

    if next_step:
        if next_step not in AGENT_ORDER:
            return {
                "current_step": "supervisor",
                "next_step": None,
                "error": f"Invalid workflow step '{next_step}'.",
            }
        return {"current_step": "supervisor"}

    # Infer next step from current position if caller did not specify one.
    if current_step in AGENT_ORDER:
        if target_step and current_step == target_step:
            return {"current_step": "supervisor", "next_step": None}
        inferred = _next_step_after(current_step)
        return {"current_step": "supervisor", "next_step": inferred}

    return {"current_step": "supervisor", "next_step": None}


def route_from_supervisor(state: ContribFlowState) -> str:
    """
    Conditional edge router for the supervisor node.
    """
    if state.get("error"):
        return "end"

    next_step = state.get("next_step")
    if not next_step or next_step not in AGENT_ORDER:
        return "end"
    return next_step
