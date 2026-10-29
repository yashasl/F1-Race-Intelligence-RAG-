"""Data preprocessor for F1 RAG ingestion pipeline.

Responsibilities:
- Join driver/constructor names to race results
- Filter data for 2021-2025 seasons
- Handle missing values, \\N markers, invalid data types
- Create meaningful, readable documents for each document type
- Preserve provenance (source IDs, source table, source record ID)
- Report missing columns or incompatible tables
"""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from data_loader import (
    load_drivers,
    load_constructors,
    load_races,
    load_results,
    load_qualifying,
    load_pit_stops,
    load_lap_times,
    load_driver_standings,
    load_constructor_standings,
    get_2021_2025_race_ids,
    filter_results_by_race_ids,
    filter_qualifying_by_race_ids,
    filter_pit_stops_by_race_ids,
    filter_lap_times_by_race_ids,
    filter_driver_standings_by_race_ids,
    filter_constructor_standings_by_race_ids,
)

from utils import is_missing, format_lap_milliseconds

logger = logging.getLogger("f1rag.preprocessor")

MIN_SEASON = 2021
MAX_SEASON = 2025


def _format_missing(value: Any) -> str:
    """Convert missing/None values to '\\N' for consistent documentation."""
    if value is None or value == "" or value == "\\N":
        return "\\N"
    return str(value)


def _format_number(value: Any) -> str:
    """Format a number value, handling missing values."""
    if value is None or value == "\\N" or value == "":
        return "\\N"
    try:
        v = float(value)
        if abs(v - round(v)) < 1e-9:
            return str(int(round(v)))
        text = f"{v:.2f}".rstrip("0").rstrip(".")
        return text or "0"
    except (ValueError, TypeError):
        return str(value).strip() or "\\N"


def _build_driver_name_cache(drivers: Dict[int, Dict[str, Any]]) -> Dict[int, str]:
    """Build a cache of driverId -> "forename surname"."""
    cache = {}
    for driver_id, info in drivers.items():
        forename = info.get("forename") or "\\N"
        surname = info.get("surname") or "\\N"
        if forename != "\\N" and surname != "\\N":
            cache[driver_id] = f"{forename} {surname}".strip()
        else:
            cache[driver_id] = _format_missing(info.get("driverRef"))
    return cache


def _build_constructor_name_cache(constructors: Dict[int, Dict[str, Any]]) -> Dict[int, str]:
    """Build a cache of constructorId -> constructor name."""
    cache = {}
    for constructor_id, info in constructors.items():
        name = info.get("name") or "\\N"
        cache[constructor_id] = name if name else "\\N"
    return cache


