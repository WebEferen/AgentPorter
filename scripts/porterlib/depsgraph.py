"""Parse manifests and lockfiles into one normalized dependency list."""
from __future__ import annotations

import argparse
import configparser
import json
import re
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

from .common import PorterError, emit, find_workspace, iter_files, now_iso, read_json, write_json

SCOPE_RANK = {"runtime": 0, "peer": 1, "optional": 2, "build": 3, "dev": 4, "platform": 5}
PEP508 = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*(.*)$")

ROLE_PATTERNS = [
    ("type-stubs", re.compile(r"^(types-.+|@types/.+|.+-stubs|mypy-extensions)$")),
    ("test-tool", re.compile(r"^(pytest.*|mock|coverage|tox|nox|nose2?|hypothesis|freezegun|responses|faker|"
                             r"jest|mocha|chai|sinon|vitest|ava|tap|nyc|istanbul|c8|expect\.js|should|supertest|karma.*|"
                             r"@testing-library/.+|junit.*|org\.junit.*:.+|.*:junit.*|.*mockito.*|.*assertj.*|.*hamcrest.*|"
                             r"phpunit/phpunit|mockery/mockery|pestphp/pest|rspec.*|minitest|xunit.*|nunit.*|moq|"
                             r"github\.com/stretchr/testify|criterion|proptest|quickcheck|ex_machina|mox)$", re.I)),
    ("lint-tool", re.compile(r"^(flake8.*|pylint|black|ruff|isort|mypy|pyright|bandit|pre-commit|eslint.*|@eslint/.+|"
                             r"prettier|tslint|jshint|jscs|standard|xo|@biomejs/.+|rubocop.*|standard|phpstan/.+|"
                             r"vimeo/psalm|friendsofphp/php-cs-fixer|squizlabs/php_codesniffer|ktlint|detekt.*|"
                             r"credo|dialyxir|golangci-lint|stylelint.*)$", re.I)),
    ("build-tool", re.compile(r"^(setuptools.*|wheel|hatchling|hatch-.+|poetry-core|flit-core|pdm-backend|maturin|"
                              r"cython|babel.*|@babel/.+|webpack.*|rollup.*|@rollup/.+|typescript|ts-node|tsx|esbuild|vite|"
                              r"gulp.*|grunt.*|browserify|uglify-js|terser|coffee-script|coffeescript|microbundle|tsup|"
                              r"org\.apache\.maven\.plugins:.+|.*-maven-plugin|.*:lombok)$", re.I)),
    ("polyfill", re.compile(r"^(core-js|es6-promise|@babel/polyfill|regenerator-runtime|whatwg-fetch|six|future|"
                            r"typing[-_]extensions|importlib[-_]metadata|importlib[-_]resources|dataclasses|enum34|"
                            r"pathlib2|backports\..+|futures|symfony/polyfill-.+)$", re.I)),
    ("framework", re.compile(r"^(django|flask|fastapi|starlette|tornado|express|koa|fastify|@nestjs/core|react|vue|"
                             r"@angular/core|svelte|rails|sinatra|laravel/framework|symfony/symfony|"
                             r"org\.springframework.*:.+|github\.com/gin-gonic/gin|phoenix)$", re.I)),
]


def role_hint(name: str, scope: str) -> str:
    for role, rx in ROLE_PATTERNS:
        if rx.match(name):
            return role
    if scope == "build":
        return "build-tool"
    if scope == "dev":
        return "test-tool"
    if scope == "platform":
        return "platform-binding"
    return "runtime-library"


