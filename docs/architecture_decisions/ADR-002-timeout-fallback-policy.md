# ADR-002 Timeout and Fallback Policy

Status: Accepted
Date: 2026-07-28

Context:
- Live draft recommendations require predictable latency at each pick boundary.
- Model variability can exceed acceptable real-time decision windows.

Decision:
- Enforce hard 5-second timeout on each external model/network call.
- Use deterministic Ada-only fallback when timeout, parse, or provider failures occur.
- Never block draft board render/update path waiting for model responses.

Consequences:
- Recommendation quality can degrade gracefully under provider instability.
- User experience remains continuous during high-pressure draft windows.

Reference:
- WAR_ROOM_SPEC.md Section 7.
