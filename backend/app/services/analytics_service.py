"""Analytics service for the F1 Performance Analytics Platform.

Loads the existing CSV dataset once and exposes read-only helpers used by the
dashboard, race explorer and driver comparison endpoints. All computation stays
on the backend; the frontend only receives JSON.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from ..core.config import DATA_DIR

logger = logging.getLogger("f1rag.analytics")

# Tables needed by the API. lap_times/pit_stops/qualifying are large and are not
# used by the current endpoints, so they are not loaded eagerly.
_CSV_TABLES = [
    "races",
    "results",
    "drivers",
    "constructors",
    "driver_standings",
    "constructor_standings",
    "status",
    "circuits",
]

_cached_dfs: Dict[str, pd.DataFrame] = {}
_loaded = False
_merged_results: Optional[pd.DataFrame] = None


def _snake_case(name: str) -> str:
    """Convert camelCase CSV headers (raceId) to snake_case (race_id)."""
    name = name.strip().replace(" ", "_")
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    name = re.sub(r"[^0-9A-Za-z_]+", "_", name)
    return name.lower().strip("_")


def _ensure_data_loaded() -> None:
    global _loaded

    if _loaded:
        return

    for table in _CSV_TABLES:
        path = DATA_DIR / f"{table}.csv"
        if not path.exists():
            logger.warning("Dataset file not found: %s", path)
            continue
        try:
            frame = pd.read_csv(path, dtype=str)
            frame.columns = [_snake_case(column) for column in frame.columns]
            _cached_dfs[table] = frame
            logger.info("Loaded %s (%d rows)", path.name, len(frame))
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Could not load %s: %s", path, exc)

    _loaded = True


def _get_df(name: str) -> Optional[pd.DataFrame]:
    """Return a cached DataFrame by table name (without the .csv suffix)."""
    _ensure_data_loaded()
    return _cached_dfs.get(name)


def _clean(value: Any) -> str:
    """Return a display-safe string for a pandas value."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if text in {"nan", "None", "<NA>", "\\N"}:
        return ""
    return text


def _to_int(value: Any) -> Optional[int]:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number


def _driver_names() -> Dict[str, str]:
    drivers = _get_df("drivers")
    if drivers is None:
        return {}
    names = {}
    for _, row in drivers.iterrows():
        name = f"{_clean(row.get('forename'))} {_clean(row.get('surname'))}".strip()
        names[_clean(row.get("driver_id"))] = name
    return names


def _constructor_names() -> Dict[str, str]:
    constructors = _get_df("constructors")
    if constructors is None:
        return {}
    return {
        _clean(row.get("constructor_id")): _clean(row.get("name"))
        for _, row in constructors.iterrows()
    }


def _status_names() -> Dict[str, str]:
    status = _get_df("status")
    if status is None:
        return {}
    return {
        _clean(row.get("status_id")): _clean(row.get("status"))
        for _, row in status.iterrows()
    }


def _results_with_races() -> Optional[pd.DataFrame]:
    """Results joined with race metadata (season, race name, round)."""
    global _merged_results

    if _merged_results is not None:
        return _merged_results

    results = _get_df("results")
    races = _get_df("races")
    if results is None or races is None:
        return None

    race_columns = [
        column
        for column in ("race_id", "year", "round", "name", "date")
        if column in races.columns
    ]
    merged = results.merge(
        races[race_columns],
        on="race_id",
        how="left",
        suffixes=("", "_race"),
    )
    _merged_results = merged
    return merged


def _season_frame(season: int) -> Optional[pd.DataFrame]:
    merged = _results_with_races()
    if merged is None or "year" not in merged.columns:
        return None
    return merged[merged["year"].astype(str) == str(season)]


def get_seasons_available() -> List[int]:
    """Return the seasons present in the dataset (2021-2025)."""
    races = _get_df("races")
    if races is None or "year" not in races.columns:
        return []

    seasons = set()
    for value in races["year"].dropna().unique():
        year = _to_int(value)
        if year is not None and 2021 <= year <= 2025:
            seasons.add(year)
    return sorted(seasons)


