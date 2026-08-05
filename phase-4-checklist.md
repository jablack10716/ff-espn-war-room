# Phase 4 Checklist: Multi-Agent Orchestration & Fallbacks

Use this checklist to track Phase 4 implementation and verification.

Phase 4 Scope from [WAR_ROOM_SPEC.md](WAR_ROOM_SPEC.md): Multi-Agent Orchestration Graph (`agents/war_room_agents.py`), JSON Schema enforcement, 5-second hard timeouts, and deterministic Ada fallbacks.

---

## 1) Agent Role Implementations

- [x] Implement **MarcusAgent** (Chief Scout) for upside talent analysis ([agents/war_room_agents.py](file:///c:/Code/FF-War-Room/agents/war_room_agents.py)).
- [x] Implement **WinstonAgent** (Roster Architect) for structural roster need analysis ([agents/war_room_agents.py](file:///c:/Code/FF-War-Room/agents/war_room_agents.py)).
- [x] Implement **ArthurAgent** (General Manager) for 2-sentence GM rationale synthesis ([agents/war_room_agents.py](file:///c:/Code/FF-War-Room/agents/war_room_agents.py)).

---

## 2) Orchestrator Graph & Fallback Policy

- [x] Implement **WarRoomOrchestrator** with Fan-Out to Marcus/Winston and Fan-In to Arthur.
- [x] Implement trigger condition (`picks_until_user_turn <= 2`).
- [x] Enforce strict JSON schema validation against `agents/schemas/`.
- [x] Enforce hard **5.0-second timeout cap** per network/LLM call.
- [x] Implement deterministic Ada-only fallback payload when timeout, validation error, or missing API key occurs.

---

## 3) Streamlit UI Integration & Verification

- [x] Integrate orchestrator into [ui/app.py](file:///c:/Code/FF-War-Room/ui/app.py).
- [x] Update [ui/components/recommendations.py](file:///c:/Code/FF-War-Room/ui/components/recommendations.py) to render Arthur GM rationale, Marcus upside chips, Winston roster chips, and fallback banners.
- [x] Implement unit & integration test suite ([tests/test_agent_schema_validation.py](file:///c:/Code/FF-War-Room/tests/test_agent_schema_validation.py)).
- [x] Run full pytest suite across all modules: 22/22 tests passing.
