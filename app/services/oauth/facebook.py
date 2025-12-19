import httpx
from urllib.parse import urlencode
from typing import Dict
from app.services.oauth.base import BaseOAuthProvider
from app.core.config import settings
from app.core.oauth_constants import FacebookOAuthURLs


class FacebookOAuthProvider(BaseOAuthProvider):
    """
    Facebook/Instagram OAuth 2.0 provider.
    Uses Facebook Graph API for both Facebook and Instagram Business accounts.
    """
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        super().__init__(client_id, client_secret, redirect_uri)
        # Use configurable scopes from settings
        self.scopes = settings.facebook_scopes_list
        # Get URLs from centralized constants
        self.authorization_url = FacebookOAuthURLs.get_authorization_url()
        self.token_url = FacebookOAuthURLs.get_token_url()
        self.user_info_url = FacebookOAuthURLs.get_user_info_url()
    
    def get_authorization_url(self, state: str) -> str:
        """Generate Facebook OAuth authorization URL."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": f"{self.redirect_uri}/api/v1/oauth/callback/facebook",
            "state": state,
            "scope": ",".join(self.scopes),
            "response_type": "code",
        }
        return f"{self.authorization_url}?{urlencode(params)}"
    
    async def exchange_code_for_token(self, code: str) -> Dict[str, any]:
        """Exchange authorization code for access token."""
        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": f"{self.redirect_uri}/api/v1/oauth/callback/facebook",
            "code": code,
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(self.token_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            return {
                "access_token": data["access_token"],
                "token_type": data.get("token_type", "bearer"),
                "expires_in": data.get("expires_in"),
                "refresh_token": None,  # Facebook uses long-lived tokens
            }
    
    async def exchange_for_long_lived_token(self, short_lived_token: str) -> Dict[str, any]:
        """
        Exchange short-lived user token for long-lived token (60 days).
        
        Args:
            short_lived_token: Short-lived access token from OAuth
            
        Returns:
            Long-lived token data with 60-day expiration
        """
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "fb_exchange_token": short_lived_token,
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(self.token_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            return {
                "access_token": data["access_token"],
                "token_type": data.get("token_type", "bearer"),
                "expires_in": data.get("expires_in", 5184000),  # 60 days default
            }
    
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, any]:
        """
        Facebook doesn't use refresh tokens.
        Instead, exchange short-lived token for long-lived token.
        """
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "fb_exchange_token": refresh_token,  # Actually the access token
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(self.token_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            return {
                "access_token": data["access_token"],
                "token_type": data.get("token_type", "bearer"),
                "expires_in": data.get("expires_in"),
                "refresh_token": None,
            }
    
    async def get_user_info(self, access_token: str) -> Dict[str, any]:
        """Get Facebook user profile information."""
        params = {
            "fields": "id,name,email",
            "access_token": access_token,
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(self.user_info_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            return {
                "user_id": data["id"],
                "username": data.get("name", ""),
                "name": data.get("name", ""),
                "email": data.get("email"),
            }
