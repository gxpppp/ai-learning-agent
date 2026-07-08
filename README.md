# AI Learning Agent

An AI-native learning enhancement system with **self-evolution capabilities** — your lifelong learning companion. It goes beyond a chatbot or note-taking app: it plans learning paths like a senior tutor, visualizes knowledge like a top-tier analyst, and optimizes itself through iterative feedback like a professional developer.

## Features (Roadmap)

| Feature | Description | Status |
|---|---|---|
| **F1 — AI Agent** | Multi-agent collaboration: Planner, Researcher, Tutor, Reviewer | Phase 1 |
| **F2 — Obsidian Integration** | Deep bidirectional integration with Obsidian vaults & knowledge graphs | Phase 1 |
| **F3 — Document Library** | Auto-generate structured, publishable doc sites from notes | Phase 3 |
| **F4 — Word Cloud** | Interactive visual analysis with TF-IDF + link weighting | Phase 2 |
| **F5 — Self-Evolution** | RLHF feedback loops, LoRA fine-tuning, prompt optimization | Phase 3 |

## Tech Stack

| Layer | Technology |
|---|---|
| Monorepo | pnpm workspaces + Turborepo |
| Obsidian Plugin | TypeScript + esbuild |
| AI Backend | Python 3.11+ + FastAPI |
| LLM Client | OpenAI SDK (compatible with DeepSeek, OpenAI, Ollama, Groq, vLLM) |
| Lint/Format | Biome |
| Vector DB | LanceDB (Phase 2) |

## Project Structure

```
ai-learning-agent/
├── apps/
│   └── obsidian-plugin/     # Obsidian plugin (TypeScript)
├── packages/
│   ├── shared-types/        # Shared TypeScript interfaces
│   ├── typescript-config/   # Shared tsconfig presets
│   └── eslint-config/       # Shared ESLint configs
├── python/
│   └── backend/             # FastAPI AI backend (Python)
├── .github/workflows/       # CI/CD
├── turbo.json
└── pnpm-workspace.yaml
```

## Getting Started

### Prerequisites

- Node.js >= 22
- pnpm >= 9
- Python >= 3.11
- uv (Python package manager)

### Setup

```bash
# Install JS dependencies
pnpm install

# Install Python dependencies
cd python/backend
uv sync

# Start backend
uv run uvicorn app.main:app --reload --port 8765

# Build Obsidian plugin (from root)
pnpm run build
```

### Configuration

Set environment variables or use the Obsidian plugin settings panel:

```bash
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=sk-xxxxxxxx
LLM_MODEL=deepseek-chat
SERVER_PORT=8765
OBSIDIAN_VAULT_PATH=/path/to/your/vault
```

## Development

```bash
pnpm run dev          # Start all packages in dev mode
pnpm run build        # Build all packages
pnpm run lint         # Run Biome linting
pnpm run check-types  # TypeScript type checking
pnpm run format       # Format with Biome
```

## License

MIT
