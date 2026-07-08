import type { IAppConfig, ILLMConfig } from "@ai-tutor/shared-types";
import { DEFAULT_CONFIG } from "@ai-tutor/shared-types";
import { Notice, Plugin } from "obsidian";
import { CHAT_VIEW_TYPE, ChatView } from "./chat/ChatView";
import { AISettingsTab } from "./settings";
import { SidecarManager } from "./sidecar";

export default class AILearningAgentPlugin extends Plugin {
  settings: IAppConfig = DEFAULT_CONFIG;
  sidecar: SidecarManager | null = null;

  async onload() {
    await this.loadSettings();

    this.addSettingTab(new AISettingsTab(this.app, this));

    this.registerView(CHAT_VIEW_TYPE, (leaf) => new ChatView(leaf, this));

    this.addRibbonIcon("message-square", "AI Tutor Chat", () => this.activateChatView());

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

    this.startSidecar();
  }

  async onunload() {
    this.app.workspace.detachLeavesOfType(CHAT_VIEW_TYPE);
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

  async loadSettings() {
    const data = await this.loadData();
    this.settings = { ...DEFAULT_CONFIG, ...data };
  }

  async saveSettings() {
    await this.saveData(this.settings);
  }

  async startSidecar() {
    if (this.sidecar) {
      new Notice("AI backend is already running");
      return;
    }
    this.sidecar = new SidecarManager(this.settings);
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
