"""Phase 1 ESPN ingestion script for Fantasy Football AI War Room.

This script authenticates to ESPN using espn-api cookies, pulls league metadata,
extracts scoring settings, builds an initial player pool, normalizes records to
match public.available_players, and optionally upserts into Supabase.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from dotenv import load_dotenv
from espn_api.football import League

try:
    from supabase import Client, create_client
except Exception:  # pragma: no cover - optional path for dry-run-only usage
    Client = Any  # type: ignore[misc,assignment]
    create_client = None  # type: ignore[assignment]


LOGGER = logging.getLogger("espn_ingest")

ALLOWED_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DST"}


@dataclass
class IngestConfig:
    league_id: int
    season_year: int
    espn_s2_cookie: str
    espn_swid_cookie: str
    output_dir: Path
    dry_run: bool
    upsert_supabase: bool


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def get_env(name: str, required: bool = True, default: Optional[str] = None) -> str:
    value = os.getenv(name, default)
    if required and (value is None or str(value).strip() == ""):
        raise ValueError(f"Missing required environment variable: {name}")
    return str(value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest ESPN league data for War Room")
    parser.add_argument("--league-id", type=int, help="ESPN league id override")
    parser.add_argument("--season-year", type=int, help="ESPN season year override")
    parser.add_argument(
        "--output-dir",
        default="data/seed",
        help="Directory for generated seed artifacts",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build artifacts and validation report without database writes",
    )
    parser.add_argument(
        "--upsert-supabase",
        action="store_true",
        help="Upsert formatted players into Supabase available_players table",
    )
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> IngestConfig:
    league_id = args.league_id or int(get_env("ESPN_LEAGUE_ID"))
    season_year = args.season_year or int(get_env("ESPN_SEASON_YEAR"))

    dry_run_env = os.getenv("INGEST_DRY_RUN", "true").strip().lower() in {"1", "true", "yes", "on"}
    dry_run = True if args.dry_run else dry_run_env

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    return IngestConfig(
        league_id=league_id,
        season_year=season_year,
        espn_s2_cookie=get_env("ESPN_S2_COOKIE"),
        espn_swid_cookie=get_env("ESPN_SWID_COOKIE"),
        output_dir=output_dir,
        dry_run=dry_run,
        upsert_supabase=bool(args.upsert_supabase),
    )


def normalize_name(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9 ]+", " ", name or "")
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def slugify(value: str) -> str:
    value = normalize_name(value)
    return re.sub(r"\s+", "-", value).strip("-")


def normalize_position(raw_position: Any) -> str:
    value = str(raw_position or "").upper().strip()
    if value in {"D/ST", "DEF", "D"}:
        return "DST"
    if value not in ALLOWED_POSITIONS:
        return "DST" if "DST" in value else "RB"
    return value


def safe_get(obj: Any, names: Sequence[str], default: Any = None) -> Any:
    for name in names:
        if isinstance(obj, dict):
            if name in obj and obj[name] is not None:
                return obj[name]
        elif hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None:
                return value
    return default


def as_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


POSITION_VARIANCE = {
    "QB": {"floor_mult": 0.88, "ceil_mult": 1.12},
    "RB": {"floor_mult": 0.75, "ceil_mult": 1.30},
    "WR": {"floor_mult": 0.78, "ceil_mult": 1.28},
    "TE": {"floor_mult": 0.72, "ceil_mult": 1.35},
    "K": {"floor_mult": 0.80, "ceil_mult": 1.20},
    "DST": {"floor_mult": 0.70, "ceil_mult": 1.40},
}


def projection_triplet(player: Any, position: Optional[str] = None) -> Tuple[float, float, float]:
    floor = as_number(safe_get(player, ["projection_floor", "floor", "projected_floor"]))
    median = as_number(
        safe_get(
            player,
            ["projection_median", "projected_points", "projected_total_points", "avg_points", "points"],
        )
    )
    ceiling = as_number(safe_get(player, ["projection_ceiling", "ceiling", "projected_ceiling"]))

    if median is None:
        stats = safe_get(player, ["stats"], default=None)
        if isinstance(stats, dict):
            for key in ("projected_points", "projected_total", "avg"):
                if key in stats:
                    median = as_number(stats.get(key))
                    if median is not None:
                        break

    if median is None:
        median = 0.0

    pos = str(position or safe_get(player, ["position", "defaultPositionId"], "FA")).upper()
    var_config = POSITION_VARIANCE.get(pos, {"floor_mult": 0.80, "ceil_mult": 1.20})

    if floor is None:
        floor = max(0.0, round(median * var_config["floor_mult"], 2))
    if ceiling is None:
        ceiling = round(max(median, median * var_config["ceil_mult"]), 2)

    return round(floor, 2), round(median, 2), round(ceiling, 2)


def derive_tier(player: Any) -> int:
    tier = safe_get(player, ["tier"]) 
    if tier is not None:
        try:
            tier_i = int(tier)
            if tier_i > 0:
                return tier_i
        except (TypeError, ValueError):
            pass

    pos_rank = safe_get(player, ["posRank", "position_rank", "positionRank"]) 
    if pos_rank is not None:
        try:
            pos_rank_i = max(1, int(pos_rank))
            return ((pos_rank_i - 1) // 12) + 1
        except (TypeError, ValueError):
            pass

    overall_rank = safe_get(player, ["rank", "player_rank", "overallRank"]) 
    if overall_rank is not None:
        try:
            overall_rank_i = max(1, int(overall_rank))
            return ((overall_rank_i - 1) // 24) + 1
        except (TypeError, ValueError):
            pass

    return 99


def derive_adp(player: Any) -> Optional[float]:
    return as_number(safe_get(player, ["adp", "averageDraftPosition", "avgDraftPosition"]))


def to_available_players_row(player: Any) -> Dict[str, Any]:
    raw_name = str(safe_get(player, ["name", "full_name"], default="Unknown Player"))
    full_name = raw_name.strip() or "Unknown Player"
    normalized = normalize_name(full_name)

    raw_player_id = safe_get(player, ["playerId", "player_id", "id"]) 
    if raw_player_id is not None and str(raw_player_id).strip() != "":
        player_id = f"espn_{str(raw_player_id).strip()}"
    else:
        team = str(safe_get(player, ["proTeam", "pro_team", "team"], default="FA")).upper()
        pos = normalize_position(safe_get(player, ["position", "defaultPositionId", "eligibleSlots"], default="RB"))
        player_id = f"espn_{slugify(full_name)}_{team}_{pos}"

    team = str(safe_get(player, ["proTeam", "pro_team", "team"], default="FA")).upper()
    position = normalize_position(safe_get(player, ["position", "defaultPositionId"], default="RB"))
    bye_week = safe_get(player, ["bye_week", "byeWeek"]) 

    try:
        bye_week_val = int(bye_week) if bye_week is not None else None
    except (TypeError, ValueError):
        bye_week_val = None

    raw_injury = safe_get(player, ["injuryStatus", "injury_status", "status"], default="ACTIVE")
    injury_status = str(raw_injury).upper() if raw_injury else "ACTIVE"

    floor, median, ceiling = projection_triplet(player, position=position)

    return {
        "player_id": player_id,
        "full_name": full_name,
        "normalized_name": normalized,
        "team": team if team else None,
        "position": position,
        "bye_week": bye_week_val,
        "injury_status": injury_status,
        "tier": derive_tier(player),
        "adp": derive_adp(player),
        "projection_floor": floor,
        "projection_median": median,
        "projection_ceiling": ceiling,
        "depth_role": safe_get(player, ["depth_role", "depthRole", "lineupSlot"], default=None),
        "handcuff_for_player_id": None,
        "is_available": True,
        "last_metric_refresh_ts": None,
    }


def object_to_jsonable(obj: Any, depth: int = 0, max_depth: int = 6) -> Any:
    if depth > max_depth:
        return str(obj)

    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, dict):
        return {str(k): object_to_jsonable(v, depth + 1, max_depth) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        return [object_to_jsonable(v, depth + 1, max_depth) for v in obj]

    if hasattr(obj, "__dict__"):
        return {
            str(k): object_to_jsonable(v, depth + 1, max_depth)
            for k, v in vars(obj).items()
            if not k.startswith("_")
        }

    return str(obj)


def extract_scoring_rules(league: League) -> Dict[str, Any]:
    settings = getattr(league, "settings", None)
    scoring_candidates = {}

    if settings is not None:
        for attr_name in ("scoring_format", "scoring_type", "scoring_settings", "settings"):
            if hasattr(settings, attr_name):
                scoring_candidates[attr_name] = object_to_jsonable(getattr(settings, attr_name))

        scoring_candidates["settings_snapshot"] = object_to_jsonable(settings)

    scoring_payload = {
        "league_id": league.league_id,
        "season_year": league.year,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scoring": scoring_candidates,
    }
    return scoring_payload


def fetch_espn_pick_order(
    league_id: int,
    season_year: int,
    espn_s2: str = "",
    swid: str = "",
) -> List[int]:
    """Fetch draft pickOrder array from ESPN raw league settings API endpoint."""
    try:
        import requests

        url = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season_year}/segments/0/leagues/{league_id}"
        cookies = {}
        if espn_s2:
            cookies["espn_s2"] = espn_s2
        if swid:
            cookies["SWID"] = swid
        r = requests.get(url, params={"view": "mSettings"}, cookies=cookies, timeout=10)
        if r.status_code == 200:
            data = r.json()
            pick_order = data.get("settings", {}).get("draftSettings", {}).get("pickOrder", [])
            if isinstance(pick_order, list):
                return [int(x) for x in pick_order]
    except Exception as exc:
        LOGGER.warning("Failed to fetch draft pickOrder from ESPN API: %s", exc)
    return []


def extract_teams(
    league: League,
    pick_order: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """Extract list of teams, team slots, and team names from ESPN League."""
    teams_list: List[Dict[str, Any]] = []
    teams = getattr(league, "teams", []) or []

    if pick_order:
        order_map = {int(tid): idx + 1 for idx, tid in enumerate(pick_order)}
        sorted_teams = sorted(
            teams,
            key=lambda t: (order_map.get(int(getattr(t, "team_id", 0)), 999), getattr(t, "team_id", 0)),
        )
    else:
        sorted_teams = sorted(teams, key=lambda t: getattr(t, "team_id", 0))

    for idx, team in enumerate(sorted_teams, start=1):
        team_id = getattr(team, "team_id", idx)
        team_name = getattr(team, "team_name", f"Team {team_id}")
        owner = getattr(team, "owner", "")
        standing = getattr(team, "standing", idx)

        teams_list.append({
            "team_slot": idx,
            "team_id": team_id,
            "team_name": str(team_name),
            "owner": str(owner),
            "standing": standing,
        })

    return teams_list


def extract_roster_requirements(league: League) -> Dict[str, int]:
    """Extract position starter requirements from ESPN League settings.

    Falls back to raw API lineupSlotCounts if the python package doesn't expose them.
    """
    defaults = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "SUPERFLEX": 1, "DST": 1}
    settings = getattr(league, "settings", None)

    if settings is None:
        return defaults

    slot_map = getattr(settings, "positional_play_limits", {}) or getattr(settings, "roster_slots", {})
    if isinstance(slot_map, dict) and slot_map:
        reqs = {}
        for pos_key, val in slot_map.items():
            pos_str = normalize_position(pos_key)
            try:
                reqs[pos_str] = int(val)
            except (TypeError, ValueError):
                pass
        if reqs:
            return reqs

    return defaults


# ESPN lineup slot ID -> position name mapping
_ESPN_SLOT_ID_MAP: Dict[int, str] = {
    0: "QB",
    2: "RB",
    4: "WR",
    6: "TE",
    7: "SUPERFLEX",   # OP (Offensive Player)
    16: "DST",
    17: "K",
    23: "FLEX",        # RB/WR/TE
}


def fetch_espn_roster_and_scoring(
    league_id: int,
    season_year: int,
    espn_s2: str = "",
    swid: str = "",
) -> Dict[str, Any]:
    """Fetch roster slot counts and scoring format from the ESPN raw settings API.

    Returns a dict with:
        - "roster_requirements": Dict[str, int] mapping position -> count
        - "scoring_format": str ("PPR", "HALF_PPR", or "STANDARD")
        - "total_rounds": int or None (if available from draftSettings)
    Returns empty dict on failure.
    """
    try:
        import requests

        url = (
            f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/"
            f"{season_year}/segments/0/leagues/{league_id}"
        )
        cookies: Dict[str, str] = {}
        if espn_s2:
            cookies["espn_s2"] = espn_s2
        if swid:
            cookies["SWID"] = swid

        r = requests.get(url, params={"view": "mSettings"}, cookies=cookies, timeout=10)
        if r.status_code != 200:
            LOGGER.warning("ESPN mSettings returned HTTP %s", r.status_code)
            return {}

        data = r.json()
        settings = data.get("settings", {})

        # --- Roster Requirements from lineupSlotCounts ---
        roster_settings = settings.get("rosterSettings", {})
        lineup_slot_counts = roster_settings.get("lineupSlotCounts", {})
        roster_requirements: Dict[str, int] = {}
        if lineup_slot_counts:
            for slot_id_str, count in lineup_slot_counts.items():
                slot_id = int(slot_id_str)
                pos_name = _ESPN_SLOT_ID_MAP.get(slot_id)
                if pos_name and int(count) > 0:
                    roster_requirements[pos_name] = int(count)
            LOGGER.info("Extracted roster requirements from ESPN API: %s", roster_requirements)

        # --- Scoring Format from statId 53 (receptions) ---
        scoring_format = "STANDARD"
        scoring_settings = settings.get("scoringSettings", {})
        scoring_items = scoring_settings.get("scoringItems", [])
        for item in scoring_items:
            if item.get("statId") == 53:
                ppr_val = item.get("pointsOverride") or item.get("points", 0)
                if ppr_val == 1.0:
                    scoring_format = "PPR"
                elif ppr_val == 0.5:
                    scoring_format = "HALF_PPR"
                else:
                    scoring_format = "STANDARD"
                LOGGER.info("Detected scoring format: %s (reception pts=%.1f)", scoring_format, ppr_val)
                break

        # --- Draft rounds (if available) ---
        draft_settings = settings.get("draftSettings", {})
        total_rounds = draft_settings.get("rounds")

        result: Dict[str, Any] = {
            "scoring_format": scoring_format,
        }
        if roster_requirements:
            result["roster_requirements"] = roster_requirements
        if total_rounds is not None:
            result["total_rounds"] = int(total_rounds)

        return result

    except Exception as exc:
        LOGGER.warning("Failed to fetch roster/scoring from ESPN API: %s", exc)
        return {}


def collect_players(league: League) -> List[Any]:
    collected: List[Any] = []

    player_map = getattr(league, "player_map", None)
    if isinstance(player_map, dict) and player_map:
        collected.extend(list(player_map.values()))

    teams = getattr(league, "teams", []) or []
    for team in teams:
        roster = getattr(team, "roster", []) or []
        collected.extend(roster)

    free_agents = []
    if hasattr(league, "free_agents"):
        try:
            free_agents = league.free_agents(size=2500) or []
        except Exception as exc:  # pragma: no cover - runtime/network dependent
            LOGGER.warning("Unable to fetch free agents in bulk: %s", exc)
    collected.extend(free_agents)

    seen_keys = set()
    unique_players: List[Any] = []
    for player in collected:
        pid = safe_get(player, ["playerId", "player_id", "id"], default=None)
        name = str(safe_get(player, ["name", "full_name"], default="")).strip().lower()
        team = str(safe_get(player, ["proTeam", "pro_team", "team"], default="")).strip().upper()
        pos = str(safe_get(player, ["position", "defaultPositionId"], default="")).strip().upper()
        key = (str(pid), name, team, pos)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique_players.append(player)

    return unique_players


def validate_rows(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    duplicates = 0
    seen_ids = set()
    missing_name = 0
    invalid_position = 0

    for row in rows:
        pid = row.get("player_id")
        if pid in seen_ids:
            duplicates += 1
        else:
            seen_ids.add(pid)

        if not row.get("full_name"):
            missing_name += 1

        if row.get("position") not in ALLOWED_POSITIONS:
            invalid_position += 1

    return {
        "rows_total": len(rows),
        "unique_player_ids": len(seen_ids),
        "duplicate_player_ids": duplicates,
        "missing_full_name": missing_name,
        "invalid_position": invalid_position,
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=True)


def chunked(seq: Sequence[Dict[str, Any]], size: int) -> Iterable[Sequence[Dict[str, Any]]]:
    for idx in range(0, len(seq), size):
        yield seq[idx : idx + size]


def upsert_available_players(rows: Sequence[Dict[str, Any]]) -> None:
    supabase_url = get_env("SUPABASE_URL")
    supabase_key = get_env("SUPABASE_SERVICE_ROLE_KEY", required=False) or get_env("SUPABASE_KEY")

    if create_client is None:
        raise RuntimeError("supabase package is not installed. Install dependencies first.")

    client: Client = create_client(supabase_url, supabase_key)

    batch_size = 500
    for batch in chunked(rows, batch_size):
        try:
            client.table("available_players").upsert(list(batch), on_conflict="player_id").execute()
        except Exception as exc:
            if "injury_status" in str(exc):
                LOGGER.warning("injury_status column not yet in Supabase schema. Upserting without injury_status.")
                stripped_batch = [
                    {k: v for k, v in row.items() if k != "injury_status"}
                    for row in batch
                ]
                client.table("available_players").upsert(stripped_batch, on_conflict="player_id").execute()
            else:
                raise


def derive_scoring_format(league: League) -> str:
    """Derive scoring format string (PPR, HALF_PPR, STANDARD) from ESPN League settings."""
    try:
        settings = getattr(league, "settings", None)
        if settings and hasattr(settings, "scoring_settings"):
            scoring_list = getattr(settings, "scoring_settings", [])
            for item in scoring_list:
                stat_id = safe_get(item, ["stat_id", "id", "statId"])
                points = float(safe_get(item, ["points", "value", "score"], 0) or 0)
                if stat_id in (53, "receivingReceptions", "receptions") or "reception" in str(stat_id).lower():
                    if points >= 0.8:
                        return "PPR"
                    elif points >= 0.4:
                        return "HALF_PPR"
    except Exception:
        pass
    return "STANDARD"


HANDCUFF_MAP = {
    "chuba hubbard": "bijan robinson",
    "zack moss": "chase brown",
    "khalil herbert": "david montgomery",
    "roschon johnson": "d'andre swift",
    "braelon allen": "breece hall",
    "ray davis": "james cook",
    "blake corum": "kyren williams",
    "ty chandler": "aaron jones",
    "jaylen wright": "de'von achane",
    "trey benson": "james conner",
    "tyjae spears": "tony pollard",
    "jordan mason": "christian mccaffrey",
    "elija mitchell": "christian mccaffrey",
    "jaylen warren": "najee harris",
}


def apply_handcuff_mappings(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Populate handcuff_for_player_id for known backup RBs."""
    name_to_id = {
        str(r.get("normalized_name", "")).lower(): str(r.get("player_id"))
        for r in rows if r.get("normalized_name")
    }

    for r in rows:
        norm_name = str(r.get("normalized_name", "")).lower()
        if norm_name in HANDCUFF_MAP:
            starter_norm_name = HANDCUFF_MAP[norm_name].lower()
            if starter_norm_name in name_to_id:
                r["handcuff_for_player_id"] = name_to_id[starter_norm_name]

    return rows


