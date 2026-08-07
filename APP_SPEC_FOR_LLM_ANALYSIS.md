# The Best Damn Fantasy Football Drafting App — Comprehensive System Specification
## For Deep-Research LLM Analysis

> **Purpose**: This document is a dense, self-contained technical specification intended for a deep-research LLM to analyze the system holistically and provide structured feedback on architecture, code quality, correctness, and improvement opportunities.

---

## 1. Overview

### 1.1 What It Is

A **real-time Fantasy Football draft assistant** designed to run during live ESPN drafts. It provides:
- Live pick tracking and board state management
- Deterministic quantitative player ranking (no LLM math)
- Multi-agent LLM synthesis for draft recommendations
- Snake draft and 3rd Round Reversal (3RR) support
- Exportable Ada-ranked cheat sheets (CSV + printable HTML)

### 1.2 Technology Stack

| Layer | Technology |
|---|---|
| Frontend / UI | Streamlit (Python) |
| Database | Supabase Postgres |
| Realtime Events | Supabase Realtime (WebSocket) |
| LLM Backbone | Google Gemini (via `google-generativeai`, fallback to `gemini-flash-latest`) |
| Data Ingestion | `espn-api` Python library + Sleeper public REST API + FantasyPros ECR scraping |
| Package Manager | pip + `.venv` |
| Language | Python 3.11+ |

### 1.3 Production Status

**All 4 phases and 4 enhancement sprints are complete and verified.** As of commit `91e6061`:
- 49/49 unit tests pass (`python -m pytest`)
- LLM agents (Marcus, Winston, Arthur) are live on Gemini API
- System is ready for production draft-day use

---

## 2. Repository Structure

```
FF-War-Room/
  WAR_ROOM_SPEC.md         # SSOT specification document
  README.md                # Setup guide
  requirements.txt         # Python dependencies
  .env.example             # Environment variable template
  to-do.md                 # Master sprint checklist (all complete)

  config/
    settings.py            # Centralized env-var config

  data/
    espn_ingest.py         # ESPN + multi-source data ingestion (894 lines)
    seed/
      sample_players.csv   # Offline fallback seed data

  db/
    supabase_schema.sql    # Full DDL (tables, indexes, triggers)
    migrations/
      001_init_tables.sql
      002_indexes_realtime.sql
      003_add_injury_and_vor.sql

  engine/
    ada_math.py            # AdaQuantEngine: composite ranking orchestrator
    scoring_models.py      # FCVS, HLI, RosterFit, VOR, PPR, normalization
    tier_cliff.py          # PRV tier cliff detection
    cheat_sheet.py         # CSV + HTML export generators

  agents/
    war_room_agents.py     # MarcusAgent, WinstonAgent, ArthurAgent, WarRoomOrchestrator
    prompts/
      marcus_system.txt    # Chief Scout system prompt
      winston_system.txt   # Roster Architect system prompt
      arthur_system.txt    # General Manager system prompt
    schemas/
      marcus_output.schema.json
      winston_output.schema.json
      arthur_output.schema.json

  ui/
    app.py                 # Main Streamlit app (738 lines) — primary entry point
    components/
      draft_board.py       # Pick logging searchbox + board controls
      recommendations.py   # Ada ranking cards + agent synthesis panel
      full_draft_grid.py   # Full snake draft grid (all picks, all teams)
      keeper_manager.py    # Pre-draft keeper lock UI
      my_roster.py         # User roster tracker with positional need status
      connectivity_status.py # WebSocket + heartbeat health badges

  services/
    supabase_client.py     # Singleton Supabase client with thread safety
    draft_state_service.py # Core CRUD: record_pick, undo_last_pick, upsert_pick, reset
    realtime_listener.py   # WebSocket subscriber (threaded, queue-based)
    heartbeat.py           # REST poll loop for sequence drift detection
    action_logger.py       # File-based audit logger for all UI interactions
    sleeper_client.py      # Sleeper API client (free, no auth)
    fantasypros_client.py  # FantasyPros ECR scraper
    depth_chart_service.py # Depth chart data fetcher

  tests/                   # 49 unit + integration tests across 13 files
```

---

## 3. Data Model

### 3.1 `available_players` Table (Supabase Postgres)

This is the canonical player pool. Players are marked `is_available=false` when drafted.

