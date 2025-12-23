from pydantic import BaseModel
from datetime import datetime


class SocialAccountBase(BaseModel):
    platform: str
    platform_username: str | None = None


class SocialAccountResponse(SocialAccountBase):
    id: int
    platform_user_id: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class OAuthInitiateResponse(BaseModel):
    authorization_url: str
    state: str


class OAuthCallbackRequest(BaseModel):
    code: str
    state: str
