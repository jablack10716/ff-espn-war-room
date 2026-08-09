"""Streamlit Component: Recommendations & Multi-Agent Synthesis Panel (Fragment B)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st


def render_recommendations(
    rankings: List[Dict[str, Any]],
    agent_payload: Optional[Dict[str, Any]] = None,
    user_roster: Optional[List[Dict[str, Any]]] = None,
    top_n: int = 5,
) -> None:
    """Render Ada quantitative recommendations, multi-agent notes, and GM synthesis rationale."""
    st.subheader("🎯 Recommendations & GM Synthesis")

    # Render Arthur GM Synthesis Block & War Room Debate if available
    if agent_payload:
        reasoning = agent_payload.get("reasoning_2_sentences")
        fallback = agent_payload.get("fallback_used", False)
        marcus_dict = agent_payload.get("marcus_notes", {})
        winston_dict = agent_payload.get("winston_notes", {})

        if fallback:
            st.info("⚡ **Ada Deterministic Mode**: Quant engine scores active.")
        else:
            st.success("🤖 **Arthur (GM) Multi-Agent Synthesis Active**")

        if reasoning:
            st.markdown(f"> 👑 **GM Strategy Rationale**: *\"{reasoning}\"*")

        # Interactive War Room Debate & Commentary Expander
        expander_title = "🗣️ Live War Room Agent Debate & Commentary (🤖 AI Active)" if not fallback else "🗣️ Live War Room Agent Debate & Commentary (⚠️ Fallback Active)"
        with st.expander(expander_title, expanded=not fallback):
            if fallback:
                st.markdown("### 🎙️ The War Room Debate `(⚠️ Fallback Templates)`")
            else:
                st.markdown("### 🎙️ The War Room Debate `(🤖 AI Active)`")
            st.markdown(
                "Here is the live exchange between **Marcus** (Upside Scout), **Winston** (Roster Architect), and **Arthur** (GM):"
            )

            col_m, col_w = st.columns(2)
            with col_m:
                m_fallback = agent_payload.get("marcus_fallback", False)
                m_tag = " `[Fallback]`" if m_fallback else " `[AI]`"
                st.markdown(f"#### 🏃 Marcus (Chief Scout){m_tag}")
                if marcus_dict:
                    for pid, sentence in marcus_dict.items():
                        st.markdown(f"- **{sentence}**")
                else:
                    st.caption("No scouting notes generated.")

            with col_w:
                w_fallback = agent_payload.get("winston_fallback", False)
                w_tag = " `[Fallback]`" if w_fallback else " `[AI]`"
                st.markdown(f"#### 📋 Winston (Roster Architect){w_tag}")
                if winston_dict:
                    for pid, sentence in winston_dict.items():
                        st.markdown(f"- **{sentence}**")
                else:
                    st.caption("No roster notes generated.")

            st.markdown("---")
            a_tag = " `[Fallback]`" if fallback else " `[AI]`"
            st.markdown(f"#### 👑 Arthur (General Manager Verdict){a_tag}")
            st.write(reasoning or "Arthur synthesized Ada's quant baseline to lock in top recommendation.")

        st.markdown("---")

    if not rankings:
        st.info("No available candidate recommendations.")
        return

    top_candidates = rankings[:top_n]
    marcus_notes = agent_payload.get("marcus_notes", {}) if agent_payload else {}
    winston_notes = agent_payload.get("winston_notes", {}) if agent_payload else {}

    for item in top_candidates:
        pid = str(item.get("player_id"))
        rank = item.get("rank")
        name = item.get("player_name")
        pos = item.get("position")
        team = item.get("team", "FA")
        composite = item.get("composite_score")
        tier = item.get("tier")
        adp = item.get("adp")
        bye = item.get("bye_week")
        injury = item.get("injury_status", "ACTIVE")
        bd = item.get("breakdown", {})

        with st.container():
            col_rank, col_details, col_scores = st.columns([1, 4, 4])

            with col_rank:
                st.markdown(f"### #{rank}")

            with col_details:
                st.markdown(f"**{name}** ({pos} - {team})")
                st.caption(f"Tier: {tier} | ADP: {adp} | {bye_str} | Median Proj: {item.get('projection_median')} pts")

                sources = item.get("data_sources") or ["espn"]
                source_labels = {
                    "espn": "ESPN",
                    "sleeper": "Sleeper",
                    "fantasypros": "FantasyPros",
                    "underdog": "Underdog ADP",
                    "underdog_adp": "Underdog ADP",
                    "vegas": "Vegas Props",
                    "vegas_props": "Vegas Props",
                    "high_stakes": "ETR/PFF",
                    "advanced": "AirYards/xFP",
                    "advanced_metrics": "AirYards/xFP",
                }
                tags = " | ".join([f"`[{source_labels.get(s, s)}]`" for s in sources])
                st.caption(f"🟢 **Blended Feeds**: {tags}")

                # Injury badge
                if injury in ("OUT", "INJURY_RESERVE", "IR", "SUSPENSION"):
                    st.error(f"🚑 {injury} — High risk injury/suspension")
                elif injury in ("DOUBTFUL", "QUESTIONABLE"):
                    st.warning(f"⚠️ {injury} — Monitor health before drafting")

                # Bye week conflict check
                if bye and user_roster:
                    same_bye_count = sum(1 for r in user_roster if r.get("bye_week") == bye)
                    if same_bye_count >= 2:
                        st.warning(f"⚠️ Bye Week Conflict: {same_bye_count} players already on Bye {bye}")

                # Value gap / ADP arbitrage badge
                val_gap = item.get("value_gap", 0.0)
                if val_gap >= 15.0:
                    st.success(f"💎 STEAL ALERT: +{val_gap:.0f} picks of value vs ADP")
                elif val_gap >= 8.0:
                    st.info(f"📈 Good Value: +{val_gap:.0f} picks above ADP")
                elif val_gap <= -10.0:
                    st.warning(f"📉 Reach: {abs(val_gap):.0f} picks below ADP — consider waiting")

                # Urgent indicators
                prv_mult = bd.get("prv_mult", 1.0)
                if prv_mult > 1.0:
                    st.error(f"🔥 Position Run Alert! (PRV Boost: {prv_mult:.2f}x)")

                hli_raw = bd.get("hli_raw", 0.0)
                if hli_raw > item.get("projection_median", 0.0):
                    st.success("🔒 High-Leverage Handcuff Protection")

                # Agent Scout & Roster Notes
                m_fallback = agent_payload.get("marcus_fallback", False) if agent_payload else True
                w_fallback = agent_payload.get("winston_fallback", False) if agent_payload else True
                m_label = "Fallback" if m_fallback else "AI"
                w_label = "Fallback" if w_fallback else "AI"

                if pid in marcus_notes:
                    st.markdown(f"🏃 **Marcus (Scout - {m_label})**: *{marcus_notes[pid]}*")
                if pid in winston_notes:
                    st.markdown(f"📋 **Winston (Architect - {w_label})**: *{winston_notes[pid]}*")

            with col_scores:
                st.metric("Composite Score", f"{composite:.4f}")
                st.caption(
                    f"OC_norm: {bd.get('oc_norm', 0.0):.2f} | "
                    f"FCVS_norm: {bd.get('fcvs_norm', 0.0):.2f} | "
                    f"HLI_norm: {bd.get('hli_norm', 0.0):.2f} | "
                    f"RosterFit: {bd.get('roster_fit_mult', 1.0):.2f}"
                )

            st.divider()