```sql
create table public.available_players (
    player_id             text primary key,
    full_name             text not null,
    normalized_name       text not null,
    team                  text,
    position              text not null check (position in ('QB','RB','WR','TE','K','DST')),
    bye_week              smallint check (bye_week between 1 and 18),

    -- Tiering and projections
    tier                  smallint not null check (tier >= 1),
    adp                   numeric(6,2),
    consensus_adp         numeric(6,2),
    sleeper_adp           numeric(6,2),
    analyst_tier          smallint,
    fantasypros_ecr       numeric(6,2),
    projection_floor      numeric(7,2) not null,
    projection_median     numeric(7,2) not null,
    projection_ceiling    numeric(7,2) not null,
    projected_receptions  numeric(6,2),  -- for PPR adjustment

    -- Handcuff metadata
    depth_role            text,           -- 'RB1', 'RB2', 'BACKUP', etc.
    handcuff_for_player_id text,          -- FK to primary RB's player_id

    -- Status and audit
    is_available          boolean not null default true,
    injury_status         text,           -- 'ACTIVE', 'QUESTIONABLE', 'DOUBTFUL', 'OUT', 'IR'
    data_sources          text[],         -- ['espn', 'sleeper', 'fantasypros']
    last_metric_refresh_ts timestamptz,
    created_at            timestamptz not null default now(),
    updated_at            timestamptz not null default now()
);
-- Indexes: (is_available, position, tier), (team, position), (normalized_name), (handcuff_for_player_id)
```

### 3.2 `draft_log` Table (Supabase Postgres)

The ordered event log of all picks. This is the single source of truth for board state.

```sql
create table public.draft_log (
    event_id      bigint generated always as identity primary key,
    draft_id      text not null,

    pick_no       integer not null check (pick_no > 0),
    round_no      integer not null check (round_no > 0),

    team_slot     integer not null check (team_slot > 0),
    team_name     text,

    player_id     text not null,
    player_name   text not null,
    position      text not null check (position in ('QB','RB','WR','TE','K','DST')),

    picked_by_user boolean not null default false,

    -- Event typing for atomic undo support
    event_type    text not null check (event_type in ('PICK','UNDO')),

    -- Source tracking
    source        text not null default 'manual' check (source in ('manual','import','system','keeper')),
    notes         text,

    -- Concurrency
    client_mutation_id uuid,
    created_at    timestamptz not null default now()
);

-- Unique constraint: one PICK per (draft_id, pick_no)
create unique index uq_draft_log_draft_pick on public.draft_log (draft_id, pick_no)
    where event_type = 'PICK';
```

**Realtime Configuration:**
```sql
alter table public.draft_log replica identity full;
alter publication supabase_realtime add table public.draft_log;
```

---

## 4. End-to-End Data Flow

```
User Action (log pick / undo)
    │
    ▼
ui/app.py (handle_record_pick)
    │
    ├─► services/action_logger.py → war_room_actions.log (audit trail)
    │
    ▼
services/draft_state_service.py (DraftStateService.upsert_pick)
    │
    ├─► Supabase: INSERT into draft_log (event_type='PICK')
    ├─► Supabase: UPDATE available_players SET is_available=false WHERE player_id=X
    │
    ▼
Supabase Realtime WebSocket → all connected clients
    │
    ▼
services/realtime_listener.py (threaded, queue-based)
    │  polls event queue on each Streamlit rerun
    ▼
services/heartbeat.py (REST fallback every 2.5s)
    │  detects sequence drift, triggers reconcile
    ▼
services/draft_state_service.py (reconcile_state)
    │  returns canonical (available_players, draft_log)
    ▼
engine/ada_math.py (AdaQuantEngine.compute_rankings)
    │  computes OC, FCVS, HLI, PRV, VOR, RosterFit
    │  sorts deterministically → ranked list
    ▼
agents/war_room_agents.py (WarRoomOrchestrator.run_orchestration)
    │  [triggered when picks_until_user_turn <= 2]
    │
    ├─► Fan-Out (ThreadPoolExecutor, 6 workers, timeout=60% of total):
    │       MarcusAgent.evaluate_player() × 3 top candidates → upside_sentence
    │       WinstonAgent.evaluate_player() × 3 top candidates → need_sentence
    │
    └─► Fan-In (timeout=40% of total):
            ArthurAgent.synthesize(marcus_notes, winston_notes, ada_rankings)
            → reasoning_2_sentences + top_3_picks JSON

    │  on any failure/timeout → build_fallback_payload(ada_rankings)
    ▼
ui/components/recommendations.py (render_recommendations)
    │  renders ranked cards with:
    │    - composite score + score breakdown
    │    - injury/bye conflict badges
    │    - ADP arbitrage value badges (STEAL / Good Value / Reach)
    │    - PRV urgency alerts
    │    - HLI handcuff protection badges
    │    - Marcus + Winston agent notes per player
    │    - Arthur GM synthesis rationale
    ▼
User sees live recommendations
```

---

## 5. Ada Deterministic Quant Engine

**File:** `engine/ada_math.py` + `engine/scoring_models.py` + `engine/tier_cliff.py`

