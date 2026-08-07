-- Migration 004: Add Multi-Source Player Data Columns
-- Supports Sleeper ADP, FantasyPros ECR, Analyst Tiers, Projected Receptions, and Consensus ADP.

alter table if exists public.available_players
    add column if not exists consensus_adp numeric(6,2),
    add column if not exists sleeper_adp numeric(6,2),
    add column if not exists analyst_tier smallint,
    add column if not exists projected_receptions numeric(5,1),
    add column if not exists fp_ecr numeric(6,2),
    add column if not exists data_sources jsonb default '["espn"]'::jsonb;

create index if not exists idx_available_players_consensus_adp
    on public.available_players (consensus_adp);

create index if not exists idx_available_players_analyst_tier
    on public.available_players (analyst_tier);