class Collector:
    def __init__(self) -> None:
        self.deps: dict[tuple[str, str], dict] = {}
        self.notes: list[str] = []
        self.manifests: list[dict] = []

    def add(self, eco: str, name: str, scope: str, direct: bool, manifest: str, spec: str | None = None,
            version: str | None = None) -> None:
        if not name:
            return
        if eco == "pypi":
            name = re.sub(r"[-_.]+", "-", name).lower()
        key = (eco, name)
        d = self.deps.get(key)
        if d is None:
            self.deps[key] = {"name": name, "ecosystem": eco, "scope": scope, "direct": direct,
                              "versionSpec": spec, "version": version, "manifests": [manifest]}
            return
        if SCOPE_RANK[scope] < SCOPE_RANK[d["scope"]] and (direct or not d["direct"]):
            d["scope"] = scope
        if direct and not d["direct"]:
            d["direct"] = True
            d["scope"] = scope
        d["versionSpec"] = d["versionSpec"] or spec
        d["version"] = d["version"] or version
        if manifest not in d["manifests"]:
            d["manifests"].append(manifest)

    def lock(self, eco: str, name: str, version: str | None, manifest: str, dev: bool = False) -> None:
        if eco == "pypi":
            name = re.sub(r"[-_.]+", "-", name).lower()
        key = (eco, name)
        if key in self.deps:
            self.deps[key]["version"] = self.deps[key]["version"] or version
            if manifest not in self.deps[key]["manifests"]:
                self.deps[key]["manifests"].append(manifest)
        else:
            self.add(eco, name, "dev" if dev else "runtime", False, manifest, None, version)


def _pep508(spec: str) -> tuple[str, str] | None:
    spec = spec.split(";")[0].strip()
    if not spec or spec.startswith(("-", "#", "git+", "http")):
        egg = re.search(r"#egg=([\w.-]+)", spec)
        return (egg.group(1), spec) if egg else None
    m = PEP508.match(spec)
    if not m:
        return None
    return m.group(1), m.group(3).strip() or None


def parse_npm(c: Collector, path: Path, rel: str) -> None:
    data = read_json(path)
    for section, scope in (("dependencies", "runtime"), ("peerDependencies", "peer"),
                           ("optionalDependencies", "optional"), ("devDependencies", "dev")):
        for name, spec in (data.get(section) or {}).items():
            c.add("npm", name, scope, True, rel, str(spec))


def parse_npm_lock(c: Collector, path: Path, rel: str) -> None:
    data = read_json(path)
    packages = data.get("packages")
    if isinstance(packages, dict):
        for key, info in packages.items():
            if not key or "node_modules/" not in key:
                continue
            name = key.rsplit("node_modules/", 1)[1]
            c.lock("npm", name, info.get("version"), rel, dev=bool(info.get("dev")))
        return

    def walk(deps: dict) -> None:
        for name, info in deps.items():
            c.lock("npm", name, info.get("version"), rel, dev=bool(info.get("dev")))
            walk(info.get("dependencies") or {})
    walk(data.get("dependencies") or {})


def parse_yarn_lock(c: Collector, path: Path, rel: str) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    for block in re.split(r"\n(?=\S)", text):
        head = block.split("\n", 1)[0]
        m = re.match(r'^"?(@?[^@\s"]+)@', head)
        v = re.search(r'^\s+version:?\s+"?([^"\s]+)"?', block, re.M)
        if m and v and not head.startswith("#"):
            c.lock("npm", m.group(1), v.group(1), rel)


def parse_pyproject(c: Collector, path: Path, rel: str) -> None:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    proj = data.get("project", {})
    for spec in proj.get("dependencies", []) or []:
        p = _pep508(spec)
        if p:
            c.add("pypi", p[0], "runtime", True, rel, p[1])
    for group, specs in (proj.get("optional-dependencies") or {}).items():
        scope = "dev" if re.search(r"dev|test|lint|doc|type", group, re.I) else "optional"
        for spec in specs:
            p = _pep508(spec)
            if p:
                c.add("pypi", p[0], scope, True, rel, p[1])
    for group, specs in (data.get("dependency-groups") or {}).items():
        for spec in specs:
            if isinstance(spec, str):
                p = _pep508(spec)
                if p:
                    c.add("pypi", p[0], "dev", True, rel, p[1])
    for spec in (data.get("build-system") or {}).get("requires", []) or []:
        p = _pep508(spec)
        if p:
            c.add("pypi", p[0], "build", True, rel, p[1])
    poetry = data.get("tool", {}).get("poetry", {})

    def poetry_deps(table: dict, scope: str) -> None:
        for name, spec in (table or {}).items():
            if name.lower() == "python":
                continue
            optional = isinstance(spec, dict) and spec.get("optional")
            version = spec.get("version") if isinstance(spec, dict) else str(spec)
            c.add("pypi", name, "optional" if optional else scope, True, rel, version)
    poetry_deps(poetry.get("dependencies"), "runtime")
    poetry_deps(poetry.get("dev-dependencies"), "dev")
    for group in (poetry.get("group") or {}).values():
        poetry_deps(group.get("dependencies"), "dev")


