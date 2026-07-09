# AI Learning Agent

> AI-Native 自主学习助手 —— 深度集成 Obsidian，像真人一样操作你的知识库。

搜索、整理、创建笔记、扫描文档、打标签、联网搜索、持续进化。四层架构 + OpenHarness 多 Agent 协调引擎。

## 功能

| 功能 | 说明 |
|---|---|
| **AI Chat** | SSE 流式对话，多 Provider，智能路由（简单/搜索/复杂） |
| **Agent 工具调用** | 15 个工具：笔记 CRUD、文件夹管理、语义搜索、OCR、分类、摘要 |
| **联网搜索** | Tavily 实时搜索，与本地 RAG 结果合并 |
| **多 Agent 协调** | OpenHarness 引擎：Orchestrator→Searcher→Operator→Verifier |
| **Thinking 思考** | DeepSeek V4 reasoning 可折叠块 |
| **RAG 知识引擎** | BGE-M3 (GPU) + LanceDB 向量库，自动引用来源 |
| **知识词云** | d3-cloud SVG 交互式词云，点击词跳转搜索 |
| **知识图谱** | D3-force 图谱，拖拽+缩放，点击打开笔记 |
| **自进化引擎** | Prompt 变异 + LLM-as-Judge + 自动部署 |
| **文档 OCR** | PaddleOCR PP-OCRv6 (GPU) |
| **文档导出** | VitePress 兼容的 vault 导出 |
| **结构化日志** | JSON 格式 + trace_id + agent 标签 |
| **会话持久化** | Markdown 人类可读 + JSONL 机器可恢复 |

## 架构

```
Obsidian Plugin ──SSE──→ FastAPI Backend (PORT 8765)
                            │
                    ┌──── dispatcher ────┐
                    │ classifies intent  │
                    └───┬───┬───┬───────┘
                        │   │   │
            ┌───────────┘   │   └──────────────┐
            ▼               ▼                  ▼
         SIMPLE          SEARCH            COMPLEX
      JSON plan         RAG+Tavily      OpenHarness
      (legacy)          (router)        (coordinator)
                                            │
                                    15 BaseTools
                                   ┌────┼────┐
                                   │    │    │
                               infra  llm  core
                               (GPU) (API) (Vault)
```

## 技术栈

| 层 | 技术 |
|---|---|
| **Monorepo** | pnpm workspaces + Turborepo |
| **Obsidian 插件** | TypeScript + esbuild + d3/d3-cloud/d3-force |
| **后端** | Python 3.11+ + FastAPI |
| **Agent 引擎** | OpenHarness (OpenAI 兼容 Agent Loop) |
| **向量数据库** | LanceDB (嵌入式) |
| **嵌入模型** | BGE-M3 (GPU, 1024维) |
| **OCR** | PaddleOCR PP-OCRv6 (GPU) |
| **联网搜索** | Tavily API |
| **代码质量** | Biome + Ruff + mypy + pytest (77 tests) |

## 项目结构

```
ai-learning-agent/
├── apps/obsidian-plugin/          # Obsidian 插件 (TypeScript)
│   └── src/
│       ├── main.ts                # 插件入口
│       ├── sidecar.ts             # 后端进程管理
│       ├── settings.ts            # 设置面板 (含 Tavily)
│       ├── chat/                  # 聊天、Agent SSE、ToolCard
│       ├── knowledge/             # 词云、知识图谱、标签推荐
│       ├── ocr/                   # OCR 面板
│       └── rag/                   # RAG 客户端
│
├── packages/shared-types/         # 共享 TypeScript 接口
│
├── python/backend/                # FastAPI 后端
│   └── src/app/
│       ├── api/                   # L2 HTTP 路由层 (13 模块)
│       ├── core/                  # L2 核心枢纽 (dispatcher/vault/event_bus/tool_registry)
│       ├── gateway/               # L3 网关层 (OpenHarness coordinator/router/memory/session)
│       │   └── agents/            # 4 个 Agent 角色定义
│       ├── infra/                 # L4a 本地 GPU 设施 (embedding/ocr/vector_store/wordcloud/graph)
│       ├── llm/                   # L4b LLM 服务 (client/manager/prompts/search)
│       ├── models/                # Pydantic 数据模型
│       └── evolution/             # 自进化引擎
│
├── docs/                          # 设计文档
├── tests/                         # pytest (77 cases)
└── docker-compose.yml
```

