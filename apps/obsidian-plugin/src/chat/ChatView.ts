/** AI Chat panel — Agent SSE with tool call rendering, model dropdown, conversation history. */

import type { IChatMessage } from "@ai-tutor/shared-types";
import { type App, ItemView, Notice, type WorkspaceLeaf } from "obsidian";
import type AILearningAgentPlugin from "../main";
import { MessageRenderer } from "./MessageRenderer";
import { ToolCallRenderer } from "./ToolCallRenderer";
import { UploadZone } from "./UploadZone";
import { FeedbackBar } from "./FeedbackBar";

export const CHAT_VIEW_TYPE = "ai-learning-chat";

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
}

export class ChatView extends ItemView {
  plugin: AILearningAgentPlugin;
  renderer: MessageRenderer;

  private messages: ChatMessage[] = [];
  private messagesEl!: HTMLElement;
  private agentStatusEl!: HTMLElement;
  private inputEl!: HTMLTextAreaElement;
  private uploadZone!: UploadZone;
  private sendBtn!: HTMLElement;
  private stopBtn!: HTMLElement;
  private abortController: AbortController | null = null;
  private isStreaming = false;
  private userScrolledUp = false;
  private readonly SCROLL_THRESHOLD = 50;
  private currentChatFile: string | null = null;

  constructor(leaf: WorkspaceLeaf, plugin: AILearningAgentPlugin) {
    super(leaf);
    this.plugin = plugin;
    this.renderer = new MessageRenderer(this.app, this);
    this.navigation = false;
  }

  getViewType(): string { return CHAT_VIEW_TYPE; }
  getDisplayText(): string { return "AI Tutor"; }
  getIcon(): string { return "message-square"; }

  async onOpen(): Promise<void> {
    const container = this.containerEl.children[1] as HTMLElement;
    container.empty();
    container.addClass("ai-chat-container");

    const modelBar = container.createDiv({ cls: "ai-chat-model-bar" });
    const models = this.plugin.settings.providers?.flatMap((p) => p.models || []) || [];
    if (models.length > 0) {
      const select = modelBar.createEl("select", { cls: "ai-chat-model-select" });
      for (const m of models) {
        const opt = select.createEl("option", { text: m, value: m });
        if (m === this.plugin.settings.activeChatModel) opt.selected = true;
      }
      select.addEventListener("change", () => {
        this.plugin.settings.activeChatModel = select.value;
        this.plugin.saveSettings();
      });
    } else {
      modelBar.createSpan({ text: this.plugin.settings.activeChatModel || "No model", cls: "ai-chat-model-label" });
    }

    this.buildMessageArea(container);
    this.agentStatusEl = container.createDiv({ cls: "ai-agent-status-bar" });
    this.agentStatusEl.style.display = "none";
    this.buildUploadZone(container);
    this.buildInputBar(container);
    await this.loadLastSession();
  }

  async onClose(): Promise<void> {
    this.abortStreaming();
    if (this.messages.length > 0) await this.saveSession();
  }

  private buildMessageArea(container: HTMLElement): void {
    this.messagesEl = container.createDiv({ cls: "ai-chat-messages" });
    this.messagesEl.addEventListener("scroll", () => {
      const { scrollTop, scrollHeight, clientHeight } = this.messagesEl;
      this.userScrolledUp = scrollHeight - scrollTop - clientHeight > this.SCROLL_THRESHOLD;
    });
  }

  private buildUploadZone(container: HTMLElement): void {
    this.uploadZone = new UploadZone(container, this.plugin.settings.server.port);
  }

  private buildInputBar(container: HTMLElement): void {
    const inputBar = container.createDiv({ cls: "ai-chat-input-bar" });
    this.inputEl = inputBar.createEl("textarea", {
      attr: { placeholder: "Ask your AI tutor anything...", rows: "1" },
      cls: "ai-chat-input",
    });
    this.inputEl.addEventListener("input", () => {
      this.inputEl.style.height = "auto";
      this.inputEl.style.height = `${Math.min(this.inputEl.scrollHeight, 200)}px`;
    });
    this.inputEl.addEventListener("keydown", (evt: KeyboardEvent) => {
      if (evt.key === "Enter" && !evt.shiftKey) { evt.preventDefault(); this.sendMessage(); }
      if (evt.key === "Escape" && this.isStreaming) { evt.preventDefault(); this.abortStreaming(); }
    });
    const btnRow = inputBar.createDiv({ cls: "ai-chat-btn-row" });
    this.stopBtn = btnRow.createEl("button", { cls: "ai-chat-stop-btn", text: "Stop" });
    this.stopBtn.addEventListener("click", () => this.abortStreaming());
    this.stopBtn.style.display = "none";
    this.sendBtn = btnRow.createEl("button", { cls: "ai-chat-send-btn mod-cta", text: "Send" });
    this.sendBtn.addEventListener("click", () => this.sendMessage());
  }