def parse_requirements(c: Collector, path: Path, rel: str, seen: set | None = None) -> None:
    seen = seen or set()
    if path in seen or not path.exists():
        return
    seen.add(path)
    scope = "dev" if re.search(r"dev|test|lint|doc|ci", path.name, re.I) else "runtime"
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split(" #")[0].strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-r", "--requirement", "-c")):
            inc = line.split(maxsplit=1)[1] if " " in line else line[2:]
            parse_requirements(c, path.parent / inc.strip(), rel, seen)
            continue
        if line.startswith("-e"):
            line = line[2:].strip()
        if line.startswith("-"):
            continue
        p = _pep508(line)
        if p:
            c.add("pypi", p[0], scope, True, rel, p[1])


def parse_setup_cfg(c: Collector, path: Path, rel: str) -> None:
    cp = configparser.ConfigParser()
    cp.read(path, encoding="utf-8")
    for line in cp.get("options", "install_requires", fallback="").splitlines():
        p = _pep508(line)
        if p:
            c.add("pypi", p[0], "runtime", True, rel, p[1])
    if cp.has_section("options.extras_require"):
        for group, value in cp.items("options.extras_require"):
            scope = "dev" if re.search(r"dev|test|lint|doc", group, re.I) else "optional"
            for line in value.splitlines():
                p = _pep508(line)
                if p:
                    c.add("pypi", p[0], scope, True, rel, p[1])


def parse_setup_py(c: Collector, path: Path, rel: str) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    for key, scope in (("install_requires", "runtime"), ("tests_require", "dev"), ("setup_requires", "build")):
        m = re.search(rf"{key}\s*=\s*\[(.*?)\]", text, re.S)
        if m:
            for spec in re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)):
                p = _pep508(spec)
                if p:
                    c.add("pypi", p[0], scope, True, rel, p[1])
    m = re.search(r"extras_require\s*=\s*\{(.*?)\n\s*\}", text, re.S)
    if m:
        for group, body in re.findall(r"['\"]([^'\"]+)['\"]\s*:\s*\[(.*?)\]", m.group(1), re.S):
            scope = "dev" if re.search(r"dev|test|lint|doc", group, re.I) else "optional"
            for spec in re.findall(r"['\"]([^'\"]+)['\"]", body):
                p = _pep508(spec)
                if p:
                    c.add("pypi", p[0], scope, True, rel, p[1])
    if "install_requires" in text and not re.search(r"install_requires\s*=\s*\[", text):
        c.notes.append(f"{rel}: install_requires is computed, not a literal list; check it by hand")


def parse_toml_lock(c: Collector, path: Path, rel: str, eco: str) -> None:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    for pkg in data.get("package", []):
        dev = pkg.get("category") == "dev" or pkg.get("groups") == ["dev"]
        c.lock(eco, pkg.get("name", ""), pkg.get("version"), rel, dev=dev)


def parse_pipfile(c: Collector, path: Path, rel: str) -> None:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    for section, scope in (("packages", "runtime"), ("dev-packages", "dev")):
        for name, spec in (data.get(section) or {}).items():
            c.add("pypi", name, scope, True, rel, spec if isinstance(spec, str) else json.dumps(spec))


def parse_pipfile_lock(c: Collector, path: Path, rel: str) -> None:
    data = read_json(path)
    for section, dev in (("default", False), ("develop", True)):
        for name, info in (data.get(section) or {}).items():
            c.lock("pypi", name, (info.get("version") or "").lstrip("="), rel, dev=dev)


def parse_go_mod(c: Collector, path: Path, rel: str) -> None:
    text = path.read_text(encoding="utf-8")
    lines = []
    for block in re.finditer(r"^require\s*\((.*?)\)", text, re.M | re.S):
        lines.extend(block.group(1).splitlines())
    lines.extend(m.group(1) for m in re.finditer(r"^require\s+([^(\s].*)$", text, re.M))
    for line in lines:
        m = re.match(r"^\s*(\S+)\s+(\S+)(.*)$", line)
        if m and not m.group(1).startswith("//"):
            indirect = "// indirect" in m.group(3)
            c.add("go", m.group(1), "runtime", not indirect, rel, None, m.group(2))
    if re.search(r"^replace\b", text, re.M):
        c.notes.append(f"{rel}: has replace directives; versions may come from forks or local paths")


