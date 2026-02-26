"""
GitHub Tools for ContribFlow

Wraps PyGithub to provide structured access to GitHub repos and issues.
"""

import re
import os
from datetime import datetime, timezone, timedelta
from github import Github, GithubException
from dotenv import load_dotenv

load_dotenv()


def get_github_client() -> Github:
    """Create an authenticated GitHub client."""
    token = os.getenv("GITHUB_TOKEN")
    if token:
        return Github(token)
    return Github()  # Unauthenticated (lower rate limits)


def resolve_input(user_input: str) -> dict:
    """
    Detect input type and resolve to owner/repo.

    Supports:
    - Org name: "DeepChem" → searches GitHub for the main repo
    - Repo URL: "https://github.com/owner/repo" → extracts owner/repo
    - Issue URL: "https://github.com/owner/repo/issues/123" → extracts owner/repo + issue number
    - Short form: "owner/repo" → used directly

    Returns:
        {
            "resolved_repo": "owner/repo",
            "input_type": "org" | "repo_url" | "issue_url" | "short_form",
            "resolved_issue_number": int | None
        }
    """
    user_input = user_input.strip()

    # Pattern: GitHub issue URL
    issue_match = re.match(
        r"https?://github\.com/([^/]+)/([^/]+)/issues/(\d+)",
        user_input
    )
    if issue_match:
        owner, repo, issue_num = issue_match.groups()
        return {
            "resolved_repo": f"{owner}/{repo}",
            "input_type": "issue_url",
            "resolved_issue_number": int(issue_num),
        }

    # Pattern: GitHub repo URL
    repo_match = re.match(
        r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
        user_input
    )
    if repo_match:
        owner, repo = repo_match.groups()
        return {
            "resolved_repo": f"{owner}/{repo}",
            "input_type": "repo_url",
            "resolved_issue_number": None,
        }

    # Pattern: owner/repo short form
    if "/" in user_input and len(user_input.split("/")) == 2:
        return {
            "resolved_repo": user_input,
            "input_type": "short_form",
            "resolved_issue_number": None,
        }

    # Pattern: Org or repo name — search GitHub
    g = get_github_client()
    try:
        # First try: exact org/repo match
        try:
            org = g.get_organization(user_input)
            repos = list(org.get_repos(sort="stars", direction="desc"))
            if repos:
                # Prefer repo matching org name (e.g., deepchem/deepchem)
                name_match = [r for r in repos if r.name.lower() == user_input.lower()]
                top_repo = name_match[0] if name_match else repos[0]
                return {
                    "resolved_repo": top_repo.full_name,
                    "input_type": "org",
                    "resolved_issue_number": None,
                }
        except GithubException:
            pass

        # Second try: direct repo lookup (user might be a user, not org)
        try:
            user = g.get_user(user_input)
            repos = list(user.get_repos(sort="stars", direction="desc"))
            if repos:
                top_repo = repos[0]
                return {
                    "resolved_repo": top_repo.full_name,
                    "input_type": "org",
                    "resolved_issue_number": None,
                }
        except GithubException:
            pass

        # Third try: search repos by name
        search_results = g.search_repositories(query=user_input, sort="stars")
        for repo in search_results:
            return {
                "resolved_repo": repo.full_name,
                "input_type": "org",
                "resolved_issue_number": None,
            }

    except GithubException as e:
        raise ValueError(f"Could not resolve '{user_input}': {str(e)}")

    raise ValueError(
        f"Could not find a GitHub repository for '{user_input}'. "
        "Try a GitHub URL, owner/repo, or organization name."
    )


