# AI Learning Agent

> AI-Native 学习增强系统 —— 一个像真人一样使用 Obsidian 的自主 Agent。

能够搜索知识库、创建/整理笔记、扫描文档、打标签、写总结、持续自我进化。基于 LLM + RAG + 工具调用的架构，通过 OpenAI 兼容 API 连接任意 LLM Provider。

## 功能

| 功能 | 说明 | 状态 |
|---|---|---|
| **AI Chat** | SSE 流式对话，支持多 Provider，全时 RAG 搜索知识库 | ✅ |
| **Agent 工具调用** | AI 自主操作 Obsidian：创建/修改/移动/删除笔记、建文件夹、OCR 扫描 | ✅ |
| **Thinking 思考模式** | DeepSeek V4 的 reasoning 过程可视化为可折叠块 | ✅ |
| **RAG 知识引擎** | BGE-M3 嵌入 + LanceDB 向量库，自动引用来源 | ✅ |
| **知识词云** | d3-cloud SVG 交互式词云，点击词搜索笔记 | ✅ |
| **智能标签** | AI 自动推荐 frontmatter 标签 | ✅ |
| **双链推荐** | AI 推荐笔记之间的 `[[内部链接]]` | ✅ |
| **文档 OCR** | PaddleOCR PP-OCRv6（本地 GPU），图片提取文字 | ✅ |
| **多文件上传** | 拖拽 PDF/图片入聊天区，自动 OCR → 归类 → 标签 | ✅ |
| **文件监听** | 笔记变更自动同步向量索引和词云 | ✅ |
| **多 Provider** | 支持多个 OpenAI 兼容提供商的添加/切换 | ✅ |
| **反馈系统** | 👍/👎 按钮 → evolution/feedback.jsonl | ✅ |
| **自进化引擎** | Eval Harness + Prompt 变异 + 沙箱测试（OpenHarness 思路） | ✅ |

## 技术栈

| 层 | 技术 |
|---|---|
| **Monorepo** | pnpm workspaces + Turborepo |
| **Obsidian 插件** | TypeScript + esbuild + d3-cloud |
| **AI 后端** | Python 3.11+ + FastAPI |
| **LLM 客户端** | OpenAI SDK（DeepSeek / OpenAI / Ollama 兼容） |
| **向量数据库** | LanceDB（嵌入式，零服务） |
| **嵌入模型** | BGE-M3（568M，100+ 语言） |
| **OCR** | PaddleOCR PP-OCRv6（GPU，中英文） |
| **词云** | jieba 分词 + TF-IDF + d3-cloud 渲染 |
| **代码质量** | Biome + Ruff + mypy + pytest (29 tests) |
| **自进化** | OpenHarness 思路：Evaluator + Mutator + Runner |

## 项目结构

```
ai-learning-agent/
├── apps/
│   └── obsidian-plugin/          # Obsidian 插件 (TypeScript, esbuild)
│       ├── src/
│       │   ├── main.ts           # 插件入口：注册视图/命令
│       │   ├── sidecar.ts        # Python 后端进程管理 + 启动向导
│       │   ├── settings.ts       # 多 Provider 设置面板
│       │   ├── chat/             # 聊天、Agent SSE、ToolCall 渲染、上传
│       │   ├── rag/              # RAG SSE 客户端
│       │   ├── ocr/              # OCR 面板
│       │   └── knowledge/        # 词云、标签推荐
│       └── styles.css
│
├── packages/
│   └── shared-types/             # TypeScript 接口定义
│
├── python/
│   └── backend/                  # FastAPI AI 后端
│       ├── src/app/
│       │   ├── main.py           # 应用入口 + lifespan
│       │   ├── config.py         # 环境变量配置
│       │   ├── constants.py      # 共享常量（路径、chunk 等）
│       │   ├── routes/           # 13 个路由模块
│       │   ├── services/         # 11 个服务模块
│       │   ├── models/           # Pydantic 数据模型
│       │   └── evolution/        # 自进化引擎
│       ├── tests/                # pytest (29 cases)
│       └── models/               # BGE-M3 本地存放
│
├── docs/                         # 设计文档
├── .github/workflows/ci.yml      # CI/CD
├── install.ps1                   # 一键安装脚本
├── docker-compose.yml            # (可选) PaddleOCR-VL Docker
├── turbo.json
└── pnpm-workspace.yaml
```

