# AI Learning Agent

> AI-Native 学习增强系统 —— 一个像真人一样使用 Obsidian 的自主 Agent。

基于 LLM + RAG + 工具调用，能够：搜索知识库、创建/整理笔记、扫描文档、打标签、写总结、持续自我进化。

## 架构

```
┌──────────────────────────────────────────────────────────────┐
│  Obsidian Plugin (TypeScript + esbuild)                      │
│  ┌──────────┐ ┌──────────────┐ ┌────────────┐               │
│  │ ChatView │ │ WordCloudView│ │  OcrView   │               │
│  │ + Agent  │ │  (d3-cloud)  │ │ (PaddleOCR)│               │
│  └────┬─────┘ └──────┬───────┘ └─────┬──────┘               │
│       │              │               │                       │
│       ▼              ▼               ▼                       │
│  ┌─────────────────────────────────────────────────────┐     │
│  │              Sidecar Manager                        │     │
│  │        (spawns/manages Python backend)              │     │
│  └───────────────────────┬─────────────────────────────┘     │
└──────────────────────────┼──────────────────────────────────┘
                           │ HTTP + SSE
┌──────────────────────────┼──────────────────────────────────┐
│  Python Backend (FastAPI)                                   │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌──────────────┐  │
│  │  chat    │ │   rag    │ │    ocr    │ │    vault     │  │
│  │  (SSE)   │ │ (BGE-M3) │ │(PaddleOCR)│ │  (indexer)   │  │
│  └──────────┘ └────┬─────┘ └─────┬─────┘ └──────┬───────┘  │
│                    │             │              │            │
│        ┌───────────┼─────────────┼──────────────┘            │
│        ▼           ▼             ▼                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                     │
│  │ LanceDB  │ │ BGE-M3   │ │ Docker   │                     │
│  │(向量检索) │ │(嵌入模型) │ │(OCR服务) │                     │
│  └──────────┘ └──────────┘ └──────────┘                     │
└──────────────────────────────────────────────────────────────┘
```

## 功能

| 功能 | 说明 | 状态 |
|---|---|---|
| **AI Chat** | SSE 流式对话，多 Provider 切换，全时 RAG 搜索知识库 | 可用 |
| **RAG 知识引擎** | BGE-M3 嵌入 + LanceDB 向量库，自动引用来源 | 可用 |
| **知识词云** | d3-cloud SVG 交互式词云，点击词搜索笔记 | 可用 |
| **智能标签** | AI 自动推荐 frontmatter 标签 | 可用 |
| **双链推荐** | AI 推荐笔记之间的 `[[内部链接]]` | 可用 |
| **文档 OCR** | PaddleOCR-VL 0.9B，PDF/图片提取为 Markdown | 可用 |
| **文件监听** | 笔记变更自动同步向量索引和词云 | 可用 |
| **Agent 工具调用** | AI 自主操作 Obsidian（创建/修改/整理笔记） | 3.2 |
| **多模态上传** | 拖拽文件自动 OCR → 归类 → 标签 | 3.3 |
| **自进化引擎** | 反馈收集 → Eval Harness → Prompt 变异 | 3.5 |
| **文档库生成** | Starlight/Astro 静态站自动部署 | 3+ |

## 技术栈

| 层 | 技术 |
|---|---|
| **Monorepo** | pnpm workspaces + Turborepo |
| **Obsidian 插件** | TypeScript + esbuild + d3-cloud |
| **AI 后端** | Python 3.11+ + FastAPI |
| **LLM 客户端** | OpenAI SDK (DeepSeek/OpenAI/Ollama 兼容) |
| **向量数据库** | LanceDB (嵌入式) |
| **嵌入模型** | BGE-M3 (568M, 100+ 语言) |
| **OCR** | PaddleOCR-VL 0.9B (Docker) |
| **词云** | jieba + d3-cloud |
| **代码质量** | Biome + Ruff + mypy + pytest |

## 项目结构

