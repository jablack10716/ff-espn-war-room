"""Supabase Client Singleton Wrapper.

Provides thread-safe access to the Supabase Postgres and Realtime client.
"""

from __future__ import annotations

import os
import threading
from typing import Optional

from dotenv import load_dotenv
from supabase import Client, create_client

_CLIENT_LOCK = threading.Lock()
_SUPABASE_CLIENT: Optional[Client] = None


def get_supabase_client() -> Client:
    """Get or initialize the global Supabase client singleton."""
    global _SUPABASE_CLIENT

    if _SUPABASE_CLIENT is not None:
        return _SUPABASE_CLIENT

    with _CLIENT_LOCK:
        if _SUPABASE_CLIENT is not None:
            return _SUPABASE_CLIENT

        load_dotenv()
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

        if not url or not key:
            raise ValueError(
                "Missing required environment variables: SUPABASE_URL and/or SUPABASE_KEY."
            )

        _SUPABASE_CLIENT = create_client(url, key)
        return _SUPABASE_CLIENT
