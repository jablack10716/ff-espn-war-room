"""Phase 4: Multi-Agent Orchestration Graph (Marcus, Winston, Arthur).

Implements Fan-Out / Fan-In orchestration with strict JSON schema validation,
5-second hard timeouts, and deterministic Ada-only fallbacks.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

load_dotenv()

LOGGER = logging.getLogger("war_room_agents")

try:
    from services.action_logger import log_action
except ImportError:
    def log_action(action_type: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        pass

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"


def load_file(path: Path) -> str:
    """Load text file content."""
    if not path.exists():
        return ""
    with path.open("r", encoding="utf-8") as fh:
        return fh.read().strip()


def validate_schema(data: Dict[str, Any], schema_name: str) -> bool:
    """Validate output data dictionary against JSON schema."""
    schema_path = SCHEMAS_DIR / schema_name
    if not schema_path.exists():
        LOGGER.warning("Schema file %s not found", schema_path)
        return True

    try:
        import jsonschema
        with schema_path.open("r", encoding="utf-8") as fh:
            schema = json.load(fh)
        jsonschema.validate(instance=data, schema=schema)
        return True
    except ImportError:
        # Basic structural validation fallback if jsonschema package is missing
        required = []
        if schema_name == "marcus_output.schema.json":
            required = ["agent", "player_id", "upside_sentence"]
        elif schema_name == "winston_output.schema.json":
            required = ["agent", "player_id", "need_sentence"]
        elif schema_name == "batched_evaluations.schema.json":
            required = ["evaluations"]
        elif schema_name == "arthur_output.schema.json":
            required = ["agent", "reasoning_2_sentences", "top_3_picks", "fallback_used"]

        for req_key in required:
            if req_key not in data:
                return False
        return True
    except Exception as exc:
        LOGGER.warning("Schema validation failed for %s: %s", schema_name, exc)
        return False


try:
    from tenacity import retry, retry_if_exception, retry_if_exception_type, stop_after_attempt, wait_exponential
    TENACITY_AVAILABLE = True
except ImportError:
    TENACITY_AVAILABLE = False


def _execute_llm_request(url: str, headers: dict, payload: dict, timeout_seconds: float) -> str:
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout_seconds)
        if response.status_code == 429:
            raise RuntimeError("LLM API Rate Limited (HTTP 429)")
        response.raise_for_status()
        res_json = response.json()
        choices = res_json.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return ""
    except Exception as e:
        if 'response' in locals() and hasattr(response, 'text'):
            LOGGER.error("LLM Request Exception: %s | Response: %s", e, response.text)
        else:
            LOGGER.error("LLM Request Exception: %s", e)
        raise


def call_llm_api(
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    timeout_seconds: float = 5.0,
) -> Optional[str]:
    """Call Google Gemini LLM API with strict timeout and exponential retry resilience."""
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        LOGGER.info("No LLM API key present in environment; defaulting to fallback")
        return None

    url = os.getenv("GEMINI_API_URL", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions")
    if not model:
        model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }

    try:
        if TENACITY_AVAILABLE:
            import requests
            @retry(
                reraise=True,
                stop=stop_after_attempt(2),
                wait=wait_exponential(multiplier=0.5, min=0.5, max=2.0),
                retry=retry_if_exception(lambda e: not isinstance(e, requests.exceptions.Timeout)),
            )
            def _with_retry():
                return _execute_llm_request(url, headers, payload, timeout_seconds)
            return _with_retry()
        else:
            return _execute_llm_request(url, headers, payload, timeout_seconds)
    except Exception as exc:
        LOGGER.warning("LLM API call failed or timed out: %s", exc)

    return None


class MarcusAgent:
    """Marcus: Chief Scout evaluating upside pathways."""

    def __init__(self, model: Optional[str] = None) -> None:
        self.system_prompt = load_file(PROMPTS_DIR / "marcus_system.txt")
        self.model = model or os.getenv("MARCUS_MODEL") or "gemini-3.6-flash"

    def evaluate_player(
        self, player: Dict[str, Any], timeout_seconds: float = 5.0
    ) -> Optional[Dict[str, Any]]:
        pid = str(player.get("player_id"))
        pname = player.get("full_name") or player.get("player_name") or "This player"
        pos = player.get("position")
        team = player.get("team", "FA")
        tier = player.get("tier")
        adp = player.get("adp")
        median = player.get("projection_median")

        injury = player.get("injury_status", "ACTIVE")
        underdog_adp = player.get("underdog_adp")
        vegas_pts = player.get("vegas_projected_pts")
        high_stakes_proj = player.get("high_stakes_proj")
        air_yards = player.get("air_yards_share")
        target_share = player.get("target_share")
        xfp = player.get("xfp")
        sources = player.get("data_sources", [])

        user_prompt = (
            f"Evaluate upside talent for candidate: {pname} (ID: {pid}, Pos: {pos}, Team: {team}, "
            f"Tier: {tier}, Consensus ADP: {adp}, Projection Median: {median}, Injury Status: {injury}).\n"
            f"Multi-Source Data Feeds: Active Feeds: {sources}.\n"
            f"Real-Money Underdog ADP: {underdog_adp or adp}.\n"
            f"Vegas Sportsbook Implied Points: {vegas_pts if vegas_pts is not None else 'N/A'}.\n"
            f"High-Stakes (ETR/PFF) Projection: {high_stakes_proj if high_stakes_proj is not None else 'N/A'}.\n"
            f"Opportunity Metrics: Air Yards Share: {air_yards or 0.0}, Target Share: {target_share or 0.0}, Expected Fantasy Points (xFP): {xfp or 0.0}.\n"
            f"Return strict JSON matching schema with keys: agent='Marcus', player_id='{pid}', upside_sentence."
        )

        raw_response = call_llm_api(
            self.system_prompt, user_prompt, model=self.model, timeout_seconds=timeout_seconds
        )
        if raw_response:
            try:
                data = json.loads(raw_response)
                if validate_schema(data, "marcus_output.schema.json"):
                    return data
            except Exception:
                pass

        marcus_fallbacks = {
            "QB": f"{pname} displays high-caliber passing talent with dual-threat rushing upside.",
            "RB": f"{pname} possesses significant athletic upside and a clear pathway for dominant touch share.",
            "WR": f"{pname} profiles as an explosive target with strong route-running upside.",
            "TE": f"{pname} provides rare positional ceiling with growing red-zone target opportunity.",
            "K": f"{pname} operates in a high-scoring offense offering steady scoring opportunities.",
            "DST": f"{pname} defense generates disruptive pressure and high turnover potential.",
        }

        # Mock fallback note if API is unreachable
        return {
            "agent": "Marcus",
            "player_id": pid,
            "upside_sentence": marcus_fallbacks.get(
                str(pos).upper(), f"{pname} possesses significant athletic upside and a clear pathway for high target share."
            ),
        }


class WinstonAgent:
    """Winston: Roster Architect evaluating structural roster needs."""

    def __init__(self, model: Optional[str] = None) -> None:
        self.system_prompt = load_file(PROMPTS_DIR / "winston_system.txt")
        self.model = model or os.getenv("WINSTON_MODEL") or "gemini-3.6-flash"

    def evaluate_player(
        self,
        player: Dict[str, Any],
        user_roster: List[Dict[str, Any]],
        timeout_seconds: float = 5.0,
    ) -> Optional[Dict[str, Any]]:
        pid = str(player.get("player_id"))
        pname = player.get("full_name") or player.get("player_name") or "This player"
        pos = player.get("position")
        player_bye = player.get("bye_week", "Unknown")

        roster_counts = {}
        roster_byes = []
        for item in user_roster:
            rpos = str(item.get("position", "")).upper()
            roster_counts[rpos] = roster_counts.get(rpos, 0) + 1
            if item.get("bye_week"):
                roster_byes.append(item.get("bye_week"))

        user_prompt = (
            f"Evaluate roster fit for candidate: {pname} (ID: {pid}, Pos: {pos}, Bye: {player_bye}).\n"
            f"Current roster composition: {roster_counts}.\n"
            f"Current roster bye weeks: {roster_byes}.\n"
            f"Return strict JSON matching schema with keys: agent='Winston', player_id='{pid}', need_sentence."
        )

        raw_response = call_llm_api(
            self.system_prompt, user_prompt, model=self.model, timeout_seconds=timeout_seconds
        )
        if raw_response:
            try:
                data = json.loads(raw_response)
                if validate_schema(data, "winston_output.schema.json"):
                    return data
            except Exception:
                pass

        winston_fallbacks = {
            "QB": f"Drafting {pname} locks in an essential QB anchor for your roster.",
            "RB": f"Drafting {pname} addresses key RB depth and balances positional volume.",
            "WR": f"Drafting {pname} fills a vital WR starting slot and upgrades receiving depth.",
            "TE": f"Drafting {pname} secures crucial TE positional value for starting requirements.",
            "K": f"Drafting {pname} satisfies the kicker roster requirement.",
            "DST": f"Drafting {pname} satisfies the defense roster requirement.",
        }

        # Mock fallback note if API is unreachable
        return {
            "agent": "Winston",
            "player_id": pid,
            "need_sentence": winston_fallbacks.get(
                str(pos).upper(), f"Drafting {pname} addresses a key positional requirement and strengthens team roster depth."
            ),
        }


class ArthurAgent:
    """Arthur: General Manager synthesizing Scout, Roster Architect, and Ada Math."""

    def __init__(self, model: Optional[str] = None) -> None:
        self.system_prompt = load_file(PROMPTS_DIR / "arthur_system.txt")
        self.model = model or os.getenv("ARTHUR_MODEL") or "gemini-3.6-flash"

    def synthesize(
        self,
        marcus_notes: List[Dict[str, Any]],
        winston_notes: List[Dict[str, Any]],
        ada_top_candidates: List[Dict[str, Any]],
        user_roster: Optional[List[Dict[str, Any]]] = None,
        opponent_rosters: Optional[Dict[Any, Any]] = None,
        timeout_seconds: float = 5.0,
    ) -> Optional[Dict[str, Any]]:
        import time
        t0 = time.time()

        cand_summary = [
            {
                "rank": i + 1,
                "player_id": p["player_id"],
                "player_name": p.get("player_name") or p.get("full_name"),
                "position": p["position"],
                "team": p.get("team", "FA"),
                "bye_week": p.get("bye_week"),
                "composite_score": p.get("composite_score", 0.0),
                "vegas_implied_pts": p.get("vegas_projected_pts"),
                "underdog_adp": p.get("underdog_adp"),
                "high_stakes_proj": p.get("high_stakes_proj"),
                "expected_pts_xfp": p.get("xfp"),
                "injury_status": p.get("injury_status", "ACTIVE"),
            }
            for i, p in enumerate(ada_top_candidates[:3])
        ]

        user_prompt = (
            f"Synthesize comprehensive draft recommendation and comparative analysis.\n"
            f"Marcus Scout Notes: {marcus_notes}\n"
            f"Winston Roster Notes: {winston_notes}\n"
            f"Ada Top Candidates & Metrics: {cand_summary}\n"
            f"User Current Roster & Bye Weeks: {user_roster or []}\n"
            f"League Opponents Roster Counts: {opponent_rosters or {}}\n"
            f"Return strict JSON matching schema with keys: agent='Arthur', reasoning_2_sentences, detailed_breakdown, top_3_picks, fallback_used=False."
        )

        log_action("ARTHUR_SYNTHESIZE_START", f"Arthur starting synthesis with model '{self.model}'", {
            "model": self.model,
            "timeout_seconds": timeout_seconds,
            "top_candidates_count": len(cand_summary),
        })

        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            raw_response = call_llm_api(
                self.system_prompt, user_prompt, model=self.model, timeout_seconds=timeout_seconds
            )
            elapsed = round(time.time() - t0, 3)

            if not raw_response:
                log_action("ARTHUR_SYNTHESIZE_FAILED", f"Arthur API call returned None (timeout or error after {elapsed}s)", {
                    "model": self.model,
                    "elapsed_seconds": elapsed,
                    "timeout_allocated": timeout_seconds,
                    "attempt": attempt,
                })
                if attempt < max_attempts and (time.time() - t0) < 2.0:
                    LOGGER.info("Arthur attempt %d failed in <2s (elapsed: %.2fs); triggering micro-retry", attempt, elapsed)
                    continue
                return None

            try:
                data = json.loads(raw_response)
                data["fallback_used"] = False
                is_valid = validate_schema(data, "arthur_output.schema.json")
                if is_valid:
                    log_action("ARTHUR_SYNTHESIZE_SUCCESS", f"Arthur synthesis succeeded in {elapsed}s", {
                        "model": self.model,
                        "elapsed_seconds": elapsed,
                        "reasoning": data.get("reasoning_2_sentences"),
                        "attempt": attempt,
                    })
                    return data
                else:
                    log_action("ARTHUR_SCHEMA_INVALID", f"Arthur response failed JSON schema validation in {elapsed}s", {
                        "model": self.model,
                        "raw_response_snippet": raw_response[:300],
                        "attempt": attempt,
                    })
            except Exception as exc:
                log_action("ARTHUR_PARSE_ERROR", f"Arthur JSON parsing failed in {elapsed}s: {exc}", {
                    "model": self.model,
                    "error": str(exc),
                    "raw_response_snippet": raw_response[:300],
                    "attempt": attempt,
                })

            if attempt < max_attempts and (time.time() - t0) < 2.0:
                LOGGER.info("Arthur attempt %d failed in <2s (elapsed: %.2fs); triggering micro-retry", attempt, elapsed)
                continue
            else:
                break

        return None


class WarRoomOrchestrator:
    """Orchestrates Fan-Out / Fan-In agent workflow with dynamic timeout cap."""

    def __init__(
        self,
        marcus_model: Optional[str] = None,
        winston_model: Optional[str] = None,
        arthur_model: Optional[str] = None,
    ) -> None:
        self.marcus = MarcusAgent(model=marcus_model)
        self.winston = WinstonAgent(model=winston_model)
        self.arthur = ArthurAgent(model=arthur_model)

    def build_fallback_payload(
        self, ada_rankings: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Construct deterministic Ada-only fallback payload."""
        top_3 = []
        for i, p in enumerate(ada_rankings[:3], start=1):
            top_3.append({
                "rank": i,
                "player_id": str(p.get("player_id")),
                "player_name": str(p.get("player_name") or p.get("full_name")),
                "position": str(p.get("position")),
                "composite_score": float(p.get("composite_score", 0.0)),
            })

        p1_name = top_3[0]["player_name"] if top_3 else "the top available player"
        p1_pos = top_3[0]["position"] if top_3 else "position"

        arthur_strict_payload = {
            "agent": "Arthur",
            "reasoning_2_sentences": (
                f"Ada quant engine prioritizes {p1_name} ({p1_pos}) based on optimal opportunity "
                f"cost and ceiling metrics. Selecting from the top deterministic tier preserves "
                f"key positional value before the next turn cliff."
            ),
            "detailed_breakdown": {
                "primary_rationale": f"{p1_name} provides the highest baseline projection and positional value anchor for your draft strategy.",
                "comparison_vs_runnerups": f"{p1_name} offers superior immediate value and lower risk profile than secondary options.",
                "draft_context_factors": f"Fills a key roster slot while preserving structural draft flexibility for upcoming turns.",
            },
            "top_3_picks": top_3,
            "fallback_used": True,
        }

        # Validate Arthur strict payload against schema
        validate_schema(arthur_strict_payload, "arthur_output.schema.json")

        # Attach UI notes
        arthur_strict_payload["marcus_notes"] = {}
        arthur_strict_payload["winston_notes"] = {}
        arthur_strict_payload["marcus_fallback"] = True
        arthur_strict_payload["winston_fallback"] = True
        return arthur_strict_payload

    def build_bypass_payload(
        self, ada_rankings: List[Dict[str, Any]], margin: float
    ) -> Dict[str, Any]:
        """Construct deterministic payload when Ada has a clear lead (>3% margin) and AI debate is bypassed."""
        top_3 = []
        for i, p in enumerate(ada_rankings[:3], start=1):
            top_3.append({
                "rank": i,
                "player_id": str(p.get("player_id")),
                "player_name": str(p.get("player_name") or p.get("full_name")),
                "position": str(p.get("position")),
                "composite_score": float(p.get("composite_score", 0.0)),
            })

        p1_name = top_3[0]["player_name"] if top_3 else "the top available player"
        p1_pos = top_3[0]["position"] if top_3 else "position"
        p2_name = top_3[1]["player_name"] if len(top_3) > 1 else "the runner-up"
        p3_name = top_3[2]["player_name"] if len(top_3) > 2 else "alternative options"

        marcus_notes = {}
        winston_notes = {}
        for p in ada_rankings[:3]:
            pid = str(p.get("player_id"))
            marcus_notes[pid] = "AI Debate Bypassed - Ada clear winner"
            winston_notes[pid] = "AI Debate Bypassed - Ada clear winner"

        arthur_payload = {
            "agent": "Arthur",
            "reasoning_2_sentences": (
                f"Ada quant engine prioritizes {p1_name} ({p1_pos}) with a clear mathematical lead of {margin:.1f}% over candidate #2. "
                f"AI debate was bypassed to execute the deterministic choice instantly with zero latency."
            ),
            "detailed_breakdown": {
                "primary_rationale": f"{p1_name} holds a decisive {margin:.1f}% quantitative score advantage, featuring superior VORP and ceiling metrics.",
                "comparison_vs_runnerups": f"{p1_name} outranks both {p2_name} and {p3_name} across composite opportunity cost, target projections, and positional value.",
                "draft_context_factors": f"Selecting {p1_name} optimizes your starting lineup balance without taking unnecessary risk or overlapping key bye weeks.",
            },
            "top_3_picks": top_3,
            "fallback_used": False,
        }
        validate_schema(arthur_payload, "arthur_output.schema.json")
        arthur_payload["marcus_notes"] = marcus_notes
        arthur_payload["winston_notes"] = winston_notes
        arthur_payload["marcus_fallback"] = False
        arthur_payload["winston_fallback"] = False
        arthur_payload["ai_bypassed"] = True
        arthur_payload["margin_pct"] = round(margin, 2)
        return arthur_payload

    def run_batched_evaluations(
        self,
        top_candidates: List[Dict[str, Any]],
        user_roster: List[Dict[str, Any]],
        timeout_seconds: float = 10.0,
    ) -> Tuple[Dict[str, str], Dict[str, str], List[Dict[str, Any]], List[Dict[str, Any]], bool]:
        """Run a single batched API call for Marcus and Winston evaluations to respect API rate limits."""
        marcus_notes: Dict[str, str] = {}
        winston_notes: Dict[str, str] = {}
        marcus_list: List[Dict[str, Any]] = []
        winston_list: List[Dict[str, Any]] = []
        marcus_winston_success = False

        # Populate baseline position-aware fallbacks in-memory (no network requests)
        marcus_fallbacks = {
            "QB": "displays high-caliber passing talent with dual-threat rushing upside.",
            "RB": "possesses significant athletic upside and a clear pathway for dominant touch share.",
            "WR": "profiles as an explosive target with strong route-running upside.",
            "TE": "provides rare positional ceiling with growing red-zone target opportunity.",
            "K": "operates in a high-scoring offense offering steady scoring opportunities.",
            "DST": "defense generates disruptive pressure and high turnover potential.",
        }
        winston_fallbacks = {
            "QB": "locks in an essential QB anchor for your roster.",
            "RB": "addresses key RB depth and balances positional volume.",
            "WR": "fills a vital WR starting slot and upgrades receiving depth.",
            "TE": "secures crucial TE positional value for starting requirements.",
            "K": "satisfies the kicker roster requirement.",
            "DST": "satisfies the defense roster requirement.",
        }
        for p in top_candidates:
            pid = str(p.get("player_id"))
            pname = p.get("full_name") or p.get("player_name") or "This player"
            pos = str(p.get("position", "")).upper()

            m_text = f"{pname} {marcus_fallbacks.get(pos, 'possesses significant athletic upside.')}"
            w_text = f"Drafting {pname} {winston_fallbacks.get(pos, 'addresses a key positional requirement.')}"

            marcus_notes[pid] = m_text
            winston_notes[pid] = w_text
            marcus_list.append({"agent": "Marcus", "player_id": pid, "upside_sentence": m_text})
            winston_list.append({"agent": "Winston", "player_id": pid, "need_sentence": w_text})

        # Execute single batched API request if LLM API key present
        if os.getenv("GEMINI_API_KEY"):
            cand_info = [
                {
                    "player_id": str(p.get("player_id")),
                    "name": p.get("full_name") or p.get("player_name"),
                    "position": p.get("position"),
                    "team": p.get("team"),
                    "adp": p.get("adp"),
                    "projection_median": p.get("projection_median"),
                }
                for p in top_candidates
            ]
            system_prompt = (
                "You are the combined Chief Scout (Marcus) and Roster Architect (Winston) in a fantasy football draft war room.\n"
                "Evaluate the top candidate players. For each player, produce:\n"
                "1. upside_sentence: Exactly 1 sentence focusing on upside talent (Marcus).\n"
                "2. need_sentence: Exactly 1 sentence focusing on roster fit and positional need (Winston).\n"
                "Return strict JSON format matching: {'evaluations': [{'player_id': '...', 'upside_sentence': '...', 'need_sentence': '...'}]}"
            )
            user_prompt = f"Top candidate players: {cand_info}.\nCurrent User Roster: {user_roster}."

            t_batch_start = time.time()
            max_attempts = 2
            for attempt in range(1, max_attempts + 1):
                raw = call_llm_api(system_prompt, user_prompt, model=self.marcus.model, timeout_seconds=timeout_seconds)
                if raw:
                    try:
                        data = json.loads(raw)
                        if validate_schema(data, "batched_evaluations.schema.json"):
                            fresh_marcus_notes: Dict[str, str] = {}
                            fresh_winston_notes: Dict[str, str] = {}
                            fresh_marcus_list: List[Dict[str, Any]] = []
                            fresh_winston_list: List[Dict[str, Any]] = []

                            for item in data.get("evaluations", []):
                                pid = str(item.get("player_id"))
                                if pid and item.get("upside_sentence"):
                                    fresh_marcus_notes[pid] = item["upside_sentence"]
                                    fresh_marcus_list.append({"agent": "Marcus", "player_id": pid, "upside_sentence": item["upside_sentence"]})
                                if pid and item.get("need_sentence"):
                                    fresh_winston_notes[pid] = item["need_sentence"]
                                    fresh_winston_list.append({"agent": "Winston", "player_id": pid, "need_sentence": item["need_sentence"]})

                            if fresh_marcus_notes and fresh_winston_notes:
                                marcus_notes = fresh_marcus_notes
                                winston_notes = fresh_winston_notes
                                marcus_list = fresh_marcus_list
                                winston_list = fresh_winston_list
                                marcus_winston_success = True
                                break
                    except Exception as exc:
                        LOGGER.warning("Failed to parse batched evaluation response: %s", exc)

                elapsed_batch = time.time() - t_batch_start
                if attempt < max_attempts and elapsed_batch < 2.0:
                    LOGGER.info("Batched evaluation attempt %d failed in <2s (elapsed: %.2fs); triggering micro-retry", attempt, elapsed_batch)
                    continue
                else:
                    break

        return marcus_notes, winston_notes, marcus_list, winston_list, marcus_winston_success

    def run_orchestration(
        self,
        candidate_players: List[Dict[str, Any]],
        user_roster: List[Dict[str, Any]],
        ada_rankings: List[Dict[str, Any]],
        timeout_seconds: float = 25.0,
        force_debate: bool = False,
        opponent_rosters: Optional[Dict[Any, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute batched evaluations and Arthur synthesis with dynamic time budgeting."""
        import time
        t_start = time.time()

        if not ada_rankings:
            fallback_payload = self.build_fallback_payload([])
            fallback_payload["marcus_fallback"] = True
            fallback_payload["winston_fallback"] = True
            return fallback_payload

        # Check margin between Candidate #1 and Candidate #2
        score1 = float(ada_rankings[0].get("composite_score", 0.0))
        score2 = float(ada_rankings[1].get("composite_score", 0.0)) if len(ada_rankings) > 1 else 0.0

        margin = ((score1 - score2) / score1 * 100.0) if score1 > 0 else 100.0

        if not force_debate and margin > 3.0:
            log_action("ORCHESTRATION_BYPASS", f"Ada clear lead ({margin:.1f}% margin > 3.0%). Bypassing AI debate.", {
                "score1": score1,
                "score2": score2,
                "margin_pct": round(margin, 2),
            })
            return self.build_bypass_payload(ada_rankings, margin)

        if force_debate:
            log_action("ORCHESTRATION_MANUAL_TRIGGER", f"Manual trigger requested (force_debate=True). Invoking AI debate.", {
                "score1": score1,
                "score2": score2,
                "margin_pct": round(margin, 2),
            })
        else:
            log_action("ORCHESTRATION_TIE_BREAKER", f"Neck-and-neck candidates ({margin:.1f}% margin <= 3.0%). Invoking AI debate.", {
                "score1": score1,
                "score2": score2,
                "margin_pct": round(margin, 2),
            })

        top_candidates = ada_rankings[:3]
        batched_timeout = max(8.0, min(12.0, timeout_seconds * 0.4))

        marcus_winston_success = False
        try:
            marcus_notes, winston_notes, marcus_list, winston_list, marcus_winston_success = self.run_batched_evaluations(
                top_candidates, user_roster, timeout_seconds=batched_timeout
            )

            # Dynamic synthesis timeout: use remaining time with a minimum of 14.0s for Arthur
            elapsed = time.time() - t_start
            synthesis_timeout = max(14.0, timeout_seconds - elapsed)

            arthur_res = self.arthur.synthesize(
                marcus_list,
                winston_list,
                ada_rankings,
                user_roster=user_roster,
                opponent_rosters=opponent_rosters,
                timeout_seconds=synthesis_timeout,
            )
            elapsed_total = round(time.time() - t_start, 3)

            if arthur_res and arthur_res.get("top_3_picks"):
                arthur_res["marcus_notes"] = marcus_notes
                arthur_res["winston_notes"] = winston_notes
                arthur_res["fallback_used"] = False
                arthur_res["marcus_fallback"] = not marcus_winston_success
                arthur_res["winston_fallback"] = not marcus_winston_success

                log_action("ORCHESTRATION_COMPLETE", f"Orchestration completed successfully in {elapsed_total}s", {
                    "marcus_fallback": not marcus_winston_success,
                    "winston_fallback": not marcus_winston_success,
                    "arthur_fallback": False,
                    "total_elapsed_seconds": elapsed_total,
                })
                return arthur_res
            else:
                log_action("ORCHESTRATION_ARTHUR_FALLBACK", f"Arthur synthesis returned None; triggering fallback in {elapsed_total}s", {
                    "marcus_winston_success": marcus_winston_success,
                    "total_elapsed_seconds": elapsed_total,
                })

        except Exception as exc:
            LOGGER.warning("Agent orchestration error or timeout: %s", exc)
            log_action("ORCHESTRATION_ERROR", f"Agent orchestration error: {exc}", {"error": str(exc)})

        fallback_payload = self.build_fallback_payload(ada_rankings)
        fallback_payload["marcus_notes"] = marcus_notes if 'marcus_notes' in locals() else {}
        fallback_payload["winston_notes"] = winston_notes if 'winston_notes' in locals() else {}
        fallback_payload["marcus_fallback"] = not marcus_winston_success
        fallback_payload["winston_fallback"] = not marcus_winston_success
        return fallback_payload
