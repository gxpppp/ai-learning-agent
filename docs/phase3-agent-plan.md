# Phase 3：Agent 型学习助手 —— 完整设计方案

| 文档版本 | 1.0 |
| 发布日期 | 2026-07-08 |
| 状态 | 设计中 |

---

## 1. 目标

将当前的聊天式助手升级为**自主 Agent**：

- 用户一句话 → Agent 自主决策 → 选择工具 → 操作 Obsidian → 汇报结果
- 像真人使用 Obsidian 一样：创建文件夹、整理笔记、扫描文档、打标签、写总结
- 支持多 LLM Provider 切换，聊天的模型和 Agent 工具调用的模型可以不同
- 内置自进化引擎，借鉴 OpenHarness 思路持续自我优化

## 2. 多模型支持

### 2.1 数据模型变更

```typescript
// packages/shared-types/src/config.ts

interface ILLMProvider {
  id: string;                    // "deepseek" | "ollama" | "openai"
  name: string;                  // 显示名
  baseUrl: string;               // OpenAI-compatible 端点
  apiKey: string;
  models: string[];              // 从 /v1/models 拉取的模型列表
  isActive: boolean;
}

interface IAppConfig {
  vaultPath: string;
  providers: ILLMProvider[];     // 取代单 llm: ILLMConfig
  activeProviderId: string;
  activeChatModel: string;       // 聊天用的模型
  activeAgentModel: string;      // Agent 工具调用用的模型（需支持 function calling）
  server: IServerConfig;
  toolPermissions: "readonly" | "full";
}
```

### 2.2 设置面板设计

```
┌────────────────────────────────────────────────┐
│  AI Learning Agent Settings                    │
│                                                │
│  ┌─ Providers ─────────────────────────────────┐
│  │  [+ Add Provider]                           │
│  │                                             │
│  │  ┌ [DeepSeek] ────────────────────────┐     │
│  │  │  Name: DeepSeek                     │     │
│  │  │  URL:  https://api.deepseek.com/v1  │     │
│  │  │  Key:  sk-•••••••••                 │     │
│  │  │  Models: [Fetch from API]            │     │
│  │  │    ☑ deepseek-v4-flash             │     │
│  │  │    ☐ deepseek-chat                 │     │
│  │  │  [Test Connection] [× Remove]       │     │
│  │  └──────────────────────────────────────┘    │
│  └──────────────────────────────────────────────┘
│                                                │
│  ┌─ Model Assignment ──────────────────────────┐
│  │  Chat model:  [deepseek-v4-flash ▼]         │
│  │  Agent model: [deepseek-v4-flash ▼]         │
│  └──────────────────────────────────────────────┘
│                                                │
│  ┌─ Tool Permissions ──────────────────────────┐
│  │  ○ Read-only  (search, read, list, tags)   │
│  │  ● Full access (create, delete, move, OCR) │
│  └──────────────────────────────────────────────┘
└────────────────────────────────────────────────┘
```

### 2.3 后端 LLM 管理

```python
# python/backend/src/app/services/llm_manager.py

class LLMManager:
    """Manages multiple OpenAI-compatible providers."""
    
    def __init__(self, providers: list[dict]):
        self.providers = providers
        self.clients = {
            p["id"]: LLMClient(p["baseUrl"], p["apiKey"])
            for p in providers
        }
    
    async def fetch_models(self, provider_id: str) -> list[str]:
        """Call /v1/models endpoint."""
    
    def get_client(self, provider_id: str) -> LLMClient:
        """Get LLMClient for a specific provider."""
```

### 2.4 聊天面板模型切换

聊天面板顶部显示当前模型名，点击可下拉切换：

```
┌─ AI Tutor ────── [deepseek-v4-flash ▼] ───┐
│                                              │
│  [消息内容...]                                │
└──────────────────────────────────────────────┘
```

---

## 3. Agent Tool System

### 3.1 工具分级

#### 只读工具（readonly 模式始终可用）

| 工具 | 功能 | 参数 |
|---|---|---|
| `search_notes` | 语义+关键词搜索笔记 | `query`, `top_k` |
| `read_note` | 读取笔记完整内容 | `note_path` |
| `list_folder` | 列出目录内容 | `path` |
| `suggest_tags` | 推荐 frontmatter 标签 | `note_path`, `max_tags` |
| `recommend_links` | 推荐双向链接 `[[]]` | `note_path` |

#### 完整工具（full 模式下额外可用）

