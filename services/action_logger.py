"""Persistent Action Logger for Fantasy Football AI War Room.

Logs UI user interactions, state changes, and modal lifecycles to a local log file
for debugging and trace sharing.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

LOG_FILE = Path(__file__).resolve().parent.parent / "war_room_actions.log"

# Configure dedicated logger
_file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
_file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

_action_logger = logging.getLogger("war_room_actions")
_action_logger.setLevel(logging.INFO)
_action_logger.addHandler(_file_handler)


def log_action(action_type: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Log an interaction or state update with structured details."""
    payload = f"[{action_type.upper()}] {message}"
    if details:
        try:
            payload += f" | Details: {json.dumps(details)}"
        except Exception:
            payload += f" | Details: {details}"
    _action_logger.info(payload)
