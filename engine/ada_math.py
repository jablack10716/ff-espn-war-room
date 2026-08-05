"""Phase 2 target: pure deterministic Ada quant math engine implementation.

Computes Opportunity Cost (OC), Floor-to-Ceiling Variance Shift (FCVS),
Handcuff Leverage Index (HLI), Positional Run Velocity (PRV), and RosterFit,
and combines them into deterministic, auditable composite candidate rankings.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from engine.scoring_models import (
    calculate_fcvs_raw,
    calculate_hli_raw,
    calculate_roster_fit,
    calculate_vor,
    min_max_normalize,
    z_score_normalize,
)
from engine.tier_cliff import calculate_prv_multiplier

LOGGER = logging.getLogger("ada_math")


def estimate_best_at_next_turn(
    position: str,
    available_players: Sequence[Dict[str, Any]],
    picks_until_next_turn: int,
) -> float:
    """Estimate expected best projection median remaining at next turn.

    Simulates the drafting of `picks_until_next_turn` players using ADP ranking.
    Counts how many players of `position` would be taken in those picks ($k$),
    and returns the projection_median of the $(k+1)$-th best player at $position$.
    """
    pos_players = [
        p for p in available_players
        if str(p.get("position", "")).upper() == position.upper()
        and p.get("is_available", True)
    ]

    if not pos_players:
        return 0.0

    # Sort position pool by projection median DESC
    pos_players_sorted = sorted(
        pos_players,
        key=lambda x: float(x.get("projection_median") or 0.0),
        reverse=True,
    )

    if picks_until_next_turn <= 0:
        return float(pos_players_sorted[0].get("projection_median") or 0.0)

    # Sort entire available pool by ADP ASC to simulate draft run
    all_available = [p for p in available_players if p.get("is_available", True)]
    all_available_by_adp = sorted(
        all_available,
        key=lambda x: float(x.get("adp") if x.get("adp") is not None else 999.0),
    )

    simulated_drafted = all_available_by_adp[:picks_until_next_turn]
    k_drafted_of_pos = sum(
        1 for p in simulated_drafted
        if str(p.get("position", "")).upper() == position.upper()
    )

    target_index = k_drafted_of_pos
    if target_index < len(pos_players_sorted):
        return float(pos_players_sorted[target_index].get("projection_median") or 0.0)

    return 0.0


def calculate_opportunity_cost_raw(
    player: Dict[str, Any],
    available_players: Sequence[Dict[str, Any]],
    picks_until_next_turn: int,
) -> float:
    """Calculate raw Opportunity Cost (OC) for a player.

    OC_raw = projection_median(player) - expected_best_at_next_turn(position)
    """
    pos = str(player.get("position", "")).upper()
    median = float(player.get("projection_median") or 0.0)
    expected_best = estimate_best_at_next_turn(pos, available_players, picks_until_next_turn)
    return round(median - expected_best, 4)


class AdaQuantEngine:
    """Deterministic Quantitative Engine for Fantasy Football Draft Ranking."""

    def __init__(self, weights: Optional[Dict[str, float]] = None) -> None:
        if weights is None:
            weights = {
                "w_oc": 0.20,
                "w_fcvs": 0.20,
                "w_hli": 0.15,
                "w_prv": 0.10,
                "w_roster_fit": 0.15,
                "w_vor": 0.20,
            }
        self.weights = weights

    def compute_rankings(
        self,
        available_players: Sequence[Dict[str, Any]],
        draft_log: Sequence[Dict[str, Any]],
        user_team_slot: int = 1,
        current_round: int = 1,
        current_pick: int = 1,
        picks_until_next_turn: int = 1,
        roster_requirements: Optional[Dict[str, int]] = None,
        scoring_format: str = "STANDARD",
        num_teams: int = 12,
    ) -> List[Dict[str, Any]]:
        """Compute ranked player recommendations with scoring breakdown snapshots."""
        # Filter available players
        candidates = [p for p in available_players if p.get("is_available", True)]
        if not candidates:
            return []

        # Reconstruct team rosters from draft_log
        all_rosters: Dict[int, List[Dict[str, Any]]] = {}
        recent_picks: List[Dict[str, Any]] = []

        for event in draft_log:
            if str(event.get("event_type", "PICK")).upper() == "PICK":
                slot = int(event.get("team_slot", 1))
                all_rosters.setdefault(slot, []).append(event)
                recent_picks.append(event)

        user_roster = all_rosters.get(user_team_slot, [])

        # 1. Compute raw metric values
        raw_metrics: List[Dict[str, float]] = []
        for player in candidates:
            pos = str(player.get("position", "")).upper()

            oc_raw = calculate_opportunity_cost_raw(player, candidates, picks_until_next_turn)
            vor_raw = calculate_vor(player, candidates, roster_requirements, num_teams=num_teams)
            fcvs_raw = calculate_fcvs_raw(player, current_round)
            hli_raw = calculate_hli_raw(player, user_roster, all_rosters, user_team_slot)
            prv_mult = calculate_prv_multiplier(pos, candidates, recent_picks)
            rfit_mult = calculate_roster_fit(player, user_roster, current_round, roster_requirements, available_players=candidates)

            raw_metrics.append({
                "oc_raw": oc_raw,
                "vor_raw": vor_raw,
                "fcvs_raw": fcvs_raw,
                "hli_raw": hli_raw,
                "prv_mult": prv_mult,
                "rfit_mult": rfit_mult,
            })

        # 2. Normalize components
        # OC: Z-score normalized across all candidates
        oc_values = [m["oc_raw"] for m in raw_metrics]
        oc_norms = z_score_normalize(oc_values)

        # VOR: Z-score normalized across all candidates
        vor_values = [m["vor_raw"] for m in raw_metrics]
        vor_norms = z_score_normalize(vor_values)

        # FCVS: Min-Max normalized by position group
        fcvs_norms = [0.0] * len(candidates)
        by_pos_indices: Dict[str, List[int]] = {}
        for idx, player in enumerate(candidates):
            pos = str(player.get("position", "")).upper()
            by_pos_indices.setdefault(pos, []).append(idx)

        for pos, indices in by_pos_indices.items():
            pos_fcvs = [raw_metrics[i]["fcvs_raw"] for i in indices]
            pos_fcvs_norm = min_max_normalize(pos_fcvs)
            for i, norm_val in zip(indices, pos_fcvs_norm):
                fcvs_norms[i] = norm_val

        # HLI: Min-Max normalized within RB candidate pool
        hli_norms = [0.0] * len(candidates)
        rb_indices = [i for i, p in enumerate(candidates) if str(p.get("position", "")).upper() == "RB"]
        if rb_indices:
            rb_hli_raws = [raw_metrics[i]["hli_raw"] for i in rb_indices]
            rb_hli_norms = min_max_normalize(rb_hli_raws)
            for i, norm_val in zip(rb_indices, rb_hli_norms):
                hli_norms[i] = norm_val

        # PRV: Min-Max normalized across shortlist
        prv_mults = [m["prv_mult"] for m in raw_metrics]
        prv_norms = min_max_normalize(prv_mults)

        base_w_oc = self.weights.get("w_oc", 0.20)
        base_w_vor = self.weights.get("w_vor", 0.20)
        base_w_fcvs = self.weights.get("w_fcvs", 0.20)
        base_w_hli = self.weights.get("w_hli", 0.15)
        base_w_prv = self.weights.get("w_prv", 0.10)
        base_w_rfit = self.weights.get("w_roster_fit", 0.15)

        results: List[Dict[str, Any]] = []
        for idx, player in enumerate(candidates):
            pos = str(player.get("position", "")).upper()
            oc_n = oc_norms[idx]
            vor_n = vor_norms[idx]
            fcvs_n = fcvs_norms[idx]
            hli_n = hli_norms[idx]
            prv_n = prv_norms[idx]
            rfit_m = raw_metrics[idx]["rfit_mult"]

            # For non-RBs, HLI is not applicable -> redistribute w_hli equally to w_oc and w_vor
            if pos != "RB":
                w_oc = base_w_oc + (base_w_hli * 0.5)
                w_vor = base_w_vor + (base_w_hli * 0.5)
                w_hli = 0.0
            else:
                w_oc = base_w_oc
                w_vor = base_w_vor
                w_hli = base_w_hli

            w_fcvs = base_w_fcvs
            w_prv = base_w_prv
            w_rfit = base_w_rfit

            composite_score = round(
                w_oc * oc_n + w_vor * vor_n + w_fcvs * fcvs_n + w_hli * hli_n + w_prv * prv_n + w_rfit * rfit_m,
                4,
            )

            results.append({
                "player_id": player.get("player_id"),
                "player_name": player.get("full_name"),
                "position": player.get("position"),
                "team": player.get("team"),
                "tier": player.get("tier"),
                "adp": player.get("adp"),
                "bye_week": player.get("bye_week"),
                "injury_status": player.get("injury_status", "ACTIVE"),
                "projection_median": float(player.get("projection_median") or 0.0),
                "composite_score": composite_score,
                "breakdown": {
                    "oc_raw": raw_metrics[idx]["oc_raw"],
                    "oc_norm": round(oc_n, 4),
                    "vor_raw": raw_metrics[idx]["vor_raw"],
                    "vor_norm": round(vor_n, 4),
                    "fcvs_raw": raw_metrics[idx]["fcvs_raw"],
                    "fcvs_norm": round(fcvs_n, 4),
                    "hli_raw": raw_metrics[idx]["hli_raw"],
                    "hli_norm": round(hli_n, 4),
                    "prv_mult": raw_metrics[idx]["prv_mult"],
                    "prv_norm": round(prv_n, 4),
                    "roster_fit_mult": rfit_m,
                },
            })

        # 4. Deterministic Sorting:
        # composite_score DESC, projection_median DESC, adp ASC, player_id ASC
        sorted_results = sorted(
            results,
            key=lambda x: (
                -x["composite_score"],
                -x["projection_median"],
                float(x["adp"]) if x["adp"] is not None else 999.0,
                str(x["player_id"]),
            ),
        )

        # Attach 1-based ranks & value gap vs ADP
        for rank_idx, item in enumerate(sorted_results, start=1):
            item["rank"] = rank_idx
            adp_val = float(item["adp"]) if item["adp"] is not None else 999.0
            item["value_gap"] = round(adp_val - rank_idx, 1)

        return sorted_results
