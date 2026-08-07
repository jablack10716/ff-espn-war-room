-- Supabase DDL Migration for Year-Over-Year Draft Telemetry
CREATE TABLE IF NOT EXISTS draft_decision_telemetry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    draft_id TEXT NOT NULL,
    pick_number INT NOT NULL,
    round INT NOT NULL,
    selected_player_id TEXT NOT NULL,
    selected_player_name TEXT NOT NULL,
    
    -- Ada Model State at Time of Pick
    ada_rank_recommended INT,
    ada_composite_score FLOAT,
    projected_points_median FLOAT,
    projected_floor FLOAT,
    projected_ceiling FLOAT,
    dynamic_vorp FLOAT,
    opportunity_cost_delta FLOAT,
    fcvs_weight_applied TEXT,
    hli_multiplier_applied FLOAT,
    prv_alert_active BOOLEAN,
    
    -- Market & Draft State
    consensus_ecr_rank INT,
    adp_at_draft_time FLOAT,
    adp_survival_prob_to_next_turn FLOAT,
    qbs_drafted_count INT,
    rbs_drafted_count INT,
    wrs_drafted_count INT,
    
    -- Agent Reasoning Context
    marcus_pitch TEXT,
    winston_pitch TEXT,
    arthur_gm_reasoning TEXT,
    created_at TIMESTAMP WITH TIMEZONE DEFAULT NOW()
);
