from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORTER = ROOT / "scripts" / "porter.py"
sys.path.insert(0, str(ROOT / "scripts"))


def porter(*args: str, cwd: Path, check: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    proc = subprocess.run([sys.executable, str(PORTER), *args], cwd=cwd, capture_output=True, text=True, env=env)
    if check and proc.returncode != 0:
        raise AssertionError(f"porter {' '.join(args)} failed ({proc.returncode}):\n{proc.stdout}\n{proc.stderr}")
    return proc


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def tiny_python_project(root: Path) -> Path:
    write(root / "pyproject.toml", '[project]\nname = "tinylib"\nversion = "1.2.3"\nlicense = "MIT"\ndependencies = []\n')
    write(root / "LICENSE", "MIT License\n\nPermission is hereby granted, free of charge, to any person obtaining a copy\n")
    write(root / "tinylib" / "__init__.py", "from .core import shout, whisper\n")
    write(root / "tinylib" / "core.py",
          "import re\n\n\ndef _clean(text):\n    return re.sub(r'\\s+', ' ', text).strip()\n\n\n"
          "def shout(text):\n    \"\"\"Upper-case.\"\"\"\n    return _clean(text).upper() + '!'\n\n\n"
          "def whisper(text):\n    return _clean(text).lower()\n")
    write(root / "tests" / "test_core.py", "from tinylib import shout\n\n\ndef test_shout():\n    assert shout('a') == 'A!'\n")
    return root


class TempDir:
    def __enter__(self) -> Path:
        self._td = tempfile.TemporaryDirectory(prefix="porter-test-")
        return Path(self._td.name).resolve()

    def __exit__(self, *exc) -> None:
        self._td.cleanup()
