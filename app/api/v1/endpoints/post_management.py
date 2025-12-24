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
    topic: Optional[str]  # For display in list
    status: str  # draft | scheduled | publishing | published | failed
    scheduled_at: Optional[str]
    created_at: str
    platform_count: int
    completed_count: int
    failed_count: int
    in_progress_count: int



class PostStats(BaseModel):
    """User post statistics - counts unique posts by status"""
    total_posts: int
    draft_posts: int
    scheduled_posts: int
    published_posts: int
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
    """Update post request - updates post metadata, not platform content"""
    topic: Optional[str] = None
    tone: Optional[str] = None
    hashtag: Optional[str] = None
    scheduled_at: Optional[str] = None



class TimeSeriesDataPoint(BaseModel):
    """Single data point in time series"""
    period: str           # Date or period label (e.g., "2025-12-23", "2025-W51", "2025-12")
    total: int
    published: int
    failed: int
    scheduled: int
    draft: int


class TimeSeriesResponse(BaseModel):
    """Response for time series statistics"""
    group_by: str         # "day" | "week" | "month"
    start_date: str
    end_date: str
    data: List[TimeSeriesDataPoint]
    summary: dict         # Overall summary for the period


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
    if status == "draft":
        query = query.where(Post.status == "draft")
    elif status == "scheduled":
        query = query.where(Post.status == "scheduled")
    
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
            topic=post.topic,
            status=post.status,
            scheduled_at=post.scheduled_at.isoformat() if post.scheduled_at else None,
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
    Update a draft or scheduled post.
    
    **Note:** Only draft/scheduled posts that haven't been processed can be updated.
    For platform content updates, use PUT /posts/{post_id}/platforms.
    """
    # Get post
    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.user_id == current_user.id)
    )
    post = result.scalars().first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    if post.status not in ["draft", "scheduled"]:
        raise HTTPException(status_code=400, detail="Cannot update post that has already been processed")
    
    # Update post metadata fields
    if request.topic is not None:
        post.topic = request.topic
    
    if request.tone is not None:
        post.tone = request.tone
    
    if request.hashtag is not None:
        post.hashtag = request.hashtag
    
    if request.scheduled_at is not None:
        try:
            scheduled_at = datetime.fromisoformat(request.scheduled_at.replace('Z', '+00:00'))
            post.scheduled_at = scheduled_at
            # Auto-change draft to scheduled when scheduled_at is set
            if post.status == "draft":
                post.status = "scheduled"
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid scheduled_at format")
    
    await db.commit()
    
    return await MultiPlatformPostingService.get_post_status(db, post_id, current_user.id)


# ==================== Replace Entire Post (PUT) ====================

class PlatformInput(BaseModel):
    """Platform configuration for creating/updating"""
    platform: str  # facebook, instagram, twitter, linkedin
    page_account_id: Optional[int] = None  # For Facebook/Instagram
    social_account_id: Optional[int] = None  # For Twitter/LinkedIn
    content: str  # Content for this platform (required)
    image_url: Optional[str] = None  # Image URL for this platform


class FullPostUpdate(BaseModel):
    """Full post update - replaces entire post"""
    topic: Optional[str] = None
    tone: Optional[str] = None
    hashtag: Optional[str] = None
    scheduled_at: Optional[str] = None
    platforms: List[PlatformInput]


@router.put("/{post_id}")
async def replace_post(
    post_id: int,
    request: FullPostUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Replace entire post - updates both metadata and all platforms.
    
    This is a complete replacement - existing platforms are deleted and replaced
    with the new ones provided.
    
    **Note:** Only draft/scheduled posts can be updated.
    """
    # Get post
    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.user_id == current_user.id)
    )
    post = result.scalars().first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    if post.status not in ["draft", "scheduled"]:
        raise HTTPException(status_code=400, detail="Cannot update post that has already been processed")
    
    if not request.platforms:
        raise HTTPException(status_code=400, detail="At least one platform is required")
    
    # Update post metadata
    if request.topic is not None:
        post.topic = request.topic
    if request.tone is not None:
        post.tone = request.tone
    if request.hashtag is not None:
        post.hashtag = request.hashtag
    
    if request.scheduled_at is not None:
        try:
            scheduled_at = datetime.fromisoformat(request.scheduled_at.replace('Z', '+00:00'))
            post.scheduled_at = scheduled_at
            if post.status == "draft":
                post.status = "scheduled"
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid scheduled_at format")
    
    # Delete existing platforms
    existing_result = await db.execute(
        select(PostPlatform).where(PostPlatform.post_id == post_id)
    )
    existing_platforms = existing_result.scalars().all()
    for existing in existing_platforms:
        await db.delete(existing)
    
    # Create new platform entries
    for platform_config in request.platforms:
        platform = platform_config.platform
        
        # Validate platform config
        if platform in ["facebook", "instagram"]:
            if not platform_config.page_account_id:
                raise HTTPException(status_code=400, detail=f"{platform} requires page_account_id")
            account_id = platform_config.page_account_id
        elif platform in ["twitter", "linkedin"]:
            if not platform_config.social_account_id:
                raise HTTPException(status_code=400, detail=f"{platform} requires social_account_id")
            account_id = platform_config.social_account_id
        else:
            raise HTTPException(status_code=400, detail=f"Invalid platform: {platform}")
        
        # Get account name
        account_name = await MultiPlatformPostingService._get_account_name(
            db, platform, platform_config.dict()
        )
        
        post_platform = PostPlatform(
            post_id=post.id,
            platform=platform,
            account_id=account_id,
            account_name=account_name,
            content=platform_config.content,
            image_url=platform_config.image_url,
            status=PostStatus.QUEUED
        )
        db.add(post_platform)
    
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
    
    if post.status not in ["draft", "scheduled"]:
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


