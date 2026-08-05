# Fantasy Football AI War Room - Master To-Do Checklist

Use this checklist to track phase completion across all phases and enhancement sprints of the project.

---

## 1) Phase 1: Supabase Setup and ESPN Ingestion

- [x] Environment variables configured (`.env`).
- [x] Supabase DDL migrations applied (`001_init_tables.sql`, `002_indexes_realtime.sql`).
- [x] Realtime publication enabled on `public.draft_log`.
- [x] ESPN Ingestion script executed and verified (`data/espn_ingest.py`).
- [x] Player seed data upserted into `available_players`.
- [x] Keeper handling strategy confirmed.

---

## 2) Phase 2: Python Quant Engine (`ada_math.py`)

- [x] Standalone planning checklist created and approved ([phase-2-checklist.md](phase-2-checklist.md)).
- [x] Opportunity Cost (OC) formula & ADP next-turn simulation implemented.
- [x] Floor-to-Ceiling Variance Shift (FCVS) piecewise round weighting implemented.
- [x] Handcuff Leverage Index (HLI) protection multipliers implemented.
- [x] Positional Run Velocity (PRV) tier cliff detection implemented.
- [x] RosterFit positional demand multiplier implemented.
- [x] Composite score ranking & snapshot generation implemented.
- [x] Unit test suite implemented and passing (13/13 tests).

---

## 3) Phase 3: Streamlit Clone Board UI & Service Layer (`ui/app.py`)

- [x] Standalone planning checklist created and approved ([phase-3-checklist.md](phase-3-checklist.md)).
- [x] Supabase thread-safe client singleton ([services/supabase_client.py](services/supabase_client.py)).
- [x] Draft state management service & atomic Undo Last Pick ([services/draft_state_service.py](services/draft_state_service.py)).
- [x] Supabase Realtime WebSocket listener ([services/realtime_listener.py](services/realtime_listener.py)).
- [x] REST heartbeat loop poller for sequence drift repair ([services/heartbeat.py](services/heartbeat.py)).
- [x] Streamlit UI layout and component fragments ([ui/app.py](ui/app.py)):
  - [x] Connectivity & health status badges ([ui/components/connectivity_status.py](ui/components/connectivity_status.py)).
  - [x] Interactive draft board grid & searchbox ([ui/components/draft_board.py](ui/components/draft_board.py)).
  - [x] Live vs Practice Mock Simulator mode.
  - [x] Recommendations view with composite breakdown cards ([ui/components/recommendations.py](ui/components/recommendations.py)).
- [x] Integration & unit test suite implemented and passing (16/16 total tests).

---

## 4) Phase 4: Agent Orchestration & Fallbacks (`war_room_agents.py`)

- [x] Standalone planning checklist created and approved ([phase-4-checklist.md](phase-4-checklist.md)).
- [x] MarcusAgent (Chief Scout), WinstonAgent (Roster Architect), ArthurAgent (GM) implemented.
- [x] WarRoomOrchestrator Fan-Out / Fan-In graph implemented.
- [x] JSON Schema validation enforced per agent schema.
- [x] 5-second hard timeout cap and deterministic Ada fallback implemented.
- [x] Full unit test suite implemented and passing (22/22 total tests).

---

## 5) Sprint 1 Enhancements: Critical Data & Formula Fixes

- [x] **Item 1: Value Over Replacement Player (VOR/VORP)**
  - Implemented `calculate_vor` in `engine/scoring_models.py`.
  - Integrated `w_vor=0.20` into `AdaQuantEngine` in `engine/ada_math.py`.
  - Implemented test suite in `tests/test_vor.py`.
- [x] **Item 2: Scoring Format Awareness (PPR/Half-PPR/Standard)**
  - Extracted scoring format from ESPN settings in `data/espn_ingest.py`.
  - Implemented `apply_ppr_adjustment` in `engine/scoring_models.py` and `engine/ada_math.py`.
  - Displayed scoring format in Streamlit UI sidebar.
  - Implemented test suite in `tests/test_ppr_adjustment.py`.
- [x] **Item 3: Realistic Positional Projection Variance**
  - Added `POSITION_VARIANCE` table to `data/espn_ingest.py` (QB, RB, WR, TE, K, DST specific floor/ceil multipliers).
  - Implemented test suite in `tests/test_espn_ingest.py`.