def get_races_by_season(season: int) -> List[Dict[str, Any]]:
    """Return all races for a season, ordered by round."""
    races = _get_df("races")
    if races is None:
        return []

    season_races = races[races["year"].astype(str) == str(season)].copy()
    if season_races.empty:
        return []

    season_races["_round"] = pd.to_numeric(season_races.get("round"), errors="coerce")
    season_races = season_races.sort_values("_round", na_position="last")

    return [
        {
            "race_id": _clean(row.get("race_id")),
            "race_name": _clean(row.get("name")),
            "circuit": _clean(row.get("circuit_id")),
            "date": _clean(row.get("date")),
            "round": _clean(row.get("round")),
            "season": _to_int(row.get("year")),
        }
        for _, row in season_races.iterrows()
    ]


def get_results_for_race(race_id: str) -> List[Dict[str, Any]]:
    """Return the full classification for one race."""
    merged = _results_with_races()
    if merged is None:
        return []

    race_results = merged[merged["race_id"].astype(str) == str(race_id)].copy()
    if race_results.empty:
        return []

    drivers = _driver_names()
    constructors = _constructor_names()
    statuses = _status_names()

    race_results["_position_order"] = pd.to_numeric(
        race_results.get("position_order"), errors="coerce"
    )
    race_results = race_results.sort_values("_position_order", na_position="last")

    results = []
    for _, row in race_results.iterrows():
        driver_id = _clean(row.get("driver_id"))
        constructor_id = _clean(row.get("constructor_id"))
        status_id = _clean(row.get("status_id"))
        results.append(
            {
                "position": _clean(row.get("position")),
                "position_text": _clean(row.get("position_text")),
                "points": _clean(row.get("points")),
                "grid": _clean(row.get("grid")),
                "laps": _clean(row.get("laps")),
                "driver_id": driver_id,
                "driver_name": drivers.get(driver_id, ""),
                "constructor_id": constructor_id,
                "constructor_name": constructors.get(constructor_id, ""),
                "time": _clean(row.get("time")),
                "status": statuses.get(status_id, ""),
            }
        )
    return results


def _final_standings(table: str, season: int) -> Optional[pd.DataFrame]:
    """Return the final standings snapshot (last race of the season)."""
    standings = _get_df(table)
    races = _get_df("races")
    if standings is None or races is None:
        return None

    season_races = races[races["year"].astype(str) == str(season)].copy()
    if season_races.empty:
        return None

    season_races["_round"] = pd.to_numeric(season_races.get("round"), errors="coerce")
    season_races = season_races.sort_values("_round", na_position="last")
    last_race_id = _clean(season_races.iloc[-1].get("race_id"))

    rows = standings[standings["race_id"].astype(str) == last_race_id].copy()
    if rows.empty:
        return None

    rows["_position"] = pd.to_numeric(rows.get("position"), errors="coerce")
    return rows.sort_values("_position", na_position="last")


def get_driver_standings(season: int) -> List[Dict[str, Any]]:
    """Return the final driver championship standings for a season."""
    rows = _final_standings("driver_standings", season)
    if rows is None:
        return []

    names = _driver_names()
    standings = []
    for _, row in rows.iterrows():
        driver_id = _clean(row.get("driver_id"))
        standings.append(
            {
                "position": _clean(row.get("position")),
                "points": _clean(row.get("points")),
                "wins": _clean(row.get("wins")),
                "driver_id": driver_id,
                "driver_name": names.get(driver_id, ""),
            }
        )
    return standings


def get_constructor_standings(season: int) -> List[Dict[str, Any]]:
    """Return the final constructor championship standings for a season."""
    rows = _final_standings("constructor_standings", season)
    if rows is None:
        return []

    names = _constructor_names()
    standings = []
    for _, row in rows.iterrows():
        constructor_id = _clean(row.get("constructor_id"))
        standings.append(
            {
                "position": _clean(row.get("position")),
                "points": _clean(row.get("points")),
                "wins": _clean(row.get("wins")),
                "constructor_id": constructor_id,
                "constructor_name": names.get(constructor_id, ""),
            }
        )
    return standings


