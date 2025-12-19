"""Posts endpoints - Create and manage social media posts"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.api.dependencies.auth import get_current_user
from app.models.user import User
from app.services.posting import (
    PostingValidator,
    FacebookPostingService,
    InstagramPostingService
)

router = APIRouter()


class CreatePostRequest(BaseModel):
    """Request schema for creating a post"""
    page_account_id: int
    platform: str  # "facebook" or "instagram"
    content: Optional[str] = None
    image_url: Optional[str] = None


class CreatePostResponse(BaseModel):
    """Response schema for created post"""
    success: bool
    post_id: str
    platform: str
    platform_url: str
    page_name: str


@router.post("/create", response_model=CreatePostResponse)
async def create_post(
    request: CreatePostRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a post on Facebook or Instagram.
    
    - **page_account_id**: ID of the page to post to
    - **platform**: "facebook" or "instagram"
    - **content**: Post content/caption
    - **image_url**: Image URL (required for Instagram, optional for Facebook)
    """
    # Validate platform
    if request.platform not in ["facebook", "instagram"]:
        raise HTTPException(
            status_code=400,
            detail="Platform must be 'facebook' or 'instagram'"
        )
    
    # Validate request
    page_account, page_token = await PostingValidator.validate_post_request(
        db=db,
        user_id=current_user.id,
        page_account_id=request.page_account_id,
        platform=request.platform,
        content=request.content,
        image_url=request.image_url
    )
    
    try:
        if request.platform == "facebook":
            # Post to Facebook
            result = await FacebookPostingService.post_to_page(
                page_id=page_account.page_id,
                page_access_token=page_token,
                message=request.content or "",
                image_url=request.image_url
            )
        else:  # instagram
            # Post to Instagram
            result = await InstagramPostingService.post_image(
                instagram_account_id=page_account.instagram_account_id,
                page_access_token=page_token,
                image_url=request.image_url,
                caption=request.content or ""
            )
        
        return CreatePostResponse(
            success=True,
            post_id=result["post_id"],
            platform=request.platform,
            platform_url=result["platform_url"],
            page_name=page_account.page_name
        )
        
    except Exception as e:
        # Log the error
        import traceback
        print(f"Error posting to {request.platform}:")
        print(f"Error: {str(e)}")
        print(traceback.format_exc())
        
        # Return user-friendly error
        error_message = str(e)
        
        if "HTTPStatusError" in str(type(e)):
            if "400" in str(e):
                error_message = f"Invalid request to {request.platform}. Please check your content and try again."
            elif "403" in str(e):
                error_message = f"Permission denied by {request.platform}. Please reconnect your account with required permissions."
            elif "429" in str(e):
                error_message = f"Rate limit exceeded. Please try again later."
            else:
                error_message = f"{request.platform} API error: {str(e)}"
        
        raise HTTPException(
            status_code=500,
            detail=error_message
        )
