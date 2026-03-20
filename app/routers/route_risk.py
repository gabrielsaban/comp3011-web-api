from __future__ import annotations

from fastapi import APIRouter

from app.dependencies import DbSession
from app.schemas.route_risk import (
    RouteRiskRequest,
    RouteRiskResponse,
    RouteRiskScoringModelResponse,
)
from app.services.route_risk_service import get_route_risk_scoring_model, score_route_risk

router = APIRouter(prefix="/api/v1/analytics/route-risk", tags=["Route Risk"])


@router.post("", response_model=RouteRiskResponse)
async def score_route(
    body: RouteRiskRequest,
    db: DbSession,
) -> RouteRiskResponse:
    return await score_route_risk(db, body)


@router.get("/scoring-model", response_model=RouteRiskScoringModelResponse)
async def scoring_model() -> RouteRiskScoringModelResponse:
    return get_route_risk_scoring_model()
