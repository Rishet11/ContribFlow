"""
Session Chat Agent

Handles follow-up user questions grounded in the current session context.
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from graph.state import ContribFlowState

load_dotenv()

_llm = None


def get_llm():
    global _llm
    if _llm is None:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is not set. Add it to your .env file.")
        _llm = ChatGoogleGenerativeAI(
            model="gemini-3-flash-preview",
            google_api_key=api_key,
            temperature=0.3,
        )
    return _llm


CHAT_PROMPT = """You are ContribFlow's in-session assistant.

You MUST answer using only the context below from the current repository session.
If the user asks something outside this context, say it's not available in the current session and suggest what to inspect next.

## Session Context
Repository: {repo}
Selected issue: #{issue_number} {issue_title}
Issue summary:
{issue_body}

Repo analysis:
{repo_analysis}

Domain context:
{domain_context}

Action plan:
{action_plan}

Recent chat history:
{chat_history}

## User question
{user_message}

Respond in concise markdown. Be specific and actionable.
"""


def chat_node(state: ContribFlowState, user_message: str) -> dict:
    """
    Generate a session-grounded reply for a follow-up question.

    Reads: resolved_repo, selected_issue, repo_analysis, domain_context, action_plan, chat_history
    Writes: none (endpoint updates chat history after reply)
    """
    message = (user_message or "").strip()
    if not message:
        return {"reply": None, "error": "Message cannot be empty."}

    repo = state.get("resolved_repo")
    selected_issue = state.get("selected_issue")
    repo_analysis = state.get("repo_analysis")

    if not repo or not selected_issue or not repo_analysis:
        return {
            "reply": None,
            "error": "Session context is incomplete. Select an issue and run analysis first.",
        }

    try:
        history = state.get("chat_history", [])
        history_tail = history[-8:] if history else []
        history_text = "\n".join(
            f"{item.get('role', 'user')}: {item.get('content', '')}" for item in history_tail
        ) or "No prior chat."

        prompt = CHAT_PROMPT.format(
            repo=repo,
            issue_number=selected_issue.get("number"),
            issue_title=selected_issue.get("title", ""),
            issue_body=selected_issue.get("body", "")[:2000] or "No issue body available.",
            repo_analysis=repo_analysis[:12000],
            domain_context=(state.get("domain_context") or "Not generated yet.")[:4000],
            action_plan=(state.get("action_plan") or "Not generated yet.")[:8000],
            chat_history=history_text,
            user_message=message,
        )

        response = get_llm().invoke(prompt)
        content = response.content
        if isinstance(content, list):
            reply = "".join(
                block.get("text", str(block)) if isinstance(block, dict) else str(block)
                for block in content
            ).strip()
        else:
            reply = str(content).strip()

        if not reply:
            reply = "I couldn't generate a response from the current session context."

        return {"reply": reply, "error": None}

    except Exception as e:
        return {"reply": None, "error": f"Error generating chat response: {str(e)}"}