def create_race_result_documents(
    results: List[Dict[str, Any]],
    drivers: Dict[int, Dict[str, Any]],
    constructors: Dict[int, Dict[str, Any]],
    races: Dict[int, Dict[str, Any]],
    season_race_ids: Dict[int, List[int]],
) -> List[Dict[str, Any]]:
    """Create race result documents: one per driver per race.

    Each document captures the full race result for a single driver in a single race.
    """
    logger.info("Creating race result documents...")
    driver_cache = _build_driver_name_cache(drivers)
    constructor_cache = _build_constructor_name_cache(constructors)

    documents = []
    # Build race name lookup
    race_name_lookup = {rid: info.get("name") for rid, info in races.items()}

    for result in results:
        race_id = result.get("raceId")
        driver_id = result.get("driverId")
        constructor_id = result.get("constructorId")

        if race_id is None or driver_id is None:
            logger.warning(f"Skipping result with missing raceId or driverId: {result}")
            continue

        # Get race season and filter to 2021-2025
        race_info = races.get(race_id, {})
        year = race_info.get("year")
        if year is None or not (MIN_SEASON <= year <= MAX_SEASON):
            continue

        # Get race round and name
        race_round = race_info.get("round")
        race_name = race_name_lookup.get(race_id, "\\N")

        # Determine if this race is in our target seasons
        if race_id not in season_race_ids.get(year, []):
            continue

        doc = {
            "document_type": "race_result",
            "season": year,
            "race_id": race_id,
            "race_name": race_name,
            "race_round": race_round,
            "driver_id": driver_id,
            "constructor_id": constructor_id,
            "source_table": "results",
            "source_record_id": result.get("resultId"),
            # Driver information
            "driver_forename": driver_cache.get(driver_id, "\\N"),
            # driver_surname extracted from the full name
            "driver_surname": driver_cache.get(driver_id, "").rsplit(" ", 1)[-1] if " " in str(driver_cache.get(driver_id, "")) else "\\N",
            "driver_code": result.get("code") if isinstance(result.get("code"), str) and result.get("code") != "\\N" else _format_missing(drivers.get(driver_id, {}).get("code")),
            "driver_number": _format_number(result.get("number")),
            # Position information
            "grid": _format_number(result.get("grid")),
            "position": _format_number(result.get("position")),
            "positionText": result.get("positionText") or "\\N",
            "positionOrder": _format_missing(result.get("positionOrder")),
            # Constructor information
            "constructor_name": constructor_cache.get(constructor_id, "\\N"),
            # Constructor nationality extracted from name
            "constructor_nationality": constructor_cache.get(constructor_id, "").rsplit(" ", 1)[-1] if " " in str(constructor_cache.get(constructor_id, "")) else "\\N"
            if constructor_id in constructor_cache
            else "\\N",
            # Race performance
            "points": _format_number(result.get("points")),
            "laps_completed": _format_number(result.get("laps")),
            "fastest_lap": _format_number(result.get("fastestLap")),
            "fastest_lap_time": result.get("fastestLapTime") or "\\N",
            "fastest_lap_speed": result.get("fastestLapSpeed") or "\\N",
            "status": result.get("statusId") or "\\N",
            # Result-specific time
            "race_time": result.get("time") or "\\N",
            "race_milliseconds": result.get("milliseconds") or "\\N",
        }
        documents.append(doc)

    logger.info(f"Created {len(documents)} race result documents")
    return documents


def create_qualifying_documents(
    qualifying: List[Dict[str, Any]],
    drivers: Dict[int, Dict[str, Any]],
    constructors: Dict[int, Dict[str, Any]],
    races: Dict[int, Dict[str, Any]],
    season_race_ids: Dict[int, List[int]],
) -> List[Dict[str, Any]]:
    """Create qualifying documents: one per driver per qualifying session.

    Each document captures a driver's qualifying performance at a single race.
    """
    logger.info("Creating qualifying documents...")
    driver_cache = _build_driver_name_cache(drivers)
    constructor_cache = _build_constructor_name_cache(constructors)

    documents = []
    race_name_lookup = {rid: info.get("name") for rid, info in races.items()}

    for q in qualifying:
        race_id = q.get("raceId")
        driver_id = q.get("driverId")
        constructor_id = q.get("constructorId")

        if race_id is None or driver_id is None:
            logger.warning(f"Skipping qualifying record with missing raceId or driverId: {q}")
            continue

        race_info = races.get(race_id, {})
        year = race_info.get("year")
        if year is None or not (MIN_SEASON <= year <= MAX_SEASON):
            continue

        if race_id not in season_race_ids.get(year, []):
            continue

        race_name = race_name_lookup.get(race_id, "\\N")

        doc = {
            "document_type": "qualifying",
            "season": year,
            "race_id": race_id,
            "race_name": race_name,
            "driver_id": driver_id,
            "constructor_id": constructor_id,
            "source_table": "qualifying",
            "source_record_id": q.get("qualifyId"),
            # Driver info
            "driver_forename": driver_cache.get(driver_id, "\\N"),
            "driver_code": _format_missing(drivers.get(driver_id, {}).get("code")),
            "driver_number": _format_number(q.get("number")),
            # Qualifying position
            "qualifying_position": _format_number(q.get("position")),
            # Q1, Q2, Q3 times
            "q1_time": q.get("q1") or "\\N",
            "q2_time": q.get("q2") or "\\N",
            "q3_time": q.get("q3") or "\\N",
            # Constructor info
            "constructor_name": constructor_cache.get(constructor_id, "\\N"),
            # Constructor nationality
            "constructor_nationality": constructor_cache.get(constructor_id, "\\N"),
        }
        documents.append(doc)

    logger.info(f"Created {len(documents)} qualifying documents")
    return documents


