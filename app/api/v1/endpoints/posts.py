"""Posts endpoints - Create and manage social media posts"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List

from app.core.database import get_db
from app.api.dependencies.auth import get_current_user
from app.core.encryption import decrypt_token
from app.models.user import User
from app.models.social_account import SocialAccount
from app.models.page_account import PageAccount
from app.services.posting import (
    FacebookPostingService,
    InstagramPostingService,
    TwitterPostingService,
    LinkedInPostingService
)

router = APIRouter()


class CreatePostRequest(BaseModel):
    """Request schema for creating a post"""
    platform: str  # "facebook", "instagram", "twitter", or "linkedin"
    content: Optional[str] = None
    
    # For Facebook/Instagram (uses page accounts)
    page_account_id: Optional[int] = None
    
    # For Twitter/LinkedIn (uses social accounts directly)
    social_account_id: Optional[int] = None
    
    # Media
    image_url: Optional[str] = None  # Single image for Facebook/Instagram/LinkedIn
    image_urls: Optional[List[str]] = None  # Multiple images for Twitter (max 4)


class CreatePostResponse(BaseModel):
    """Response schema for created post"""
    success: bool
    post_id: str
    platform: str
    platform_url: str
    account_name: str


@router.post("/create", response_model=CreatePostResponse)
async def create_post(
    request: CreatePostRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a post on any supported platform.
    
    **Platforms**: facebook, instagram, twitter, linkedin
    
    **For Facebook/Instagram**:
    - Use `page_account_id`
    - `image_url` for single image
    
    **For Twitter**:
    - Use `social_account_id`
    - `image_urls` for multiple images (max 4)
    - Max 280 characters
    
    **For LinkedIn**:
    - Use `social_account_id`
    - `image_url` for single image
    - Max 3000 characters
    """
    # Validate platform
    if request.platform not in ["facebook", "instagram", "twitter", "linkedin"]:
        raise HTTPException(
            status_code=400,
            detail="Platform must be 'facebook', 'instagram', 'twitter', or 'linkedin'"
        )
    
    try:
        if request.platform in ["facebook", "instagram"]:
            # Facebook/Instagram use page accounts
            if not request.page_account_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"{request.platform} requires page_account_id"
                )
            
            # Get page account
            result = await db.execute(
                select(PageAccount).where(PageAccount.id == request.page_account_id)
            )
            page_account = result.scalars().first()
            
            if not page_account:
                raise HTTPException(status_code=404, detail="Page not found")
            
            # Verify ownership
            result = await db.execute(
                select(SocialAccount).where(
                    SocialAccount.id == page_account.social_account_id,
                    SocialAccount.user_id == current_user.id
                )
            )
            if not result.scalars().first():
                raise HTTPException(status_code=403, detail="Access denied")
            
            # Decrypt token
            page_token = decrypt_token(page_account.page_access_token)
            
            # Post
            if request.platform == "facebook":
                result = await FacebookPostingService.post_to_page(
                    page_id=page_account.page_id,
                    page_access_token=page_token,
                    message=request.content or "",
                    image_url=request.image_url
                )
            else:  # instagram
                if not request.image_url:
                    raise HTTPException(
                        status_code=400,
                        detail="Instagram posts require an image"
                    )
                result = await InstagramPostingService.post_image(
                    instagram_account_id=page_account.instagram_account_id,
                    page_access_token=page_token,
                    image_url=request.image_url,
                    caption=request.content or ""
                )
            
            account_name = page_account.page_name
            
        else:
            # Twitter/LinkedIn use social accounts directly
            if not request.social_account_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"{request.platform} requires social_account_id"
                )
            
            # Get social account
            result = await db.execute(
                select(SocialAccount).where(
                    SocialAccount.id == request.social_account_id,
                    SocialAccount.user_id == current_user.id
                )
            )
            social_account = result.scalars().first()
            
            if not social_account:
                raise HTTPException(status_code=404, detail="Social account not found")
            
            if social_account.platform != request.platform:
                raise HTTPException(
                    status_code=400,
                    detail=f"Social account is for {social_account.platform}, not {request.platform}"
                )
            
            if not social_account.is_active:
                raise HTTPException(
                    status_code=400,
                    detail="Social account is disconnected. Please reconnect."
                )
            
            # Refresh token if needed (handles expiration automatically)
            from app.services.token_refresh import TokenRefreshService
            access_token = await TokenRefreshService.refresh_if_needed(db, social_account)
            
            # Post
            if request.platform == "twitter":
                if not request.content:
                    raise HTTPException(
                        status_code=400,
                        detail="Twitter posts require content"
                    )
                result = await TwitterPostingService.post_tweet(
                    access_token=access_token,
                    text=request.content,
                    image_urls=request.image_urls
                )
            else:  # linkedin
                if not request.content:
                    raise HTTPException(
                        status_code=400,
                        detail="LinkedIn posts require content"
                    )
                result = await LinkedInPostingService.create_post(
                    access_token=access_token,
                    text=request.content,
                    image_url=request.image_url
                )
            
            account_name = social_account.platform_username
        
        return CreatePostResponse(
            success=True,
            post_id=result["post_id"],
            platform=request.platform,
            platform_url=result["platform_url"],
            account_name=account_name
        )
        
    except HTTPException:
        raise
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
