// Preload for oracle.mjs (node --import): lets Node's built-in type stripping (Node 22.18+/23.6+) load the
// pinned src/index.ts unbuilt. The source uses bundler-style extensionless relative imports
// (`export * from "./types"`), which Node's resolver rejects; this hook retries them with ".ts" and
// "/index.ts". Only resolution changes: the executed code is the pinned source file with types erased.
import { registerHooks } from "node:module";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";

registerHooks({
  resolve(specifier, context, nextResolve) {
    try {
      return nextResolve(specifier, context);
    } catch (err) {
      const relative = specifier.startsWith("./") || specifier.startsWith("../");
      const fromTs = typeof context.parentURL === "string" && context.parentURL.endsWith(".ts");
      if (err?.code !== "ERR_MODULE_NOT_FOUND" || !relative || !fromTs) throw err;
      for (const suffix of [".ts", "/index.ts"]) {
        const url = new URL(specifier + suffix, context.parentURL);
        if (existsSync(fileURLToPath(url))) return nextResolve(url.href, context);
      }
      throw err;
    }
  },
  load(url, context, nextLoad) {
    if (url.startsWith("file:") && url.endsWith(".ts")) return nextLoad(url, { ...context, format: "module-typescript" });
    return nextLoad(url, context);
  },
});
