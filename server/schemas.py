from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PickRequest(BaseModel):
    player_id: str
    pick_number: Optional[int] = None
    drafted_by_user: bool = False
    team_slot: Optional[int] = None
    draft_id: Optional[str] = "default_draft_2026"
    notes: Optional[str] = None


class UndoRequest(BaseModel):
    draft_id: Optional[str] = "default_draft_2026"


class ResetRequest(BaseModel):
    draft_id: Optional[str] = "default_draft_2026"


class StateQuery(BaseModel):
    draft_id: Optional[str] = "default_draft_2026"
    user_team_slot: Optional[int] = 1


class SyncESPNRequest(BaseModel):
    league_id: Optional[int] = None
    season_year: Optional[int] = 2026
    espn_s2: Optional[str] = None
    swid: Optional[str] = None
    use_multi_source: bool = True
    enable_sleeper_adp: bool = True
    enable_fantasypros_ecr: bool = True
    enable_underdog_adp: bool = True
    enable_vegas_props: bool = True
    enable_high_stakes_projections: bool = True
    enable_advanced_metrics: bool = True
    draft_id: Optional[str] = "default_draft_2026"


class ConfigUpdateRequest(BaseModel):
    user_team_slot: Optional[int] = None
    num_teams: Optional[int] = None
    is_3rr: Optional[bool] = None
    draft_id: Optional[str] = "default_draft_2026"


class KeeperRequest(BaseModel):
    player_id: str
    team_slot: int
    round_no: int
    draft_id: Optional[str] = "default_draft_2026"


class KeeperUndoRequest(BaseModel):
    draft_id: Optional[str] = "default_draft_2026"
