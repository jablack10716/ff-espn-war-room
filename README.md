# Fantasy Football AI War Room 🏈🤖

The Fantasy Football AI War Room is a real-time, high-throughput draft assistant built for live ESPN fantasy football drafts. It combines a **deterministic Python Quant Engine** (Ada) with a **Multi-Agent LLM Debate system** (Marcus, Winston, Arthur) to provide championship-caliber drafting recommendations under live draft time constraints.

## 🚀 Features

- **Real-Time ESPN Draft Sync**: Instantly detects picks made in your ESPN draft via Supabase Realtime WebSockets.
- **Ada Quant Engine**: A lightning-fast, purely deterministic math engine that scores players on:
  - **VORP** (Value Over Replacement Player)
  - **FCVS** (Floor-to-Ceiling Variance Shift based on draft round)
  - **HLI** (Handcuff Leverage Index)
  - **PRV** (Positional Run Velocity and Tier Cliff Detection)
  - **Opportunity Cost** and **RosterFit Scarcity**
- **Multi-Agent GM Synthesis**: When you are on the clock, a Fan-Out/Fan-In LLM graph activates:
  - **Marcus (Chief Scout)**: Analyzes player upside and injury risk.
  - **Winston (Roster Architect)**: Analyzes roster synergy and bye week conflicts.
  - **Arthur (General Manager)**: Synthesizes Marcus, Winston, and Ada's math into a final 2-sentence recommendation and top 3 picks.
- **Strict Latency Guarantees**: Hard 5-second cap on LLM generation with automatic fallback to Ada's math so you never miss a pick.
- **Offline Backup Cheat Sheets**: Export Ada's Master Rankings to printable HTML or CSV formats for emergency use if internet goes down on draft day.

## 🛠️ Quick Start

### 1. Install Dependencies
```bash
python -m pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env` and fill in your keys:
- `SUPABASE_URL` and `SUPABASE_KEY` (Required for Realtime DB)
- `OPENROUTER_API_KEY` (Required for AI Agents)
- `ESPN_S2` and `SWID` (Required to sync your ESPN league data)

### 3. Sync Your League Data
Use the ESPN ingest script to pull your league's scoring rules, rosters, and player pool into Supabase:
```bash
python data/espn_ingest.py
```

### 4. Run the War Room Dashboard
Launch the Streamlit interface:
```bash
streamlit run ui/app.py
```

## 📚 Documentation Index

- **Single Source of Truth**: [`WAR_ROOM_SPEC.md`](WAR_ROOM_SPEC.md) (Architecture, Data Flow, Formulas)
- **Master Checklist**: [`to-do.md`](to-do.md)
- **Automated Tests**: Run `python -m pytest` to execute the 35-test verification suite.
