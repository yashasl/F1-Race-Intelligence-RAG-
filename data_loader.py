"""Data loader for F1 CSV datasets.

Loads CSV files from the data/ directory, validates schemas,
and provides filtered views for the 2021-2025 season range.
Reuses existing utility functions from utils.py where possible.

Key schema observations (from inspect.py):
- races: raceId(0), year(1), round(2), circuitId(3), name(4), date(5), time(6)
- drivers: driverId(0), driverRef(1), number(2), code(3), forename(4), surname(5), dob(6), nationality(7)
- constructors: constructorId(0), constructorRef(1), name(2), nationality(3), url(4)
- results: resultId(0), raceId(1), driverId(2), constructorId(3), number(4), grid(5), position(6),
           positionText(7), positionOrder(8), points(9), laps(10), time(11), milliseconds(12),
           fastestLap(13), rank(14), fastestLapTime(15), fastestLapSpeed(17), statusId(18)
- qualifying: qualifyId(0), raceId(1), driverId(2), constructorId(3), number(4), position(5), q1(6), q2(7), q3(8)
- pit_stops: raceId(0), driverId(1), stop(2), lap(3), time(4), duration(5), milliseconds(6)
- lap_times: raceId(0), driverId(1), lap(2), position(3), time(4), milliseconds(5)
- driver_standings: driverStandingsId(0), raceId(1), driverId(2), points(3), position(4), positionText(5), wins(6)
- constructor_standings: constructorStandingsId(0), raceId(1), constructorId(2), points(3), position(4), positionText(5), wins(6)
"""

import csv
import os
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from config import MIN_SEASON, MAX_SEASON

import numpy as np

from utils import is_missing

logger = logging.getLogger("f1rag.data_loader")

DATA_DIR = Path(__file__).resolve().parent / "data"


def read_csv_rows(path: Path) -> Tuple[List[str], List[List[str]]]:
    """Read a CSV file and return (header, rows)."""
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)
    return header, rows


def load_drivers() -> Dict[int, Dict[str, Any]]:
    """Load drivers.csv into a dict keyed by driverId.

    Returns dict mapping driverId -> {driverRef, number, code, forename, surname, dob, nationality, url}
    """
    path = DATA_DIR / "drivers.csv"
    header, rows = read_csv_rows(path)
    drivers = {}
    for row in rows:
        try:
            driver_id = int(row[0])
        except (ValueError, IndexError):
            logger.warning(f"Skipping driver row with invalid driverId: {row}")
            continue
        drivers[driver_id] = {
            "driverId": driver_id,
            "driverRef": row[1] if len(row) > 1 else None,
            "number": row[2] if len(row) > 2 else None,
            "code": row[3] if len(row) > 3 else None,
            "forename": row[4] if len(row) > 4 else None,
            "surname": row[5] if len(row) > 5 else None,
            "dob": row[6] if len(row) > 6 else None,
            "nationality": row[7] if len(row) > 7 else None,
            "url": row[8] if len(row) > 8 else None,
        }
    logger.info(f"Loaded {len(drivers)} drivers")
    return drivers


def load_constructors() -> Dict[int, Dict[str, Any]]:
    """Load constructors.csv into a dict keyed by constructorId."""
    path = DATA_DIR / "constructors.csv"
    header, rows = read_csv_rows(path)
    constructors = {}
    for row in rows:
        try:
            constructor_id = int(row[0])
        except (ValueError, IndexError):
            logger.warning(f"Skipping constructor row with invalid constructorId: {row}")
            continue
        constructors[constructor_id] = {
            "constructorId": constructor_id,
            "constructorRef": row[1] if len(row) > 1 else None,
            "name": row[2] if len(row) > 2 else None,
            "nationality": row[3] if len(row) > 3 else None,
            "url": row[4] if len(row) > 4 else None,
        }
    logger.info(f"Loaded {len(constructors)} constructors")
    return constructors


