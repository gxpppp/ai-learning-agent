import type { IAppConfig, ILLMProvider } from "@ai-tutor/shared-types";
import { DEFAULT_CONFIG } from "@ai-tutor/shared-types";
import { Notice, Plugin } from "obsidian";
import { CHAT_VIEW_TYPE, ChatView } from "./chat/ChatView";
import { WORDCLOUD_VIEW_TYPE, WordCloudView } from "./knowledge/WordCloudView";
import { TagSuggestService } from "./knowledge/TagSuggest";
import { OCR_VIEW_TYPE, OcrView } from "./ocr/OcrView";
import { AISettingsTab } from "./settings";
import { SidecarManager } from "./sidecar";

export default class AILearningAgentPlugin extends Plugin {
  settings: IAppConfig = DEFAULT_CONFIG;
  sidecar: SidecarManager | null = null;

  async onload() {
    await this.loadSettings();

    this.addSettingTab(new AISettingsTab(this.app, this));

    this.registerView(CHAT_VIEW_TYPE, (leaf) => new ChatView(leaf, this));
    this.registerView(OCR_VIEW_TYPE, (leaf) => new OcrView(leaf, this));
    this.registerView(WORDCLOUD_VIEW_TYPE, (leaf) => new WordCloudView(leaf, this));

    this.addRibbonIcon("message-square", "AI Tutor Chat", () => this.activateChatView());

    // Chat commands
    this.addCommand({
      id: "open-ai-chat",
      name: "Open AI chat panel",
      hotkeys: [{ modifiers: ["Mod", "Shift"], key: "L" }],
      callback: () => this.activateChatView(),
    });

    this.addCommand({
      id: "new-chat-session",
      name: "New AI chat session",
      callback: async () => {
        const leaf = this.app.workspace.getLeavesOfType(CHAT_VIEW_TYPE)[0];
        if (leaf?.view instanceof ChatView) {
          await leaf.view.newSession();
          new Notice("New chat session started");
        }
      },
    });

    // OCR commands
    this.addCommand({
      id: "ocr-current-file",
      name: "OCR: Scan current document",
      callback: async () => {
        const leaf = this.app.workspace.getLeavesOfType(OCR_VIEW_TYPE)[0];
        const view = leaf?.view;
        if (view instanceof OcrView) {
          await view.ocrCurrentFile();
        } else {
          new Notice("Open the OCR panel first (AI Tutor: Open OCR panel)");
        }
      },
    });

    this.addCommand({
      id: "open-ocr-panel",
      name: "Open OCR panel",
      callback: () => this.activateOcrView(),
    });

    // Backend management
    this.addCommand({
      id: "start-ai-backend",
      name: "Start AI backend",
      callback: () => this.startSidecar(),
    });

    this.addCommand({
      id: "stop-ai-backend",
      name: "Stop AI backend",
      callback: () => this.stopSidecar(),
    });

    // Word cloud
    this.addCommand({
      id: "open-wordcloud",
      name: "Open word cloud",
      callback: () => this.activateWordCloudView(),
    });

    this.addCommand({
      id: "refresh-wordcloud",
      name: "Word cloud: Refresh",
      callback: async () => {
        const leaf = this.app.workspace.getLeavesOfType(WORDCLOUD_VIEW_TYPE)[0];
        if (leaf?.view instanceof WordCloudView) {
          await leaf.view.refresh();
        }
      },
    });

    // Tag & link commands
    this.addCommand({
      id: "suggest-tags",
      name: "AI: Suggest tags for current note",
      callback: async () => {
        const file = this.app.workspace.getActiveFile();
        if (!file) { new Notice("No active note"); return; }
        const service = new TagSuggestService(this.settings.server.port);
        try {
          const result = await service.suggestTags(file.path);
          new Notice(`Suggested tags: ${result.tags.join(", ")} (${(result.confidence * 100).toFixed(0)}%)`);
        } catch (e) {
          new Notice(`Tag suggestion failed: ${e instanceof Error ? e.message : String(e)}`);
        }
      },
    });

    this.addCommand({
      id: "recommend-links",
      name: "AI: Recommend links for current note",
      callback: async () => {
        const file = this.app.workspace.getActiveFile();
        if (!file) { new Notice("No active note"); return; }
        const service = new TagSuggestService(this.settings.server.port);
        try {
          const result = await service.recommendLinks(file.path);
          if (result.links.length === 0) {
            new Notice("No link recommendations found.");
            return;
          }
          const items = result.links.map((l) => `- [[${l.target}]] (${(l.score * 100).toFixed(0)}%)`);
          new Notice(`Recommended links:\n${items.join("\n")}`, 0);
        } catch (e) {
          new Notice(`Link recommendation failed: ${e instanceof Error ? e.message : String(e)}`);
        }
      },
    });

    this.startSidecar();
  }

