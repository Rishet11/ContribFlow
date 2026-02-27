"""
Contribution Planner Agent

Takes repo analysis + selected issue and produces a concrete,
step-by-step action plan for making the contribution.
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from graph.state import ContribFlowState

load_dotenv()

# Lazy LLM initialization
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
            temperature=0.4,
        )
    return _llm


CONTRIB_PLAN_PROMPT = """You are an expert open source contribution coach. A developer is about to make their FIRST contribution to an open source project. Your job is to give them a clear, actionable, step-by-step plan.

## Repository: {repo}

## Selected Issue #{issue_number}: {issue_title}
{issue_body}

## Codebase Analysis:
{repo_analysis}

{domain_context_section}
{pitfall_warnings_section}

---

Generate a **numbered step-by-step contribution plan**. Be specific and actionable. The developer should be able to follow this plan and open a PR. Include:

1. **Environment Setup** — How to fork, clone, and set up the development environment (use info from CONTRIBUTING.md if available)
2. **Understand the Problem** — What exactly needs to change and why
3. **Find the Files** — Specific files and folders to open and examine
4. **Make the Changes** — What code to write or modify (be specific about the approach, not the actual code)
5. **Test Your Changes** — How to run tests, what to verify
6. **Open the PR** — Suggested PR title, description structure, and any conventions to follow
7. **Contribution Tips** — Etiquette reminders (link the issue, be patient, don't ask "is this still open")
8. **Pitfall Checklist** — Explicitly call out repo-specific pitfalls (formatters, lint, test, commit message rules) and exact commands to run
9. **Next Steps** — What to do after this PR to keep contributing

IMPORTANT RULES:
- Do NOT write actual code for the developer — they must write it themselves
- Be specific about file paths and approaches, not vague
- If there's a CONTRIBUTING.md, reference its specific instructions
- Keep your plan honest — if something is tricky, say so
- Use markdown formatting with clear sections

Respond in markdown.
"""


def contrib_planner_node(state: ContribFlowState) -> dict:
    """
    LangGraph node: Generate a step-by-step contribution plan.

    Reads: resolved_repo, selected_issue, repo_analysis, domain_context
    Writes: action_plan, current_step, error
    """
    repo = state.get("resolved_repo")
    selected_issue = state.get("selected_issue")
    repo_analysis = state.get("repo_analysis")

    if not repo or not selected_issue:
        return {
            "action_plan": None,
            "current_step": "contrib_planner",
            "error": "Missing repo or selected issue.",
        }

    if not repo_analysis:
        return {
            "action_plan": None,
            "current_step": "contrib_planner",
            "error": "Repo analysis not available. Please analyze the repo first.",
        }

    try:
        # Build domain context section
        domain_context = state.get("domain_context")
        domain_context_section = ""
        if domain_context:
            domain_context_section = f"""## Domain Context:
{domain_context}
"""

        # Build pitfall warning section
        pitfall_warnings = state.get("pitfall_warnings", [])
        pitfall_warnings_section = ""
        if pitfall_warnings:
            warnings_md = "\n".join(
                f"- {w.get('title', 'Warning')}: {w.get('recommendation', '')} (source: {w.get('source', 'repo config')})"
                for w in pitfall_warnings
            )
            pitfall_warnings_section = f"""## Repo-Specific Pitfall Warnings:
{warnings_md}
"""

        # Build prompt
        prompt = CONTRIB_PLAN_PROMPT.format(
            repo=repo,
            issue_number=selected_issue["number"],
            issue_title=selected_issue["title"],
            issue_body=selected_issue.get("body", "No description provided."),
            repo_analysis=repo_analysis,
            domain_context_section=domain_context_section,
            pitfall_warnings_section=pitfall_warnings_section,
        )

        # Ask Gemini
        response = get_llm().invoke(prompt)

        # Handle both string and list content
        content = response.content
        if isinstance(content, list):
            plan = "".join(
                block.get("text", str(block)) if isinstance(block, dict) else str(block)
                for block in content
            ).strip()
        else:
            plan = content.strip()

        return {
            "action_plan": plan,
            "current_step": "contrib_planner",
            "error": None,
        }

    except Exception as e:
        return {
            "action_plan": None,
            "current_step": "contrib_planner",
            "error": f"Error generating plan: {str(e)}",
        }