**Design principle:** All ranking math is pure deterministic Python — zero LLM involvement in scoring.

### 5.1 Engine Inputs

```python
AdaQuantEngine.compute_rankings(
    available_players: List[Dict],   # players where is_available=True
    draft_log: List[Dict],           # all PICK events to reconstruct rosters
    user_team_slot: int,             # which team slot is the user
    current_round: int,
    current_pick: int,
    picks_until_next_turn: int,
    roster_requirements: Dict[str, int],  # e.g. {QB:1, RB:2, WR:2, TE:1, FLEX:1, SUPERFLEX:1}
    scoring_format: str,             # 'PPR', 'HALF_PPR', 'STANDARD'
    num_teams: int,                  # league size
)
```

### 5.2 Metric Computation Pipeline

**Step 1: Compute 6 raw metrics per candidate**

| Metric | Function | What It Measures |
|---|---|---|
| OC (Opportunity Cost) | `calculate_opportunity_cost_raw()` | Value lost by waiting — `projection_median(p) − expected_best_at_next_turn(pos)` |
| VOR (Value Over Replacement) | `calculate_vor()` | Player projection above the replacement-level player at that position |
| FCVS (Floor-to-Ceiling Variance Shift) | `calculate_fcvs_raw()` | Weighted blend of floor/ceiling by draft round |
| HLI (Handcuff Leverage Index) | `calculate_hli_raw()` | Handcuff value multiplied by protection role (RB only) |
| PRV (Positional Run Velocity) | `calculate_prv_multiplier()` | Urgency boost when a position is being drafted heavily + tier cliff detected |
| RosterFit | `calculate_roster_fit()` | Gradient multiplier based on positional need + scarcity |

**Step 2: Normalize**

- OC → z-score across all candidates
- VOR → z-score across all candidates
- FCVS → min-max normalize **per position group**
- HLI → min-max normalize **within RB pool only** (returns 0.0 for non-RBs)
- PRV → min-max across all candidates
- RosterFit → used directly as multiplier (not re-normalized)

**Step 3: Composite Score**

Default weights:
```python
w_oc       = 0.20  # (bumped to 0.275 for non-RBs via HLI redistribution)
w_vor      = 0.20  # (bumped to 0.275 for non-RBs via HLI redistribution)
w_fcvs     = 0.20
w_hli      = 0.15  # → 0.0 for non-RBs; redistributed 50/50 to w_oc/w_vor
w_prv      = 0.10
w_roster_fit = 0.15

composite = w_oc*OC_norm + w_vor*VOR_norm + w_fcvs*FCVS_norm +
            w_hli*HLI_norm + w_prv*PRV_norm + w_roster_fit*RosterFit_mult
```

**Step 4: Deterministic Sort**
```
ORDER BY composite_score DESC, projection_median DESC, adp ASC, player_id ASC
```

**Step 5: ADP Value Gap**
```
value_gap = adp - rank  (positive = steal, negative = reach)
```

---

### 5.3 FCVS (Floor-to-Ceiling Variance Shift)

Round-based blending strategy reflecting risk tolerance:

| Rounds | Floor Weight | Ceiling Weight | Rationale |
|---|---|---|---|
| 1–5 | 80% | 20% | Early picks need reliable production (floor dominates) |
| 6–9 | 50% | 50% | Mid-rounds balance risk/reward |
| 10+ | 10% | 90% | Late rounds reward upside lottery tickets |

If projection_floor/ceiling missing, fallback: `floor = median * 0.85`, `ceiling = median * 1.15`.

---

### 5.4 HLI (Handcuff Leverage Index) — RB-only

```
1.5x  → backup is direct handcuff to user's own RB1
1.3x  → backup to an opponent's unhandcuffed RB1 (denial value)
0.5x  → low-tier backup with projection < 50 pts
1.0x  → default
```

Detection logic:
1. Checks `handcuff_for_player_id` FK first (populated during ESPN ingest via `HANDCUFF_MAP`)
2. Falls back to: same team + depth_role in ('RB2', 'BACKUP')

For non-RB positions, `hli_raw = 0.0` and the 15% weight is redistributed 7.5% to OC and 7.5% to VOR.

---

### 5.5 PRV (Positional Run Velocity) — Gradient Tier Cliff

`calculate_prv_multiplier(position, available_players, recent_picks_last_10)`:

**Tier cliff severity:**
| Players remaining in top tier | Run share threshold | Multiplier |
|---|---|---|
| 1 | > 30% | **1.25× (URGENT)** |
| 2 | > 30% | 1.18× |
| 3 | > 35% | 1.12× |
| 4–5 | > 40% | 1.06× |
| any other | — | 1.00× (no boost) |

