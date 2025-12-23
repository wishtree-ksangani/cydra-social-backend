"""Posting validators - Pre-post validation checks"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

from app.models.social_account import SocialAccount
from app.models.page_account import PageAccount
from app.core.encryption import decrypt_token
from app.services.facebook import FacebookPagesService


class PostingValidator:
    """Validates posting requests before sending to social media platforms"""
    
    @staticmethod
    async def validate_post_request(
        db: AsyncSession,
        user_id: int,
        page_account_id: int,
        platform: str,
        content: str = None,
        image_url: str = None
    ) -> tuple[PageAccount, str]:
        """
        Validate a posting request.
        
        Args:
            db: Database session
            user_id: ID of the user making the request
            page_account_id: ID of the page account to post to
            platform: Platform to post to ("facebook" or "instagram")
            content: Post content/caption
            image_url: Image URL (required for Instagram)
            
        Returns:
            Tuple of (PageAccount, decrypted_page_token)
            
        Raises:
            HTTPException: If validation fails
        """
        # Get the page account
        result = await db.execute(
            select(PageAccount).where(PageAccount.id == page_account_id)
        )
        page_account = result.scalars().first()
        
        if not page_account:
            raise HTTPException(status_code=404, detail="Page not found")
        
        # Verify ownership through social account
        result = await db.execute(
            select(SocialAccount).where(
                SocialAccount.id == page_account.social_account_id,
                SocialAccount.user_id == user_id
            )
        )
        social_account = result.scalars().first()
        
        if not social_account:
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this page"
            )
        
        # Check if social account is active
        if not social_account.is_active:
            raise HTTPException(
                status_code=400,
                detail="Social account is disconnected. Please reconnect your Facebook account."
            )
        
        # Check if page is active
        if not page_account.is_active:
            raise HTTPException(
                status_code=400,
                detail="Page access has been revoked. Please refresh your pages."
            )
        
        # Validate platform capability
        if platform == "facebook" and not page_account.can_post_to_facebook:
            raise HTTPException(
                status_code=400,
                detail="This page cannot post to Facebook"
            )
        elif platform == "instagram" and not page_account.can_post_to_instagram:
            raise HTTPException(
                status_code=400,
                detail="This page doesn't have Instagram linked. Please link an Instagram Business account."
            )
        
        # Validate content requirements
        if platform == "instagram":
            if not image_url:
                raise HTTPException(
                    status_code=400,
                    detail="Instagram posts require an image URL"
                )
            # Validate image URL is accessible
            import httpx
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.head(image_url, timeout=5.0)
                    if response.status_code != 200:
                        raise HTTPException(
                            status_code=400,
                            detail="Image URL is not accessible"
                        )
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to validate image URL: {str(e)}"
                )
        
        # Decrypt page token
        try:
            page_token = decrypt_token(page_account.page_access_token)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail="Failed to decrypt access token"
            )
        
        # Note: We don't validate the token here because:
        # 1. Page tokens are long-lived and rarely expire
        # 2. The posting API will return a clear error if token is invalid
        # 3. Pre-validation adds latency and can cause false positives
        
        return page_account, page_token
