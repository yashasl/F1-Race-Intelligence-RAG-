"""Dashboard, race and season endpoints for the F1 Performance Analytics Platform."""

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query

from ..services.analytics_service import (
    get_constructor_standings,
    get_driver_standings,
    get_races_by_season,
    get_results_for_all_drivers,
    get_results_for_race,
    get_seasons_available,
)

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/health")
async def health_check() -> Dict[str, str]:
    return {"status": "healthy", "service": "F1 Performance Analytics API"}


@router.get("/seasons", response_model=List[int])
async def get_seasons() -> List[int]:
    seasons = get_seasons_available()
    if not seasons:
        raise HTTPException(status_code=503, detail="Season data is not available")
    return seasons


@router.get("/dashboard", response_model=Dict[str, Any])
async def dashboard_data(
    season: int = Query(2021, ge=2021, le=2025, description="F1 season year"),
) -> Dict[str, Any]:
    available_seasons = get_seasons_available()
    if season not in available_seasons:
        raise HTTPException(
            status_code=400,
            detail=f"Season {season} not available. Available: {available_seasons}",
        )

    races = get_races_by_season(season)
    season_results = get_results_for_all_drivers(season=season)

    race_winners = []
    for race in races:
        results = get_results_for_race(race["race_id"])
        winner = next(
            (result for result in results if str(result.get("position")) == "1"),
            None,
        )
        if winner:
            race_winners.append(
                {
                    "race_id": race["race_id"],
                    "race_name": race["race_name"],
                    "round": race.get("round", ""),
                    "winner": winner.get("driver_name", ""),
                    "winner_constructor": winner.get("constructor_name", ""),
                }
            )

    driver_standings = get_driver_standings(season)
    constructor_standings = get_constructor_standings(season)
    driver_ids = {
        result.get("driver_id")
        for result in season_results
        if result.get("driver_id")
    }

    return {
        "season": season,
        "total_races": len(races),
        "available_drivers": len(driver_ids),
        "total_race_results": len(season_results),
        "race_winners": race_winners,
        "driver_championship_standings": driver_standings,
        "constructor_championship_standings": constructor_standings,
        "top_three_drivers": driver_standings[:3],
    }


@router.get("/races", response_model=List[Dict[str, Any]])
async def list_races(
    season: int = Query(..., ge=2021, le=2025, description="F1 season year"),
) -> List[Dict[str, Any]]:
    available_seasons = get_seasons_available()
    if season not in available_seasons:
        raise HTTPException(
            status_code=400,
            detail=f"Season {season} not available. Available: {available_seasons}",
        )

    races = get_races_by_season(season)
    if not races:
        raise HTTPException(status_code=404, detail=f"No races found for season {season}")
    return races


@router.get("/races/{race_id}", response_model=Dict[str, Any])
async def race_detail(race_id: str) -> Dict[str, Any]:
    results = get_results_for_race(race_id)
    if not results:
        raise HTTPException(status_code=404, detail=f"No results found for race {race_id}")

    season = None
    for race in get_seasons_available():
        if any(
            race_item["race_id"] == str(race_id)
            for race_item in get_races_by_season(race)
        ):
            season = race
            break

    race_name = ""
    if season is not None:
        race_name = next(
            (
                race["race_name"]
                for race in get_races_by_season(season)
                if race["race_id"] == str(race_id)
            ),
            "",
        )

    return {
        "race_id": str(race_id),
        "race_name": race_name,
        "season": season,
        "results": results,
        "result_count": len(results),
    }
