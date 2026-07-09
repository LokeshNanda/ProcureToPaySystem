import uuid

from pydantic import BaseModel, ConfigDict, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    role_names: list[str] = []


class RoleAssign(BaseModel):
    role_names: list[str]


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: EmailStr
    full_name: str
    is_active: bool
    roles: list[RoleOut]


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int


class UserPage(BaseModel):
    data: list[UserOut]
    meta: PageMeta
