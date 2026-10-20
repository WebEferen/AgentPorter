"""Registry lookups: prove a candidate package exists and read its maturity signals.

Every MAP or SHIM decision in deps.json must be backed by a cached record written here.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable

from .common import PorterError, emit, find_workspace, now_iso, read_json, write_json
from .langs import REGISTRY_OF

USER_AGENT = "agentporter/0.1 (+https://github.com/WebEferen/AgentPorter)"
PRERELEASE = re.compile(r"(?i)[-.]?(alpha|beta|rc|cr|m\d|milestone|snapshot|dev|pre|preview|canary|next|ea)\d*\b")
REGISTRIES = ("npm", "pypi", "crates", "go", "maven", "packagist", "rubygems", "nuget", "hex")


class HttpResult:
    def __init__(self, status: int, body: bytes, error: str | None = None):
        self.status = status
        self.body = body
        self.error = error

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


def http_get(url: str, timeout: float = 25, retries: int = 2) -> HttpResult:
    last_error = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT, "Accept": "application/json, text/xml;q=0.9, */*;q=0.5",
            "Accept-Encoding": "gzip",
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip" or body[:2] == b"\x1f\x8b":
                    body = gzip.decompress(body)
                return HttpResult(resp.status, body)
        except urllib.error.HTTPError as exc:
            if exc.code in (404, 410):
                return HttpResult(exc.code, b"")
            last_error = f"HTTP {exc.code}"
            if exc.code not in (429, 500, 502, 503, 504):
                return HttpResult(exc.code, b"", last_error)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = str(getattr(exc, "reason", exc))
        time.sleep(1.5 * (attempt + 1))
    return HttpResult(0, b"", last_error or "network error")


def _stable(version: str | None) -> bool:
    return bool(version) and not PRERELEASE.search(version.lstrip("v"))


def _result(registry: str, name: str, **fields: Any) -> dict:
    base = {
        "registry": registry, "name": name, "exists": None, "latestVersion": None, "latestReleaseDate": None,
        "firstReleaseDate": None, "versionsCount": None, "license": None, "description": None,
        "homepage": None, "repository": None, "deprecated": None, "adoption": None, "advisories": None,
        "url": None, "fetchedAt": now_iso(), "error": None,
    }
    base.update(fields)
    return base


def _q(s: str) -> str:
    return urllib.parse.quote(s, safe="")


# ------------------------------------------------------------------ adapters

def lookup_npm(name: str) -> dict:
    r = http_get(f"https://registry.npmjs.org/{name.replace('/', '%2F')}")
    if r.status in (404, 410):
        return _result("npm", name, exists=False)
    if r.error:
        return _result("npm", name, error=r.error)
    doc = r.json()
    latest = (doc.get("dist-tags") or {}).get("latest")
    vinfo = (doc.get("versions") or {}).get(latest, {})
    lic = vinfo.get("license") or doc.get("license")
    if isinstance(lic, dict):
        lic = lic.get("type")
    if not lic:
        legacy = vinfo.get("licenses") or doc.get("licenses") or []
        lic = " OR ".join(x.get("type") if isinstance(x, dict) else str(x) for x in legacy if x) or None
    repo = vinfo.get("repository") or doc.get("repository")
    times = doc.get("time") or {}
    dl = http_get(f"https://api.npmjs.org/downloads/point/last-month/{name}", timeout=15, retries=1)
    downloads = dl.json().get("downloads") if dl.status == 200 and not dl.error else None
    return _result(
        "npm", name, exists=True, latestVersion=latest, latestReleaseDate=times.get(latest),
        firstReleaseDate=times.get("created"), versionsCount=len(doc.get("versions") or {}), license=lic,
        description=doc.get("description"), homepage=doc.get("homepage"),
        repository=repo.get("url") if isinstance(repo, dict) else repo, deprecated=vinfo.get("deprecated"),
        adoption={"metric": "downloads last month", "value": downloads} if downloads is not None else None,
        url=f"https://www.npmjs.com/package/{name}",
    )


def lookup_pypi(name: str) -> dict:
    r = http_get(f"https://pypi.org/pypi/{_q(name)}/json")
    if r.status in (404, 410):
        return _result("pypi", name, exists=False)
    if r.error:
        return _result("pypi", name, error=r.error)
    doc = r.json()
    info = doc.get("info", {})
    releases = doc.get("releases") or {}
    version = info.get("version")
    files = releases.get(version) or []
    times = sorted(f.get("upload_time_iso_8601") for rel in releases.values() for f in rel if f.get("upload_time_iso_8601"))
    cls = [c.split("::")[-1].strip() for c in info.get("classifiers", []) if c.startswith("License ::")]
    lic = (info.get("license_expression") or (" OR ".join(cls) if len(cls) > 1 else None)
           or (info.get("license") if info.get("license") and len(info["license"]) < 80 else None)
           or (cls[0] if cls else None))
    urls = info.get("project_urls") or {}
    repo = next((v for k, v in urls.items() if re.search(r"source|repo|github|gitlab|code", k, re.I)), None)
    return _result(
        "pypi", name, exists=True, latestVersion=version,
        latestReleaseDate=files[0].get("upload_time_iso_8601") if files else None,
        firstReleaseDate=times[0] if times else None, versionsCount=len(releases), license=lic,
        description=info.get("summary"), homepage=info.get("home_page") or urls.get("Homepage"), repository=repo,
        deprecated=info.get("yanked_reason") if info.get("yanked") else None, adoption=None,
        url=f"https://pypi.org/project/{name}/",
    )


def lookup_crates(name: str) -> dict:
    r = http_get(f"https://crates.io/api/v1/crates/{_q(name)}")
    if r.status in (404, 410):
        return _result("crates", name, exists=False)
    if r.error:
        return _result("crates", name, error=r.error)
    doc = r.json()
    crate = doc.get("crate", {})
    latest = crate.get("max_stable_version") or crate.get("newest_version")
    versions = doc.get("versions") or []
    vinfo = next((v for v in versions if v.get("num") == latest), {})
    return _result(
        "crates", name, exists=True, latestVersion=latest, latestReleaseDate=vinfo.get("created_at"),
        firstReleaseDate=crate.get("created_at"), versionsCount=len(versions),
        license=(vinfo.get("license") or "").replace("/", " OR ") or None, description=crate.get("description"),
        homepage=crate.get("homepage"), repository=crate.get("repository"),
        deprecated="yanked" if vinfo.get("yanked") else None,
        adoption={"metric": "downloads last 90 days", "value": crate.get("recent_downloads")},
        url=f"https://crates.io/crates/{name}",
    )


def _go_escape(path: str) -> str:
    return re.sub(r"[A-Z]", lambda m: "!" + m.group(0).lower(), path)


def lookup_go(name: str) -> dict:
    esc = _go_escape(name)
    r = http_get(f"https://proxy.golang.org/{esc}/@latest")
    if r.status in (404, 410):
        return _result("go", name, exists=False)
    if r.error:
        return _result("go", name, error=r.error)
    latest = r.json()
    version = latest.get("Version")
    lst = http_get(f"https://proxy.golang.org/{esc}/@v/list", timeout=15, retries=1)
    count = len([l for l in lst.text().splitlines() if l.strip()]) if lst.status == 200 else None
    dd = http_get(f"https://api.deps.dev/v3/systems/go/packages/{_q(name)}/versions/{_q(version)}", timeout=20, retries=1)
    lic, repo, adv = None, None, None
    if dd.status == 200 and not dd.error:
        ddj = dd.json()
        lic = " AND ".join(ddj.get("licenses") or []) or None
        repo = next((l["url"] for l in ddj.get("links", []) if l.get("label") == "SOURCE_REPO"), None)
        adv = len(ddj.get("advisoryKeys") or [])
    search = http_get(f"https://pkg.go.dev/v1/search?q={_q(name)}&limit=5", timeout=15, retries=0)
    adoption = None
    if search.status == 200 and not search.error:
        try:
            for item in search.json().get("items", []):
                if item.get("modulePath") == name or item.get("packagePath") == name:
                    adoption = {"metric": "imported by packages", "value": (item.get("importedByCounts") or {}).get("packages")}
                    break
        except ValueError:
            pass
    return _result(
        "go", name, exists=True, latestVersion=version, latestReleaseDate=latest.get("Time"), versionsCount=count,
        license=lic, repository=repo or (f"https://{name}" if name.startswith("github.com/") else None),
        advisories=adv, adoption=adoption, url=f"https://pkg.go.dev/{name}",
    )


def lookup_maven(name: str) -> dict:
    if ":" not in name:
        return _result("maven", name, error="maven names are group:artifact")
    group, artifact = name.split(":", 1)
    base = f"https://repo1.maven.org/maven2/{group.replace('.', '/')}/{artifact}"
    r = http_get(f"{base}/maven-metadata.xml")
    if r.status in (404, 410):
        return _result("maven", name, exists=False)
    if r.error:
        return _result("maven", name, error=r.error)
    root = ET.fromstring(r.body)
    versions = [v.text for v in root.iter("version") if v.text]
    stable = [v for v in versions if _stable(v)]
    version = stable[-1] if stable else root.findtext("versioning/release")
    updated = root.findtext("versioning/lastUpdated")
    lic, desc, repo, adv, published = None, None, None, None, None
    dd = http_get(f"https://api.deps.dev/v3/systems/maven/packages/{_q(name)}", timeout=20, retries=1)
    if dd.status == 200 and not dd.error:
        default = next((v for v in dd.json().get("versions", []) if v.get("isDefault")), None)
        if default:
            version = default["versionKey"]["version"]
    ddv = http_get(f"https://api.deps.dev/v3/systems/maven/packages/{_q(name)}/versions/{_q(version)}", timeout=20, retries=1)
    if ddv.status == 200 and not ddv.error:
        j = ddv.json()
        lic = " AND ".join(j.get("licenses") or []) or None
        adv = len(j.get("advisoryKeys") or [])
        published = j.get("publishedAt")
        repo = next((l["url"] for l in j.get("links", []) if l.get("label") == "SOURCE_REPO"), None)
    pom = http_get(f"{base}/{version}/{artifact}-{version}.pom", timeout=20, retries=1)
    if pom.status == 200 and not pom.error:
        text = pom.text()
        m = re.search(r"<description>(.*?)</description>", text, re.S)
        desc = re.sub(r"\s+", " ", m.group(1)).strip()[:300] if m else None
        if not lic:
            m = re.search(r"<license>\s*<name>(.*?)</name>", text, re.S)
            lic = m.group(1).strip() if m else None
        if not repo:
            m = re.search(r"<scm>.*?<url>(.*?)</url>", text, re.S)
            repo = m.group(1).strip() if m else None
    if not published and updated and len(updated) >= 8:
        published = f"{updated[:4]}-{updated[4:6]}-{updated[6:8]} (metadata lastUpdated)"
    return _result(
        "maven", name, exists=True, latestVersion=version, latestReleaseDate=published, versionsCount=len(versions),
        license=lic, description=desc, repository=repo, advisories=adv,
        url=f"https://central.sonatype.com/artifact/{group}/{artifact}",
    )


def _expand_minified(entries: list[dict]) -> list[dict]:
    out, current = [], {}
    for entry in entries:
        current = dict(current)
        for k, v in entry.items():
            if v == "__unset":
                current.pop(k, None)
            else:
                current[k] = v
        out.append(current)
    return out


def lookup_packagist(name: str) -> dict:
    if "/" not in name:
        return _result("packagist", name, error="packagist names are vendor/package")
    r = http_get(f"https://repo.packagist.org/p2/{name}.json")
    if r.status in (404, 410):
        return _result("packagist", name, exists=False)
    if r.error:
        return _result("packagist", name, error=r.error)
    doc = r.json()
    entries = (doc.get("packages") or {}).get(name, [])
    if doc.get("minified") == "composer/2.0":
        entries = _expand_minified(entries)
    stable = [e for e in entries if _stable(e.get("version"))] or entries
    top = stable[0] if stable else {}
    times = sorted(e.get("time") for e in entries if e.get("time"))
    meta = http_get(f"https://packagist.org/packages/{name}.json", timeout=20, retries=1)
    downloads, abandoned, repo = None, None, None
    if meta.status == 200 and not meta.error:
        pkg = meta.json().get("package", {})
        downloads = (pkg.get("downloads") or {}).get("monthly")
        abandoned = pkg.get("abandoned")
        repo = pkg.get("repository")
    adv = doc.get("security-advisories")
    return _result(
        "packagist", name, exists=True, latestVersion=top.get("version"), latestReleaseDate=top.get("time"),
        firstReleaseDate=times[0] if times else None, versionsCount=len(entries),
        license=", ".join(top.get("license") or []) or None, description=top.get("description"),
        homepage=top.get("homepage"), repository=repo,
        deprecated=(f"abandoned (use {abandoned})" if isinstance(abandoned, str) else "abandoned") if abandoned else None,
        adoption={"metric": "downloads last month", "value": downloads} if downloads is not None else None,
        advisories=len(adv) if isinstance(adv, list) else None, url=f"https://packagist.org/packages/{name}",
    )


def lookup_rubygems(name: str) -> dict:
    r = http_get(f"https://rubygems.org/api/v1/gems/{_q(name)}.json")
    if r.status in (404, 410):
        return _result("rubygems", name, exists=False)
    if r.error:
        return _result("rubygems", name, error=r.error)
    try:
        doc = r.json()
    except ValueError:
        return _result("rubygems", name, exists=False)
    vers = http_get(f"https://rubygems.org/api/v1/versions/{_q(name)}.json", timeout=20, retries=1)
    count, first = None, None
    if vers.status == 200 and not vers.error:
        vlist = vers.json()
        count = len({v.get("number") for v in vlist})
        dates = sorted(v.get("created_at") for v in vlist if v.get("created_at"))
        first = dates[0] if dates else None
    return _result(
        "rubygems", name, exists=True, latestVersion=doc.get("version"), latestReleaseDate=doc.get("version_created_at"),
        firstReleaseDate=first, versionsCount=count, license=", ".join(doc.get("licenses") or []) or None,
        description=doc.get("info"), homepage=doc.get("homepage_uri"), repository=doc.get("source_code_uri"),
        adoption={"metric": "total downloads", "value": doc.get("downloads")}, url=f"https://rubygems.org/gems/{name}",
    )


def lookup_nuget(name: str) -> dict:
    r = http_get(f"https://azuresearch-usnc.nuget.org/query?q=packageid:{_q(name)}&prerelease=false&semVerLevel=2.0.0")
    if r.error:
        return _result("nuget", name, error=r.error)
    data = [d for d in r.json().get("data", []) if d.get("id", "").lower() == name.lower()]
    if not data:
        return _result("nuget", name, exists=False)
    d = data[0]
    published, lic = None, None
    reg = http_get(f"https://api.nuget.org/v3/registration5-gz-semver2/{name.lower()}/index.json", timeout=25, retries=1)
    if reg.status == 200 and not reg.error:
        pages = reg.json().get("items", [])
        if pages:
            page = pages[-1]
            if "items" not in page:
                pr = http_get(page["@id"], timeout=25, retries=1)
                page = pr.json() if pr.status == 200 and not pr.error else {}
            for leaf in reversed(page.get("items", [])):
                entry = leaf.get("catalogEntry", {})
                if entry.get("version") == d.get("version") or not published:
                    if not str(entry.get("published", "")).startswith("1900"):
                        published = entry.get("published")
                        lic = entry.get("licenseExpression") or None
                    if entry.get("version") == d.get("version"):
                        break
    dep = d.get("deprecation")
    return _result(
        "nuget", d.get("id", name), exists=True, latestVersion=d.get("version"), latestReleaseDate=published,
        versionsCount=len(d.get("versions") or []), license=lic or (d.get("licenseUrl") and f"see {d['licenseUrl']}"),
        description=d.get("description"), homepage=d.get("projectUrl"),
        deprecated=", ".join(dep.get("reasons", [])) if isinstance(dep, dict) else None,
        advisories=len(d.get("vulnerabilities") or []),
        adoption={"metric": "total downloads", "value": d.get("totalDownloads")},
        url=f"https://www.nuget.org/packages/{d.get('id', name)}",
    )


def lookup_hex(name: str) -> dict:
    r = http_get(f"https://hex.pm/api/packages/{_q(name)}")
    if r.status in (404, 410):
        return _result("hex", name, exists=False)
    if r.error:
        return _result("hex", name, error=r.error)
    doc = r.json()
    latest = doc.get("latest_stable_version") or doc.get("latest_version")
    rel = next((x for x in doc.get("releases", []) if x.get("version") == latest), {})
    meta = doc.get("meta") or {}
    links = meta.get("links") or {}
    retired = (doc.get("retirements") or {}).get(latest)
    return _result(
        "hex", name, exists=True, latestVersion=latest, latestReleaseDate=rel.get("inserted_at"),
        firstReleaseDate=doc.get("inserted_at"), versionsCount=len(doc.get("releases") or []),
        license=", ".join(meta.get("licenses") or []) or None, description=meta.get("description"),
        repository=next((v for k, v in links.items() if re.search(r"github|gitlab|source", k, re.I)), None),
        deprecated=retired.get("reason") if isinstance(retired, dict) else None,
        advisories=len(doc.get("security_advisories") or []) if "security_advisories" in doc else None,
        adoption={"metric": "downloads last 90 days", "value": (doc.get("downloads") or {}).get("recent")},
        url=f"https://hex.pm/packages/{name}",
    )


LOOKUPS: dict[str, Callable[[str], dict]] = {
    "npm": lookup_npm, "pypi": lookup_pypi, "crates": lookup_crates, "go": lookup_go, "maven": lookup_maven,
    "packagist": lookup_packagist, "rubygems": lookup_rubygems, "nuget": lookup_nuget, "hex": lookup_hex,
}


def search(registry: str, query: str, size: int = 10) -> list[dict]:
    q = _q(query)
    if registry == "npm":
        r = http_get(f"https://registry.npmjs.org/-/v1/search?text={q}&size={size}")
        return [] if r.error else [{"name": o["package"]["name"], "version": o["package"].get("version"),
                                    "description": o["package"].get("description"),
                                    "adoption": (o.get("downloads") or {}).get("monthly")} for o in r.json().get("objects", [])]
    if registry == "crates":
        r = http_get(f"https://crates.io/api/v1/crates?q={q}&per_page={size}")
        return [] if r.error else [{"name": c["name"], "version": c.get("max_stable_version"), "description": c.get("description"),
                                    "adoption": c.get("recent_downloads")} for c in r.json().get("crates", [])]
    if registry == "go":
        r = http_get(f"https://pkg.go.dev/v1/search?q={q}&limit={size}")
        return [] if r.error else [{"name": i.get("modulePath"), "package": i.get("packagePath"), "version": i.get("version"),
                                    "description": i.get("synopsis"),
                                    "adoption": (i.get("importedByCounts") or {}).get("packages")} for i in r.json().get("items", [])]
    if registry == "packagist":
        r = http_get(f"https://packagist.org/search.json?q={q}&per_page={size}")
        return [] if r.error else [{"name": p["name"], "description": p.get("description"), "adoption": p.get("downloads")}
                                   for p in r.json().get("results", [])]
    if registry == "rubygems":
        r = http_get(f"https://rubygems.org/api/v1/search.json?query={q}")
        return [] if r.error else [{"name": g["name"], "version": g.get("version"), "description": g.get("info"),
                                    "adoption": g.get("downloads")} for g in r.json()[:size]]
    if registry == "nuget":
        r = http_get(f"https://azuresearch-usnc.nuget.org/query?q={q}&take={size}&prerelease=false&semVerLevel=2.0.0")
        return [] if r.error else [{"name": d["id"], "version": d.get("version"), "description": d.get("description"),
                                    "adoption": d.get("totalDownloads")} for d in r.json().get("data", [])]
    if registry == "hex":
        r = http_get(f"https://hex.pm/api/packages?search={q}&sort=downloads")
        return [] if r.error else [{"name": p["name"], "version": p.get("latest_stable_version"),
                                    "description": (p.get("meta") or {}).get("description"),
                                    "adoption": (p.get("downloads") or {}).get("recent")} for p in r.json()[:size]]
    if registry == "maven":
        r = http_get(f"https://search.maven.org/solrsearch/select?q={q}&rows={size}&wt=json", timeout=35)
        return [] if r.error else [{"name": f"{d['g']}:{d['a']}", "version": d.get("latestVersion"),
                                    "description": None, "adoption": None} for d in r.json().get("response", {}).get("docs", [])]
    raise PorterError(f"{registry} has no search API; use web search to find names, then porter.py registry lookup", code=1)


# ------------------------------------------------------------------ cache

def cache_path(cache_dir: Path, registry: str, name: str) -> Path:
    return Path(cache_dir) / (registry or "unknown") / (_q(name.lower()) + ".json")


def lookup(registry: str, name: str, cache_dir: Path | None, ttl_hours: float = 24, offline: bool = False,
           refresh: bool = False) -> dict:
    if registry not in LOOKUPS:
        raise PorterError(f"unknown registry '{registry}'. Known: {', '.join(REGISTRIES)}")
    path = cache_path(cache_dir, registry, name) if cache_dir else None
    if path and path.exists() and not refresh:
        cached = read_json(path)
        age = time.time() - path.stat().st_mtime
        if offline or age < ttl_hours * 3600:
            cached["cached"] = True
            return cached
    if offline:
        return _result(registry, name, error="offline and not cached")
    result = LOOKUPS[registry](name)
    if path and result.get("exists") is not None:
        write_json(path, result)
    result["cached"] = False
    return result


# ------------------------------------------------------------------ deps.json verification

COPYLEFT_STRONG = re.compile(r"\b(A?GPL)", re.I)
COPYLEFT_WEAK = re.compile(r"\b(LGPL|MPL|EPL|CDDL)", re.I)


def _older_than(date: str | None, days: int) -> bool:
    try:
        when = dt.date.fromisoformat(str(date)[:10])
    except ValueError:
        return False
    return (dt.date.fromisoformat(now_iso()[:10]) - when).days > days


def license_compat(candidate: str | None, port_license: str | None) -> dict:
    if not candidate:
        return {"spdx": None, "compatible": None, "note": "license unknown; check the repository"}
    strong = bool(COPYLEFT_STRONG.search(candidate)) and not re.search(r"\bOR\b", candidate)
    port_strong = bool(port_license and COPYLEFT_STRONG.search(port_license))
    if strong and not port_strong:
        return {"spdx": candidate, "compatible": False, "note": "strong copyleft dependency in a permissive port"}
    if COPYLEFT_WEAK.search(candidate):
        return {"spdx": candidate, "compatible": True, "note": "weak copyleft: fine as a dependency, not for copying code"}
    return {"spdx": candidate, "compatible": True, "note": None}


PERMISSIVE = re.compile(r"\b(MIT|ISC|BSD|Apache|0BSD|Unlicense|CC0|Zlib|PSF|Python Software Foundation|BSL-1\.0|Boost)", re.I)


def copy_license(lic: str | None, port_license: str | None) -> dict:
    """License check for PORT and VENDOR: the dependency's own code ends up in the port."""
    if not lic:
        return {"spdx": None, "compatible": None, "note": "license unknown: check it before copying code"}
    options = re.split(r"\s+OR\s+", lic)
    if any(PERMISSIVE.search(o) or (port_license and o.strip().lower() == port_license.lower()) for o in options):
        return {"spdx": lic, "compatible": True, "note": None}
    return {"spdx": lic, "compatible": False, "note": "porting or vendoring copies code under these terms into the port"}


