"""
Issue Finder Agent

Finds and ranks the best beginner-friendly issues in a GitHub repo.
Uses Gemini to analyze and explain why each issue is a good starting point.
"""

import os
import json
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from graph.state import ContribFlowState
from tools.github_tool import get_beginner_issues

load_dotenv()

# Lazy LLM initialization (avoids crash when API key isn't set at import time)
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

ISSUE_RANKING_PROMPT = """You are an expert open source contribution advisor. 
A developer wants to make their first contribution to the repository: {repo}

Here are the open issues found in the repository:

{issues_text}

Your job:
1. Analyze each issue and determine how suitable it is for a FIRST-TIME contributor.
2. Select the TOP 3-5 best issues (fewer if there aren't enough good ones).
3. For each selected issue, provide:
   - A clear, plain-English explanation of what the issue is asking
   - WHY this issue is good for a newcomer (e.g., "documentation fix, no domain knowledge needed")
   - A difficulty rating: "easy", "medium", or "hard"

IMPORTANT: If none of the issues are suitable for beginners, say so honestly. Don't recommend bad issues.

Respond in this exact JSON format (no markdown, no code blocks, just raw JSON):
[
  {{
    "number": <issue_number>,
    "title": "<issue_title>",
    "url": "<issue_url>",
    "labels": ["label1", "label2"],
    "body": "<first 500 chars of issue body>",
    "recommendation": "<your plain-English explanation of what this issue needs and why it's good for a newcomer>",
    "difficulty": "easy|medium|hard"
  }}
]

If no issues are suitable, respond with:
[]
"""


def issue_finder_node(state: ContribFlowState) -> dict:
    """
    LangGraph node: Find and rank beginner-friendly issues.
    
    Reads: resolved_repo
    Writes: issues, current_step, error
    """
    repo = state.get("resolved_repo")
    if not repo:
        return {
            "issues": [],
            "current_step": "issue_finder",
            "error": "No repository resolved. Please provide a valid GitHub repo.",
        }

    try:
        # Fetch raw issues from GitHub
        raw_issues = get_beginner_issues(repo)

        if not raw_issues:
            return {
                "issues": [],
                "current_step": "issue_finder",
                "error": f"No open issues found in {repo}. The repo might not have any beginner-friendly issues right now.",
            }

        # Format issues for the LLM
        issues_text = ""
        for issue in raw_issues:
            labels_str = ", ".join(issue["labels"]) if issue["labels"] else "none"
            issues_text += f"""
---
Issue #{issue['number']}: {issue['title']}
URL: {issue['url']}
Labels: {labels_str}
Comments: {issue['comments_count']}
Last updated: {issue['updated_at']}
Body: {issue['body'][:500]}
---
"""

        # Ask Gemini to rank and explain
        prompt = ISSUE_RANKING_PROMPT.format(repo=repo, issues_text=issues_text)
        response = get_llm().invoke(prompt)

        # Parse the response — handle both string and list content formats
        content = response.content
        if isinstance(content, list):
            # Gemini 3 returns a list of content blocks
            response_text = "".join(
                block.get("text", str(block)) if isinstance(block, dict) else str(block)
                for block in content
            ).strip()
        else:
            response_text = content.strip()
        # Clean up potential markdown code blocks
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1]
        if response_text.endswith("```"):
            response_text = response_text.rsplit("```", 1)[0]
        response_text = response_text.strip()

        ranked_issues = json.loads(response_text)

        return {
            "issues": ranked_issues,
            "current_step": "issue_finder",
            "error": None,
        }

    except json.JSONDecodeError:
        # If LLM response isn't valid JSON, return raw issues with basic info
        fallback_issues = []
        for issue in raw_issues[:5]:
            fallback_issues.append({
                "number": issue["number"],
                "title": issue["title"],
                "url": issue["url"],
                "labels": issue["labels"],
                "body": issue["body"][:500],
                "recommendation": "This issue appears to be open and available for contribution.",
                "difficulty": "medium",
            })
        return {
            "issues": fallback_issues,
            "current_step": "issue_finder",
            "error": None,
        }

    except Exception as e:
        return {
            "issues": [],
            "current_step": "issue_finder",
            "error": f"Error finding issues: {str(e)}",
        }