def parse_cargo(c: Collector, path: Path, rel: str) -> None:
    data = tomllib.loads(path.read_text(encoding="utf-8"))

    def take(table: dict, scope: str) -> None:
        for name, spec in (table or {}).items():
            if isinstance(spec, dict):
                real = spec.get("package", name)
                version = spec.get("version") or ("workspace" if spec.get("workspace") else spec.get("git") or spec.get("path"))
                c.add("crates", real, "optional" if spec.get("optional") else scope, True, rel, version)
            else:
                c.add("crates", name, scope, True, rel, str(spec))
    take(data.get("dependencies"), "runtime")
    take(data.get("dev-dependencies"), "dev")
    take(data.get("build-dependencies"), "build")
    for target in (data.get("target") or {}).values():
        take(target.get("dependencies"), "runtime")
        take(target.get("dev-dependencies"), "dev")
    take((data.get("workspace") or {}).get("dependencies"), "runtime")


def parse_pom(c: Collector, path: Path, rel: str) -> None:
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        c.notes.append(f"{rel}: XML parse error {exc}")
        return
    root = tree.getroot()
    ns = {"m": root.tag[1:].split("}")[0]} if root.tag.startswith("{") else {}
    q = (lambda t: f"m:{t}") if ns else (lambda t: t)
    props = {}
    pnode = root.find(q("properties"), ns)
    if pnode is not None:
        for child in pnode:
            props[child.tag.split("}")[-1]] = (child.text or "").strip()
    for key in ("version", "groupId"):
        node = root.find(q(key), ns)
        if node is not None and node.text:
            props[f"project.{key}"] = node.text.strip()

    def sub(text: str | None) -> str | None:
        if not text:
            return None
        return re.sub(r"\$\{([^}]+)\}", lambda m: props.get(m.group(1), m.group(0)), text.strip())
    managed = {}
    for dep in root.findall(f"{q('dependencyManagement')}/{q('dependencies')}/{q('dependency')}", ns):
        g, a = sub(dep.findtext(q("groupId"), None, ns)), sub(dep.findtext(q("artifactId"), None, ns))
        managed[f"{g}:{a}"] = sub(dep.findtext(q("version"), None, ns))
    for dep in root.findall(f"{q('dependencies')}/{q('dependency')}", ns):
        g, a = sub(dep.findtext(q("groupId"), None, ns)), sub(dep.findtext(q("artifactId"), None, ns))
        name = f"{g}:{a}"
        version = sub(dep.findtext(q("version"), None, ns)) or managed.get(name)
        scope_raw = (dep.findtext(q("scope"), None, ns) or "compile").strip()
        scope = {"test": "dev", "provided": "build", "system": "platform"}.get(scope_raw, "runtime")
        if (dep.findtext(q("optional"), None, ns) or "").strip() == "true":
            scope = "optional"
        c.add("maven", name, scope, True, rel, None, version)
    if root.find(q("parent"), ns) is not None:
        c.notes.append(f"{rel}: has a parent POM; inherited dependencies and versions are not resolved")


GRADLE_CONF = {
    "implementation": "runtime", "api": "runtime", "runtimeOnly": "runtime", "compile": "runtime",
    "compileOnly": "build", "kapt": "build", "ksp": "build", "annotationProcessor": "build",
    "testImplementation": "dev", "testRuntimeOnly": "dev", "testCompileOnly": "dev", "testCompile": "dev",
    "androidTestImplementation": "dev", "debugImplementation": "dev",
}


