"""Analytics pipeline (bronze -> silver -> gold).

Importing the package puts the repo root and backend/ on sys.path, so `python -m pipeline.run`
from the repo root can reuse the backend's settings and models (`from app.config import ...`)
without duplicating them. Python imports this file before any pipeline submodule runs.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT, REPO_ROOT / "backend"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
