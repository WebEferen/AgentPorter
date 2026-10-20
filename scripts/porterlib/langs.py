from __future__ import annotations

EXT_LANG = {
    ".py": "python", ".pyi": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".mts": "typescript", ".cts": "typescript",
    ".coffee": "coffeescript", ".litcoffee": "coffeescript",
    ".go": "go", ".rs": "rust", ".java": "java", ".kt": "kotlin", ".kts": "kotlin",
    ".scala": "scala", ".php": "php", ".rb": "ruby", ".cs": "csharp", ".fs": "fsharp",
    ".c": "c", ".h": "c", ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".hh": "cpp",
    ".m": "objective-c", ".swift": "swift", ".ex": "elixir", ".exs": "elixir", ".erl": "erlang",
    ".pl": "perl", ".pm": "perl", ".lua": "lua", ".dart": "dart", ".sh": "shell", ".bash": "shell",
    ".r": "r", ".jl": "julia", ".clj": "clojure", ".hs": "haskell", ".ml": "ocaml", ".vb": "vb",
    ".groovy": "groovy",
}

REGISTRY_OF = {
    "typescript": "npm", "javascript": "npm", "coffeescript": "npm", "python": "pypi", "rust": "crates",
    "go": "go", "java": "maven", "kotlin": "maven", "scala": "maven", "php": "packagist",
    "ruby": "rubygems", "csharp": "nuget", "fsharp": "nuget", "elixir": "hex",
}

NODE_BUILTINS = {
    "assert", "async_hooks", "buffer", "child_process", "cluster", "console", "constants", "crypto",
    "dgram", "diagnostics_channel", "dns", "domain", "events", "fs", "http", "http2", "https",
    "inspector", "module", "net", "os", "path", "perf_hooks", "process", "punycode", "querystring",
    "readline", "repl", "stream", "string_decoder", "sys", "test", "timers", "tls", "trace_events",
    "tty", "url", "util", "v8", "vm", "wasi", "worker_threads", "zlib",
}

CLASS_LANGS = {"java", "kotlin", "csharp", "php", "ruby", "scala", "swift", "dart", "groovy"}

TEST_DIR_NAMES = {"test", "tests", "__tests__", "spec", "specs", "testing", "t"}
AUX_DIR_NAMES = {"docs", "doc", "examples", "example", "benchmarks", "benchmark", "bench", "scripts",
                 "tools", "fixtures", "samples", "demo", "demos", "contrib", "misc"}

LANG_ALIASES = {
    "ts": "typescript", "js": "javascript", "node": "javascript", "nodejs": "javascript", "py": "python",
    "python3": "python", "golang": "go", "rs": "rust", "kt": "kotlin", "rb": "ruby", "c#": "csharp",
    "cs": "csharp", "dotnet": "csharp", ".net": "csharp", "ex": "elixir", "c++": "cpp",
}


def normalize_lang(name: str | None) -> str | None:
    if not name:
        return None
    key = name.strip().lower()
    return LANG_ALIASES.get(key, key)