def parse_gradle(c: Collector, path: Path, rel: str, catalog: dict[str, tuple[str, str | None]]) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    conf_rx = "|".join(GRADLE_CONF)
    for m in re.finditer(rf"^\s*({conf_rx})\s*\(?\s*['\"]([^'\":]+):([^'\":]+)(?::([^'\"]+))?['\"]", text, re.M):
        c.add("maven", f"{m.group(2)}:{m.group(3)}", GRADLE_CONF[m.group(1)], True, rel, None, m.group(4))
    for m in re.finditer(rf"^\s*({conf_rx})\s*\(?\s*libs\.([\w.]+)", text, re.M):
        accessor = m.group(2)
        if accessor in catalog:
            module, version = catalog[accessor]
            c.add("maven", module, GRADLE_CONF[m.group(1)], True, rel, None, version)
        else:
            c.notes.append(f"{rel}: catalog accessor libs.{accessor} not found in libs.versions.toml")


def load_catalog(path: Path) -> dict[str, tuple[str, str | None]]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    versions = data.get("versions", {})
    out = {}
    for alias, spec in (data.get("libraries") or {}).items():
        if isinstance(spec, str):
            parts = spec.split(":")
            module, version = ":".join(parts[:2]), (parts[2] if len(parts) > 2 else None)
        else:
            module = spec.get("module") or f"{spec.get('group')}:{spec.get('name')}"
            v = spec.get("version")
            if isinstance(v, dict):
                version = versions.get(v.get("ref")) if v.get("ref") else v.get("strictly") or v.get("prefer")
            else:
                version = v
        out[re.sub(r"[-_]", ".", alias)] = (module, version)
    return out


def parse_composer(c: Collector, path: Path, rel: str) -> None:
    data = read_json(path)
    for section, scope in (("require", "runtime"), ("require-dev", "dev")):
        for name, spec in (data.get(section) or {}).items():
            plat = name == "php" or name.startswith(("ext-", "lib-", "composer-"))
            c.add("packagist", name, "platform" if plat else scope, True, rel, spec)


def parse_composer_lock(c: Collector, path: Path, rel: str) -> None:
    data = read_json(path)
    for section, dev in (("packages", False), ("packages-dev", True)):
        for pkg in data.get(section) or []:
            c.lock("packagist", pkg.get("name", ""), pkg.get("version"), rel, dev=dev)


def parse_gemfile(c: Collector, path: Path, rel: str) -> None:
    groups: list[list[str]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        g = re.match(r"^group\s+(.*?)\s+do\b", s)
        if g:
            groups.append(re.findall(r":(\w+)", g.group(1)))
            continue
        if s == "end" and groups:
            groups.pop()
            continue
        m = re.match(r"""^gem\s+['"]([^'"]+)['"](?:\s*,\s*['"]([^'"]+)['"])?(.*)$""", s)
        if m:
            inline = re.findall(r":(\w+)", m.group(3) or "") if "group" in (m.group(3) or "") else []
            active = {x for grp in groups for x in grp} | set(inline)
            scope = "dev" if active & {"test", "development"} and "production" not in active else "runtime"
            c.add("rubygems", m.group(1), scope, True, rel, m.group(2))


def parse_gemfile_lock(c: Collector, path: Path, rel: str) -> None:
    section = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if re.match(r"^[A-Z]", line):
            section = line.strip()
            continue
        if section == "GEM" or section == "GIT" or section == "PATH":
            m = re.match(r"^ {4}([\w.-]+) \(([^)]+)\)$", line)
            if m:
                c.lock("rubygems", m.group(1), m.group(2), rel)
        elif section == "DEPENDENCIES":
            m = re.match(r"^\s+([\w.-]+)", line)
            if m and ("rubygems", m.group(1)) in c.deps:
                c.deps[("rubygems", m.group(1))]["direct"] = True


def parse_gemspec(c: Collector, path: Path, rel: str) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r"""\.add_(runtime_|development_)?dependency\s*\(?\s*['"]([^'"]+)['"](?:\s*,\s*['"]([^'"]+)['"])?""", text):
        scope = "dev" if m.group(1) == "development_" else "runtime"
        c.add("rubygems", m.group(2), scope, True, rel, m.group(3))