"Run share" = fraction of last 10 picks that were the given position.

---

### 5.6 VOR (Value Over Replacement)

Replacement level = projection_median of the `(num_teams × effective_starters + 1)`-th ranked player at that position.

**FLEX/SUPERFLEX fractional starters:**
```python
FLEX_WEIGHTS     = {RB: 0.45, WR: 0.35, TE: 0.20}
SUPERFLEX_WEIGHTS = {QB: 1.0}  # SUPERFLEX is essentially a QB2 slot
```

VOR is especially impactful for QB2 in superflex leagues where replacement level is much higher.

---

### 5.7 RosterFit (Gradient Positional Demand)

```
if pos in (K, DST) and round < 10:    → 0.30 (suppress early kicker/DST)
if 2+ base starter slots needed:       → 1.50 (critical need)
if 1 base slot needed:
    if remaining_at_pos <= 15:         → 1.40 (scarce)
    if remaining_at_pos <= 30:         → 1.20 (moderately scarce)
    else:                              → 1.10 (soft need)
if FLEX/SUPERFLEX slot available:
    QB for SUPERFLEX, remaining <= 20: → 1.35
    QB for SUPERFLEX, remaining > 20:  → 1.15
    other FLEX:                        → 1.00
if all slots filled:
    round <= 6:                        → 0.60 (bench suppression early)
    round > 6:                         → 0.80 (bench suppression late)
```

---

### 5.8 OC (Opportunity Cost)

```
estimate_best_at_next_turn(pos, available_players, picks_until_next_turn):
    - Sort entire available pool by ADP ascending
    - Simulate drafting top-ADP players for the next N picks
    - Count how many of `pos` would be taken (k)
    - Return projection_median of the (k+1)-th best remaining player at pos

OC_raw = projection_median(player) - expected_best_at_next_turn(pos)
```

Higher OC = passing on this player is expensive.

---

### 5.9 PPR Adjustment

```python
apply_ppr_adjustment(player, scoring_format):
    # Uses projected_receptions if available
    # Fallback positional estimates:
    WR: +85 (PPR) / +42.5 (Half-PPR)
    TE: +55 (PPR) / +27.5 (Half-PPR)
    RB: +40 (PPR) / +20 (Half-PPR)
    QB/K/DST: +0
```

---

## 6. Multi-Agent Orchestration Layer

**File:** `agents/war_room_agents.py`

### 6.1 Architecture

```
WarRoomOrchestrator
    │
    ├── MarcusAgent  (Chief Scout — fast, upside-focused)
    ├── WinstonAgent (Roster Architect — structural/positional needs)
    └── ArthurAgent  (General Manager — synthesizer/decision-maker)
```

Trigger condition: `picks_until_user_turn <= 2`

### 6.2 LLM Call Mechanism

```python
call_llm_api(system_prompt, user_prompt, model, timeout_seconds):
    # Uses google-generativeai
    # Model default: gemini-flash-latest (set in .env)
    # Returns raw text of LLM response or None on failure
    # Hard timeout enforced via threading.Timer
```

### 6.3 Fan-Out / Fan-In Flow

```python
WarRoomOrchestrator.run_orchestration(
    candidate_players,     # full available pool
    user_roster,           # user's current picks from draft_log
    ada_rankings,          # sorted output from AdaQuantEngine
    timeout_seconds=15.0   # configurable via sidebar slider (3–30s)
):
    fan_out_timeout = timeout_seconds * 0.6  # default: 9s
    fan_in_timeout  = timeout_seconds * 0.4  # default: 6s

    # Parallel Fan-Out (ThreadPoolExecutor, max_workers=6)
    for p in ada_rankings[:3]:
        submit marcus.evaluate_player(p)
        submit winston.evaluate_player(p)

    wait(fan_out_timeout)  # collect completed futures

    # Fan-In to Arthur
    arthur.synthesize(marcus_list, winston_list, ada_rankings, fan_in_timeout)

    # Fallback if any failure/timeout
    build_fallback_payload(ada_rankings)  # Ada-only, deterministic
```

### 6.4 MarcusAgent (Chief Scout)

**Role:** Player upside + news/injury context.

**System Prompt:**
```
You are Marcus, Chief Scout for a fantasy football draft war room.
Task: Produce exactly one sentence evaluating upside talent for ONE candidate player.
Constraints:
- Use only provided context and player attributes.
- Focus on upside pathways (athletic profile, role expansion, camp/injury news impact).
- Do not discuss roster construction, bye week strategy, or math scores.
- Output must be strict JSON only, no markdown.
- Return exactly the keys required by schema and no extras.

Reliability constraints:
- Never claim or imply a pick has been persisted unless the prompt explicitly confirms save success.
```

