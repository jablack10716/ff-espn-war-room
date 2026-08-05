"""Streamlit Component: Full Draft Board Grid Matrix (Tab 2)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st
from ui.components.keeper_manager import calculate_keeper_pick_no


def render_full_draft_grid(
    draft_log: List[Dict[str, Any]],
    espn_teams: Optional[List[Dict[str, Any]]] = None,
    num_teams: int = 12,
    is_3rr: bool = False,
    total_rounds: int = 16,
) -> None:
    """Render 2D Full Draft Board Matrix (Rounds vs Teams)."""
    st.subheader("📊 Full Draft Board Grid")
    st.caption(
        "Complete matrix view of all picks across all teams and rounds. Automatically updates live as picks are logged."
    )

    # Build team slot -> team name mapping
    if espn_teams:
        team_headers = [
            f"Slot {t['team_slot']}: {t['team_name']}"
            for t in espn_teams
            if "team_slot" in t and "team_name" in t
        ]
        slot_to_name = {
            int(t["team_slot"]): str(t["team_name"])
            for t in espn_teams
            if "team_slot" in t and "team_name" in t
        }
        if len(team_headers) < num_teams:
            for s in range(len(team_headers) + 1, num_teams + 1):
                team_headers.append(f"Slot {s}: Team {s}")
                slot_to_name[s] = f"Team {s}"
    else:
        team_headers = [f"Slot {s}: Team {s}" for s in range(1, num_teams + 1)]
        slot_to_name = {s: f"Team {s}" for s in range(1, num_teams + 1)}

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

    # Summary Metrics Header
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

    # Build Grid Matrix DataFrame
    matrix_data: Dict[str, List[str]] = {col: [] for col in team_headers}
    row_labels: List[str] = [f"Round {r}" for r in range(1, total_rounds + 1)]

    for r in range(1, total_rounds + 1):
        for s in range(1, num_teams + 1):
            col_name = team_headers[s - 1]
            calc_p_no = calculate_keeper_pick_no(
                round_no=r, team_slot=s, num_teams=num_teams, is_3rr=is_3rr
            )

            # Check if pick is logged by pick_no or (round, slot)
            event = pick_map.get(calc_p_no) or slot_round_map.get((r, s))

            if event:
                player_name = event.get("player_name", "Unknown")
                pos = event.get("position", "")
                is_user = event.get("picked_by_user", False)
                is_keeper = (
                    event.get("source") == "keeper"
                    or "keeper" in str(event.get("notes", "")).lower()
                )

                tag = ""
                if is_keeper:
                    tag = " 🔒[KEEPER]"
                elif is_user:
                    tag = " ⭐[YOU]"

                cell_text = f"#{calc_p_no} {player_name} ({pos}){tag}"
            else:
                cell_text = f"#{calc_p_no}"

            matrix_data[col_name].append(cell_text)

    df_grid = pd.DataFrame(matrix_data, index=row_labels)

    # Render interactive grid table
    st.dataframe(
        df_grid,
        use_container_width=True,
        height=min(600, 40 * (total_rounds + 1)),
    )
