"""Read-only, bounded run diagnostics. No credentials, request bodies or AI data."""

import os
import math
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from .projects import ProjectError, load_project
from .workflow import load_run

STARTED = time.monotonic()
MAX_RUNS = 20


def redact(text, token=""):
    if not isinstance(text, str):
        return ""
    if token:
        text = text.replace(token, "[redacted]")
    text = re.sub(r"(?i)(bearer\s+)[^\s\"',;]+", r"\1[redacted]", text)
    text = re.sub(r'''(?i)((?:api[_-]?key|x-parkhaven-session|token)\s*["']?\s*[:=]\s*["']?)[^\s"',;]+''',
                  r"\1[redacted]", text)
    return text[:4000]


def developer_status(projects_root: Path, token=""):
    payload = {
        "server_time": datetime.now(timezone.utc).isoformat(),
        "process_id": os.getpid(),
        "uptime_seconds": round(time.monotonic() - STARTED, 1),
        "runs": [],
        "warnings": [],
        "limit": MAX_RUNS,
    }
    try:
        candidates = sorted(projects_root.glob("*/runs/*/job.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    except OSError:
        payload["warnings"].append("De projectmap kon niet volledig worden gelezen.")
        return payload
    # Limit parsing/work per poll; recent damaged records are reported, never fatal to the panel.
    for path in candidates[:MAX_RUNS]:
        project_id, run_id = path.parents[2].name, path.parent.name
        try:
            job = load_run(projects_root, project_id, run_id)
            project = load_project(projects_root, project_id)
        except (ProjectError, OSError):
            payload["warnings"].append("Een recente project- of runstatus kon niet worden gelezen.")
            continue
        warnings = job.get("warnings", [])
        pid = job.get("rhino_process_id")
        timings = job.get("step_seconds", {})
        payload["runs"].append({
            "project_id": project_id,
            "project_name": redact(project.get("name"), token),
            "run_id": run_id,
            "status": redact(job.get("status"), token),
            "created_at": redact(job.get("created_at"), token),
            "updated_at": redact(job.get("updated_at"), token),
            "phase_started_at": redact(job.get("phase_started_at") or job.get("updated_at"), token),
            "progress_step": redact(job.get("progress_step"), token),
            "progress_detail": redact(job.get("progress_detail"), token),
            "progress_at": redact(job.get("progress_at"), token),
            "step_seconds": {redact(key, token)[:80]: value for key, value in list(timings.items())[:20]
                             if type(value) in (int, float) and 0 <= value < 1e9 and math.isfinite(value)}
                if isinstance(timings, dict) else {},
            "rhino_process_id": pid if type(pid) is int and 0 < pid <= 2147483647 else None,
            "error": redact(job.get("error"), token),
            "warnings": [redact(value, token) for value in warnings[:10] if isinstance(value, str)]
                if isinstance(warnings, list) else [],
        })
    return payload
