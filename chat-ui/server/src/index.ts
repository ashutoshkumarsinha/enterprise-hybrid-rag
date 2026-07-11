import cookieParser from "cookie-parser";
import cors from "cors";
import express from "express";
import session from "express-session";

import { handleCallback, startLogin } from "./auth.js";
import { config } from "./config.js";
import { registerRoutes } from "./routes.js";

const app = express();

app.use(
  cors({
    origin: config.webOrigin,
    credentials: true,
  }),
);
app.use(cookieParser());
app.use(express.json());
app.use(
  session({
    secret: config.sessionSecret,
    resave: false,
    saveUninitialized: false,
    cookie: {
      httpOnly: true,
      sameSite: "lax",
      secure: false,
      maxAge: 24 * 60 * 60 * 1000,
    },
  }),
);

app.get("/auth/login", (req, res) => {
  void startLogin(req, res);
});
app.get("/auth/callback", (req, res) => {
  void handleCallback(req, res);
});

registerRoutes(app);

app.listen(config.port, () => {
  console.log(`mod-chat BFF listening on :${config.port}`);
});