def create_pit_stop_documents(
    pit_stops: List[Dict[str, Any]],
    drivers: Dict[int, Dict[str, Any]],
    constructors: Dict[int, Dict[str, Any]],
    races: Dict[int, Dict[str, Any]],
    season_race_ids: Dict[int, List[int]],
) -> List[Dict[str, Any]]:
    """Create pit stop documents: one per pit stop.

    Each document captures a single pit stop event with available race and driver context.
    """
    logger.info("Creating pit stop documents...")
    driver_cache = _build_driver_name_cache(drivers)
    constructor_cache = _build_constructor_name_cache(constructors)

    documents = []
    race_name_lookup = {rid: info.get("name") for rid, info in races.items()}

    for ps in pit_stops:
        race_id = ps.get("raceId")
        driver_id = ps.get("driverId")

        if race_id is None or driver_id is None:
            logger.warning(f"Skipping pit stop with missing raceId or driverId: {ps}")
            continue

        race_info = races.get(race_id, {})
        year = race_info.get("year")
        if year is None or not (MIN_SEASON <= year <= MAX_SEASON):
            continue

        if race_id not in season_race_ids.get(year, []):
            continue

        race_name = race_name_lookup.get(race_id, "\\N")

        doc = {
            "document_type": "pit_stop",
            "season": year,
            "race_id": race_id,
            "race_name": race_name,
            "driver_id": driver_id,
            "constructor_id": ps.get("constructorId") if isinstance(ps.get("constructorId"), int) else None,
            "source_table": "pit_stops",
            "source_record_id": None,  # pit_stops doesn't have a separate result ID
            # Driver context
            "driver_forename": driver_cache.get(driver_id, "\\N"),
            "driver_code": _format_missing(drivers.get(driver_id, {}).get("code")),
            "driver_number": _format_number(ps.get("number")),
            # Pit stop details
            "stop_number": _format_number(ps.get("stop")),
            "lap_number": _format_number(ps.get("lap")),
            "stop_duration": _format_number(ps.get("duration")),
            "stop_milliseconds": _format_number(ps.get("milliseconds")),
            "stop_time": ps.get("time") or "\\N",
            # Constructor context - get constructor name by constructor_id
            "constructor_name": constructor_cache.get(ps.get("constructorId"), "\\N") if ps.get("constructorId") is not None else "\\N",
        }
        documents.append(doc)

    logger.info(f"Created {len(documents)} pit stop documents")
    return documents


def create_driver_profile_documents(
    drivers: Dict[int, Dict[str, Any]],
    results: List[Dict[str, Any]],
    season_race_ids: Dict[int, List[int]],
) -> List[Dict[str, Any]]:
    """Create driver profile documents: one per driver.

    Each document summarizes a driver's career across the 2021-2025 period,
    including total races, points, wins, and teams.
    """
    logger.info("Creating driver profile documents...")

    # Aggregate results per driver for 2021-2025 season
    driver_stats: Dict[int, Dict[str, Any]] = {}

    for result in results:
        driver_id = result.get("driverId")
        if driver_id is None:
            continue

        if driver_id not in driver_stats:
            driver_stats[driver_id] = {
                "driverId": driver_id,
                "total_races": 0,
                "total_points": 0.0,
                "wins": 0,
                "best_position": None,
                "podiums": 0,
                "seasons": set(),
            }

        stats = driver_stats[driver_id]
        stats["total_races"] += 1

        # Get year from race
        race_id = result.get("raceId")
        if race_id is not None:
            year = None
            for y, rids in season_race_ids.items():
                if race_id in rids:
                    year = int(y)
                    break
            if year is not None and MIN_SEASON <= year <= MAX_SEASON:
                stats["seasons"].add(year)

        pts = result.get("points")
        if pts is not None and str(pts) != "\\N":
            try:
                stats["total_points"] += float(pts)
            except (ValueError, TypeError):
                pass

        pos = result.get("position")
        if pos is not None and str(pos) != "\\N":
            try:
                p = int(pos)
                if stats["best_position"] is None or p < stats["best_position"]:
                    stats["best_position"] = p
                if pos <= 3:
                    stats["podiums"] += 1
            except (ValueError, TypeError):
                pass

        # Count wins (position = 1)
        if pos is not None and str(pos) != "\\N":
            try:
                if int(pos) == 1:
                    stats["wins"] += 1
            except (ValueError, TypeError):
                pass

    # Now create the actual documents for each driver
    documents = []
    for driver_id, info in drivers.items():
        participation = driver_stats.get(driver_id, {
            "total_races": 0,
            "total_points": 0.0,
            "wins": 0,
            "best_position": None,
            "podiums": 0,
            "seasons": set(),
        })

        doc = {
            "document_type": "driver_profile",
            "season": None,  # Driver profile spans seasons 2021-2025
            "race_id": None,
            "driver_id": driver_id,
            "source_table": "drivers",
            "source_record_id": driver_id,
            "driver_ref": info.get("driverRef") or "\\N",
            "driver_number": info.get("number") if not is_missing(info.get("number")) else "\\N",
            "code": info.get("code") if not is_missing(info.get("code")) else "\\N",
            "forename": info.get("forename") or "\\N",
            "surname": info.get("surname") or "\\N",
            "dob": info.get("dob") or "\\N",
            "nationality": info.get("nationality") or "\\N",
            "url": info.get("url") or "\\N",
            # Participation stats for 2021-2025
            "total_races_2021_2025": participation.get("total_races", 0),
            "total_points_2021_2025": round(participation.get("total_points", 0.0), 2),
            "wins_2021_2025": participation.get("wins", 0),
            "best_position_2021_2025": _format_number(participation.get("best_position")),
        }
        documents.append(doc)

    logger.info(f"Created {len(documents)} driver profile documents")
    return documents


