export interface Player {
  player_id: string;
  player_name?: string;
  full_name?: string;
  position: string;
  team: string;
  tier?: number;
  adp?: number | null;
  consensus_adp?: number | null;
  sleeper_adp?: number | null;
  bye_week?: number | null;
  injury_status?: string;
  projection_median?: number;
  composite_score?: number;
  rank?: number;
  value_gap?: number;
  is_available?: boolean;
  breakdown?: {
    oc_raw?: number;
    oc_norm?: number;
    vor_raw?: number;
    vor_norm?: number;
    fcvs_raw?: number;
    fcvs_norm?: number;
    hli_raw?: number;
    hli_norm?: number;
    prv_mult?: number;
    prv_norm?: number;
    roster_fit_mult?: number;
    rfit_norm?: number;
  };
}

export interface PickEvent {
  draft_id: string;
  pick_no: number;
  round_no: number;
  team_slot: number;
  team_name?: string;
  player_id: string;
  player_name: string;
  position: string;
  picked_by_user: boolean;
  event_type: string;
  source?: string;
  notes?: string;
}

export interface ESPNTeam {
  team_slot: number;
  team_name: string;
  owner: string;
  abbrev?: string;
}

export interface AgentAdvisories {
  top_3_picks?: Array<{
    rank: number;
    player_id: string;
    player_name: string;
    position: string;
    composite_score: number;
    marcus_upside?: string;
    winston_need?: string;
    arthur_reasoning?: string;
  }>;
  reasoning_2_sentences?: string;
  marcus_notes?: Record<string, string>;
  winston_notes?: Record<string, string>;
  fallback_used?: boolean;
  marcus_fallback?: boolean;
  winston_fallback?: boolean;
}

export interface DraftStatePayload {
  draft_id: string;
  user_team_slot: number;
  num_teams: number;
  current_pick: number;
  current_round: number;
  team_on_clock: number;
  picks_until_user_turn: number;
  is_user_on_clock: boolean;
  draft_log: PickEvent[];
  user_roster: PickEvent[];
  roster_by_position: Record<string, PickEvent[]>;
  ada_rankings: Player[];
  agent_advisories?: AgentAdvisories | null;
  espn_teams?: ESPNTeam[];
  scoring_format?: string;
  roster_requirements?: Record<string, number>;
  is_3rr?: boolean;
  draft_started?: boolean;
}
