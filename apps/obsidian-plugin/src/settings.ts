import { App, Notice, PluginSettingTab, Setting } from "obsidian";
import type AILearningAgentPlugin from "./main";
import type { ILLMProvider } from "@ai-tutor/shared-types";
import { DEFAULT_PROVIDER } from "@ai-tutor/shared-types";

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

    // ─── Vault ───
    containerEl.createEl("h3", { text: "Vault" });
    const vaultPath = (this.app.vault.adapter as unknown as { basePath?: string }).basePath || "";
    new Setting(containerEl)
      .setName("Vault path")
      .setDesc(`Auto-detected from Obsidian: ${vaultPath}`)
      .addText((text) =>
        text
          .setPlaceholder(vaultPath || "Auto-detected")
          .setValue(vaultPath || this.plugin.settings.vaultPath)
          .onChange(async (value) => {
            this.plugin.settings.vaultPath = value;
            await this.plugin.saveSettings();
          }),
      )
      .addExtraButton((btn) =>
        btn.setIcon("reset").setTooltip("Auto-fill from Obsidian").onClick(async () => {
          const detected = (this.app.vault.adapter as unknown as { basePath?: string }).basePath || "";
          this.plugin.settings.vaultPath = detected;
          await this.plugin.saveSettings();
          this.display();
        }),
      );

    // ─── Providers ───
    containerEl.createEl("h3", { text: "LLM Providers" });

    const providersEl = containerEl.createDiv({ cls: "ai-settings-providers" });

    const renderProviders = () => {
      providersEl.empty();
      const providers = this.plugin.settings.providers || [];
      let idx = 0;

      for (const p of providers) {
        const card = providersEl.createDiv({ cls: "ai-settings-provider-card" });
        const header = card.createDiv({ cls: "ai-settings-provider-header" });
        header.createEl("strong", { text: p.name || `Provider ${idx + 1}` });

        new Setting(card)
          .setName("Provider name")
          .addText((t) =>
            t
              .setPlaceholder("DeepSeek")
              .setValue(p.name)
              .onChange(async (v) => {
                p.name = v;
                await this.plugin.saveSettings();
              }),
          );

        new Setting(card)
          .setName("Base URL")
          .setDesc("OpenAI-compatible endpoint")
          .addText((t) =>
            t
              .setPlaceholder("https://api.deepseek.com/v1")
              .setValue(p.baseUrl)
              .onChange(async (v) => {
                p.baseUrl = v;
                await this.plugin.saveSettings();
              }),
          );

        new Setting(card)
          .setName("API key")
          .addText((t) => {
            t.inputEl.type = "password";
            t.setPlaceholder("sk-...")
              .setValue(p.apiKey)
              .onChange(async (v) => {
                p.apiKey = v;
                await this.plugin.saveSettings();
              });
          });

        new Setting(card)
          .setName("Models")
          .setDesc(`Current: ${(p.models || []).join(", ") || "none"}`)
          .addButton((btn) =>
            btn.setButtonText("Fetch from API").onClick(async () => {
              const port = this.plugin.settings.server.port;
              try {
                const resp = await fetch(`http://127.0.0.1:${port}/api/models/fetch`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ provider_id: p.id }),
                });
                if (resp.ok) {
                  const data = await resp.json();
                  p.models = data.models;
                  await this.plugin.saveSettings();
                  this.display();
                }
              } catch {
                // server not running yet — silently skip
              }
            }),
          );

        new Setting(card).addButton((btn) =>
          btn.setButtonText("Remove provider").onClick(async () => {
            this.plugin.settings.providers = providers.filter((_, i) => i !== idx);
            await this.plugin.saveSettings();
            renderProviders();
          }),
        );

        idx++;
      }
    };

    renderProviders();

    new Setting(providersEl).addButton((btn) =>
      btn.setButtonText("Add Provider").onClick(async () => {
        const newId = `provider_${Date.now()}`;
        const p: ILLMProvider = { ...DEFAULT_PROVIDER, id: newId, name: `Provider ${(this.plugin.settings.providers.length || 0) + 1}` };
        this.plugin.settings.providers = [...(this.plugin.settings.providers || []), p];
        await this.plugin.saveSettings();
        renderProviders();
      }),
    );

    // ─── Active Provider ───
    const providerIds = (this.plugin.settings.providers || []).map((p) => p.id);
    const providerNames = (this.plugin.settings.providers || []).map((p) => p.name);
    if (providerIds.length > 0) {
      containerEl.createEl("h3", { text: "Active Provider" });
      new Setting(containerEl)
        .setName("Active provider")
        .setDesc("Which provider's API key is used for all requests. Change this if you have multiple providers.")
        .addDropdown((dd) => {
          for (let i = 0; i < providerIds.length; i++) {
            const pid = providerIds[i] || "";
            const pname = providerNames[i] || pid;
            dd.addOption(pid, pname);
          }
          dd.setValue(this.plugin.settings.activeProviderId || providerIds[0] || "deepseek");
          dd.onChange(async (v) => {
            this.plugin.settings.activeProviderId = v;
            await this.plugin.saveSettings();
          });
        });
    }

    // ─── Model Assignment ───
    containerEl.createEl("h3", { text: "Model Assignment" });
    const allModels = (this.plugin.settings.providers || []).flatMap((p) => p.models || []);

    new Setting(containerEl)
      .setName("Chat model")
      .setDesc("Model used for normal chat (non-Agent)")
      .addDropdown((dd) => {
        for (const m of allModels) dd.addOption(m, m);
        if (this.plugin.settings.activeChatModel) {
          dd.setValue(this.plugin.settings.activeChatModel);
        }
        dd.onChange(async (v) => {
          this.plugin.settings.activeChatModel = v;
          await this.plugin.saveSettings();
        });
      });

    new Setting(containerEl)
      .setName("Agent model")
      .setDesc("Model used for Agent tool calls (must support function calling)")
      .addDropdown((dd) => {
        for (const m of allModels) dd.addOption(m, m);
        if (this.plugin.settings.activeAgentModel) {
          dd.setValue(this.plugin.settings.activeAgentModel);
        }
        dd.onChange(async (v) => {
          this.plugin.settings.activeAgentModel = v;
          await this.plugin.saveSettings();
        });
      });

    // ─── Tool Permissions ───
    containerEl.createEl("h3", { text: "Tool Permissions" });
    new Setting(containerEl)
      .setName("Permission mode")
      .setDesc("Read-only: search/read/list only. Full: create/delete/move/OCR allowed.")
      .addDropdown((dd) => {
        dd.addOption("readonly", "Read-only (safe)");
        dd.addOption("full", "Full access");
        dd.setValue(this.plugin.settings.toolPermissions || "readonly");
        dd.onChange(async (v) => {
          this.plugin.settings.toolPermissions = v as "readonly" | "full";
          await this.plugin.saveSettings();
        });
      });

    // ─── Thinking Mode ───
    containerEl.createEl("h3", { text: "Reasoning (Thinking Mode)" });
    new Setting(containerEl)
      .setName("Enable thinking mode")
      .setDesc("DeepSeek V4 Pro/Flash will show its reasoning process before answering. Requires model that supports thinking.")
      .addToggle((toggle) => {
        toggle.setValue(this.plugin.settings.thinkingEnabled || false);
        toggle.onChange(async (v) => {
          this.plugin.settings.thinkingEnabled = v;
          await this.plugin.saveSettings();
        });
      });

    new Setting(containerEl)
      .setName("Reasoning effort")
      .setDesc("low/medium map to high. max only for deepseek-v4-pro.")
      .addDropdown((dd) => {
        dd.addOption("low", "low (fast)");
        dd.addOption("medium", "medium");
        dd.addOption("high", "high (deep, recommended)");
        dd.addOption("max", "max (strongest, V4 Pro only)");
        dd.setValue(this.plugin.settings.reasoningEffort || "high");
        dd.onChange(async (v) => {
          this.plugin.settings.reasoningEffort = v as "low" | "medium" | "high" | "max";
          await this.plugin.saveSettings();
        });
      });

    // ─── Server ───
    containerEl.createEl("h3", { text: "Server" });
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

    // ─── Web Search ───
    containerEl.createEl("h3", { text: "Web Search (Tavily)" });
    new Setting(containerEl)
      .setName("Enable web search")
      .setDesc("Let the AI search the internet for current information. Requires Tavily API key.")
      .addToggle((toggle) => {
        toggle.setValue(this.plugin.settings.webSearchEnabled || false);
        toggle.onChange(async (v) => {
          this.plugin.settings.webSearchEnabled = v;
          await this.plugin.saveSettings();
        });
      });

    new Setting(containerEl)
      .setName("Tavily API key")
      .setDesc("Get yours at https://tavily.com")
      .addText((t) => {
        t.inputEl.type = "password";
        t.setPlaceholder("tvly-...")
          .setValue(this.plugin.settings.tavilyApiKey || "")
          .onChange(async (v) => {
            this.plugin.settings.tavilyApiKey = v;
            await this.plugin.saveSettings();
          });
      });

    // Save & Restart button
    containerEl.createEl("div", { cls: "ai-settings-save-bar" }, (bar) => {
      const btn = bar.createEl("button", { cls: "mod-cta", text: "Save & Restart Backend" });
      btn.addEventListener("click", async () => {
        await this.plugin.saveSettings();
        await this.plugin.stopSidecar();
        try {
          await this.plugin.startSidecar();
          new Notice("Settings saved and backend restarted.");
        } catch (e) {
          new Notice(`Restart failed: ${e}`);
        }
      });
    });
  }
}
