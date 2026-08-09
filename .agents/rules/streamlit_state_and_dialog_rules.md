# Web State & UI Reliability Rules

This rule file documents critical architectural constraints and lessons learned for state management, React store updates, and Supabase event logs in the Fantasy Football AI War Room codebase.

## 1. Mandatory Explicit Component Keys & Atomic State Updates
- **Rule**: All interactive components rendered inside dynamic React lists (e.g. `FullDraftGrid`, `PickInput`) MUST have explicit unique `key` props.
- **Rationale**: Prevents React DOM reconciliation mismatches when draft state or candidate rankings update in real time.

## 2. Event Log Deduplication & Timestamp Sorting
- **Rule**: All data retrieval methods that fetch event logs from Supabase or local memory (`DraftStateService.get_draft_log`) MUST sort by `created_at ASC` and deduplicate entries by key (`pick_no`), keeping only the latest event.
- **Rationale**: Swaps or updates to pick events can result in multiple log entries. If the query does not order by creation timestamp and deduplicate, dictionary lookups in the UI can be overwritten by older rows depending on database return order.

## 3. Separation of Destructive Actions in UI Modals
- **Rule**: Destructive actions (e.g., `Erase Pick & Leave Blank`) MUST be visually isolated in a dedicated Danger Zone section at the bottom of modals.
- **Rationale**: Prominently placing clear/erase buttons at the top of an edit modal causes user error.
