# ContribFlow 🚀

**AI-powered open source contribution guide** — From zero to Pull Request.

Give ContribFlow any GitHub repo, org, or issue URL, and it will:
1. 🔍 **Find** beginner-friendly issues ranked by AI
2. 🧠 **Analyze** the codebase and explain the project architecture
3. 🧬 **Explain** the domain (for niche repos like ML/chemistry/compilers)
4. 📋 **Generate** a step-by-step action plan to make your first contribution

---

## ⚡ Quick Start

### Prerequisites
- **Python 3.11+**
- **Node.js 18+**
- **GitHub Token** ([create one](https://github.com/settings/tokens) with `public_repo` scope)
- **Google AI API Key** ([get one](https://aistudio.google.com/apikey))

### 1. Clone & Setup Backend
```bash
git clone https://github.com/Rishet11/ContribFlow.git
cd ContribFlow/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your GITHUB_TOKEN and GOOGLE_API_KEY
```

### 2. Setup Frontend
```bash
cd ../frontend
npm install
```

### 3. Run
```bash
# Terminal 1 — Backend
cd backend
source venv/bin/activate
uvicorn main:app --reload

# Terminal 2 — Frontend
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) and start contributing! 🎉

---

## 🏗 Architecture

```
ContribFlow/
├── backend/
│   ├── main.py                  # FastAPI server
│   ├── agents/
│   │   ├── issue_finder.py      # Finds & ranks beginner issues
│   │   ├── repo_analyst.py      # Analyzes codebase structure
│   │   ├── domain_context.py    # Explains specialized domains
│   │   └── contrib_planner.py   # Generates action plans
│   ├── tools/
│   │   └── github_tool.py       # GitHub API utilities
│   └── graph/
│       ├── state.py             # Shared state schema
│       └── graph.py             # LangGraph workflow
└── frontend/
    └── src/app/
        ├── page.tsx             # Main UI
        ├── layout.tsx           # Root layout
        └── globals.css          # Premium dark theme
```

### Tech Stack
| Layer | Technology |
|-------|-----------|
| **LLM** | Gemini 3 Flash Preview |
| **Agent Framework** | LangGraph + LangChain |
| **Backend** | FastAPI (Python) |
| **Frontend** | Next.js 16 (React) |
| **GitHub API** | PyGithub |

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/analyze` | Find beginner-friendly issues |
| `POST` | `/api/select-issue` | Analyze repo + detect domain |
| `POST` | `/api/generate-plan` | Generate contribution plan |
| `GET` | `/api/session/{id}` | Get session state |

---

## 🤖 Agent Pipeline

```
User Input → Resolve Repo → Issue Finder → [User selects issue]
                                                    ↓
                                            Repo Analyst → Domain Context → Contribution Planner
```

1. **Issue Finder** — Scans open issues for beginner-friendly labels, ranks them by approachability using Gemini
2. **Repo Analyst** — Reads README, CONTRIBUTING.md, file tree, and issue details to explain the project
3. **Domain Context** — Auto-detects specialized domains (ML, chemistry, etc.) and generates a beginner primer
4. **Contribution Planner** — Creates a concrete, step-by-step plan: setup → code → test → PR

---

## 📝 License

MIT

---

Built with ❤️ to make open source more accessible.
