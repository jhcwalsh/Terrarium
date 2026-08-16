import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    // the session service (su-eng-02) is the API authority; same-origin in dev.
    // sib-01 adds /worlds (the decade picker) and /runs (bundle bytes);
    // su-app-06 adds /book (GET /book/default, BookEntry's pre-fill) —
    // same authority, same port (8787 — see the serve-port-8787 gotcha).
    proxy: {
      "/sessions": "http://127.0.0.1:8787",
      "/worlds": "http://127.0.0.1:8787",
      "/runs": "http://127.0.0.1:8787",
      "/book": "http://127.0.0.1:8787",
    },
  },
  test: {
    environment: "happy-dom",
  },
});