| 工具 | 功能 | 参数 |
|---|---|---|
| `create_note` | 创建/覆盖 Markdown 笔记 | `folder`, `filename`, `content`, `tags` |
| `update_note` | 修改已有笔记内容 | `note_path`, `content` |
| `delete_note` | 删除笔记（移到 .trash） | `note_path` |
| `create_folder` | 创建任意目录 | `path` |
| `move_note` | 移动/重命名笔记 | `source`, `destination` |
| `ocr_document` | PDF/图片文字提取 | `file_path`, `output_folder` |
| `classify_note` | 按内容类型自动归类 | `note_path` |
| `generate_summary` | 生成 TL;DR 摘要 | `note_path` |
| `get_vault_status` | 查看索引/词云状态 | 无 |

### 3.2 Agent Loop（SSE 流式）

```
POST /api/agent/chat

LLM 生成回复:
  ├── 纯文本        → event: token        → 前端正常渲染
  ├── 工具调用       → event: tool_call     → 前端显示 ToolCall 小卡片
  ├── 工具执行结果    → event: tool_result   → 卡片更新为完成+耗时
  └── LLM 继续思考   → (循环直到无 tool_call)

协议:
  event: token        → {"content": "让我先看看..."}
  event: tool_call    → {"name":"list_folder","args":{...},"id":"call_1"}
  event: tool_result  → {"id":"call_1","content":"3 files found","elapsed_ms":234}
  data: [DONE]
```

### 3.3 Tool Call 前端渲染

工具调用在聊天中以 **更小字体（0.75em）** 的灰色卡片展示：

```
┌─ AI Tutor ──────────────────────────────────────┐
│                                                  │
│  让我先看看你的教材文件夹...                       │  ← 正常 14px
│                                                  │
│  ┌ 🔧 list_folder ──── 234ms ──────────────────┐ │  ← 11px, 灰底
│  │ 📁 教材/  →  高数.pdf, 线代.pdf, 概率论.pdf  │ │
│  └────────────────────────────────────────────────┘ │
│                                                  │
│  ┌ 🔧 ocr_document ──── 4.7s ──────────────────┐ │  ← 11px, 灰底
│  │ 📄 教材/高数.pdf  →  已提取 8,560 字          │ │
│  │ 已存入 Math/高数.md                           │ │
│  └────────────────────────────────────────────────┘ │
│                                                  │
│  已帮你把三本教材扫描完成。                        │  ← 正常 14px
│                                                  │
└──────────────────────────────────────────────────┘
```

### 3.4 权限模式

| 模式 | 可用工具 | 使用场景 |
|---|---|---|
| **readonly** | search_notes, read_note, list_folder, suggest_tags, recommend_links | 浏览和学习 |
| **full** | 全部 14 个工具 | 整理、创作、批量操作 |

在设置面板中一键切换。Agent 根据当前权限动态注册可用工具。

---

## 4. 自进化引擎（OpenHarness 思路）

### 4.1 借鉴 OpenHarness 设计

从用户本地 `.ohmo/` 部署提取的精华：

| OpenHarness 模式 | 在自进化引擎中的应用 |
|---|---|
| **Layered prompts** (soul/identity/user) | CONSTITUTION（不可变） + IDENTITY（可变） + RUBRIC（评分标准） |
| **Soul gatekeeping** | "改变 CONSTITUTION 必须告知用户" |
| **Filesystem as state** | 所有变体、评分、历史存为 Markdown/JSON 文件 |
| **Memory as directed files** | 每次进化迭代写入独立的 memory 文件 |
| **Bootstrap self-destruct** | 一次性的变异任务完成后自动删除 |

### 4.2 文件结构

```
.ai-tutor/evolution/
├── CONSTITUTION.md          ← 不可变核心（"Soul"）
├── IDENTITY.md              ← 可变的引擎身份
├── RUBRIC.md                ← 定量评分标准
├── VARIANTS/                ← Prompt 变体
│   ├── v001.md
│   └── v002.md
├── EVALS/                   ← 评估运行结果
│   └── 2026-07-08_run01.json
├── MUTATIONS/               ← 变异提案+日志
│   └── 2026-07-08_mutation.jsonl
├── HISTORY.md               ← 谱系日志
├── feedback.jsonl           ← 用户 👍/👎
└── sessions/                ← 会话日志
```

### 4.3 CONSTITUTION.md