def get_beginner_issues(repo_full_name: str, max_issues: int = 20) -> list[dict]:
    """
    Fetch open issues suitable for beginners from a GitHub repo.

    Filters by labels: good first issue, help wanted, beginner, gsoc, etc.
    Also fetches recent unlabeled issues as candidates.
    Filters out stale issues (no activity in 90+ days) and assigned issues.
    """
    g = get_github_client()

    try:
        repo = g.get_repo(repo_full_name)
    except GithubException as e:
        raise ValueError(f"Repository '{repo_full_name}' not found: {str(e)}")

    beginner_labels = [
        "good first issue",
        "good-first-issue",
        "help wanted",
        "help-wanted",
        "beginner",
        "beginner-friendly",
        "easy",
        "starter",
        "gsoc",
        "first-timers-only",
        "up-for-grabs",
        "low-hanging-fruit",
    ]

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=180)
    collected_issues = {}

    # Fetch issues with beginner-friendly labels
    for label in beginner_labels:
        try:
            issues = repo.get_issues(
                state="open",
                labels=[label],
                sort="updated",
                direction="desc",
            )
            count = 0
            for issue in issues:
                if count >= 10:
                    break
                count += 1
                try:
                    if issue.pull_request:
                        continue
                    if issue.assignee:
                        continue
                    if issue.updated_at < cutoff_date:
                        continue
                    if issue.number not in collected_issues:
                        collected_issues[issue.number] = _issue_to_dict(issue)
                except Exception:
                    continue
        except GithubException:
            continue
        except Exception:
            continue

    # If we didn't find enough labeled issues, grab recent open issues (AI will filter)
    if len(collected_issues) < 8:
        try:
            issues = repo.get_issues(
                state="open",
                sort="updated",
                direction="desc",
            )
            count = 0
            for issue in issues:
                if count >= 50:
                    break
                count += 1
                try:
                    if issue.pull_request:
                        continue
                    if issue.assignee:
                        continue
                    if issue.updated_at < cutoff_date:
                        continue
                    if issue.number not in collected_issues:
                        collected_issues[issue.number] = _issue_to_dict(issue)
                    if len(collected_issues) >= max_issues:
                        break
                except Exception:
                    continue
        except Exception:
            pass

    return list(collected_issues.values())[:max_issues]


def _issue_to_dict(issue) -> dict:
    """Convert a PyGithub issue to a plain dict."""
    return {
        "number": issue.number,
        "title": issue.title,
        "url": issue.html_url,
        "labels": [label.name for label in issue.labels],
        "body": (issue.body or "")[:2000],  # Truncate long bodies
        "created_at": issue.created_at.isoformat(),
        "updated_at": issue.updated_at.isoformat(),
        "comments_count": issue.comments,
    }


def get_repo_structure(repo_full_name: str) -> dict:
    """
    Fetch repository structure: top-level file tree, README, and CONTRIBUTING.md.

    Returns:
        {
            "file_tree": ["file1", "dir1/", ...],
            "readme": "...",
            "contributing": "...",
            "description": "...",
            "language": "...",
            "topics": [...],
            "stars": int,
        }
    """
    g = get_github_client()

    try:
        repo = g.get_repo(repo_full_name)
    except GithubException as e:
        raise ValueError(f"Repository '{repo_full_name}' not found: {str(e)}")

    result = {
        "file_tree": [],
        "readme": "",
        "contributing": "",
        "description": repo.description or "",
        "language": repo.language or "Unknown",
        "topics": repo.get_topics() if hasattr(repo, 'get_topics') else [],
        "stars": repo.stargazers_count,
    }

    # Get top-level file tree
    try:
        contents = repo.get_contents("")
        for item in contents:
            if item.type == "dir":
                result["file_tree"].append(f"{item.name}/")
            else:
                result["file_tree"].append(item.name)
        result["file_tree"].sort(key=lambda x: (not x.endswith("/"), x.lower()))
    except Exception:
        pass

    # Get README
    try:
        readme = repo.get_readme()
        result["readme"] = readme.decoded_content.decode("utf-8", errors="replace")[:5000]
    except Exception:
        pass

    # Get CONTRIBUTING.md
    try:
        for path in ["CONTRIBUTING.md", "contributing.md", ".github/CONTRIBUTING.md"]:
            try:
                contrib = repo.get_contents(path)
                result["contributing"] = contrib.decoded_content.decode("utf-8", errors="replace")[:3000]
                break
            except Exception:
                continue
    except Exception:
        pass

    return result


def get_issue_details(repo_full_name: str, issue_number: int) -> dict:
    """
    Fetch detailed information about a specific issue.

    Returns:
        {
            "number": int,
            "title": str,
            "url": str,
            "body": str,
            "labels": [...],
            "comments": [...],
            "created_at": str,
            "updated_at": str,
        }
    """
    g = get_github_client()

    try:
        repo = g.get_repo(repo_full_name)
        issue = repo.get_issue(number=issue_number)
    except GithubException as e:
        raise ValueError(f"Issue #{issue_number} not found in {repo_full_name}: {str(e)}")

    # Fetch comments
    comments = []
    try:
        for comment in issue.get_comments():
            comments.append({
                "author": comment.user.login if comment.user else "unknown",
                "body": (comment.body or "")[:1000],
                "created_at": comment.created_at.isoformat(),
            })
            if len(comments) >= 10:  # Limit to 10 comments
                break
    except Exception:
        pass

    return {
        "number": issue.number,
        "title": issue.title,
        "url": issue.html_url,
        "body": (issue.body or "")[:5000],
        "labels": [label.name for label in issue.labels],
        "comments": comments,
        "created_at": issue.created_at.isoformat(),
        "updated_at": issue.updated_at.isoformat(),
    }

