"""Supabase Realtime WebSocket Listener Service.

Subscribes to INSERT and DELETE events on public.draft_log and enqueues events
for UI state consumption.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Any, Dict, Optional

from services.supabase_client import get_supabase_client

LOGGER = logging.getLogger("realtime_listener")


class RealtimeListener:
    """Listens for realtime updates on draft_log table via WebSocket."""

    def __init__(self, draft_id: str) -> None:
        self.draft_id = draft_id
        self.event_queue: queue.Queue[Dict[str, Any]] = queue.Queue()
        self.is_connected = False
        self.last_event_ts: Optional[float] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def _handle_realtime_payload(self, payload: Any) -> None:
        """Process incoming Realtime payload."""
        try:
            record = payload.get("new") or payload.get("old") or {}
            event_type = payload.get("eventType") or "INSERT"

            if record.get("draft_id") == self.draft_id or not record.get("draft_id"):
                event_data = {
                    "event_type": event_type,
                    "payload": record,
                    "received_at": payload.get("commit_timestamp"),
                }
                self.event_queue.put(event_data)
                self.is_connected = True
        except Exception as exc:
            LOGGER.error("Error processing realtime payload: %s", exc)

    def start(self) -> None:
        """Start listening for Realtime events."""
        if self.is_connected:
            return

        def _run_listener() -> None:
            try:
                client = get_supabase_client()
                channel = client.channel(f"realtime_draft_{self.draft_id}")
                channel.on_postgres_changes(
                    event="*",
                    schema="public",
                    table="draft_log",
                    callback=self._handle_realtime_payload,
                ).subscribe()
                self.is_connected = True
                LOGGER.info("Supabase Realtime WebSocket listener subscribed for draft_id=%s", self.draft_id)
            except Exception as exc:
                LOGGER.warning("Could not subscribe to Realtime WebSocket: %s", exc)
                self.is_connected = False

        self._thread = threading.Thread(target=_run_listener, daemon=True)
        try:
            from streamlit.runtime.scriptrunner import add_script_run_ctx
            add_script_run_ctx(self._thread)
        except Exception:
            pass
        self._thread.start()

    def stop(self) -> None:
        """Stop listening."""
        self._stop_event.set()
        self.is_connected = False

    def poll_events(self) -> list[Dict[str, Any]]:
        """Retrieve and clear pending events from queue."""
        events: list[Dict[str, Any]] = []
        while not self.event_queue.empty():
            try:
                events.append(self.event_queue.get_nowait())
            except queue.Empty:
                break
        return events