def load_races() -> Dict[int, Dict[str, Any]]:
    """Load races.csv into a dict keyed by raceId.

    Also returns a set of raceIds for the 2021-2025 seasons.
    """
    path = DATA_DIR / "races.csv"
    header, rows = read_csv_rows(path)
    races = {}
    season_race_ids = {2021: [], 2022: [], 2023: [], 2024: [], 2025: []}
    for row in rows:
        try:
            race_id = int(row[0])
            year = int(row[1])
        except (ValueError, IndexError):
            logger.warning(f"Skipping race row with invalid ID: {row}")
            continue

        races[race_id] = {
            "raceId": race_id,
            "year": year,
            "round": int(row[2]) if len(row) > 2 and not is_missing(row[2]) else None,
            "circuitId": int(row[3]) if len(row) > 3 and not is_missing(row[3]) else None,
            "name": row[4] if len(row) > 4 else None,
            "date": row[5] if len(row) > 5 else None,
            "time": row[6] if len(row) > 6 else None,
        }

        if year in season_race_ids:
            season_race_ids[year].append(race_id)

    logger.info(f"Loaded {len(races)} races, {sum(len(v) for v in season_race_ids.values())} in seasons {MIN_SEASON}-{MAX_SEASON}")
    return races, season_race_ids


def load_results() -> List[Dict[str, Any]]:
    """Load results.csv into a list of dicts.

    Each dict contains the result fields for one driver in one race.
    """
    path = DATA_DIR / "results.csv"
    header, rows = read_csv_rows(path)
    results = []
    for row in rows:
        try:
            result_id = int(row[0])
        except (ValueError, IndexError):
            logger.warning(f"Skipping result row with invalid resultId: {row}")
            continue
        results.append({
            "resultId": result_id,
            "raceId": int(row[1]) if len(row) > 1 and not is_missing(row[1]) else None,
            "driverId": int(row[2]) if len(row) > 2 and not is_missing(row[2]) else None,
            "constructorId": int(row[3]) if len(row) > 3 and not is_missing(row[3]) else None,
            "number": row[4] if len(row) > 4 else None,
            "grid": int(row[5]) if len(row) > 5 and not is_missing(row[5]) else None,
            "position": int(row[6]) if len(row) > 6 and not is_missing(row[6]) else None,
            "positionText": row[7] if len(row) > 7 else None,
            "positionOrder": row[8] if len(row) > 8 else None,
            "points": row[9] if len(row) > 9 else None,
            "laps": int(row[10]) if len(row) > 10 and not is_missing(row[10]) else None,
            "time": row[11] if len(row) > 11 else None,
            "milliseconds": int(row[12]) if len(row) > 12 and not is_missing(row[12]) else None,
            "fastestLap": int(row[13]) if len(row) > 13 and not is_missing(row[13]) else None,
            "rank": int(row[14]) if len(row) > 14 and not is_missing(row[14]) else None,
            "fastestLapTime": row[15] if len(row) > 15 else None,
            "fastestLapSpeed": row[16] if len(row) > 16 else None,
            "statusId": int(row[17]) if len(row) > 17 and not is_missing(row[17]) else None,
        })
    logger.info(f"Loaded {len(results)} results")
    return results


def load_qualifying() -> List[Dict[str, Any]]:
    """Load qualifying.csv into a list of dicts."""
    path = DATA_DIR / "qualifying.csv"
    header, rows = read_csv_rows(path)
    qualifying = []
    for row in rows:
        try:
            qualify_id = int(row[0])
        except (ValueError, IndexError):
            logger.warning(f"Skipping qualifying row with qualifyId: {row}")
            continue
        qualifying.append({
            "qualifyId": qualify_id,
            "raceId": int(row[1]) if len(row) > 1 and not is_missing(row[1]) else None,
            "driverId": int(row[2]) if len(row) > 2 and not is_missing(row[2]) else None,
            "constructorId": int(row[3]) if len(row) > 3 and not is_missing(row[3]) else None,
            "number": row[4] if len(row) > 4 else None,
            "position": int(row[5]) if len(row) > 5 and not is_missing(row[5]) else None,
            "q1": row[6] if len(row) > 6 else None,
            "q2": row[7] if len(row) > 7 else None,
            "q3": row[8] if len(row) > 8 else None,
        })
    logger.info(f"Loaded {len(qualifying)} qualifying records")
    return qualifying


