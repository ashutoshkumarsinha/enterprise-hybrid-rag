import type { Express, Request, Response } from "express";

import { currentUser, requireAuth } from "./auth.js";
import { config } from "./config.js";
import { QueryClientError, proxyResearchStream, queryJson } from "./queryClient.js";

type ThreadRecord = {
  threadId: string;
  sessionId: string;
  tenantId: string;
  collectionId?: string;
  documentId?: string;
  versionId?: string;
};

const threads = new Map<string, ThreadRecord>();

export function registerRoutes(app: Express): void {
  app.get("/healthz", (_req, res) => {
    res.json({ status: "ok", module: "mod-chat-bff", auth_stub: config.authStub });
  });

  app.get("/auth/me", requireAuth, (req, res) => {
    const user = currentUser(req);
    res.json({
      sub: user.sub,
      email: user.email,
      tenant_id: user.tenantId,
    });
  });

  app.post("/auth/logout", (req, res) => {
    req.session.destroy(() => {
      res.json({ status: "ok" });
    });
  });

  app.get("/api/collections", requireAuth, async (req, res) => {
    const user = currentUser(req);
    try {
      const result = await queryJson<{ documents?: Array<{ collection_id: string }> }>(
        "/mcp/tools/list_indexed_documents",
        { tenant_id: user.tenantId, limit: 200 },
        user.accessToken || config.queryAccessToken,
      );
      const ids = new Set<string>(config.defaultCollections);
      for (const doc of result.documents ?? []) {
        if (doc.collection_id) {
          ids.add(doc.collection_id);
        }
      }
      res.json({
        collections: [...ids].map((collection_id) => ({
          tenant_id: user.tenantId,
          collection_id,
        })),
      });
    } catch (error) {
      res.json({
        collections: config.defaultCollections.map((collection_id) => ({
          tenant_id: user.tenantId,
          collection_id,
        })),
      });
    }
  });

  app.get("/api/collections/:collectionId/documents", requireAuth, async (req, res) => {
    const user = currentUser(req);
    const payload = await queryJson(
      "/mcp/tools/list_indexed_documents",
      {
        tenant_id: user.tenantId,
        collection_id: req.params.collectionId,
        limit: Number(req.query.limit ?? 50),
      },
      user.accessToken || config.queryAccessToken,
    );
    res.json(payload);
  });

  app.post("/api/threads", requireAuth, async (req, res) => {
    const user = currentUser(req);
    const body = (req.body ?? {}) as Record<string, string>;
    const session = await queryJson<{ session_id: string }>(
      "/mcp/tools/create_conversation_session",
      {
        tenant_id: user.tenantId,
        collection_id: body.collection_id,
        document_id: body.document_id,
        version_id: body.version_id,
      },
      user.accessToken || config.queryAccessToken,
    );
    const threadId = session.session_id;
    threads.set(threadId, {
      threadId,
      sessionId: session.session_id,
      tenantId: user.tenantId,
      collectionId: body.collection_id,
      documentId: body.document_id,
      versionId: body.version_id,
    });
    res.status(201).json({ thread_id: threadId, session_id: session.session_id });
  });

  app.get("/api/threads/:threadId/messages", requireAuth, async (req, res) => {
    const user = currentUser(req);
    const thread = threads.get(req.params.threadId);
    if (!thread) {
      res.status(404).json({ code: "not_found" });
      return;
    }
    const history = await queryJson(
      "/mcp/tools/get_conversation_history",
      { session_id: thread.sessionId, limit: Number(req.query.limit ?? 50) },
      user.accessToken || config.queryAccessToken,
    );
    res.json(history);
  });

  app.post("/api/threads/:threadId/messages", requireAuth, async (req, res) => {
    const user = currentUser(req);
    const thread = threads.get(req.params.threadId);
    if (!thread) {
      res.status(404).json({ code: "not_found" });
      return;
    }
    const body = (req.body ?? {}) as Record<string, unknown>;
    const query = String(body.content ?? body.query ?? "");
    const upstream = await proxyResearchStream(
      {
        query,
        tenant_id: user.tenantId,
        session_id: thread.sessionId,
        collection_id: body.collection_id ?? thread.collectionId,
        document_id: body.document_id ?? thread.documentId,
        version_id: body.version_id ?? thread.versionId,
      },
      user.accessToken || config.queryAccessToken,
    );
    res.setHeader("Content-Type", "text/event-stream");
    res.setHeader("Cache-Control", "no-cache");
    res.setHeader("Connection", "keep-alive");
    const reader = upstream.body!.getReader();
    const pump = async () => {
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          res.end();
          return;
        }
        res.write(value);
      }
    };
    pump().catch(() => res.end());
  });

  app.use((error: unknown, _req: Request, res: Response, _next: () => void) => {
    if (error instanceof QueryClientError) {
      res.status(error.status).json(error.body);
      return;
    }
    res.status(500).json({ code: "internal_error" });
  });
}
