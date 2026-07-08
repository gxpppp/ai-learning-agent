export interface ILLMProvider {
  id: string;
  name: string;
  baseUrl: string;
  apiKey: string;
  models: string[];
}

export interface IServerConfig {
  port: number;
  host: string;
}

export interface IAppConfig {
  vaultPath: string;
  providers: ILLMProvider[];
  activeProviderId: string;
  activeChatModel: string;
  activeAgentModel: string;
  server: IServerConfig;
  toolPermissions: "readonly" | "full";
}

export const DEFAULT_PROVIDER: ILLMProvider = {
  id: "deepseek",
  name: "DeepSeek",
  baseUrl: "https://api.deepseek.com/v1",
  apiKey: "",
  models: ["deepseek-chat"],
};

export const DEFAULT_CONFIG: IAppConfig = {
  vaultPath: "",
  providers: [DEFAULT_PROVIDER],
  activeProviderId: "deepseek",
  activeChatModel: "deepseek-chat",
  activeAgentModel: "deepseek-chat",
  server: {
    port: 8765,
    host: "127.0.0.1",
  },
  toolPermissions: "readonly",
};
