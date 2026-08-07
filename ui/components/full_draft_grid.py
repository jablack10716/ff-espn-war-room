from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import pandas as pd
import streamlit as st
from services.action_logger import log_action
from ui.components.keeper_manager import calculate_keeper_pick_no


def _format_short_name(full_name: str) -> str:
    """Format 'Jalen Hurts' into 'J. Hurts' to fit cleanly in matrix cells."""
    parts = full_name.split()
    if len(parts) >= 2 and not parts[0].endswith("."):
        return f"{parts[0][0]}. {' '.join(parts[1:])}"
    return full_name


def _format_short_team(slot: int, name: str, max_len: int = 10) -> str:
    """Format team header e.g. '3: Killer Kow...' to prevent horizontal scrolling."""
    clean_name = name
    if len(clean_name) > max_len:
        clean_name = clean_name[: max_len - 1] + "…"
    return f"{slot}: {clean_name}"


if hasattr(st, "dialog"):
    @st.dialog("✏️ Manage Draft Pick")
    def _manage_pick_dialog(
        pick_no: int,
        round_no: int,
        team_slot: int,
        team_name: str,
        existing_event: Optional[Dict[str, Any]],
        available_players: List[Dict[str, Any]],
        user_team_slot: int,
        on_record_pick: Optional[Callable[[int, int, int, str, str, str, bool], None]],
        on_delete_specific_pick: Optional[Callable[[int], None]],
    ) -> None:
        """Modal dialog to add, edit, or vacate a specific pick directly from the grid matrix."""
        log_action("DIALOG_RENDERED", f"Opened pick editor for Pick #{pick_no}", {"pick_no": pick_no, "round_no": round_no, "team_slot": team_slot, "team_name": team_name})
        st.markdown(f"### Pick #{pick_no} (Round {round_no})")
        st.caption(f"Team: **{team_name}** (Slot {team_slot})")

        if existing_event:
            player_name = existing_event.get("player_name", "Unknown")
            pos = existing_event.get("position", "")
            is_user = existing_event.get("picked_by_user", False)
            is_keeper = (
                existing_event.get("source") == "keeper"
                or "keeper" in str(existing_event.get("notes", "")).lower()
            )
            tag = "🔒 Keeper" if is_keeper else ("⭐ Your Pick" if is_user else "👤 Opponent Pick")

            st.info(f"**Current Drafted Player**: **{player_name}** ({pos}) — *{tag}*")
            st.markdown("#### 🔄 Swap to a New Player")
        else:
            st.subheader("Assign Player to Pick")

        if available_players:
            player_options = {
                f"{(p.get('full_name') or p.get('player_name'))} ({p.get('position')} - {p.get('team', 'FA')})": p
                for p in available_players
                if (p.get("full_name") or p.get("player_name"))
            }
            selected_label = st.selectbox(
                "Search and select replacement player:" if existing_event else "Search and select player:",
                options=["-- Select Player --"] + list(player_options.keys()),
                key=f"modal_player_select_{pick_no}",
            )

            is_user_turn = (team_slot == user_team_slot)
            if is_user_turn:
                st.caption("⭐ **YOUR TURN**: Will be automatically added to your roster.")
            else:
                st.caption(f"👤 Assigned to {team_name}.")

            save_btn_label = "💾 Save Replacement Player" if existing_event else "💾 Save Pick"
            if st.button(save_btn_label, type="primary", use_container_width=True, key=f"modal_save_btn_{pick_no}"):
                log_action("DIALOG_SAVE_CLICKED", f"User clicked save pick #{pick_no}", {"selected_label": selected_label})
                if selected_label and selected_label != "-- Select Player --":
                    player = player_options[selected_label]
                    p_name = player.get("full_name") or player.get("player_name") or "Unknown"
                    p_id = str(player.get("player_id", ""))
                    p_pos = str(player.get("position", ""))

                    st.session_state["grid_dialog_force_close_once"] = True
                    st.session_state["active_grid_pick_no"] = None
                    st.session_state["fallback_active_grid_pick_no"] = None

                    if on_record_pick:
                        on_record_pick(
                            pick_no,
                            round_no,
                            team_slot,
                            p_id,
                            p_name,
                            p_pos,
                            is_user_turn,
                        )
                    else:
                        st.rerun()
                else:
                    st.warning("⚠️ Please select a player from the dropdown list before saving.")

        if existing_event:
            st.markdown("---")
            with st.expander("🗑️ Danger Zone: Erase Pick & Leave Blank"):
                st.caption("Warning: This will permanently delete the pick from this slot and return the player to the available pool.")
                if st.button("🗑️ Erase Pick & Leave Blank", type="secondary", use_container_width=True, key=f"modal_vacate_btn_{pick_no}"):
                    log_action("DIALOG_VACATE_CLICKED", f"User clicked vacate pick #{pick_no}")
                    st.session_state["grid_dialog_force_close_once"] = True
                    st.session_state["active_grid_pick_no"] = None
                    st.session_state["fallback_active_grid_pick_no"] = None
                    if on_delete_specific_pick:
                        on_delete_specific_pick(pick_no)
                    else:
                        st.rerun()

        st.markdown("---")
        if st.button("❌ Cancel / Close", type="secondary", use_container_width=True, key=f"dialog_cancel_{pick_no}"):
            log_action("DIALOG_CANCEL_CLICKED", f"User clicked cancel pick #{pick_no}")
            st.session_state["grid_dialog_force_close_once"] = True
            st.session_state["active_grid_pick_no"] = None
            st.session_state["fallback_active_grid_pick_no"] = None
            st.rerun()