```markdown
# Evolution Engine Constitution

## Identity
You are the self-evolution engine.
Your job: improve system prompts that govern the Tutor Agent.

## Core Truths
1. Score honestly. High scores must be earned.
2. Small surgical edits > big rewrites.
3. Every mutation must be logged with rationale.
4. A failed experiment is progress if documented.

## Boundaries
- Never change CONSTITUTION without user approval
- Never deploy a variant with lower eval score
- Always log: timestamp, variant ID, score delta, rationale
```

### 4.4 RUBRIC.md — 评分标准

| 维度 | 权重 | 标准 |
|---|---|---|
| Accuracy | 40% | 答案是否准确？有无幻觉？ |
| Conciseness | 20% | 简洁度：无废话 |
| Helpfulness | 20% | 是否采取了行动（工具调用）？ |
| Tone | 10% | 温和高效，不机械 |
| Tool Choice | 10% | 工具选择和顺序是否正确？ |

评分方式：
- **LLM-as-judge**：用 GPT/DeepSeek 按维度打分
- **用户反馈**：👍/👎 可覆盖 LLM 评委的分数

### 4.5 变异算子

| 算子 | 操作 | 灵感来源 |
|---|---|---|
| **shorten** | 删减冗余，保留核心 | SOUL 的简洁原则 |
| **negative-space** | "你应该 X" → "你不应该做非 X" | SOUL 的边界定义 |
| **add-example** | 插入 1-shot 示例 | - |
| **reorder** | 调换指令顺序 | 注意力窗口优化 |
| **parameterize** | 模糊 → 参数化 | user.md 结构化模板 |

### 4.6 变异循环

```
1. Load VARIANTS/v_active.md (当前最优)
2. 施加 2-3 个变异算子 → 生成 5 个变体
3. Eval Harness 对各变体跑 10 个 QA 对
4. 按 RUBRIC.md 评分
5. 最佳变体 > current × 1.05 → deploy 为新的 active
6. 记录日志: MUTATIONS/ + HISTORY.md
7. 若全部更差 → 记录失败实验，保留当前
8. 每周报告: "本周测试 5 变体，最佳提升 +3.2%"
```

### 4.7 聊天面板反馈 UI

```
┌──────────────────────────────────────────────┐
│ AI Tutor                                     │
│                                              │
│  已帮你整理完成。                             │
│                                              │
│  [👍 有帮助]  [👎 不够好]                     │
└──────────────────────────────────────────────┘
```

点击 👎 → 问卷：*"哪里不对？[ ] 不准确 [ ] 工具选错 [ ] 太啰嗦 [ ] 其他"*

---

## 5. 文件变更清单

| 层 | 文件 | 说明 |
|---|---|---|
| **Config** | `packages/shared-types/src/config.ts` | ILLMProvider + toolPermissions |
| **后端** | `python/backend/src/app/services/llm_manager.py` | 多 provider 管理 |
| **后端** | `python/backend/src/app/routes/agent.py` | Agent Loop + 工具执行 |
| **后端** | `python/backend/src/app/routes/models.py` | `/api/models/fetch` |
| **后端** | `python/backend/src/evolution/constitution.md` | 自进化宪法 |
| **后端** | `python/backend/src/evolution/rubric.md` | 评分标准 |
| **后端** | `python/backend/src/evolution/mutator.py` | 变异引擎 |
| **后端** | `python/backend/src/evolution/evaluator.py` | 评分执行器 |
| **前端** | `apps/obsidian-plugin/src/settings.ts` | 多 provider 设置面板 |
| **前端** | `apps/obsidian-plugin/src/chat/ToolCallRenderer.ts` | 工具调用小卡片 |
| **前端** | `apps/obsidian-plugin/src/chat/FeedbackBar.ts` | 👍/👎 反馈条 |
| **前端** | `apps/obsidian-plugin/src/chat/ChatView.ts` | Agent SSE 消费 + 模型切换 |

---

## 6. 执行计划

| 阶段 | 内容 | 工期 |
|---|---|---|
| **3.1** 模型切换 | config → LLMManager → 设置面板 → 聊天面板下拉 | 2 天 |
| **3.2** Agent Core | 工具注册 → Agent Loop → ToolCallRenderer | 3 天 |
| **3.3** 权限控制 | toolPermissions → 动态工具注册 | 1 天 |
| **3.4** 反馈系统 | 👍/👎 → feedback.jsonl → 问卷 | 1 天 |
| **3.5** 自进化 | CONSTITUTION + RUBRIC → Eval Harness → 变异引擎 | 3 天 |

**共约 2 周**。
