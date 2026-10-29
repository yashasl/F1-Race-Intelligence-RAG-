"""Driver and constructor endpoints for the F1 Performance Analytics Platform."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from ..services.analytics_service import (
    _get_df,
    get_constructor_stats,
    get_driver_stats,
    get_seasons_available,
)

router = APIRouter(prefix="/api", tags=["drivers_constructors"])


@router.get("/drivers", response_model=List[Dict[str, Any]])
async def list_drivers() -> List[Dict[str, Any]]:
    drivers_df = _get_df("drivers")
    if drivers_df is None:
        raise HTTPException(status_code=503, detail="Drivers data is not available")

    drivers = []
    for _, row in drivers_df.iterrows():
        forename = str(row.get("forename") or "").strip()
        surname = str(row.get("surname") or "").strip()
        drivers.append(
            {
                "driver_id": str(row.get("driver_id") or ""),
                "driver_name": f"{forename} {surname}".strip(),
                "driver_ref": str(row.get("driver_ref") or ""),
                "nationality": str(row.get("nationality") or ""),
                "number": str(row.get("number") or ""),
            }
        )
    return drivers


@router.get("/drivers/{driver_id}", response_model=Dict[str, Any])
async def driver_detail(
    driver_id: str,
    season: Optional[int] = Query(None, ge=2021, le=2025),
) -> Dict[str, Any]:
    stats = get_driver_stats(driver_id, season=season)
    if not stats:
        raise HTTPException(
            status_code=404, detail=f"Driver statistics not found for ID {driver_id}"
        )
    return stats


@router.get("/constructors", response_model=List[Dict[str, Any]])
async def list_constructors() -> List[Dict[str, Any]]:
    constructors_df = _get_df("constructors")
    if constructors_df is None:
        raise HTTPException(status_code=503, detail="Constructors data is not available")

    constructors = []
    for _, row in constructors_df.iterrows():
        constructors.append(
            {
                "constructor_id": str(row.get("constructor_id") or ""),
                "constructor_name": str(row.get("name") or ""),
                "constructor_ref": str(row.get("constructor_ref") or ""),
                "nationality": str(row.get("nationality") or ""),
            }
        )
    return constructors


@router.get("/constructors/{constructor_id}", response_model=Dict[str, Any])
async def constructor_detail(
    constructor_id: str,
    season: Optional[int] = Query(None, ge=2021, le=2025),
) -> Dict[str, Any]:
    stats = get_constructor_stats(constructor_id, season=season)
    if not stats:
        raise HTTPException(
            status_code=404,
            detail=f"Constructor statistics not found for ID {constructor_id}",
        )
    return stats


@router.get("/seasons", response_model=List[int])
async def api_seasons() -> List[int]:
    seasons = get_seasons_available()
    if not seasons:
        raise HTTPException(status_code=503, detail="Season data is not available")
    return seasons
