"""Background scheduler for processing scheduled posts"""

import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.post import Post, PostPlatform, PostStatus
from app.services.posting.multi_platform import MultiPlatformPostingService


class PostScheduler:
    """Background scheduler for processing scheduled posts"""
    
    _running = False
    _task = None
    
    @classmethod
    async def start(cls):
        """Start the scheduler"""
        if cls._running:
            return
        
        cls._running = True
        cls._task = asyncio.create_task(cls._run())
        print("📅 Post scheduler started")
    
    @classmethod
    async def stop(cls):
        """Stop the scheduler"""
        cls._running = False
        if cls._task:
            cls._task.cancel()
            try:
                await cls._task
            except asyncio.CancelledError:
                pass
        print("📅 Post scheduler stopped")
    
    @classmethod
    async def _run(cls):
        """Main scheduler loop"""
        from app.core.config import settings
        
        while cls._running:
            try:
                await cls._process_scheduled_posts()
            except Exception as e:
                print(f"❌ Scheduler error: {e}")
            
            # Check at configured interval
            await asyncio.sleep(settings.SCHEDULER_INTERVAL_SECONDS)
    
    @classmethod
    async def _process_scheduled_posts(cls):
        """Process all scheduled posts that are due"""
        async for db in get_db():
            try:
                # Find scheduled posts that are due
                now = datetime.now(timezone.utc)
                
                result = await db.execute(
                    select(Post).where(
                        Post.is_scheduled == 1,
                        Post.scheduled_at <= now
                    )
                )
                due_posts = result.scalars().all()
                
                for post in due_posts:
                    print(f"📤 Processing scheduled post {post.id}")
                    
                    # Get platform configurations
                    result = await db.execute(
                        select(PostPlatform).where(
                            PostPlatform.post_id == post.id,
                            PostPlatform.status == PostStatus.QUEUED
                        )
                    )
                    platforms = result.scalars().all()
                    
                    if not platforms:
                        # Mark as processed
                        post.is_scheduled = 0
                        await db.commit()
                        continue
                    
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
                    
                    # Process platforms
                    await MultiPlatformPostingService._process_platforms(
                        post.id,
                        platforms,
                        post.content,
                        post.image_url,
                        platform_configs
                    )
                    
                    # Mark as processed
                    post.is_scheduled = 0
                    await db.commit()
                    
                    print(f"✅ Scheduled post {post.id} processed")
                
            except Exception as e:
                print(f"❌ Error processing scheduled posts: {e}")
            finally:
                break
