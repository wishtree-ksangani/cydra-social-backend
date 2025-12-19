"""Multi-platform posting endpoint"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Optional

from app.core.database import get_db
from app.api.dependencies.auth import get_current_user
from app.models.user import User
from app.services.posting.multi_platform import MultiPlatformPostingService

router = APIRouter()


class PlatformConfig(BaseModel):
    """Configuration for posting to a specific platform"""
    platform: str  # facebook, instagram, twitter, linkedin
    page_account_id: Optional[int] = None  # For Facebook/Instagram
    social_account_id: Optional[int] = None  # For Twitter/LinkedIn


class MultiPostRequest(BaseModel):
    """Request schema for multi-platform posting"""
    content: Optional[str] = None
    image_url: Optional[str] = None  # Single image URL
    platforms: List[PlatformConfig]
    scheduled_at: Optional[str] = None  # ISO 8601 datetime string


class PlatformStatus(BaseModel):
    """Status of posting to a single platform"""
    platform: str
    account_name: str
    status: str  # queued, in_progress, completed, failed
    post_id: Optional[str] = None
    platform_url: Optional[str] = None
    error: Optional[str] = None
    queued_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class MultiPostResponse(BaseModel):
    """Response schema for multi-platform posting"""
    id: int
    content: Optional[str]
    image_url: Optional[str] = None
    scheduled_at: Optional[str] = None
    is_scheduled: bool = False
    platforms: List[PlatformStatus]
    created_at: str


@router.post("/multi", response_model=MultiPostResponse)
async def create_multi_platform_post(
    request: MultiPostRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Post to multiple social media platforms simultaneously.
    
    This endpoint creates a post and distributes it across all selected platforms.
    Each platform's posting status is tracked independently.
    
    **Platform Configuration:**
    - **Facebook**: `{"platform": "facebook", "page_account_id": 1}`
    - **Instagram**: `{"platform": "instagram", "page_account_id": 1}`
    - **Twitter**: `{"platform": "twitter", "social_account_id": 2}`
    - **LinkedIn**: `{"platform": "linkedin", "social_account_id": 3}`
    
    **Example Request:**
    ```json
    {
      "content": "Hello from all platforms!",
      "image_url": "https://example.com/image.jpg",
      "platforms": [
        {"platform": "facebook", "page_account_id": 1},
        {"platform": "twitter", "social_account_id": 2},
        {"platform": "linkedin", "social_account_id": 3}
      ],
      "scheduled_at": "2025-12-20T10:00:00Z"
    }
    ```
    
    **Status Tracking:**
    - `queued`: Post is queued for processing
    - `in_progress`: Currently posting to platform
    - `completed`: Successfully posted
    - `failed`: Posting failed (check error field)
    
    **Returns:**
    Post object with status for each platform. Use the `id` to check status later.
    """
    # Validate platforms
    if not request.platforms:
        raise HTTPException(status_code=400, detail="At least one platform is required")
    
    # Validate platform configs
    for platform_config in request.platforms:
        if platform_config.platform in ["facebook", "instagram"]:
            if not platform_config.page_account_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"{platform_config.platform} requires page_account_id"
                )
        elif platform_config.platform in ["twitter", "linkedin"]:
            if not platform_config.social_account_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"{platform_config.platform} requires social_account_id"
                )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid platform: {platform_config.platform}"
            )
    
    try:
        # Parse scheduled_at if provided
        scheduled_at = None
        if request.scheduled_at:
            from datetime import datetime
            try:
                scheduled_at = datetime.fromisoformat(request.scheduled_at.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid scheduled_at format. Use ISO 8601 format (e.g., '2025-12-20T10:00:00Z')"
                )
        
        # Create multi-platform post
        post = await MultiPlatformPostingService.create_multi_platform_post(
            db=db,
            user_id=current_user.id,
            content=request.content,
            image_url=request.image_url,
            platforms=[p.dict() for p in request.platforms],
            scheduled_at=scheduled_at
        )
        
        # Get initial status
        status = await MultiPlatformPostingService.get_post_status(
            db, post.id, current_user.id
        )
        
        return status
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{post_id}/status", response_model=MultiPostResponse)
async def get_post_status(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the current status of a multi-platform post.
    
    Use this endpoint to check the progress of your post across all platforms.
    
    **Returns:**
    - Post details
    - Status for each platform (queued, in_progress, completed, failed)
    - Platform-specific post IDs and URLs
    - Error messages if any platform failed
    """
    status = await MultiPlatformPostingService.get_post_status(
        db, post_id, current_user.id
    )
    
    if not status:
        raise HTTPException(status_code=404, detail="Post not found")
    
    return status