def sync_espn_league_data(
    league_id: int,
    season_year: int,
    espn_s2: str,
    swid: str,
    upsert_supabase: bool = True,
) -> Dict[str, Any]:
    """Programmatically sync ESPN league data, extract teams and roster settings, and upsert players."""
    LOGGER.info("Connecting to ESPN league_id=%s year=%s for direct UI sync", league_id, season_year)
    league = League(
        league_id=league_id,
        year=season_year,
        espn_s2=espn_s2,
        swid=swid,
    )

    pick_order = fetch_espn_pick_order(
        league_id=league_id,
        season_year=season_year,
        espn_s2=espn_s2,
        swid=swid,
    )
    teams = extract_teams(league, pick_order=pick_order)
    roster_reqs = extract_roster_requirements(league)
    scoring_payload = extract_scoring_rules(league)
    scoring_fmt = derive_scoring_format(league)
    players = collect_players(league)
    rows = [to_available_players_row(p) for p in players]
    rows = apply_handcuff_mappings(rows)

    if upsert_supabase:
        LOGGER.info("Upserting %s normalized players into Supabase", len(rows))
        upsert_available_players(rows)

    return {
        "league_id": league_id,
        "season_year": season_year,
        "teams": teams,
        "roster_requirements": roster_reqs,
        "scoring_rules": scoring_payload,
        "scoring_format": scoring_fmt,
        "player_count": len(rows),
    }


