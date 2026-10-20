#!/usr/bin/env python3
"""AgentPorter CLI. Deterministic helpers for the porting skills. Standard library only, Python 3.11+.

Exit codes: 0 ok, 1 findings or refused transition, 2 usage or environment error.
"""
import sys
from pathlib import Path

if sys.version_info < (3, 11):
    sys.stderr.write("porter.py needs Python 3.11 or newer (it uses tomllib).\n")
    sys.exit(2)

sys.path.insert(0, str(Path(__file__).resolve().parent))

from porterlib.main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
