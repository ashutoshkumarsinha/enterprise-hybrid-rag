import { config } from "./config.js";

export class QueryClientError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly body: unknown,
  ) {
    super(message);
  }
}

function authHeaders(accessToken: string): HeadersInit {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }
  return headers;
}

export async function queryJson<T>(
  path: string,
  body: Record<string, unknown>,
  accessToken: string,
): Promise<T> {
  const response = await fetch(`${config.queryBaseUrl}${path}`, {
    method: "POST",
    headers: authHeaders(accessToken),
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new QueryClientError(`query ${path} failed`, response.status, payload);
  }
  return payload as T;
}

export async function proxyResearchStream(
  body: Record<string, unknown>,
  accessToken: string,
): Promise<Response> {
  const response = await fetch(`${config.queryBaseUrl}/research/stream`, {
    method: "POST",
    headers: authHeaders(accessToken),
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new QueryClientError("research stream failed", response.status, payload);
  }
  if (!response.body) {
    throw new QueryClientError("research stream missing body", 502, {});
  }
  return response;
}