def parse_csproj(c: Collector, path: Path, rel: str, central: dict[str, str]) -> None:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        c.notes.append(f"{rel}: XML parse error {exc}")
        return
    for el in root.iter():
        if el.tag.split("}")[-1] != "PackageReference":
            continue
        name = el.get("Include") or el.get("Update")
        version = el.get("Version")
        private = el.get("PrivateAssets")
        for child in el:
            tag = child.tag.split("}")[-1]
            if tag == "Version":
                version = (child.text or "").strip()
            if tag == "PrivateAssets":
                private = (child.text or "").strip()
        version = version or central.get(name or "")
        c.add("nuget", name or "", "build" if (private or "").lower() == "all" else "runtime", True, rel, version)


def load_central(path: Path) -> dict[str, str]:
    out = {}
    try:
        for el in ET.parse(path).getroot().iter():
            if el.tag.split("}")[-1] == "PackageVersion" and el.get("Include"):
                out[el.get("Include")] = el.get("Version")
    except ET.ParseError:
        pass
    return out


def parse_nuget_lock(c: Collector, path: Path, rel: str) -> None:
    data = read_json(path)
    for packages in (data.get("dependencies") or {}).values():
        for name, info in packages.items():
            c.lock("nuget", name, info.get("resolved"), rel)


def parse_mix(c: Collector, path: Path, rel: str) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r"\{:(\w+)\s*,\s*(?:\"([^\"]+)\")?([^}]*)\}", text):
        rest = m.group(3) or ""
        scope = "dev" if re.search(r"only:\s*(\[?\s*:(test|dev))", rest) else "runtime"
        if "optional: true" in rest:
            scope = "optional"
        c.add("hex", m.group(1), scope, True, rel, m.group(2))


def parse_mix_lock(c: Collector, path: Path, rel: str) -> None:
    for m in re.finditer(r'^\s*"([\w-]+)":\s*\{:hex,\s*:[\w-]+,\s*"([^"]+)"', path.read_text(encoding="utf-8"), re.M):
        c.lock("hex", m.group(1), m.group(2), rel)


def build_graph(root: Path, subpath: str | None = None) -> dict:
    base = (root / subpath) if subpath else root
    if not base.is_dir():
        raise PorterError(f"not a directory: {base}")
    files = [f for f in iter_files(base)]
    by_name: dict[str, list[Path]] = {}
    for f in files:
        by_name.setdefault(f.name, []).append(f)
    c = Collector()
    catalog: dict = {}
    for f in by_name.get("libs.versions.toml", []):
        catalog.update(load_catalog(f))
    central: dict = {}
    for f in by_name.get("Directory.Packages.props", []):
        central.update(load_central(f))
    handlers = [
        ("package.json", parse_npm), ("package-lock.json", parse_npm_lock), ("npm-shrinkwrap.json", parse_npm_lock),
        ("yarn.lock", parse_yarn_lock), ("pyproject.toml", parse_pyproject), ("setup.cfg", parse_setup_cfg),
        ("setup.py", parse_setup_py), ("Pipfile", parse_pipfile), ("Pipfile.lock", parse_pipfile_lock),
        ("poetry.lock", lambda c, p, r: parse_toml_lock(c, p, r, "pypi")),
        ("uv.lock", lambda c, p, r: parse_toml_lock(c, p, r, "pypi")),
        ("go.mod", parse_go_mod), ("Cargo.toml", parse_cargo),
        ("Cargo.lock", lambda c, p, r: parse_toml_lock(c, p, r, "crates")),
        ("pom.xml", parse_pom),
        ("build.gradle", lambda c, p, r: parse_gradle(c, p, r, catalog)),
        ("build.gradle.kts", lambda c, p, r: parse_gradle(c, p, r, catalog)),
        ("composer.json", parse_composer), ("composer.lock", parse_composer_lock),
        ("Gemfile", parse_gemfile), ("Gemfile.lock", parse_gemfile_lock),
        ("packages.lock.json", parse_nuget_lock), ("mix.exs", parse_mix), ("mix.lock", parse_mix_lock),
    ]
    order = [name for name, _ in handlers]
    manifest_files = []
    for name, handler in handlers:
        for f in by_name.get(name, []):
            manifest_files.append((order.index(name), f, handler))
    for f in files:
        if re.match(r"^(.*[._-])?requirements([._-].*)?\.txt$", f.name) or (f.parent.name == "requirements" and f.suffix == ".txt"):
            manifest_files.append((len(order), f, parse_requirements))
        elif f.suffix == ".gemspec":
            manifest_files.append((len(order), f, parse_gemspec))
        elif f.suffix == ".csproj":
            manifest_files.append((len(order), f, lambda c, p, r: parse_csproj(c, p, r, central)))
    lock_names = {"package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "Pipfile.lock", "poetry.lock", "uv.lock",
                  "Cargo.lock", "composer.lock", "Gemfile.lock", "packages.lock.json", "mix.lock"}
    manifest_files.sort(key=lambda x: (x[1].name in lock_names, x[0], str(x[1])))
    for _, f, handler in manifest_files:
        rel = f.relative_to(base).as_posix()
        try:
            handler(c, f, rel)
            c.manifests.append({"path": rel, "parsed": True})
        except (OSError, ValueError, tomllib.TOMLDecodeError, PorterError) as exc:
            c.manifests.append({"path": rel, "parsed": False, "error": str(exc)[:200]})
            c.notes.append(f"{rel}: could not parse ({exc})")
    if by_name.get("pnpm-lock.yaml"):
        c.notes.append("pnpm-lock.yaml is not parsed; versions come from package.json ranges")
    if not c.manifests:
        c.notes.append("no supported manifest found; fall back to import scanning (porter.py usage-scan) and say so in deps.md")
    deps = sorted(c.deps.values(), key=lambda d: (not d["direct"], SCOPE_RANK[d["scope"]], d["ecosystem"], d["name"]))
    for d in deps:
        d["roleHint"] = role_hint(d["name"], d["scope"])
    ecos = sorted({d["ecosystem"] for d in deps})
    return {
        "schema": 1,
        "generatedAt": now_iso(),
        "root": str(base),
        "ecosystems": ecos,
        "manifests": c.manifests,
        "counts": {
            "direct": sum(1 for d in deps if d["direct"]),
            "directRuntime": sum(1 for d in deps if d["direct"] and d["scope"] in ("runtime", "peer", "optional")),
            "transitive": sum(1 for d in deps if not d["direct"]),
        },
        "dependencies": deps,
        "notes": c.notes,
    }


