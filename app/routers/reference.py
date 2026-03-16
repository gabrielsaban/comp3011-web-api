from __future__ import annotations

from fastapi import APIRouter, Query

from app.dependencies import DbSession
from app.schemas.reference import ConditionsResponse
from app.services.reference_service import list_reference_conditions

router = APIRouter(prefix="/api/v1/reference", tags=["Reference"])


@router.get("/conditions", response_model=ConditionsResponse)
async def get_reference_conditions(
    db: DbSession,
    condition_type: str | None = Query(default=None, alias="type"),
) -> ConditionsResponse:
    return ConditionsResponse(data=await list_reference_conditions(db, condition_type))
