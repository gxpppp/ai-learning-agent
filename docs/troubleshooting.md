# 故障排查 Q&A

## Q1: 后端启动 30 秒超时

```
Failed to start backend: Backend did not become healthy within 30000ms
```

**原因**：首次加载 BGE-M3 模型需要额外时间（模型加载 + GPU 预热）。

**解决**：重启 Obsidian 再试一次。如果反复超时，检查 `RAG_ENABLED=false` 是否配置正确——BGE-M3 加载是最耗时的操作。

---

## Q2: Backend not found at electron.asar\renderer\backend

```
Backend not found at F:\...\electron.asar\renderer\backend
```

**原因**：早期版本用 `__dirname` 定位插件目录，但在 Obsidian Electron 环境下 `__dirname` 指向 Electron 内部。

**解决**：v0.5.0+ 已修复。升级到最新代码，重启 Obsidian。

---

## Q3: PaddleOCR 识别全是乱码单字母（`n a o t o e e e...`）

**原因**：系统 CUDNN 版本与 PaddlePaddle 编译版本不匹配（系统 CUDNN 9.2 vs PaddlePaddle 需要 9.9）。

**解决**：
```powershell
# 升级 nvidia-cudnn-cu12 pip 包
cd backend
uv pip install "nvidia-cudnn-cu12>=9.24"

# 复制 DLL 到 CUDA toolkit 目录
Copy-Item ".venv\Lib\site-packages\nvidia\cudnn\bin\*.dll" `
    "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4\bin\" -Force
```

---

## Q4: tokenizer.json 只有 136 字节（Git LFS 指针）

**现象**：HuggingFace 下载的 tokenizer.json 是 Git LFS 指针文件，不是实际 JSON。

**原因**：浏览器直链下载 HuggingFace 文件时不解析 LFS。

**解决**：用 Python urllib 重下载：
```python
import urllib.request
url = "https://hf-mirror.com/PaddlePaddle/PaddleOCR-VL/resolve/main/tokenizer.json"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
data = urllib.request.urlopen(req, timeout=120).read()
with open("tokenizer.json", "wb") as f:
    f.write(data)  # 应该约 11MB
```

> 注意：当前版本已改用传统 PaddleOCR，不再需要 PaddleOCR-VL。

---

## Q5: PaddleOCR-VL PyTorch 版加载失败

```
KeyError: 'default'  →  TypeError: create_causal_mask() got unexpected keyword argument
```

**原因**：PaddleOCR-VL 的 HuggingFace 版与 transformers 5.x 兼容性差，需要特定 transformers 版本，且需手动修改 config.json 和 modeling 源码。

**解决**：当前版本已改用传统 **PaddleOCR (PP-OCRv6)**，中文识别准确率够用，无需这些兼容性 hack。

---

## Q6: RAG 返回 503 "not initialized (no vault indexed)"

```
RAG service not initialized (no vault indexed)
```

**原因**：RAG 功能默认关闭，需手动启用。

**解决**：
1. 确保 BGE-M3 模型已下载到 `backend/models/bge-m3/`
2. 在设置中把 `RAG_ENABLED=true`
3. 重启后端后调用：
```bash
curl -X POST http://127.0.0.1:8765/api/vault/index \
  -H "Content-Type: application/json" \
  -d '{"vault_path":"C:/Users/.../YourVault"}'
```

---

## Q7: BGE-M3 模型下载慢

**原因**：HuggingFace 直连慢。

**解决方案**：
1. 用 HuggingFace 国内镜像下载模型文件
2. 放到 `backend/models/bge-m3/` 目录
3. 重启后端自动识别

**下载链接**：
```
https://hf-mirror.com/BAAI/bge-m3/resolve/main/pytorch_model.bin  (~2.2GB)
https://hf-mirror.com/BAAI/bge-m3/resolve/main/config.json
https://hf-mirror.com/BAAI/bge-m3/resolve/main/tokenizer.json
https://hf-mirror.com/BAAI/bge-m3/resolve/main/sentence_bert_config.json
https://hf-mirror.com/BAAI/bge-m3/resolve/main/modules.json
https://hf-mirror.com/BAAI/bge-m3/resolve/main/1_Pooling/config.json
```

---

## Q8: 聊天还是用旧 API key（opencode.ai）

**现象**：即使设置面板换了新 key，聊天仍然报 RateLimitError (opencode.ai)。

**原因**：新 key 填到了"新增的 Provider"卡片里，但 **Active Provider** 下拉还是选中的旧 Provider（ID="deepseek"）。

**解决**：
1. 打开设置 → AI Learning Agent
2. 找到 **Active Provider** 区域
3. 下拉选择你填了新 key 的 Provider
4. 点击 **Save & Restart Backend**

---

## Q9: Agent 返回 422 Unprocessable Entity

```
POST /api/agent/chat → 422
```

**原因**：早期版本 AgentChatRequest 错误继承了 ChatMessage（要求 role 字段），前端传的 JSON 缺 role。

**解决**：v0.5.0+ 已修复。AgentChatRequest 改为独立 BaseModel。

---

## Q10: 聊天回报 RateLimit 429

```
openai.RateLimitError: Monthly usage limit reached. Resets in 13 days.
```

**原因**：当前 API key 月配额用完。

**解决**：
1. 添加新 Provider（其他 key / 其他平台）
2. 设置里 Active Provider 切换到新 Provider
3. Save & Restart Backend

---

## Q11: CUDNN 版本警告（反复出现）

```
WARNING: CUDNN version 9.5 vs Paddle compiled with CUDNN 9.9
```

**影响**：可能导致 PaddleOCR 识别质量下降或乱码。

**解决**：见 **Q3** 的完整方案。

---

## Q12: Docker 拉取超慢 / 磁盘占用巨大

**现象**：`docker pull paddleocr-genai-vllm-server` 要下载 15GB+ 且经常断。

**原因**：PaddleOCR-VL Docker 镜像包含完整 Ubuntu + CUDA + PaddlePaddle + vLLM + 模型。

**解决**：当前版本已弃用 Docker 方案，改用本地 **PaddleOCR (PP-OCRv6)**。引擎更小（~100MB）、更快、更稳定。
