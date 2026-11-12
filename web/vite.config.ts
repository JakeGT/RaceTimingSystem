// SPDX-FileCopyrightText: 2026 Race Timing System contributors
// SPDX-License-Identifier: AGPL-3.0-or-later
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// API_PROXY_TARGET lets docker-compose point the dev proxy at the server container.
const apiTarget = process.env.API_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: { "/api": apiTarget, "/admin": apiTarget, "/static": apiTarget },
  },
});