def create_constructor_profile_documents(
    constructors: Dict[int, Dict[str, Any]],
    results: List[Dict[str, Any]],
    season_race_ids: Dict[int, List[int]],
) -> List[Dict[str, Any]]:
    """Create constructor profile documents: one per constructor.

    Each document summarizes a constructor's performance across 2021-2025.
    """
    logger.info("Creating constructor profile documents...")

    # Aggregate results per constructor for 2021-2025 season
    constructor_stats: Dict[int, Dict[str, Any]] = {}

    for result in results:
        constructor_id = result.get("constructorId")
        if constructor_id is None:
            continue

        if constructor_id not in constructor_stats:
            constructor_stats[constructor_id] = {
                "constructorId": constructor_id,
                "total_races": 0,
                "total_points": 0.0,
                "wins": 0,
                "best_position": None,
                "podiums": 0,
                "seasons": set(),
            }

        stats = constructor_stats[constructor_id]
        stats["total_races"] += 1

        # Get year from race
        race_id = result.get("raceId")
        if race_id is not None:
            year = None
            for y, rids in season_race_ids.items():
                if race_id in rids:
                    year = int(y)
                    break
            if year is not None and MIN_SEASON <= year <= MAX_SEASON:
                stats["seasons"].add(year)

        pts = result.get("points")
        if pts is not None and str(pts) != "\\N":
            try:
                stats["total_points"] += float(pts)
            except (ValueError, TypeError):
                pass

        pos = result.get("position")
        if pos is not None and str(pos) != "\\N":
            try:
                if int(pos) == 1:
                    stats["wins"] += 1
            except (ValueError, TypeError):
                pass

    # Now create the actual documents for each constructor
    documents = []
    for constructor_id, info in constructors.items():
        stats = constructor_stats.get(constructor_id, {
            "constructorId": constructor_id,
            "total_races": 0,
            "total_points": 0.0,
            "wins": 0,
            "best_position": None,
            "podiums": 0,
        })

        name = info.get("name") or "\\N"
        nationality = info.get("nationality") or "\\N"

        doc = {
            "document_type": "constructor_profile",
            "season": None,
            "race_id": None,
            "constructor_id": constructor_id,
            "source_table": "constructors",
            "source_record_id": constructor_id,
            "constructor_ref": info.get("constructorRef") or "\\N",
            "constructor_name": name,
            "constructor_nationality": nationality,
            "url": info.get("url") or "\\N",
            # Performance stats for 2021-2025
            "total_races_2021_2025": stats.get("total_races", 0),
            "total_points_2021_2025": stats.get("total_points", 0.0),
            "wins_2021_2025": stats.get("wins", 0),
            "best_position_2021_2025": _format_number(stats.get("best_position")),
            "podiums_2021_2025": stats.get("podiums", 0),
        }
        documents.append(doc)

    logger.info(f"Created {len(documents)} constructor profile documents")
    return documents


