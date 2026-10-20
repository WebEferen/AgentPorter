#!/usr/bin/env node
// AgentPorter oracle driver for JavaScript sources (see knowledge/oracles/CONTRACT.md). Node 18+, no dependencies.
import { createRequire } from "node:module";
import { readFileSync, writeFileSync, mkdirSync, readdirSync, existsSync, renameSync } from "node:fs";
import { dirname, join, resolve, extname } from "node:path";
import { pathToFileURL } from "node:url";
import { performance } from "node:perf_hooks";
import vm from "node:vm";

const DRIVER = "agentporter/knowledge/oracles/javascript/oracle.mjs";
const MAX_DEPTH = 64;

class OracleError extends Error {}

function parseArgs(argv) {
  const out = { workspace: ".porter", unit: [], timeout: 10, packageVersion: null, commit: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = () => argv[++i];
    if (a === "--workspace") out.workspace = next();
    else if (a === "--unit") out.unit.push(next());
    else if (a === "--timeout") out.timeout = Number(next());
    else if (a === "--package-version") out.packageVersion = next();
    else if (a === "--commit") out.commit = next();
    else if (a === "--help" || a === "-h") {
      console.log("node oracle.mjs --workspace .porter [--unit U]... [--package-version V] [--commit SHA] [--timeout S]");
      process.exit(0);
    } else throw new OracleError(`unknown argument ${a}`);
  }
  return out;
}

function canonical(v) {
  if (Array.isArray(v)) return "[" + v.map(canonical).join(",") + "]";
  if (v && typeof v === "object") return "{" + Object.keys(v).sort().map((k) => JSON.stringify(k) + ":" + canonical(v[k])).join(",") + "}";
  return JSON.stringify(v);
}

function serializeNumber(n) {
  if (Number.isNaN(n)) return { $float: "nan" };
  if (n === Infinity) return { $float: "inf" };
  if (n === -Infinity) return { $float: "-inf" };
  if (Object.is(n, -0)) return { $float: "-0" };
  return n;
}

export function serialize(value, depth = 0) {
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
  if (ArrayBuffer.isView(value)) return Array.from(value, (v) => serialize(v, d));
  if (value instanceof Date) return { $datetime: Number.isNaN(value.getTime()) ? "Invalid Date" : value.toISOString() };
  if (value instanceof RegExp) return { $type: "RegExp", flags: value.flags, source: value.source };
  if (value instanceof Set) return { $set: [...value].map((v) => serialize(v, d)).sort((a, b) => (canonical(a) < canonical(b) ? -1 : canonical(a) > canonical(b) ? 1 : 0)) };
  if (value instanceof Map) {
    const entries = [...value.entries()];
    if (entries.every(([k]) => typeof k === "string")) return Object.fromEntries(entries.map(([k, v]) => [k, serialize(v, d)]));
    return { $map: entries.map(([k, v]) => [serialize(k, d), serialize(v, d)]) };
  }
  if (value instanceof Error) return { $type: errorName(value), message: value.message };
  const proto = Object.getPrototypeOf(value);
  if (proto === null || proto === Object.prototype) {
    const out = {};
    for (const [k, v] of Object.entries(value)) if (v !== undefined) out[k] = serialize(v, d);
    return out;
  }
  const out = { $type: typeName(value) };
  for (const k of Object.keys(value).filter((k) => !k.startsWith("_")).sort()) {
    if (value[k] !== undefined) out[k] = serialize(value[k], d);
  }
  return out;
}

export function decode(v) {
  if (Array.isArray(v)) return v.map(decode);
  if (!v || typeof v !== "object") return v;
  const keys = Object.keys(v);
  if (keys.length === 1) {
    const raw = v[keys[0]];
    switch (keys[0]) {
      case "$float":
        return { nan: NaN, inf: Infinity, "-inf": -Infinity, "-0": -0 }[raw];
      case "$int":
        return BigInt(raw);
      case "$bytes":
        return Buffer.from(raw, "base64");
      case "$datetime":
        return new Date(raw);
      case "$set":
        return new Set(raw.map(decode));
      case "$map":
        return new Map(raw.map(([k, val]) => [decode(k), decode(val)]));
      case "$undefined":
        return undefined;
    }
  }
  return Object.fromEntries(Object.entries(v).map(([k, val]) => [k, decode(val)]));
}

function typeName(v) {
  return (v && v.constructor && v.constructor.name) || typeof v;
}

function errorName(e) {
  const ctor = e && e.constructor && e.constructor.name;
  if (ctor && ctor !== "Error") return ctor;
  return (e && e.name) || "Error";
}

