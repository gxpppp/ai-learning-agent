# Phase 2：知识引擎 —— 完整设计方案

| 文档版本 | 1.0 |
| 发布日期 | 2026-07-08 |
| 状态 | 执行中 |

---

## 1. 目标

让 AI 读懂你的全部笔记和 OCR 扫描文档，实现：
- **RAG 全时问答**：每条消息自动检索知识库，带来源引用回答
- **智能标签**：AI 自动为笔记写入 frontmatter 标签
- **双链推荐**：AI 建议笔记之间的 `[[内部链接]]`
- **词云可视化**：d3-cloud SVG 渲染，点击词跳转笔记，增量更新
- **文件监听**：笔记变更自动同步向量索引

## 2. 技术选型

| 组件 | 选择 | 资源 | 理由 |
|---|---|---|---|
| Embedding | BGE-M3 (568M) | ~2GB VRAM | dense+sparse 双向量，100+ 语言，MIT 许可 |
| Vector DB | LanceDB | 嵌入式，零服务 | Apache 2.0，与 FastAPI 同进程，列式存储 |
| 文本分块 | RecursiveCharacterTextSplitter | chunk=512, overlap=64 | 适合 Markdown 笔记粒度 |
| 中文分词 | jieba | CPU | TF-IDF + 词云 |
| 英文分词 | nltk | CPU | 停用词过滤 |
| 词云布局 | d3-cloud (npm) | 浏览器 SVG | MIT，轻量，点击交互 |
| 文件监听 | watchdog (Python) + Obsidian vault events | — | 双重同步机制 |

## 3. 架构

```
Obsidian Vault (.md)
    │
    ├── 文件监听器 (watchdog) ──┐
    │                          ▼
    │                   文本分块器 (512/64)
    │                          │
    │            ┌─────────────┼─────────────┐
    │            ▼             ▼             ▼
    │        BGE-M3          jieba         TF-IDF
    │     (dense+sparse)    (分词)        (加权)
    │            │             │             │
    │            ▼             ▼             ▼
    │       LanceDB        TF-IDF词表    标签/链接
    │       (向量检索)     (增量持久)    (LLM推荐)
    │            │             │             │
    │            ▼             ▼             ▼
    │      /api/rag       /api/wordcloud  /api/tags
    │       /query          /generate      /suggest
    │            │             │             │
    │            └─────────────┼─────────────┘
    │                          │
    │                          ▼
    │                  Obsidian Plugin
    └──── Obsidian vault events ──► 自动索引同步
```

## 4. 数据统一在 Vault 下

```
MyVault/
├── .obsidian/                    Obsidian 自带
├── .ai-tutor/                    本项目全部数据
│   ├── lancedb/                  向量库文件
│   ├── tfidf.db                 TF-IDF 持久词表 (增量)
│   ├── index_state.json         索引状态
│   └── config.json              项目配置
├── AI Chat Logs/                 聊天记录
├── OCR/                         OCR 结果
└── notes/                       你的笔记
```

## 5. RAG 全时自动

```
用户消息 → BGE-M3 生成查询向量
         → LanceDB 混合检索 (vector + full-text)
         → top-5 相似块拼入 system prompt
         → LLM 流式回答 (SSE, 带引用脚注)
         → ChatView 渲染引用块
```

## 6. 分块策略

```
一篇 3000 字笔记:
├─ Chunk1 [~400字]  ─┐
├─ Chunk2 [~400字]  ─┤ overlap ~50字 (防止关键概念被切断)
├─ Chunk3 [~400字]  ─┘
└─ Chunk4 [~400字] ...
```

| 参数 | 值 |
|---|---|
| chunk_size | 512 tokens (~400 汉字) |
| chunk_overlap | 64 tokens (~50 汉字) |
| top_k (检索) | 5 |

## 7. 词云增量更新

| 事件 | 操作 |
|---|---|
| 新笔记 | 分词 → 写入 tfidf.db → 新词入词云 |
| 修改笔记 | 重分旧词 → 更新权重 → 词云微调 |
| 删除笔记 | 移除该笔记词 → 权重衰减 |
| 首次创建 | 全量扫描 → 生成完整词云 |

## 8. 文件变更清单 (27+ files)

### Python 后端

| 路径 | 说明 |
|---|---|
| `services/vector_store.py` | LanceDB 封装 |
| `services/embedding.py` | BGE-M3 客户端 |
| `services/indexer.py` | Vault 扫描 + 分块 + 写库 |
| `services/tag_service.py` | 自动标签 + 双链推荐 |
| `services/wordcloud_service.py` | jieba + TF-IDF 词云管道 |
| `services/file_watcher.py` | watchdog 文件监听 |
| `routes/rag.py` | RAG 检索 + 回答 |
| `routes/tags.py` | 标签/链接 API |
| `routes/wordcloud.py` | 词云 API |
| `routes/vault.py` | 索引触发 + 状态 |
| `models/rag.py, tag.py, wordcloud.py, vault.py` | Pydantic 模型 |
| `main.py` (改) | lifespan 初始化 |
| `config.py` (改) | 新增配置项 |

### 共享类型

| 路径 | 说明 |
|---|---|
| `shared-types/src/rag.ts` | IRagQuery, IRagChunk, etc. |
| `shared-types/src/knowledge.ts` | ITagSuggestion, IWordCloud*, etc. |

### Obsidian 插件

| 路径 | 说明 |
|---|---|
| `rag/RagService.ts` | RAG API 客户端 |
| `knowledge/WordCloudView.ts` | d3-cloud SVG 词云 |
| `knowledge/WordCloudService.ts` | 词云 API 客户端 |
| `knowledge/TagSuggest.ts` | 标签/链接推荐 UI |
| `chat/ChatView.ts` (改) | RAG 引用渲染 |
| `chat/MessageRenderer.ts` (改) | 引用脚注样式 |
| `main.ts` (改) | 注册新视图 + 命令 |

## 9. API 规格

### RAG

```
POST /api/rag/query (SSE 流式)
→ {"query": "...", "top_k": 5}
← event:token {"content":"..."}
← event:source {"path":"...", "score":0.92, "excerpt":"..."}
← data:[DONE]
```

### 标签/链接

```
POST /api/tags/suggest
→ {"note_path":"..."} ← {"tags":["..."]}

POST /api/links/recommend
→ {"note_path":"..."} ← {"links":[{"target":"...","score":0.9}]}
```

### 词云

```
POST /api/wordcloud/generate
→ {"folder": "Rust/", "top_n": 50}
← {"words":[{"word":"所有权","weight":0.98,...}], "total_notes":45}
```

### 索引

```
POST /api/vault/index → {"vault_path":"..."} ← status
GET  /api/vault/status → index progress
```

## 10. 执行计划 (6 周)

| 周 | 内容 |
|---|---|
| W1-2 | RAG 核心: LanceDB + BGE-M3 + indexer + rag 路由 |
| W3 | 智能标签: tag_service + 双链推荐 |
| W4-5 | 词云: wordcloud_service + d3-cloud SVG 面板 |
| W6 | 文件监听: watchdog + vault events + 收尾测试 |
