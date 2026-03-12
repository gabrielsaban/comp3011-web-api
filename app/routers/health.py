from fastapi import APIRouter
from sqlalchemy import text

from app.dependencies import DbSession

router = APIRouter(tags=["Health"])


@router.get("/health", include_in_schema=False)
async def health(db: DbSession) -> dict[str, str]:
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}
