"use client";

import { useState } from "react";

/* ─── Types ─── */
interface Issue {
  number: number;
  title: string;
  url: string;
  labels: string[];
  body: string;
  recommendation: string;
  difficulty: string;
}

interface AnalyzeResponse {
  session_id: string;
  resolved_repo: string;
  input_type: string;
  issues: Issue[];
  error: string | null;
}

/* ─── Constants ─── */
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const EXAMPLES = [
  "DeepChem",
  "pallets/flask",
  "https://github.com/langchain-ai/langchain",
  "scikit-learn",
];

/* ─── Steps ─── */
type AppStep = "input" | "issues" | "analyzing" | "analysis";

/* ─── Component ─── */
export default function HomePage() {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<AppStep>("input");
  const [repoAnalysis, setRepoAnalysis] = useState<string | null>(null);
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);

  const handleAnalyze = async () => {
    if (!input.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);
    setRepoAnalysis(null);
    setSelectedIssue(null);
    setStep("input");

    try {
      const res = await fetch(`${API_BASE}/api/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_input: input.trim() }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => null);
        throw new Error(errData?.detail || `Server error (${res.status})`);
      }

      const data: AnalyzeResponse = await res.json();

      if (data.error) {
        setError(data.error);
      } else {
        setResult(data);
        setStep("issues");
      }
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Something went wrong. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  const handleIssueSelect = async (issue: Issue) => {
    if (!result) return;

    setSelectedIssue(issue);
    setStep("analyzing");
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/api/select-issue`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: result.session_id,
          issue: issue,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => null);
        throw new Error(errData?.detail || `Server error (${res.status})`);
      }

      const data = await res.json();

      if (data.error) {
        setError(data.error);
        setStep("issues");
      } else {
        setRepoAnalysis(data.repo_analysis);
        setStep("analysis");
      }
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Something went wrong. Please try again."
      );
      setStep("issues");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !loading) handleAnalyze();
  };

  const handleExampleClick = (example: string) => {
    setInput(example);
  };

  const handleReset = () => {
    setInput("");
    setResult(null);
    setError(null);
    setRepoAnalysis(null);
    setSelectedIssue(null);
    setStep("input");
  };

  const handleBackToIssues = () => {
    setStep("issues");
    setRepoAnalysis(null);
    setSelectedIssue(null);
    setError(null);
  };

  /* ─── Progress Steps ─── */
  const progressSteps = [
    { label: "Find Issues", icon: "🔍" },
    { label: "Select Issue", icon: "✋" },
    { label: "Analyze Repo", icon: "🧠" },
  ];

  const currentProgressIndex =
    step === "input" ? -1
    : step === "issues" ? 1
    : step === "analyzing" ? 2
    : step === "analysis" ? 3
    : 0;

  return (
    <div className="page-container">
      {/* ─── HERO ─── */}
      <section className="hero">
        <div className="hero-badge">
          <span className="dot" />
          Powered by AI Agents
        </div>
        <h1>
          From zero to{" "}
          <span className="gradient-text">Pull Request</span>
        </h1>
        <p className="subtitle">
          Give me any GitHub repo or org name — I&apos;ll find you the right issue,
          explain the codebase, and give you a clear plan to make your first
          contribution.
        </p>
      </section>

      {/* ─── INPUT ─── */}
      <section className="input-section">
        <div className="input-wrapper">
          <input
            className="input-field"
            type="text"
            placeholder="Enter a GitHub org, repo URL, or issue URL..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading || step === "analyzing"}
            id="main-input"
          />
          <button
            className="analyze-btn"
            onClick={handleAnalyze}
            disabled={loading || !input.trim() || step === "analyzing"}
            id="analyze-btn"
          >
            {loading ? "Analyzing..." : "Find Issues"}
          </button>
        </div>

        {step === "input" && !loading && (
          <div className="input-examples">
            <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
              Try:
            </span>
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                className="example-chip"
                onClick={() => handleExampleClick(ex)}
              >
                {ex}
              </button>
            ))}
          </div>
        )}
      </section>

      {/* ─── PROGRESS TRACKER ─── */}
      {(step !== "input" || loading) && (
        <section className="progress-tracker">
          {progressSteps.map((s, index) => (
            <div
              key={s.label}
              className={`progress-step ${
                index < currentProgressIndex ? "completed" : ""
              } ${index === currentProgressIndex ? "active" : ""}`}
            >
              <div className="progress-step-icon">
                {index < currentProgressIndex ? "✓" : s.icon}
              </div>
              <span className="progress-step-label">{s.label}</span>
              {index < progressSteps.length - 1 && (
                <div className={`progress-line ${index < currentProgressIndex ? "filled" : ""}`} />
              )}
            </div>
          ))}
        </section>
      )}

      {/* ─── LOADING (Issue Finding) ─── */}
      {loading && (
        <section className="loading-section">
          <div className="loading-spinner" />
          <p className="loading-text">Finding beginner-friendly issues...</p>
          <p className="loading-subtext">
            Scanning the repository and analyzing open issues with AI
          </p>
        </section>
      )}

      {/* ─── ANALYZING (Repo Analysis) ─── */}
      {step === "analyzing" && (
        <section className="loading-section">
          <div className="loading-spinner" />
          <p className="loading-text">Analyzing the codebase...</p>
          <p className="loading-subtext">
            Reading README, file structure, and issue details to give you a complete picture
          </p>
        </section>
      )}

      {/* ─── ERROR ─── */}
      {error && step !== "analyzing" && !loading && (
        <section className="error-section">
          <div className="error-box">{error}</div>
          <button className="retry-btn" onClick={handleReset}>
            ← Try another repo
          </button>
        </section>
      )}

      {/* ─── ISSUE CARDS ─── */}
      {step === "issues" && result && !loading && (
        <section className="results-section">
          <div className="results-header">
            <h2>
              {result.issues.length === 0
                ? "No issues found"
                : "Pick an issue to get started"}
            </h2>
            <span className="repo-tag">📦 {result.resolved_repo}</span>
          </div>

          {result.issues.length === 0 && (
            <div className="error-box" style={{ textAlign: "center" }}>
              No beginner-friendly issues found in this repo right now.
              <br />
              Try a different repository!
            </div>
          )}

          <div className="issue-cards">
            {result.issues.map((issue) => (
              <div
                key={issue.number}
                className="issue-card"
                onClick={() => handleIssueSelect(issue)}
                id={`issue-card-${issue.number}`}
              >
                <div className="issue-card-header">
                  <span className="issue-card-title">{issue.title}</span>
                  <span className="issue-number">#{issue.number}</span>
                </div>

                {issue.labels.length > 0 && (
                  <div className="issue-labels">
                    {issue.labels.map((label) => (
                      <span key={label} className="issue-label">
                        {label}
                      </span>
                    ))}
                  </div>
                )}

                <p className="issue-card-body">{issue.recommendation}</p>

                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span
                    className={`difficulty-badge difficulty-${issue.difficulty}`}
                  >
                    {issue.difficulty === "easy" && "🟢"}
                    {issue.difficulty === "medium" && "🟡"}
                    {issue.difficulty === "hard" && "🔴"}
                    {issue.difficulty === "unknown" && "⚪"}
                    {" "}{issue.difficulty}
                  </span>
                  <span className="select-hint">Click to analyze →</span>
                </div>
              </div>
            ))}
          </div>

          <div style={{ textAlign: "center", marginTop: "24px" }}>
            <button className="retry-btn" onClick={handleReset}>
              ← Analyze another repo
            </button>
          </div>
        </section>
      )}

      {/* ─── REPO ANALYSIS ─── */}
      {step === "analysis" && repoAnalysis && selectedIssue && (
        <section className="results-section">
          <div className="results-header">
            <h2>Codebase Analysis</h2>
            <span className="repo-tag">📦 {result?.resolved_repo}</span>
          </div>

          <div className="selected-issue-banner">
            <span className="selected-issue-label">Selected Issue</span>
            <span className="selected-issue-title">
              #{selectedIssue.number} — {selectedIssue.title}
            </span>
          </div>

          <div
            className="analysis-content"
            dangerouslySetInnerHTML={{ __html: formatMarkdown(repoAnalysis) }}
          />

          <div className="analysis-actions">
            <button className="retry-btn" onClick={handleBackToIssues}>
              ← Pick a different issue
            </button>
            <a
              href={selectedIssue.url}
              target="_blank"
              rel="noopener noreferrer"
              className="analyze-btn"
              style={{ textDecoration: "none", display: "inline-block" }}
            >
              Open Issue on GitHub →
            </a>
          </div>
        </section>
      )}

      {/* ─── FEATURES (shown on initial state) ─── */}
      {step === "input" && !loading && !error && (
        <section className="features-row">
          <div className="feature-card">
            <div className="feature-icon">🔍</div>
            <h3>Smart Issue Finder</h3>
            <p>AI scans and ranks issues by beginner-friendliness</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">🧠</div>
            <h3>Codebase Analyst</h3>
            <p>Understand any repo in under 2 minutes</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">📋</div>
            <h3>Action Planner</h3>
            <p>Get a step-by-step plan to make your first PR</p>
          </div>
        </section>
      )}
    </div>
  );
}

/* ─── Simple Markdown → HTML ─── */
function formatMarkdown(md: string): string {
  let html = md
    // Headers
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    // Bold
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // Italic
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // Unordered lists
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/^(\d+)\. (.+)$/gm, '<li>$2</li>')
    // Line breaks
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br/>');

  // Wrap lists
  html = html.replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>');
  // Remove nested ul/ul
  html = html.replace(/<\/ul>\s*<ul>/g, '');

  return `<p>${html}</p>`;
}
