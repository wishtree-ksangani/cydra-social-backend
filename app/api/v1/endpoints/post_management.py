"""Post management and tracking endpoints"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta

from app.core.database import get_db
from app.api.dependencies.auth import get_current_user
from app.models.user import User
from app.models.post import Post, PostPlatform, PostStatus
from app.services.posting.multi_platform import MultiPlatformPostingService

router = APIRouter()


# ==================== Response Schemas ====================

class PostListItem(BaseModel):
    """Post list item schema"""
    id: int
    content: Optional[str]
    image_url: Optional[str]
    scheduled_at: Optional[str]
    is_scheduled: bool
    created_at: str
    platform_count: int
    completed_count: int
    failed_count: int
    in_progress_count: int


class PostStats(BaseModel):
    """User post statistics"""
    total_posts: int
    scheduled_posts: int
    completed_posts: int
    failed_posts: int
    posts_today: int
    posts_this_week: int
    posts_this_month: int


class PlatformStats(BaseModel):
    """Platform-specific statistics"""
    platform: str
    total_posts: int
    completed: int
    failed: int
    success_rate: float


class UpdatePostRequest(BaseModel):
    """Update post request"""
    content: Optional[str] = None
    image_url: Optional[str] = None
    scheduled_at: Optional[str] = None


# ==================== List & Filter Posts ====================

@router.get("/", response_model=List[PostListItem])
async def list_posts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    status: Optional[str] = Query(None, description="Filter by status: scheduled, completed, failed, in_progress"),
    platform: Optional[str] = Query(None, description="Filter by platform: facebook, instagram, twitter, linkedin"),
    limit: int = Query(50, le=100),
    offset: int = Query(0)
):
    """
    List all posts for the current user with filtering options.
    
    **Filters:**
    - `status`: Filter by post status
    - `platform`: Filter by specific platform
    - `limit`: Number of posts to return (max 100)
    - `offset`: Pagination offset
    """
    # Build query
    query = select(Post).where(Post.user_id == current_user.id)
    
    # Apply filters
    if status == "scheduled":
        query = query.where(Post.is_scheduled == 1)
    
    # Order by created_at descending
    query = query.order_by(Post.created_at.desc()).limit(limit).offset(offset)
    
    result = await db.execute(query)
    posts = result.scalars().all()
    
    # Get platform stats for each post
    post_items = []
    for post in posts:
        # Get platform statuses
        platform_result = await db.execute(
            select(PostPlatform).where(PostPlatform.post_id == post.id)
        )
        platforms = platform_result.scalars().all()
        
        # Filter by platform if specified
        if platform:
            platforms = [p for p in platforms if p.platform == platform]
            if not platforms:
                continue
        
        # Count statuses
        completed = sum(1 for p in platforms if p.status == PostStatus.COMPLETED)
        failed = sum(1 for p in platforms if p.status == PostStatus.FAILED)
        in_progress = sum(1 for p in platforms if p.status == PostStatus.IN_PROGRESS)
        
        # Filter by status if specified
        if status and status != "scheduled":
            if status == "completed" and completed == 0:
                continue
            if status == "failed" and failed == 0:
                continue
            if status == "in_progress" and in_progress == 0:
                continue
        
        post_items.append(PostListItem(
            id=post.id,
            content=post.content,
            image_url=post.image_url,
            scheduled_at=post.scheduled_at.isoformat() if post.scheduled_at else None,
            is_scheduled=bool(post.is_scheduled),
            created_at=post.created_at.isoformat(),
            platform_count=len(platforms),
            completed_count=completed,
            failed_count=failed,
            in_progress_count=in_progress
        ))
    
    return post_items


# ==================== Get Post Details ====================

@router.get("/{post_id}")
async def get_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed post information including all platform statuses."""
    status = await MultiPlatformPostingService.get_post_status(db, post_id, current_user.id)
    
    if not status:
        raise HTTPException(status_code=404, detail="Post not found")
    
    return status


# ==================== Update Post ====================

