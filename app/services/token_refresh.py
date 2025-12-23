"""Token refresh helper - Automatically refresh expired tokens"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.models.social_account import SocialAccount
from app.core.encryption import encrypt_token, decrypt_token
from app.services.oauth.factory import get_oauth_provider


class TokenRefreshService:
    """Service to handle automatic token refresh"""
    
    @staticmethod
    async def refresh_if_needed(
        db: AsyncSession,
        social_account: SocialAccount
    ) -> Optional[str]:
        """
        Check if token needs refresh and refresh if necessary.
        
        Args:
            db: Database session
            social_account: Social account to check
            
        Returns:
            Decrypted access token (refreshed if needed)
        """
        # Decrypt current token
        access_token = decrypt_token(social_account.access_token)
        
        # Check if token is expired or about to expire (within 5 minutes)
        if social_account.token_expires_at:
            now = datetime.now(timezone.utc)
            # Make token_expires_at timezone-aware if it isn't
            expires_at = social_account.token_expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            
            # Refresh if expired or expiring soon (5 min buffer)
            time_until_expiry = (expires_at - now).total_seconds()
            
            if time_until_expiry < 300:  # Less than 5 minutes
                # Token expired or expiring soon, refresh it
                if not social_account.refresh_token:
                    # No refresh token available
                    raise Exception(
                        f"{social_account.platform} token expired and no refresh token available. "
                        "Please reconnect your account."
                    )
                
                # Decrypt refresh token
                refresh_token = decrypt_token(social_account.refresh_token)
                
                # Get OAuth provider
                provider = get_oauth_provider(social_account.platform)
                
                # Refresh the token
                try:
                    token_data = await provider.refresh_access_token(refresh_token)
                    
                    # Update social account with new tokens
                    social_account.access_token = encrypt_token(token_data["access_token"])
                    
                    if token_data.get("refresh_token"):
                        social_account.refresh_token = encrypt_token(token_data["refresh_token"])
                    
                    if token_data.get("expires_in"):
                        social_account.token_expires_at = datetime.now(timezone.utc).replace(
                            microsecond=0
                        ) + timedelta(seconds=token_data["expires_in"])
                    
                    await db.commit()
                    await db.refresh(social_account)
                    
                    # Return new access token
                    access_token = token_data["access_token"]
                    
                    print(f"✅ Refreshed {social_account.platform} token for user {social_account.user_id}")
                    
                except Exception as e:
                    print(f"❌ Failed to refresh {social_account.platform} token: {str(e)}")
                    raise Exception(
                        f"Failed to refresh {social_account.platform} token. "
                        "Please reconnect your account."
                    )
        
        return access_token
