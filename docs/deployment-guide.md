# 部署指南

## 环境要求

| 组件 | 最低版本 | 说明 |
|---|---|---|
| Windows | 10 / 11 | — |
| Node.js | 22 | — |
| pnpm | 9 | `npm install -g pnpm` |
| Python | 3.11 | — |
| uv | 最新 | `pip install uv` |
| NVIDIA GPU | 6GB VRAM | RTX 3060 或更高 |
| CUDA | 12.4+ | `nvidia-smi` 查看 |
| CUDNN | 9.2+ | 见下方 CUDNN 排错 |
| Obsidian | 1.5+ | Desktop only |
| Docker Desktop | 可选 | 已弃用，见下方说明 |

## 一键安装

```powershell
# 1. 克隆并安装依赖
git clone https://github.com/gxpppp/ai-learning-agent.git
cd ai-learning-agent
pnpm install
cd python/backend && uv sync && cd ../..

# 2. 部署到 Obsidian
.\install.ps1 -VaultPath "C:\Users\你的用户名\你的Vault"
```

## 模型部署

安装脚本**不会**部署模型文件——模型太大（BGE-M3 ~2.2GB），需手动完成。

### BGE-M3（RAG 语义搜索）

| 方式 | 步骤 |
|---|---|
| **HuggingFace 直链** | 从 [hf-mirror.com](https://hf-mirror.com/BAAI/bge-m3) 下载 6 个文件到 `backend/models/bge-m3/` |
| **自动下载** | 首次启用 RAG 时后端会自动从 HuggingFace 下载 |

### PaddleOCR（文档扫描）

**无需手动部署**。首次使用 OCR 时，PaddleOCR 自动从 modelscope 下载 4 个子模型（~100MB），缓存到 `C:\Users\你\.paddlex\official_models\`。

### CUDNN 版本修复（PaddleOCR 乱码修复）

如果 PaddleOCR 输出乱码（单字母），见 [故障排查 Q3](troubleshooting.md#q3)。

## 不需要 Docker

当前版本使用本地 PaddleOCR（unpip 直接安装），**不再需要 Docker**。

```diff
- docker-compose.yml    # 已弃用
- paddleocr-genai-vllm-server  # 已弃用
+ pip paddleocr           # 当前方案
```

## 配置详解

### 后端环境变量（`.env` 或 sidecar 传递）

```bash
# ─── LLM ───
PROVIDERS_JSON=[{"id":"deepseek","name":"DeepSeek","baseUrl":"https://api.deepseek.com/v1","apiKey":"sk-xxx","models":["deepseek-chat"]}]
ACTIVE_PROVIDER_ID=deepseek
ACTIVE_CHAT_MODEL=deepseek-chat
ACTIVE_AGENT_MODEL=deepseek-chat

# ─── 服务器 ───
SERVER_PORT=8765
SERVER_HOST=127.0.0.1

# ─── RAG ───
RAG_ENABLED=false           # 设为 true 启用
EMBEDDING_MODEL=backend/models/bge-m3  # 本地路径
AUTO_INDEX=false            # 自动监听 vault 变更
CHUNK_SIZE=512
CHUNK_OVERLAP=64

# ─── OCR ───
OCR_ENABLED=false           # 设为 true 启用

# ─── Agent ───
TOOL_PERMISSIONS=readonly   # readonly | full

# ─── Thinking ───
REASONING_ENABLED=false     # 设为 true 启用
REASONING_EFFORT=high       # low|medium|high|max

# ─── Vault ───
OBSIDIAN_VAULT_PATH=C:/Users/你/YourVault
```

### Obsidian 设置面板

所有配置都可以在 **Obsidian → Settings → AI Learning Agent** 中修改，无需手动编辑 `.env`。

设置面板分 7 个区块：
- **Vault** — vault 路径
- **Providers** — LLM 提供商管理（增删改、Fetch Models、Test Connection）
- **Active Provider** — 当前使用的提供商
- **Model Assignment** — 聊天模型 / Agent 模型
- **Tool Permissions** — readonly 或 full
- **Thinking Mode** — 启用 + reasoning effort
- **Server** — 端口号

## 启用功能

| 功能 | 开关 | 额外条件 |
|---|---|---|
| 聊天 | 默认开 | API key 配置正确 |
| Agent 工具 | 默认开 | 支持 function calling 的模型 |
| RAG | `RAG_ENABLED=true` | BGE-M3 模型就绪 + vault 已索引 |
| OCR | `OCR_ENABLED=true` | PaddleOCR 子模型下载完成 |
| 词云 | 自动 | vault 有笔记 |
| Thinking | `REASONING_ENABLED=true` | 使用 DeepSeek V4 Pro/Flash |

## 目录结构

```
YourVault/
├── .obsidian/
│   └── plugins/
│       └── ai-learning-agent/    ← 插件安装位置
│           ├── main.js
│           ├── styles.css
│           ├── manifest.json
│           └── backend/          ← Python 后端
│               ├── src/app/
│               ├── models/       ← BGE-M3 模型放这里
│               │   └── bge-m3/
│               ├── pyproject.toml
│               └── .venv/
├── .ai-tutor/                    ← 运行时数据
│   ├── lancedb/                  ← 向量库
│   ├── evolution/                ← 自进化引擎
│   ├── index_state.json
│   └── tfidf.db                  ← 词云数据
├── AI Chat Logs/                 ← 聊天记录
├── OCR/                          ← 默认 OCR 输出
└── your-notes/                   ← 你的笔记
```

## 升级

```powershell
# 在项目根目录
git pull
pnpm install
cd python/backend && uv sync && cd ../..
.\install.ps1 -VaultPath "你的Vault"
```

重启 Obsidian 即可。
