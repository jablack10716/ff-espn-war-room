# The Best Damn Fantasy Football Drafting App 🏈🤖

**The Best Damn Fantasy Football Drafting App** is a real-time, high-throughput draft assistant built for live ESPN fantasy football drafts. It combines a **deterministic Python Quant Engine** (Ada) with a **Multi-Agent LLM Debate system** (Marcus, Winston, Arthur) to provide championship-caliber drafting recommendations under live draft time constraints.

## 🚀 Features

- **7-Source Blended Data Ingestion Pipeline**: Blends market consensus and dynamic sharp data feeds:
  - 🏈 **ESPN Platform Baseline**
  - 📈 **Sleeper ADP API**
  - 🎯 **FantasyPros Consensus ECR**
  - ⚡ **Underdog High-Stakes ADP** (Real Money)
  - 🎲 **Vegas Sportsbook Props** (Passing/Rushing/Receiving Over/Under Implied Points)
  - 🔬 **High-Stakes Projections** (Establish The Run / 4for4 / PFF)
  - 📊 **Advanced Opportunity Metrics** (Air Yards Share, Target Share, Expected Fantasy Points xFP)
- **Granular Data Source Controls & Feed Audit**: Interactive toggles in the UI modal with live `🟢 OK` status breakdowns.
- **Modern Web Architecture**: Next.js / React / Tailwind CSS web dashboard (`client/`) powered by a high-throughput FastAPI Python engine (`server/`).
- **Ada Quant Engine**: A lightning-fast, purely deterministic math engine scoring players on:
  - **Hybrid VOR Baseline**: Hybrid mathematical average of VORP (best unrostered player) and VOLS (worst starting player).
  - **Continuous FCVS**: Smooth linear interpolation decaying Floor weight (80% -> 10%) pick-by-pick across 160 draft slots.
  - **Monte Carlo Opportunity Cost**: 200-iteration draft simulation with Gaussian noise ($\sigma=10\%$) and state-seeded determinism.
  - **HLI** (Handcuff Leverage Index & primary NFL RB backup mapping)
  - **PRV** (Positional Run Velocity & Tier Cliff Detection)
  - **RosterFit Scarcity**: Scarcity-aware positional demand gradient.
- **Multi-Agent GM Synthesis**: Fan-Out/Fan-In LLM graph debating live candidate recommendations:
  - **Marcus (Chief Scout)**: Evaluates player upside, injury risk, and Vegas/Underdog market metrics.
  - **Winston (Roster Architect)**: Evaluates roster synergy, positional urgency, and Bye week conflicts.
  - **Arthur (General Manager)**: Synthesizes Marcus, Winston, and Ada's quantitative math into a 2-sentence recommendation and top 3 picks.
- **Resilient Micro-Retry Architecture**: 2-attempt micro-retry loop for fast-failing API calls with schema relaxation and automatic deterministic fallback.
- **Offline Backup Cheat Sheets**: Export Ada's Master Rankings to printable HTML or CSV formats for emergency use if internet drops on draft day.

## 🛠️ Quick Start

### 1. Install Dependencies
```bash
python -m pip install -r requirements.txt
cd client && npm install && cd ..
```

### 2. Configure Environment
Copy `.env.example` to `.env` and fill in your keys:
- `SUPABASE_URL` and `SUPABASE_KEY` (Required for Realtime DB)
- `GEMINI_API_KEY` (Required for AI War Room Agents)
- `ESPN_LEAGUE_ID`, `ESPN_S2_COOKIE`, and `ESPN_SWID_COOKIE` (Required to sync ESPN league data)

### 3. Run FastAPI Backend & Dashboard
```bash
# Terminal 1: FastAPI Backend Engine
uvicorn server.main:app --reload --port 8000

# Terminal 2: Next.js React Dashboard
cd client && npm run dev
```

## 📚 Documentation & Verification

- **Master Documentation Audit**: [`master_documentation_audit.md`](master_documentation_audit.md)
- **Single Source of Truth**: [`WAR_ROOM_SPEC.md`](WAR_ROOM_SPEC.md) (Architecture, Data Flow, Formulas)
- **Master Checklist**: [`to-do.md`](to-do.md)
- **Automated Test Suite**: Run `python -m pytest` to execute the **65-test** verification suite.