```
ai-learning-agent/
├── apps/
│   └── obsidian-plugin/     # Obsidian 插件 (TypeScript)
│       ├── src/
│       │   ├── main.ts      # 插件入口：注册视图、命令
│       │   ├── sidecar.ts   # Python 后端进程管理
│       │   ├── settings.ts  # 设置面板
│       │   ├── chat/        # 聊天面板、SSE 客户端、渲染器
│       │   ├── rag/         # RAG 客户端
│       │   ├── ocr/         # OCR 面板
│       │   └── knowledge/   # 词云、标签推荐
│       └── styles.css
├── packages/
│   └── shared-types/        # TypeScript 接口定义
├── python/
│   └── backend/             # FastAPI AI 后端
│       ├── src/app/
│       │   ├── main.py      # 应用入口 + lifespan
│       │   ├── config.py    # 环境变量配置
│       │   ├── routes/      # chat, rag, ocr, notes, tags, vault, wordcloud
│       │   ├── services/    # llm_client, embedding, indexer, vector_store...
│       │   └── models/      # Pydantic 数据模型
│       ├── tests/           # pytest 测试
│       └── evolution/       # 自进化引擎 (Phase 3)
├── docs/                    # 设计文档
├── docker-compose.yml       # PaddleOCR-VL 服务
├── install.ps1              # 一键安装脚本
└── turbo.json               # Turborepo 配置
```

## 快速开始

### 前置条件

- **Node.js** >= 22
- **pnpm** >= 9
- **Python** >= 3.11
- **uv** (Python 包管理器)
- **Docker Desktop** (OCR 功能需要)
- **NVIDIA GPU** >= 6GB VRAM (RAG 需要)

### 安装

```powershell
# 克隆仓库
git clone https://github.com/gxpppp/ai-learning-agent.git
cd ai-learning-agent

# 安装 JS 依赖
pnpm install

# 安装 Python 依赖
cd python/backend && uv sync && cd ../..

# 一键安装到 Obsidian
.\install.ps1 -VaultPath "C:\Users\你的用户名\你的Vault"
```

### 配置

1. 重启 Obsidian
2. `Settings → AI Learning Agent`
3. 填写 **API Key**（DeepSeek/OpenAI/Ollama）
4. 填写 **Vault Path**
5. 插件自动启动后端

### 开发

```bash
pnpm run dev          # 开发模式
pnpm run build        # 构建
pnpm run check-types  # TypeScript + Python 类型检查
pnpm run lint         # Biome + Ruff lint
pnpm run format       # 格式化
```

### 环境变量

```bash
# LLM
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=sk-xxx
LLM_MODEL=deepseek-chat

# 服务器
SERVER_PORT=8765

# RAG (可选)
RAG_ENABLED=true
EMBEDDING_MODEL=BAAI/bge-m3
AUTO_INDEX=true

# OCR (可选, 需 Docker)
OCR_ENABLED=true
OCR_SERVER_URL=http://127.0.0.1:8080/v1
```

## 文档

| 文档 | 说明 |
|---|---|
| [PRD](ai_learning_agent_prd.md) | 产品需求规格说明书 |
| [OCR 集成方案](docs/ocr-integration-plan.md) | PaddleOCR-VL 设计文档 |
| [Phase 2 知识引擎](docs/phase2-knowledge-engine-plan.md) | RAG + 词云 + 标签方案 |
| [Phase 3 Agent 方案](docs/phase3-agent-plan.md) | Agent 工具调用 + 自进化引擎 |

## 路线图

```
Phase 1    ✅  聊天 MVP (SSE 流式 + 笔记 CRUD)
Phase 1.5  ✅  OCR 集成 (PaddleOCR-VL Docker)
Phase 2    ✅  知识引擎 (RAG + 标签 + 词云)
Phase 2.5  ✅  生产就绪 (安装脚本 + 启动向导 + 部署)
Phase 3    📋  自主 Agent (工具调用 + 多 Provider + 自进化)
Phase 4    ⏳  多智能体 (Planner/Researcher/Tutor/Reviewer)
```

## 许可证

MIT

## 致谢

- [OpenHarness](https://github.com/gxpppp/openharness) — 自进化引擎设计灵感
- [OpenBMB MiniCPM-V](https://github.com/OpenBMB/MiniCPM-V) — 视觉模型参考
- [PaddleOCR-VL](https://github.com/PaddlePaddle/PaddleOCR) — 文档解析引擎
