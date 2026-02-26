"""
Domain Context Agent

Analyzes the repo's domain (e.g., ML, chemistry, compilers) and provides
a beginner-friendly primer so contributors can understand the codebase
even if they're unfamiliar with the field.
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


DOMAIN_DETECT_PROMPT = """You are analyzing a GitHub repository.

Repository: {repo}
Description: {description}
Topics: {topics}
Language: {language}
README excerpt (first 500 chars):
{readme_excerpt}

Does this project operate in a specialized technical domain that a typical software developer might NOT be familiar with?

Examples of specialized domains: machine learning/AI, computational chemistry, bioinformatics, compiler design, signal processing, cryptography, game physics, robotics, etc.

Examples of NON-specialized domains (skip these): web apps, CLI tools, libraries, frameworks, DevOps tools, testing tools, etc.

Respond with ONLY one of:
- "SKIP" if the domain is general enough that most developers would understand it
- A short domain label (e.g., "machine learning", "computational chemistry") if specialized
"""

DOMAIN_PRIMER_PROMPT = """You are a friendly technical educator. A software developer wants to contribute to an open-source project in the domain of **{domain}**.

Repository: {repo}
Project description: {description}

Write a SHORT, beginner-friendly primer (under 300 words) that covers:

1. **What is {domain}?** — One-paragraph plain-English explanation
2. **Key terms** — 5-8 essential terms they'll encounter in this codebase, each with a one-line definition
3. **How code fits in** — How software is typically used in this domain (e.g., "ML code usually involves loading data, building models, and training them")

Keep it casual and encouraging. Use analogies where helpful. Do NOT be exhaustive — just enough so the developer can read the codebase without being totally lost.

Respond in markdown.
"""


def domain_context_node(state: ContribFlowState) -> dict:
    """
    LangGraph node: Detect domain and optionally generate a primer.

    Reads: resolved_repo, repo_analysis
    Writes: domain_context, current_step, error
    """
    repo = state.get("resolved_repo")
    repo_analysis = state.get("repo_analysis", "")

    if not repo:
        return {
            "domain_context": None,
            "current_step": "domain_context",
            "error": "Missing repo.",
        }

    try:
        # Extract info from repo_analysis for detection
        description = ""
        topics = ""
        language = ""
        readme_excerpt = ""

        # Try to get repo metadata from GitHub
        from tools.github_tool import get_repo_structure
        structure = get_repo_structure(repo)
        if structure:
            meta = structure.get("metadata", {})
            description = meta.get("description", "")
            topics = ", ".join(meta.get("topics", []))
            language = meta.get("language", "")
            readme_excerpt = (structure.get("readme", "") or "")[:500]

        # Step 1: Detect if domain is specialized
        detect_prompt = DOMAIN_DETECT_PROMPT.format(
            repo=repo,
            description=description,
            topics=topics,
            language=language,
            readme_excerpt=readme_excerpt,
        )

        detect_response = get_llm().invoke(detect_prompt)
        detect_content = detect_response.content
        if isinstance(detect_content, list):
            detect_result = "".join(
                block.get("text", str(block)) if isinstance(block, dict) else str(block)
                for block in detect_content
            ).strip()
        else:
            detect_result = detect_content.strip()

        # If domain is general, skip the primer
        if detect_result.upper() == "SKIP":
            return {
                "domain_context": None,
                "current_step": "domain_context",
                "error": None,
            }

        # Step 2: Generate domain primer
        domain = detect_result
        primer_prompt = DOMAIN_PRIMER_PROMPT.format(
            domain=domain,
            repo=repo,
            description=description,
        )

        primer_response = get_llm().invoke(primer_prompt)
        primer_content = primer_response.content
        if isinstance(primer_content, list):
            primer = "".join(
                block.get("text", str(block)) if isinstance(block, dict) else str(block)
                for block in primer_content
            ).strip()
        else:
            primer = primer_content.strip()

        return {
            "domain_context": primer,
            "current_step": "domain_context",
            "error": None,
        }

    except Exception as e:
        # Domain context is optional — don't fail the whole pipeline
        return {
            "domain_context": None,
            "current_step": "domain_context",
            "error": None,  # Silently skip on error
        }
