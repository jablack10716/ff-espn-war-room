"""My Roster component with real-time positional need tracking."""

from __future__ import annotations
import streamlit as st
from typing import Any, Dict, List, Optional


def render_my_roster(
    draft_log: List[Dict[str, Any]],
    user_team_slot: int,
    roster_requirements: Optional[Dict[str, int]] = None,
) -> None:
    """Render the user's current roster and position-need tracker."""
    if roster_requirements is None:
        roster_requirements = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DST": 1}

    st.subheader("📋 My Roster")

    # Filter user's picks from draft log
    user_picks = [
        e for e in draft_log
        if int(e.get("team_slot", 0)) == user_team_slot
        and str(e.get("event_type", "PICK")).upper() == "PICK"
    ]

    # Group drafted players by position
    drafted_by_pos: Dict[str, List[Dict[str, Any]]] = {}
    for p in user_picks:
        pos = str(p.get("position", "OTHER")).upper()
        drafted_by_pos.setdefault(pos, []).append(p)

    st.caption(f"Total Players Drafted: **{len(user_picks)}**")

    # Display position-by-position tracker
    for pos, required_count in roster_requirements.items():
        players = drafted_by_pos.get(pos, [])
        count = len(players)

        if count >= required_count:
            status_badge = "✅ Filled"
        else:
            needed = required_count - count
            status_badge = f"⚠️ Need {needed}"

        st.markdown(f"**{pos}** ({count}/{required_count}) — {status_badge}")

        if players:
            for p in players:
                pname = p.get("player_name", "Unknown")
                pick_num = p.get("pick_no")
                st.caption(f"  • Pick #{pick_num}: {pname}")
        else:
            st.caption("  *(No players drafted)*")

        st.markdown("---")

    # Show additional bench picks (positions beyond starting requirements)
    all_req_positions = set(roster_requirements.keys())
    bench_picks = [p for p in user_picks if str(p.get("position", "")).upper() not in all_req_positions]
    if bench_picks:
        st.markdown("**Bench / Flex / Other**")
        for p in bench_picks:
            pname = p.get("player_name", "Unknown")
            pos = p.get("position", "FA")
            st.caption(f"  • {pname} ({pos})")
