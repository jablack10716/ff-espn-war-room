# Phase 2 Planning & Execution Checklist

Use this checklist to plan, review, and track Phase 2 (Deterministic Ada Math Engine) implementation.

Scope from [WAR_ROOM_SPEC.md](WAR_ROOM_SPEC.md): Pure deterministic quant engine (`engine/ada_math.py`) and support helpers only.

---

## 1) Phase 2 Scope & Architectural Boundaries

- [x] Confirm Phase 2 is limited to the deterministic quant engine in `engine/ada_math.py` and support helpers (`scoring_models.py`, `tier_cliff.py`).
- [x] Confirm no Streamlit UI work starts in Phase 2.
- [x] Confirm no agent orchestration work starts in Phase 2.
- [x] Confirm no database schema changes are required for Phase 2.
- [x] Confirm no LLM calls are used for any deterministic math.
- [x] Confirm Phase 2 output must be reproducible from the same draft state.
- [x] Confirm Phase 2 will preserve auditability and replayability.

---

## 2) Source Inputs and Data Contracts

- [x] Confirm player fields from `public.available_players`: `player_id`, `position`, `tier`, `adp`, `projection_floor`, `projection_median`, `projection_ceiling`, `depth_role`, `handcuff_for_player_id`, `bye_week`.
- [x] Confirm roster-state inputs: starting position requirements per team, roster slots filled by position, active user team identifier.
- [x] Confirm recent-draft-window inputs: list of last 10 picks from `public.draft_log` with player position and pick number.
- [x] Confirm per-pick scoring snapshot format: JSON dictionary containing raw metric values (`oc`, `fcvs`, `hli`, `prv`, `roster_fit`), normalized metrics, weights, and final `composite_score`.
- [x] Confirm stable score output format: Ranked candidate dictionary list with `rank`, `player_id`, `player_name`, `position`, `composite_score`, and `breakdown`.
- [x] Confirm missing input fallbacks:
  - Missing floor/ceiling -> default to `median * 0.85` and `median * 1.15`.
  - Missing ADP -> default to 999.0.
  - Missing tier -> default to 99.
- [x] Confirm tie-break rules: `composite_score` DESC, then `projection_median` DESC, then `adp` ASC, then `player_id` ASC.

---

## 3) Opportunity Cost (OC) Design & Validation

- [x] Formula: $OC(p) = \text{value\_now}(p) - \text{expected\_best\_at\_next\_turn}(pos(p))$.
- [x] Define `best_now(pos)`: Maximum `projection_median` available at position `pos`.
- [x] Define `expected_best_at_next_turn(pos)`:
  - Calculate distance $D$ (picks until user's next turn).
  - Simulate draft of next $D$ picks using overall top $D$ remaining players by ADP.
  - Count how many players of position $pos$ are in those $D$ picks (say $k$).
  - `expected_best_at_next_turn(pos)` is the projection of the $(k+1)$-th best available player currently remaining at position $pos$.
- [x] Define OC Normalization: Z-Score normalization across candidate shortlist:
  $$Z_{OC}(p) = \frac{OC(p) - \mu_{OC}}{\sigma_{OC}}$$
  (Fallback to 0.0 if standard deviation $\sigma_{OC} == 0$).

---

## 4) Floor-to-Ceiling Variance Shift (FCVS) Design

- [x] Base inputs: `projection_floor` and `projection_ceiling`.
- [x] Round-band weights:
  - Rounds 1–5: $0.80 \times \text{floor} + 0.20 \times \text{ceiling}$
  - Rounds 6–9: $0.50 \times \text{floor} + 0.50 \times \text{ceiling}$
  - Rounds 10+: $0.10 \times \text{floor} + 0.90 \times \text{ceiling}$
- [x] Normalization: Min-Max normalization **by position group**:
  $$FCVS_{\text{norm}}(p) = \frac{FCVS(p) - \min_{pos} FCVS}{\max_{pos} FCVS - \min_{pos} FCVS}$$

---

## 5) Handcuff Leverage Index (HLI) Design

- [x] Multipliers:
  - `1.5` for direct backup to user's own RB1.
  - `1.3` for backup to opponent's unhandcuffed RB1.
  - `0.5` for unowned low-tier backup (`depth_role` in `['RB3', 'backup']` with low median projection).
  - `1.0` default.
- [x] Backup candidate matching: Match RB candidates where `depth_role` is backup or `handcuff_for_player_id` matches an RB1 on the same NFL team.
- [x] `base_backup_value`: `projection_median`.
- [x] Multiplier calculation: $HLI(b) = \text{projection\_median}(b) \times \text{multiplier}$. Min-Max normalized within RB pool.

---

## 6) Positional Run Velocity (PRV) Design

- [x] Rolling Window: Last 10 picks from `draft_log`.
- [x] Run Share Threshold: $> 40\%$ share (i.e. $\ge 5$ picks of position in last 10 picks).
- [x] Tier Cliff Imminent: Remaining available players in current highest tier at position is $\le 2$.
- [x] Trigger Condition: `run_share > 0.40` AND `tier_cliff_imminent == True`.
- [x] PRV Boost Multiplier: Bounded between $1.05$ and $1.20$:
  $$\text{PRV\_boost} = 1.05 + 0.15 \times \left(1 - \frac{\text{remaining\_tier\_players}}{2}\right)$$
  (Defaults to $1.00$ when trigger condition is false).

---

## 7) RosterFit Design

- [x] Position saturation penalty:
  - If starting requirement for position is met, scale RosterFit weight to $0.2$.
  - If starting requirement is open, RosterFit weight is $1.0$.
  - If late round ($\ge 8$) and starting QB/TE is still unfilled, boost to $1.5$.

---

## 8) Composite Score Formula

- [x] Formula:
  $$\text{score}(p) = w_1 Z_{OC}(p) + w_2 FCVS_{\text{norm}}(p) + w_3 HLI_{\text{norm}}(p) + w_4 PRV_{\text{norm}}(p) + w_5 RosterFit(p)$$
- [x] Default Weights:
  - $w_1 = 0.30$ (Opportunity Cost)
  - $w_2 = 0.25$ (FCVS)
  - $w_3 = 0.20$ (HLI)
  - $w_4 = 0.15$ (PRV)
  - $w_5 = 0.10$ (RosterFit)

---

## 9) Unit Test Plan

- [ ] `test_ada_math.py`:
  - Test OC calculation with simulated next-turn draft.
  - Test FCVS round-band transitions (Rounds 1-5, 6-9, 10+).
  - Test HLI multiplier assignments for user RB1 backup vs. opponent RB1 backup.
  - Test PRV trigger detection on run share + tier cliff.
  - Test composite score ordering and deterministic tie-breaking.
  - Test edge cases: empty candidate list, missing projections, identical candidate scores.

---

## 10) Implementation Steps

- [ ] Implement `engine/scoring_models.py` (FCVS, HLI, RosterFit formulas & normalizers).
- [ ] Implement `engine/tier_cliff.py` (Tier cliff detector & PRV run velocity helpers).
- [ ] Implement `engine/ada_math.py` (Core engine class `AdaQuantEngine` and `compute_rankings`).
- [ ] Implement unit tests in `tests/test_ada_math.py`, `tests/test_prv_detection.py`, and `tests/test_hli_logic.py`.
- [ ] Execute `pytest` to verify 100% test pass rate.
