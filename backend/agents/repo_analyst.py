"""
Repo Analyst Agent

Analyzes a GitHub repository's structure and explains the selected issue
in plain English. Makes an unfamiliar codebase feel approachable.
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from graph.state import ContribFlowState
from tools.github_tool import get_repo_structure, get_issue_details
from agents.pitfall_detector import detect_repo_pitfalls

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
            temperature=0.3,
        )
    return _llm


REPO_ANALYSIS_PROMPT = """You are an expert open source mentor helping a developer understand a codebase for the first time.

## Repository: {repo}
**Description:** {description}
**Primary Language:** {language}
**Stars:** {stars}
**Topics:** {topics}

## File Structure (top-level):
{file_tree}

## README (first 5000 chars):
{readme}

## CONTRIBUTING.md:
{contributing}

## Repo Pitfall Signals (deterministic extraction):
{pitfall_context}

## Selected Issue #{issue_number}: {issue_title}
{issue_body}

## Issue Comments:
{issue_comments}

---

Your job is to produce a clear, structured analysis that helps a FIRST-TIME contributor understand:

1. **Project Overview** — What does this project do? Explain in 2-3 simple sentences. No jargon.
2. **Tech Stack** — What language, frameworks, and tools does this project use?
3. **Contribution Workflow** — How does this repo accept contributions? (fork? branch? PR format? required tests?)
4. **Issue Breakdown** — Explain the selected issue in plain English:
   - What is being asked?
   - Why does it matter?
   - What files/folders are likely relevant?
5. **Relevant Files** — List the specific files or directories the contributor should look at.
6. **Difficulty Assessment** — Honest rating of how hard this issue is for a first-timer.
7. **Pitfall Warnings** — Mention repo-specific pitfalls detected from configs/docs and how to avoid them.

Be concise but thorough. Use markdown formatting. If you detect scientific or domain-specific terminology, flag it clearly — the Domain Context agent will handle deeper explanations.

Respond in markdown format.
"""


def repo_analyst_node(state: ContribFlowState) -> dict:
    """
    LangGraph node: Analyze repository and explain the selected issue.

    Reads: resolved_repo, selected_issue
    Writes: repo_analysis, current_step, error
    """
    repo = state.get("resolved_repo")
    selected_issue = state.get("selected_issue")

    if not repo:
        return {
            "repo_analysis": None,
            "current_step": "repo_analyst",
            "error": "No repository resolved.",
        }

    if not selected_issue:
        return {
            "repo_analysis": None,
            "current_step": "repo_analyst",
            "error": "No issue selected.",
        }

    try:
        # Fetch repo structure
        repo_info = get_repo_structure(repo)

        # Fetch detailed issue info
        issue_details = get_issue_details(repo, selected_issue["number"])

        # Detect deterministic repo-specific pitfalls from docs/config files
        pitfall_warnings = detect_repo_pitfalls(
            repo,
            readme_text=repo_info.get("readme", ""),
            contributing_text=repo_info.get("contributing", ""),
        )

        # Format file tree
        file_tree = "\n".join(f"  {'📁' if f.endswith('/') else '📄'} {f}" for f in repo_info["file_tree"])

        # Format issue comments
        comments_text = ""
        if issue_details.get("comments"):
            for comment in issue_details["comments"]:
                comments_text += f"\n**@{comment['author']}** ({comment['created_at']}):\n{comment['body']}\n"
        else:
            comments_text = "No comments yet."

        # Format deterministic pitfall context for the LLM
        if pitfall_warnings:
            pitfall_context = "\n".join(
                f"- {w['title']}: {w['recommendation']} (source: {w['source']})"
                for w in pitfall_warnings
            )
        else:
            pitfall_context = "No explicit pitfalls detected from standard config/docs files."

        # Build prompt
        prompt = REPO_ANALYSIS_PROMPT.format(
            repo=repo,
            description=repo_info["description"],
            language=repo_info["language"],
            stars=repo_info["stars"],
            topics=", ".join(repo_info["topics"]) if repo_info["topics"] else "none",
            file_tree=file_tree or "Could not fetch file tree.",
            readme=repo_info["readme"] or "No README found.",
            contributing=repo_info["contributing"] or "No CONTRIBUTING.md found.",
            pitfall_context=pitfall_context,
            issue_number=selected_issue["number"],
            issue_title=selected_issue["title"],
            issue_body=issue_details.get("body", selected_issue.get("body", "No description.")),
            issue_comments=comments_text,
        )

        # Ask Gemini to analyze
        response = get_llm().invoke(prompt)

        # Handle both string and list content formats
        content = response.content
        if isinstance(content, list):
            analysis = "".join(
                block.get("text", str(block)) if isinstance(block, dict) else str(block)
                for block in content
            ).strip()
        else:
            analysis = content.strip()

        # Ensure pitfalls always appear explicitly for the frontend/user.
        if pitfall_warnings:
            pitfalls_md = "\n".join(
                f"- **{w['title']}**: {w['recommendation']} _(Source: `{w['source']}`)_"
                for w in pitfall_warnings
            )
            analysis = f"""{analysis}

## Repo-Specific Pitfall Warnings
{pitfalls_md}
"""

        return {
            "repo_analysis": analysis,
            "pitfall_warnings": pitfall_warnings,
            "current_step": "repo_analyst",
            "error": None,
        }

    except Exception as e:
        return {
            "repo_analysis": None,
            "pitfall_warnings": [],
            "current_step": "repo_analyst",
            "error": f"Error analyzing repository: {str(e)}",
        }
