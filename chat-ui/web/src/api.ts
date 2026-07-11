const baseUrl = "";

export type UserProfile = {
  sub: string;
  email?: string;
  tenant_id: string;
};

export type Collection = {
  tenant_id: string;
  collection_id: string;
};

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    credentials: "include",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    throw new Error(`request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function getMe(): Promise<UserProfile> {
  return fetchJson<UserProfile>("/auth/me");
}

export async function listCollections(): Promise<Collection[]> {
  const payload = await fetchJson<{ collections: Collection[] }>("/api/collections");
  return payload.collections;
}

export async function createThread(collectionId: string): Promise<string> {
  const payload = await fetchJson<{ thread_id: string }>("/api/threads", {
    method: "POST",
    body: JSON.stringify({ collection_id: collectionId }),
  });
  return payload.thread_id;
}

export async function streamMessage(
  threadId: string,
  content: string,
  collectionId: string,
  onChunk: (chunk: string) => void,
): Promise<void> {
  const response = await fetch(`${baseUrl}/api/threads/${threadId}/messages`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, collection_id: collectionId }),
  });
  if (!response.ok || !response.body) {
    throw new Error(`stream failed: ${response.status}`);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      return;
    }
    onChunk(decoder.decode(value));
  }
}