def create_standings_documents(
    driver_standings: List[Dict[str, Any]],
    constructor_standings: List[Dict[str, Any]],
    drivers: Dict[int, Dict[str, Any]],
    constructors: Dict[int, Dict[str, Any]],
    races: Dict[int, Dict[str, Any]],
    season_race_ids: Dict[int, List[int]],
) -> List[Dict[str, Any]]:
    """Create driver and constructor standings documents.

    Each document captures the standings position for a driver/constructor
    at a specific race in a specific season.
    """
    logger.info("Creating standings documents...")
    driver_cache = _build_driver_name_cache(drivers)
    constructor_cache = _build_constructor_name_cache(constructors)
    race_name_lookup = {rid: info.get("name") for rid, info in races.items()}

    documents = []

    # Driver standings documents
    for ds in driver_standings:
        race_id = ds.get("raceId")
        driver_id = ds.get("driverId")

        if race_id is None or driver_id is None:
            continue

        race_info = races.get(race_id, {})
        year = race_info.get("year") if isinstance(race_info, dict) else None
        if year is None or not (MIN_SEASON <= year <= MAX_SEASON):
            continue

        if race_id not in season_race_ids.get(year, []):
            continue

        race_name = race_name_lookup.get(race_id, "\\N")

        doc = {
            "document_type": "driver_standings",
            "season": year,
            "race_id": race_id,
            "race_name": race_name,
            "driver_id": driver_id,
            "source_table": "driver_standings",
            "source_record_id": ds.get("driverStandingsId"),
            "driver_forename": driver_cache.get(driver_id, "\\N"),
            # Surname - get from driver cache
            "driver_surname": driver_cache.get(driver_id, "").rsplit(" ", 1)[-1] if " " in str(driver_cache.get(driver_id, "")) else "\\N",
            # Standings data
            "points": _format_number(ds.get("points")),
            "position": _format_number(ds.get("position")),
            "positionText": ds.get("positionText") or "\\N",
            "wins": _format_number(ds.get("wins")),
        }
        documents.append(doc)

    # Constructor standings documents
    for cs in constructor_standings:
        race_id = cs.get("raceId")
        constructor_id = cs.get("constructorId")

        if race_id is None or constructor_id is None:
            continue

        race_info = races.get(race_id, {})
        year = race_info.get("year") if isinstance(race_info, dict) else None
        if year is None or not (MIN_SEASON <= year <= MAX_SEASON):
            continue

        if race_id not in season_race_ids.get(year, []):
            continue

        race_name = race_name_lookup.get(race_id, "\\N")

        doc = {
            "document_type": "constructor_standings",
            "season": year,
            "race_id": race_id,
            "race_name": race_name,
            "constructor_id": constructor_id,
            "source_table": "constructor_standings",
            "source_record_id": cs.get("constructorStandingsId"),
            "constructor_name": constructor_cache.get(constructor_id, "\\N"),
            "points": _format_number(cs.get("points")),
            "position": _format_number(cs.get("position")),
            "positionText": cs.get("positionText") or "\\N",
            "wins": _format_number(cs.get("wins")),
        }
        documents.append(doc)

    logger.info(f"Created {len(documents)} standings documents")
    return documents


