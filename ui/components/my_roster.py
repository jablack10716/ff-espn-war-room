"""My Roster component with real-time positional need tracking.

Supports FLEX (RB/WR/TE) and SUPERFLEX (QB/RB/WR/TE) slot display and tracking.
"""

from __future__ import annotations
import streamlit as st
from typing import Any, Dict, List, Optional


# Flex eligibility constants
FLEX_ELIGIBLE = {"RB", "WR", "TE"}
SUPERFLEX_ELIGIBLE = {"QB", "RB", "WR", "TE"}

# Display labels for special slots
_SLOT_LABELS = {
    "FLEX": "FLEX (RB/WR/TE)",
    "SUPERFLEX": "SUPERFLEX (QB/RB/WR/TE)",
}


def _assign_flex_slots(
    user_picks: List[Dict[str, Any]],
    roster_requirements: Dict[str, int],
) -> Dict[str, List[Dict[str, Any]]]:
    """Assign drafted players to roster slots including FLEX and SUPERFLEX.

    Returns a dict mapping slot name -> list of players assigned to that slot.
    Players fill base starter slots first, then FLEX, then SUPERFLEX.
    QB overflow fills SUPERFLEX before other positions.
    """
    # Group drafted players by position
    by_pos: Dict[str, List[Dict[str, Any]]] = {}
    for p in user_picks:
        pos = str(p.get("position", "OTHER")).upper()
        by_pos.setdefault(pos, []).append(p)

    assigned: Dict[str, List[Dict[str, Any]]] = {}

    # Fill base starter slots first
    for pos in ("QB", "RB", "WR", "TE", "K", "DST"):
        req = roster_requirements.get(pos, 0)
        if req <= 0:
            continue
        players = by_pos.get(pos, [])
        assigned[pos] = players[:req]
        by_pos[pos] = players[req:]  # remainder = overflow

    # Collect overflow eligible for FLEX and SUPERFLEX
    flex_max = roster_requirements.get("FLEX", 0)
    sf_max = roster_requirements.get("SUPERFLEX", 0)
    flex_assigned: List[Dict[str, Any]] = []
    sf_assigned: List[Dict[str, Any]] = []

    # QB overflow fills SUPERFLEX first
    qb_overflow = by_pos.get("QB", [])
    for p in qb_overflow:
        if len(sf_assigned) < sf_max:
            sf_assigned.append(p)
        # QB can't fill FLEX

    # RB/WR/TE overflow fills FLEX first, then SUPERFLEX
    for pos in ("RB", "WR", "TE"):
        overflow = by_pos.get(pos, [])
        for p in overflow:
            if len(flex_assigned) < flex_max:
                flex_assigned.append(p)
            elif len(sf_assigned) < sf_max:
                sf_assigned.append(p)
            # else: bench

    if flex_max > 0:
        assigned["FLEX"] = flex_assigned
    if sf_max > 0:
        assigned["SUPERFLEX"] = sf_assigned

    return assigned


def render_my_roster(
    draft_log: List[Dict[str, Any]],
    user_team_slot: int,
    roster_requirements: Optional[Dict[str, int]] = None,
) -> None:
    """Render the user's current roster and position-need tracker."""
    if roster_requirements is None:
        roster_requirements = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "SUPERFLEX": 1, "DST": 1}

    st.subheader("📋 My Roster")

    # Filter user's picks from draft log
    user_picks = [
        e for e in draft_log
        if int(e.get("team_slot", 0)) == user_team_slot
        and str(e.get("event_type", "PICK")).upper() == "PICK"
    ]

    st.caption(f"Total Players Drafted: **{len(user_picks)}**")

    # Smart slot assignment
    assigned = _assign_flex_slots(user_picks, roster_requirements)

    # Display position-by-position tracker (including FLEX/SUPERFLEX)
    display_order = []
    for pos in ("QB", "RB", "WR", "TE", "FLEX", "SUPERFLEX", "K", "DST"):
        req = roster_requirements.get(pos, 0)
        if req > 0:
            display_order.append(pos)

    for pos in display_order:
        required_count = roster_requirements.get(pos, 0)
        players = assigned.get(pos, [])
        count = len(players)
        display_label = _SLOT_LABELS.get(pos, pos)

        if count >= required_count:
            status_badge = "✅ Filled"
        else:
            needed = required_count - count
            status_badge = f"⚠️ Need {needed}"

        st.markdown(f"**{display_label}** ({count}/{required_count}) — {status_badge}")

        if players:
            for p in players:
                pname = p.get("player_name", "Unknown")
                pick_num = p.get("pick_no")
                p_pos = p.get("position", "")
                if pos in ("FLEX", "SUPERFLEX"):
                    st.caption(f"  • Pick #{pick_num}: {pname} ({p_pos})")
                else:
                    st.caption(f"  • Pick #{pick_num}: {pname}")
        else:
            st.caption("  *(No players drafted)*")

        st.markdown("---")

    # Show bench picks (players beyond all starter + flex slots)
    all_assigned_picks = set()
    for slot_players in assigned.values():
        for p in slot_players:
            all_assigned_picks.add(id(p))

    bench_picks = [p for p in user_picks if id(p) not in all_assigned_picks]
    if bench_picks:
        st.markdown(f"**Bench** ({len(bench_picks)})")
        for p in bench_picks:
            pname = p.get("player_name", "Unknown")
            pos = p.get("position", "FA")
            pick_num = p.get("pick_no")
            st.caption(f"  • Pick #{pick_num}: {pname} ({pos})")
