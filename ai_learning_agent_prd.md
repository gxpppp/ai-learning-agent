# AI-Native 学习增强系统——需求规格说明书 (PRD)

| 文档版本 | 1.0 |
| :--- | :--- |
| 发布日期 | 2026-07-08 |
| 作者 | gxpppp |
| 状态 | 草案 (Draft) |

---

## 目录

1. [产品愿景与定位](#1-产品愿景与定位)
2. [核心需求拆解](#2-核心需求拆解)
3. [详细功能规格](#3-详细功能规格)
   - [3.1 AI学习智能体 (Learning Agent)](#31-ai学习智能体-learning-agent)
   - [3.2 知识库引擎 (与Obsidian深度集成)](#32-知识库引擎-与obsidian深度集成)
   - [3.3 文档库自动生成](#33-文档库自动生成)
   - [3.4 视觉化分析 (词云)](#34-视觉化分析-词云)
   - [3.5 自我进化引擎 (Self-Evolution)](#35-自我进化引擎-self-evolution)
4. [系统架构概览](#4-系统架构概览)
5. [技术栈建议](#5-技术栈建议)
6. [开发路线图 (Roadmap)](#6-开发路线图-roadmap)
7. [附录：市场竞品分析摘要](#7-附录市场竞品分析摘要)

---

## 1. 产品愿景与定位

打造一个**具备自我进化能力的AI-Native第二大脑**。它不只是一个聊天机器人或笔记软件，而是一个能像资深导师一样规划学习路径、像顶级分析师一样将知识可视化、像专业开发者一样通过迭代来优化自身（类似 OpenHarness）的终身学习伴侣。

**目标用户**：需要深度知识管理、跨学科学习、且具备一定技术背景的学习者与开发者。

---

## 2. 核心需求拆解

| 编号 | 需求关键词 | 一句话描述 | 优先级 |
| :--- | :--- | :--- | :--- |
| **F1** | AI Agent 辅助学习 | 多智能体协作，主动拆解课题，生成学习路径与深度问答 | P0 核心 |
| **F2** | 连接 Obsidian | 深度双向集成，读写 Obsidian Vault，维护知识图谱 | P0 核心 |
| **F3** | 生成文档库 | 基于私有知识库，自动生成结构化、可发布的文档站点 | P1 高 |
| **F4** | 生成词云 | 基于笔记内容智能提取关键词，生成可交互的视觉化词云 | P2 中 |
| **F5** | 自我进化 | 记录用户反馈，自动优化提示词与工具链，具备程序级自迭代 | P1 高 |

---

## 3. 详细功能规格

### 3.1 AI学习智能体 (Learning Agent)

#### 3.1.1 多智能体协作架构
- **规划智能体 (Planner)**：接收模糊的学习意图（例如“我想搞懂 Rust 的所有权机制”），自动拆解为 `学习路径图`（Markdown 任务列表）。
- **研究智能体 (Researcher)**：集成联网搜索（Tavily/SerpAPI）与本地 RAG，搜集资料并标注引用来源。
- **导师智能体 (Tutor)**：采用苏格拉底式问答，进行形成性评价，指出知识盲区。
- **审查智能体 (Reviewer)**：检查生成内容是否偏离用户设定的学习目标，防止幻觉。

#### 3.1.2 交互模式
- **主动式推送**：每天启动时生成 "今日学习卡片"。
- **Feynman 模式**：让 AI 扮演学生，由用户讲解，AI 追问细节，直到用户讲透。

### 3.2 知识库引擎 (与Obsidian深度集成)

#### 3.2.1 本地插件 (Obsidian Plugin)
- **双向链接增强**：AI 读取笔记后，自动推荐内部 `[[双向链接]]`。
- **智能标签**：自动为无标签笔记补充 `--- tags: [...] ---` 元数据。
- **命令面板集成**：在 Obsidian 内按 `Ctrl+P` 直接唤出 Agent 对话窗口。

#### 3.2.2 外部服务 (Local Server / Sidecar)
- **文件监听**：通过 `chokidar` 监听 `.obsidian/` 目录变更，实时同步向量数据库。
- **图谱增强**：提供 JSON API，将 AI 分析后的语义关系注入 Obsidian Graph View。

### 3.3 文档库自动生成

- **输入**：Obsidian 中某个文件夹（如 `Published/`）下的 Markdown 笔记。
- **输出**：静态文档网站（可选 VitePress、Docusaurus 或 Nextra）。
- **AI 赋能**：
  1. 自动生成 `SUMMARY.md` / 侧边栏结构。
  2. 为每篇笔记生成 "TL;DR" 摘要块和导航卡片。
  3. 修复 Markdown 语法错误及相对路径引用。
- **一键部署**：集成 GitHub Actions，推送即部署到 Vercel / Cloudflare Pages。

### 3.4 视觉化分析 (词云)

- **词云生成管道**：
  1. **读取**：扫描选定笔记库或搜索结果。
  2. **分词与清洗**：接入中文分词（结巴 `jieba`）与英文 NLTK，去除停用词。
  3. **加权算法**：结合 `TF-IDF` 与笔记内的 `双链权重`（被链接越多的词权重越高）。
  4. **渲染**：生成 SVG / Canvas 可交互词云，点击词语直接跳转 Obsidian 对应笔记。
- **视觉进化**：生成随时间变化的 "知识热力图"，显示用户关注点的迁移。

### 3.5 自我进化引擎 (Self-Evolution)

这是本产品与普通 AI 工具的核心差异点：

#### 3.5.1 反馈闭环 (RLHF Light)
- 用户对任何 AI 输出执行 👍 / 👎 操作。
- 系统将评分、上下文和修正结果存入本地 `evolution/feedback.jsonl`。
- 定期（每周）触发微调适配器（LoRA）训练脚本（自动调用本地 GPU）。

#### 3.5.2 程序级自我迭代 (Inspired by OpenHarness)
- **基准测试 (Eval Harness)**：内置一套测试集（包含 QA 对、任务完成度评估）。
- **变异与验证**：
  1. 当需要提升某项能力时，Agent 生成新的 System Prompt 变体。
  2. 在沙箱中运行评测。
  3. 如果通过测试，自动替换旧配置；如果不通过，回滚并记录日志。
- **插件热插拔**：核心逻辑模块化。Agent 能编写新的 Python/TS 函数（Skill Plugin），加载到 Runtime 中扩展能力，失败时自动隔离。

---

## 4. 系统架构概览

```mermaid
graph TD
    subgraph "用户交互层"
        A[Obsidian 编辑器]
        B[Web UI / 桌面端]
    end

    subgraph "AI 编排层 (Core)"
        C[任务路由器 & 多智能体]
        D[自我进化模块 (Evo Engine)]
        E[评估测试框架 (Eval Harness)]
    end

    subgraph "知识处理层"
        F[本地 RAG / 向量数据库 (Chroma/LanceDB)]
        G[文档静态生成器]
        H[词云分析管道]
    end

    subgraph "数据持久层"
        I[Obsidian Vault (Markdown Files)]
        J[元数据库 (SQLite / JSON)]
    end

    A <--> C
    B <--> C
    C --> F
    C --> G
    C --> H
    F --> I
    E <--> C
    D <--> E
    D --> J
```

---

## 5. 技术栈建议

鉴于你熟练掌握 C++、熟悉 VS Code，且仓库位于 GitHub，建议采用 **TypeScript (前端/插件) + Python (AI核心) + Rust/C++ (性能敏感模块)** 的混合架构：

| 层级 | 推荐技术 | 原因 |
| :--- | :--- | :--- |
| **Obsidian 插件** | TypeScript + Obsidian API | 原生开发体验最佳 |
| **AI Agent 框架** | LangChain.js / LangGraph | 完善的工具链与记忆管理 |
| **后端/CLI** | Python (FastAPI / Typer) | 数据科学生态丰富 (jieba, scikit-learn) |
| **向量存储** | LanceDB (本地文件) | 无需部署服务器，性能强于 Chroma |
| **自进化框架** | 自研 Evo SDK (TypeScript) | 借鉴 EleutherAI LM Evaluation Harness 设计 |
| **静态文档** | VitePress 或 Astro | 构建速度快，Markdown 原生支持 |

---

## 6. 开发路线图 (Roadmap)

### Phase 1: 基础连接与对话 (MVP - 4周)
- [ ] 搭建 Obsidian 插件基础框架，实现侧边栏聊天面板。
- [ ] 实现与 OpenAI/DeepSeek 兼容 API 的流式对话。
- [ ] 实现 Markdown 文件级 CRUD 操作（AI 帮助创建/修改笔记）。

### Phase 2: 知识引擎 (6周)
- [ ] 引入向量数据库，实现 Vault 全量索引。
- [ ] 实现基于 RAG 的问答（带引用脚注）。
- [ ] 实现自动标签与双链推荐。
- [ ] 实现词云生成管道（侧边栏渲染）。

### Phase 3: 进化与文档 (6周)
- [ ] 开发文档库一键生成 CLI 工具。
- [ ] 构建反馈收集与 LoRA 微调调度器。
- [ ] 实现 Eval Harness 评测框架原型。
- [ ] 实现 System Prompt 自动优化变异。

### Phase 4: 多智能体协作 (长期)
- [ ] 实现 Planner / Researcher / Tutor 角色分离。
- [ ] 实现 Agent 自主编写新 Skill Plugin。

---

## 7. 附录：市场竞品分析摘要

基于先前的搜索调研，现有工具均无法覆盖全部需求：

- **Obsidian Copilot / Smart Connections**：擅长聊天和基础 RAG，但**无自我进化**能力。
- **AutoGPT / CrewAI**：多智能体编排能力强，但与 Obsidian 的**本地文件集成不深**，无法生成双向链接。
- **Continue.dev**：优秀的代码 IDE 插件，但**不擅长通用知识学习**与文档库生成。
- **Notion AI**：封闭生态，**不开放本地知识库**，无法导出标准 Markdown。

我们的系统将填补 **"代码级可定制性"** 与 **"自我进化能力"** 这两个关键空白。

---

*该文档由 DeepSeek 辅助生成，基于用户 `gxpppp` 的原始需求讨论。*
