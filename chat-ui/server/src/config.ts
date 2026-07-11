import "dotenv/config";

function bool(value: string | undefined, defaultValue: boolean): boolean {
  if (value === undefined || value === "") {
    return defaultValue;
  }
  return ["true", "1", "yes"].includes(value.toLowerCase());
}

export const config = {
  port: Number(process.env.BFF_PORT ?? "4000"),
  webOrigin: process.env.WEB_ORIGIN ?? "http://localhost:5173",
  queryBaseUrl: process.env.QUERY_BASE_URL ?? "http://localhost:8010",
  queryAccessToken: process.env.QUERY_ACCESS_TOKEN ?? process.env.MCP_ACCESS_TOKEN ?? "",
  authStub: bool(process.env.AUTH_STUB, true),
  oidcIssuer: process.env.OIDC_ISSUER ?? "http://localhost:8081/realms/hybrid-rag",
  oidcClientId: process.env.OIDC_CLIENT_ID ?? "mod-chat",
  sessionSecret: process.env.SESSION_SECRET ?? "dev-change-me",
  defaultTenantId: process.env.DEFAULT_TENANT_ID ?? "dev",
  defaultCollections: (process.env.DEFAULT_COLLECTIONS ?? "docs")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean),
};
