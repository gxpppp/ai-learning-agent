# PaddleOCR-VL 集成方案

| 文档版本 | 1.0 |
| :--- | :--- |
| 发布日期 | 2026-07-08 |
| 作者 | gxpppp |
| 状态 | 执行中 (Phase 1.5) |

---

## 1. 背景

Phase 1 MVP（聊天 + SSE 流式）已完成。用户需要文档扫描能力，用于从 PDF、图片中提取文本，作为后续 RAG 知识库（Phase 2）的输入管道。

### 技术选型

| 方案 | 精度 | 大小 | Windows | 结论 |
|---|---|---|---|---|
| PaddleOCR-VL 1.6 | OmniDocBench 96.33 (#1) | 0.9B | Docker/WSL | **选中** |
| MiniCPM-V 4.6 | OCRBench 831 | 1.3B | 原生 Ollama | 备选 |
| Tesseract/PaddleOCR | 传统 OCR | 轻量 | 原生 | 不适合 |

**选 PaddleOCR-VL 的理由**：

- 文档解析全球第一（OmniDocBench v1.6 96.33）
- RTX 3060 6GB 显存绰绰有余（~3.3GB VRAM）
- Docker 一键部署，用户已有 Docker + WSL
- vLLM 服务暴露 OpenAI 兼容 API → **现有 LLMClient 零修改复用**

---

## 2. 架构设计

```
                         ┌──────────────────────────────────────┐
                         │     Docker Container (持久运行)        │
                         │     PaddleOCR-VL vLLM Server          │
                         │     port 8080                         │
                         │     model: PaddleOCR-VL-0.9B          │
                         │     backend: vllm                     │
                         └──────────────┬───────────────────────┘
                                        │ OpenAI兼容 API
                                        │ POST /v1/chat/completions
                                        │
┌──────────────────┐    SSE stream    ┌──────────────────────────┐
│ Obsidian Plugin  │◄────────────────►│   Python FastAPI Backend  │
│                  │   HTTP POST     │   port 8765               │
│  ChatView.ts     │── /api/chat  ──►│   routes/chat.py          │
│  OcrService.ts   │── /api/ocr   ──►│   routes/ocr.py           │
│  main.ts         │                 │                           │
└──────────────────┘                 │   services/llm_client.py  │
                                     │   (聊天和OCR共用)          │
                                     │   base_url 不同：          │
                                     │   聊天 → DeepSeek/OpenAI   │
                                     │   OCR  → Docker vLLM      │
                                     └──────────────────────────┘
```

### 关键设计决策

**决策 1：复用 LLMClient，不引入新 Python 依赖**

PaddleOCR-VL vLLM 服务通过 `/v1/chat/completions` 暴露 vision chat API，使用标准 OpenAI 多模态消息格式：

```python
messages = [{
    "role": "user",
    "content": [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,{b64}"}},
        {"type": "text", "text": "OCR:"}
    ]
}]
```

现有 `LLMClient`（`services/llm_client.py`）无需任何修改，只需在路由层创建第二个实例指向 Docker 服务。

**决策 2：Docker 容器持久运行，不在 sidecar 生命周期内**

- OCR 模型加载耗时较长（首次 ~30s），不应频繁启停
- 容器通过 `docker compose up -d` 手动启动一次，`restart: unless-stopped`
- 后端通过 `/api/ocr/health` 检查 OCR 服务可用性
- 如果 OCR 不可用，API 返回 503 并提示启动 Docker

**决策 3：OCR 结果直接写入 Obsidian Vault**

- `/api/ocr/parse` 接收文件路径，返回 Markdown
- 前端 `OcrService` 调用后，可选调用 `/api/notes/create` 写入 vault
- 或者后端 `/api/ocr/parse-and-save` 一键完成 OCR→写入

**决策 4：初期使用命令触发，后续可加面板**

- 命令：`AI Tutor: OCR current file` — 对当前文件浏览器选中的文件
- 命令：`AI Tutor: OCR and save to vault` — OCR 后自动保存为笔记
- OcrView.ts 预留面板占位，UI 稍后完善

---

## 3. 任务识别（适用于 PaddleOCR-VL）

vLLM 文档显示 PaddleOCR-VL 支持四种任务类型：

| 任务 | Prompt |
|---|---|
| OCR（文字提取） | `"OCR:"` |
| 表格识别 | `"Table Recognition:"` |
| 公式识别 | `"Formula Recognition:"` |
| 图表识别 | `"Chart Recognition:"` |

默认使用 `"OCR:"` 做全文提取。未来可按需选择。

---

## 4. 文件变更清单

### 新增文件 (8)

| # | 路径 | 说明 |
|---|---|---|
| 1 | `docker-compose.yml` | PaddleOCR-VL Docker 服务定义 |
| 2 | `docs/ocr-integration-plan.md` | 本文档 |
| 3 | `python/backend/src/app/models/ocr.py` | Pydantic 请求/响应模型 |
| 4 | `python/backend/src/app/routes/ocr.py` | `/api/ocr/parse`, `/api/ocr/health` |
| 5 | `packages/shared-types/src/ocr.ts` | TypeScript 类型定义 |
| 6 | `apps/obsidian-plugin/src/ocr/OcrService.ts` | 前端 OCR API 客户端 |
| 7 | `apps/obsidian-plugin/src/ocr/OcrView.ts` | OCR 面板骨架 |
| 8 | `python/backend/tests/test_ocr.py` | OCR 端点测试 |

### 修改文件 (6)

| # | 路径 | 变更内容 |
|---|---|---|
| 9 | `python/backend/src/app/config.py` | +OCR_SERVER_URL, OCR_MODEL, OCR_ENABLED |
| 10 | `python/backend/src/app/main.py` | +include_router(ocr_router) |
| 11 | `.env.example` | +OCR_* 环境变量 |
| 12 | `packages/shared-types/src/index.ts` | +export * from "./ocr" |
| 13 | `apps/obsidian-plugin/src/main.ts` | +注册 OCR 命令 |
| 14 | `apps/obsidian-plugin/styles.css` | +OCR 面板样式 |

---

## 5. API 规格

### POST /api/ocr/parse

```json
// Request
{
    "file_path": "/path/to/document.pdf",
    "task": "ocr"
}

// Response
{
    "success": true,
    "markdown": "# 提取的文本内容\n\n...",
    "error": null
}
```

### GET /api/ocr/health

```json
// Response
{
    "status": "ok",
    "model": "PaddleOCR-VL-0.9B",
    "server": "http://127.0.0.1:8080/v1"
}
```

### POST /api/ocr/parse-and-save

```json
// Request
{
    "file_path": "/path/to/document.pdf",
    "vault_path": "/path/to/vault",
    "target_folder": "OCR",
    "filename": "document.md",
    "task": "ocr"
}

// Response
{
    "success": true,
    "markdown": "...",
    "saved_path": "OCR/document.md"
}
```

---

## 6. 环境变量

```bash
# OCR Service (PaddleOCR-VL via Docker)
OCR_SERVER_URL=http://127.0.0.1:8080/v1
OCR_MODEL=PaddleOCR-VL-0.9B
OCR_ENABLED=true
```

---

## 7. Docker 启动命令

```bash
# 首次启动（拉镜像+启动，可能需要几分钟下载镜像）
docker compose up -d

# 查看日志
docker compose logs -f

# 停止
docker compose down
```

---

## 8. 测试策略

| 测试 | 说明 |
|---|---|
| `test_ocr_health_available` | 健康检查返回 200 |
| `test_ocr_health_unavailable` | OCR 禁用时返回 503 |
| `test_ocr_parse_file_not_found` | 文件不存在返回 404 |
| `test_ocr_parse_invalid_task` | 无效 task 返回 422 |
| `test_ocr_parse_and_save` | 端到端：OCR → 写入 vault |
| `test_ocr_disabled` | OCR_ENABLED=false 时返回 503 |
