from fastapi import APIRouter

from app.dependencies import AdminUser, EditorUser

router = APIRouter(prefix="/_auth", include_in_schema=False)


@router.post("/editor-check")
async def editor_check(user: EditorUser) -> dict[str, str]:
    return {"status": "ok", "role": user.role}


@router.post("/admin-check")
async def admin_check(user: AdminUser) -> dict[str, str]:
    return {"status": "ok", "role": user.role}
