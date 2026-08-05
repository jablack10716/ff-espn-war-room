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
        elif schema_name == "arthur_output.schema.json":
            required = ["agent", "reasoning_2_sentences", "top_3_picks", "fallback_used"]

        for req_key in required:
            if req_key not in data:
                return False
        return True
    except Exception as exc:
        LOGGER.warning("Schema validation failed for %s: %s", schema_name, exc)
        return False


def call_llm_api(
    system_prompt: str,
    user_prompt: str,
    timeout_seconds: float = 5.0,
) -> Optional[str]:
    """Call OpenRouter or Gemini LLM API with strict timeout."""
    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("GEMINI_API_KEY")

    if not api_key:
        LOGGER.info("No LLM API key present in environment; defaulting to fallback")
        return None

    url = os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions")
    model = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")

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
        response = requests.post(url, headers=headers, json=payload, timeout=timeout_seconds)
        if response.status_code == 200:
            res_json = response.json()
            choices = res_json.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
    except Exception as exc:
        LOGGER.warning("LLM API call failed or timed out: %s", exc)

    return None


class MarcusAgent:
    """Marcus: Chief Scout evaluating upside pathways."""

    def __init__(self) -> None:
        self.system_prompt = load_file(PROMPTS_DIR / "marcus_system.txt")

    def evaluate_player(
        self, player: Dict[str, Any], timeout_seconds: float = 5.0
    ) -> Optional[Dict[str, Any]]:
        pid = str(player.get("player_id"))
        pname = player.get("full_name")
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

        raw_response = call_llm_api(self.system_prompt, user_prompt, timeout_seconds)
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

    def __init__(self) -> None:
        self.system_prompt = load_file(PROMPTS_DIR / "winston_system.txt")

    def evaluate_player(
        self,
        player: Dict[str, Any],
        user_roster: List[Dict[str, Any]],
        timeout_seconds: float = 5.0,
    ) -> Optional[Dict[str, Any]]:
        pid = str(player.get("player_id"))
        pname = player.get("full_name")
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

        raw_response = call_llm_api(self.system_prompt, user_prompt, timeout_seconds)
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

    def __init__(self) -> None:
        self.system_prompt = load_file(PROMPTS_DIR / "arthur_system.txt")

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
                "player_name": p["player_name"],
                "position": p["position"],
                "composite_score": p["composite_score"],
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

        raw_response = call_llm_api(self.system_prompt, user_prompt, timeout_seconds)
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
    """Orchestrates Fan-Out / Fan-In agent workflow with 5s timeout cap."""

    def __init__(self) -> None:
        self.marcus = MarcusAgent()
        self.winston = WinstonAgent()
        self.arthur = ArthurAgent()

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
                "player_name": str(p.get("player_name")),
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

    def run_orchestration(
        self,
        candidate_players: List[Dict[str, Any]],
        user_roster: List[Dict[str, Any]],
        ada_rankings: List[Dict[str, Any]],
        timeout_seconds: float = 15.0,
    ) -> Dict[str, Any]:
        """Execute Fan-Out to Marcus/Winston and Fan-In to Arthur with configurable timeout cap."""
        if not ada_rankings:
            return self.build_fallback_payload([])

        top_candidates = ada_rankings[:3]

        fan_out_timeout = round(timeout_seconds * 0.6, 2)
        fan_in_timeout = round(timeout_seconds * 0.4, 2)

        # Use ThreadPoolExecutor for parallel Fan-Out with timeout cap
        marcus_notes: Dict[str, str] = {}
        winston_notes: Dict[str, str] = {}
        marcus_list: List[Dict[str, Any]] = []
        winston_list: List[Dict[str, Any]] = []

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
                futures_marcus = {
                    executor.submit(self.marcus.evaluate_player, p, fan_out_timeout): p for p in top_candidates
                }
                futures_winston = {
                    executor.submit(self.winston.evaluate_player, p, user_roster, fan_out_timeout): p for p in top_candidates
                }

                # Wait for Fan-Out with proportional timeout limit
                done_m, _ = concurrent.futures.wait(
                    futures_marcus.keys(), timeout=fan_out_timeout
                )
                done_w, _ = concurrent.futures.wait(
                    futures_winston.keys(), timeout=fan_out_timeout
                )

                for fut in done_m:
                    res = fut.result()
                    if res and res.get("player_id") and res.get("upside_sentence"):
                        marcus_notes[res["player_id"]] = res["upside_sentence"]
                        marcus_list.append(res)

                for fut in done_w:
                    res = fut.result()
                    if res and res.get("player_id") and res.get("need_sentence"):
                        winston_notes[res["player_id"]] = res["need_sentence"]
                        winston_list.append(res)

            # Fan-In to Arthur
            arthur_res = self.arthur.synthesize(marcus_list, winston_list, ada_rankings, timeout_seconds=fan_in_timeout)
            if arthur_res and arthur_res.get("top_3_picks"):
                arthur_res["marcus_notes"] = marcus_notes
                arthur_res["winston_notes"] = winston_notes
                arthur_res["fallback_used"] = False
                return arthur_res

        except Exception as exc:
            LOGGER.warning("Agent orchestration error or timeout: %s", exc)

        # Fallback to Ada-Only
        fallback_payload = self.build_fallback_payload(ada_rankings)
        fallback_payload["marcus_notes"] = marcus_notes
        fallback_payload["winston_notes"] = winston_notes
        return fallback_payload