def verify_deps(ws: Path, offline: bool = False, refresh: bool = False) -> list[str]:
    deps = read_json(ws / "deps.json")
    cfg = read_json(ws / "config.json")
    ttl = cfg.get("options", {}).get("registryTtlHours", 24)
    target_registry = deps.get("target", {}).get("registry")
    port_license = (cfg["source"].get("license") or {}).get("spdx")
    source_registry = REGISTRY_OF.get(cfg["source"].get("language") or "")
    report = []
    for d in deps["dependencies"]:
        if d["decision"] in ("PORT", "VENDOR") and source_registry:
            res = lookup(source_registry, d["name"], ws / "cache" / "registry", ttl, offline, refresh)
            if res.get("exists") is True:
                d["sourceLicense"] = copy_license(res.get("license"), port_license)
                if d["sourceLicense"]["compatible"] is False:
                    report.append(f"{d['name']}: {d['decision']} copies code licensed {res.get('license')}; this becomes a gate item")
        cand = d.get("candidate") or {}
        if d["decision"] not in ("MAP", "SHIM") or not cand.get("name"):
            d.setdefault("verified", {"registryLookup": False, "status": "NOT_APPLICABLE",
                                      "reason": "no registry candidate for this decision", "fetchedAt": None})
            continue
        registry = cand.get("registry") or target_registry
        cand["registry"] = registry
        res = lookup(registry, cand["name"], ws / "cache" / "registry", ttl, offline, refresh)
        if res.get("exists") is True:
            cand["version"] = cand.get("version") or res.get("latestVersion")
            cand["license"] = res.get("license")
            cand["lastRelease"] = res.get("latestReleaseDate")
            d["verified"] = {"registryLookup": True, "status": "VERIFIED", "fetchedAt": res.get("fetchedAt"),
                             "reason": None}
            d["license"] = license_compat(res.get("license"), port_license)
            notes = []
            if res.get("deprecated"):
                notes.append(f"deprecated: {res['deprecated']}")
                d["gate"] = True
            if res.get("advisories"):
                notes.append(f"{res['advisories']} known advisories")
            if _older_than(res.get("latestReleaseDate"), days=730):
                notes.append(f"no release in two years (last {res['latestReleaseDate'][:10]})")
            report.append(f"{d['name']}: {cand['name']}@{res.get('latestVersion')} on {registry} VERIFIED"
                          + (f" ({'; '.join(notes)})" if notes else ""))
            if notes:
                d["notes"] = "; ".join(x for x in [d.get("notes"), *notes] if x)
        elif res.get("exists") is False:
            d["verified"] = {"registryLookup": True, "status": "NOT_FOUND", "fetchedAt": res.get("fetchedAt"),
                             "reason": f"{cand['name']} does not exist on {registry}"}
            report.append(f"{d['name']}: {cand['name']} NOT FOUND on {registry}; pick another candidate or change the decision")
        else:
            d["verified"] = {"registryLookup": False, "status": "UNVERIFIED", "fetchedAt": None,
                             "reason": res.get("error") or "lookup failed"}
            report.append(f"{d['name']}: {cand['name']} UNVERIFIED ({res.get('error')}); this becomes a gate item")
    write_json(ws / "deps.json", deps)
    return report