def load_pit_stops() -> List[Dict[str, Any]]:
    """Load pit_stops.csv into a list of dicts."""
    path = DATA_DIR / "pit_stops.csv"
    header, rows = read_csv_rows(path)
    pit_stops = []
    for row in rows:
        try:
            race_id = int(row[0])
            driver_id = int(row[1])
            stop = int(row[2]) if len(row) > 2 and not is_missing(row[2]) else None
            lap = int(row[3]) if len(row) > 3 and not is_missing(row[3]) else None
        except (ValueError, IndexError):
            logger.warning(f"Skipping pit stop row: {row}")
            continue
        pit_stops.append({
            "raceId": race_id,
            "driverId": driver_id,
            "stop": stop,
            "lap": lap,
            "time": row[4] if len(row) > 4 else None,
            "duration": row[5] if len(row) > 5 else None,
            "milliseconds": int(row[6]) if len(row) > 6 and not is_missing(row[6]) else None,
        })
    logger.info(f"Loaded {len(pit_stops)} pit stop records")
    return pit_stops


def load_lap_times() -> List[Dict[str, Any]]:
    """Load lap_times.csv into a list of dicts.

    Note: This table can be very large (886k+ rows). Consider sampling or
    summarizing for embedding purposes.
    """
    path = DATA_DIR / "lap_times.csv"
    header, rows = read_csv_rows(path)
    lap_times = []
    for row in rows:
        try:
            race_id = int(row[0])
            driver_id = int(row[1])
            lap = int(row[2])
        except (ValueError, IndexError):
            logger.warning(f"Skipping lap time row: {row}")
            continue
        lap_times.append({
            "raceId": race_id,
            "driverId": driver_id,
            "lap": lap,
            "position": int(row[3]) if len(row) > 3 and not is_missing(row[3]) else None,
            "time": row[4] if len(row) > 4 else None,
            "milliseconds": int(row[5]) if len(row) > 5 and not is_missing(row[5]) else None,
        })
    logger.info(f"Loaded {len(lap_times)} lap time records")
    return lap_times


def load_driver_standings() -> List[Dict[str, Any]]:
    """Load driver_standings.csv into a list of dicts."""
    path = DATA_DIR / "driver_standings.csv"
    header, rows = read_csv_rows(path)
    standings = []
    for row in rows:
        try:
            standings.append({
                "driverStandingsId": int(row[0]),
                "raceId": int(row[1]) if len(row) > 1 and not is_missing(row[1]) else None,
                "driverId": int(row[2]) if len(row) > 2 and not is_missing(row[2]) else None,
                "points": row[3] if len(row) > 3 else None,
                "position": int(row[4]) if len(row) > 4 and not is_missing(row[4]) else None,
                "positionText": row[5] if len(row) > 5 else None,
                "wins": int(row[6]) if len(row) > 6 and not is_missing(row[6]) else None,
            })
        except (ValueError, IndexError):
            logger.warning(f"Skipping driver standings row: {row}")
            continue
    logger.info(f"Loaded {len(standings)} driver standing records")
    return standings


def load_constructor_standings() -> List[Dict[str, Any]]:
    """Load constructor_standings.csv into a list of dicts."""
    path = DATA_DIR / "constructor_standings.csv"
    header, rows = read_csv_rows(path)
    standings = []
    for row in rows:
        try:
            standings.append({
                "constructorStandingsId": int(row[0]),
                "raceId": int(row[1]) if len(row) > 1 and not is_missing(row[1]) else None,
                "constructorId": int(row[2]) if len(row) > 2 and not is_missing(row[2]) else None,
                "points": row[3] if len(row) > 3 else None,
                "position": int(row[4]) if len(row) > 4 and not is_missing(row[4]) else None,
                "positionText": row[5] if len(row) > 5 else None,
                "wins": int(row[6]) if len(row) > 6 and not is_missing(row[6]) else None,
            })
        except (ValueError, IndexError):
            logger.warning(f"Skipping constructor standings row: {row}")
            continue
    logger.info(f"Loaded {len(standings)} constructor standing records")
    return standings


