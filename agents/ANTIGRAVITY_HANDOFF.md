# Antigravity Handoff: Next.js + FastAPI Engine & Architectural Rules

## Scope
This project operates on a modern **Next.js (React / TailwindCSS / TypeScript)** client and a high-performance **FastAPI (Python 3.13)** backend engine. The legacy Streamlit prototype UI has been fully removed.

## Active Stack Architecture
1. **Client**: Next.js App Router ([`client/`](file:///c:/Code/FF-War-Room/client)), Zustand store ([`useDraftStore.ts`](file:///c:/Code/FF-War-Room/client/stores/useDraftStore.ts)), WebSockets `<10ms` state synchronization.
2. **Backend**: FastAPI ([`server/main.py`](file:///c:/Code/FF-War-Room/server/main.py)), Uvicorn ASGI server, Ada Quant Math Engine ([`engine/ada_math.py`](file:///c:/Code/FF-War-Room/engine/ada_math.py)).
3. **Database**: Supabase PostgreSQL with local seed fallback capability.

