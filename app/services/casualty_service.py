from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.age_band import derive_age_band
from app.models.accident import Accident, Casualty, Vehicle
from app.schemas.accident import CasualtyCreate, CasualtyPatch, CasualtyResponse, IdLabel


def _to_casualty_response(casualty: Casualty) -> CasualtyResponse:
    return CasualtyResponse(
        casualty_ref=casualty.casualty_ref,
        vehicle_ref=casualty.vehicle_ref,
        severity=IdLabel(id=casualty.severity_id, label=casualty.severity.label),
        casualty_class=casualty.casualty_class,
        casualty_type=casualty.casualty_type,
        sex=casualty.sex,
        age=casualty.age,
        age_band=casualty.age_band,
    )


def _invalid_vehicle_ref_error() -> HTTPException:
    return HTTPException(
        status_code=422,
        detail=[
            {
                "loc": ["body", "vehicle_ref"],
                "msg": "vehicle_ref must reference a vehicle in this accident.",
                "type": "value_error",
            }
        ],
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


async def _validate_vehicle_ref(
    session: AsyncSession,
    accident_id: str,
    vehicle_ref: int | None,
) -> None:
    if vehicle_ref is None:
        return
    vehicle_exists = await session.scalar(
        select(Vehicle.id).where(
            Vehicle.accident_id == accident_id,
            Vehicle.vehicle_ref == vehicle_ref,
        )
    )
    if vehicle_exists is None:
        raise _invalid_vehicle_ref_error()


async def _fetch_casualty(
    session: AsyncSession,
    accident_id: str,
    casualty_ref: int,
) -> Casualty | None:
    return (
        await session.scalars(
            select(Casualty)
            .options(joinedload(Casualty.severity))
            .where(Casualty.accident_id == accident_id, Casualty.casualty_ref == casualty_ref)
        )
    ).first()


async def list_casualties(session: AsyncSession, accident_id: str) -> list[CasualtyResponse]:
    await _ensure_accident_exists(session, accident_id)
    casualties = (
        await session.scalars(
            select(Casualty)
            .options(joinedload(Casualty.severity))
            .where(Casualty.accident_id == accident_id)
            .order_by(Casualty.casualty_ref.asc())
        )
    ).all()
    return [_to_casualty_response(casualty) for casualty in casualties]


async def get_casualty(
    session: AsyncSession,
    accident_id: str,
    casualty_ref: int,
) -> CasualtyResponse:
    await _ensure_accident_exists(session, accident_id)
    casualty = await _fetch_casualty(session, accident_id, casualty_ref)
    if casualty is None:
        raise HTTPException(status_code=404, detail="Casualty not found.")
    return _to_casualty_response(casualty)


async def create_casualty(
    session: AsyncSession,
    accident_id: str,
    payload: CasualtyCreate,
) -> CasualtyResponse:
    accident = await _lock_accident(session, accident_id)
    await _validate_vehicle_ref(session, accident_id, payload.vehicle_ref)

    current_max_ref = await session.scalar(
        select(func.coalesce(func.max(Casualty.casualty_ref), 0)).where(
            Casualty.accident_id == accident_id
        )
    )
    if current_max_ref is None:
        raise HTTPException(status_code=500, detail="Failed to allocate casualty reference.")
    next_ref = current_max_ref + 1

    created = Casualty(
        accident_id=accident_id,
        casualty_ref=next_ref,
        age_band=derive_age_band(payload.age),
        **payload.model_dump(),
    )
    session.add(created)
    accident.number_of_casualties += 1

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=422, detail="Invalid casualty payload.") from exc

    fresh = await _fetch_casualty(session, accident_id, next_ref)
    if fresh is None:
        raise HTTPException(status_code=500, detail="Casualty creation failed.")
    return _to_casualty_response(fresh)


async def patch_casualty(
    session: AsyncSession,
    accident_id: str,
    casualty_ref: int,
    payload: CasualtyPatch,
) -> CasualtyResponse:
    await _ensure_accident_exists(session, accident_id)
    casualty = await _fetch_casualty(session, accident_id, casualty_ref)
    if casualty is None:
        raise HTTPException(status_code=404, detail="Casualty not found.")

    updates = payload.model_dump(exclude_unset=True)
    if "vehicle_ref" in updates:
        await _validate_vehicle_ref(session, accident_id, updates["vehicle_ref"])
    if "age" in updates:
        updates["age_band"] = derive_age_band(updates["age"])

    for field, value in updates.items():
        setattr(casualty, field, value)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=422, detail="Invalid casualty patch payload.") from exc

    refreshed = await _fetch_casualty(session, accident_id, casualty_ref)
    if refreshed is None:
        raise HTTPException(status_code=500, detail="Casualty patch failed.")
    return _to_casualty_response(refreshed)


async def delete_casualty(session: AsyncSession, accident_id: str, casualty_ref: int) -> None:
    await _ensure_accident_exists(session, accident_id)
    casualty_exists = await session.scalar(
        select(Casualty.id).where(
            Casualty.accident_id == accident_id,
            Casualty.casualty_ref == casualty_ref,
        )
    )
    if casualty_exists is None:
        raise HTTPException(status_code=404, detail="Casualty not found.")

    accident = await _lock_accident(session, accident_id)
    deleted_id = await session.scalar(
        delete(Casualty)
        .where(
            Casualty.accident_id == accident_id,
            Casualty.casualty_ref == casualty_ref,
        )
        .returning(Casualty.id)
    )
    if deleted_id is None:
        raise HTTPException(status_code=404, detail="Casualty not found.")

    accident.number_of_casualties = max(accident.number_of_casualties - 1, 0)
    await session.commit()
