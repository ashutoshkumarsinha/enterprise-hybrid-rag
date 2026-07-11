import { useMemo, useState } from "react";

import { createThread, getMe, listCollections, streamMessage } from "./api";
import { ChatViewport, ScopeBar, useAsync } from "./components";

export function App() {
  const me = useAsync(() => getMe(), []);
  const collections = useAsync(() => listCollections(), [me.value?.tenant_id]);
  const collectionIds = useMemo(
    () => (collections.value ?? []).map((item) => item.collection_id),
    [collections.value],
  );
  const [collectionId, setCollectionId] = useState("docs");
  const [threadId, setThreadId] = useState<string | null>(null);
  const [output, setOutput] = useState("");
  const [busy, setBusy] = useState(false);

  if (me.error) {
    return (
      <main className="app">
        <h1>Hybrid RAG Chat</h1>
        <p className="error">Login required.</p>
        <a className="button" href="/auth/login">
          Sign in
        </a>
      </main>
    );
  }

  if (!me.value) {
    return <main className="app">Loading session...</main>;
  }

  return (
    <main className="app">
      <header>
        <h1>Hybrid RAG Chat</h1>
        <p className="meta">
          {me.value.email ?? me.value.sub} · tenant {me.value.tenant_id}
        </p>
      </header>
      <ScopeBar
        collections={collectionIds.length ? collectionIds : [collectionId]}
        value={collectionId}
        onChange={setCollectionId}
      />
      <ChatViewport
        output={output}
        disabled={busy}
        onSend={async (message) => {
          setBusy(true);
          setOutput("");
          try {
            const activeThread =
              threadId ?? (await createThread(collectionId));
            if (!threadId) {
              setThreadId(activeThread);
            }
            await streamMessage(activeThread, message, collectionId, (chunk) => {
              setOutput((current) => current + chunk);
            });
          } catch (error) {
            setOutput(error instanceof Error ? error.message : "stream failed");
          } finally {
            setBusy(false);
          }
        }}
      />
    </main>
  );
}
