-- Migration 005: Allow 'keeper' in draft_log source constraint
alter table if exists public.draft_log
    drop constraint if exists draft_log_source_check;

alter table if exists public.draft_log
    add constraint draft_log_source_check
    check (source in ('manual', 'import', 'system', 'keeper'));
