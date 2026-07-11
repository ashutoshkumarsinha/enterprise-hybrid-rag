import assert from "node:assert/strict";
import test from "node:test";

import express from "express";
import request from "node:http";

import { registerRoutes } from "../src/routes.js";

function withServer(
  handler: (port: number) => Promise<void>,
): Promise<void> {
  const app = express();
  registerRoutes(app);
  return new Promise((resolve, reject) => {
    const server = app.listen(0, () => {
      const address = server.address();
      if (!address || typeof address === "string") {
        reject(new Error("failed to bind test server"));
        return;
      }
      handler(address.port)
        .then(() => server.close(() => resolve()))
        .catch((error) => server.close(() => reject(error)));
    });
  });
}

function getJson(port: number, path: string): Promise<{ status: number; body: string }> {
  return new Promise((resolve, reject) => {
    const req = request.get(`http://127.0.0.1:${port}${path}`, (res) => {
      let body = "";
      res.on("data", (chunk) => {
        body += chunk;
      });
      res.on("end", () => resolve({ status: res.statusCode ?? 0, body }));
    });
    req.on("error", reject);
  });
}

test("GET /healthz returns mod-chat module id", async () => {
  await withServer(async (port) => {
    const response = await getJson(port, "/healthz");
    assert.equal(response.status, 200);
    const payload = JSON.parse(response.body);
    assert.equal(payload.module, "mod-chat-bff");
    assert.equal(payload.status, "ok");
  });
});
