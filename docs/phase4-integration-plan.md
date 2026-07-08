# Phase 4 整合方案：OpenHarness 多 Agent 协调层 + 四层架构重构

> 核心目标：将 AI Learning Agent 从单 Agent 工具调用升级为多 Agent 协作系统，
> 同时重构后端为清晰的分层架构，引入 OpenHarness 作为网关引擎。

---

## 一、总体架构：四层 + 网关

```
┌──────────────────────────────────────────────────────────────┐
│  L1 表现层 — Obsidian Plugin (TypeScript)                     │
│  ─────────────────────────────────                           │
│  只做三件事:                                                   │
│  1. 聊天 UI 渲染 (SSE stream → Markdown → Thinking/ToolCard)  │
│  2. 命令传递 (用户输入 → POST /api/agent/chat)                │
│  3. 状态展示 (词云、OCR结果、设置面板)                         │
│  不包含: 任何业务逻辑、工具执行、RAG推理                       │
└────────────────────────┬─────────────────────────────────────┘
                         │ SSE / HTTP (localhost:8765)
┌────────────────────────┴─────────────────────────────────────┐
│  L2 核心层 — FastAPI Backend                                 │
│  ─────────────────────────────────                           │
│  职责:                                                        │
│  ├─ Obsidian Vault 直接交互 (读写笔记、操作文件)               │
│  ├─ 工具注册 & 执行 (tool_registry)                           │
│  ├─ 文件监听 & 自动索引 (file_watcher + indexer)               │
│  ├─ 自进化引擎 (evolution/)                                   │
│  └─ ★ 请求分发: 简单操作自己处理, 复杂任务 → 转发网关         │
│                                                               │
│  核心判断逻辑 (core/dispatcher.py):                            │
│    if 单步工具调用 → 直接用 tool_registry 执行                 │
│    if 需要推理/多步/搜索 → 转发 L3 Gateway                     │
│    if 纯本地操作(索引/OCR) → 调 L4a 本地设施                  │
└────────────────────────┬─────────────────────────────────────┘
                         │ Python 内部调用 (同进程)
┌────────────────────────┴─────────────────────────────────────┐
│  L3 网关层 — Gateway (OpenHarness Coordinator)                │
│  ─────────────────────────────────                           │
│  这是系统的 "大脑", 基于 OpenHarness 实现:                     │
│                                                               │
│  ┌─────────────────────────────────────┐                     │
│  │  Task Router (gateway/router.py)     │                     │
│  │  分析用户意图 → 拆解子任务 → 选择服务 │                     │
│  └─────────────────────────────────────┘                     │
│  ┌─────────────────────────────────────┐                     │
│  │  Context Assembler (gateway/context) │                     │
│  │  组装 LLM 调用所需的完整上下文        │                     │
│  └─────────────────────────────────────┘                     │
│  ┌─────────────────────────────────────┐                     │
│  │  Agent Coordinator (gateway/agents/) │ ← OpenHarness      │
│  │  Orchestrator / Searcher /          │                     │
│  │  Operator / Verifier                │                     │
│  └─────────────────────────────────────┘                     │
│  ┌─────────────────────────────────────┐                     │
│  │  Memory & Session (gateway/memory)   │ ← OpenHarness      │
│  └─────────────────────────────────────┘                     │
└──────────┬──────────────────────┬────────────────────────────┘
           │ 本地调用              │ API 调用
┌──────────┴──────────┐  ┌───────┴────────────────────────────┐
│  L4a 本地基础设施     │  │  L4b LLM 服务层                    │
│  infra/ 模块        │  │  llm/ 模块                         │
│                     │  │                                    │
│  embedding.py       │  │  client.py                         │
│  BGE-M3 (GPU, 本地) │  │  OpenAI SDK 统一接口               │
│  → 文本→1024维向量   │  │  → DeepSeek / OpenAI / Ollama     │
│                     │  │                                    │
│  vector_store.py    │  │  manager.py                        │
│  LanceDB (嵌入式)    │  │  多 Provider 管理                  │
│                     │  │                                    │
│  ocr.py             │  │  search.py (NEW)                   │
│  PaddleOCR (GPU)    │  │  → Tavily 联网搜索                 │
│                     │  │                                    │
│  wordcloud.py       │  │  prompts.py                        │
│  jieba+TF-IDF       │  │  所有系统提示词                     │
│                     │  │                                    │
│  indexer.py         │  │                                    │
│  file_watcher.py    │  │                                    │
│  tag_engine.py      │  │                                    │
│                     │  │                                    │
│  特点:               │  │  特点:                             │
│  本地GPU计算          │  │  统一 OpenAI 兼容接口              │
│  零网络依赖            │  │  Ollama 本地 LLM 也可接入         │
└─────────────────────┘  └────────────────────────────────────┘
```

