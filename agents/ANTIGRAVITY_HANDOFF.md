# Antigravity Handoff: Draft Grid Hotfixes & Architectural Rules

## Scope
This handoff covers the Full Draft Board Grid edit/swap flow regressions fixed on 2026-08-06 and the persistent rules established to prevent future regressions.

## What Was Fixed
1. **Dialog Reopen Loop**: Replaced manual `st.session_state` modal tracking with native Streamlit `@st.dialog` lifecycle execution inside `st.button` handlers.
2. **Key Collision & False Vacate Actions**: Added explicit unique keys (`key=f"modal_save_btn_{pick_no}"`, `key=f"modal_vacate_btn_{pick_no}"`) to all modal buttons to prevent Streamlit widget index mismatch when layouts shift.
3. **UX Danger Zone Isolation**: Moved `Erase Pick & Leave Blank` into a collapsible `Danger Zone` expander at the bottom of the modal so users cannot accidentally click it when attempting to swap players.
4. **Log Deduplication & Timestamp Sorting**: Updated `DraftStateService.get_draft_log` to order events by `created_at ASC` and deduplicate by `pick_no` so the latest swapped player ALWAYS overwrites older events.
5. **Dynamic Hot-Reload Protection**: Added `importlib.reload(...)` for core component modules and `DraftStateService` inside `ui/app.py` to guarantee fresh in-memory bytecode across reruns.
6. **Action Logging**: Integrated persistent file logging (`war_room_actions.log`) to trace every UI interaction and callback execution.

## Rules Documented for Future Development
A permanent agent rule file has been saved at [`.agents/rules/streamlit_state_and_dialog_rules.md`](file:///c:/Code/FF-War-Room/.agents/rules/streamlit_state_and_dialog_rules.md).

Summary of rules:
1. **Mandatory Explicit Widget Keys**: Always pass unique `key=` arguments to widgets in dynamic/conditional blocks.
2. **Deduplication in Event Logs**: Always order log queries by `created_at ASC` and deduplicate by `pick_no`.
3. **Destructive Action Isolation**: Keep primary actions (`Save Replacement Player`) top and center; isolate destructive actions in expanders.
4. **Module Hot-Reloading**: Use `importlib.reload` in `app.py` for decorated components to avoid stale Python memory caches.
