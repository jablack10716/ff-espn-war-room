# Phase 3 Checklist: Streamlit UI and Service Layer

Use this checklist to track Phase 3 implementation and verification.

Phase 3 Scope from [WAR_ROOM_SPEC.md](WAR_ROOM_SPEC.md): Streamlit Clone Board UI (`ui/app.py`), backend services (`services/`), and atomic Undo Last Pick support.

---

## 1) Service Layer Implementation

- [x] Implement thread-safe Supabase client singleton ([services/supabase_client.py](file:///c:/Code/FF-War-Room/services/supabase_client.py)).
- [x] Implement draft state service ([services/draft_state_service.py](file:///c:/Code/FF-War-Room/services/draft_state_service.py)) supporting:
  - [x] Player availability querying (`get_available_players`).
  - [x] Draft log retrieval (`get_draft_log`).
  - [x] Pick event logging (`record_pick`).
  - [x] Atomic Undo Last Pick transaction (`undo_last_pick`).
  - [x] Canonical state reconciliation (`reconcile_state`).
- [x] Implement Supabase Realtime WebSocket listener ([services/realtime_listener.py](file:///c:/Code/FF-War-Room/services/realtime_listener.py)).
- [x] Implement REST heartbeat poller worker ([services/heartbeat.py](file:///c:/Code/FF-War-Room/services/heartbeat.py)) for sequence drift detection and state repair.

---

## 2) Streamlit UI Components

- [x] Implement main Streamlit application entry point ([ui/app.py](file:///c:/Code/FF-War-Room/ui/app.py)).
- [x] Implement connectivity status component ([ui/components/connectivity_status.py](file:///c:/Code/FF-War-Room/ui/components/connectivity_status.py)).
- [x] Implement interactive draft board & searchbox input ([ui/components/draft_board.py](file:///c:/Code/FF-War-Room/ui/components/draft_board.py)).
- [x] Implement Live vs Mock Draft mode selector (`🎯 Live ESPN Draft` vs `🧪 Practice Mock Draft`).
- [x] Implement Mock Bot controls (`🤖 Simulate Next Bot Pick`, `⏩ Auto-Simulate to My Turn`, `🗑️ Reset Mock Draft`).
- [x] Implement Ada quantitative recommendations view ([ui/components/recommendations.py](file:///c:/Code/FF-War-Room/ui/components/recommendations.py)).
- [x] Verify `@st.fragment` isolation blocks for low-latency rerenders.

---

## 3) Automated Testing & Verification

- [x] Implement unit tests for `DraftStateService` pick logging and atomic undo in [tests/test_draft_log_undo.py](file:///c:/Code/FF-War-Room/tests/test_draft_log_undo.py).
- [x] Run full pytest suite across all modules: 16/16 tests passing.
- [x] Verify state consistency after pick recording and undo operations.
