"""Live progress reporting for background pipeline runs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlmodel import Session

from app.db import get_engine
from app.models import RunEvent

ProgressCallback = Callable[[str, int, str, dict[str, Any] | None], None]


def record_run_event(
    run_id: int,
    phase: str,
    progress: int,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Persist one progress event in an independent short transaction."""
    with Session(get_engine()) as session:
        session.add(
            RunEvent(
                run_id=run_id,
                phase=phase,
                progress=max(0, min(100, progress)),
                message=message,
                details=details,
            )
        )
        session.commit()


def callback_for_run(run_id: int) -> ProgressCallback:
    """Return a callback bound to one run ID."""

    def publish(
        phase: str,
        progress: int,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        record_run_event(run_id, phase, progress, message, details)

    return publish
