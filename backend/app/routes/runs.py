"""Pipeline run triggering and history.

  - POST /runs/trigger        : manual trigger from the UI (runs in background)
  - POST /runs/pipeline       : secured endpoint for an HTTP cron (optional;
                                the Railway-native path is the CLI in cli.py)
  - GET  /runs , /runs/latest : run history for the dashboard
"""
from __future__ import annotations

import logging
import threading

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal, get_db
from ..models import DailyRun
from ..pipeline import run_pipeline
from ..schemas import RunOut

log = logging.getLogger(__name__)
router = APIRouter(prefix="/runs", tags=["runs"])

# Guards against overlapping pipeline executions.
_run_lock = threading.Lock()


def _run_in_background():
    if not _run_lock.acquire(blocking=False):
        log.warning("Pipeline already running; ignoring trigger.")
        return
    try:
        db = SessionLocal()
        try:
            run_pipeline(db)
        finally:
            db.close()
    except Exception:
        log.exception("Background pipeline run failed")
    finally:
        _run_lock.release()


@router.post("/trigger")
def trigger_run():
    """Kick off a pipeline run in the background; poll /runs/latest for status."""
    if _run_lock.locked():
        raise HTTPException(409, "A pipeline run is already in progress")
    threading.Thread(target=_run_in_background, daemon=True).start()
    return {"status": "started"}


@router.post("/pipeline")
def cron_pipeline(x_cron_secret: str = Header(default="")):
    """Secured trigger for an HTTP-based cron (optional)."""
    if x_cron_secret != settings.cron_secret:
        raise HTTPException(401, "Invalid cron secret")
    threading.Thread(target=_run_in_background, daemon=True).start()
    return {"status": "started"}


@router.get("", response_model=list[RunOut])
def list_runs(db: Session = Depends(get_db), limit: int = 20):
    return db.execute(
        select(DailyRun).order_by(DailyRun.id.desc()).limit(limit)
    ).scalars().all()


@router.get("/latest", response_model=RunOut | None)
def latest_run(db: Session = Depends(get_db)):
    return db.execute(
        select(DailyRun).order_by(DailyRun.id.desc())
    ).scalars().first()
