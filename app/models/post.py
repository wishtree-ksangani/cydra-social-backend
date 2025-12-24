"""Post tracking model - Track multi-platform post status"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Enum as SQLEnum, JSON
from sqlalchemy.sql import func
from datetime import datetime
import enum

from app.core.database import Base


class PostStatus(str, enum.Enum):
    """Post status enum"""
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Post(Base):
    """
    Post model - Tracks posts across multiple platforms
    
    A single Post can have multiple PostPlatform entries (one per platform)
    Content is stored per-platform in PostPlatform, not here.
    """
    __tablename__ = "posts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    
    # Generation inputs (original context for regeneration)
    topic = Column(String(500), nullable=True)  # What the content is about
    tone = Column(String(100), nullable=True)  # Tone used for generation
    hashtag = Column(String(500), nullable=True)  # Hashtags provided
    
    # Status: draft | scheduled | publishing | published | failed
    status = Column(String(50), default="draft", nullable=False)
    
    # Scheduling
    scheduled_at = Column(DateTime(timezone=True), nullable=True)  # When to post
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())



class PostPlatform(Base):
    """
    PostPlatform model - Tracks individual platform posting status
    
    Each platform has its own content, image, status, and error tracking
    """
    __tablename__ = "post_platforms"
    
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, nullable=False, index=True)  # FK to posts.id
    
    # Platform info
    platform = Column(String(50), nullable=False)  # facebook, instagram, twitter, linkedin
    account_id = Column(Integer, nullable=False)  # page_account_id or social_account_id
    account_name = Column(String(255), nullable=True)
    
    # Content for this platform (each platform has its own content)
    content = Column("platform_content", Text, nullable=True)  # Post content for this platform
    image_url = Column("platform_image_url", String(500), nullable=True)  # Image URL for this platform

    
    # Status tracking
    status = Column(SQLEnum(PostStatus), default=PostStatus.QUEUED, nullable=False)
    
    # Results
    platform_post_id = Column(String(255), nullable=True)  # ID from the platform
    platform_url = Column(String(500), nullable=True)  # URL to view the post
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    queued_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
