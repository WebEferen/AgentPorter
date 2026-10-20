// AgentPorter parity harness for TypeScript and JavaScript ports, see knowledge/oracles/CONTRACT.md.
// Runs on Node 22.18+ or 23.6+ with native type stripping (older 22.x: node --experimental-strip-types):
//   node porter/harness.ts --workspace .porter --run <run> [--unit <unit>] [--bindings porter/bindings.ts]
// Only erasable TypeScript syntax is allowed here (no enums, namespaces or parameter properties).
import { existsSync, mkdirSync, readdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { performance } from "node:perf_hooks";
import vm from "node:vm";

export type CaseInput = { args?: unknown[]; kwargs?: Record<string, unknown>; init?: { args?: unknown[]; kwargs?: Record<string, unknown> } };
export type Binding = (args: any[], kwargs: Record<string, any>, input: CaseInput) => unknown;
export type Bindings = Record<string, Binding>;

type Outcome = { kind: "value"; value: unknown } | { kind: "error"; category: string; message: string };
type Case = { case: string; call: string; input?: CaseInput; expect: { kind: string } };

const DRIVER = "agentporter/knowledge/harnesses/typescript/harness.ts";
const MAX_DEPTH = 64;
const UNDEFINED_LANGUAGES = new Set(["javascript", "typescript"]);

class HarnessError extends Error {}

function canonical(v: unknown): string {
  if (Array.isArray(v)) return "[" + v.map(canonical).join(",") + "]";
  if (v && typeof v === "object") {
    const o = v as Record<string, unknown>;
    return "{" + Object.keys(o).sort().map((k) => JSON.stringify(k) + ":" + canonical(o[k])).join(",") + "}";
  }
  return JSON.stringify(v);
}

function serializeNumber(n: number): unknown {
  if (Number.isNaN(n)) return { $float: "nan" };
  if (n === Infinity) return { $float: "inf" };
  if (n === -Infinity) return { $float: "-inf" };
  if (Object.is(n, -0)) return { $float: "-0" };
  return n;
}

function typeName(v: any): string {
  return (v && v.constructor && v.constructor.name) || typeof v;
}

function errorName(e: any): string {
  const ctor = e && e.constructor && e.constructor.name;
  if (ctor && ctor !== "Error") return ctor;
  return (e && e.name) || "Error";
}

export function serialize(value: any, depth = 0): unknown {
  if (depth > MAX_DEPTH) return { $type: typeName(value), truncated: true };
  const d = depth + 1;
  if (value === null || value === undefined) return null;
  switch (typeof value) {
    case "boolean":
    case "string":
      return value;
    case "number":
      return serializeNumber(value);
    case "bigint":
      return value >= -(2n ** 53n) && value <= 2n ** 53n ? Number(value) : { $int: value.toString() };
    case "symbol":
      return { $type: "symbol", description: value.description ?? null };
    case "function":
      return { $type: "function", name: value.name || null };
  }
  if (Array.isArray(value)) return value.map((v) => serialize(v, d));
  if (value instanceof Uint8Array) return { $bytes: Buffer.from(value.buffer, value.byteOffset, value.byteLength).toString("base64") };
  if (value instanceof ArrayBuffer) return { $bytes: Buffer.from(value).toString("base64") };
  if (ArrayBuffer.isView(value)) return Array.from(value as unknown as ArrayLike<number>, (v) => serialize(v, d));
  if (value instanceof Date) return { $datetime: Number.isNaN(value.getTime()) ? "Invalid Date" : value.toISOString() };
  if (value instanceof RegExp) return { $type: "RegExp", flags: value.flags, source: value.source };
  if (value instanceof Set) {
    const items = [...value].map((v) => serialize(v, d));
    return { $set: items.sort((a, b) => (canonical(a) < canonical(b) ? -1 : canonical(a) > canonical(b) ? 1 : 0)) };
  }
  if (value instanceof Map) {
    const entries = [...value.entries()];
    if (entries.every(([k]) => typeof k === "string")) return Object.fromEntries(entries.map(([k, v]) => [k, serialize(v, d)]));
    return { $map: entries.map(([k, v]) => [serialize(k, d), serialize(v, d)]) };
  }
  if (value instanceof Error) return { $type: errorName(value), message: value.message };
  const proto = Object.getPrototypeOf(value);
  if (proto === null || proto === Object.prototype) {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value)) if (v !== undefined) out[k] = serialize(v, d);
    return out;
  }
  const out: Record<string, unknown> = { $type: typeName(value) };
  for (const k of Object.keys(value).filter((k) => !k.startsWith("_") && !k.startsWith("#")).sort()) {
    if (value[k] !== undefined) out[k] = serialize(value[k], d);
  }
  return out;
}

export function decode(v: any): any {
  if (Array.isArray(v)) return v.map(decode);
  if (!v || typeof v !== "object") return v;
  const keys = Object.keys(v);
  if (keys.length === 1) {
    const raw = v[keys[0]];
    switch (keys[0]) {
      case "$float":
        return ({ nan: NaN, inf: Infinity, "-inf": -Infinity, "-0": -0 } as Record<string, number>)[raw];
      case "$int":
        return BigInt(raw);
      case "$bytes":
        return new Uint8Array(Buffer.from(raw, "base64"));
      case "$datetime":
        return new Date(raw);
      case "$decimal":
        return raw;
      case "$set":
        return new Set(raw.map(decode));
      case "$map":
        return new Map(raw.map(([k, val]: [unknown, unknown]) => [decode(k), decode(val)]));
      case "$undefined":
        return undefined;
    }
  }
  return Object.fromEntries(Object.entries(v).map(([k, val]) => [k, decode(val)]));
}

