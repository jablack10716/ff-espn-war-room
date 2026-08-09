"""Phase 2 target: pure deterministic Ada quant math engine implementation.

Computes Opportunity Cost (OC), Floor-to-Ceiling Variance Shift (FCVS),
Handcuff Leverage Index (HLI), Positional Run Velocity (PRV), and RosterFit,
and combines them into deterministic, auditable composite candidate rankings.
"""

from __future__ import annotations

import logging
import math
import random
from typing import Any, Dict, List, Optional, Sequence

from engine.scoring_models import (
    apply_playoff_schedule_modifier,
    apply_scheme_and_line_scalars,
    apply_stacking_multiplier,
    blend_vegas_props,
    calculate_effective_starters,
    calculate_fcvs_raw,
    calculate_hli_raw,
    calculate_roster_fit,
    calculate_vor,
    min_max_normalize,
    z_score_normalize,
)
from engine.tier_cliff import calculate_prv_multiplier

from config.settings import ENABLE_HIGH_STAKES_ADP

LOGGER = logging.getLogger("ada_math")


INJURY_EGP_MULTIPLIERS: Dict[str, float] = {
    "ACTIVE": 1.0,
    "QUESTIONABLE": 0.95,
    "DOUBTFUL": 0.88,
    "OUT": 0.82,
    "IR": 0.70,
    "PUP": 0.75,
}


