import { type ChildProcess, execSync, spawn } from "node:child_process";
import * as path from "node:path";
import { Notice } from "obsidian";
import type { IAppConfig } from "@ai-tutor/shared-types";

export class SidecarManager {
  private process: ChildProcess | null = null;
  private config: IAppConfig;
  private vaultPath: string;

  constructor(config: IAppConfig, vaultPath: string) {
    this.config = config;
    this.vaultPath = vaultPath;
  }

  async start(): Promise<void> {
    const projectRoot = this.getProjectRoot();

    // Startup wizard: verify prerequisites
    const pyprojectPath = path.join(projectRoot, "pyproject.toml");
    if (!this.fileExists(pyprojectPath)) {
      new Notice(
        "AI Learning Agent: Backend not installed. Run install.ps1 first. " +
          `Expected backend at: ${projectRoot}`,
        0,
      );
      throw new Error(`Backend not found at ${projectRoot}`);
    }

    const venvPath = path.join(projectRoot, ".venv");
    if (!this.dirExists(venvPath)) {
      new Notice("AI Learning Agent: Installing Python dependencies (uv sync)...");
      try {
        this.runSync("uv", ["sync"], { cwd: projectRoot });
        new Notice("AI Learning Agent: Dependencies installed.");
      } catch {
        new Notice("AI Learning Agent: Failed to install dependencies. Is uv installed? Run `uv sync` manually in backend/.");
        throw new Error("uv sync failed");
      }
    }

    const firstProvider = this.config.providers?.[0];
    if (!firstProvider || !firstProvider.apiKey) {
      new Notice(
        "AI Learning Agent: No API key configured. Open Settings → add a Provider with an API key.",
        0,
      );
      throw new Error("No provider with API key configured");
    }

    if (!this.config.vaultPath) {
      new Notice("AI Learning Agent: Vault path not set. Open Settings → AI Learning Agent.", 0);
      throw new Error("Vault path not configured");
    }

    // Kill any zombie process on our port before starting
    const { port, host } = this.config.server;
    this._killStaleProcess(port);

    // Start backend
    const providersJson = JSON.stringify(this.config.providers || []);
    const env = {
      ...process.env,
      PROVIDERS_JSON: providersJson,
      ACTIVE_PROVIDER_ID: this.config.activeProviderId || "deepseek",
      ACTIVE_CHAT_MODEL: this.config.activeChatModel || "deepseek-chat",
      ACTIVE_AGENT_MODEL: this.config.activeAgentModel || "deepseek-chat",
      LLM_BASE_URL: this.config.providers?.[0]?.baseUrl || "https://api.deepseek.com/v1",
      LLM_API_KEY: this.config.providers?.[0]?.apiKey || "",
      LLM_MODEL: this.config.activeChatModel || "deepseek-chat",
      TOOL_PERMISSIONS: this.config.toolPermissions || "readonly",
      REASONING_ENABLED: String(this.config.thinkingEnabled || false),
      REASONING_EFFORT: this.config.reasoningEffort || "high",
      EMBEDDING_MODEL: path.join(this.getProjectRoot(), "models", "bge-m3"),
      SERVER_PORT: String(port),
      SERVER_HOST: host,
      OBSIDIAN_VAULT_PATH: this.vaultPath,
      TAVILY_API_KEY: this.config.tavilyApiKey || "",
      WEB_SEARCH_ENABLED: String(this.config.webSearchEnabled || false),
    };

    const pythonExe =
      process.platform === "win32"
        ? path.join(projectRoot, ".venv", "Scripts", "python.exe")
        : path.join(projectRoot, ".venv", "bin", "python");

    const proc = spawn(
      pythonExe,
      ["-m", "uvicorn", "app.main:app", "--host", host, "--port", String(port)],
      {
        env,
        cwd: this.getSourceDir(),
        stdio: ["ignore", "pipe", "pipe"],
      },
    );
    this.process = proc;

    proc.stdout?.on("data", (data: Buffer) => {
      console.log(`[backend] ${data.toString().trim()}`);
    });

    proc.stderr?.on("data", (data: Buffer) => {
      console.log(`[backend] ${data.toString().trim()}`);
    });

    proc.on("error", (err: Error) => {
      console.error("[sidecar] process error:", err.message);
      this.process = null;
    });

    proc.on("close", (code: number | null) => {
      console.log(`[sidecar] process exited with code ${code}`);
      this.process = null;
    });

    await this.waitForHealth(30000);
  }

  async stop(): Promise<void> {
    const proc = this.process;
    if (!proc || !proc.pid) return;

    return new Promise((resolve) => {
      proc.on("close", () => {
        this.process = null;
        resolve();
      });

      if (process.platform === "win32") {
        try {
          execSync(`taskkill /pid ${proc.pid} /T /F`);
        } catch {
          proc.kill?.("SIGTERM");
        }
      } else {
        try {
          execSync(`pkill -P ${proc.pid}`);
        } catch {
          // children may already be dead
        }
        proc.kill?.("SIGTERM");
      }
    });
  }

  private async waitForHealth(timeoutMs: number): Promise<void> {
    const start = Date.now();
    const port = this.config.server.port;
    const host = this.config.server.host;

    while (Date.now() - start < timeoutMs) {
      try {
        const resp = await fetch(`http://${host}:${port}/api/health`);
        if (resp.ok) return;
      } catch {
        // server not ready yet
      }
      await new Promise((r) => setTimeout(r, 500));
    }

    throw new Error(`Backend did not become healthy within ${timeoutMs}ms`);
  }

  private getProjectRoot(): string {
    return path.join(this.vaultPath, ".obsidian", "plugins", "ai-learning-agent", "backend");
  }

  private getSourceDir(): string {
    return path.join(this.getProjectRoot(), "src");
  }

  private fileExists(p: string): boolean {
    try {
      const fs = require("node:fs");
      return fs.existsSync(p) && fs.statSync(p).isFile();
    } catch {
      return false;
    }
  }

  private dirExists(p: string): boolean {
    try {
      const fs = require("node:fs");
      return fs.existsSync(p) && fs.statSync(p).isDirectory();
    } catch {
      return false;
    }
  }

  private runSync(cmd: string, args: string[], opts: Record<string, unknown>): void {
    execSync(`${cmd} ${args.join(" ")}`, { stdio: "inherit", ...opts });
  }
}

// Standalone function (not a class method) to avoid esbuild method TDZ
function _killStaleProcess(port: number): void {
  try {
    if (process.platform === "win32") {
      const out = execSync(
        `netstat -ano | findstr ":${port}" | findstr "LISTENING"`,
        { encoding: "utf-8", timeout: 3000 },
      );
      for (const line of out.trim().split("\n")) {
        const parts = line.trim().split(/\s+/);
        const pid = parts[parts.length - 1];
        if (pid && /^\d+$/.test(pid)) {
          execSync(`taskkill /PID ${pid} /F`, { timeout: 3000 });
          return;
        }
      }
    } else {
      execSync(`lsof -ti:${port} | xargs kill -9`, { timeout: 3000 });
    }
  } catch {
    // port is free
  }
}