- [x] **Item 4: Bye Week Conflict & Injury Status Badges**
  - Extracted `injury_status` in `data/espn_ingest.py` and created DDL `db/migrations/003_add_injury_and_vor.sql`.
  - Added bye week conflict warnings and injury status badges in `ui/components/recommendations.py`.
  - Passed `bye_week` and `injury_status` through `engine/ada_math.py`.
  - Implemented test suite in `tests/test_bye_week_injury.py`.
- [x] **Item 5: Wired Realtime Listener & Heartbeat Worker**
  - Wired `RealtimeListener` and `HeartbeatWorker` into `ui/app.py`.
  - Polled WebSocket event queue and REST heartbeat checks live.
- [x] **Verification**: All 30 unit & integration tests passing (`python -m pytest`).

---

## 6) Sprint 2 Enhancements: Strategic Depth & Agent Intelligence

- [x] **Item 6: Positional Scarcity-Aware RosterFit (Gradient)**
  - Updated `calculate_roster_fit` in `engine/scoring_models.py` with gradient rules (1.50 for 2+ slots needed, 1.40/1.20/1.10 for 1 slot based on remaining pool scarcity, 0.60/0.80 for 0 slots needed, 0.30 for early K/DST suppression).
  - Passed `available_players=candidates` in `engine/ada_math.py`.
  - Added unit tests in `tests/test_ada_math.py`.
- [x] **Item 7: Gradient PRV Cliff Multiplier**
  - Updated `calculate_prv_multiplier` in `engine/tier_cliff.py` with gradient rules (1.25 for 1 left, 1.18 for 2 left, 1.12 for 3 left, 1.06 for 4-5 left).
  - Updated unit tests in `tests/test_prv_detection.py`.
- [x] **Item 8: Position-Aware Agent Fallback Templates & Context Enrichment**
  - Implemented position-aware fallback templates for Marcus (Scout) and Winston (Architect) in `agents/war_room_agents.py`.
  - Injected `bye_week` and `roster_byes` into Winston's prompt; injected `injury_status` into Marcus's prompt.
  - Relaxed regex constraints in `marcus_output.schema.json`, `winston_output.schema.json`, `arthur_output.schema.json` to allow internal periods.
  - Added unit test in `tests/test_agent_schema_validation.py`.
- [x] **Verification**: All 32 unit & integration tests passing (`python -m pytest`).

---

## 7) Sprint 3 Enhancements: UX & Draft Day Experience

- [x] **Item 9: "My Roster" Panel with Position-Need Tracker**
  - Created `ui/components/my_roster.py` displaying user's drafted roster and real-time positional need status (`✅ Filled` vs `⚠️ Need N`).
  - Integrated 3-column layout in `ui/app.py`: Recommendations | My Roster | Draft Board.
- [x] **Item 10: ADP Arbitrage / Value Flag Badges**
  - Computed `value_gap` vs. ADP in `engine/ada_math.py`.
  - Added value badges in `ui/components/recommendations.py` (`💎 STEAL ALERT`, `📈 Good Value`, `📉 Reach`).
- [x] **Item 11: Ada-Ranked Master Cheat Sheet Exports**
  - Added `generate_ranked_csv_cheat_sheet` and `generate_ranked_html_cheat_sheet` in `engine/cheat_sheet.py`.
  - Added download buttons for Ada-ranked CSV and printable HTML cheat sheets in `ui/app.py`.
  - Added unit test in `tests/test_cheat_sheet.py`.
- [x] **Verification**: All 33 unit & integration tests passing (`python -m pytest`).

---

## 8) Sprint 4 Enhancements: Polish & Reliability

- [x] **Item 12: Primary NFL RB Handcuff Mapping**
  - Added `HANDCUFF_MAP` dictionary and `apply_handcuff_mappings` in `data/espn_ingest.py`.
  - Automatically mapped backup RBs to their primary starters during ingest.
  - Added unit test in `tests/test_hli_logic.py`.
- [x] **Item 13: Dynamic Non-RB HLI Weight Redistribution**
  - In `engine/ada_math.py`, dynamically redistributed `w_hli` 50/50 into `w_oc` and `w_vor` for non-RB candidate positions.
  - Added unit test in `tests/test_hli_logic.py`.
- [x] **Final Verification**: All 35 unit & integration tests passing (`python -m pytest`).
