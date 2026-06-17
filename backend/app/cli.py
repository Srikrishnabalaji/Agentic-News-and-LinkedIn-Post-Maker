"""Command-line entrypoint for the Railway cron job.

Run the full daily pipeline once and exit:

    python -m app.cli run

This is the Railway-native scheduling path: a cron service runs this
command at 11 AM, sharing the same code and DATABASE_URL as the API.
"""
from __future__ import annotations

import logging
import sys

from .db import SessionLocal, init_db
from .pipeline import run_pipeline

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger("cli")


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    cmd = argv[0] if argv else "run"

    if cmd != "run":
        log.error("Unknown command %r (expected 'run')", cmd)
        return 2

    init_db()
    db = SessionLocal()
    try:
        result = run_pipeline(db)
        log.info("Done: run_id=%d posts=%d email_sent=%s",
                 result.run_id, result.num_posts, result.email_sent)
        return 0
    except Exception:
        log.exception("Pipeline failed")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