  private setStreamingMode(active: boolean): void {
    this.isStreaming = active;
    this.sendBtn.style.display = active ? "none" : "";
    this.stopBtn.style.display = active ? "" : "none";
    if (active) this.inputEl.setAttribute("disabled", "true");
    else { this.inputEl.removeAttribute("disabled"); this.inputEl.focus(); }
  }

  async sendMessage(): Promise<void> {
    let content = this.inputEl.value.trim();
    const paths = this.uploadZone.getUploadedPaths();
    if (paths.length > 0) {
      const fileHints = paths.map((p) => `[File: ${p}]`).join("\n");
      content = content ? `${fileHints}\n${content}` : fileHints;
      this.uploadZone.clear();
    }
    if (!content || this.isStreaming) return;
    this.inputEl.value = "";
    this.inputEl.style.height = "auto";

    const userMsg = this.addMessage("user", content);
    this.renderMessageToDOM(userMsg);
    this.forceScrollToBottom();

    this.setStreamingMode(true);
    this.abortController = new AbortController();

    const assistantMsgEl = this.renderer.createMessageContainer("assistant");
    this.messagesEl.appendChild(assistantMsgEl);
    this.renderer.beginStreaming(assistantMsgEl);
    this.forceScrollToBottom();

    const port = this.plugin.settings.server.port;
    const toolRenderer = new ToolCallRenderer(this.messagesEl);

    try {
      const responseText = await this.agentStream(content, port, toolRenderer);
      await this.renderer.finishStreaming();
      this.addMessage("assistant", responseText);
      new FeedbackBar(assistantMsgEl, port, this.currentChatFile || "session");
      await this.saveSession();
    } catch (err: unknown) {
      await this.renderer.finishStreaming();
      try {
        const fb = await this.chatFallback(content, port);
        await this.renderer.finishStreaming();
        this.addMessage("assistant", fb);
        await this.saveSession();
      } catch {
        const msg = err instanceof Error ? err.message : String(err);
        this.renderer.renderError(assistantMsgEl, msg);
      }
    } finally {
      this.setStreamingMode(false);
      this.abortController = null;
    }
  }

  private async agentStream(content: string, port: number, toolRenderer: ToolCallRenderer): Promise<string> {
    const resp = await fetch(`http://127.0.0.1:${port}/api/agent/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation: this.messages.map((m) => ({ role: m.role, content: m.content })),
        content,
      }),
      signal: this.abortController!.signal,
    });
    if (!resp.ok) throw new Error(`Agent error (${resp.status})`);
    if (!resp.body) throw new Error("No response body");

    const reader = resp.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let fullText = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";
      for (const part of parts) {
        if (!part.trim()) continue;
        const lines = part.split("\n");
        let eventType = "message";
        let dataPayload = "";
        for (const line of lines) {
          if (line.startsWith("event:")) eventType = line.slice(6).trim();
          else if (line.startsWith("data:")) dataPayload = line.slice(5).trim();
        }
        if (dataPayload === "[DONE]") return fullText;
        try {
          const parsed = JSON.parse(dataPayload);
          if (eventType === "thinking" && parsed.content) {
            this.renderer.appendThinking(parsed.content);
            this.scrollToBottomIfDesired();
          } else if (eventType === "token" && parsed.content) {
            fullText += parsed.content;
            this.renderer.appendToken(parsed.content);
            this.scrollToBottomIfDesired();
          } else if (eventType === "tool_call") {
            toolRenderer.renderToolCall(parsed);
            this.scrollToBottomIfDesired();
          } else if (eventType === "tool_result") {
            await toolRenderer.renderToolResult(parsed, this.app, this);
            this.scrollToBottomIfDesired();
          } else if (eventType === "agent_start") {
            toolRenderer.renderAgentMarker(parsed.agent, "start", parsed.task);
            this.showAgentStatus(parsed.agent, parsed.task || "");
            this.scrollToBottomIfDesired();
          } else if (eventType === "agent_end") {
            toolRenderer.renderAgentMarker(parsed.agent, "end");
            this.hideAgentStatus();
            this.scrollToBottomIfDesired();
          }
        } catch { /* skip */ }
      }
    }
    return fullText;
  }

  private async chatFallback(content: string, port: number): Promise<string> {
    const { streamChat } = await import("./sse-client");
    const msgs: IChatMessage[] = [
      { role: "system", content: "You are an AI tutor. Be concise and helpful." },
      ...this.messages.map((m) => ({ role: m.role as "system" | "user" | "assistant", content: m.content })),
    ];
    return streamChat(msgs,
      { onToken: (t) => { this.renderer.appendToken(t); this.scrollToBottomIfDesired(); }, onError: () => {}, onDone: () => {} },
      { baseUrl: `http://127.0.0.1:${port}`, model: this.plugin.settings.activeChatModel || "deepseek-chat", signal: this.abortController?.signal },
    );
  }

