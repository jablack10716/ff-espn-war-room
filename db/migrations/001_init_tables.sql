-- 001_init_tables.sql
-- Section 3 DDL: base tables and supporting trigger objects.

create table if not exists public.available_players (
    player_id text primary key,
    full_name text not null,
    normalized_name text not null,
    team text,
    position text not null check (position in ('QB','RB','WR','TE','K','DST')),
    bye_week smallint check (bye_week between 1 and 18),

    -- Tiering and baseline projections
    tier smallint not null check (tier >= 1),
    adp numeric(6,2),
    projection_floor numeric(7,2) not null,
    projection_median numeric(7,2) not null,
    projection_ceiling numeric(7,2) not null,

    -- Handcuff metadata
    depth_role text, -- e.g. RB1, RB2, backup
    handcuff_for_player_id text,

    -- Derived and operational fields
    is_available boolean not null default true,
    last_metric_refresh_ts timestamptz,

    -- Audit
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.draft_log (
    event_id bigint generated always as identity primary key,
    draft_id text not null,

    pick_no integer not null check (pick_no > 0),
    round_no integer not null check (round_no > 0),

    team_slot integer not null check (team_slot > 0),
    team_name text,

    player_id text not null,
    player_name text not null,
    position text not null check (position in ('QB','RB','WR','TE','K','DST')),

    picked_by_user boolean not null default false,

    -- Event typing for atomic undo support
    event_type text not null check (event_type in ('PICK','UNDO')),

    -- Optional reason/context fields
    source text not null default 'manual' check (source in ('manual','import','system')),
    notes text,

    -- Concurrency and ordering
    client_mutation_id uuid,

    created_at timestamptz not null default now()
);

-- Track update timestamps automatically
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_available_players_updated_at on public.available_players;
create trigger trg_available_players_updated_at
before update on public.available_players
for each row execute function public.set_updated_at();