# ------------------------------------------------------------------ commands

def _fmt(res: dict) -> str:
    if res.get("exists") is False:
        return f"{res['registry']}:{res['name']} does NOT exist"
    if res.get("error"):
        return f"{res['registry']}:{res['name']} lookup failed: {res['error']}"
    adoption = res.get("adoption") or {}
    parts = [
        f"{res['registry']}:{res['name']} {res.get('latestVersion')}",
        f"released {str(res.get('latestReleaseDate') or '?')[:10]}",
        f"license {res.get('license') or '?'}",
        f"versions {res.get('versionsCount') or '?'}",
    ]
    if adoption.get("value") is not None:
        parts.append(f"{adoption['metric']} {adoption['value']}")
    if res.get("deprecated"):
        parts.append(f"DEPRECATED {res['deprecated']}")
    if res.get("advisories"):
        parts.append(f"advisories {res['advisories']}")
    if res.get("cached"):
        parts.append("(cached)")
    return ", ".join(parts)


def cmd_registry(args: argparse.Namespace) -> int:
    ws = None
    try:
        ws = find_workspace(args.workspace)
    except PorterError:
        if args.action == "verify-deps":
            raise
    cache = ws / "cache" / "registry" if ws and not args.no_cache else None
    if args.action == "lookup":
        results = [lookup(args.registry, n, cache, args.ttl, args.offline, args.refresh) for n in args.names]
        if args.json:
            emit(results, True)
        else:
            for res in results:
                print(_fmt(res))
        return 1 if any(r.get("exists") is not True for r in results) else 0
    if args.action == "search":
        results = search(args.registry, " ".join(args.names), args.size)
        if args.json:
            emit(results, True)
        else:
            for r in results:
                print(f"{r['name']}  {r.get('version') or ''}  adoption={r.get('adoption')}  {(r.get('description') or '')[:90]}")
            print("\nSearch results are leads only. Confirm each with: porter.py registry lookup")
        return 0
    if args.action == "verify-deps":
        for line in verify_deps(ws, args.offline, args.refresh):
            print(line)
        deps = read_json(ws / "deps.json")["dependencies"]
        statuses = [(d.get("verified") or {}).get("status") or "NONE" for d in deps]
        print("verify-deps: " + (", ".join(f"{statuses.count(s)} {s}" for s in sorted(set(statuses))) or "no dependencies"))
        return 1 if "NOT_FOUND" in statuses else 0
    return 2


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "registry", help="look up and search package registries; verify deps.json candidates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="lookup NAME...   one record per name: latest version, release date, license, adoption, deprecation.\n"
                    "                 Exit 1 when any name does not exist or the lookup failed (the output is still complete).\n"
                    "search WORDS...  candidate names from the registry's search; leads only, confirm each with lookup.\n"
                    "verify-deps      inside a workspace: look up every MAP and SHIM candidate in deps.json, record\n"
                    "                 license compatibility and maintenance notes, and check the source license of\n"
                    "                 every PORT and VENDOR dependency. Writes deps.json; postflight deps needs it.")
    p.add_argument("action", choices=("lookup", "search", "verify-deps"))
    p.add_argument("names", nargs="*", help="package names (lookup) or search words (search)")
    p.add_argument("--registry", choices=REGISTRIES)
    p.add_argument("--workspace")
    p.add_argument("--offline", action="store_true", help="use cached records only")
    p.add_argument("--refresh", action="store_true", help="ignore cache age")
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--ttl", type=float, default=24, help="cache age in hours before refetching")
    p.add_argument("--size", type=int, default=10)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_registry)