def main() -> None:
    configure_logging()
    load_dotenv()

    args = parse_args()
    config = build_config(args)

    LOGGER.info("Connecting to ESPN league_id=%s year=%s", config.league_id, config.season_year)
    league = League(
        league_id=config.league_id,
        year=config.season_year,
        espn_s2=config.espn_s2_cookie,
        swid=config.espn_swid_cookie,
    )

    LOGGER.info("Extracting scoring settings, team metadata, and collecting player pool")
    scoring_payload = extract_scoring_rules(league)
    pick_order = fetch_espn_pick_order(
        league_id=config.league_id,
        season_year=config.season_year,
        espn_s2=config.espn_s2_cookie,
        swid=config.espn_swid_cookie,
    )
    teams = extract_teams(league, pick_order=pick_order)
    roster_reqs = extract_roster_requirements(league)
    players = collect_players(league)

    LOGGER.info("Normalizing %s players to available_players schema", len(players))
    rows = [to_available_players_row(player) for player in players]

    report = validate_rows(rows)
    report["captured_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["league_id"] = config.league_id
    report["season_year"] = config.season_year
    report["teams_count"] = len(teams)
    report["roster_requirements"] = roster_reqs

    stamp = f"{config.league_id}_{config.season_year}"
    scoring_path = config.output_dir / f"scoring_rules_{stamp}.json"
    players_path = config.output_dir / f"available_players_seed_{stamp}.json"
    report_path = config.output_dir / f"ingest_validation_report_{stamp}.json"

    write_json(scoring_path, scoring_payload)
    write_json(players_path, rows)
    write_json(report_path, report)

    LOGGER.info("Wrote scoring payload: %s", scoring_path)
    LOGGER.info("Wrote player seed payload: %s", players_path)
    LOGGER.info("Wrote validation report: %s", report_path)
    LOGGER.info("Validation summary: %s", json.dumps(report, indent=2))

    if config.upsert_supabase:
        if config.dry_run:
            LOGGER.warning("Skipping Supabase upsert because dry-run is enabled")
        else:
            LOGGER.info("Upserting normalized rows into Supabase available_players")
            upsert_available_players(rows)
            LOGGER.info("Supabase upsert complete")


if __name__ == "__main__":
    main()

