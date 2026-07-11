import type { Request, Response, NextFunction } from "express";
import * as client from "openid-client";

import { config } from "./config.js";

export type UserSession = {
  sub: string;
  email?: string;
  tenantId: string;
  accessToken: string;
};

declare module "express-session" {
  interface SessionData {
    user?: UserSession;
    oidcState?: string;
    oidcVerifier?: string;
  }
}

let oidcConfig: client.Configuration | null = null;

async function getOidcConfig(): Promise<client.Configuration> {
  if (!oidcConfig) {
    oidcConfig = await client.discovery(
      new URL(config.oidcIssuer),
      config.oidcClientId,
    );
  }
  return oidcConfig;
}

export async function startLogin(req: Request, res: Response): Promise<void> {
  if (config.authStub) {
    req.session.user = {
      sub: "dev-user",
      email: "dev@example.com",
      tenantId: config.defaultTenantId,
      accessToken: config.queryAccessToken,
    };
    res.redirect(config.webOrigin);
    return;
  }

  const oidc = await getOidcConfig();
  const verifier = client.randomPKCECodeVerifier();
  const challenge = await client.calculatePKCECodeChallenge(verifier);
  const state = client.randomState();
  req.session.oidcState = state;
  req.session.oidcVerifier = verifier;
  const redirectUri = `${req.protocol}://${req.get("host")}/auth/callback`;
  const url = client.buildAuthorizationUrl(oidc, {
    redirect_uri: redirectUri,
    scope: "openid profile email",
    code_challenge: challenge,
    code_challenge_method: "S256",
    state,
  });
  res.redirect(url.href);
}

export async function handleCallback(req: Request, res: Response): Promise<void> {
  if (config.authStub) {
    res.redirect(config.webOrigin);
    return;
  }

  const oidc = await getOidcConfig();
  const redirectUri = `${req.protocol}://${req.get("host")}/auth/callback`;
  const currentUrl = new URL(`${req.protocol}://${req.get("host")}${req.originalUrl}`);
  const tokens = await client.authorizationCodeGrant(oidc, currentUrl, {
    pkceCodeVerifier: req.session.oidcVerifier,
    expectedState: req.session.oidcState,
  });
  const claims = tokens.claims();
  const tenantId =
    (typeof claims?.tenant_id === "string" && claims.tenant_id) || config.defaultTenantId;
  req.session.user = {
    sub: String(claims?.sub ?? "unknown"),
    email: typeof claims?.email === "string" ? claims.email : undefined,
    tenantId,
    accessToken: tokens.access_token ?? config.queryAccessToken,
  };
  delete req.session.oidcState;
  delete req.session.oidcVerifier;
  res.redirect(config.webOrigin);
}

export function requireAuth(req: Request, res: Response, next: NextFunction): void {
  if (!req.session.user) {
    res.status(401).json({ code: "unauthorized", message: "Login required" });
    return;
  }
  next();
}

export function currentUser(req: Request): UserSession {
  if (!req.session.user) {
    throw new Error("missing session user");
  }
  return req.session.user;
}
