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
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

LOGGER = logging.getLogger("war_room_agents")

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
    from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
    TENACITY_AVAILABLE = True
except ImportError:
    TENACITY_AVAILABLE = False


def _execute_llm_request(url: str, headers: dict, payload: dict, timeout_seconds: float) -> str:
    response = requests.post(url, headers=headers, json=payload, timeout=timeout_seconds)
    if response.status_code == 429:
        raise RuntimeError("LLM API Rate Limited (HTTP 429)")
    response.raise_for_status()
    res_json = response.json()
    choices = res_json.get("choices", [])
    if choices:
        return choices[0].get("message", {}).get("content", "")
    return ""


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
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

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
            @retry(
                reraise=True,
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=0.5, min=0.5, max=3.0),
                retry=retry_if_exception_type(Exception),
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
        self.model = model or os.getenv("MARCUS_MODEL") or "gemini-2.5-flash"

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

        user_prompt = (
            f"Evaluate upside talent for candidate: {pname} (ID: {pid}, Pos: {pos}, Team: {team}, "
            f"Tier: {tier}, ADP: {adp}, Projection Median: {median}, Injury Status: {injury}).\n"
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
        self.model = model or os.getenv("WINSTON_MODEL") or "gemini-2.5-flash"

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
        self.model = model or os.getenv("ARTHUR_MODEL") or "gemini-2.5-pro"

    def synthesize(
        self,
        marcus_notes: List[Dict[str, Any]],
        winston_notes: List[Dict[str, Any]],
        ada_top_candidates: List[Dict[str, Any]],
        timeout_seconds: float = 5.0,
    ) -> Optional[Dict[str, Any]]:
        cand_summary = [
            {
                "rank": i + 1,
                "player_id": p["player_id"],
                "player_name": p.get("player_name") or p.get("full_name"),
                "position": p["position"],
                "composite_score": p.get("composite_score", 0.0),
            }
            for i, p in enumerate(ada_top_candidates[:3])
        ]

        user_prompt = (
            f"Synthesize recommendations.\n"
            f"Marcus Scout Notes: {marcus_notes}\n"
            f"Winston Roster Notes: {winston_notes}\n"
            f"Ada Top Candidates: {cand_summary}\n"
            f"Return strict JSON matching schema with keys: agent='Arthur', reasoning_2_sentences, top_3_picks, fallback_used=False."
        )

        raw_response = call_llm_api(
            self.system_prompt, user_prompt, model=self.model, timeout_seconds=timeout_seconds
        )
        if raw_response:
            try:
                data = json.loads(raw_response)
                data["fallback_used"] = False
                if validate_schema(data, "arthur_output.schema.json"):
                    return data
            except Exception:
                pass

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

    def should_trigger(self, picks_until_user_turn: int) -> bool:
        """Trigger agent graph when user turn is within 2 picks."""
        return picks_until_user_turn <= 2

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
            "top_3_picks": top_3,
            "fallback_used": True,
        }

        # Validate Arthur strict payload against schema
        validate_schema(arthur_strict_payload, "arthur_output.schema.json")

        # Attach UI notes
        arthur_strict_payload["marcus_notes"] = {}
        arthur_strict_payload["winston_notes"] = {}
        return arthur_strict_payload

    def run_batched_evaluations(
        self,
        top_candidates: List[Dict[str, Any]],
        user_roster: List[Dict[str, Any]],
        timeout_seconds: float = 6.0,
    ) -> Tuple[Dict[str, str], Dict[str, str], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Run a single batched API call for Marcus and Winston evaluations to respect API rate limits."""
        marcus_notes: Dict[str, str] = {}
        winston_notes: Dict[str, str] = {}
        marcus_list: List[Dict[str, Any]] = []
        winston_list: List[Dict[str, Any]] = []

        # Populate baseline position-aware fallbacks first
        for p in top_candidates:
            m_eval = self.marcus.evaluate_player(p, timeout_seconds=0.01)
            w_eval = self.winston.evaluate_player(p, user_roster, timeout_seconds=0.01)
            pid = str(p.get("player_id"))
            if m_eval and m_eval.get("upside_sentence"):
                marcus_notes[pid] = m_eval["upside_sentence"]
                marcus_list.append(m_eval)
            if w_eval and w_eval.get("need_sentence"):
                winston_notes[pid] = w_eval["need_sentence"]
                winston_list.append(w_eval)

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

            raw = call_llm_api(system_prompt, user_prompt, model=self.marcus.model, timeout_seconds=timeout_seconds)
            if raw:
                try:
                    data = json.loads(raw)
                    if validate_schema(data, "batched_evaluations.schema.json"):
                        for item in data.get("evaluations", []):
                            pid = str(item.get("player_id"))
                            if pid and item.get("upside_sentence"):
                                marcus_notes[pid] = item["upside_sentence"]
                                marcus_list.append({"agent": "Marcus", "player_id": pid, "upside_sentence": item["upside_sentence"]})
                            if pid and item.get("need_sentence"):
                                winston_notes[pid] = item["need_sentence"]
                                winston_list.append({"agent": "Winston", "player_id": pid, "need_sentence": item["need_sentence"]})
                except Exception as exc:
                    LOGGER.warning("Failed to parse batched evaluation response: %s", exc)

        return marcus_notes, winston_notes, marcus_list, winston_list

    def run_orchestration(
        self,
        candidate_players: List[Dict[str, Any]],
        user_roster: List[Dict[str, Any]],
        ada_rankings: List[Dict[str, Any]],
        timeout_seconds: float = 15.0,
    ) -> Dict[str, Any]:
        """Execute batched evaluations and Arthur synthesis with dynamic time budgeting."""
        import time
        t_start = time.time()

        if not ada_rankings:
            return self.build_fallback_payload([])

        top_candidates = ada_rankings[:3]
        batched_timeout = min(6.0, timeout_seconds * 0.5)

        try:
            marcus_notes, winston_notes, marcus_list, winston_list = self.run_batched_evaluations(
                top_candidates, user_roster, timeout_seconds=batched_timeout
            )

            # Dynamic synthesis timeout: use whatever time remains from total budget
            elapsed = time.time() - t_start
            synthesis_timeout = max(2.0, timeout_seconds - elapsed)

            arthur_res = self.arthur.synthesize(marcus_list, winston_list, ada_rankings, timeout_seconds=synthesis_timeout)
            if arthur_res and arthur_res.get("top_3_picks"):
                arthur_res["marcus_notes"] = marcus_notes
                arthur_res["winston_notes"] = winston_notes
                arthur_res["fallback_used"] = False
                return arthur_res

        except Exception as exc:
            LOGGER.warning("Agent orchestration error or timeout: %s", exc)

        fallback_payload = self.build_fallback_payload(ada_rankings)
        fallback_payload["marcus_notes"] = marcus_notes if 'marcus_notes' in locals() else {}
        fallback_payload["winston_notes"] = winston_notes if 'winston_notes' in locals() else {}
        return fallback_payload