def load_circuits() -> Dict[int, Dict[str, Any]]:
    """Load circuits.csv into a dict keyed by circuitId."""
    path = DATA_DIR / "circuits.csv"
    header, rows = read_csv_rows(path)
    circuits = {}
    for row in rows:
        try:
            circuit_id = int(row[0])
        except (ValueError, IndexError):
            logger.warning(f"Skipping circuit row with invalid circuitId: {row}")
            continue
        circuits[circuit_id] = {
            "circuitId": circuit_id,
            "circuitRef": row[1] if len(row) > 1 else None,
            "name": row[2] if len(row) > 2 else None,
            "location": row[3] if len(row) > 3 else None,
            "country": row[4] if len(row) > 4 else None,
            "lat": row[5] if len(row) > 5 else None,
            "lng": row[6] if len(row) > 6 else None,
            "alt": row[7] if len(row) > 7 else None,
            "url": row[8] if len(row) > 8 else None,
        }
    logger.info(f"Loaded {len(circuits)} circuits")
    return circuits


def get_2021_2025_race_ids(races: Dict[int, Dict[str, Any]]) -> Set[int]:
    """Get the set of raceIds belonging to the 2021-2025 seasons."""
    race_ids = set()
    for race_id, race_info in races.items():
        year = race_info.get("year")
        if year is not None and MIN_SEASON <= year <= MAX_SEASON:
            race_ids.add(race_id)
    return race_ids


def filter_results_by_race_ids(results: List[Dict[str, Any]], race_ids: Set[int]) -> List[Dict[str, Any]]:
    """Filter results to only include those belonging to the given race IDs."""
    filtered = [r for r in results if r.get("raceId") in race_ids]
    logger.info(f"Filtered {len(filtered)} results from {len(results)} total (race IDs: {sorted(race_ids)})")
    return filtered


def filter_qualifying_by_race_ids(qualifying: List[Dict[str, Any]], race_ids: Set[int]) -> List[Dict[str, Any]]:
    """Filter qualifying to only include those belonging to the given race IDs."""
    filtered = [q for q in qualifying if q.get("raceId") in race_ids]
    logger.info(f"Filtered {len(filtered)} qualifying records from {len(qualifying)} total")
    return filtered


def filter_pit_stops_by_race_ids(pit_stops: List[Dict[str, Any]], race_ids: Set[int]) -> List[Dict[str, Any]]:
    """Filter pit stops to only include those belonging to the given race IDs."""
    filtered = [p for p in pit_stops if p.get("raceId") in race_ids]
    logger.info(f"Filtered {len(filtered)} pit stops from {len(pit_stops)} total")
    return filtered


def filter_lap_times_by_race_ids(lap_times: List[Dict[str, Any]], race_ids: Set[int]) -> List[Dict[str, Any]]:
    """Filter lap times to only include those belonging to the given race IDs."""
    filtered = [l for l in lap_times if l.get("raceId") in race_ids]
    logger.info(f"Filtered {len(filtered)} lap times from {len(lap_times)} total")
    return filtered


def filter_driver_standings_by_race_ids(standings: List[Dict[str, Any]], race_ids: Set[int]) -> List[Dict[str, Any]]:
    """Filter driver standings to only include those belonging to the given race IDs."""
    filtered = [s for s in standings if s.get("raceId") in race_ids]
    logger.info(f"Filtered {len(filtered)} driver standings from {len(standings)} total")
    return filtered


def filter_constructor_standings_by_race_ids(standings: List[Dict[str, Any]], race_ids: Set[int]) -> List[Dict[str, Any]]:
    """Filter constructor standings to only include those belonging to the given race IDs."""
    filtered = [s for s in standings if s.get("raceId") in race_ids]
    logger.info(f"Filtered {len(filtered)} constructor standings from {len(standings)} total")
    return filtered