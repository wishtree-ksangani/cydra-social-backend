from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class PageAccount(Base):
    """
    Facebook Pages and Instagram Business accounts.
    
    Each record represents either:
    - A Facebook Page (can_post_to_facebook=True)
    - An Instagram Business account linked to a Facebook Page (can_post_to_instagram=True)
    
    A single Facebook Page can have both capabilities if it has Instagram linked.
    """
    __tablename__ = "page_accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    social_account_id = Column(Integer, ForeignKey("social_accounts.id"), nullable=False)
    
    # Facebook Page Information
    page_id = Column(String(255), nullable=False, index=True)
    page_name = Column(String(255))
    page_access_token = Column(Text, nullable=False)  # Encrypted, never expires
    
    # Instagram Information (optional - only if page has Instagram linked)
    instagram_account_id = Column(String(255), nullable=True)
    instagram_username = Column(String(255), nullable=True)
    
    # Posting Capabilities
    can_post_to_facebook = Column(Boolean, default=True, nullable=False)
    can_post_to_instagram = Column(Boolean, default=False, nullable=False)
    
    # User Selection (which page to use for posting)
    is_selected_for_facebook = Column(Boolean, default=False, nullable=False)
    is_selected_for_instagram = Column(Boolean, default=False, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    last_validated_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    social_account = relationship("SocialAccount", back_populates="page_accounts")