## 快速开始

### 前置条件

- **Node.js** >= 22 + **pnpm** >= 9
- **Python** >= 3.11 + **uv** (包管理器)
- **NVIDIA GPU** >= 6GB VRAM (RAG 的 BGE-M3 需要)
- **Obsidian** >= 1.5.0

### 安装

```powershell
git clone https://github.com/gxpppp/ai-learning-agent.git
cd ai-learning-agent
pnpm install
cd python/backend && uv sync && cd ../..

# 一键安装到 Obsidian
.\install.ps1 -VaultPath "C:\Users\你的用户名\你的Vault"
```

### 首次配置

1. 重启 Obsidian → `Ctrl+P → Reload app without saving`
2. 设置 → 启用 **AI Learning Agent** 插件
3. 设置 → **AI Learning Agent** 面板：
   - Vault path：填你的 vault 绝对路径
   - 在 Provider 卡片里填 **API key**
   - Active Provider 下拉选择正确的
4. 点底部的 **Save & Restart Backend**
5. `Ctrl+Shift+L` 打开聊天

### 模型部署（首次需手动完成一次）

| 模型 | 需手动操作 | 位置 |
|---|---|---|
| **BGE-M3** | 下载到 `backend/models/bge-m3/` | ~2.2GB，HuggingFace |
| **PaddleOCR** | 插件首次使用时自动下载 | ~100MB，4 个子模型 |

### 环境变量

```bash
# LLM
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=sk-xxx
LLM_MODEL=deepseek-chat

# RAG
RAG_ENABLED=true
EMBEDDING_MODEL=backend/models/bge-m3   # 本地路径
AUTO_INDEX=true

# OCR
OCR_ENABLED=true

# Thinking
REASONING_ENABLED=true
REASONING_EFFORT=high                    # low|medium|high|max

# Agent
TOOL_PERMISSIONS=readonly                # readonly|full
```

## 开发

```bash
pnpm run dev          # 开发模式
pnpm run build        # 构建
pnpm run check-types  # TypeScript + Python 类型检查
pnpm run lint         # Biome + Ruff
uv run pytest -v      # Python 测试 (29 cases)
```

## 文档

| 文档 | 说明 |
|---|---|
| [PRD](ai_learning_agent_prd.md) | 产品需求规格说明书 |
| [OCR 集成方案](docs/ocr-integration-plan.md) | Phase 1.5 设计 |
| [知识引擎方案](docs/phase2-knowledge-engine-plan.md) | Phase 2 设计 |
| [Agent 方案](docs/phase3-agent-plan.md) | Phase 3 设计 |
| [部署指南](docs/deployment-guide.md) | 安装、模型、配置详解 |
| [故障排查](docs/troubleshooting.md) | 常见错误 Q&A |

## 路线图

```
Phase 1    ✅ 聊天 MVP (SSE + 笔记 CRUD)
Phase 1.5  ✅ OCR 集成 (PaddleOCR)
Phase 2    ✅ 知识引擎 (RAG + 标签 + 词云)
Phase 2.5  ✅ 生产就绪 (部署 + 安装 + 启动向导)
Phase 3    ✅ 自主 Agent (工具调用 + 多模型 + 思维 + 上传 + 反馈 + 自进化)
Phase 4    ⏳ 多智能体 (Planner / Researcher / Tutor / Reviewer)
```

## 许可证

MIT · gxpppp · 2026
