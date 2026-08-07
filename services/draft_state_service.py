"""Draft state management service for Fantasy Football AI War Room.

Handles database operations, local cache reconciliation, pick recording,
and atomic Undo Last Pick transactions via Supabase client.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from services.supabase_client import get_supabase_client

LOGGER = logging.getLogger("draft_state_service")

try:
    from services.action_logger import log_action
except ImportError:
    def log_action(action_type: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        pass


class DraftStateService:
    """Manages active draft state, pick events, and player availability."""

    def __init__(self, use_supabase: bool = True) -> None:
        self.use_supabase = use_supabase
        self._lock = threading.Lock()
        self._local_available_players: Dict[str, Dict[str, Any]] = {}
        self._local_draft_log: Dict[str, List[Dict[str, Any]]] = {}
        self._local_telemetry: List[Dict[str, Any]] = []

    def set_local_players(self, draft_id: str, players: List[Dict[str, Any]]) -> None:
        """Seed or override local player cache for draft_id."""
        with self._lock:
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
        with self._lock:
            return [dict(p) for p in self._local_available_players.values() if p.get("is_available", True)]

    def get_draft_log(self, draft_id: str) -> List[Dict[str, Any]]:
        """Fetch full draft event log ordered by pick_no ASC (deduplicated by pick_no)."""
        if self.use_supabase:
            try:
                client = get_supabase_client()
                response = (
                    client.table("draft_log")
                    .select("*")
                    .eq("draft_id", draft_id)
                    .order("pick_no", desc=False)
                    .order("created_at", desc=False)
                    .execute()
                )
                if response.data is not None:
                    # Deduplicate by pick_no, keeping the latest created_at entry per pick_no
                    latest_by_pick: Dict[int, Dict[str, Any]] = {}
                    for row in response.data:
                        p_no = row.get("pick_no")
                        if p_no is not None:
                            latest_by_pick[int(p_no)] = row
                    return sorted(list(latest_by_pick.values()), key=lambda x: int(x.get("pick_no", 0)))
            except Exception as exc:
                LOGGER.warning("Supabase get_draft_log failed: %s", exc)

        with self._lock:
            local_entries = list(self._local_draft_log.get(draft_id, []))
            local_by_pick: Dict[int, Dict[str, Any]] = {}
            for entry in local_entries:
                p_no = entry.get("pick_no")
                if p_no is not None:
                    local_by_pick[int(p_no)] = entry

            return sorted(
                list(local_by_pick.values()),
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
        telemetry_data: Optional[Dict[str, Any]] = None,
        marcus_pitch: Optional[str] = None,
        winston_pitch: Optional[str] = None,
        arthur_gm_reasoning: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a new player draft pick event and set player unavailable."""
        db_source = source if source in ("manual", "system", "import") else "manual"
        db_notes = notes or ("Pre-draft keeper" if source == "keeper" else None)

        if picked_by_user or telemetry_data or marcus_pitch or winston_pitch or arthur_gm_reasoning:
            self.log_user_pick(
                draft_id=draft_id,
                pick_number=pick_no,
                round_no=round_no,
                selected_player_id=player_id,
                selected_player_name=player_name,
                telemetry_data=telemetry_data,
                marcus_pitch=marcus_pitch,
                winston_pitch=winston_pitch,
                arthur_gm_reasoning=arthur_gm_reasoning,
            )

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
            "source": db_source,
            "notes": db_notes,
        }

        log_action("SERVICE_RECORD_PICK_START", f"Recording pick #{pick_no} for {player_name}", {
            "draft_id": draft_id,
            "pick_no": pick_no,
            "player_id": player_id,
            "source": db_source,
            "use_supabase": self.use_supabase,
        })

        if self.use_supabase:
            try:
                client = get_supabase_client()
                rpc_params = {
                    "p_draft_id": draft_id,
                    "p_pick_no": pick_no,
                    "p_round_no": round_no,
                    "p_team_slot": team_slot,
                    "p_player_id": player_id,
                    "p_player_name": player_name,
                    "p_position": position,
                    "p_team_name": team_name or f"Team {team_slot}",
                    "p_picked_by_user": picked_by_user,
                    "p_source": db_source,
                    "p_notes": db_notes,
                }
                res = client.rpc("record_pick_atomic", rpc_params).execute()
                if res.data and isinstance(res.data, dict):
                    if not res.data.get("success", True):
                        raise RuntimeError(res.data.get("message", "Database rejected atomic pick"))
                    if "pick" in res.data and res.data["pick"]:
                        log_action("SERVICE_RPC_SUCCESS", f"RPC saved pick #{pick_no}")
                        return dict(res.data["pick"])
                log_action("SERVICE_RPC_SUCCESS", f"RPC saved pick #{pick_no}")
                return event_payload
            except Exception as exc:
                LOGGER.warning("RPC record_pick_atomic failed, executing fallback direct write: %s", exc)
                log_action("SERVICE_RPC_FAILED", f"RPC failed, running direct write fallback: {exc}")
                try:
                    # 1. Update player availability if replacing a player in this slot
                    existing = client.table("draft_log").select("player_id").eq("draft_id", draft_id).eq("pick_no", pick_no).execute()
                    if existing.data and len(existing.data) > 0:
                        old_pid = existing.data[0].get("player_id")
                        if old_pid and old_pid != player_id:
                            client.table("available_players").update({"is_available": True}).eq("player_id", old_pid).execute()

                    # 2. Mark new player unavailable
                    client.table("available_players").update({"is_available": False}).eq("player_id", player_id).execute()

                    # 3. Clean replace: delete any existing pick in this slot, then insert new row
                    client.table("draft_log").delete().eq("draft_id", draft_id).eq("pick_no", pick_no).execute()
                    insert_res = client.table("draft_log").insert({
                        "draft_id": draft_id,
                        "pick_no": pick_no,
                        "round_no": round_no,
                        "team_slot": team_slot,
                        "player_id": player_id,
                        "player_name": player_name,
                        "position": position,
                        "team_name": team_name or f"Team {team_slot}",
                        "picked_by_user": picked_by_user,
                        "event_type": "PICK",
                        "source": db_source,
                        "notes": db_notes,
                    }).execute()

                    log_action("SERVICE_DIRECT_WRITE_SUCCESS", f"Direct write saved pick #{pick_no} to Supabase", {"inserted": str(insert_res.data)})
                    return event_payload
                except Exception as inner_exc:
                    LOGGER.error("Direct table write fallback also failed: %s", inner_exc)
                    log_action("SERVICE_DIRECT_WRITE_ERROR", f"Direct table write failed: {inner_exc}", {"error": str(inner_exc)})
                    # Local fallback to memory cache to keep application responsive
                    with self._lock:
                        self._local_draft_log.setdefault(draft_id, []).append(event_payload)
                        if player_id in self._local_available_players:
                            self._local_available_players[player_id]["is_available"] = False
                    return event_payload

        # Local cache update (non-Supabase mode or local fallback)
        with self._lock:
            self._local_draft_log.setdefault(draft_id, []).append(event_payload)
            if player_id in self._local_available_players:
                self._local_available_players[player_id]["is_available"] = False

        return event_payload

    def upsert_pick(
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
        """Create or replace a pick at pick_no using atomic DB RPC or thread-safe local cache."""
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
            return self.record_pick(
                draft_id=draft_id,
                pick_no=pick_no,
                round_no=round_no,
                team_slot=team_slot,
                player_id=player_id,
                player_name=player_name,
                position=position,
                team_name=team_name,
                picked_by_user=picked_by_user,
                source=source,
                notes=notes,
            )

        with self._lock:
            local_log = self._local_draft_log.setdefault(draft_id, [])
            existing_idx: Optional[int] = None
            existing_entry: Optional[Dict[str, Any]] = None
            for idx, e in enumerate(local_log):
                if int(e.get("pick_no", -1)) == int(pick_no):
                    existing_idx = idx
                    existing_entry = e
                    break

            if existing_idx is not None:
                old_player_id = existing_entry.get("player_id") if existing_entry else None
                local_log[existing_idx] = event_payload
                if old_player_id and str(old_player_id) != str(player_id) and old_player_id in self._local_available_players:
                    self._local_available_players[old_player_id]["is_available"] = True
            else:
                local_log.append(event_payload)

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
        with self._lock:
            if draft_id in self._local_draft_log:
                self._local_draft_log[draft_id] = [
                    e for e in self._local_draft_log[draft_id]
                    if int(e.get("pick_no", 0)) != int(latest_pick["pick_no"])
                ]

            if player_id and player_id in self._local_available_players:
                self._local_available_players[player_id]["is_available"] = True

        return latest_pick

    def delete_specific_pick(self, draft_id: str, pick_no: int) -> Optional[Dict[str, Any]]:
        """Delete a specific pick event by pick_no and restore player availability.

        Returns the deleted pick event payload if found, or None.
        """
        log = self.get_draft_log(draft_id)
        target_pick = next((e for e in log if int(e.get("pick_no", -1)) == int(pick_no)), None)

        if not target_pick:
            LOGGER.info("No pick found with pick_no=%s for draft_id=%s", pick_no, draft_id)
            return None

        player_id = target_pick.get("player_id")

        if self.use_supabase:
            try:
                client = get_supabase_client()
                client.table("draft_log").delete().eq("draft_id", draft_id).eq("pick_no", pick_no).execute()
                if player_id:
                    client.table("available_players").update({"is_available": True}).eq("player_id", player_id).execute()
                return target_pick
            except Exception as exc:
                LOGGER.error("Failed to delete specific pick in Supabase: %s", exc)

        with self._lock:
            if draft_id in self._local_draft_log:
                self._local_draft_log[draft_id] = [
                    e for e in self._local_draft_log[draft_id]
                    if int(e.get("pick_no", 0)) != int(pick_no)
                ]

            if player_id and player_id in self._local_available_players:
                self._local_available_players[player_id]["is_available"] = True

        return target_pick

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
        with self._lock:
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
        """Simulate an opponent drafting the top available player by ESPN rank / projection."""
        available = self.get_available_players(draft_id)
        if not available:
            return None

        def _sort_rank(x: Dict[str, Any]) -> float:
            # Filter out placeholder unknown players
            if "unknown" in str(x.get("player_id", "")).lower() or "unknown" in str(x.get("full_name", "")).lower():
                return 99999.0

            # 1. Prefer explicit rank or ADP metrics if available (> 0)
            for field in ["espn_rank", "overall_rank", "consensus_adp", "sleeper_adp", "fantasypros_ecr", "adp"]:
                val = x.get(field)
                if val is not None and float(val) > 0:
                    return float(val)

            # 2. Fallback to projected median points DESC (higher projection = lower sort rank)
            proj = float(x.get("projection_median", 0.0) or 0.0)
            if proj > 0:
                return 10000.0 - proj

            return 99999.0

        sorted_available = sorted(available, key=_sort_rank)
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

    def log_user_pick(
        self,
        draft_id: str,
        pick_number: int,
        round_no: int,
        selected_player_id: str,
        selected_player_name: str,
        telemetry_data: Optional[Dict[str, Any]] = None,
        marcus_pitch: Optional[str] = None,
        winston_pitch: Optional[str] = None,
        arthur_gm_reasoning: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Freeze exact calculations, market context, and LLM pitch outputs and INSERT into draft_decision_telemetry."""
        t_data = telemetry_data or {}
        telemetry_payload = {
            "draft_id": draft_id,
            "pick_number": pick_number,
            "round": round_no,
            "selected_player_id": str(selected_player_id),
            "selected_player_name": str(selected_player_name),
            "ada_rank_recommended": t_data.get("ada_rank_recommended"),
            "ada_composite_score": t_data.get("ada_composite_score"),
            "projected_points_median": t_data.get("projected_points_median"),
            "projected_floor": t_data.get("projected_floor"),
            "projected_ceiling": t_data.get("projected_ceiling"),
            "dynamic_vorp": t_data.get("dynamic_vorp"),
            "opportunity_cost_delta": t_data.get("opportunity_cost_delta"),
            "fcvs_weight_applied": str(t_data.get("fcvs_weight_applied")) if t_data.get("fcvs_weight_applied") is not None else None,
            "hli_multiplier_applied": t_data.get("hli_multiplier_applied"),
            "prv_alert_active": bool(t_data.get("prv_alert_active")) if t_data.get("prv_alert_active") is not None else None,
            "consensus_ecr_rank": t_data.get("consensus_ecr_rank"),
            "adp_at_draft_time": t_data.get("adp_at_draft_time"),
            "adp_survival_prob_to_next_turn": t_data.get("adp_survival_prob_to_next_turn"),
            "qbs_drafted_count": t_data.get("qbs_drafted_count"),
            "rbs_drafted_count": t_data.get("rbs_drafted_count"),
            "wrs_drafted_count": t_data.get("wrs_drafted_count"),
            "marcus_pitch": marcus_pitch or t_data.get("marcus_pitch"),
            "winston_pitch": winston_pitch or t_data.get("winston_pitch"),
            "arthur_gm_reasoning": arthur_gm_reasoning or t_data.get("arthur_gm_reasoning"),
        }

        log_action("TELEMETRY_LOG_START", f"Logging draft decision telemetry for pick #{pick_number}", {
            "draft_id": draft_id,
            "pick_number": pick_number,
            "player_id": selected_player_id,
        })

        if self.use_supabase:
            try:
                client = get_supabase_client()
                client.table("draft_decision_telemetry").insert(telemetry_payload).execute()
                log_action("TELEMETRY_LOG_SUCCESS", f"Telemetry inserted into Supabase for pick #{pick_number}")
            except Exception as exc:
                LOGGER.warning("Failed to insert telemetry into Supabase: %s", exc)

        with self._lock:
            self._local_telemetry.append(telemetry_payload)

        return telemetry_payload

