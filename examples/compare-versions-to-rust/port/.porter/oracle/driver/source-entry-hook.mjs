// Loaded with `node --import` before the unmodified oracle.mjs. The pinned checkout has no lib/ (build
// output is not in the repo), so the package entry points (package.json main and module) are redirected
// to the tsc build of the same commit under .porter/oracle/build/lib/esm. Nothing is written to the source.
import { registerHooks } from "node:module";
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ws = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const config = JSON.parse(readFileSync(join(ws, "config.json"), "utf8"));
const sourceRoot = resolve(config.source.path, config.source.subpath || ".");
const buildEntry = pathToFileURL(join(ws, "oracle", "build", "lib", "esm", "index.js")).href;
const entries = new Set([join(sourceRoot, "lib", "umd", "index.js"), join(sourceRoot, "lib", "esm", "index.js")]);

registerHooks({
  resolve(specifier, context, nextResolve) {
    const path = specifier.startsWith("file:") ? fileURLToPath(specifier) : specifier.startsWith("/") ? specifier : null;
    if (path && entries.has(path)) return { url: buildEntry, format: "module", shortCircuit: true };
    return nextResolve(specifier, context);
  },
});
