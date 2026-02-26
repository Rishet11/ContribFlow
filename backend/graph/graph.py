"""
LangGraph Workflow — ContribFlow Pipeline

Wires all agents together in a proper LangGraph StateGraph:
  resolve → find_issues → select_issue → repo_analysis → domain_context → contrib_plan

The supervisor routes between steps and handles errors.
"""

from langgraph.graph import StateGraph, END
from graph.state import ContribFlowState
from agents.issue_finder import issue_finder_node
from agents.repo_analyst import repo_analyst_node
from agents.domain_context import domain_context_node
from agents.contrib_planner import contrib_planner_node


def should_skip_domain(state: ContribFlowState) -> str:
    """After domain context, always proceed to action plan."""
    return "contrib_planner"


def check_error(state: ContribFlowState) -> str:
    """Check if the current step errored. If so, stop."""
    if state.get("error"):
        return "end"
    return "continue"


# --- Build the Graph ---

def build_graph():
    """Build and compile the ContribFlow LangGraph workflow."""

    workflow = StateGraph(ContribFlowState)

    # Add nodes
    workflow.add_node("issue_finder", issue_finder_node)
    workflow.add_node("repo_analyst", repo_analyst_node)
    workflow.add_node("domain_context", domain_context_node)
    workflow.add_node("contrib_planner", contrib_planner_node)

    # Entry point
    workflow.set_entry_point("issue_finder")

    # Edges: issue_finder → repo_analyst (after user selects an issue)
    workflow.add_conditional_edges(
        "issue_finder",
        check_error,
        {"end": END, "continue": END},  # Pause here — user selects issue
    )

    # repo_analyst → domain_context → contrib_planner → END
    workflow.add_edge("repo_analyst", "domain_context")
    workflow.add_edge("domain_context", "contrib_planner")
    workflow.add_edge("contrib_planner", END)

    return workflow.compile()


# Pre-compiled graph instance
contribflow_graph = build_graph()
