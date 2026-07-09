import uuid

from pydantic import BaseModel, ConfigDict

from app.modules.users.schemas import PageMeta


class CostCenterCreate(BaseModel):
    code: str
    name: str
    owner_id: uuid.UUID | None = None


class CostCenterUpdate(BaseModel):
    name: str | None = None
    owner_id: uuid.UUID | None = None  # note: null clears the owner


class CostCenterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str
    owner_id: uuid.UUID | None
    is_active: bool


class CostCenterPage(BaseModel):
    data: list[CostCenterOut]
    meta: PageMeta


class GLAccountCreate(BaseModel):
    code: str
    name: str


class GLAccountUpdate(BaseModel):
    name: str | None = None


class GLAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str
    is_active: bool


class GLAccountPage(BaseModel):
    data: list[GLAccountOut]
    meta: PageMeta


class RowError(BaseModel):
    row: int
    code: str | None = None
    reason: str


class ImportResult(BaseModel):
    created: int
    updated: int
    errors: list[RowError]
