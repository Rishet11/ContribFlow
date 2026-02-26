"""
ContribFlow LangGraph State Schema

Shared state passed between all agents in the graph.
"""

from typing import TypedDict, Optional


class Issue(TypedDict):
    """A single GitHub issue."""
    number: int
    title: str
    url: str
    labels: list[str]
    body: str
    recommendation: str  # AI-generated explanation of why this issue is good
    difficulty: str  # "easy", "medium", "hard"


class ContribFlowState(TypedDict):
    """Shared state for the ContribFlow agent graph."""

    # Input
    user_input: str  # Raw text from user (org name, repo URL, or issue URL)

    # Resolved
    resolved_repo: Optional[str]  # "owner/repo" format
    input_type: Optional[str]  # "org", "repo_url", "issue_url"
    resolved_issue_number: Optional[int]  # If user pasted an issue URL directly

    # Issue Finder output
    issues: list[Issue]  # Top ranked issues for newcomers

    # User selection
    selected_issue: Optional[Issue]  # The issue the user picked

    # Repo Analyst output
    repo_analysis: Optional[str]  # Markdown analysis of the codebase

    # Domain Context output (optional)
    domain_context: Optional[str]  # Domain primer if scientific repo

    # Contrib Planner output
    action_plan: Optional[str]  # Final step-by-step contribution plan

    # Flow control
    current_step: str  # Which agent is currently running
    error: Optional[str]  # Error message if something went wrong
