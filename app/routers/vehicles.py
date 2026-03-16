from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Response, status

from app.dependencies import AdminUser, DbSession, EditorUser
from app.schemas.accident import (
    VehicleCollectionResponse,
    VehicleCreate,
    VehicleItemResponse,
    VehiclePatch,
)
from app.services.vehicle_service import (
    create_vehicle,
    delete_vehicle,
    get_vehicle,
    list_vehicles,
    patch_vehicle,
)

router = APIRouter(prefix="/api/v1/accidents/{accident_id}/vehicles", tags=["Vehicles"])
VehicleRef = Annotated[int, Path(ge=1)]


@router.get("", response_model=VehicleCollectionResponse)
async def get_vehicles(accident_id: str, db: DbSession) -> VehicleCollectionResponse:
    return VehicleCollectionResponse(data=await list_vehicles(db, accident_id))


@router.get("/{vehicle_ref}", response_model=VehicleItemResponse)
async def get_vehicle_by_ref(
    accident_id: str,
    vehicle_ref: VehicleRef,
    db: DbSession,
) -> VehicleItemResponse:
    return VehicleItemResponse(data=await get_vehicle(db, accident_id, vehicle_ref))


@router.post("", response_model=VehicleItemResponse, status_code=status.HTTP_201_CREATED)
async def post_vehicle(
    accident_id: str,
    body: VehicleCreate,
    db: DbSession,
    user: EditorUser,
) -> VehicleItemResponse:
    return VehicleItemResponse(data=await create_vehicle(db, accident_id, body))


@router.patch("/{vehicle_ref}", response_model=VehicleItemResponse)
async def patch_vehicle_by_ref(
    accident_id: str,
    body: VehiclePatch,
    vehicle_ref: VehicleRef,
    db: DbSession,
    user: EditorUser,
) -> VehicleItemResponse:
    return VehicleItemResponse(data=await patch_vehicle(db, accident_id, vehicle_ref, body))


@router.delete("/{vehicle_ref}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vehicle_by_ref(
    accident_id: str,
    vehicle_ref: VehicleRef,
    db: DbSession,
    user: AdminUser,
) -> Response:
    await delete_vehicle(db, accident_id, vehicle_ref)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
