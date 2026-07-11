import { useEffect, useState } from "react";

type ScopeBarProps = {
  collections: string[];
  value: string;
  onChange: (collectionId: string) => void;
};

export function ScopeBar({ collections, value, onChange }: ScopeBarProps) {
  return (
    <label className="scope-bar">
      Collection
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {collections.map((collectionId) => (
          <option key={collectionId} value={collectionId}>
            {collectionId}
          </option>
        ))}
      </select>
    </label>
  );
}

type ChatViewportProps = {
  output: string;
  onSend: (message: string) => Promise<void>;
  disabled?: boolean;
};

export function ChatViewport({ output, onSend, disabled }: ChatViewportProps) {
  const [draft, setDraft] = useState("");

  return (
    <section className="chat-viewport">
      <pre className="chat-output">{output || "Ask a question about your indexed documents."}</pre>
      <form
        className="chat-form"
        onSubmit={(event) => {
          event.preventDefault();
          const message = draft.trim();
          if (!message || disabled) {
            return;
          }
          void onSend(message);
          setDraft("");
        }}
      >
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Ask a research question..."
          disabled={disabled}
        />
        <button type="submit" disabled={disabled}>
          Send
        </button>
      </form>
    </section>
  );
}

export function useAsync<T>(loader: () => Promise<T>, deps: unknown[] = []) {
  const [value, setValue] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    loader()
      .then((result) => {
        if (active) {
          setValue(result);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (active) {
          setError(err instanceof Error ? err.message : "load failed");
        }
      });
    return () => {
      active = false;
    };
  }, deps);

  return { value, error };
}