async function runCase(binding: Binding, input: CaseInput, timeoutMs: number): Promise<unknown> {
  const decoded = decode(input);
  const args = decoded.args ?? [];
  const kwargs = decoded.kwargs ?? {};
  // vm's timeout interrupts synchronous infinite loops even in functions from this realm.
  let result: any = vm.runInNewContext("fn()", { fn: () => binding(args, kwargs, decoded) }, { timeout: timeoutMs });
  if (result && typeof result.then === "function") {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const timeout = new Promise((_, reject) => {
      timer = setTimeout(() => reject(Object.assign(new Error(`timed out after ${timeoutMs / 1000}s`), { porterTimeout: true })), timeoutMs);
    });
    try {
      result = await Promise.race([result, timeout]);
    } finally {
      clearTimeout(timer);
    }
  }
  return result;
}

function errorOutcome(err: any): Outcome {
  if (err && (err.porterTimeout || err.code === "ERR_SCRIPT_EXECUTION_TIMEOUT")) {
    return { kind: "error", category: "timeout", message: String(err.message) };
  }
  if (err instanceof Error || (err && typeof err === "object" && "message" in err)) {
    return { kind: "error", category: errorName(err), message: String(err.message) };
  }
  return { kind: "error", category: "NonError", message: String(err) };
}

function parseArgs(argv: string[]) {
  const here = dirname(fileURLToPath(import.meta.url));
  const out = { workspace: ".porter", unit: [] as string[], run: "", bindings: join(here, "bindings.ts"), timeout: 10 };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = () => {
      if (i + 1 >= argv.length) throw new HarnessError(`${a} needs a value`);
      return argv[++i];
    };
    if (a === "--workspace") out.workspace = next();
    else if (a === "--unit") out.unit.push(next());
    else if (a === "--run") out.run = next();
    else if (a === "--bindings") out.bindings = resolve(next());
    else if (a === "--timeout") out.timeout = Number(next());
    else throw new HarnessError(`unknown argument ${a}`);
  }
  if (!out.run) out.run = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d+Z$/, "Z");
  return out;
}

function writeJson(path: string, data: unknown): void {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path + ".tmp", JSON.stringify(data, null, 2) + "\n");
  renameSync(path + ".tmp", path);
}

async function main(): Promise<number> {
  const opts = parseArgs(process.argv.slice(2));
  const ws = resolve(opts.workspace);
  const fixturesDir = join(ws, "fixtures");
  if (!existsSync(opts.bindings)) throw new HarnessError(`no bindings file at ${opts.bindings}`);
  const mod = await import(pathToFileURL(opts.bindings).href);
  const bindings: Bindings | undefined = mod.bindings ?? mod.default;
  if (!bindings || typeof bindings !== "object") throw new HarnessError(`${opts.bindings} must export const bindings`);
  const units = opts.unit.length
    ? opts.unit
    : readdirSync(fixturesDir, { withFileTypes: true }).filter((d) => d.isDirectory()).map((d) => d.name).sort();
  if (!units.length) throw new HarnessError(`no fixtures under ${fixturesDir}`);
  let missing = 0;
  for (const unit of units) {
    const dir = join(fixturesDir, unit);
    if (!existsSync(dir)) throw new HarnessError(`no fixtures for unit ${unit}`);
    const startedAt = new Date().toISOString().replace(/\.\d+Z$/, "Z");
    const results: { case: string; actual: Outcome; durationMs: number }[] = [];
    for (const file of readdirSync(dir).filter((f) => f.endsWith(".json")).sort()) {
      const fixture = JSON.parse(readFileSync(join(dir, file), "utf8"));
      const keepUndefined = UNDEFINED_LANGUAGES.has(fixture.oracle?.language);
      for (const c of fixture.cases as Case[]) {
        if (c.expect.kind === "cli") continue;
        const binding = bindings[c.call];
        if (!binding) {
          missing++;
          results.push({ case: c.case, actual: { kind: "error", category: "MissingBinding", message: `no binding for ${c.call}` }, durationMs: 0 });
          continue;
        }
        const started = performance.now();
        let actual: Outcome;
        try {
          const value = await runCase(binding, c.input ?? {}, opts.timeout * 1000);
          actual = { kind: "value", value: value === undefined && keepUndefined ? { $undefined: true } : serialize(value) };
        } catch (err) {
          actual = errorOutcome(err);
        }
        results.push({ case: c.case, actual, durationMs: Math.round((performance.now() - started) * 10000) / 10000 });
      }
    }
    writeJson(join(ws, "runs", opts.run, unit + ".json"), {
      schema: 1,
      unit,
      runner: { language: "typescript", driver: DRIVER, runtime: `node ${process.versions.node}` },
      startedAt,
      results,
    });
    const errors = results.filter((r) => r.actual.kind === "error").length;
    console.log(`${unit}: ran ${results.length} cases (${errors} errors) -> runs/${opts.run}/${unit}.json`);
  }
  if (missing) console.error(`harness: ${missing} case(s) have no binding (recorded as MissingBinding)`);
  return 0;
}

main().then(
  (code) => process.exit(code),
  (err) => {
    process.stderr.write(`harness: ${err instanceof HarnessError ? err.message : err?.stack || err}\n`);
    process.exit(2);
  },
);