@router.patch("/{post_id}")
async def update_post(
    post_id: int,
    request: UpdatePostRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a scheduled post.
    
    **Note:** Only scheduled posts that haven't been processed can be updated.
    """
    # Get post
    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.user_id == current_user.id)
    )
    post = result.scalars().first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    if not post.is_scheduled:
        raise HTTPException(status_code=400, detail="Cannot update post that has already been processed")
    
    # Update fields
    if request.content is not None:
        post.content = request.content
    
    if request.image_url is not None:
        post.image_url = request.image_url
    
    if request.scheduled_at is not None:
        try:
            scheduled_at = datetime.fromisoformat(request.scheduled_at.replace('Z', '+00:00'))
            post.scheduled_at = scheduled_at
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid scheduled_at format")
    
    await db.commit()
    
    return await MultiPlatformPostingService.get_post_status(db, post_id, current_user.id)


# ==================== Delete Post ====================

@router.delete("/{post_id}")
async def delete_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a post.
    
    **Note:** Only scheduled posts that haven't been processed can be deleted.
    Already published posts cannot be deleted from the database.
    """
    # Get post
    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.user_id == current_user.id)
    )
    post = result.scalars().first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    if not post.is_scheduled:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete post that has already been processed. Use platform APIs to delete published posts."
        )
    
    # Delete platform entries
    await db.execute(
        select(PostPlatform).where(PostPlatform.post_id == post_id)
    )
    
    # Delete post
    await db.delete(post)
    await db.commit()
    
    return {"success": True, "message": "Post deleted successfully"}


# ==================== Cancel Scheduled Post ====================

@router.post("/{post_id}/cancel")
async def cancel_scheduled_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Cancel a scheduled post.
    
    This marks the post as not scheduled, preventing it from being published.
    """
    # Get post
    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.user_id == current_user.id)
    )
    post = result.scalars().first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    if not post.is_scheduled:
        raise HTTPException(status_code=400, detail="Post is not scheduled")
    
    # Mark as not scheduled
    post.is_scheduled = 0
    await db.commit()
    
    return {"success": True, "message": "Scheduled post cancelled"}


# ==================== User Statistics ====================

@router.get("/stats/overview", response_model=PostStats)
async def get_post_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get overall post statistics for the current user."""
    
    # Total posts
    total_result = await db.execute(
        select(func.count(Post.id)).where(Post.user_id == current_user.id)
    )
    total_posts = total_result.scalar()
    
    # Scheduled posts
    scheduled_result = await db.execute(
        select(func.count(Post.id)).where(
            Post.user_id == current_user.id,
            Post.is_scheduled == 1
        )
    )
    scheduled_posts = scheduled_result.scalar()
    
    # Get platform stats
    platform_result = await db.execute(
        select(PostPlatform).join(Post).where(Post.user_id == current_user.id)
    )
    platforms = platform_result.scalars().all()
    
    completed = sum(1 for p in platforms if p.status == PostStatus.COMPLETED)
    failed = sum(1 for p in platforms if p.status == PostStatus.FAILED)
    
    # Time-based stats
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=now.weekday())
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Posts today
    today_result = await db.execute(
        select(func.count(Post.id)).where(
            Post.user_id == current_user.id,
            Post.created_at >= today_start
        )
    )
    posts_today = today_result.scalar()
    
    # Posts this week
    week_result = await db.execute(
        select(func.count(Post.id)).where(
            Post.user_id == current_user.id,
            Post.created_at >= week_start
        )
    )
    posts_this_week = week_result.scalar()
    
    # Posts this month
    month_result = await db.execute(
        select(func.count(Post.id)).where(
            Post.user_id == current_user.id,
            Post.created_at >= month_start
        )
    )
    posts_this_month = month_result.scalar()
    
    return PostStats(
        total_posts=total_posts,
        scheduled_posts=scheduled_posts,
        completed_posts=completed,
        failed_posts=failed,
        posts_today=posts_today,
        posts_this_week=posts_this_week,
        posts_this_month=posts_this_month
    )


@router.get("/stats/platforms", response_model=List[PlatformStats])
async def get_platform_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get statistics broken down by platform."""
    
    # Get all platform entries for user's posts
    result = await db.execute(
        select(PostPlatform).join(Post).where(Post.user_id == current_user.id)
    )
    platforms = result.scalars().all()
    
    # Group by platform
    stats_by_platform = {}
    for p in platforms:
        if p.platform not in stats_by_platform:
            stats_by_platform[p.platform] = {
                "total": 0,
                "completed": 0,
                "failed": 0
            }
        
        stats_by_platform[p.platform]["total"] += 1
        if p.status == PostStatus.COMPLETED:
            stats_by_platform[p.platform]["completed"] += 1
        elif p.status == PostStatus.FAILED:
            stats_by_platform[p.platform]["failed"] += 1
    
    # Build response
    platform_stats = []
    for platform, stats in stats_by_platform.items():
        success_rate = (stats["completed"] / stats["total"] * 100) if stats["total"] > 0 else 0
        platform_stats.append(PlatformStats(
            platform=platform,
            total_posts=stats["total"],
            completed=stats["completed"],
            failed=stats["failed"],
            success_rate=round(success_rate, 2)
        ))
    
    return platform_stats
