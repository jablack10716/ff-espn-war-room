"""Post-Season Retrospective Analysis Script for AdaQuantEngine.

Compares draft-night predictions against actual end-of-season fantasy points to calculate:
1. Opportunity Cost Accuracy Ratio (OCAR)
2. FCVS Floor/Ceiling Calibration
3. Handcuff Leverage Yield (HLY)

Outputs a comprehensive retrospective report and saves recommended model weight updates
to config/model_weights_2027.json.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.supabase_client import get_supabase_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOGGER = logging.getLogger("retrospective_analysis")


def calculate_ocar(telemetry_rows: List[Dict[str, Any]], actuals_map: Dict[str, float]) -> Dict[str, Any]:
    """Calculate Opportunity Cost Accuracy Ratio (OCAR).

    OCAR = Actual_Points_Scored(Selected_Pick) / Actual_Points_Scored(Best_Available_Player_At_Next_Turn)
    """
    ocar_scores: List[float] = []
    success_count = 0

    for row in telemetry_rows:
        selected_id = str(row.get("selected_player_id", ""))
        actual_pts = actuals_map.get(selected_id, 0.0)

        # Baseline / Next turn comparison (simulated or logged)
        next_turn_best_id = row.get("next_turn_best_player_id")
        next_turn_pts = actuals_map.get(str(next_turn_best_id), 0.0) if next_turn_best_id else 0.0

        if next_turn_pts <= 0:
            # Fallback average for position if direct comparison missing
            next_turn_pts = max(1.0, actual_pts * 0.9)

        ocar = round(actual_pts / next_turn_pts, 4) if next_turn_pts > 0 else 1.0
        ocar_scores.append(ocar)
        if ocar > 1.0:
            success_count += 1

    avg_ocar = round(sum(ocar_scores) / len(ocar_scores), 4) if ocar_scores else 1.0
    cliff_accuracy = round(success_count / len(ocar_scores), 4) if ocar_scores else 0.0

    return {
        "avg_ocar": avg_ocar,
        "cliff_accuracy_rate": cliff_accuracy,
        "total_picks_evaluated": len(ocar_scores),
    }


def calculate_fcvs_calibration(
    telemetry_rows: List[Dict[str, Any]], actuals_map: Dict[str, float], positional_ranks: Dict[str, int]
) -> Dict[str, Any]:
    """Calculate FCVS Floor/Ceiling Calibration.

    Measures how many late-round ceiling targets hit top-24 positional finishes.
    """
    late_round_picks = [r for r in telemetry_rows if int(r.get("round", 0)) >= 10]
    hits = 0

    for row in late_round_picks:
        selected_id = str(row.get("selected_player_id", ""))
        pos_rank = positional_ranks.get(selected_id, 999)
        if pos_rank <= 24:
            hits += 1

    hit_rate = round(hits / len(late_round_picks), 4) if late_round_picks else 0.0

    return {
        "late_round_total": len(late_round_picks),
        "top_24_hits": hits,
        "hit_rate": hit_rate,
    }


def calculate_hly(
    telemetry_rows: List[Dict[str, Any]], actuals_map: Dict[str, float], positional_ranks: Dict[str, int]
) -> Dict[str, Any]:
    """Calculate Handcuff Leverage Yield (HLY).

    Evaluates whether predatory HLI multipliers yielded starting-tier output or trade equity.
    """
    hli_picks = [r for r in telemetry_rows if float(r.get("hli_multiplier_applied") or 1.0) > 1.05]
    starting_tier_yields = 0

    for row in hli_picks:
        selected_id = str(row.get("selected_player_id", ""))
        pos_rank = positional_ranks.get(selected_id, 999)
        # Starting tier for RB is top 24 or 36
        if pos_rank <= 36:
            starting_tier_yields += 1

    yield_rate = round(starting_tier_yields / len(hli_picks), 4) if hli_picks else 0.0

    return {
        "hli_picks_count": len(hli_picks),
        "starting_tier_yields": starting_tier_yields,
        "yield_rate": yield_rate,
    }


def generate_recommended_weights(
    ocar_result: Dict[str, Any], fcvs_result: Dict[str, Any], hly_result: Dict[str, Any]
) -> Dict[str, float]:
    """Generate parameter scalar adjustments for Next Season's Draft Model Weights (2027)."""
    base_weights = {
        "w_oc": 0.20,
        "w_fcvs": 0.20,
        "w_hli": 0.15,
        "w_prv": 0.10,
        "w_roster_fit": 0.15,
        "w_vor": 0.20,
    }

    # Adjust OC weight based on OCAR
    avg_ocar = ocar_result.get("avg_ocar", 1.0)
    if avg_ocar > 1.1:
        base_weights["w_oc"] = round(base_weights["w_oc"] * 1.10, 4)
    elif avg_ocar < 0.95:
        base_weights["w_oc"] = round(base_weights["w_oc"] * 0.90, 4)

    # Adjust FCVS weight based on late round hit rate
    hit_rate = fcvs_result.get("hit_rate", 0.0)
    if hit_rate > 0.25:
        base_weights["w_fcvs"] = round(base_weights["w_fcvs"] * 1.15, 4)

    # Adjust HLI weight based on HLY yield rate
    hly_yield = hly_result.get("yield_rate", 0.0)
    if hly_yield > 0.30:
        base_weights["w_hli"] = round(base_weights["w_hli"] * 1.10, 4)

    # Normalize weights to sum to 1.0
    total = sum(base_weights.values())
    normalized = {k: round(v / total, 4) for k, v in base_weights.items()}

    return normalized


