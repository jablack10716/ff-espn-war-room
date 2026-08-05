"""Streamlit Component: Connectivity & Health Status Indicators."""

from __future__ import annotations

import streamlit as st


def render_connectivity_status(
    ws_connected: bool,
    heartbeat_healthy: bool,
    fallback_mode: bool = False,
) -> None:
    """Render status badges and degraded mode warning banners."""
    cols = st.columns([1, 1, 1, 2])

    with cols[0]:
        if ws_connected:
            st.markdown("🟢 **Realtime**: Connected")
        else:
            st.markdown("🟠 **Realtime**: Reconnecting")

    with cols[1]:
        if heartbeat_healthy:
            st.markdown("🟢 **Heartbeat**: Healthy")
        else:
            st.markdown("🔴 **Heartbeat**: Degraded")

    with cols[2]:
        if fallback_mode:
            st.markdown("⚠️ **Engine**: Ada-Only Fallback")
        else:
            st.markdown("⚡ **Engine**: Normal (Ada Math)")

    if not ws_connected or not heartbeat_healthy:
        st.warning(
            "WebSocket connection is experiencing latency or drift. REST heartbeat auto-reconciliation is active."
        )
