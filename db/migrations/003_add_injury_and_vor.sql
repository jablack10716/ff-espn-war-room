-- Migration 003: Add injury_status column to public.available_players
ALTER TABLE public.available_players ADD COLUMN IF NOT EXISTS injury_status TEXT DEFAULT 'ACTIVE';