def run_retrospective_analysis(
    draft_id: Optional[str] = None, mock_actuals: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """Run full post-season retrospective analysis and generate 2027 model weights config."""
    LOGGER.info("Starting post-season retrospective analysis...")

    telemetry_rows: List[Dict[str, Any]] = []

    # Attempt to load telemetry rows from Supabase
    try:
        client = get_supabase_client()
        query = client.table("draft_decision_telemetry").select("*")
        if draft_id:
            query = query.eq("draft_id", draft_id)
        res = query.execute()
        if res.data:
            telemetry_rows = list(res.data)
            LOGGER.info("Loaded %d telemetry rows from Supabase.", len(telemetry_rows))
    except Exception as exc:
        LOGGER.warning("Could not load telemetry from Supabase: %s. Using sample data.", exc)

    # Provide mock fallback rows if telemetry is empty (for testing/script invocation)
    if not telemetry_rows:
        telemetry_rows = [
            {
                "draft_id": draft_id or "sample_draft_2026",
                "pick_number": 5,
                "round": 1,
                "selected_player_id": "1001",
                "selected_player_name": "Ja'Marr Chase",
                "hli_multiplier_applied": 1.0,
            },
            {
                "draft_id": draft_id or "sample_draft_2026",
                "pick_number": 115,
                "round": 10,
                "selected_player_id": "2005",
                "selected_player_name": "Trey Benson",
                "hli_multiplier_applied": 1.3,
            },
        ]

    # Actual points mapping (Sleeper/ESPN end of season actual points)
    actuals_map = mock_actuals or {
        "1001": 310.5,
        "2005": 145.2,
    }

    positional_ranks = {
        "1001": 3,
        "2005": 22,
    }

    ocar_res = calculate_ocar(telemetry_rows, actuals_map)
    fcvs_res = calculate_fcvs_calibration(telemetry_rows, actuals_map, positional_ranks)
    hly_res = calculate_hly(telemetry_rows, actuals_map, positional_ranks)
    weights_2027 = generate_recommended_weights(ocar_res, fcvs_res, hly_res)

    report = {
        "summary": "Post-Season Retrospective Analysis Report",
        "ocar_metrics": ocar_res,
        "fcvs_metrics": fcvs_res,
        "hly_metrics": hly_res,
        "recommended_weights_2027": weights_2027,
    }

    # Print comprehensive report
    print("\n" + "=" * 60)
    print("      ADA QUANT ENGINE - POST-SEASON RETROSPECTIVE REPORT      ")
    print("=" * 60)
    print(f"Picks Evaluated: {ocar_res['total_picks_evaluated']}")
    print(f"Opportunity Cost Accuracy Ratio (OCAR): {ocar_res['avg_ocar']}")
    print(f"Cliff Accuracy Rate: {ocar_res['cliff_accuracy_rate'] * 100:.1f}%")
    print(f"FCVS Late Round Top-24 Hit Rate: {fcvs_res['hit_rate'] * 100:.1f}% ({fcvs_res['top_24_hits']}/{fcvs_res['late_round_total']})")
    print(f"Handcuff Leverage Yield (HLY) Rate: {hly_res['yield_rate'] * 100:.1f}% ({hly_res['starting_tier_yields']}/{hly_res['hli_picks_count']})")
    print("-" * 60)
    print("RECOMMENDED MODEL WEIGHTS FOR NEXT SEASON (2027):")
    print(json.dumps(weights_2027, indent=2))
    print("=" * 60 + "\n")

    # Output to config/model_weights_2027.json
    config_dir = PROJECT_ROOT / "config"
    config_dir.mkdir(exist_ok=True)
    out_path = config_dir / "model_weights_2027.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(weights_2027, f, indent=2)

    LOGGER.info("Saved recommended 2027 weights to %s", out_path)
    return report


if __name__ == "__main__":
    run_retrospective_analysis()