## 快速开始

### 前置条件

- **Node.js** >= 22 + **pnpm** >= 9
- **Python** >= 3.11 + **uv**
- **NVIDIA GPU** >= 6GB VRAM
- **Obsidian** >= 1.5.0

### 安装

```powershell
git clone https://github.com/gxpppp/ai-learning-agent.git
cd ai-learning-agent
pnpm install
cd python/backend && uv sync && cd ../..
.\install.ps1 -VaultPath "C:\Users\用户名\YourVault"
```

### 首次配置

1. 重启 Obsidian → `Ctrl+P → Reload app without saving`
2. 设置 → 启用 **AI Learning Agent**
3. 设置 → AI Learning Agent 面板：
   - Vault path：填你的 vault 绝对路径
   - 填 Provider 的 **API key**
   - (可选) 填 **Tavily API key** 开启联网搜索
4. **Save & Restart Backend**
5. `Ctrl+Shift+L` 打开聊天

### 模型部署

| 模型 | 方式 | 大小 |
|---|---|---|
| **BGE-M3** | 下载到 `backend/models/bge-m3/` | ~2.2GB |
| **PaddleOCR** | 首次使用自动下载 | ~100MB |

### 环境变量

```bash
# LLM
PROVIDERS_JSON=[{"id":"deepseek","name":"DeepSeek","baseUrl":"https://api.deepseek.com/v1","apiKey":"sk-xxx","models":["deepseek-chat"]}]
ACTIVE_PROVIDER_ID=deepseek

# RAG
RAG_ENABLED=true
AUTO_INDEX=true

# Web Search
WEB_SEARCH_ENABLED=true
TAVILY_API_KEY=tvly-xxx

# Agent
TOOL_PERMISSIONS=readonly

# Thinking
REASONING_ENABLED=true
REASONING_EFFORT=high
```

## 开发

```bash
pnpm run dev          # 监听模式
pnpm run build        # 构建
pnpm run check-types  # TS + Python 类型检查
pnpm run lint         # Biome + Ruff
uv run pytest -v      # 77 tests
```

## API 端点 (25)

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/agent/chat` | 主聊天（智能路由） |
| `POST` | `/api/chat/stream` | SSE 流式聊天 |
| `POST` | `/api/rag/query` | RAG 向量搜索 |
| `POST` | `/api/notes/*` | 笔记 CRUD (4 端点) |
| `GET` | `/api/ocr/health` | OCR 状态 |
| `POST` | `/api/ocr/parse` | OCR 识别 |
| `POST` | `/api/ocr/parse-and-save` | OCR + 保存 |
| `POST` | `/api/tags/suggest` | 标签建议 |
| `POST` | `/api/links/recommend` | 双链推荐 |
| `POST` | `/api/vault/index` | 索引 Vault |
| `GET` | `/api/vault/status` | 索引状态 |
| `POST` | `/api/wordcloud/generate` | 词云数据 |
| `POST` | `/api/models/fetch` | 获取模型列表 |
| `POST` | `/api/upload/` | 文件上传 |
| `POST` | `/api/feedback` | 用户反馈 |
| `GET` | `/api/graph/` | 知识图谱数据 |
| `POST` | `/api/export/` | 文档导出 |
| `POST` | `/api/evolution/sync` | 进化提示词同步 |
| `GET` | `/api/evolution/active-prompt` | 当前进化提示词 |

## 路线图

```
Phase 1    ✅ 聊天 MVP (SSE + 笔记 CRUD)
Phase 1.5  ✅ OCR 集成 (PaddleOCR)
Phase 2    ✅ 知识引擎 (RAG + 标签 + 词云)
Phase 2.5  ✅ 生产就绪 (部署 + 安装)
Phase 3    ✅ 自主 Agent (工具调用 + 自进化 + 反馈)
Phase 4    ✅ 多 Agent 协调 (OpenHarness + 网关 + 图谱)
```

## 许可证

MIT · gxpppp · 2026
