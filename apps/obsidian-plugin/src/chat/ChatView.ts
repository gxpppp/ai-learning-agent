/** AI Chat panel — ItemView with streaming SSE chat, conversation history,
 *  smart auto-scroll, and Markdown file persistence.
 */

import type { IChatMessage } from "@ai-tutor/shared-types";
import { type App, ItemView, Notice, type WorkspaceLeaf } from "obsidian";
import type AILearningAgentPlugin from "../main";
import { ragQuery } from "../rag/RagService";
import { MessageRenderer } from "./MessageRenderer";
import { streamChat } from "./sse-client";

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
  private inputEl!: HTMLTextAreaElement;
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

  getViewType(): string {
    return CHAT_VIEW_TYPE;
  }

  getDisplayText(): string {
    return "AI Tutor";
  }

  getIcon(): string {
    return "message-square";
  }

  async onOpen(): Promise<void> {
    const container = this.containerEl.children[1] as HTMLElement;
    container.empty();
    container.addClass("ai-chat-container");

    // Model selector dropdown
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
    this.buildInputBar(container);

    await this.loadLastSession();
  }

  async onClose(): Promise<void> {
    this.abortStreaming();
    if (this.messages.length > 0) {
      await this.saveSession();
    }
  }

  // ─── DOM Construction ────────────────────────────────────────

  private buildMessageArea(container: HTMLElement): void {
    this.messagesEl = container.createDiv({ cls: "ai-chat-messages" });

    this.messagesEl.addEventListener("scroll", () => {
      const { scrollTop, scrollHeight, clientHeight } = this.messagesEl;
      const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
      this.userScrolledUp = distanceFromBottom > this.SCROLL_THRESHOLD;
    });
  }

  private buildInputBar(container: HTMLElement): void {
    const inputBar = container.createDiv({ cls: "ai-chat-input-bar" });

    this.inputEl = inputBar.createEl("textarea", {
      attr: {
        placeholder: "Ask your AI tutor anything... (Enter to send, Shift+Enter for newline)",
        rows: "1",
      },
      cls: "ai-chat-input",
    });

    this.inputEl.addEventListener("input", () => {
      this.inputEl.style.height = "auto";
      this.inputEl.style.height = `${Math.min(this.inputEl.scrollHeight, 200)}px`;
    });

    this.inputEl.addEventListener("keydown", (evt: KeyboardEvent) => {
      if (evt.key === "Enter" && !evt.shiftKey) {
        evt.preventDefault();
        this.sendMessage();
      }
      if (evt.key === "Escape" && this.isStreaming) {
        evt.preventDefault();
        this.abortStreaming();
      }
    });

    const btnRow = inputBar.createDiv({ cls: "ai-chat-btn-row" });

    this.stopBtn = btnRow.createEl("button", { cls: "ai-chat-stop-btn", text: "Stop" });
    this.stopBtn.addEventListener("click", () => this.abortStreaming());
    this.stopBtn.style.display = "none";

    this.sendBtn = btnRow.createEl("button", { cls: "ai-chat-send-btn mod-cta", text: "Send" });
    this.sendBtn.addEventListener("click", () => this.sendMessage());
  }

  // ─── Streaming UI State ──────────────────────────────────────

  private setStreamingMode(active: boolean): void {
    this.isStreaming = active;
    this.sendBtn.style.display = active ? "none" : "";
    this.stopBtn.style.display = active ? "" : "none";
    if (active) {
      this.inputEl.setAttribute("disabled", "true");
    } else {
      this.inputEl.removeAttribute("disabled");
      this.inputEl.focus();
    }
  }

  // ─── Message Sending & Streaming ─────────────────────────────

  async sendMessage(): Promise<void> {
    const content = this.inputEl.value.trim();
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

    try {
      let responseText = "";
      let sources: Array<{ note_path: string; content: string; score: number }> = [];

      responseText = await ragQuery(
        content,
        `http://127.0.0.1:${port}`,
        {
          onToken: (token: string) => {
            this.renderer.appendToken(token);
            this.scrollToBottomIfDesired();
          },
          onSource: (srcs) => {
            sources = srcs;
          },
          onError: (msg: string) => {
            if (!msg.includes("503")) {
              new Notice(`RAG error: ${msg}`);
            }
          },
          onDone: () => {},
        },
        this.abortController.signal,
      );

      // Append source citations
      if (sources.length > 0) {
        const citationMd = sources
          .map(
            (s, i) =>
              `> [${i + 1}] **${s.note_path}** (${(s.score * 100).toFixed(0)}%)\n> ${s.content.trim()}`,
          )
          .join("\n\n");
        responseText += `\n\n---\n**Sources:**\n${citationMd}`;
        this.renderer.appendToken(`\n\n---\n**Sources:**\n${citationMd}`);
        this.scrollToBottomIfDesired();
      }

      await this.renderer.finishStreaming();
      this.addMessage("assistant", responseText);
      await this.saveSession();
    } catch (err: unknown) {
      // Fallback to direct chat if RAG fails
      let fellBack = true;
      try {
        const fullContent: IChatMessage[] = [
          { role: "system" as const, content: "You are an AI tutor. Use Socratic questioning." },
          ...this.messages.map((m) => ({
            role: m.role as "system" | "user" | "assistant",
            content: m.content,
          })),
        ];
        const fallbackText = await streamChat(
          fullContent,
          {
            onToken: (t: string) => {
              this.renderer.appendToken(t);
              this.scrollToBottomIfDesired();
            },
            onError: () => {},
            onDone: () => {},
          },
          {
            baseUrl: `http://127.0.0.1:${port}`,
            model: this.plugin.settings.activeChatModel || "deepseek-chat",
            signal: this.abortController?.signal,
          },
        );
        fellBack = false;
        await this.renderer.finishStreaming();
        this.addMessage("assistant", fallbackText);
        await this.saveSession();
      } catch {
        // both failed
      }

      if (fellBack) {
        await this.renderer.finishStreaming();
        const msg = err instanceof Error ? err.message : String(err);
        this.renderer.renderError(assistantMsgEl, msg);
      }
    } finally {
      this.setStreamingMode(false);
      this.abortController = null;
    }
  }

  abortStreaming(): void {
    this.abortController?.abort();
  }

  // ─── Message Storage ─────────────────────────────────────────

  private addMessage(role: "user" | "assistant" | "system", content: string): ChatMessage {
    const msg: ChatMessage = {
      id: crypto.randomUUID(),
      role,
      content,
      timestamp: Date.now(),
    };
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
    for (const msg of this.messages) {
      this.renderMessageToDOM(msg);
    }
    this.forceScrollToBottom();
  }

  // ─── Conversation Persistence (Markdown files) ───────────────

  private readonly CHAT_FOLDER = "AI Chat Logs";

  private async saveSession(): Promise<void> {
    if (this.messages.length === 0) return;

    try {
      await this.ensureFolder(this.CHAT_FOLDER);

      if (!this.currentChatFile) {
        const date = new Date().toISOString().slice(0, 10);
        this.currentChatFile = `${this.CHAT_FOLDER}/Chat - ${date}.md`;
      }

      let md = "---\n";
      md += `session_date: ${new Date().toISOString()}\n`;
      md += `message_count: ${this.messages.length}\n`;
      md += `model: ${this.plugin.settings.activeChatModel || "unknown"}\n`;
      md += "---\n\n";

      for (const msg of this.messages) {
        const roleIcon = msg.role === "user" ? "You" : "AI Tutor";
        md += `### ${roleIcon}\n\n${msg.content}\n\n---\n\n`;
      }

      await this.app.vault.adapter.write(this.currentChatFile, md);
    } catch (err) {
      console.error("[ai-tutor] Failed to save chat session:", err);
    }
  }

  private async loadLastSession(): Promise<void> {
    try {
      await this.ensureFolder(this.CHAT_FOLDER);

      const files = await this.app.vault.adapter.list(this.CHAT_FOLDER);
      if (files.files.length === 0) return;

      const mdFiles = files.files
        .filter((f) => f.endsWith(".md"))
        .sort()
        .reverse();

      const latest = mdFiles[0];
      if (!latest) return;

      const content = await this.app.vault.adapter.read(latest);
      this.currentChatFile = latest;
      this.messages = this.parseMarkdownToMessages(content);
      this.renderAllMessages();
    } catch (err) {
      console.error("[ai-tutor] Failed to load chat session:", err);
    }
  }

  private parseMarkdownToMessages(md: string): ChatMessage[] {
    const messages: ChatMessage[] = [];
    const sections = md.split(/\n### (You|AI Tutor)\n\n/);

    for (let i = 1; i < sections.length; i += 2) {
      const roleStr = sections[i];
      let content = (sections[i + 1] ?? "").trim();
      content = content.replace(/\n---\n\n$/, "").replace(/\n---$/, "");

      const role = roleStr === "You" ? "user" : "assistant";
      messages.push({
        id: crypto.randomUUID(),
        role,
        content,
        timestamp: Date.now(),
      });
    }
    return messages;
  }

  private async ensureFolder(folderPath: string): Promise<void> {
    const exists = await this.app.vault.adapter.exists(folderPath);
    if (!exists) {
      await this.app.vault.createFolder(folderPath);
    }
  }

  /** Clear current conversation and start fresh. */
  async newSession(): Promise<void> {
    await this.saveSession();
    this.messages = [];
    this.currentChatFile = null;
    this.messagesEl.empty();
  }

  // ─── Scroll Helpers ──────────────────────────────────────────

  private forceScrollToBottom(): void {
    this.userScrolledUp = false;
    requestAnimationFrame(() => {
      this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
    });
  }

  private scrollToBottomIfDesired(): void {
    if (this.userScrolledUp) return;
    requestAnimationFrame(() => {
      this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
    });
  }
}
