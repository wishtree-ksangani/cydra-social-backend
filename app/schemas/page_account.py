from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class PageAccountBase(BaseModel):
    """Base schema for PageAccount"""
    page_name: Optional[str] = None
    instagram_username: Optional[str] = None
    can_post_to_facebook: bool = True
    can_post_to_instagram: bool = False


class PageAccountCreate(PageAccountBase):
    """Schema for creating a PageAccount"""
    page_id: str
    page_access_token: str
    instagram_account_id: Optional[str] = None


class PageAccountUpdate(BaseModel):
    """Schema for updating a PageAccount"""
    is_selected_for_facebook: Optional[bool] = None
    is_selected_for_instagram: Optional[bool] = None
    is_active: Optional[bool] = None


class PageAccountResponse(PageAccountBase):
    """Schema for PageAccount response"""
    id: int
    social_account_id: int
    page_id: str
    instagram_account_id: Optional[str] = None
    is_selected_for_facebook: bool
    is_selected_for_instagram: bool
    is_active: bool
    last_validated_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class PageAccountSummary(BaseModel):
    """Summary of user's pages"""
    total_pages: int
    pages_with_instagram: int
    pages_without_instagram: int
    selected_facebook_page: Optional[PageAccountResponse] = None
    selected_instagram_page: Optional[PageAccountResponse] = None


class PageListResponse(BaseModel):
    """Response for listing pages"""
    pages: list[PageAccountResponse]
    summary: PageAccountSummary