def cmd_deps_graph(args: argparse.Namespace) -> int:
    root, subpath, ws = args.path, args.subpath, None
    artifact = False
    if args.write or not root:
        ws = find_workspace(args.workspace)
        cfg = read_json(ws / "config.json")
        artifact = cfg["source"].get("mode") == "artifact" and not root and not (ws / "recover" / "source").exists()
        root = root or cfg["source"].get("path")
        subpath = subpath or cfg["source"].get("subpath")
    if artifact:
        from .recover import deps_from_recovery
        graph = deps_from_recovery(ws)
    elif not root:
        raise PorterError("source path unknown: pass a path or run porter.py source fetch")
    else:
        graph = build_graph(Path(root), subpath)
    if args.write and ws:
        write_json(ws / "cache" / "deps-graph.json", graph)
    if args.json:
        emit(graph, True)
        return 0
    print(f"Manifests: {', '.join(m['path'] + ('' if m['parsed'] else ' (FAILED)') for m in graph['manifests']) or 'none'}")
    print(f"Direct: {graph['counts']['direct']} ({graph['counts']['directRuntime']} runtime), transitive: {graph['counts']['transitive']}")
    print("\n| Name | Ecosystem | Scope | Direct | Spec | Locked | Role hint |\n| --- | --- | --- | --- | --- | --- | --- |")
    for d in graph["dependencies"]:
        if d["direct"] or args.all:
            print(f"| {d['name']} | {d['ecosystem']} | {d['scope']} | {'yes' if d['direct'] else 'no'} | "
                  f"{d['versionSpec'] or ''} | {d['version'] or ''} | {d['roleHint']} |")
    for n in graph["notes"]:
        print(f"Note: {n}")
    if args.write and ws:
        print(f"\nWrote {ws / 'cache' / 'deps-graph.json'}")
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("deps-graph", help="parse manifests and lockfiles into a normalized dependency list")
    p.add_argument("path", nargs="?")
    p.add_argument("--subpath")
    p.add_argument("--workspace")
    p.add_argument("--write", action="store_true", help="write .porter/cache/deps-graph.json")
    p.add_argument("--all", action="store_true", help="also list transitive dependencies")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_deps_graph)
