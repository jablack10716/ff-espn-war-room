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
    v_existing_player_id TEXT;
BEGIN
    -- 1. Check if pick already exists at this slot
    SELECT player_id INTO v_existing_player_id
    FROM public.draft_log
    WHERE draft_id = p_draft_id AND pick_no = p_pick_no;

    -- 2. Lock the new player row in available_players for UPDATE
    SELECT * INTO v_player
    FROM public.available_players
    WHERE player_id = p_player_id
    FOR UPDATE;

    -- If player doesn't exist or is already taken by another pick slot, return failure
    IF NOT FOUND THEN
        -- Allow recording unknown/placeholder players even if not in pool
        NULL;
    ELSIF NOT v_player.is_available AND (v_existing_player_id IS NULL OR v_existing_player_id != p_player_id) THEN
        RETURN jsonb_build_object(
            'success', false,
            'message', 'Player already drafted'
        );
    ELSE
        -- Mark new player unavailable
        UPDATE public.available_players
        SET is_available = FALSE
        WHERE player_id = p_player_id;
    END IF;

    -- 3. If there was a different player in this slot, restore their availability
    IF v_existing_player_id IS NOT NULL AND v_existing_player_id != p_player_id THEN
        UPDATE public.available_players
        SET is_available = TRUE
        WHERE player_id = v_existing_player_id;
    END IF;

    -- 4. Insert into draft_log
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