---

## 二、关键设计原则

### 1. 统一服务接口

L4a 和 L4b 用同一套抽象，网关层不感知"本地还是远程"：

```python
# infra/embedding.py
class EmbeddingService:
    def encode(self, texts: list[str]) -> list[list[float]]: ...
    def encode_query(self, text: str) -> list[float]: ...
    def health(self) -> bool: ...

# llm/client.py
class LLMService:
    async def chat(self, messages, tools=None) -> AsyncIterator[Token]: ...
    async def chat_sync(self, messages) -> str: ...
    def health(self) -> bool: ...
```

### 2. 网关不碰 Obsidian

L3 网关层**绝不直接操作 vault 文件**。它只：
- 分析意图、拆解任务
- 组装上下文
- 调用 L4 服务获取能力
- 通过 L2 的 `core/tool_registry` 操作 vault

### 3. 请求流与响应流分离

```
请求流 (向下):   Plugin → L2 Core → L3 Gateway → L4 Services
响应流 (向上):   L4 Services → L3 Gateway → L2 Core SSE → Plugin
```

---

## 三、目录重组映射

| 当前路径 | 目标路径 | 变化 |
|---|---|---|
| `routes/chat.py` | `api/chat.py` | 改名 + 精简为纯 HTTP 层 |
| `routes/agent.py` | `api/agent.py` | 改名，不再自己解析 JSON plan，委托 Gateway |
| `routes/rag.py` | `api/rag.py` | 改名 |
| `routes/health.py` | `api/health.py` | 改名 |
| `routes/models.py` | `api/models.py` | 改名 |
| `routes/notes.py` | `api/notes.py` | 改名 |
| `routes/ocr.py` | `api/ocr.py` | 改名，OCR 逻辑拆到 infra/ocr.py |
| `routes/tags.py` | `api/tags.py` | 改名 |
| `routes/upload.py` | `api/upload.py` | 改名 |
| `routes/vault.py` | `api/vault.py` | 改名 |
| `routes/wordcloud.py` | `api/wordcloud.py` | 改名 |
| `routes/feedback.py` | `api/feedback.py` | 改名 |
| `services/llm_client.py` | `llm/client.py` | 移入 llm/ |
| `services/llm_manager.py` | `llm/manager.py` | 移入 llm/ |
| `services/prompts.py` | `llm/prompts.py` | 移入 llm/ |
| `services/embedding.py` | `infra/embedding.py` | 移入 infra/ |
| `services/vector_store.py` | `infra/vector_store.py` | 移入 infra/ |
| `services/indexer.py` | `infra/indexer.py` | 移入 infra/ |
| `services/file_watcher.py` | `infra/file_watcher.py` | 移入 infra/ |
| `services/wordcloud_service.py` | `infra/wordcloud.py` | 移入 infra/ |
| `services/tag_service.py` | `infra/tag_engine.py` | 移入 infra/ |
| `services/tool_registry.py` | `core/tool_registry.py` | 移入 core/ |
| — | `core/dispatcher.py` | 新：请求分发逻辑 |
| — | `core/vault_ops.py` | 新：Obsidian 文件操作封装 |
| — | `core/event_bus.py` | 新：SSE 事件统一管理 |
| — | `infra/ocr.py` | 新：OCR 逻辑从 route 拆出 |
| — | `llm/search.py` | 新：Tavily 联网搜索 |
| — | `gateway/router.py` | 新：任务分类与路由 |
| — | `gateway/context.py` | 新：上下文组装 |
| — | `gateway/coordinator.py` | 新：OpenHarness 协调器包装 |
| — | `gateway/tools_adapter.py` | 新：14 工具 → OpenHarness BaseTool |
| — | `gateway/memory.py` | 新：Memory 管理 |
| — | `gateway/session.py` | 新：会话持久化 |
| — | `gateway/agents/orchestrator.py` | 新：编排者 Agent |
| — | `gateway/agents/searcher.py` | 新：搜索者 Agent |
| — | `gateway/agents/operator.py` | 新：操作者 Agent |
| — | `gateway/agents/verifier.py` | 新：验证者 Agent |

