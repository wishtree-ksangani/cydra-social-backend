"""Facebook Pages Service - Fetch and manage Facebook Pages and Instagram accounts"""

import httpx
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models.page_account import PageAccount
from app.models.social_account import SocialAccount
from app.core.config import settings
from app.core.encryption import encrypt_token


class FacebookPagesService:
    """Service for managing Facebook Pages and Instagram Business accounts"""
    
    @staticmethod
    async def fetch_user_pages(user_access_token: str) -> List[Dict]:
        """
        Fetch all Facebook Pages that the user manages.
        
        Args:
            user_access_token: User's Facebook access token
            
        Returns:
            List of pages with their access tokens
        """
        url = f"https://graph.facebook.com/{settings.FACEBOOK_API_VERSION}/me/accounts"
        params = {
            "access_token": user_access_token,
            "fields": "id,name,access_token"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            return data.get("data", [])
    
    @staticmethod
    async def get_page_instagram_account(page_id: str, page_access_token: str) -> Optional[Dict]:
        """
        Check if a Facebook Page has an Instagram Business account linked.
        
        Args:
            page_id: Facebook Page ID
            page_access_token: Page's access token
            
        Returns:
            Instagram account info if linked, None otherwise
        """
        url = f"https://graph.facebook.com/{settings.FACEBOOK_API_VERSION}/{page_id}"
        params = {
            "fields": "instagram_business_account",
            "access_token": page_access_token
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                # If page has Instagram linked, fetch the account details
                if "instagram_business_account" in data:
                    ig_account_id = data["instagram_business_account"]["id"]
                    
                    # Fetch Instagram account username
                    ig_url = f"https://graph.facebook.com/{settings.FACEBOOK_API_VERSION}/{ig_account_id}"
                    ig_params = {
                        "fields": "username",
                        "access_token": page_access_token
                    }
                    
                    ig_response = await client.get(ig_url, params=ig_params)
                    ig_response.raise_for_status()
                    ig_data = ig_response.json()
                    
                    return {
                        "id": ig_account_id,
                        "username": ig_data.get("username")
                    }
                
                return None
        except Exception as e:
            # Log error but don't fail - page just doesn't have Instagram
            print(f"Could not fetch Instagram account for page {page_id}: {str(e)}")
            return None
    
    @staticmethod
    async def fetch_and_save_pages(
        db: AsyncSession,
        social_account_id: int,
        user_access_token: str
    ) -> List[PageAccount]:
        """
        Fetch pages from Facebook and save/update them in the database.
        
        Args:
            db: Database session
            social_account_id: ID of the social account
            user_access_token: User's Facebook access token
            
        Returns:
            List of saved PageAccount objects
        """
        # Fetch pages from Facebook
        pages = await FacebookPagesService.fetch_user_pages(user_access_token)
        
        saved_pages = []
        
        for page in pages:
            page_id = page["id"]
            page_name = page["name"]
            page_token = page["access_token"]
            
            # Check if page has Instagram linked
            instagram_account = await FacebookPagesService.get_page_instagram_account(
                page_id, page_token
            )
            
            # Check if page already exists
            result = await db.execute(
                select(PageAccount).where(
                    PageAccount.social_account_id == social_account_id,
                    PageAccount.page_id == page_id
                )
            )
            existing_page = result.scalars().first()
            
            if existing_page:
                # Update existing page
                existing_page.page_name = page_name
                existing_page.page_access_token = encrypt_token(page_token)
                existing_page.instagram_account_id = instagram_account["id"] if instagram_account else None
                existing_page.instagram_username = instagram_account["username"] if instagram_account else None
                existing_page.can_post_to_instagram = instagram_account is not None
                existing_page.is_active = True
                existing_page.last_validated_at = datetime.utcnow()
                existing_page.updated_at = datetime.utcnow()
                saved_pages.append(existing_page)
            else:
                # Create new page
                new_page = PageAccount(
                    social_account_id=social_account_id,
                    page_id=page_id,
                    page_name=page_name,
                    page_access_token=encrypt_token(page_token),
                    instagram_account_id=instagram_account["id"] if instagram_account else None,
                    instagram_username=instagram_account["username"] if instagram_account else None,
                    can_post_to_facebook=True,
                    can_post_to_instagram=instagram_account is not None,
                    is_active=True,
                    last_validated_at=datetime.utcnow()
                )
                db.add(new_page)
                saved_pages.append(new_page)
        
        await db.commit()
        
        # Refresh to get IDs for new pages
        for page in saved_pages:
            await db.refresh(page)
        
        # Auto-select first page if none selected
        if saved_pages:
            result = await db.execute(
                select(PageAccount).where(
                    PageAccount.social_account_id == social_account_id,
                    PageAccount.is_selected_for_facebook == True
                )
            )
            if not result.scalars().first():
                saved_pages[0].is_selected_for_facebook = True
                
                # Also select for Instagram if available
                if saved_pages[0].can_post_to_instagram:
                    saved_pages[0].is_selected_for_instagram = True
                
                await db.commit()
        
        return saved_pages
    
    @staticmethod
    async def validate_page_token(page_access_token: str) -> bool:
        """
        Validate if a page access token is still valid.
        
        Args:
            page_access_token: Page's access token
            
        Returns:
            True if valid, False otherwise
        """
        url = f"https://graph.facebook.com/{settings.FACEBOOK_API_VERSION}/me"
        params = {"access_token": page_access_token}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return True
        except:
            return False
