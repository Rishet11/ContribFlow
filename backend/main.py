"""
ContribFlow — FastAPI Backend

Full pipeline: analyze → find issues → repo analysis → contribution plan.
"""

import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from tools.github_tool import resolve_input
from agents.chat import chat_node
from graph.graph import contribflow_graph

load_dotenv()

app = FastAPI(
    title="ContribFlow API",
    description="AI-powered open source contribution guide",
    version="0.3.0",
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


def invoke_supervised_flow(state: dict, start_step: str, target_step: str) -> dict:
    """
    Run the supervisor-routed LangGraph flow from start_step until target_step.
    """
    run_state = {
        **state,
        "next_step": start_step,
        "target_step": target_step,
        "current_step": "supervisor",
        "error": None,
    }

    try:
        result = contribflow_graph.invoke(run_state)
        if isinstance(result, dict):
            result["next_step"] = None
            return result
        run_state["error"] = "Workflow returned an unexpected state format."
        run_state["next_step"] = None
        return run_state
    except Exception as e:
        run_state["error"] = f"Workflow error while running {start_step.replace('_', ' ')}: {str(e)}"
        run_state["next_step"] = None
        return run_state


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
    difficulty_score: int | None = None
    activity_score: int | None = None


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


class GeneratePlanRequest(BaseModel):
    session_id: str


class GeneratePlanResponse(BaseModel):
    session_id: str
    action_plan: str | None = None
    error: str | None = None


class DomainContextRequest(BaseModel):
    session_id: str


class DomainContextResponse(BaseModel):
    session_id: str
    domain_context: str | None = None
    error: str | None = None


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str | None = None
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
        "pitfall_warnings": [],
        "action_plan": None,
        "chat_history": [],
        "next_step": None,
        "target_step": None,
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

    # Run Issue Finder through supervisor orchestration
    state = invoke_supervised_flow(
        state,
        start_step="issue_finder",
        target_step="issue_finder",
    )

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

    # Run Repo Analyst through supervisor orchestration
    state = invoke_supervised_flow(
        state,
        start_step="repo_analyst",
        target_step="repo_analyst",
    )

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


@app.post("/api/generate-plan", response_model=GeneratePlanResponse)
def generate_plan(request: GeneratePlanRequest):
    """
    Phase 3 endpoint: Generate a contribution action plan.

    Requires a completed repo analysis (select-issue must be called first).
    """
    session_id = request.session_id
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    state = sessions[session_id]

    if not state.get("repo_analysis"):
        raise HTTPException(
            status_code=400,
            detail="Repo analysis not complete. Select an issue first.",
        )

    # Run Contrib Planner through supervisor orchestration
    state = invoke_supervised_flow(
        state,
        start_step="contrib_planner",
        target_step="contrib_planner",
    )
    sessions[session_id] = state

    if state.get("error"):
        return GeneratePlanResponse(
            session_id=session_id,
            action_plan=None,
            error=state["error"],
        )

    return GeneratePlanResponse(
        session_id=session_id,
        action_plan=state.get("action_plan"),
        error=None,
    )


@app.post("/api/domain-context", response_model=DomainContextResponse)
def get_domain_context(request: DomainContextRequest):
    """
    Opt-in endpoint: Generate a domain primer for specialized repos.

    Called on-demand when the user clicks "Show Domain Primer".
    """
    session_id = request.session_id
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    state = sessions[session_id]

    # Return cached result if already generated
    if state.get("domain_context"):
        return DomainContextResponse(
            session_id=session_id,
            domain_context=state["domain_context"],
            error=None,
        )

    # Run Domain Context through supervisor orchestration
    state = invoke_supervised_flow(
        state,
        start_step="domain_context",
        target_step="domain_context",
    )
    sessions[session_id] = state

    return DomainContextResponse(
        session_id=session_id,
        domain_context=state.get("domain_context"),
        error=state.get("error"),
    )


@app.post("/api/chat", response_model=ChatResponse)
def chat_with_session(request: ChatRequest):
    """
    Session-scoped follow-up Q&A grounded in repo/issue context.
    """
    session_id = request.session_id
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    state = sessions[session_id]
    state.setdefault("chat_history", [])

    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    result = chat_node(state, message)
    if result.get("error"):
        return ChatResponse(
            session_id=session_id,
            reply=None,
            error=result["error"],
        )

    reply = result.get("reply", "")
    state["chat_history"].append({"role": "user", "content": message})
    state["chat_history"].append({"role": "assistant", "content": reply})
    sessions[session_id] = state

    return ChatResponse(
        session_id=session_id,
        reply=reply,
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