---

## 四、目标目录结构

```
python/backend/src/app/
│
├── main.py                    # FastAPI 入口 (轻改)
├── config.py                  # 统一配置 (扩展)
├── constants.py               # 常量 (扩展)
│
├── api/                       # L2: HTTP 路由层
│   ├── __init__.py
│   ├── health.py
│   ├── chat.py
│   ├── agent.py               # ★ 核心改动
│   ├── models.py
│   ├── notes.py
│   ├── ocr.py
│   ├── rag.py
│   ├── tags.py
│   ├── upload.py
│   ├── vault.py
│   ├── wordcloud.py
│   └── feedback.py
│
├── core/                      # L2: 核心枢纽
│   ├── __init__.py
│   ├── dispatcher.py          # 请求分类：简单/复杂 → 直行/转网关
│   ├── tool_registry.py       # 14 工具定义+执行
│   ├── vault_ops.py           # Obsidian 文件操作封装
│   └── event_bus.py           # SSE 事件统一发射
│
├── infra/                     # L4a: 本地 GPU 基础设施
│   ├── __init__.py
│   ├── embedding.py           # BGE-M3 (GPU)
│   ├── vector_store.py        # LanceDB
│   ├── indexer.py             # 文本分块+索引
│   ├── ocr.py                 # PaddleOCR (GPU)
│   ├── wordcloud.py           # jieba+TF-IDF
│   ├── tag_engine.py          # 标签+双链推荐
│   └── file_watcher.py        # Watchdog
│
├── llm/                       # L4b: LLM 服务层
│   ├── __init__.py
│   ├── client.py              # OpenAI SDK 封装
│   ├── manager.py             # 多 Provider 管理
│   ├── prompts.py             # 系统提示词
│   └── search.py              # Tavily 联网搜索 ★新
│
├── gateway/                   # L3: 网关层 (OpenHarness)
│   ├── __init__.py
│   ├── router.py              # 任务分类 → 选择Agent/直行
│   ├── context.py             # 上下文组装
│   ├── coordinator.py         # OpenHarness Coordinator 包装器
│   ├── tools_adapter.py       # 14工具 → OpenHarness BaseTool
│   ├── memory.py              # 跨会话记忆
│   ├── session.py             # 会话管理
│   └── agents/
│       ├── __init__.py
│       ├── orchestrator.py    # 任务拆解
│       ├── searcher.py        # 本地RAG + 联网搜索
│       ├── operator.py        # 笔记操作
│       └── verifier.py        # 结果验证
│
├── models/                    # Pydantic 数据模型 (不动)
├── evolution/                 # 自进化引擎 (不动)
└── tests/
    ├── test_health.py
    ├── test_chat.py
    ├── test_notes.py
    ├── test_ocr.py
    ├── test_rag.py
    ├── test_tags.py
    ├── test_tools.py
    ├── test_vault.py
    ├── test_wordcloud.py
    ├── test_gateway.py        # ★新
    ├── test_coordinator.py    # ★新
    └── test_search.py         # ★新
```

