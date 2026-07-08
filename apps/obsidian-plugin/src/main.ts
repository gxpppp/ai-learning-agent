import { Plugin, Notice } from "obsidian";
import type { IAppConfig, ILLMConfig } from "@ai-tutor/shared-types";
import { DEFAULT_CONFIG } from "@ai-tutor/shared-types";
import { AISettingsTab } from "./settings";
import { SidecarManager } from "./sidecar";

export default class AILearningAgentPlugin extends Plugin {
  settings: IAppConfig = DEFAULT_CONFIG;
  sidecar: SidecarManager | null = null;

  async onload() {
    await this.loadSettings();

    this.addSettingTab(new AISettingsTab(this.app, this));

    this.addCommand({
      id: "open-ai-chat",
      name: "Open AI chat panel",
      callback: () => {
        new Notice("AI Chat: coming in Phase 1");
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
    await this.stopSidecar();
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