**User Prompt (runtime):**
```python
f"Evaluate upside for player: {player_dict}. Injury: {injury_status}."
```

**Output JSON Schema:**
```json
{
  "agent": "Marcus",
  "player_id": "<string>",
  "upside_sentence": "<1 sentence, 10-280 chars>"
}
```

**Fallback template** (when LLM fails):
```python
f"<player_name> ({pos}) offers {fallback_note} ceiling potential at pick value {adp}."
# where fallback_note is position-specific (e.g. RB="elite RB1", WR="top-end WR1")
```

---

### 6.5 WinstonAgent (Roster Architect)

**Role:** Positional need + bye week stack + scarcity.

**System Prompt:**
```
You are Winston, Roster Architect for a fantasy football draft war room.
Task: Produce exactly one sentence evaluating roster fit and positional need for ONE candidate player.
Constraints:
- Use only provided roster state, bye weeks, and positional scarcity context.
- Focus on structural needs and synergy with current roster.
- Do not discuss raw upside scouting narratives or deterministic math details.
- Output must be strict JSON only, no markdown.
```

**User Prompt (runtime):**
```python
f"Evaluate roster fit. Player: {player_dict}. User roster: {user_roster}. Roster byes: {roster_byes}."
```

**Output JSON Schema:**
```json
{
  "agent": "Winston",
  "player_id": "<string>",
  "need_sentence": "<1 sentence, 10-280 chars>"
}
```

**Fallback template:**
```python
f"Adding <player_name> ({pos}) fills a <position> need while addressing roster balance needs."
```

---

### 6.6 ArthurAgent (General Manager)

**Role:** Synthesizes Ada + Marcus + Winston into final ranked recommendations.

**System Prompt:**
```
You are Arthur, General Manager for a fantasy football draft war room.
You must synthesize:
1) Marcus upside sentence(s),
2) Winston roster-need sentence(s),
3) Ada deterministic ranking metrics.

Decision policy:
- Respect Ada deterministic ranking as primary anchor.
- Use Marcus/Winston only as tie-breakers or confidence modifiers.
- If supplied context is conflicting, prefer deterministic risk-controlled choice.

Output constraints:
- Output strict JSON only, no markdown.
- reasoning_2_sentences must contain exactly two sentences.
- top_3_picks must contain exactly 3 ranked players.
```

**User Prompt (runtime):**
```python
f"Synthesize recommendations.\n"
f"Marcus Scout Notes: {marcus_notes}\n"
f"Winston Roster Notes: {winston_notes}\n"
f"Ada Top Candidates: {cand_summary}\n"  # rank, player_id, name, pos, composite_score
f"Return strict JSON with keys: agent='Arthur', reasoning_2_sentences, top_3_picks, fallback_used=False."
```

**Output JSON Schema:**
```json
{
  "agent": "Arthur",
  "reasoning_2_sentences": "<exactly 2 sentences>",
  "top_3_picks": [
    {"rank": 1, "player_id": "...", "player_name": "...", "position": "...", "composite_score": 0.0},
    {"rank": 2, ...},
    {"rank": 3, ...}
  ],
  "fallback_used": false
}
```

---

### 6.7 Fallback Payload (Ada-Only Mode)

When LLM calls fail/timeout, the system builds a deterministic Arthur-format payload:

```python
{
    "agent": "Arthur",
    "reasoning_2_sentences": (
        f"Ada quant engine prioritizes {p1_name} ({p1_pos}) based on optimal opportunity "
        f"cost and ceiling metrics. Selecting from the top deterministic tier preserves "
        f"key positional value before the next turn cliff."
    ),
    "top_3_picks": [top 3 from ada_rankings],
    "fallback_used": True,
    "marcus_notes": {},   # empty if agents timed out
    "winston_notes": {},
}
```

UI renders this with `st.info("⚡ Ada Deterministic Mode")` instead of `st.success("🤖 Arthur synthesis active")`.

---

## 7. Streamlit UI Architecture

**File:** `ui/app.py` (738 lines)

### 7.1 Session State Keys

```python
draft_mode             # "🎯 Live ESPN Draft" | "🧪 Practice Mock Draft"
draft_id               # e.g. "live_draft_2026"
user_team_slot         # int, 1-based team slot
num_teams              # league size (default: 12)
total_rounds           # draft rounds (default: 16)
is_3rr                 # bool: 3rd Round Reversal active
espn_teams             # list of {team_slot, team_name, owner, team_id}
roster_requirements    # {QB:1, RB:2, WR:2, TE:1, FLEX:1, SUPERFLEX:1, DST:1}
scoring_format         # "PPR" | "HALF_PPR" | "STANDARD"
realtime_listener      # RealtimeListener instance (once per session)
heartbeat_worker       # HeartbeatWorker instance (once per session)
ws_connected           # bool
heartbeat_healthy      # bool
fallback_mode          # bool
keeper_expander_open   # bool
agent_timeout_seconds  # int (3-30, from sidebar slider)
flash_notification     # (type, message) tuple for toast notifications
show_reset_confirm     # bool: triggers reset confirmation dialog
active_grid_pick_no    # currently active pick in full grid
```