  abortStreaming(): void { this.abortController?.abort(); }

  private showAgentStatus(agent: string, task: string): void {
    this.agentStatusEl.style.display = "block";
    const icons: Record<string, string> = {
      orchestrator: "🧩", searcher: "🔍", operator: "⚙️", verifier: "✅",
    };
    const icon = icons[agent] || "🤖";
    const steps = ["orchestrator", "searcher", "operator", "verifier"];
    const currentIdx = steps.indexOf(agent);
    let html = "";
    for (let i = 0; i < steps.length; i++) {
      const active = i === currentIdx;
      const done = i < currentIdx;
      const icon = icons[steps[i]] || "⬤";
      html += `<span class="${active ? "ai-status-active" : done ? "ai-status-done" : "ai-status-pending"}">
        ${done ? "✅" : icon} ${steps[i]}
      </span>${i < steps.length - 1 ? " → " : ""}`;
    }
    html += `<span class="ai-status-task">: ${task.slice(0, 50)}</span>`;
    this.agentStatusEl.innerHTML = html;
  }

  private hideAgentStatus(): void {
    setTimeout(() => { this.agentStatusEl.style.display = "none"; }, 2000);
  }

  private addMessage(role: "user" | "assistant" | "system", content: string): ChatMessage {
    const msg: ChatMessage = { id: crypto.randomUUID(), role, content, timestamp: Date.now() };
    this.messages.push(msg);
    return msg;
  }

  private renderMessageToDOM(msg: ChatMessage): void {
    const msgEl = this.renderer.createMessageContainer(msg.role);
    this.messagesEl.appendChild(msgEl);
    this.renderer.renderMessage(msgEl, msg.content);
  }

  renderAllMessages(): void {
    this.messagesEl.empty();
    for (const msg of this.messages) this.renderMessageToDOM(msg);
    this.forceScrollToBottom();
  }

  private readonly CHAT_FOLDER = "AI Chat Logs";

  private async saveSession(): Promise<void> {
    if (this.messages.length === 0) return;
    try {
      await this.ensureFolder(this.CHAT_FOLDER);
      if (!this.currentChatFile) {
        this.currentChatFile = `${this.CHAT_FOLDER}/Chat - ${new Date().toISOString().slice(0, 10)}.md`;
      }
      let md = `---\nsession_date: ${new Date().toISOString()}\nmessage_count: ${this.messages.length}\nmodel: ${this.plugin.settings.activeChatModel || "unknown"}\n---\n\n`;
      for (const msg of this.messages) md += `### ${msg.role === "user" ? "You" : "AI Tutor"}\n\n${msg.content}\n\n---\n\n`;
      await this.app.vault.adapter.write(this.currentChatFile, md);
    } catch (err) { console.error("[ai-tutor] save failed:", err); }
  }

  private async loadLastSession(): Promise<void> {
    try {
      await this.ensureFolder(this.CHAT_FOLDER);
      const files = await this.app.vault.adapter.list(this.CHAT_FOLDER);
      const mdFiles = files.files.filter((f) => f.endsWith(".md")).sort().reverse();
      if (!mdFiles[0]) return;
      const content = await this.app.vault.adapter.read(mdFiles[0]);
      this.currentChatFile = mdFiles[0];
      this.messages = this.parseMarkdownToMessages(content);
      this.renderAllMessages();
    } catch (err) { console.error("[ai-tutor] load failed:", err); }
  }

  private parseMarkdownToMessages(md: string): ChatMessage[] {
    const messages: ChatMessage[] = [];
    const sections = md.split(/\n### (You|AI Tutor)\n\n/);
    for (let i = 1; i < sections.length; i += 2) {
      let content = (sections[i + 1] ?? "").trim();
      content = content.replace(/\n---\n\n$/, "").replace(/\n---$/, "");
      messages.push({ id: crypto.randomUUID(), role: sections[i] === "You" ? "user" : "assistant", content, timestamp: Date.now() });
    }
    return messages;
  }

  private async ensureFolder(folderPath: string): Promise<void> {
    if (!(await this.app.vault.adapter.exists(folderPath))) {
      await this.app.vault.createFolder(folderPath);
    }
  }

  async newSession(): Promise<void> {
    await this.saveSession();
    this.messages = [];
    this.currentChatFile = null;
    this.messagesEl.empty();
  }

  private forceScrollToBottom(): void {
    this.userScrolledUp = false;
    requestAnimationFrame(() => { this.messagesEl.scrollTop = this.messagesEl.scrollHeight; });
  }

  private scrollToBottomIfDesired(): void {
    if (this.userScrolledUp) return;
    requestAnimationFrame(() => { this.messagesEl.scrollTop = this.messagesEl.scrollHeight; });
  }
}
