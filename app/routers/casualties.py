from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Response, status

from app.dependencies import AdminUser, DbSession, EditorUser
from app.schemas.accident import (
    CasualtyCollectionResponse,
    CasualtyCreate,
    CasualtyItemResponse,
    CasualtyPatch,
)
from app.services.casualty_service import (
    create_casualty,
    delete_casualty,
    get_casualty,
    list_casualties,
    patch_casualty,
)

router = APIRouter(prefix="/api/v1/accidents/{accident_id}/casualties", tags=["Casualties"])
CasualtyRef = Annotated[int, Path(ge=1)]


@router.get("", response_model=CasualtyCollectionResponse)
async def get_casualties(accident_id: str, db: DbSession) -> CasualtyCollectionResponse:
    return CasualtyCollectionResponse(data=await list_casualties(db, accident_id))


@router.get("/{casualty_ref}", response_model=CasualtyItemResponse)
async def get_casualty_by_ref(
    accident_id: str,
    casualty_ref: CasualtyRef,
    db: DbSession,
) -> CasualtyItemResponse:
    return CasualtyItemResponse(data=await get_casualty(db, accident_id, casualty_ref))


@router.post("", response_model=CasualtyItemResponse, status_code=status.HTTP_201_CREATED)
async def post_casualty(
    accident_id: str,
    body: CasualtyCreate,
    db: DbSession,
    user: EditorUser,
) -> CasualtyItemResponse:
    return CasualtyItemResponse(data=await create_casualty(db, accident_id, body))


@router.patch("/{casualty_ref}", response_model=CasualtyItemResponse)
async def patch_casualty_by_ref(
    accident_id: str,
    body: CasualtyPatch,
    casualty_ref: CasualtyRef,
    db: DbSession,
    user: EditorUser,
) -> CasualtyItemResponse:
    return CasualtyItemResponse(data=await patch_casualty(db, accident_id, casualty_ref, body))


@router.delete("/{casualty_ref}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_casualty_by_ref(
    accident_id: str,
    casualty_ref: CasualtyRef,
    db: DbSession,
    user: AdminUser,
) -> Response:
    await delete_casualty(db, accident_id, casualty_ref)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