  async onunload() {
    this.app.workspace.detachLeavesOfType(CHAT_VIEW_TYPE);
    this.app.workspace.detachLeavesOfType(OCR_VIEW_TYPE);
    this.app.workspace.detachLeavesOfType(WORDCLOUD_VIEW_TYPE);
    await this.stopSidecar();
  }

  async activateChatView() {
    const { workspace } = this.app;
    const leaf = workspace.getLeavesOfType(CHAT_VIEW_TYPE)[0];
    if (!leaf) {
      const rightLeaf = workspace.getRightLeaf(false);
      if (rightLeaf) {
        await rightLeaf.setViewState({ type: CHAT_VIEW_TYPE, active: true });
      }
    } else {
      workspace.revealLeaf(leaf);
    }
  }

  async activateOcrView() {
    const { workspace } = this.app;
    const leaf = workspace.getLeavesOfType(OCR_VIEW_TYPE)[0];
    if (!leaf) {
      const rightLeaf = workspace.getRightLeaf(false);
      if (rightLeaf) {
        await rightLeaf.setViewState({ type: OCR_VIEW_TYPE, active: true });
      }
    } else {
      workspace.revealLeaf(leaf);
    }
  }

  async activateWordCloudView() {
    const { workspace } = this.app;
    const leaf = workspace.getLeavesOfType(WORDCLOUD_VIEW_TYPE)[0];
    if (!leaf) {
      const rightLeaf = workspace.getRightLeaf(false);
      if (rightLeaf) {
        await rightLeaf.setViewState({ type: WORDCLOUD_VIEW_TYPE, active: true });
      }
    } else {
      workspace.revealLeaf(leaf);
    }
  }

  async loadSettings() {
    const data = await this.loadData();
    this.settings = { ...DEFAULT_CONFIG, ...data };

    // Migrate old single-provider config to new multi-provider format
    const old = data as { llm?: { baseUrl: string; apiKey: string; model: string } };
    if (old?.llm) {
      this.settings.providers = [
        {
          id: "deepseek",
          name: "Migrated Provider",
          baseUrl: old.llm.baseUrl || "https://api.deepseek.com/v1",
          apiKey: old.llm.apiKey || "",
          models: [old.llm.model || "deepseek-chat"],
        },
      ];
      this.settings.activeChatModel = old.llm.model || "deepseek-chat";
      this.settings.activeAgentModel = old.llm.model || "deepseek-chat";
      await this.saveSettings();
    }
  }

  getVaultBasePath(): string {
    // @ts-expect-error basePath is available on the vault adapter in desktop Obsidian
    return this.app.vault.adapter.basePath ?? "";
  }

  async saveSettings() {
    await this.saveData(this.settings);
  }

  async startSidecar() {
    if (this.sidecar) {
      new Notice("AI backend is already running");
      return;
    }
    this.sidecar = new SidecarManager(this.settings, this.getVaultBasePath());
    try {
      await this.sidecar.start();
      new Notice("AI backend started");
    } catch (e) {
      new Notice(`Failed to start backend: ${e}`);
      this.sidecar = null;
    }
  }

  async stopSidecar() {
    if (this.sidecar) {
      await this.sidecar.stop();
      this.sidecar = null;
      new Notice("AI backend stopped");
    }
  }
}
