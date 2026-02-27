"""
Repo Pitfall Detector

Extracts repo-specific contribution pitfalls from common config/docs files.
Uses deterministic parsing first; falls back to LLM inference only if needed.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from tools.github_tool import get_github_client

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
            temperature=0.2,
        )
    return _llm


def _decode_file_content(file_obj: Any, max_chars: int = 12000) -> str:
    """Decode a GitHub file object into UTF-8 text."""
    try:
        return file_obj.decoded_content.decode("utf-8", errors="replace")[:max_chars]
    except Exception:
        return ""


def _read_first_existing_file(repo, paths: list[str], max_chars: int = 12000) -> tuple[str, str]:
    """
    Return (path, content) for the first matching file path in the repo.
    Returns ("", "") if none found.
    """
    for path in paths:
        try:
            file_obj = repo.get_contents(path)
            if isinstance(file_obj, list):
                continue
            return path, _decode_file_content(file_obj, max_chars=max_chars)
        except Exception:
            continue
    return "", ""


def _add_warning(
    warnings: list[dict[str, str]],
    seen_keys: set[str],
    key: str,
    title: str,
    recommendation: str,
    source: str,
) -> None:
    if key in seen_keys:
        return
    seen_keys.add(key)
    warnings.append(
        {
            "title": title,
            "recommendation": recommendation,
            "source": source,
        }
    )


def _extract_make_targets(makefile_text: str) -> set[str]:
    targets = set()
    for match in re.finditer(r"^([A-Za-z0-9_.-]+)\s*:", makefile_text, flags=re.MULTILINE):
        targets.add(match.group(1).lower())
    return targets


def _clean_json_text(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    return cleaned.strip()


def _fallback_infer_from_docs(readme: str, contributing: str) -> list[dict[str, str]]:
    """
    Best-effort fallback: infer up to 3 pitfalls from docs when no config signal exists.
    """
    if not (readme or contributing):
        return []

    prompt = """You are analyzing open-source contribution docs.

Infer up to 3 practical contributor pitfalls from the provided docs.
Only include concrete, actionable warnings.

README excerpt:
{readme}

CONTRIBUTING excerpt:
{contributing}

Return ONLY valid JSON in this exact shape:
[
  {{
    "title": "Short warning title",
    "recommendation": "Actionable command or step to avoid the pitfall",
    "source": "README/CONTRIBUTING inference"
  }}
]