# ==================== Update Platforms ====================

class PlatformUpdate(BaseModel):
    """Platform update configuration"""
    platform: str  # facebook, instagram, twitter, linkedin
    page_account_id: Optional[int] = None  # For Facebook/Instagram
    social_account_id: Optional[int] = None  # For Twitter/LinkedIn
    content: str  # Content for this platform (required)
    image_url: Optional[str] = None  # Image URL for this platform


@router.put("/{post_id}/platforms")
async def update_post_platforms(
    post_id: int,
    platforms: List[PlatformUpdate],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Replace all platforms for a draft/scheduled post.
    
    This allows adding, removing, or updating platforms and their content.
    
    **Note:** Only draft/scheduled posts can have their platforms updated.
    """
    # Get post
    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.user_id == current_user.id)
    )
    post = result.scalars().first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    if post.status not in ["draft", "scheduled"]:
        raise HTTPException(status_code=400, detail="Cannot update platforms for a post that has already been processed")
    
    if not platforms:
        raise HTTPException(status_code=400, detail="At least one platform is required")
    
    # Delete existing platforms
    existing_result = await db.execute(
        select(PostPlatform).where(PostPlatform.post_id == post_id)
    )
    existing_platforms = existing_result.scalars().all()
    for existing in existing_platforms:
        await db.delete(existing)
    
    # Create new platform entries
    for platform_config in platforms:
        platform = platform_config.platform
        
        # Validate platform config
        if platform in ["facebook", "instagram"]:
            if not platform_config.page_account_id:
                raise HTTPException(status_code=400, detail=f"{platform} requires page_account_id")
            account_id = platform_config.page_account_id
        else:
            if not platform_config.social_account_id:
                raise HTTPException(status_code=400, detail=f"{platform} requires social_account_id")
            account_id = platform_config.social_account_id
        
        # Get account name
        account_name = await MultiPlatformPostingService._get_account_name(
            db, platform, platform_config.dict()
        )
        
        post_platform = PostPlatform(
            post_id=post.id,
            platform=platform,
            account_id=account_id,
            account_name=account_name,
            content=platform_config.content,
            image_url=platform_config.image_url,
            status=PostStatus.QUEUED
        )
        db.add(post_platform)
    
    await db.commit()
    
    return await MultiPlatformPostingService.get_post_status(db, post_id, current_user.id)


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
    
    if post.status != "scheduled":
        raise HTTPException(status_code=400, detail="Post is not scheduled")
    
    # Mark as cancelled (draft)
    post.status = "draft"
    post.scheduled_at = None
    await db.commit()
    
    return {"success": True, "message": "Scheduled post cancelled"}


# ==================== Publish Draft ====================

class PublishRequest(BaseModel):
    """Publish draft request"""
    mode: str  # "immediate" | "schedule"
    scheduled_at: Optional[str] = None  # Required if mode="schedule"


@router.post("/{post_id}/publish")
async def publish_draft(
    post_id: int,
    request: PublishRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Publish a draft post.
    
    **Modes:**
    - `immediate`: Post now to all platforms
    - `schedule`: Schedule for later (requires scheduled_at)
    """
    # Get post
    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.user_id == current_user.id)
    )
    post = result.scalars().first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    if post.status not in ["draft"]:
        raise HTTPException(status_code=400, detail="Only draft posts can be published")
    
    if request.mode == "schedule":
        if not request.scheduled_at:
            raise HTTPException(status_code=400, detail="scheduled_at is required for schedule mode")
        
        try:
            scheduled_at = datetime.fromisoformat(request.scheduled_at.replace('Z', '+00:00'))
            post.scheduled_at = scheduled_at
            post.status = "scheduled"
            await db.commit()
            return {"success": True, "message": "Post scheduled", "scheduled_at": scheduled_at.isoformat()}
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid scheduled_at format")
    
    elif request.mode == "immediate":
        # Get platform entries
        platform_result = await db.execute(
            select(PostPlatform).where(PostPlatform.post_id == post_id)
        )
        platforms = platform_result.scalars().all()
        
        if not platforms:
            raise HTTPException(status_code=400, detail="No platforms configured for this post")
        
        # Build platform configs
        platform_configs = []
        for p in platforms:
            if p.platform in ["facebook", "instagram"]:
                platform_configs.append({
                    "platform": p.platform,
                    "page_account_id": p.account_id
                })
            else:
                platform_configs.append({
                    "platform": p.platform,
                    "social_account_id": p.account_id
                })
        
        # Update status to publishing
        post.status = "publishing"
        await db.commit()
        
        # Start posting
        import asyncio
        asyncio.create_task(
            MultiPlatformPostingService._process_platforms(
                post.id,
                platforms,
                post.content,
                post.image_url,
                platform_configs
            )
        )
        
        return {"success": True, "message": "Post is being published"}
    
    else:
        raise HTTPException(status_code=400, detail="Invalid mode. Use 'immediate' or 'schedule'")


