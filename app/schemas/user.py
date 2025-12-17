from pydantic import BaseModel, EmailStr, Field, field_validator
from app.schemas.workspace import WorkspaceResponse

class UserBase(BaseModel):
    email: EmailStr
    full_name: str | None = None

class UserCreate(UserBase):
    password: str = Field(min_length=8)
    confirm_password: str = Field(min_length=8)

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info):
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("passwords do not match")
        return v

class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = None

class UserResponse(UserBase):
    id: int
    is_active: bool
    workspace: WorkspaceResponse | None = None

    class Config:
        from_attributes = True
