"""
LangGraph Workflow — ContribFlow Pipeline

Supervisor-routed graph:
  supervisor → agent → supervisor → ... → END
"""

from langgraph.graph import StateGraph, END
from graph.state import ContribFlowState
from agents.issue_finder import issue_finder_node
from agents.repo_analyst import repo_analyst_node
from agents.domain_context import domain_context_node
from agents.contrib_planner import contrib_planner_node
from agents.supervisor import AGENT_ORDER, supervisor_node, route_from_supervisor


def _next_after(step: str) -> str | None:
    """Get next agent in workflow order."""
    if step not in AGENT_ORDER:
        return None
    idx = AGENT_ORDER.index(step)
    if idx + 1 >= len(AGENT_ORDER):
        return None
    return AGENT_ORDER[idx + 1]


def _wrap_agent(step_name: str, node_fn):
    """
    Run an agent and return control to supervisor with updated next_step.
    """

    def wrapped(state: ContribFlowState) -> dict:
        try:
            result = node_fn(state)
        except Exception:
            return {
                "current_step": step_name,
                "next_step": None,
                "error": f"Something went wrong in {step_name.replace('_', ' ')}.",
            }

        if result.get("error"):
            result["next_step"] = None
            return result

        target_step = state.get("target_step")
        if target_step == step_name:
            result["next_step"] = None
        else:
            result["next_step"] = _next_after(step_name)
        return result

    return wrapped


# --- Build the Graph ---

def build_graph():
    """Build and compile the ContribFlow LangGraph workflow."""

    workflow = StateGraph(ContribFlowState)

    # Nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("issue_finder", _wrap_agent("issue_finder", issue_finder_node))
    workflow.add_node("repo_analyst", _wrap_agent("repo_analyst", repo_analyst_node))
    workflow.add_node("domain_context", _wrap_agent("domain_context", domain_context_node))
    workflow.add_node("contrib_planner", _wrap_agent("contrib_planner", contrib_planner_node))

    # Entry point is always supervisor.
    workflow.set_entry_point("supervisor")

    # Supervisor routes to the requested next step.
    workflow.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "issue_finder": "issue_finder",
            "repo_analyst": "repo_analyst",
            "domain_context": "domain_context",
            "contrib_planner": "contrib_planner",
            "end": END,
        },
    )

    # Every agent returns to supervisor for centralized routing decisions.
    workflow.add_edge("issue_finder", "supervisor")
    workflow.add_edge("repo_analyst", "supervisor")
    workflow.add_edge("domain_context", "supervisor")
    workflow.add_edge("contrib_planner", "supervisor")

    return workflow.compile()


# Pre-compiled graph instance
contribflow_graph = build_graph()
