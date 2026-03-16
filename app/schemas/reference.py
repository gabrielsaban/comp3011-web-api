from __future__ import annotations

from pydantic import BaseModel

from app.schemas.accident import IdLabel


class ConditionsResponse(BaseModel):
    data: dict[str, list[IdLabel]]
