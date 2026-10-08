from pathlib import Path
from fastapi import APIRouter, HTTPException
import json


eval_router = APIRouter()

RUNS_DIR = Path('eval_runs')


@eval_router.get("/runs")
def list_runs() -> dict:
    """Every saved run: filename + config + aggregate metrics.
 
    Per-question rows are NOT included here -- a --full run file is
    ~100KB and the comparison view only needs the aggregates. The
    detail endpoint below serves one full file on demand.
    """
    runs = []
    for path in RUNS_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue  # a half-written or corrupt file must not kill the list
        if not isinstance(data, dict):
            continue
 
        config = data.get("config", {})
        # Runs saved before the "search" field existed were all vector.
        config.setdefault("search", "vector")
 
        runs.append(
            {
                "file": path.name,
                "config": config,
                "aggregates": data.get("aggregates", {}),
            }
        )
 
    runs.sort(key=lambda r: r["config"].get("timestamp", ""), reverse=True)
    return {"runs": runs}


@eval_router.get("/runs/{name}")
def get_run(name: str) -> dict:
    """One full run file, per-question rows included."""
    # The name becomes a filesystem path: refuse anything that could
    # escape eval_runs/ (path traversal), and only serve .json.
    if "/" in name or "\\" in name or ".." in name or not name.endswith(".json"):
        raise HTTPException(status_code=400, detail="invalid run name")
    path = RUNS_DIR / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="run not found")
    return json.loads(path.read_text(encoding="utf-8"))
