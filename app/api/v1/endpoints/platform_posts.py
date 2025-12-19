"""Platform-specific posting endpoints - Cleaner API design"""

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
from app.services.token_refresh import TokenRefreshService

router = APIRouter()


# ==================== FACEBOOK ====================

class FacebookPostRequest(BaseModel):
    """Request schema for Facebook posts"""
    page_account_id: int
    content: Optional[str] = None
    image_url: Optional[str] = None


class PostResponse(BaseModel):
    """Response schema for all posts"""
    success: bool
    post_id: str
    platform: str
    platform_url: str
    account_name: str


@router.post("/facebook", response_model=PostResponse)
async def post_to_facebook(
    request: FacebookPostRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Post to a Facebook Page.
    
    - **page_account_id**: ID of the Facebook Page
    - **content**: Post text (optional)
    - **image_url**: Image URL (optional)
    """
    from app.services.posting.multi_platform import MultiPlatformPostingService
    
    # Verify page ownership
    result = await db.execute(
        select(PageAccount).where(PageAccount.id == request.page_account_id)
    )
    page_account = result.scalars().first()
    
    if not page_account:
        raise HTTPException(status_code=404, detail="Page not found")
    
    result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.id == page_account.social_account_id,
            SocialAccount.user_id == current_user.id
        )
    )
    if not result.scalars().first():
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        # Use multi-platform service for status tracking
        post = await MultiPlatformPostingService.create_multi_platform_post(
            db=db,
            user_id=current_user.id,
            content=request.content,
            image_url=request.image_url,
            platforms=[{"platform": "facebook", "page_account_id": request.page_account_id}],
            scheduled_at=None  # Immediate posting
        )
        
        # Wait a moment for processing to start
        import asyncio
        await asyncio.sleep(0.5)
        
        # Get status
        status = await MultiPlatformPostingService.get_post_status(db, post.id, current_user.id)
        platform_status = status["platforms"][0]
        
        return PostResponse(
            success=platform_status["status"] in ["completed", "in_progress"],
            post_id=platform_status.get("post_id") or str(post.id),
            platform="facebook",
            platform_url=platform_status.get("platform_url") or "",
            account_name=platform_status["account_name"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== INSTAGRAM ====================

class InstagramPostRequest(BaseModel):
    """Request schema for Instagram posts"""
    page_account_id: int
    image_url: str  # Required for Instagram
    caption: Optional[str] = None


@router.post("/instagram", response_model=PostResponse)
async def post_to_instagram(
    request: InstagramPostRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Post to Instagram Business account.
    
    - **page_account_id**: ID of the Facebook Page with Instagram linked
    - **image_url**: Image URL (REQUIRED)
    - **caption**: Post caption (optional)
    """
    from app.services.posting.multi_platform import MultiPlatformPostingService
    
    # Verify page ownership and Instagram link
    result = await db.execute(
        select(PageAccount).where(PageAccount.id == request.page_account_id)
    )
    page_account = result.scalars().first()
    
    if not page_account:
        raise HTTPException(status_code=404, detail="Page not found")
    
    if not page_account.instagram_account_id:
        raise HTTPException(
            status_code=400,
            detail="This page doesn't have an Instagram account linked"
        )
    
    result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.id == page_account.social_account_id,
            SocialAccount.user_id == current_user.id
        )
    )
    if not result.scalars().first():
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        # Use multi-platform service for status tracking
        post = await MultiPlatformPostingService.create_multi_platform_post(
            db=db,
            user_id=current_user.id,
            content=request.caption,
            image_url=request.image_url,
            platforms=[{"platform": "instagram", "page_account_id": request.page_account_id}],
            scheduled_at=None
        )
        
        import asyncio
        await asyncio.sleep(0.5)
        
        status = await MultiPlatformPostingService.get_post_status(db, post.id, current_user.id)
        platform_status = status["platforms"][0]
        
        return PostResponse(
            success=platform_status["status"] in ["completed", "in_progress"],
            post_id=platform_status.get("post_id") or str(post.id),
            platform="instagram",
            platform_url=platform_status.get("platform_url") or "",
            account_name=platform_status["account_name"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== TWITTER ====================

class TwitterPostRequest(BaseModel):
    """Request schema for Twitter posts"""
    social_account_id: int
    content: str  # Required for Twitter
    image_urls: Optional[List[str]] = None  # Max 4 images


@router.post("/twitter", response_model=PostResponse)
async def post_to_twitter(
    request: TwitterPostRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Post a tweet to Twitter/X.
    
    - **social_account_id**: ID of the Twitter account
    - **content**: Tweet text (REQUIRED, max 280 characters)
    - **image_urls**: List of image URLs (optional, max 4)
    """
    from app.services.posting.multi_platform import MultiPlatformPostingService
    
    # Verify account ownership
    result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.id == request.social_account_id,
            SocialAccount.user_id == current_user.id,
            SocialAccount.platform == "twitter"
        )
    )
    social_account = result.scalars().first()
    
    if not social_account:
        raise HTTPException(status_code=404, detail="Twitter account not found")
    
    if not social_account.is_active:
        raise HTTPException(status_code=400, detail="Account is disconnected")
    
    try:
        # Use first image only (multi-platform uses single image_url)
        image_url = request.image_urls[0] if request.image_urls else None
        
        # Use multi-platform service for status tracking
        post = await MultiPlatformPostingService.create_multi_platform_post(
            db=db,
            user_id=current_user.id,
            content=request.content,
            image_url=image_url,
            platforms=[{"platform": "twitter", "social_account_id": request.social_account_id}],
            scheduled_at=None
        )
        
        import asyncio
        await asyncio.sleep(0.5)
        
        status = await MultiPlatformPostingService.get_post_status(db, post.id, current_user.id)
        platform_status = status["platforms"][0]
        
        return PostResponse(
            success=platform_status["status"] in ["completed", "in_progress"],
            post_id=platform_status.get("post_id") or str(post.id),
            platform="twitter",
            platform_url=platform_status.get("platform_url") or "",
            account_name=platform_status["account_name"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== LINKEDIN ====================

class LinkedInPostRequest(BaseModel):
    """Request schema for LinkedIn posts"""
    social_account_id: int
    content: str  # Required for LinkedIn
    image_url: Optional[str] = None  # Single image


@router.post("/linkedin", response_model=PostResponse)
async def post_to_linkedin(
    request: LinkedInPostRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Post to LinkedIn.
    
    - **social_account_id**: ID of the LinkedIn account
    - **content**: Post text (REQUIRED, max 3000 characters)
    - **image_url**: Image URL (optional, single image)
    """
    from app.services.posting.multi_platform import MultiPlatformPostingService
    
    # Verify account ownership
    result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.id == request.social_account_id,
            SocialAccount.user_id == current_user.id,
            SocialAccount.platform == "linkedin"
        )
    )
    social_account = result.scalars().first()
    
    if not social_account:
        raise HTTPException(status_code=404, detail="LinkedIn account not found")
    
    if not social_account.is_active:
        raise HTTPException(status_code=400, detail="Account is disconnected")
    
    try:
        # Use multi-platform service for status tracking
        post = await MultiPlatformPostingService.create_multi_platform_post(
            db=db,
            user_id=current_user.id,
            content=request.content,
            image_url=request.image_url,
            platforms=[{"platform": "linkedin", "social_account_id": request.social_account_id}],
            scheduled_at=None
        )
        
        import asyncio
        await asyncio.sleep(0.5)
        
        status = await MultiPlatformPostingService.get_post_status(db, post.id, current_user.id)
        platform_status = status["platforms"][0]
        
        return PostResponse(
            success=platform_status["status"] in ["completed", "in_progress"],
            post_id=platform_status.get("post_id") or str(post.id),
            platform="linkedin",
            platform_url=platform_status.get("platform_url") or "",
            account_name=platform_status["account_name"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