def _get_round_and_slot_from_pick_no(p_no: int, num_teams: int, is_3rr: bool) -> tuple[int, int]:
    """Calculate round_no and team_slot from pick_no."""
    r = ((p_no - 1) // num_teams) + 1
    p_in_r = (p_no - 1) % num_teams
    if is_3rr:
        if r == 1:
            is_even = False
        elif r in (2, 3):
            is_even = True
        else:
            is_even = (r % 2 == 1)
    else:
        is_even = (r % 2 == 0)
    s = (num_teams - p_in_r) if is_even else (p_in_r + 1)
    return r, s


def render_full_draft_grid(
    draft_log: List[Dict[str, Any]],
    available_players: Optional[List[Dict[str, Any]]] = None,
    on_record_pick: Optional[Callable[[int, int, int, str, str, str, bool], None]] = None,
    on_delete_specific_pick: Optional[Callable[[int], None]] = None,
    user_team_slot: int = 1,
    espn_teams: Optional[List[Dict[str, Any]]] = None,
    num_teams: int = 12,
    is_3rr: bool = False,
    total_rounds: int = 16,
) -> None:
    """Render 2D Full Draft Board Matrix (Rounds vs Teams) with interactive cell selection."""
    st.subheader("📊 Full Draft Board Grid")
    st.caption(
        "Interactive matrix view. **Click any cell** to edit, swap, or clear a pick. Condensed to fit your display."
    )

    if hasattr(st, "dialog") and "active_grid_pick_no" not in st.session_state:
        st.session_state["active_grid_pick_no"] = None
    if hasattr(st, "dialog") and "grid_dialog_force_close_once" not in st.session_state:
        st.session_state["grid_dialog_force_close_once"] = False

    # Build team slot -> team name mapping
    raw_slot_to_name: Dict[int, str] = {}
    if espn_teams:
        raw_slot_to_name = {
            int(t["team_slot"]): str(t.get("team_name", f"Team {t['team_slot']}"))
            for t in espn_teams
            if "team_slot" in t
        }

    for s in range(1, num_teams + 1):
        if s not in raw_slot_to_name:
            raw_slot_to_name[s] = f"Team {s}"

    # Condensed column headers for no-scroll display
    team_headers = [
        _format_short_team(s, raw_slot_to_name[s]) for s in range(1, num_teams + 1)
    ]
    header_to_slot = {
        team_headers[s - 1]: s for s in range(1, num_teams + 1)
    }

    # Index draft log by pick_no and by (round_no, team_slot)
    pick_map: Dict[int, Dict[str, Any]] = {}
    slot_round_map: Dict[tuple[int, int], Dict[str, Any]] = {}

    for e in draft_log:
        if str(e.get("event_type", "PICK")).upper() == "PICK":
            p_no = e.get("pick_no")
            if p_no is not None:
                pick_map[int(p_no)] = e
            r_no = e.get("round_no")
            s_no = e.get("team_slot")
            if r_no is not None and s_no is not None:
                slot_round_map[(int(r_no), int(s_no))] = e

    # Fallback to fetching available players if not provided
    if not available_players:
        try:
            from services.draft_state_service import DraftStateService
            svc = DraftStateService(use_supabase=True)
            available_players = svc.get_available_players(st.session_state.get("draft_id", "live_draft_2026"))
        except Exception:
            available_players = []

    # ── 1. SUMMARY METRICS ────────────────────────────────────────────────────
    total_picks_possible = num_teams * total_rounds
    picks_logged = len(pick_map)
    user_picks = len([p for p in pick_map.values() if p.get("picked_by_user")])
    keepers_count = len(
        [
            p
            for p in pick_map.values()
            if p.get("source") == "keeper"
            or "keeper" in str(p.get("notes", "")).lower()
        ]
    )

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Picks Logged", f"{picks_logged} / {total_picks_possible}")
    with m2:
        progress_pct = (
            round((picks_logged / total_picks_possible) * 100, 1)
            if total_picks_possible > 0
            else 0.0
        )
        st.metric("Draft Progress", f"{progress_pct}%")
    with m3:
        st.metric("User Roster Picks", f"{user_picks}")
    with m4:
        st.metric("Pre-Draft Keepers", f"{keepers_count}")

    st.markdown("---")



    # ── 3. INTERACTIVE NATIVE BUTTON MATRIX ──────────────────────────────────
    st.caption("👇 **Click any pick button below** to edit, assign, or clear a pick. Instant 1-click modal!")

    # Team Headers Row
    header_cols = st.columns([1] + [3] * num_teams)
    with header_cols[0]:
        st.caption("**Rnd**")
    for s in range(1, num_teams + 1):
        with header_cols[s]:
            st.caption(f"**{_format_short_team(s, raw_slot_to_name[s])}**")

    # Grid Rows
    for r in range(1, total_rounds + 1):
        row_cols = st.columns([1] + [3] * num_teams)
        with row_cols[0]:
            st.markdown(f"**R{r}**")

        for s in range(1, num_teams + 1):
            calc_p_no = calculate_keeper_pick_no(
                round_no=r, team_slot=s, num_teams=num_teams, is_3rr=is_3rr
            )
            event = pick_map.get(calc_p_no) or slot_round_map.get((r, s))

            if event:
                player_name = event.get("player_name") or event.get("full_name") or "Unknown"
                pos = event.get("position", "")
                is_user = event.get("picked_by_user", False)
                is_keeper = (
                    event.get("source") == "keeper"
                    or "keeper" in str(event.get("notes", "")).lower()
                )
                tag = "🔒" if is_keeper else ("⭐" if is_user else "👤")
                short_p = _format_short_name(player_name)
                btn_label = f"{tag} {short_p} ({pos})"
                btn_type = "primary" if is_user else "secondary"
            else:
                btn_label = f"#{calc_p_no}"
                btn_type = "secondary"

            with row_cols[s]:
                if st.button(
                    btn_label,
                    key=f"grid_pick_btn_{r}_{s}_{calc_p_no}",
                    type=btn_type,
                    use_container_width=True,
                ):
                    if hasattr(st, "dialog"):
                        st.session_state["active_grid_pick_no"] = calc_p_no
                        st.rerun()
                    else:
                        st.session_state["fallback_active_grid_pick_no"] = calc_p_no

    if hasattr(st, "dialog"):
        if st.session_state.get("grid_dialog_force_close_once"):
            st.session_state["grid_dialog_force_close_once"] = False
            st.session_state["active_grid_pick_no"] = None

        active_p_no = st.session_state.get("active_grid_pick_no")
        if active_p_no is not None:
            active_round, active_slot = _get_round_and_slot_from_pick_no(
                active_p_no, num_teams, is_3rr
            )
            active_team_name = raw_slot_to_name.get(active_slot, f"Team {active_slot}")
            active_event = pick_map.get(active_p_no) or slot_round_map.get(
                (active_round, active_slot)
            )

            _manage_pick_dialog(
                pick_no=active_p_no,
                round_no=active_round,
                team_slot=active_slot,
                team_name=active_team_name,
                existing_event=active_event,
                available_players=available_players or [],
                user_team_slot=user_team_slot,
                on_record_pick=on_record_pick,
                on_delete_specific_pick=on_delete_specific_pick,
            )

    # ── 4. FALLBACK EDITOR FOR OLDER STREAMLIT VERSIONS ──────────────────────
    if not hasattr(st, "dialog"):
        active_p_no = st.session_state.get("fallback_active_grid_pick_no")
        if active_p_no is not None:
            active_round, active_slot = _get_round_and_slot_from_pick_no(
                active_p_no, num_teams, is_3rr
            )
            active_team_name = raw_slot_to_name.get(active_slot, f"Team {active_slot}")
            active_event = pick_map.get(active_p_no) or slot_round_map.get(
                (active_round, active_slot)
            )

            st.markdown("---")
            with st.container(border=True):
                hdr_col, close_col = st.columns([5, 1])
                with hdr_col:
                    st.markdown(f"### ✏️ Pick #{active_p_no} — Round {active_round}, **{active_team_name}**")
                with close_col:
                    if st.button("❌ Close", key=f"close_editor_{active_p_no}", use_container_width=True):
                        st.session_state["fallback_active_grid_pick_no"] = None
                        st.rerun()

                if active_event:
                    player_name = active_event.get("player_name") or active_event.get("full_name") or "Unknown"
                    pos = active_event.get("position", "")
                    is_user = active_event.get("picked_by_user", False)
                    is_keeper = (
                        active_event.get("source") == "keeper"
                        or "keeper" in str(active_event.get("notes", "")).lower()
                    )
                    tag = "🔒 Keeper" if is_keeper else ("⭐ Your Pick" if is_user else "👤 Opponent Pick")
                    st.info(f"**Currently Drafted**: **{player_name}** ({pos}) — *{tag}*")

                    if st.button("🗑️ Vacate / Clear Pick", type="secondary", key=f"clear_pick_{active_p_no}"):
                        st.session_state["fallback_active_grid_pick_no"] = None
                        if on_delete_specific_pick:
                            on_delete_specific_pick(active_p_no)
                        else:
                            st.rerun()
                else:
                    st.success(f"**Pick #{active_p_no}** is currently **empty**. Assign a player below.")

                if available_players:
                    player_options = {
                        f"{(p.get('full_name') or p.get('player_name'))} ({p.get('position')} - {p.get('team', 'FA')})": p
                        for p in available_players
                        if (p.get('full_name') or p.get('player_name'))
                    }
                    selected_label = st.selectbox(
                        "🔍 Search and select player:",
                        options=["-- Select Player --"] + list(player_options.keys()),
                        key=f"editor_select_{active_p_no}",
                    )
                    is_user_turn = (active_slot == user_team_slot)
                    if st.button("💾 Save Pick", type="primary", use_container_width=True, key=f"save_pick_{active_p_no}"):
                        if selected_label and selected_label != "-- Select Player --":
                            player = player_options[selected_label]
                            p_name = player.get("full_name") or player.get("player_name") or "Unknown"
                            p_id = str(player.get("player_id", ""))
                            p_pos = str(player.get("position", ""))
                            st.session_state["fallback_active_grid_pick_no"] = None
                            if on_record_pick:
                                on_record_pick(active_p_no, active_round, active_slot, p_id, p_name, p_pos, is_user_turn)
                            else:
                                st.rerun()
                else:
                    st.warning("No available players in pool to assign.")