If there is no useful signal, return [].
"""

    try:
        response = get_llm().invoke(
            prompt.format(
                readme=(readme or "")[:3500],
                contributing=(contributing or "")[:3500],
            )
        )
        content = response.content
        if isinstance(content, list):
            text = "".join(
                block.get("text", str(block)) if isinstance(block, dict) else str(block)
                for block in content
            )
        else:
            text = str(content)
        parsed = json.loads(_clean_json_text(text))
        if not isinstance(parsed, list):
            return []
        clean: list[dict[str, str]] = []
        for item in parsed[:3]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            rec = str(item.get("recommendation", "")).strip()
            source = str(item.get("source", "README/CONTRIBUTING inference")).strip()
            if title and rec:
                clean.append(
                    {
                        "title": title,
                        "recommendation": rec,
                        "source": source,
                    }
                )
        return clean
    except Exception:
        return []


def detect_repo_pitfalls(
    repo_full_name: str,
    readme_text: str = "",
    contributing_text: str = "",
) -> list[dict[str, str]]:
    """
    Detect repo-specific contribution pitfalls as structured warnings.
    """
    g = get_github_client()
    warnings: list[dict[str, str]] = []
    seen_keys: set[str] = set()

    try:
        repo = g.get_repo(repo_full_name)
    except Exception:
        return warnings

    # Load known config/docs files.
    contributing_path, repo_contributing = _read_first_existing_file(
        repo,
        ["CONTRIBUTING.md", "contributing.md", ".github/CONTRIBUTING.md"],
        max_chars=10000,
    )
    precommit_path, precommit = _read_first_existing_file(
        repo,
        [".pre-commit-config.yaml", ".pre-commit-config.yml"],
    )
    pyproject_path, pyproject = _read_first_existing_file(repo, ["pyproject.toml"])
    setup_cfg_path, setup_cfg = _read_first_existing_file(repo, ["setup.cfg"])
    eslintrc_path, eslintrc = _read_first_existing_file(
        repo,
        [".eslintrc", ".eslintrc.json", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.yaml"],
    )
    makefile_path, makefile = _read_first_existing_file(repo, ["Makefile", "makefile"])

    # Prefer explicit content passed from upstream, then repo read.
    docs_text = "\n\n".join(
        part for part in [contributing_text, repo_contributing, readme_text] if part
    ).lower()

    # --- CONTRIBUTING/README doc rules ---
    if re.search(r"\bdco\b|developer certificate of origin|sign[- ]off", docs_text):
        _add_warning(
            warnings,
            seen_keys,
            "dco_signoff",
            "Signed-off commits required",
            "Use `git commit -s` so your commit includes a Signed-off-by line.",
            contributing_path or "CONTRIBUTING/README",
        )

    if re.search(r"gpg[- ]?sign|signed commits|verified signature", docs_text):
        _add_warning(
            warnings,
            seen_keys,
            "gpg_signing",
            "Commit signing may be required",
            "Ensure Git commit signing is configured before opening your PR.",
            contributing_path or "CONTRIBUTING/README",
        )

    if re.search(r"conventional commits|commit message format|semantic commit", docs_text):
        _add_warning(
            warnings,
            seen_keys,
            "commit_convention",
            "Commit message convention enforced",
            "Follow the repository's commit format (often Conventional Commits, e.g. `feat:` / `fix:`).",
            contributing_path or "CONTRIBUTING/README",
        )

    if re.search(r"pr title|pull request title", docs_text):
        _add_warning(
            warnings,
            seen_keys,
            "pr_title_convention",
            "PR title convention likely enforced",
            "Match PR title format described in CONTRIBUTING before submission.",
            contributing_path or "CONTRIBUTING/README",
        )

    # --- Pre-commit signals ---
    precommit_lower = precommit.lower()
    if precommit:
        _add_warning(
            warnings,
            seen_keys,
            "precommit_run",
            "Pre-commit hooks configured",
            "Run `pre-commit run --all-files` before committing to avoid CI failures.",
            precommit_path,
        )

    if "black" in precommit_lower:
        _add_warning(
            warnings,
            seen_keys,
            "black_format",
            "Black formatting expected",
            "Run `black .` before committing.",
            precommit_path,
        )

    if "ruff" in precommit_lower:
        _add_warning(
            warnings,
            seen_keys,
            "ruff_lint",
            "Ruff checks configured",
            "Run `ruff check .` (and `ruff format .` if used in this repo).",
            precommit_path,
        )

    if "eslint" in precommit_lower:
        _add_warning(
            warnings,
            seen_keys,
            "eslint_lint",
            "ESLint checks configured",
            "Run `npm run lint` (or `eslint .`) before opening a PR.",
            precommit_path,
        )

    if "prettier" in precommit_lower:
        _add_warning(
            warnings,
            seen_keys,
            "prettier_format",
            "Prettier formatting expected",
            "Run `prettier --check .` or the repo's format script before committing.",
            precommit_path,
        )

    # --- pyproject/setup.cfg signals ---
    combined_python_cfg = f"{pyproject}\n{setup_cfg}".lower()
    python_cfg_source = pyproject_path or setup_cfg_path

    if "[tool.black]" in combined_python_cfg or re.search(r"\bblack\b", combined_python_cfg):
        _add_warning(
            warnings,
            seen_keys,
            "black_cfg",
            "Python formatter configured",
            "Run the configured formatter (`black` / project format command) before commit.",
            python_cfg_source or "pyproject/setup.cfg",
        )

    if "[tool.ruff]" in combined_python_cfg or re.search(r"\bruff\b", combined_python_cfg):
        _add_warning(
            warnings,
            seen_keys,
            "ruff_cfg",
            "Python linting configured",
            "Run `ruff check .` and fix lint warnings before pushing.",
            python_cfg_source or "pyproject/setup.cfg",
        )

    if "[tool.pytest]" in combined_python_cfg or re.search(r"\bpytest\b", combined_python_cfg):
        _add_warning(
            warnings,
            seen_keys,
            "pytest_cfg",
            "Pytest-based test suite detected",
            "Run `pytest` (or repo-specific test command) before opening the PR.",
            python_cfg_source or "pyproject/setup.cfg",
        )

    if "[tool.mypy]" in combined_python_cfg or re.search(r"\bmypy\b", combined_python_cfg):
        _add_warning(
            warnings,
            seen_keys,
            "mypy_cfg",
            "Type checks configured",
            "Run `mypy` (or the repo's type-check command) to prevent CI failures.",
            python_cfg_source or "pyproject/setup.cfg",
        )

    # --- ESLint signals ---
    if eslintrc:
        _add_warning(
            warnings,
            seen_keys,
            "eslintrc",
            "JavaScript/TypeScript lint rules detected",
            "Run `npm run lint` (or the workspace lint command) before creating a PR.",
            eslintrc_path,
        )

    # --- Makefile signals ---
    if makefile:
        targets = _extract_make_targets(makefile)
        if "lint" in targets:
            _add_warning(
                warnings,
                seen_keys,
                "make_lint",
                "Lint target available",
                "Run `make lint` before committing.",
                makefile_path,
            )
        if "format" in targets or "fmt" in targets:
            _add_warning(
                warnings,
                seen_keys,
                "make_format",
                "Format target available",
                "Run `make format` (or `make fmt`) before committing.",
                makefile_path,
            )
        if "test" in targets or "tests" in targets or "ci" in targets:
            _add_warning(
                warnings,
                seen_keys,
                "make_test",
                "Test/CI target available",
                "Run `make test` (or `make ci`) locally before opening a PR.",
                makefile_path,
            )

    # Fallback inference when deterministic parsing found nothing.
    if not warnings:
        inferred = _fallback_infer_from_docs(readme_text or "", contributing_text or repo_contributing)
        for item in inferred:
            _add_warning(
                warnings,
                seen_keys,
                f"inferred::{item['title'].lower()}",
                item["title"],
                item["recommendation"],
                item.get("source", "README/CONTRIBUTING inference"),
            )

    return warnings
