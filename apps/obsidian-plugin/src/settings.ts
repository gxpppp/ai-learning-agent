import { type App, PluginSettingTab, Setting } from "obsidian";
import type AILearningAgentPlugin from "./main";

export class AISettingsTab extends PluginSettingTab {
  plugin: AILearningAgentPlugin;

  constructor(app: App, plugin: AILearningAgentPlugin) {
    super(app, plugin);
    this.plugin = plugin;
  }

  display(): void {
    const { containerEl } = this;
    containerEl.empty();

    containerEl.createEl("h2", { text: "AI Learning Agent Settings" });

    new Setting(containerEl)
      .setName("Vault path")
      .setDesc("Absolute path to your Obsidian vault")
      .addText((text) =>
        text
          .setPlaceholder("/path/to/vault")
          .setValue(this.plugin.settings.vaultPath)
          .onChange(async (value) => {
            this.plugin.settings.vaultPath = value;
            await this.plugin.saveSettings();
          }),
      );

    containerEl.createEl("h3", { text: "LLM Configuration" });

    new Setting(containerEl)
      .setName("API base URL")
      .setDesc("OpenAI-compatible API base URL (e.g., https://api.deepseek.com/v1)")
      .addText((text) =>
        text
          .setPlaceholder("https://api.deepseek.com/v1")
          .setValue(this.plugin.settings.llm.baseUrl)
          .onChange(async (value) => {
            this.plugin.settings.llm.baseUrl = value;
            await this.plugin.saveSettings();
          }),
      );

    new Setting(containerEl)
      .setName("API key")
      .setDesc("Your API key (stored locally, never sent anywhere except to the LLM provider)")
      .addText((text) => {
        text.inputEl.type = "password";
        text
          .setPlaceholder("sk-...")
          .setValue(this.plugin.settings.llm.apiKey)
          .onChange(async (value) => {
            this.plugin.settings.llm.apiKey = value;
            await this.plugin.saveSettings();
          });
      });

    new Setting(containerEl)
      .setName("Model")
      .setDesc("Model name (e.g., deepseek-chat, gpt-4o, llama3.1:8b)")
      .addText((text) =>
        text
          .setPlaceholder("deepseek-chat")
          .setValue(this.plugin.settings.llm.model)
          .onChange(async (value) => {
            this.plugin.settings.llm.model = value;
            await this.plugin.saveSettings();
          }),
      );

    containerEl.createEl("h3", { text: "Server Configuration" });

    new Setting(containerEl)
      .setName("Port")
      .setDesc("Backend server port (restart required)")
      .addText((text) =>
        text
          .setPlaceholder("8765")
          .setValue(String(this.plugin.settings.server.port))
          .onChange(async (value) => {
            const port = Number.parseInt(value, 10);
            if (!Number.isNaN(port)) {
              this.plugin.settings.server.port = port;
              await this.plugin.saveSettings();
            }
          }),
      );
  }
}
