import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    // the session service (su-eng-02) is the API authority; same-origin in dev.
    // sib-01 adds /worlds (the decade picker) and /runs (bundle bytes) —
    // same authority, same port.
    proxy: {
      "/sessions": "http://127.0.0.1:8787",
      "/worlds": "http://127.0.0.1:8787",
      "/runs": "http://127.0.0.1:8787",
    },
  },
  test: {
    environment: "happy-dom",
  },
});
