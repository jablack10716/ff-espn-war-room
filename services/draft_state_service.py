"""Draft state management service for Fantasy Football AI War Room.

Handles database operations, local cache reconciliation, pick recording,
and atomic Undo Last Pick transactions via Supabase client.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from services.supabase_client import get_supabase_client

LOGGER = logging.getLogger("draft_state_service")


class DraftStateService:
    """Manages active draft state, pick events, and player availability."""

    def __init__(self, use_supabase: bool = True) -> None:
        self.use_supabase = use_supabase
        self._local_available_players: Dict[str, Dict[str, Any]] = {}
        self._local_draft_log: Dict[str, List[Dict[str, Any]]] = {}

    def set_local_players(self, draft_id: str, players: List[Dict[str, Any]]) -> None:
        """Seed or override local player cache for draft_id."""
        for p in players:
            pid = str(p.get("player_id"))
            self._local_available_players[pid] = dict(p)

    def get_available_players(self, draft_id: str) -> List[Dict[str, Any]]:
        """Fetch all available players for draft state."""
        if self.use_supabase:
            try:
                client = get_supabase_client()
                response = (
                    client.table("available_players")
                    .select("*")
                    .eq("is_available", True)
                    .execute()
                )
                if response.data is not None:
                    return list(response.data)
            except Exception as exc:
                LOGGER.warning("Supabase get_available_players failed: %s", exc)

        # Fallback to local memory cache
        return [p for p in self._local_available_players.values() if p.get("is_available", True)]

    def get_draft_log(self, draft_id: str) -> List[Dict[str, Any]]:
        """Fetch full draft event log ordered by pick_no ASC."""
        if self.use_supabase:
            try:
                client = get_supabase_client()
                response = (
                    client.table("draft_log")
                    .select("*")
                    .eq("draft_id", draft_id)
                    .order("pick_no", desc=False)
                    .execute()
                )
                if response.data is not None:
                    return list(response.data)
            except Exception as exc:
                LOGGER.warning("Supabase get_draft_log failed: %s", exc)

        return sorted(
            self._local_draft_log.get(draft_id, []),
            key=lambda x: int(x.get("pick_no", 0)),
        )

    def record_pick(
        self,
        draft_id: str,
        pick_no: int,
        round_no: int,
        team_slot: int,
        player_id: str,
        player_name: str,
        position: str,
        team_name: Optional[str] = None,
        picked_by_user: bool = False,
        source: str = "manual",
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a new player draft pick event and set player unavailable."""
        event_payload = {
            "draft_id": draft_id,
            "pick_no": pick_no,
            "round_no": round_no,
            "team_slot": team_slot,
            "team_name": team_name or f"Team {team_slot}",
            "player_id": player_id,
            "player_name": player_name,
            "position": position,
            "picked_by_user": picked_by_user,
            "event_type": "PICK",
            "source": source,
            "notes": notes,
        }

        if self.use_supabase:
            try:
                client = get_supabase_client()
                # Insert pick event
                res_log = client.table("draft_log").insert(event_payload).execute()
                # Mark player unavailable
                client.table("available_players").update({"is_available": False}).eq("player_id", player_id).execute()
                if res_log.data:
                    return dict(res_log.data[0])
            except Exception as exc:
                LOGGER.error("Failed to write pick to Supabase: %s", exc)

        # Local cache update
        self._local_draft_log.setdefault(draft_id, []).append(event_payload)
        if player_id in self._local_available_players:
            self._local_available_players[player_id]["is_available"] = False

        return event_payload

    def undo_last_pick(self, draft_id: str) -> Optional[Dict[str, Any]]:
        """Execute atomic undo of latest PICK event for active draft.

        Returns the undone pick event payload if successful, or None if empty.
        """
        log = self.get_draft_log(draft_id)
        pick_events = [e for e in log if str(e.get("event_type", "PICK")).upper() == "PICK"]

        if not pick_events:
            LOGGER.info("No active pick events to undo for draft_id=%s", draft_id)
            return None

        latest_pick = max(pick_events, key=lambda x: int(x.get("pick_no", 0)))
        player_id = latest_pick.get("player_id")

        if self.use_supabase:
            try:
                client = get_supabase_client()
                # 1. Delete pick row from draft_log
                client.table("draft_log").delete().eq("draft_id", draft_id).eq("pick_no", latest_pick["pick_no"]).execute()
                # 2. Restore player availability in available_players
                if player_id:
                    client.table("available_players").update({"is_available": True}).eq("player_id", player_id).execute()
                return latest_pick
            except Exception as exc:
                LOGGER.error("Failed to execute atomic undo in Supabase: %s", exc)

        # Local cache rollback
        if draft_id in self._local_draft_log:
            self._local_draft_log[draft_id] = [
                e for e in self._local_draft_log[draft_id]
                if int(e.get("pick_no", 0)) != int(latest_pick["pick_no"])
            ]

        if player_id and player_id in self._local_available_players:
            self._local_available_players[player_id]["is_available"] = True

        return latest_pick

    def reset_draft(self, draft_id: str) -> bool:
        """Clear all draft log events for draft_id and reset all player availability."""
        if self.use_supabase:
            try:
                client = get_supabase_client()
                client.table("draft_log").delete().eq("draft_id", draft_id).execute()
                client.table("available_players").update({"is_available": True}).neq("player_id", "").execute()
                LOGGER.info("Reset draft_id=%s in Supabase", draft_id)
            except Exception as exc:
                LOGGER.error("Failed to reset draft in Supabase: %s", exc)

        # Reset local cache
        self._local_draft_log[draft_id] = []
        for p in self._local_available_players.values():
            p["is_available"] = True

        return True

    def simulate_opponent_pick(
        self,
        draft_id: str,
        pick_no: int,
        round_no: int,
        team_slot: int,
    ) -> Optional[Dict[str, Any]]:
        """Simulate an opponent drafting the top available player by ADP."""
        available = self.get_available_players(draft_id)
        if not available:
            return None

        # Sort by ADP ASC
        sorted_available = sorted(
            available,
            key=lambda x: float(x.get("adp") if x.get("adp") is not None else 999.0),
        )
        top_player = sorted_available[0]

        return self.record_pick(
            draft_id=draft_id,
            pick_no=pick_no,
            round_no=round_no,
            team_slot=team_slot,
            player_id=str(top_player["player_id"]),
            player_name=str(top_player["full_name"]),
            position=str(top_player["position"]),
            team_name=f"Team {team_slot}",
            picked_by_user=False,
            source="system",
            notes="Mock draft auto bot pick",
        )

    def reconcile_state(self, draft_id: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Reconcile and return canonical available players and draft log."""
        available = self.get_available_players(draft_id)
        log = self.get_draft_log(draft_id)
        return available, log