---

## 五、Agent 角色定义

| Agent | 触发条件 | 工具集 | 职责 |
|---|---|---|---|
| **Orchestrator** | 用户意图涉及 ≥2 个步骤 | 全部只读 | 拆解复杂任务为子任务列表 |
| **Searcher** | Orchestrator/用户要求搜索 | search_notes, read_note, web_search (新) | 同时搜本地RAG + Tavily, 合并去重排序 |
| **Operator** | Orchestrator 产生写操作子任务 | 全部写工具 (CRUD/OCR/Move) | 执行实际的笔记操作 |
| **Verifier** | 所有操作完成后 | 全部只读 | 检查结果完整性 + 建议 |

### 工作流示例

```
用户: "帮我整理 Rust 笔记, 顺便查查最近有什么新框架"

Orchestrator:
  → [子任务1: Searcher 搜索 #rust 标签笔记]
  → [子任务2: Searcher 联网查最新 Rust 框架]
  → [子任务3: Operator 创建 "Rust/框架/" 目录]
  → [子任务4: Operator 将相关笔记移入 + 打标签 + 写总结]
  → [子任务5: Verifier 检查完整性]

Searcher(本地): search_notes("rust") → 找到 12 篇笔记
Searcher(联网): web_search("Rust 2026 new frameworks") → 3 个新框架
Operator: 创建 3 篇新笔记(框架介绍) + 移动/归类12篇旧笔记
Verifier: 15篇笔记全部到位, 标签正确, 无遗漏
→ 最终输出: 总结报告
```

---

## 六、分阶段实施

### Stage 1: 代码统一重构 (3天)

纯搬家，不改业务逻辑。

| 任务 | 详情 |
|---|---|
| 1.1 目录搬家 | `routes/*` → `api/*`；`services/llm_*` → `llm/*`；`services/embedding|vector|indexer|ocr|wordcloud|tag|watcher` → `infra/*`；`services/tool_registry` → `core/tool_registry` |
| 1.2 新建空壳 | `core/dispatcher.py`, `core/vault_ops.py`, `core/event_bus.py`, `llm/search.py`（空）, `gateway/` 全目录（空壳） |
| 1.3 全量 import 更新 | 所有 `from ..routes` → `from ..api`，所有 `from ..services` → `from ..infra|llm|core` |
| 1.4 验证 | `uv run pytest -v` 24 tests pass; `uv run ruff check` pass; `uv run mypy` pass |
| 1.5 OCR 逻辑拆出 | `api/ocr.py` 中的 PaddleOCR 调用逻辑抽到 `infra/ocr.py`，route 只留 HTTP 参数校验 |

### Stage 2: 网关骨架 + 联网搜索 (4天)

| 任务 | 详情 |
|---|---|
| 2.1 新增依赖 | `pyproject.toml` 加 `openharness-ai>=0.1.9`, `tavily-python` |
| 2.2 Tavily 搜索 | `llm/search.py`：`TavilyClient.search(query, max_results)` → 结构化结果 |
| 2.3 请求分发器 | `core/dispatcher.py`：关键词+复杂度分析 → `simple|search|complex` |
| 2.4 事件总线 | `core/event_bus.py`：统一 SSE 事件发射 |
| 2.5 Gateway 路由 | `gateway/router.py`：简单任务直调 tool_registry，复杂任务 → Agent 协调 |
| 2.6 上下文组装 | `gateway/context.py`：拼装 system_prompt + user_profile + rag_context + history |
| 2.7 改造 agent.py | 不再自己解析 JSON plan，改为委托 Gateway |
| 2.8 联网搜索端点 | 可选：`POST /api/search` 直接暴露给前端 |

### Stage 3: OpenHarness 嵌入 + 多 Agent (7天)

