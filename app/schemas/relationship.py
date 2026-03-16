from __future__ import annotations

from pydantic import BaseModel

from app.schemas.accident import AccidentListItem, MetaPagination, NamedRef


class RegionSummary(BaseModel):
    id: int
    name: str
    local_authority_count: int


class RegionCollectionResponse(BaseModel):
    data: list[RegionSummary]


class RegionItemResponse(BaseModel):
    data: RegionSummary


class RegionContext(BaseModel):
    id: int
    name: str


class LocalAuthorityContext(BaseModel):
    id: int
    name: str
    region: RegionContext


class RegionLocalAuthorityCollectionResponse(BaseModel):
    context: RegionContext
    data: list[NamedRef]


class LocalAuthorityAccidentCollectionResponse(BaseModel):
    context: LocalAuthorityContext
    data: list[AccidentListItem]
    meta: MetaPagination
