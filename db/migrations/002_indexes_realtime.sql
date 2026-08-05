-- 002_indexes_realtime.sql
-- Section 3 DDL: indexes and Supabase Realtime configuration.

create index if not exists idx_available_players_availability
    on public.available_players (is_available, position, tier);

create index if not exists idx_available_players_team_position
    on public.available_players (team, position);

create index if not exists idx_available_players_normalized_name
    on public.available_players (normalized_name);

create index if not exists idx_available_players_handcuff_for
    on public.available_players (handcuff_for_player_id);

-- One pick per draft slot unless explicitly undone via event semantics
create unique index if not exists uq_draft_log_draft_pick
    on public.draft_log (draft_id, pick_no)
    where event_type = 'PICK';

create index if not exists idx_draft_log_draft_created
    on public.draft_log (draft_id, created_at desc);

create index if not exists idx_draft_log_draft_round_pick
    on public.draft_log (draft_id, round_no, pick_no);

create index if not exists idx_draft_log_player
    on public.draft_log (player_id);

alter table public.draft_log replica identity full;
alter publication supabase_realtime add table public.draft_log;