| 任务 | 详情 |
|---|---|
| 3.1 工具适配 | `gateway/tools_adapter.py`：14 个工具 → OpenHarness BaseTool 子类，`execute()` delegate 到 `core/tool_registry.execute_tool()` |
| 3.2 新增工具 | `web_search` 工具（调 `llm/search.py`）注册为 OpenHarness 工具 |
| 3.3 Agent 定义 | 4 个 Agent：角色 prompt + 工具集 + 触发条件 |
| 3.4 Coordinator 包装 | `gateway/coordinator.py`：初始化 OpenHarness Coordinator，配置 provider（复用 llm/manager），注册工具，设置权限 |
| 3.5 Agent Loop 集成 | OpenHarness tool-call 循环接管 `api/agent.py` |
| 3.6 SSE 桥接 | OH 输出事件 → core/event_bus → SSE 流 |
| 3.7 Memory 落地 | `.ai-tutor/memory/`：跨会话记忆 |
| 3.8 会话持久化 | OpenHarness JSONL session 替换 Markdown session |
| 3.9 插件端适配 | 新增 `agent_start`/`agent_end`/`agent_handoff` SSE 事件渲染 |
| 3.10 集成测试 | E2E 测试全流程 |

### Stage 4: 可视化 + 工程质量 (4天)

| 任务 | 详情 |
|---|---|
| 4.1 知识图谱 | `infra/graph.py`：双链+层级关系 → D3-force JSON。新增 GraphView |
| 4.2 结构化日志 | `core/logging.py`：structlog, JSON 格式, trace_id |
| 4.3 E2E 测试 | Mock LLM，验证 Orchestrator→Searcher→Operator→Verifier 全链路 |
| 4.4 进化联动 | Gateway agent prompt 纳入 evolution engine 变异范围 |
| 4.5 文档导出 | PRD F3：`infra/exporter.py` VitePress 导出（低优先级） |

---

## 七、改动量汇总

| | Stage 1 | Stage 2 | Stage 3 | Stage 4 | 合计 |
|---|---|---|---|---|---|
| **新增文件** | 3 | 6 | 12 | 3 | 24 |
| **修改文件** | ~30 (import) | 3 | 2 (插件端) | 2 | ~37 |
| **新增代码** | ~100行 | ~600行 | ~1500行 | ~500行 | ~2700行 |
| **新增测试** | 0 | 2 | 2 | 2 | 6 test files |
| **工期** | 3天 | 4天 | 7天 | 4天 | **18天** |

---

## 八、核心决策记录

| 决策 | 选择 | 原因 |
|---|---|---|
| **整合方式** | 路径 B：网关层嵌入 | 保留所有现有功能，OpenHarness 只做多Agent协调 |
| **代码重组** | 统一重构 | 一次干净，后续架构清晰 |
| **Gateway 实现** | 完整 Agent Loop | OpenHarness 接管 LLM 交互全流程 |
| **联网搜索** | Python 直连 Tavily | 不走 MCP，更简单直接 |
| **BGE-M3** | GPU 优先 | 本地 GPU 基础设施，不降级 CPU |
| **PaddleOCR** | GPU 优先 | 本地 GPU 基础设施 |
| **Memory 作用域** | Project-scoped (.ai-tutor/) | 每个 Vault 独立记忆 |

---

## 九、新增依赖

```toml
# pyproject.toml (新增)
dependencies = [
    # ... existing ...
    "openharness-ai>=0.1.9",   # Agent harness framework
    "tavily-python",             # Web search
]
```

---

## 十、关键变化：api/agent.py 的演变

### 当前 (JSON 解析模式):
```
用户消息 → 拼 system_prompt → LLM → 正则找 ```json →
解析 actions[][] → for 循环 execute_tool → SSE 返回
```

### Stage 3 后 (OpenHarness Agent Loop):
```
用户消息 → dispatcher.classify() →
├─ simple → 直接用 tool_registry（不变）
└─ complex → gateway/router.handle() →
             OpenHarness session →
             LLM tool_use → 工具执行 → LLM 继续 →
             ...(循环直到任务完成) → SSE 流
```