def estimate_best_at_next_turn(
    position: str,
    available_players: Sequence[Dict[str, Any]],
    picks_until_next_turn: int,
    current_pick: int = 1,
) -> float:
    """Estimate expected best projection median remaining at next turn using Monte Carlo simulation.

    Simulates 200 draft iterations incorporating blended multi-source ADP (Sleeper + Underdog)
    and random draft room noise variance to output risk-adjusted expected value.
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

    target_pick = current_pick + picks_until_next_turn
    top_candidates = pos_players_sorted[:10]

    # Pre-calculate blended ADP for top candidates
    candidate_data = []
    for p in top_candidates:
        underdog = p.get("underdog_adp")
        sleeper = p.get("adp")
        if ENABLE_HIGH_STAKES_ADP and underdog is not None and sleeper is not None:
            blended_adp = (float(underdog) * 0.6) + (float(sleeper) * 0.4)
        elif ENABLE_HIGH_STAKES_ADP and underdog is not None:
            blended_adp = float(underdog)
        elif sleeper is not None:
            blended_adp = float(sleeper)
        elif p.get("consensus_adp") is not None:
            blended_adp = float(p["consensus_adp"])
        else:
            blended_adp = 999.0

        proj = float(p.get("projection_median") or 0.0)
        candidate_data.append((blended_adp, proj))

    iterations = 200
    expected_best_sum = 0.0
    seed_val = hash((position.upper(), current_pick, target_pick, tuple(c[0] for c in candidate_data)))
    rng = random.Random(seed_val)

    for _ in range(iterations):
        best_survivor_proj = 0.0
        for adp_val, proj in candidate_data:
            # Inject random statistical noise multiplier (10% std dev) for draft room variance
            noise = rng.gauss(mu=0.0, sigma=0.10)
            simulated_pick = adp_val * (1.0 + noise)

            if simulated_pick > target_pick:
                best_survivor_proj = proj
                break

        expected_best_sum += best_survivor_proj

    expected_best = expected_best_sum / iterations if iterations > 0 else 0.0
    return round(expected_best, 4)


def calculate_opportunity_cost_raw(
    player: Dict[str, Any],
    available_players: Sequence[Dict[str, Any]],
    picks_until_next_turn: int,
    current_pick: int = 1,
) -> float:
    """Calculate raw Opportunity Cost (OC) for a player.

    OC_raw = projection_median(player) - expected_best_at_next_turn(position)
    """
    pos = str(player.get("position", "")).upper()
    median = float(player.get("projection_median") or 0.0)
    expected_best = estimate_best_at_next_turn(pos, available_players, picks_until_next_turn, current_pick=current_pick)
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
        drafted_counts: Dict[str, int] = {}

        for event in draft_log:
            if str(event.get("event_type", "PICK")).upper() == "PICK":
                slot = int(event.get("team_slot", 1))
                all_rosters.setdefault(slot, []).append(event)
                recent_picks.append(event)
                pos_event = str(event.get("position", "")).upper()
                if pos_event:
                    drafted_counts[pos_event] = drafted_counts.get(pos_event, 0) + 1

        user_roster = all_rosters.get(user_team_slot, [])

        # Precalculate replacement level PPG per position for IR stash EGP offset
        effective_starters = calculate_effective_starters(roster_requirements or {})
        replacement_ppg_map: Dict[str, float] = {}
        for pos_name in ("QB", "RB", "WR", "TE", "K", "DST"):
            starters_count = effective_starters.get(pos_name, 1.0)
            needed_count = int(round(num_teams * starters_count))
            d_at_pos = drafted_counts.get(pos_name, 0)
            r_idx = max(0, needed_count - d_at_pos)
            pos_cand = [p for p in candidates if str(p.get("position", "")).upper() == pos_name]
            pos_cand_sorted = sorted(pos_cand, key=lambda x: float(x.get("projection_median") or 0.0), reverse=True)
            if r_idx < len(pos_cand_sorted):
                base_proj = float(pos_cand_sorted[r_idx].get("projection_median") or 0.0)
            elif pos_cand_sorted:
                base_proj = float(pos_cand_sorted[-1].get("projection_median") or 0.0)
            else:
                base_proj = 0.0
            replacement_ppg_map[pos_name] = base_proj / 17.0

        # Apply Expected Games Played (EGP) injury discounting with IR Stash replacement offset
        candidates_egp: List[Dict[str, Any]] = []
        for p in candidates:
            p_copy = dict(p)
            # 2. Vegas Market Prop Consensus Blending
            p_copy["projection_median"] = blend_vegas_props(p_copy)
            inj = str(p_copy.get("injury_status") or "ACTIVE").upper()
            mult = INJURY_EGP_MULTIPLIERS.get(inj, 1.0)
            raw_proj = float(p_copy.get("projection_median") or 0.0)
            pos_str = str(p_copy.get("position", "")).upper()

            expected_games = 17.0 * mult
            missed_games = 17.0 - expected_games
            healthy_ppg = raw_proj / 17.0
            repl_ppg = replacement_ppg_map.get(pos_str, 0.0)

            adjusted_proj = (healthy_ppg * expected_games) + (repl_ppg * missed_games)
            p_copy["projection_median"] = round(adjusted_proj, 2)
            candidates_egp.append(p_copy)

        # 1. Compute raw metric values
        raw_metrics: List[Dict[str, float]] = []
        for player in candidates_egp:
            pos = str(player.get("position", "")).upper()

            oc_raw = calculate_opportunity_cost_raw(player, candidates_egp, picks_until_next_turn, current_pick=current_pick)
            vor_raw = calculate_vor(
                player,
                candidates_egp,
                roster_requirements,
                num_teams=num_teams,
                drafted_counts=drafted_counts,
            )
            fcvs_raw = calculate_fcvs_raw(player, current_pick)
            hli_raw = calculate_hli_raw(player, user_roster, all_rosters, user_team_slot)
            prv_mult = calculate_prv_multiplier(pos, candidates_egp, recent_picks)
            rfit_mult = calculate_roster_fit(player, user_roster, current_round, roster_requirements, available_players=candidates_egp)

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

        # RosterFit: Z-score normalized across all candidates
        rfit_mults = [m["rfit_mult"] for m in raw_metrics]
        rfit_norms = z_score_normalize(rfit_mults)

        # FCVS: Min-Max normalized by position group
        fcvs_norms = [0.0] * len(candidates_egp)
        by_pos_indices: Dict[str, List[int]] = {}
        for idx, player in enumerate(candidates_egp):
            pos = str(player.get("position", "")).upper()
            by_pos_indices.setdefault(pos, []).append(idx)

        for pos, indices in by_pos_indices.items():
            pos_fcvs = [raw_metrics[i]["fcvs_raw"] for i in indices]
            pos_fcvs_norm = min_max_normalize(pos_fcvs)
            for i, norm_val in zip(indices, pos_fcvs_norm):
                fcvs_norms[i] = norm_val

        # HLI: Min-Max normalized within RB candidate pool
        hli_norms = [0.0] * len(candidates_egp)
        rb_indices = [i for i, p in enumerate(candidates_egp) if str(p.get("position", "")).upper() == "RB"]
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
        for idx, player in enumerate(candidates_egp):
            pos = str(player.get("position", "")).upper()
            oc_n = oc_norms[idx]
            vor_n = vor_norms[idx]
            fcvs_n = fcvs_norms[idx]
            hli_n = hli_norms[idx]
            prv_n = prv_norms[idx]
            rfit_n = rfit_norms[idx]

            # Extract HLI multiplier (applies post-calculation for running backs)
            hli_mult = 1.0
            if pos == "RB":
                median = float(player.get("projection_median") or 0.0)
                hli_raw = raw_metrics[idx]["hli_raw"]
                if median > 0:
                    hli_mult = round(hli_raw / median, 4)

            # Additional mathematical factor multipliers
            stacking_mult = apply_stacking_multiplier(player, user_roster)
            scheme_mult = apply_scheme_and_line_scalars(player)
            playoff_mult = apply_playoff_schedule_modifier(player, current_round)

            # Static component weights across all positions
            w_oc = base_w_oc
            w_vor = base_w_vor
            w_fcvs = base_w_fcvs
            w_hli = base_w_hli if pos == "RB" else 0.0
            w_prv = base_w_prv
            w_rfit = base_w_rfit

            base_sum = w_oc * oc_n + w_vor * vor_n + w_fcvs * fcvs_n + w_hli * hli_n + w_prv * prv_n + w_rfit * rfit_n
            composite_score = round(
                base_sum * hli_mult * stacking_mult * scheme_mult * playoff_mult, 4
            )

            results.append({
                "player_id": player.get("player_id"),
                "player_name": player.get("full_name"),
                "position": player.get("position"),
                "team": player.get("team"),
                "tier": player.get("tier"),
                "adp": player.get("consensus_adp") or player.get("adp"),
                "consensus_adp": player.get("consensus_adp") or player.get("adp"),
                "sleeper_adp": player.get("sleeper_adp"),
                "analyst_tier": player.get("analyst_tier"),
                "data_sources": player.get("data_sources", ["espn"]),
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
                    "roster_fit_mult": raw_metrics[idx]["rfit_mult"],
                    "rfit_norm": round(rfit_n, 4),
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
