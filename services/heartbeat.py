"""REST Heartbeat Reconciliation Loop.

Polls REST endpoints every 2-3 seconds to verify pick sequence monotonicity
and trigger snapshot reconciliation if WebSocket disconnects or drops events.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Optional, Tuple

from services.supabase_client import get_supabase_client

LOGGER = logging.getLogger("heartbeat")


class HeartbeatWorker:
    """REST heartbeat poller for sequence drift detection and state repair."""

    def __init__(
        self,
        draft_id: str,
        interval_seconds: float = 2.5,
        on_reconcile_required: Optional[Callable[[int], None]] = None,
    ) -> None:
        self.draft_id = draft_id
        self.interval_seconds = interval_seconds
        self.on_reconcile_required = on_reconcile_required

        self.last_seen_pick_no = 0
        self.last_ok_timestamp: float = time.time()
        self.is_healthy = True

    def check_heartbeat(self) -> Tuple[bool, int]:
        """Perform a single REST check of the latest draft log state.

        Returns (is_healthy, latest_pick_no).
        """
        try:
            client = get_supabase_client()
            res = (
                client.table("draft_log")
                .select("pick_no")
                .eq("draft_id", self.draft_id)
                .order("pick_no", desc=True)
                .limit(1)
                .execute()
            )

            latest_pick_no = 0
            if res.data:
                latest_pick_no = int(res.data[0].get("pick_no", 0))

            self.last_ok_timestamp = time.time()
            self.is_healthy = True

            # Drift detection: if latest pick_no jumped by > 1 or lags behind
            if self.last_seen_pick_no > 0 and latest_pick_no != self.last_seen_pick_no:
                LOGGER.warning(
                    "Sequence drift detected: local pick_no=%s, remote pick_no=%s",
                    self.last_seen_pick_no,
                    latest_pick_no,
                )
                if self.on_reconcile_required:
                    self.on_reconcile_required(latest_pick_no)

            self.last_seen_pick_no = latest_pick_no
            return True, latest_pick_no

        except Exception as exc:
            LOGGER.warning("Heartbeat REST check failed: %s", exc)
            # Mark unhealthy if stale > 6 seconds
            if time.time() - self.last_ok_timestamp > 6.0:
                self.is_healthy = False
            return False, self.last_seen_pick_no