### 7.2 Page Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  🏈 The Best Damn Fantasy Football Drafting App                  │
│  Live Draft Assistant | Ada Quant Engine Active                  │
│                                                                  │
│  [sidebar]                [main area: 3 tabs]                    │
│                                                                  │
│  Sidebar:                 Tab 1: 🎯 Live War Room                │
│  - Draft settings         ├─ [3:2 col split]                    │
│  - Multi-Source sync      │   ├─ Recommendations panel (60%)    │
│  - Team selection         │   │   Ada ranked cards + Agent notes │
│  - Keeper manager         │   └─ Draft board (40%)              │
│  - Agent timeout          │       Pick logging searchbox         │
│  - Cheat sheet export     │       Undo Last Pick button          │
│  - System health          │                                      │
│                           Tab 2: 📊 Full Draft Board Grid        │
│                           Tab 3: 📋 My Roster                   │
└─────────────────────────────────────────────────────────────────┘
```

### 7.3 Draft Mode: Live vs Mock

```python
if mode == "🎯 Live ESPN Draft":
    # Real-time pick logging, Realtime listener active
elif mode == "🧪 Practice Mock Draft":
    # Mock Control Bar shown with:
    #   [⏩ Auto-Pick All Opponents Until My Turn]
    #   [🤖 Simulate 1 Bot Pick]
    #   [🗑️ Reset Mock Draft]
    # Bot picks: uses simulate_opponent_pick() which selects top ADP player
