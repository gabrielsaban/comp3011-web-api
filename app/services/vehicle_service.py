from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.accident import Accident, Casualty, Vehicle
from app.schemas.accident import IdLabel, VehicleCreate, VehiclePatch, VehicleResponse


def _to_vehicle_response(vehicle: Vehicle) -> VehicleResponse:
    return VehicleResponse(
        vehicle_ref=vehicle.vehicle_ref,
        vehicle_type=(
            IdLabel(id=vehicle.vehicle_type_id, label=vehicle.vehicle_type.label)
            if vehicle.vehicle_type_id is not None and vehicle.vehicle_type is not None
            else None
        ),
        age_of_driver=vehicle.age_of_driver,
        sex_of_driver=vehicle.sex_of_driver,
        engine_capacity_cc=vehicle.engine_capacity_cc,
        propulsion_code=vehicle.propulsion_code,
        age_of_vehicle=vehicle.age_of_vehicle,
        journey_purpose=vehicle.journey_purpose,
    )


async def _ensure_accident_exists(session: AsyncSession, accident_id: str) -> None:
    if await session.get(Accident, accident_id) is None:
        raise HTTPException(status_code=404, detail="Accident not found.")


async def _lock_accident(session: AsyncSession, accident_id: str) -> Accident:
    locked = (
        await session.scalars(select(Accident).where(Accident.id == accident_id).with_for_update())
    ).first()
    if locked is None:
        raise HTTPException(status_code=404, detail="Accident not found.")
    return locked


async def _fetch_vehicle(
    session: AsyncSession,
    accident_id: str,
    vehicle_ref: int,
) -> Vehicle | None:
    return (
        await session.scalars(
            select(Vehicle)
            .options(joinedload(Vehicle.vehicle_type))
            .where(Vehicle.accident_id == accident_id, Vehicle.vehicle_ref == vehicle_ref)
        )
    ).first()


async def list_vehicles(session: AsyncSession, accident_id: str) -> list[VehicleResponse]:
    await _ensure_accident_exists(session, accident_id)
    vehicles = (
        await session.scalars(
            select(Vehicle)
            .options(joinedload(Vehicle.vehicle_type))
            .where(Vehicle.accident_id == accident_id)
            .order_by(Vehicle.vehicle_ref.asc())
        )
    ).all()
    return [_to_vehicle_response(vehicle) for vehicle in vehicles]


async def get_vehicle(session: AsyncSession, accident_id: str, vehicle_ref: int) -> VehicleResponse:
    await _ensure_accident_exists(session, accident_id)
    vehicle = await _fetch_vehicle(session, accident_id, vehicle_ref)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found.")
    return _to_vehicle_response(vehicle)


async def create_vehicle(
    session: AsyncSession,
    accident_id: str,
    payload: VehicleCreate,
) -> VehicleResponse:
    accident = await _lock_accident(session, accident_id)
    current_max_ref = await session.scalar(
        select(func.coalesce(func.max(Vehicle.vehicle_ref), 0)).where(
            Vehicle.accident_id == accident_id
        )
    )
    if current_max_ref is None:
        raise HTTPException(status_code=500, detail="Failed to allocate vehicle reference.")
    next_ref = current_max_ref + 1

    created = Vehicle(
        accident_id=accident_id,
        vehicle_ref=next_ref,
        **payload.model_dump(),
    )
    session.add(created)
    accident.number_of_vehicles += 1

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=422, detail="Invalid vehicle payload.") from exc

    fresh = await _fetch_vehicle(session, accident_id, next_ref)
    if fresh is None:
        raise HTTPException(status_code=500, detail="Vehicle creation failed.")
    return _to_vehicle_response(fresh)


async def patch_vehicle(
    session: AsyncSession,
    accident_id: str,
    vehicle_ref: int,
    payload: VehiclePatch,
) -> VehicleResponse:
    await _ensure_accident_exists(session, accident_id)
    vehicle = await _fetch_vehicle(session, accident_id, vehicle_ref)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found.")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(vehicle, field, value)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=422, detail="Invalid vehicle patch payload.") from exc

    refreshed = await _fetch_vehicle(session, accident_id, vehicle_ref)
    if refreshed is None:
        raise HTTPException(status_code=500, detail="Vehicle patch failed.")
    return _to_vehicle_response(refreshed)


async def delete_vehicle(session: AsyncSession, accident_id: str, vehicle_ref: int) -> None:
    await _ensure_accident_exists(session, accident_id)
    vehicle_exists = await session.scalar(
        select(Vehicle.id).where(
            Vehicle.accident_id == accident_id,
            Vehicle.vehicle_ref == vehicle_ref,
        )
    )
    if vehicle_exists is None:
        raise HTTPException(status_code=404, detail="Vehicle not found.")

    accident = await _lock_accident(session, accident_id)

    # Keep casualty rows valid before removing the referenced vehicle row.
    await session.execute(
        update(Casualty)
        .where(Casualty.accident_id == accident_id, Casualty.vehicle_ref == vehicle_ref)
        .values(vehicle_ref=None)
    )
    deleted_id = await session.scalar(
        delete(Vehicle)
        .where(
            Vehicle.accident_id == accident_id,
            Vehicle.vehicle_ref == vehicle_ref,
        )
        .returning(Vehicle.id)
    )
    if deleted_id is None:
        raise HTTPException(status_code=404, detail="Vehicle not found.")

    accident.number_of_vehicles = max(accident.number_of_vehicles - 1, 0)
    await session.commit()