def create_lap_time_summary_documents(
    lap_times: List[Dict[str, Any]],
    drivers: Dict[int, Dict[str, Any]],
    races: Dict[int, Dict[str, Any]],
    season_race_ids: Dict[int, List[int]],
    max_drivers: int = 50,
    max_laps_per_driver: int = 20,
) -> List[Dict[str, Any]]:
    """Create lap time summary documents.

    Creates structured summaries of lap data by driver, race, and stint
    rather than embedding every raw lap. Also creates some detailed lap
    documents for structured analysis.

    Parameters:
        max_drivers: Maximum number of drivers to include (prevents huge documents)
        max_laps_per_driver: Maximum laps to summarize per driver per race
    """
    logger.info("Creating lap time summary documents...")

    # Filter lap times to 2021-2025 races
    filtered_lap_times = filter_lap_times_by_race_ids(lap_times, set().union(*season_race_ids.values()))

    # Group by driver and race
    driver_race_laps: Dict[int, Dict[int, List[int]]] = {}  # driverId -> raceId -> list of lap numbers
    driver_race_milliseconds: Dict[int, Dict[int, List[int]]] = {}  # driverId -> raceId -> list of milliseconds

    for lt in filtered_lap_times:
        driver_id = lt.get("driverId")
        race_id = lt.get("raceId")

        if driver_id is None or race_id is None:
            continue

        # Check year properly
        race_info = races.get(race_id, {})
        year = race_info.get("year")
        if year is None or not (MIN_SEASON <= year <= MAX_SEASON):
            continue

        if driver_id not in driver_race_laps:
            driver_race_laps[driver_id] = {}
            driver_race_milliseconds[driver_id] = {}

        if race_id not in driver_race_laps[driver_id]:
            driver_race_laps[driver_id][race_id] = []
            driver_race_milliseconds[driver_id][race_id] = []

        driver_race_laps[driver_id][race_id].append(lt.get("lap", 0))
        driver_race_milliseconds[driver_id][race_id].append(lt.get("milliseconds", 0))

    # Limit number of drivers included
    driver_ids = list(driver_race_laps.keys())[:max_drivers]

    documents = []
    race_name_lookup = {rid: info.get("name") for rid, info in races.items()}

    for driver_id in driver_ids:
        laps_by_race = driver_race_laps.get(driver_id, {})
        ms_by_race = driver_race_milliseconds.get(driver_id, {})

        # Get driver name
        driver_forename = drivers.get(driver_id, {}).get("forename", "\\N")
        driver_surname = drivers.get(driver_id, {}).get("surname", "\\N")

        # Get some races for this driver
        races_for_driver = list(laps_by_race.keys())[:5]  # limit to 5 races per driver

        for race_id in races_for_driver:
            laps = laps_by_race.get(race_id, [])
            ms = ms_by_race.get(race_id, [])

            if not laps:
                continue

            race_name = race_name_lookup.get(race_id, "\\N")
            year = races.get(race_id, {}).get("year", 0)

            # Calculate summary statistics
            lap_numbers = sorted(laps)
            lap_milliseconds = ms[:len(laps)]

            # Calculate stint summary
            if len(lap_milliseconds) > 0:
                valid_ms = [m for m in lap_milliseconds if m is not None and isinstance(m, (int, float))]
                total_ms = sum(valid_ms) if valid_ms else 0
                avg_ms = total_ms / len(valid_ms) if valid_ms else 0
                min_ms = min(valid_ms) if valid_ms else 0
                max_ms = max(valid_ms) if valid_ms else 0
            else:
                total_ms = avg_ms = min_ms = max_ms = 0

            # Number of stints (groups of consecutive laps)
            stints = 1 if lap_numbers else 0
            if len(lap_numbers) > 1:
                differences = [lap_numbers[i+1] - lap_numbers[i] for i in range(len(lap_numbers)-1)]
                # A new stint starts when there's a gap > 1 lap
                stints = sum(1 for d in differences if d > 1) + 1

            doc = {
                "document_type": "lap_time_summary",
                "season": year,
                "race_id": race_id,
                "race_name": race_name,
                "driver_id": driver_id,
                "source_table": "lap_times",
                "source_record_id": None,  # no single record ID for lap data
                "driver_forename": driver_forename,
                "driver_surname": driver_surname,
                "lap_count": len(lap_numbers),
                "total_lap_milliseconds": total_ms,
                "average_lap_ms": round(avg_ms, 2),
                "min_lap_ms": min_ms,
                "max_lap_ms": max_ms,
                "stint_count": stints,
                "lap_range": f"{lap_numbers[0]}-{lap_numbers[-1]}" if lap_numbers else "\\N",
                "laps": lap_numbers[:max_laps_per_driver],  # truncated for readability
                "lap_milliseconds": lap_milliseconds[:max_laps_per_driver],
            }
            documents.append(doc)

    logger.info(f"Created {len(documents)} lap time summary documents")
    return documents