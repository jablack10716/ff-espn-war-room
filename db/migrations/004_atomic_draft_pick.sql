-- Migration 004: Atomic Draft Pick Stored Procedure
-- Wraps available_players check & lock and draft_log insertion in a single ACID transaction.

CREATE OR REPLACE FUNCTION record_pick_atomic(
    p_draft_id TEXT,
    p_pick_no INT,
    p_round_no INT,
    p_team_slot INT,
    p_player_id TEXT,
    p_player_name TEXT,
    p_position TEXT,
    p_team_name TEXT DEFAULT NULL,
    p_picked_by_user BOOLEAN DEFAULT FALSE,
    p_source TEXT DEFAULT 'user',
    p_notes TEXT DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_player record;
    v_pick record;
BEGIN
    -- 1. Lock the player row in available_players for UPDATE
    SELECT * INTO v_player
    FROM public.available_players
    WHERE player_id = p_player_id
    FOR UPDATE;

    -- If player doesn't exist or is already taken (not available), return failure
    IF NOT FOUND THEN
        -- Allow recording unknown/placeholder players even if not in pool
        NULL;
    ELSIF NOT v_player.is_available THEN
        RETURN jsonb_build_object(
            'success', false,
            'message', 'Player already drafted'
        );
    ELSE
        -- Mark player unavailable
        UPDATE public.available_players
        SET is_available = FALSE
        WHERE player_id = p_player_id;
    END IF;

    -- 2. Insert into draft_log
    INSERT INTO public.draft_log (
        draft_id,
        pick_no,
        round_no,
        team_slot,
        player_id,
        player_name,
        position,
        team_name,
        picked_by_user,
        source,
        notes,
        created_at
    )
    VALUES (
        p_draft_id,
        p_pick_no,
        p_round_no,
        p_team_slot,
        p_player_id,
        p_player_name,
        p_position,
        p_team_name,
        p_picked_by_user,
        p_source,
        p_notes,
        NOW()
    )
    ON CONFLICT (draft_id, pick_no) DO UPDATE SET
        round_no = EXCLUDED.round_no,
        team_slot = EXCLUDED.team_slot,
        player_id = EXCLUDED.player_id,
        player_name = EXCLUDED.player_name,
        position = EXCLUDED.position,
        team_name = EXCLUDED.team_name,
        picked_by_user = EXCLUDED.picked_by_user,
        source = EXCLUDED.source,
        notes = EXCLUDED.notes,
        created_at = NOW()
    RETURNING * INTO v_pick;

    RETURN jsonb_build_object(
        'success', true,
        'pick', to_jsonb(v_pick)
    );
END;
$$;
