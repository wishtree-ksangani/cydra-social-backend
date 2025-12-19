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
    """
    __tablename__ = "posts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    
    # Content
    content = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=True)  # Single image URL
    
    # Scheduling
    scheduled_at = Column(DateTime(timezone=True), nullable=True)  # When to post (NULL = immediate)
    is_scheduled = Column(Integer, default=0)  # 0 = immediate, 1 = scheduled
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PostPlatform(Base):
    """
    PostPlatform model - Tracks individual platform posting status
    
    Each platform has its own status, post_id, and error tracking
    """
    __tablename__ = "post_platforms"
    
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, nullable=False, index=True)  # FK to posts.id
    
    # Platform info
    platform = Column(String(50), nullable=False)  # facebook, instagram, twitter, linkedin
    account_id = Column(Integer, nullable=False)  # page_account_id or social_account_id
    account_name = Column(String(255), nullable=True)
    
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