function isClass(fn) {
  return typeof fn === "function" && /^class[\s{]/.test(Function.prototype.toString.call(fn));
}

function nearestPackage(dir) {
  let cur = dir;
  for (;;) {
    const p = join(cur, "package.json");
    if (existsSync(p)) return { dir: cur, json: JSON.parse(readFileSync(p, "utf8")) };
    const up = dirname(cur);
    if (up === cur) return null;
    cur = up;
  }
}

function isEsm(file) {
  const ext = extname(file);
  if (ext === ".mjs") return true;
  if (ext === ".cjs") return false;
  const pkg = nearestPackage(dirname(file));
  return Boolean(pkg && pkg.json.type === "module");
}

function exportsEntry(pkgJson, subpath) {
  const exp = pkgJson.exports;
  if (exp === undefined) return null;
  const key = subpath ? "./" + subpath : ".";
  let target = typeof exp === "string" || Array.isArray(exp) ? (key === "." ? exp : null) : exp[key];
  const pick = (t) => {
    if (typeof t === "string") return t;
    if (Array.isArray(t)) return t.map(pick).find(Boolean) ?? null;
    if (t && typeof t === "object") return pick(t.import ?? t.node ?? t.require ?? t.default);
    return null;
  };
  return pick(target);
}

function resolveSpecifier(spec, sourceRoot, ownPkg) {
  if (spec.startsWith("./") || spec.startsWith("../") || spec.startsWith("/")) {
    const req = createRequire(join(sourceRoot, "package.json"));
    try {
      return req.resolve(resolve(sourceRoot, spec));
    } catch {
      return resolve(sourceRoot, spec);
    }
  }
  if (ownPkg && (spec === ownPkg.json.name || spec.startsWith(ownPkg.json.name + "/"))) {
    const sub = spec === ownPkg.json.name ? "" : spec.slice(ownPkg.json.name.length + 1);
    const viaExports = exportsEntry(ownPkg.json, sub);
    const req = createRequire(join(ownPkg.dir, "package.json"));
    if (viaExports) return resolve(ownPkg.dir, viaExports);
    if (sub) return req.resolve(resolve(ownPkg.dir, sub));
    return req.resolve(resolve(ownPkg.dir, ownPkg.json.main || "index"));
  }
  return createRequire(join(sourceRoot, "package.json")).resolve(spec);
}

const moduleCache = new Map();

async function loadModule(spec, sourceRoot, ownPkg) {
  if (moduleCache.has(spec)) return moduleCache.get(spec);
  if (spec.startsWith("node:")) {
    const ns = await import(spec);
    moduleCache.set(spec, ns);
    return ns;
  }
  const file = resolveSpecifier(spec, sourceRoot, ownPkg);
  let ns;
  if (isEsm(file)) {
    ns = await import(pathToFileURL(file).href);
  } else {
    const exportsValue = createRequire(file)(file);
    ns = { default: exportsValue };
    if (exportsValue && (typeof exportsValue === "object" || typeof exportsValue === "function")) {
      for (const k of Object.keys(exportsValue)) if (k !== "default") ns[k] = exportsValue[k];
      if ("default" in exportsValue && exportsValue.__esModule) ns.default = exportsValue.default;
    }
  }
  moduleCache.set(spec, ns);
  return ns;
}

async function resolveCall(call, sourceRoot, ownPkg) {
  const idx = call.lastIndexOf(":");
  if (idx <= 0) throw new OracleError(`call '${call}' is not <module>:<qualified name>`);
  const spec = call.slice(0, idx);
  const parts = call.slice(idx + 1).split(".").filter(Boolean);
  let obj = await loadModule(spec, sourceRoot, ownPkg);
  let owner = null;
  for (const p of parts) {
    if (obj !== null && obj !== undefined && p in Object(obj)) {
      owner = obj;
      obj = obj[p];
    } else if (typeof obj === "function" && obj.prototype && p in obj.prototype) {
      owner = obj;
      obj = obj.prototype[p];
    } else {
      throw new OracleError(`cannot resolve ${call}: '${p}' not found`);
    }
  }
  return { owner, target: obj, parts };
}

function syncCall(fn, timeoutMs) {
  return vm.runInNewContext("fn()", { fn }, { timeout: timeoutMs });
}

async function invoke(c, sourceRoot, ownPkg, timeoutMs) {
  const input = c.input || {};
  if (input.kwargs && Object.keys(input.kwargs).length) {
    throw new OracleError(`case ${c.case}: JavaScript has no named arguments; put the options object in args`);
  }
  const { owner, target, parts } = await resolveCall(c.call, sourceRoot, ownPkg);
  const args = decode(input.args || []);
  let thunk;
  if ("init" in input) {
    if (!isClass(owner) && typeof owner !== "function") throw new OracleError(`${c.call}: input.init needs a <Class>.<method> call`);
    const init = input.init || {};
    thunk = () => {
      const instance = new owner(...decode(init.args || []));
      return instance[parts[parts.length - 1]](...args);
    };
  } else if (!("args" in input) && !("kwargs" in input)) {
    return target;
  } else if (isClass(target)) {
    thunk = () => new target(...args);
  } else if (typeof target === "function") {
    thunk = () => target.apply(owner, args);
  } else {
    throw new OracleError(`${c.call} is not callable; use input {} to read it`);
  }
  let result = syncCall(thunk, timeoutMs);
  if (result && typeof result.then === "function") {
    let timer;
    const timeout = new Promise((_, reject) => {
      timer = setTimeout(() => reject(Object.assign(new Error(`timed out after ${timeoutMs / 1000}s`), { __porterTimeout: true })), timeoutMs);
    });
    try {
      result = await Promise.race([result, timeout]);
    } finally {
      clearTimeout(timer);
    }
  }
  return result;
}

function errorOutcome(err, c) {
  if (err && (err.__porterTimeout || err.code === "ERR_SCRIPT_EXECUTION_TIMEOUT")) {
    return { kind: "error", category: "timeout", message: String(err.message) };
  }
  const isErr = err instanceof Error || (err && typeof err === "object" && "message" in err);
  const out = isErr
    ? { kind: "error", category: errorName(err), message: String(err.message) }
    : { kind: "error", category: "NonError", message: String(err) };
  if (c.messagePattern) out.messagePattern = c.messagePattern;
  return out;
}

function writeJson(path, data) {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path + ".tmp", JSON.stringify(data, null, 2) + "\n");
  renameSync(path + ".tmp", path);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const ws = resolve(args.workspace);
  const config = JSON.parse(readFileSync(join(ws, "config.json"), "utf8"));
  const src = config.source || {};
  let sourceRoot = src.path ? resolve(src.path, src.subpath || ".") : process.cwd();
  const ownPkg = nearestPackage(sourceRoot);
  const expandedDir = join(ws, "oracle", "expanded");
  const units = args.unit.length ? args.unit : readdirSync(expandedDir).filter((f) => f.endsWith(".json")).map((f) => f.slice(0, -5)).sort();
  if (!units.length) throw new OracleError(`no expanded cases in ${expandedDir}; run porter.py fixtures expand`);
  const pkg = src.package || {};
  const name = pkg.name || (ownPkg && ownPkg.json.name) || units[0];
  const version = args.packageVersion || pkg.version || (ownPkg && ownPkg.json.version) || "unknown";
  for (const unit of units) {
    const spec = JSON.parse(readFileSync(join(expandedDir, unit + ".json"), "utf8"));
    if (spec.kind === "cli") throw new OracleError(`unit ${unit} is a CLI unit; record it with porter.py cli record`);
    const cases = [];
    const timings = {};
    for (const c of spec.cases) {
      const started = performance.now();
      let expect;
      try {
        const value = await invoke(c, sourceRoot, ownPkg, args.timeout * 1000);
        expect = value === undefined && "args" in (c.input || {}) ? { kind: "value", value: { $undefined: true } } : { kind: "value", value: serialize(value) };
      } catch (err) {
        if (err instanceof OracleError) throw err;
        expect = errorOutcome(err, c);
      }
      timings[c.case] = Math.round((performance.now() - started) * 10000) / 10000;
      const { messagePattern, ...rest } = c;
      cases.push({ ...rest, expect });
    }
    writeJson(join(ws, "fixtures", unit, "oracle.json"), {
      schema: 1,
      unit,
      oracle: {
        language: "javascript",
        package: name,
        version,
        commit: args.commit || src.commit || null,
        runtime: `node ${process.versions.node}`,
        driver: DRIVER,
        recordedAt: new Date().toISOString().replace(/\.\d+Z$/, "Z"),
      },
      cases,
    });
    writeJson(join(ws, "oracle", "timings", unit + ".json"), { unit, cases: timings });
    const errors = cases.filter((c) => c.expect.kind === "error").length;
    console.log(`${unit}: recorded ${cases.length} cases (${errors} errors) -> fixtures/${unit}/oracle.json`);
  }
}

main().catch((err) => {
  process.stderr.write(`oracle: ${err instanceof OracleError ? err.message : err.stack || err}\n`);
  process.exit(2);
});
