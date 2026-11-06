import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// Logica-tests (node-env, geen DOM): de dragende, framework-onafhankelijke helpers.
// De "@/"-alias spiegelt tsconfig.paths zodat imports identiek zijn aan de app.
export default defineConfig({
  resolve: {
    alias: [
      { find: /^@\/(.*)$/, replacement: fileURLToPath(new URL("./$1", import.meta.url)) },
      // `server-only` gooit buiten een server-bundel; in de node-tests stubben we het naar een no-op
      // zodat server-only helpers (bv. lib/logger.ts) getest kunnen worden.
      { find: /^server-only$/, replacement: fileURLToPath(new URL("./test/stub-empty.ts", import.meta.url)) },
      // next-auth importeert deze zonder extensie, wat buiten een Next-bundel niet resolvet.
      // `proxy.gate.test.ts` draait de echte `proxy.ts`, en die laadt next-auth.
      { find: /^next\/(server|headers|navigation)$/, replacement: "next/$1.js" },
    ],
  },
  test: {
    environment: "node",
    include: ["**/*.test.ts"],
    exclude: ["node_modules", ".next"],
    server: { deps: { inline: ["next-auth"] } },
  },
});