def get_results_for_all_drivers(
    driver_id: Optional[str] = None, season: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Return results, optionally filtered by driver and/or season."""
    merged = _results_with_races()
    if merged is None:
        return []

    filtered = merged
    if season is not None:
        filtered = filtered[filtered["year"].astype(str) == str(season)]
    if driver_id is not None:
        filtered = filtered[filtered["driver_id"].astype(str) == str(driver_id)]

    filtered = filtered.copy()
    filtered["_position_order"] = pd.to_numeric(
        filtered.get("position_order"), errors="coerce"
    )
    filtered = filtered.sort_values("_position_order", na_position="last")

    return [
        {
            "race_id": _clean(row.get("race_id")),
            "race_name": _clean(row.get("name")),
            "season": _to_int(row.get("year")),
            "position": _clean(row.get("position")),
            "points": _clean(row.get("points")),
            "grid": _clean(row.get("grid")),
            "laps": _clean(row.get("laps")),
            "driver_id": _clean(row.get("driver_id")),
            "constructor_id": _clean(row.get("constructor_id")),
        }
        for _, row in filtered.iterrows()
    ]


def get_results_for_constructor(
    constructor_id: Optional[str] = None, season: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Return results, optionally filtered by constructor and/or season."""
    merged = _results_with_races()
    if merged is None:
        return []

    filtered = merged
    if season is not None:
        filtered = filtered[filtered["year"].astype(str) == str(season)]
    if constructor_id is not None:
        filtered = filtered[
            filtered["constructor_id"].astype(str) == str(constructor_id)
        ]

    filtered = filtered.copy()
    filtered["_position_order"] = pd.to_numeric(
        filtered.get("position_order"), errors="coerce"
    )
    filtered = filtered.sort_values("_position_order", na_position="last")

    return [
        {
            "race_id": _clean(row.get("race_id")),
            "race_name": _clean(row.get("name")),
            "season": _to_int(row.get("year")),
            "position": _clean(row.get("position")),
            "points": _clean(row.get("points")),
            "grid": _clean(row.get("grid")),
        }
        for _, row in filtered.iterrows()
    ]


def _aggregate_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_races = len(results)
    wins = 0
    podiums = 0
    points_total = 0.0
    positions: List[float] = []

    for result in results:
        position = _to_int(result.get("position"))
        if position is not None:
            positions.append(float(position))
            if position == 1:
                wins += 1
            if position <= 3:
                podiums += 1
        try:
            points_total += float(result.get("points") or 0)
        except (TypeError, ValueError):
            pass

    return {
        "total_races": total_races,
        "wins": wins,
        "podiums": podiums,
        "points_total": round(points_total, 2),
        "average_position": round(sum(positions) / len(positions), 2)
        if positions
        else 0,
    }


def get_driver_stats(
    driver_id: str, season: Optional[int] = None
) -> Dict[str, Any]:
    """Return aggregate statistics for a driver id."""
    results = get_results_for_all_drivers(driver_id=driver_id, season=season)
    if not results:
        return {}

    stats = _aggregate_results(results)
    stats["driver_id"] = str(driver_id)
    stats["driver_name"] = _driver_names().get(str(driver_id), "")
    return stats


def get_constructor_stats(
    constructor_id: str, season: Optional[int] = None
) -> Dict[str, Any]:
    """Return aggregate statistics for a constructor id."""
    results = get_results_for_constructor(constructor_id=constructor_id, season=season)
    if not results:
        return {}

    stats = _aggregate_results(results)
    stats["constructor_id"] = str(constructor_id)
    stats["constructor_name"] = _constructor_names().get(str(constructor_id), "")
    return stats
