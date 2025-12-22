"""Multi-platform posting service - Post to multiple platforms simultaneously"""

import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.post import Post, PostPlatform, PostStatus
from app.models.social_account import SocialAccount
from app.models.page_account import PageAccount
from app.core.encryption import decrypt_token
from app.services.posting import (
    FacebookPostingService,
    InstagramPostingService,
    TwitterPostingService,
    LinkedInPostingService
)
from app.services.token_refresh import TokenRefreshService


class MultiPlatformPostingService:
    """Service for posting to multiple platforms with status tracking"""
    
    @staticmethod
    async def create_multi_platform_post(
        db: AsyncSession,
        user_id: int,
        content: Optional[str],
        image_url: Optional[str],
        platforms: List[Dict[str, any]],
        status: str = "draft",
        scheduled_at: Optional[datetime] = None
    ) -> Post:
        """
        Create a post across multiple platforms.
        
        Args:
            db: Database session
            user_id: User ID
            content: Post content/text
            image_url: Single image URL
            platforms: List of platform configs
            status: Post status - "draft" | "scheduled" | "publishing"
            scheduled_at: When to post (required if status="scheduled")
        
        Returns:
            Post object with platform statuses
        """
        # Create main post record
        post = Post(
            user_id=user_id,
            content=content,
            image_url=image_url,
            status=status,
            scheduled_at=scheduled_at
        )
        db.add(post)
        await db.flush()  # Get post.id
        
        # Create platform entries
        platform_entries = []
        for platform_config in platforms:
            platform = platform_config["platform"]
            
            # Get account name
            account_name = await MultiPlatformPostingService._get_account_name(
                db, platform, platform_config
            )
            
            # Get platform-specific content (overrides global if provided)
            platform_content = platform_config.get("content")
            platform_image_url = platform_config.get("image_url")
            
            post_platform = PostPlatform(
                post_id=post.id,
                platform=platform,
                account_id=platform_config.get("page_account_id") or platform_config.get("social_account_id"),
                account_name=account_name,
                platform_content=platform_content,  # Store platform-specific content
                platform_image_url=platform_image_url,  # Store platform-specific image
                status=PostStatus.QUEUED
            )
            db.add(post_platform)
            platform_entries.append(post_platform)
        
        await db.commit()
        
        # If immediate (publishing), start posting now
        if status == "immediate" or status == "publishing":
            # Update status to publishing
            post.status = "publishing"
            await db.commit()
            
            asyncio.create_task(
                MultiPlatformPostingService._process_platforms(
                    post.id, platform_entries, content, image_url, platforms
                )
            )
        
        return post
    
    @staticmethod
    async def _get_account_name(
        db: AsyncSession,
        platform: str,
        platform_config: Dict[str, any]
    ) -> str:
        """Get account name for display"""
        if platform in ["facebook", "instagram"]:
            page_id = platform_config.get("page_account_id")
            result = await db.execute(
                select(PageAccount).where(PageAccount.id == page_id)
            )
            page = result.scalars().first()
            return page.page_name if page else "Unknown"
        else:
            social_id = platform_config.get("social_account_id")
            result = await db.execute(
                select(SocialAccount).where(SocialAccount.id == social_id)
            )
            account = result.scalars().first()
            return account.platform_username if account else "Unknown"
    
    @staticmethod
    async def _process_platforms(
        post_id: int,
        platform_entries: List[PostPlatform],
        content: Optional[str],
        image_url: Optional[str],
        platforms: List[Dict[str, any]]
    ):
        """Process posting to all platforms (runs in background)"""
        from app.core.database import get_db
        
        async for db in get_db():
            # Re-fetch platform entries in this session to avoid detached object issues
            result = await db.execute(
                select(PostPlatform).where(PostPlatform.post_id == post_id)
            )
            fresh_platform_entries = result.scalars().all()
            
            # Build a map of platform to config
            platform_config_map = {p.get("platform"): p for p in platforms}
            
            tasks = []
            for platform_entry in fresh_platform_entries:
                config = platform_config_map.get(platform_entry.platform, {})
                if not config:
                    # Try to find by account_id
                    for p in platforms:
                        if p.get("social_account_id") == platform_entry.account_id or p.get("page_account_id") == platform_entry.account_id:
                            config = p
                            break
                
                task = MultiPlatformPostingService._post_to_platform(
                    db, platform_entry, content, image_url, config
                )
                tasks.append(task)
            
            # Post to all platforms concurrently
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Update post status to published after all platforms are processed
            post_result = await db.execute(
                select(Post).where(Post.id == post_id)
            )
            post = post_result.scalars().first()
            if post:
                post.status = "published"
                await db.commit()
            
            break

    
    @staticmethod
    async def _post_to_platform(
        db: AsyncSession,
        post_platform: PostPlatform,
        content: Optional[str],
        image_url: Optional[str],
        platform_config: Dict[str, any]
    ):
        """Post to a single platform and update status"""
        platform = post_platform.platform
        
        try:
            # Update status to in_progress
            post_platform.status = PostStatus.IN_PROGRESS
            post_platform.started_at = datetime.now(timezone.utc)
            await db.commit()
            
            # Use platform-specific content if available, otherwise use global
            final_content = post_platform.platform_content if post_platform.platform_content is not None else content
            final_image_url = post_platform.platform_image_url if post_platform.platform_image_url is not None else image_url
            
            result = None
            
            # Post based on platform
            if platform == "facebook":
                result = await MultiPlatformPostingService._post_facebook(
                    db, platform_config, final_content, final_image_url
                )
            elif platform == "instagram":
                result = await MultiPlatformPostingService._post_instagram(
                    db, platform_config, final_content, final_image_url
                )
            elif platform == "twitter":
                result = await MultiPlatformPostingService._post_twitter(
                    db, platform_config, final_content, final_image_url
                )
            elif platform == "linkedin":
                result = await MultiPlatformPostingService._post_linkedin(
                    db, platform_config, final_content, final_image_url
                )
            
            # Update success
            post_platform.status = PostStatus.COMPLETED
            post_platform.platform_post_id = result["post_id"]
            post_platform.platform_url = result["platform_url"]
            post_platform.completed_at = datetime.now(timezone.utc)
            
        except Exception as e:
            # Update failure
            post_platform.status = PostStatus.FAILED
            post_platform.error_message = str(e)
            post_platform.completed_at = datetime.now(timezone.utc)
        
        await db.commit()
    
    @staticmethod
    async def _post_facebook(
        db: AsyncSession,
        config: Dict[str, any],
        content: Optional[str],
        image_url: Optional[str]
    ) -> Dict[str, str]:
        """Post to Facebook"""
        page_id = config["page_account_id"]
        result = await db.execute(select(PageAccount).where(PageAccount.id == page_id))
        page = result.scalars().first()
        
        page_token = decrypt_token(page.page_access_token)
        
        return await FacebookPostingService.post_to_page(
            page_id=page.page_id,
            page_access_token=page_token,
            message=content or "",
            image_url=image_url
        )
    
    @staticmethod
    async def _post_instagram(
        db: AsyncSession,
        config: Dict[str, any],
        content: Optional[str],
        image_url: Optional[str]
    ) -> Dict[str, str]:
        """Post to Instagram"""
        if not image_url:
            raise Exception("Instagram requires an image")
        
        page_id = config["page_account_id"]
        result = await db.execute(select(PageAccount).where(PageAccount.id == page_id))
        page = result.scalars().first()
        
        page_token = decrypt_token(page.page_access_token)
        
        return await InstagramPostingService.post_image(
            instagram_account_id=page.instagram_account_id,
            page_access_token=page_token,
            image_url=image_url,
            caption=content or ""
        )
    
    @staticmethod
    async def _post_twitter(
        db: AsyncSession,
        config: Dict[str, any],
        content: Optional[str],
        image_url: Optional[str]
    ) -> Dict[str, str]:
        """Post to Twitter"""
        if not content:
            raise Exception("Twitter requires content")
        
        social_id = config["social_account_id"]
        result = await db.execute(
            select(SocialAccount).where(SocialAccount.id == social_id)
        )
        account = result.scalars().first()
        
        access_token = await TokenRefreshService.refresh_if_needed(db, account)
        
        # Convert single image_url to array for Twitter
        image_urls = [image_url] if image_url else None
        
        return await TwitterPostingService.post_tweet(
            access_token=access_token,
            text=content,
            image_urls=image_urls
        )
    
    @staticmethod
    async def _post_linkedin(
        db: AsyncSession,
        config: Dict[str, any],
        content: Optional[str],
        image_url: Optional[str]
    ) -> Dict[str, str]:
        """Post to LinkedIn"""
        if not content:
            raise Exception("LinkedIn requires content")
        
        social_id = config["social_account_id"]
        result = await db.execute(
            select(SocialAccount).where(SocialAccount.id == social_id)
        )
        account = result.scalars().first()
        
        access_token = decrypt_token(account.access_token)
        
        return await LinkedInPostingService.create_post(
            access_token=access_token,
            text=content,
            image_url=image_url
        )
    
    @staticmethod
    async def get_post_status(db: AsyncSession, post_id: int, user_id: int) -> Dict:
        """Get post status with all platform statuses"""
        # Get post
        result = await db.execute(
            select(Post).where(Post.id == post_id, Post.user_id == user_id)
        )
        post = result.scalars().first()
        
        if not post:
            return None
        
        # Get platform statuses
        result = await db.execute(
            select(PostPlatform).where(PostPlatform.post_id == post_id)
        )
        platforms = result.scalars().all()
        
        return {
            "id": post.id,
            "content": post.content,
            "image_url": post.image_url,
            "status": post.status,
            "scheduled_at": post.scheduled_at.isoformat() if post.scheduled_at else None,
            "created_at": post.created_at.isoformat() if post.created_at else None,
            "platforms": [
                {
                    "platform": p.platform,
                    "account_name": p.account_name,
                    "status": p.status.value,
                    "post_id": p.platform_post_id,
                    "platform_url": p.platform_url,
                    "error": p.error_message,
                    "queued_at": p.queued_at.isoformat() if p.queued_at else None,
                    "started_at": p.started_at.isoformat() if p.started_at else None,
                    "completed_at": p.completed_at.isoformat() if p.completed_at else None
                }
                for p in platforms
            ]
        }