```

### 7.4 Snake Draft Pick Calculation

```python
def get_slot_for_pick(p_no: int) -> int:
    r = ((p_no - 1) // num_teams) + 1
    p_in_r = (p_no - 1) % num_teams

    if is_3rr:
        is_even = (r % 2 == 1) if r > 1 else False  # 3RR: rounds 2,3 both reverse
    else:
        is_even = (r % 2 == 0)  # standard snake

    return (num_teams - p_in_r) if is_even else (p_in_r + 1)
```

### 7.5 Picks Until User Turn Calculation

```python
picks_until_user_turn = 0
cur_check = current_pick
while cur_check < current_pick + 20:
    if get_slot_for_pick(cur_check) == user_slot:
        picks_until_user_turn = cur_check - current_pick
        break
    cur_check += 1
```

### 7.6 Callbacks

All callbacks call `st.rerun()` at the end to trigger Streamlit refresh.

```
handle_record_pick()       → upsert_pick() → flash_notification toast
handle_record_keeper()     → record_pick(source='keeper') → flash toast
handle_undo_last_pick()    → undo_last_pick() → flash toast
handle_delete_specific_pick() → delete_specific_pick() → flash toast
handle_reset_draft()       → reset_draft() → flash toast (after confirm dialog)
handle_simulate_pick()     → simulate_opponent_pick() → toast
handle_simulate_to_user_turn() → loop simulate_opponent_pick() → toast
```

---

## 8. Services Layer

### 8.1 DraftStateService (`services/draft_state_service.py`, 407 lines)

Core CRUD layer with Supabase + local memory fallback.

**Key methods:**

| Method | Description |
|---|---|
| `get_available_players(draft_id)` | Returns available players from Supabase or local cache |
| `get_draft_log(draft_id)` | Returns draft_log ordered by pick_no ASC, deduplicated |
| `record_pick(...)` | Inserts PICK event + marks player is_available=false |
| `upsert_pick(...)` | Updates existing pick or inserts new; handles player reassignment |
| `undo_last_pick(draft_id)` | Deletes latest PICK + restores player availability (atomic) |
| `delete_specific_pick(draft_id, pick_no)` | Deletes specific pick by pick_no |
| `reset_draft(draft_id)` | Deletes all picks, restores all players |
| `simulate_opponent_pick(...)` | Auto-picks top ADP player for a bot team |
| `reconcile_state(draft_id)` | Returns (available_players, draft_log) canonical pair |

**Error handling:**
- All Supabase failures are caught and logged
- Schema constraint violations (source check) are retried with `source='import'`
- Local memory fallback activates when `use_supabase=False`

---

### 8.2 RealtimeListener (`services/realtime_listener.py`, 85 lines)

```python
class RealtimeListener:
    # Starts a daemon thread that subscribes to Supabase Realtime channel
    # Listens for INSERT/DELETE on public.draft_log
    # Enqueues events to thread-safe queue
    # poll_events() retrieves and clears queue for UI consumption
```

Usage in `app.py`:
```python
rt_events = st.session_state.realtime_listener.poll_events()
if rt_events:
    st.toast(f"📡 Realtime update: {len(rt_events)} event(s)!")
    st.rerun()
```

---

### 8.3 HeartbeatWorker (`services/heartbeat.py`, 77 lines)

```python
class HeartbeatWorker:
    # REST poll: SELECT pick_no FROM draft_log ORDER BY pick_no DESC LIMIT 1
    # Checks monotonic sequence (last_seen_pick_no vs remote latest)
    # If drift detected: fires on_reconcile_required(latest_pick_no) callback
    # Marks unhealthy if REST fails for > 6 consecutive seconds
    # Default interval: 2.5 seconds
```

---

### 8.4 ActionLogger (`services/action_logger.py`, 32 lines)

Persistent file logger (`war_room_actions.log`) for all UI state changes and actions.

```python
log_action("RECORD_PICK", f"Recording pick #{pick_no} for '{player_name}'", {details_dict})
```

---

## 9. Data Ingestion (`data/espn_ingest.py`, 894 lines)

### 9.1 Main Entry Points

```python
sync_espn_league_data(league_id, season_year, espn_s2, swid, upsert_supabase, use_multi_source)
    → dict: {players, teams, player_count, roster_requirements, scoring_format, used_offline_fallback}

fetch_espn_roster_and_scoring(league_id, season_year, espn_s2, swid)
    → dict: {roster_requirements, scoring_format, total_rounds}
```

### 9.2 Multi-Source Blending

When `use_multi_source=True`:
1. Fetches ESPN players via `espn-api`
2. Blends Sleeper ADP (`services/sleeper_client.py`)
3. Blends FantasyPros ECR (`services/fantasypros_client.py`)
4. Blends depth chart data (`services/depth_chart_service.py`)
5. Produces `consensus_adp = weighted blend`

UI weights (configurable via sidebar sliders):
- FantasyPros ECR: 50%
- Sleeper ADP: 25%
- ESPN Projection: 25%

### 9.3 Position Variance Table

Realistic projection variance by position:
```python
POSITION_VARIANCE = {
    "QB":  {"floor": 0.72, "ceiling": 1.28},
    "RB":  {"floor": 0.68, "ceiling": 1.32},
    "WR":  {"floor": 0.70, "ceiling": 1.30},
    "TE":  {"floor": 0.65, "ceiling": 1.35},
    "K":   {"floor": 0.80, "ceiling": 1.20},
    "DST": {"floor": 0.60, "ceiling": 1.40},
}
```

### 9.4 Handcuff Mapping

`HANDCUFF_MAP` is a hardcoded dictionary mapping primary RB `player_id` → backup `player_id` for major NFL RB1s. Applied during `apply_handcuff_mappings()` post-ingest.

### 9.5 Offline Fallback

When ESPN API fails: falls back to `data/seed/sample_players.csv`, sets `used_offline_fallback=True`.

---

## 10. Cheat Sheet Export (`engine/cheat_sheet.py`)

Four export modes:

| Function | Output Format | Sorting |
|---|---|---|
| `generate_csv_cheat_sheet(players)` | CSV | Grouped by position, sorted by ADP |
| `generate_printable_html_cheat_sheet(players, title)` | Styled HTML | Grouped by position |
| `generate_ranked_csv_cheat_sheet(rankings)` | CSV | Ada composite score rank |
| `generate_ranked_html_cheat_sheet(rankings, title)` | Styled HTML | Ada composite score rank |

Header branding: "The Best Damn Fantasy Football Drafting App"

---

## 11. Test Suite (49 Tests, 13 Files)

| File | # Tests | Coverage Area |
|---|---|---|
| `test_ada_math.py` | ~8 | AdaQuantEngine compute_rankings + FCVS/OC edge cases |
| `test_agent_schema_validation.py` | ~6 | JSON schema validation for Marcus/Winston/Arthur |
| `test_bye_week_injury.py` | ~3 | Bye week and injury status pass-through |
| `test_cheat_sheet.py` | ~4 | CSV/HTML export generation |
| `test_draft_log_undo.py` | ~5 | Atomic undo + state rollback |
| `test_espn_ingest.py` | ~3 | Ingestion pipeline + position variance |
| `test_full_draft_grid.py` | ~3 | Grid rendering + pick insertion logic |
| `test_hli_logic.py` | ~5 | HLI multipliers + non-RB weight redistribution |
| `test_keeper_manager.py` | ~4 | Keeper locking via UI |
| `test_multisource_services.py` | ~3 | Sleeper + FantasyPros client integrations |
| `test_ppr_adjustment.py` | ~2 | PPR/Half-PPR/Standard projection math |
| `test_prv_detection.py` | ~5 | Gradient PRV multiplier + tier cliff detection |
| `test_vor.py` | ~8 | VOR/VORP formula + FLEX/SUPERFLEX replacement level |

**Run:** `python -m pytest` (all 49 pass as of last commit)

---

## 12. Configuration & Environment

### 12.1 `.env` Variables

```bash
# Supabase
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_KEY=<anon or service key>

# ESPN League
ESPN_LEAGUE_ID=<int>
ESPN_SEASON_YEAR=2026
ESPN_S2_COOKIE=<from browser>
ESPN_SWID_COOKIE={<uuid>}

# LLM
GEMINI_API_KEY=<key>
GEMINI_MODEL_NAME=gemini-flash-latest
GEMINI_FALLBACK_MODEL=gemini-flash-latest

# Ingest control
INGEST_DRY_RUN=true
```

### 12.2 Default Roster Requirements

```python
{"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "SUPERFLEX": 1, "DST": 1}
```

Overridden by ESPN API fetch during data sync.

---

## 13. Key Design Decisions & Non-Negotiables

1. **Frontend is Streamlit** — No React/Vue/other framework.
2. **Ada math is 100% deterministic Python** — No LLM math delegation. LLMs are only used for narrative synthesis.
3. **5-second hard timeout per LLM call** — Never block draft board for agent delay.
4. **Fan-Out/Fan-In triggered at picks_until_user_turn ≤ 2** — Gives agents time to deliberate before user's turn.
5. **Undo Last Pick is atomic** — DELETE from draft_log + UPDATE available_players in a single Supabase transaction.
6. **Realtime via Supabase WebSocket + REST heartbeat fallback** — Eventually consistent, never broken.
7. **Strict JSON schema validation** per agent — Agent output failures are silently caught and fallback activates.
8. **All agent system prompts** include: "Never claim a pick was persisted unless save confirmation is explicit."
9. **Gemini API rate limit**: Free tier is 5 RPM. The agent timeout slider (3–30s) gives users control.

---

## 14. Known Limitations & Open Items

1. **Supabase Realtime** — The WebSocket listener `_run_listener` subscribes but does not implement a blocking keep-alive loop. This means the subscription fires once and may not persist reconnects across session restarts.
2. **`HeartbeatWorker.check_heartbeat()` type hint bug** — Returns `Tuple[bool, int]` but the import for `Tuple` from `typing` is missing from the type annotation on line 35 (uses `Tuple` without the `from typing import Tuple` guard).
3. **Thread safety of `DraftStateService._local_available_players`** — The in-memory dict is not protected by a lock when accessed from multiple threads (realtime listener + heartbeat + main Streamlit thread).
4. **`importlib.reload(dss_mod)` on every render** — `ui/app.py` line 86-87 reloads `draft_state_service` on every Streamlit page load, which is unusual and may cause state issues with persistent background threads.
5. **Agent timeout budget split** — 60% fan-out / 40% fan-in split is hardcoded. On a 15s timeout, Arthur gets only 6 seconds, which may be tight for complex synthesis.
6. **Sleeper projections endpoint** — `fetch_sleeper_projections()` uses `/projections/nfl/{year}` which is unofficial and undocumented — may not exist or change.
7. **`is_3rr` logic** — The 3RR pick slot logic (`if r == 1: is_even = False else: is_even = (r % 2 == 1)`) inverts all rounds after 1, not just rounds 2 and 3. This may be intentional but differs from standard 3RR rules which only reverse rounds 2 and 3.
8. **No auth or multi-user isolation** — The app assumes a single user/session. `draft_id` is a string key with no user-level access control.
9. **Gemini `google-generativeai` not in requirements.txt** — The LLM client (`war_room_agents.py`) imports `google.generativeai` but this package is absent from `requirements.txt`.

---

## 15. Potential Enhancement Areas (From to-do.md Sprints)

All listed sprints (1–4) are complete. Potential next-phase enhancements:
- Live ESPN draft pick auto-import (scrape ESPN draft interface directly)
- ADP trend lines (comparing current consensus ADP to pre-draft ADP)
- Draft grade summary post-pick (how did your pick compare to field?)
- Trade value calculator integration
- Dynasty/keeper league mode (multi-year roster tracking)
- Slack/Discord webhook notifications for when it's your turn

---

*Document generated from source code as of commit `91e6061` on `2026-08-06`.*
*Repository: `jablack10716/ff-espn-war-room`*
