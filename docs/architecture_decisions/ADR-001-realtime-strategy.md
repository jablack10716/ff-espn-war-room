# ADR-001 Realtime Strategy

Status: Accepted
Date: 2026-07-28

Context:
- Draft board updates must remain responsive under websocket interruption.
- Core recommendation flow cannot block on network or model delays.

Decision:
- Use Supabase Realtime on `draft_log` as primary event source.
- Add REST heartbeat reconciliation loop every 2-3 seconds.
- On stale websocket or pick-sequence drift, perform snapshot reconcile.

Consequences:
- Eventual consistency is favored over strict real-time linearizability.
- System gains resilience to dropped websocket events.

Reference:
- WAR_ROOM_SPEC.md Section 2 and Section 7.