# ==================== User Statistics ====================

@router.get("/stats/overview", response_model=PostStats)
async def get_post_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get overall post statistics for the current user (counts unique posts by status)."""
    
    # Total posts
    total_result = await db.execute(
        select(func.count(Post.id)).where(Post.user_id == current_user.id)
    )
    total_posts = total_result.scalar()
    
    # Draft posts
    draft_result = await db.execute(
        select(func.count(Post.id)).where(
            Post.user_id == current_user.id,
            Post.status == "draft"
        )
    )
    draft_posts = draft_result.scalar()
    
    # Scheduled posts
    scheduled_result = await db.execute(
        select(func.count(Post.id)).where(
            Post.user_id == current_user.id,
            Post.status == "scheduled"
        )
    )
    scheduled_posts = scheduled_result.scalar()
    
    # Published posts
    published_result = await db.execute(
        select(func.count(Post.id)).where(
            Post.user_id == current_user.id,
            Post.status == "published"
        )
    )
    published_posts = published_result.scalar()
    
    # Failed posts
    failed_result = await db.execute(
        select(func.count(Post.id)).where(
            Post.user_id == current_user.id,
            Post.status == "failed"
        )
    )
    failed_posts = failed_result.scalar()
    
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
        draft_posts=draft_posts,
        scheduled_posts=scheduled_posts,
        published_posts=published_posts,
        failed_posts=failed_posts,
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
        select(PostPlatform)
        .join(Post, PostPlatform.post_id == Post.id)
        .where(Post.user_id == current_user.id)
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


@router.get("/stats/timeseries", response_model=TimeSeriesResponse)
async def get_timeseries_stats(
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(..., description="End date in YYYY-MM-DD format"),
    group_by: str = Query("day", description="Group by: day, week, or month"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get time-series post statistics for charting.
    
    **Parameters:**
    - `start_date`: Start of date range (YYYY-MM-DD)
    - `end_date`: End of date range (YYYY-MM-DD)
    - `group_by`: Grouping period - "day" | "week" | "month"
    
    **Returns:**
    Time-series data points with post counts grouped by period.
    """
    # Validate group_by
    if group_by not in ["day", "week", "month"]:
        raise HTTPException(status_code=400, detail="group_by must be 'day', 'week', or 'month'")
    
    # Parse dates
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    if start_dt > end_dt:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")
    
    # Get all posts in date range
    result = await db.execute(
        select(Post).where(
            Post.user_id == current_user.id,
            Post.created_at >= start_dt,
            Post.created_at <= end_dt
        ).order_by(Post.created_at)
    )
    posts = result.scalars().all()
    
    # Group posts by period
    grouped_data = {}
    summary = {"total": 0, "published": 0, "failed": 0, "scheduled": 0, "draft": 0}
    
    for post in posts:
        # Determine period key based on grouping
        if group_by == "day":
            period_key = post.created_at.strftime("%Y-%m-%d")
        elif group_by == "week":
            # ISO week format: YYYY-Wnn
            period_key = post.created_at.strftime("%Y-W%W")
        else:  # month
            period_key = post.created_at.strftime("%Y-%m")
        
        # Initialize period if not exists
        if period_key not in grouped_data:
            grouped_data[period_key] = {
                "total": 0, "published": 0, "failed": 0, "scheduled": 0, "draft": 0
            }
        
        # Count by status
        grouped_data[period_key]["total"] += 1
        summary["total"] += 1
        
        if post.status == "published":
            grouped_data[period_key]["published"] += 1
            summary["published"] += 1
        elif post.status == "failed":
            grouped_data[period_key]["failed"] += 1
            summary["failed"] += 1
        elif post.status == "scheduled":
            grouped_data[period_key]["scheduled"] += 1
            summary["scheduled"] += 1
        elif post.status == "draft":
            grouped_data[period_key]["draft"] += 1
            summary["draft"] += 1
    
    # Generate all periods in range (to include empty periods)
    all_periods = []
    current = start_dt
    
    while current <= end_dt:
        if group_by == "day":
            period_key = current.strftime("%Y-%m-%d")
            current += timedelta(days=1)
        elif group_by == "week":
            period_key = current.strftime("%Y-W%W")
            current += timedelta(weeks=1)
        else:  # month
            period_key = current.strftime("%Y-%m")
            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1, day=1)
            else:
                current = current.replace(month=current.month + 1, day=1)
        
        if period_key not in all_periods:
            all_periods.append(period_key)
    
    # Build response data with all periods
    data_points = []
    for period in all_periods:
        stats = grouped_data.get(period, {"total": 0, "published": 0, "failed": 0, "scheduled": 0, "draft": 0})
        data_points.append(TimeSeriesDataPoint(
            period=period,
            total=stats["total"],
            published=stats["published"],
            failed=stats["failed"],
            scheduled=stats["scheduled"],
            draft=stats["draft"]
        ))
    
    return TimeSeriesResponse(
        group_by=group_by,
        start_date=start_date,
        end_date=end_date,
        data=data_points,
        summary=summary
    )
