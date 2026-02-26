"""
ContribFlow — FastAPI Backend

Phase 1-2: Analyzes repos, finds issues, and provides codebase understanding.
"""

import os
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from tools.github_tool import resolve_input
from agents.issue_finder import issue_finder_node
from agents.repo_analyst import repo_analyst_node

load_dotenv()

app = FastAPI(
    title="ContribFlow API",
    description="AI-powered open source contribution guide",
    version="0.2.0",
)

# CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session storage
sessions: dict = {}


# --- Request/Response Models ---

class AnalyzeRequest(BaseModel):
    user_input: str


class IssueResponse(BaseModel):
    number: int
    title: str
    url: str
    labels: list[str]
    body: str
    recommendation: str
    difficulty: str


class AnalyzeResponse(BaseModel):
    session_id: str
    resolved_repo: str
    input_type: str
    issues: list[IssueResponse]
    error: str | None = None


class SelectIssueRequest(BaseModel):
    session_id: str
    issue: IssueResponse


class SelectIssueResponse(BaseModel):
    session_id: str
    repo_analysis: str | None = None
    error: str | None = None


# --- API Routes ---

@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "contribflow"}


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze_repo(request: AnalyzeRequest):
    """
    Accept user input → resolve repo → find issues.

    Accepts: org name, repo URL, issue URL, or owner/repo
    Returns: session_id + resolved repo + ranked issues
    """
    user_input = request.user_input.strip()
    if not user_input:
        raise HTTPException(status_code=400, detail="Input cannot be empty")

    # Step 1: Resolve input to owner/repo
    try:
        resolved = resolve_input(user_input)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Step 2: Run Issue Finder Agent
    state = {
        "user_input": user_input,
        "resolved_repo": resolved["resolved_repo"],
        "input_type": resolved["input_type"],
        "resolved_issue_number": resolved.get("resolved_issue_number"),
        "issues": [],
        "selected_issue": None,
        "repo_analysis": None,
        "domain_context": None,
        "action_plan": None,
        "current_step": "resolving",
        "error": None,
    }

    # If user pasted an issue URL, skip issue finding
    if resolved["input_type"] == "issue_url":
        session_id = str(uuid.uuid4())
        sessions[session_id] = state
        return AnalyzeResponse(
            session_id=session_id,
            resolved_repo=resolved["resolved_repo"],
            input_type=resolved["input_type"],
            issues=[
                IssueResponse(
                    number=resolved["resolved_issue_number"],
                    title=f"Issue #{resolved['resolved_issue_number']}",
                    url=f"https://github.com/{resolved['resolved_repo']}/issues/{resolved['resolved_issue_number']}",
                    labels=[],
                    body="Direct issue URL provided. Details will be fetched in the next step.",
                    recommendation="You provided this issue directly — we'll analyze it next.",
                    difficulty="unknown",
                )
            ],
            error=None,
        )

    # Run Issue Finder
    result = issue_finder_node(state)
    state.update(result)

    # Create session
    session_id = str(uuid.uuid4())
    sessions[session_id] = state

    if state.get("error"):
        return AnalyzeResponse(
            session_id=session_id,
            resolved_repo=resolved["resolved_repo"],
            input_type=resolved["input_type"],
            issues=[],
            error=state["error"],
        )

    return AnalyzeResponse(
        session_id=session_id,
        resolved_repo=resolved["resolved_repo"],
        input_type=resolved["input_type"],
        issues=[IssueResponse(**issue) for issue in state["issues"]],
        error=None,
    )


@app.post("/api/select-issue", response_model=SelectIssueResponse)
def select_issue(request: SelectIssueRequest):
    """
    Phase 2 endpoint: User selects an issue → run Repo Analyst.

    Takes the session_id and selected issue, runs repo analysis,
    and returns a structured codebase understanding.
    """
    session_id = request.session_id
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    state = sessions[session_id]

    # Store selected issue
    state["selected_issue"] = request.issue.model_dump()

    # Run Repo Analyst Agent
    result = repo_analyst_node(state)
    state.update(result)

    sessions[session_id] = state

    if state.get("error"):
        return SelectIssueResponse(
            session_id=session_id,
            repo_analysis=None,
            error=state["error"],
        )

    return SelectIssueResponse(
        session_id=session_id,
        repo_analysis=state.get("repo_analysis"),
        error=None,
    )


@app.get("/api/session/{session_id}")
def get_session(session_id: str):
    """Get session state (for debugging / frontend polling)."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions[session_id]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

