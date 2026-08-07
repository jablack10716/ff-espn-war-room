# Streamlit & Draft State Reliability Rules

This rule file documents critical architectural constraints and lessons learned for state management, Streamlit dialogs, and Supabase event logs in the Fantasy Football AI War Room codebase.

## 1. Mandatory Explicit Widget Keys in Dynamic Layouts
- **Rule**: EVERY `st.button`, `st.selectbox`, `st.text_input`, or interactive widget rendered inside dynamic components, loops, or conditional blocks (such as `_manage_pick_dialog`) **MUST HAVE AN EXPLICIT, UNIQUE `key=` PARAMETER**.
- **Rationale**: Streamlit's default auto-key assignment uses positional index in the block. When conditional layouts shift (e.g., swapping a pick vs assigning a pick), missing keys cause Streamlit to mismatch widget indices on rerun, triggering incorrect or destructive button handlers (e.g. executing Vacate instead of Save).

## 2. Event Log Deduplication & Timestamp Sorting
- **Rule**: All data retrieval methods that fetch event logs from Supabase or local memory (e.g. `DraftStateService.get_draft_log`) **MUST sort by `created_at ASC` and deduplicate entries by key (`pick_no`)**, keeping only the latest event.
- **Rationale**: Swaps or updates to pick events can result in multiple log entries. If the query does not order by creation timestamp and deduplicate, dictionary lookups in the UI (`pick_map[pick_no] = event`) can be overwritten by older rows depending on database return order.

## 3. Separation of Destructive Actions in UI Modals
- **Rule**: Destructive actions (e.g. `Erase Pick & Leave Blank`) **MUST be isolated in a dedicated collapsible expander (`with st.expander("🗑️ Danger Zone: Erase Pick..."):`) at the bottom of the modal**.
- **Rationale**: Prominently placing clear/erase buttons at the top of an edit modal causes user error, as users frequently click "Clear" under the assumption that they must clear out the old player before selecting a replacement.

## 4. Hot-Reload Module Freshness
- **Rule**: Core UI components using `@st.dialog` or complex service classes should be reloaded via `importlib.reload(...)` inside `ui/app.py` when rendered.
- **Rationale**: Long-running Streamlit processes can cache decorated functions in `sys.modules`. `importlib.reload` ensures that file edits on disk are immediately active without requiring a server restart.
